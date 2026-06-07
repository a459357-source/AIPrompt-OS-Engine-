#!/usr/bin/env python3
"""
run.py — Prompt OS Galgame Runtime v1 — Main Entry Point
==========================================================
Orchestrates the interactive narrative engine.  Three modes:

  auto  python engine/run.py --mode auto --loop N   # auto-run N turns
  cli   python engine/run.py --mode cli              # interactive CLI
  web   python engine/run.py --mode web              # FastAPI server

Each turn:
  1. Build the prompt from YAML state, memory, and last choice
  2. Call DeepSeek API
  3. Validate & apply the response to session state
  4. Update story graph and character memory
  5. Write output/chapter.md  (Obsidian-compatible)
  6. (CLI/Web) Show options and wait for player choice
"""

import argparse
import json
import logging
import sys
import threading
import time
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable, Any

# Ensure the project root (prompt-os-engine/) is on sys.path so that
# `import config` and `from engine import ...` work regardless of cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine import io_utils
from engine.builder import build_prompt
from engine.deepseek_client import call_deepseek, DeepSeekError
from engine.state_manager import apply_turn, validate_response
from engine.router import load_graph, save_graph, get_current_node, append_node
from engine.memory import (
    load_memory, save_memory, update_trust, set_flag,
    get_context_for_prompt, guess_trust_delta_from_story,
    parse_option_trust_deltas, detect_new_characters_from_story,
    get_initial_trust,
    init_factions, update_faction_reputation, set_faction_flag,
    init_faction_attitudes, update_faction_attitude,
    assign_character_tier, degrade_inactive_characters,
    build_character_tier_context, promote_to_core, remove_core_status,
)
from engine.events import (
    init_events, check_event_triggers, seed_default_events,
    get_event_context,
)
from engine.world_driver import passive_faction_drift
from engine.save_manager import autosave as do_autosave
from engine import obsidian_live
from engine.state_store import load_runtime, commit_runtime, begin_transaction, end_transaction

# ── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run")

# _prev_options removed — previous-turn options are now read from
# session_state.history[-1]["options"] inside _update_memory,
# eliminating the module-level global that was not thread-safe.


# ── Safe call wrapper ──────────────────────────────────────────────

def _safe_call(fn: Callable, label: str, *args: Any, **kwargs: Any) -> bool:
    """Call *fn* and return True.  On any exception, log the full
    traceback to error.log + console and return False — never raise.

    Use for non-critical post-turn steps where one subsystem failure
    must not crash the entire turn.
    """
    try:
        fn(*args, **kwargs)
        return True
    except Exception:
        logger.error(
            "❌ %s 失败（非致命，继续执行）:\n%s",
            label, traceback.format_exc(),
        )
        return False


# ── Core step (stateless, for web/cli reuse) ───────────────────────

_last_step_error: str = ""
_last_autosave_ts: float = 0.0


def _should_autosave_now() -> bool:
    """Respect auto_save_interval (0 = disabled)."""
    interval = config.AUTO_SAVE_INTERVAL
    if interval <= 0:
        return False
    global _last_autosave_ts
    now = time.time()
    if _last_autosave_ts <= 0 or (now - _last_autosave_ts) >= interval:
        _last_autosave_ts = now
        return True
    return False


def _maybe_retry_repetition(
    response: dict,
    system_prompt: str,
    user_prompt: str,
    history: list,
) -> dict:
    from engine.repetition import check_story_repetition

    story = response.get("story", "")
    repetitive, reason = check_story_repetition(story, history, config.REPETITION_CHECK)
    if not repetitive:
        return response

    logger.warning("⚠️ 正文重复检测: %s", reason)
    if config.REPETITION_CHECK != "strict":
        return response

    retry_user = (
        f"{user_prompt}\n\n"
        f"【反重复 — 必须遵守】{reason}。请重写本轮 story，"
        f"不得复述上一轮情节，必须推进新事件或新信息。"
    )
    try:
        return call_deepseek(system_prompt, retry_user)
    except DeepSeekError as exc:
        logger.warning("重复检测重试失败，保留首轮结果: %s", exc)
        return response


def get_last_step_error() -> str:
    """Human-readable reason for the most recent step() failure."""
    return _last_step_error


def _count_story_chars(text: str) -> int:
    """Count story body chars (ignore whitespace), matching frontend badge."""
    return len(text.replace(" ", "").replace("\n", "").replace("\r", ""))


def step(choice: str | None = None) -> dict | None:
    """
    Execute one turn: generate story + options, apply to state,
    update graph & memory.  Returns the response dict (story, options,
    state) plus metadata, or None on failure.

    Args:
        choice: The player's selection for THIS generation (A/B/C/D or custom text),
                or None for the opening turn.
    """
    global _last_step_error
    _last_step_error = ""
    logger.info("═══ TURN START ═══ choice=%s", choice or "—")

    from ui.routes.settings import pop_pending_gen_settings_note

    settings_note = pop_pending_gen_settings_note()
    if settings_note:
        logger.info("📌 本轮使用刚修改的快捷设置: %s", settings_note)

    runtime = load_runtime(clear_cache=True)
    begin_transaction()

    # 1. Build prompt
    try:
        system_prompt, user_prompt = build_prompt(current_choice=choice)
    except Exception as exc:
        end_transaction()
        _last_step_error = f"构建提示词失败: {exc}"
        logger.error("Failed to build prompt: %s", exc)
        return None

    target_len = config.STORY_LENGTH
    min_len = config.min_story_length_for_target(target_len)
    max_len = config.max_story_length_for_target(target_len)
    logger.info(
        "📋 生成参数: 目标字数=%d 至少=%d 最多=%d 最大Token=%d 自动压缩=%s 压缩阈值=%d 上下文消息=%d",
        target_len,
        min_len,
        max_len,
        config.MAX_TOKENS,
        config.AUTO_COMPRESS,
        config.COMPRESS_THRESHOLD,
        config.MAX_CONTEXT_MESSAGES,
    )

    # 2. Call DeepSeek
    try:
        response = call_deepseek(system_prompt, user_prompt)
    except DeepSeekError as exc:
        end_transaction()
        _last_step_error = str(exc)
        logger.error("DeepSeek API error: %s", exc)
        return None

    story_chars = _count_story_chars(response.get("story", ""))
    if story_chars > max_len:
        logger.warning(
            "⚠️ 正文字数超出上限: 实际=%d > 最多=%d（目标=%d），尝试一次压缩重写",
            story_chars,
            max_len,
            target_len,
        )
        retry_user = (
            f"{user_prompt}\n\n"
            f"【字数修正 — 必须遵守】上一轮 story 约 {story_chars} 字，超出上限 {max_len} 字。"
            f"请重写本轮：story 正文必须在 {min_len}–{max_len} 字之间，目标约 {target_len} 字，"
            f"精简描写与对话，宁可略短也不要超长。"
        )
        try:
            response = call_deepseek(system_prompt, retry_user)
            retry_chars = _count_story_chars(response.get("story", ""))
            logger.info(
                "📊 字数重试: 原=%d 重试后=%d 上限=%d",
                story_chars,
                retry_chars,
                max_len,
            )
            story_chars = retry_chars
        except DeepSeekError as exc:
            logger.warning("字数重试失败，保留首轮结果: %s", exc)

    pre_state = runtime.session
    response = _maybe_retry_repetition(
        response, system_prompt, user_prompt, pre_state.get("history", []),
    )

    # 3. Validate
    warnings = validate_response(response)
    for w in warnings:
        logger.warning("Validation: %s", w)

    # 4. Apply to state (record choice with the story we just generated)
    prev_chapter = pre_state.get("chapter", 1)
    try:
        new_state = apply_turn(response, choice, session=runtime.session, persist=False)
        runtime.session = new_state
    except Exception as exc:
        end_transaction()
        _last_step_error = f"写入游戏状态失败: {exc}"
        logger.error("Failed to apply turn: %s", exc)
        return None

    # 5-12. Non-critical post-turn steps — each wrapped so one failure
    #       doesn't crash the whole turn.  Full tracebacks go to error.log.
    _safe_call(_update_graph, "story graph update",
               response, new_state, choice, runtime.graph)
    _safe_call(_update_memory, "character memory update",
               response, new_state, choice, runtime.memory)

    try:
        commit_runtime(runtime)
    except Exception as exc:
        end_transaction()
        _last_step_error = f"提交游戏状态失败: {exc}"
        logger.error("Failed to commit runtime: %s", exc)
        return None
    end_transaction()

    _safe_call(_write_chapter, "chapter.md write",
               response, new_state, choice)
    _safe_call(_write_dashboard_html, "dashboard HTML write")
    _safe_call(obsidian_live.on_turn, "Obsidian live export",
               response, new_state, choice)
    _safe_call(_log_turn, "turn log append", response, choice)
    if _should_autosave_now():
        _safe_call(do_autosave, "autosave")
    else:
        logger.debug("Autosave skipped (interval=%ss)", config.AUTO_SAVE_INTERVAL)
    _safe_call(_maybe_auto_export, "auto export", response, new_state, choice, prev_chapter)

    # Clear cache after all post-turn steps to ensure next turn reads fresh data
    io_utils.clear_cache()

    story_text = response.get("story", "")
    story_chars = _count_story_chars(story_text)
    gap = story_chars - target_len
    pct = (story_chars / target_len * 100) if target_len else 0
    logger.info(
        "📊 本轮生成明细: turn=%s choice=%s | 目标=%d 范围=%d-%d 实际=%d (%d%%) 差距=%+d | max_tokens=%d",
        new_state.get("turn", "?"),
        choice or "—",
        target_len,
        min_len,
        max_len,
        story_chars,
        int(pct),
        gap,
        config.MAX_TOKENS,
    )
    if story_chars < min_len:
        logger.warning(
            "⚠️ 正文字数低于下限: 实际=%d < 至少=%d（目标=%d），可在 app.log 查看完整参数",
            story_chars,
            min_len,
            target_len,
        )
    elif story_chars > max_len:
        logger.warning(
            "⚠️ 正文字数仍超出上限: 实际=%d > 最多=%d（目标=%d）",
            story_chars,
            max_len,
            target_len,
        )

    logger.info("═══ TURN COMPLETE ═══")

    return {
        "story": response.get("story", ""),
        "options": response.get("options", []),
        "state": new_state,
        "turn": new_state.get("turn", 0),
        "status": new_state.get("status", "?"),
        "scene": new_state.get("scene", "?"),
    }


# ── Interactive CLI mode ───────────────────────────────────────────

def run_interactive() -> None:
    """Run the Galgame Runtime in interactive CLI mode."""
    from ui.cli_ui import (
        show_banner, show_turn_header, show_story, show_options,
        get_user_choice, show_goodbye, show_divider,
    )
    # Pull in ANSI helpers for inline messages
    from ui.cli_ui import _c, _GREEN, _YELLOW, _DIM, _BOLD
    from engine.save_manager import save, load, list_saves
    from engine.router import load_graph, get_path_to_root

    show_banner()

    choice: str | None = None  # first turn has no prior choice

    while True:
        # Generate the next turn
        result = step(choice)

        if result is None:
            print("❌ 生成失败，请检查 API key 和网络连接。")
            break

        # Display
        show_turn_header(result["turn"], result["status"], result["scene"])
        show_story(result["story"])
        show_options(result["options"])

        # Get player input
        next_choice = get_user_choice()

        if next_choice == "Q":
            show_goodbye()
            break

        # ── Save / Load / Graph commands ────────────────────────
        if next_choice in ("S1", "S2", "S3"):
            slot_map = {"S1": "slot1", "S2": "slot2", "S3": "slot3"}
            slot = slot_map[next_choice]
            s = save(slot)
            if s:
                print(_c(f"  ✅ 已保存到 {slot}（第 {s['turn']} 轮，{s['scene']}）", _GREEN))
            else:
                print(_c(f"  ❌ 保存到 {slot} 失败", _YELLOW))
            show_divider()
            continue  # stay on same turn

        if next_choice in ("L1", "L2", "L3"):
            slot_map = {"L1": "slot1", "L2": "slot2", "L3": "slot3"}
            slot = slot_map[next_choice]
            if load(slot):
                print(_c(f"  ✅ 已从 {slot} 读取存档。正在重新生成当前回合…", _GREEN))
                choice = None  # re-read state from loaded file
            else:
                print(_c(f"  ❌ {slot} 没有存档数据", _YELLOW))
            show_divider()
            continue

        if next_choice == "G":
            _print_graph_summary()
            show_divider()
            continue  # stay on same turn

        if next_choice == "O":
            _obsidian_setup()
            show_divider()
            continue  # stay on same turn

        show_divider()
        choice = next_choice


# ── Auto mode (backward-compatible) ────────────────────────────────

def run_one_turn() -> bool:
    """
    Execute one full turn in auto mode (no user input).
    Delegates to step() — no duplicated pipeline.
    Returns True on success, False on failure.
    """
    result = step(None)  # choice=None → auto mode
    if result is None:
        return False
    # Auto mode extras: console summary
    try:
        new_state = io_utils.read_yaml(config.SESSION_STATE_PATH)
        _print_summary(
            {"story": result["story"], "options": result["options"],
             "state": result["state"]},
            new_state,
        )
    except Exception:
        logger.error("Failed to print summary:\n%s", traceback.format_exc())
    return True


def run_loop(n: int) -> int:
    """Run N turns in auto mode; return the number of successful turns."""
    ok = 0
    for i in range(1, n + 1):
        logger.info("─" * 40)
        logger.info("Turn %d / %d", i, n)
        if run_one_turn():
            ok += 1
        else:
            logger.error("Turn %d FAILED — stopping loop.", i)
            break
    return ok


# ── Web mode ───────────────────────────────────────────────────────

def _open_browser(host: str, port: int) -> None:
    """Open the React UI in the default browser after the API server is ready."""
    ui_url = config.frontend_url()
    api_url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}"

    def _open():
        import time
        import socket
        # Wait up to 10s for the API server to start listening
        for _ in range(20):
            time.sleep(0.5)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect(('127.0.0.1', port))
                s.close()
                break  # server is ready
            except (ConnectionRefusedError, OSError):
                continue
        logger.info("Opening browser → %s (API: %s)", ui_url, api_url)
        try:
            webbrowser.open(ui_url)
        except Exception as exc:
            logger.warning("Failed to open browser: %s", exc)
            logger.info("Please open %s manually (API: %s)", ui_url, api_url)
    threading.Thread(target=_open, daemon=True).start()


def run_web(host: str = "0.0.0.0", port: int = 8000, no_browser: bool = False) -> None:
    """Start the FastAPI web server."""
    try:
        import uvicorn
    except ImportError:
        logger.error(
            "uvicorn not installed. Run: pip install uvicorn fastapi jinja2"
        )
        sys.exit(1)

    # Auto-open browser after server starts
    if not no_browser:
        _open_browser(host, port)

    logger.info("API backend → http://%s:%d", host, port)
    logger.info("React UI → %s  (cd frontend && npm run dev)", config.frontend_url())
    uvicorn.run("ui.web_app:app", host=host, port=port, reload=False)


# ── Output helpers ─────────────────────────────────────────────────

def _write_dashboard_html() -> None:
    """Write the analytics dashboard HTML to output/ (no Obsidian needed)."""
    try:
        from engine.dashboard import write_standalone
        write_standalone()
    except Exception:
        logger.error("Failed to write dashboard HTML:\n%s", traceback.format_exc())


def _maybe_auto_export(
    response: dict,
    state: dict,
    choice: str | None,
    prev_chapter: int,
) -> None:
    mode = config.AUTO_EXPORT
    if mode == "off":
        return
    from engine.story_export import export_turn

    new_chapter = state.get("chapter", prev_chapter)
    if mode == "turn":
        export_turn(response, state, choice)
    elif mode == "chapter" and new_chapter > prev_chapter:
        export_turn(response, state, choice, suffix=f"_chapter_{new_chapter}")


def _write_chapter(response: dict, state: dict, choice: str | None) -> None:
    """Write (append) the chapter Markdown file with Obsidian frontmatter."""
    turn = state.get("turn", 0)
    status = state.get("status", "?")
    scene = state.get("scene", "?")

    frontmatter = {
        "turn": turn,
        "status": status,
        "scene": scene,
        "choice": choice or "auto",
        "generated_at": datetime.now().isoformat(),
        "engine": "Prompt OS Galgame Runtime v1",
    }

    story = response.get("story", "")
    options = response.get("options", [])

    body_parts: list[str] = []
    body_parts.append(f"# Chapter {turn}\n")
    body_parts.append(f"**Status:** `{status}`  |  **Scene:** {scene}\n")
    if choice:
        body_parts.append(f"**玩家选择:** `{choice}`\n")
    body_parts.append("---\n")
    body_parts.append(story)
    body_parts.append("\n---\n")
    body_parts.append("## 玩家选项\n")
    for idx, opt in enumerate(options, 1):
        body_parts.append(f"- **{chr(64 + idx)}.** {opt}")
    body_parts.append("\n")

    io_utils.append_markdown(config.CHAPTER_PATH, "\n".join(body_parts), frontmatter)
    logger.info("Chapter appended → %s", config.CHAPTER_PATH)


def _log_turn(response: dict, choice: str | None) -> None:
    """Append a structured entry to the turn log."""
    entry = {
        "story_snippet": response.get("story", "")[:200],
        "options": response.get("options", []),
        "state_summary": response.get("state", {}),
        "choice": choice,
    }
    io_utils.append_turn_log(config.TURN_LOG_PATH, entry)


def _print_summary(response: dict, state: dict) -> None:
    """Print a one-glance console summary (auto mode)."""
    print()
    print("┌──────────────────────────────────────────────────┐")
    print(f"│  Turn {state.get('turn', 0):<4}   Status: {state.get('status', '?'):<12}        │")
    print(f"│  Scene: {state.get('scene', '?')[:36]:<36} │")
    print("├──────────────────────────────────────────────────┤")
    story_preview = response.get("story", "")[:120].replace("\n", " ")
    print(f"│  {story_preview:<48} │")
    print("├──────────────────────────────────────────────────┤")
    for idx, opt in enumerate(response.get("options", []), 1):
        print(f"│  {chr(64 + idx)}. {opt[:44]:<44} │")
    print("└──────────────────────────────────────────────────┘")
    print()


# ── Graph & memory integration ─────────────────────────────────────

def _get_prev_options(state: dict) -> list[str]:
    """Read the previous turn's AI options from session history.

    Thread-safe replacement for the old module-level _prev_options global.
    The second-to-last history entry contains the options that were shown to
    the player last turn — those are the ones whose trust deltas we need.
    """
    history = state.get("history", [])
    if len(history) >= 2:
        return history[-2].get("options", [])
    return []


def _update_graph(
    response: dict,
    state: dict,
    choice: str | None,
    graph: dict | None = None,
) -> None:
    """Append the current turn as a node in the story graph (in-memory; commit via state_store)."""
    try:
        graph = graph if graph is not None else load_graph()
        current_node = get_current_node(graph)

        effective_choice = choice or "auto"

        new_id = append_node(
            graph,
            parent_node=current_node,
            choice_taken=effective_choice,
            turn=state.get("turn", 0),
            story_snippet=response.get("story", "")[:120],
            scene=state.get("scene", "?"),
            status=state.get("status", "?"),
            options=response.get("options", []),
        )
        save_graph(graph, persist=False)
        logger.info("Graph: node %s added (parent=%s, choice=%s)", new_id, current_node, effective_choice)
    except Exception:
        logger.error("Failed to update story graph:\n%s", traceback.format_exc())


def _update_memory(
    response: dict,
    state: dict,
    choice: str | None = None,
    memory: dict | None = None,
) -> None:
    """Update character memory in-place; persisted by commit_runtime()."""
    try:
        from engine.memory_updater import (
            init_world_state, auto_register_npcs,
            apply_trust_deltas, update_factions,
        )
        memory = memory if memory is not None else load_memory()
        story = response.get("story", "")
        turn = state.get("turn", 0)
        world_pack = io_utils.read_yaml(config.WORLD_PACK_PATH)

        init_world_state(memory, world_pack, turn, persist=False)
        auto_register_npcs(memory, state, world_pack, turn, story, persist=False)
        prev_options = _get_prev_options(state)
        apply_trust_deltas(memory, story, choice, turn, prev_options, persist=False)
        update_factions(memory, story, turn, persist=False)

    except Exception:
        logger.error("Failed to update memory:\n%s", traceback.format_exc())


def _obsidian_setup() -> None:
    """Configure Obsidian vault path for live export."""
    from ui.cli_ui import _c, _GREEN, _YELLOW, _DIM, _BOLD, _CYAN
    import config as cfg

    print()
    print(_c("📓 Obsidian 实时导出设置", _BOLD + _CYAN))
    print(_c("─" * 40, _DIM))

    current = cfg.OBSIDIAN_VAULT_PATH
    if current:
        print(_c(f"  当前 vault 路径: {current}", _GREEN))
        print(_c(f"  状态: ✅ 已启用", _GREEN))
    else:
        print(_c("  当前: 未设置", _DIM))
        print(_c("  状态: ⏸️  已禁用", _DIM))

    print()
    print(_c("  输入 Obsidian vault 的文件夹路径:", _YELLOW))
    print(_c("  例如: D:/MyVault 或 C:/Users/you/Documents/Obsidian", _DIM))
    print(_c("  输入空白 + 回车 = 禁用实时导出", _DIM))
    print()

    try:
        path_input = input(_c("  Vault 路径: ", _YELLOW)).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not path_input:
        cfg.save_obsidian_path("")
        # Reload the config
        import config as cfg2
        cfg2.OBSIDIAN_VAULT_PATH = ""
        print(_c("  ⏸️  Obsidian 实时导出已禁用", _YELLOW))
        return

    p = Path(path_input)
    if not p.exists():
        print(_c(f"  ⚠️  路径不存在: {path_input}", _YELLOW))
        print(_c("  将仍然保存设置，但导出会在路径存在后生效。", _DIM))

    cfg.save_obsidian_path(str(p.resolve()))
    import config as cfg2
    cfg2.OBSIDIAN_VAULT_PATH = str(p.resolve())

    # Try to init the vault
    obsidian_live.init_vault()

    print(_c(f"  ✅ Obsidian vault 已设置: {p.resolve()}", _GREEN))
    print(_c("  每轮剧情将自动写入 vault 的「星痕纪元/」文件夹。", _DIM))
    print(_c("  在 Obsidian 中打开该 vault 即可实时阅读。", _DIM))


def _print_graph_summary() -> None:
    """Print a text summary of the story graph to the console."""
    from engine.router import load_graph

    graph = load_graph()
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    print()
    print(_c("🌳 剧情分支图", _BOLD))
    print(_c("─" * 40, _DIM))

    if not nodes:
        print(_c("  （尚无剧情节点）", _DIM))
        return

    # Print nodes
    for nid in sorted(nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        node = nodes[nid]
        turn = node.get("turn", "?")
        text = node.get("text", "")[:50]
        scene = node.get("scene", "?")
        choices = node.get("choices", {})
        print(_c(f"  [Node {nid}] T{turn} {scene}", _BOLD))
        print(f"    {text}")
        if choices:
            choice_str = ", ".join(
                f"{c}→Node {t or '?'}" for c, t in choices.items()
            )
            print(_c(f"    分支: {choice_str}", _DIM))
        print()

    # Print edges
    if edges:
        print(_c("  边 (Edges):", _BOLD))
        for edge in edges:
            print(_c(f"    Node {edge['from']} --{edge['choice']}--> Node {edge['to']}", _DIM))
    print()


# ── CLI ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prompt OS Galgame Runtime v1 — Interactive AI Narrative Engine"
    )
    parser.add_argument(
        "--mode", choices=["auto", "cli", "web"], default="auto",
        help="Run mode: auto (default), cli (interactive), or web (FastAPI).",
    )
    parser.add_argument(
        "--loop", type=int, default=1,
        help="Number of turns in auto mode (default: 1).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Build prompt and print it, but do NOT call the API.",
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Web server host (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Web server port (default: 8000).",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't auto-open the browser on web mode startup.",
    )
    args = parser.parse_args()

    # Setup file logging
    config.setup_logging()

    # Check API key
    if not args.dry_run and not config.DEEPSEEK_API_KEY:
        logger.error(
            "DEEPSEEK_API_KEY 未设置。请通过 Web UI 设置（/settings）\n"
            "  或在环境变量中 export DEEPSEEK_API_KEY=sk-..."
        )
        sys.exit(1)

    # Dry run — print prompt only
    if args.dry_run:
        logger.info("── Dry run: building prompt only ──")
        system_prompt, user_prompt = build_prompt()
        print("=" * 60)
        print("SYSTEM PROMPT:")
        print("=" * 60)
        print(system_prompt)
        print("\n" + "=" * 60)
        print("USER PROMPT:")
        print("=" * 60)
        print(user_prompt)
        return

    # Init Obsidian vault if configured
    if obsidian_live.is_enabled():
        obsidian_live.init_vault()

    # Mode dispatch
    if args.mode == "web":
        run_web(host=args.host, port=args.port, no_browser=args.no_browser)
    elif args.mode == "cli":
        run_interactive()
    else:
        # auto mode (backward-compatible)
        if args.loop == 1:
            success = run_one_turn()
            sys.exit(0 if success else 1)
        else:
            ok = run_loop(args.loop)
            logger.info("Completed %d / %d turns successfully.", ok, args.loop)
            sys.exit(0 if ok == args.loop else 1)


if __name__ == "__main__":
    main()
