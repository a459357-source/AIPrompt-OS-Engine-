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
import webbrowser
from datetime import datetime
from pathlib import Path

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
from engine.memory import load_memory, save_memory, update_trust, set_flag, get_context_for_prompt, guess_trust_delta_from_story, init_factions, update_faction_reputation, set_faction_flag
from engine.save_manager import autosave as do_autosave
from engine import obsidian_live

# ── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run")


# ── Core step (stateless, for web/cli reuse) ───────────────────────

def step(choice: str | None = None) -> dict | None:
    """
    Execute one turn: generate story + options, apply to state,
    update graph & memory.  Returns the response dict (story, options,
    state) plus metadata, or None on failure.

    Args:
        choice: The player's choice from the previous turn (A/B/C/D),
                or None for the first turn.
    """
    logger.info("═══ TURN START ═══")

    # 1. Build prompt
    try:
        system_prompt, user_prompt = build_prompt()
    except Exception as exc:
        logger.error("Failed to build prompt: %s", exc)
        return None

    # 2. Call DeepSeek
    try:
        response = call_deepseek(system_prompt, user_prompt)
    except DeepSeekError as exc:
        logger.error("DeepSeek API error: %s", exc)
        return None

    # 3. Validate
    warnings = validate_response(response)
    for w in warnings:
        logger.warning("Validation: %s", w)

    # 4. Apply to state (with choice from *previous* turn)
    try:
        new_state = apply_turn(response, choice)
    except Exception as exc:
        logger.error("Failed to apply turn: %s", exc)
        return None

    # 5. Update story graph
    _update_graph(response, new_state, choice)

    # 6. Update character memory
    _update_memory(response, new_state)

    # 7. Write chapter.md
    _write_chapter(response, new_state, choice)

    # 8. Write dashboard HTML → output/ (always, no Obsidian needed)
    _write_dashboard_html()

    # 9. Live export to Obsidian vault (optional)
    obsidian_live.on_turn(response, new_state, choice)

    # 10. Log turn
    _log_turn(response, choice)

    # 11. Autosave
    do_autosave()

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
    Returns True on success, False on failure.
    """
    logger.info("═══ TURN START ═══")

    try:
        system_prompt, user_prompt = build_prompt()
    except Exception as exc:
        logger.error("Failed to build prompt: %s", exc)
        return False

    try:
        response = call_deepseek(system_prompt, user_prompt)
    except DeepSeekError as exc:
        logger.error("DeepSeek API error: %s", exc)
        return False

    warnings = validate_response(response)
    for w in warnings:
        logger.warning("Validation: %s", w)

    try:
        new_state = apply_turn(response)  # no choice in auto mode
    except Exception as exc:
        logger.error("Failed to apply turn: %s", exc)
        return False

    _update_graph(response, new_state, None)
    _update_memory(response, new_state)
    _write_chapter(response, new_state, None)
    _write_dashboard_html()
    obsidian_live.on_turn(response, new_state, None)
    _log_turn(response, None)
    do_autosave()
    _print_summary(response, new_state)

    logger.info("═══ TURN COMPLETE ═══")
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
    """Open the web UI in the default browser after a short delay."""
    url = f"http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}"
    def _open():
        import time
        time.sleep(1.0)  # wait for uvicorn to start listening
        logger.info("Opening browser → %s", url)
        webbrowser.open(url)
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

    logger.info("Starting Galgame Web UI → http://%s:%d", host, port)
    uvicorn.run("ui.web_app:app", host=host, port=port, reload=False)


# ── Output helpers ─────────────────────────────────────────────────

def _write_dashboard_html() -> None:
    """Write the analytics dashboard HTML to output/ (no Obsidian needed)."""
    try:
        from engine.dashboard import write_standalone
        write_standalone()
    except Exception as exc:
        logger.warning("Failed to write dashboard HTML: %s", exc)


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

def _update_graph(response: dict, state: dict, choice: str | None) -> None:
    """Append the current turn as a node in the story graph."""
    try:
        graph = load_graph()
        current_node = get_current_node(graph)

        # If the player made a choice last turn, route through it
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
        save_graph(graph)
        logger.info("Graph: node %s added (parent=%s, choice=%s)", new_id, current_node, effective_choice)
    except Exception as exc:
        logger.warning("Failed to update story graph: %s", exc)


def _update_memory(response: dict, state: dict) -> None:
    """Update character memory based on the new story content."""
    try:
        memory = load_memory()
        story = response.get("story", "")
        turn = state.get("turn", 0)

        # ── Initialize factions from world pack (first time) ──────
        init_factions(memory)

        # ── Auto-register new NPCs from session state ────────────
        state_chars = state.get("characters", {})
        mem_chars = memory.setdefault("characters", {})
        for key, sc in state_chars.items():
            name = sc.get("name", key)
            if name not in mem_chars:
                # New NPC discovered — auto-register
                mem_chars[name] = {
                    "trust": 0.5,
                    "flags": [],
                    "relationship": sc.get("relation", ""),
                    "role": sc.get("role", ""),
                }
                # Record first appearance in metric_history
                mem_chars[name].setdefault("metric_history", {}).setdefault(
                    "trust", []
                ).append([turn, 0.5])
                logger.info("Memory: auto-registered new NPC '%s' (turn %d)", name, turn)

        # Heuristic trust deltas from story keywords
        deltas = guess_trust_delta_from_story(story)
        for char_name, delta, flag in deltas:
            # Apply to all known characters
            for name in list(mem_chars.keys()):
                if name in story:
                    update_trust(memory, name, delta, turn)
            if flag:
                for name in list(mem_chars.keys()):
                    if name in story:
                        set_flag(memory, name, flag)
                        break
                else:
                    set_flag(memory, None, flag)  # world flag

        # ── Faction reputation from story ───────────────────────
        mem_factions = memory.get("factions", {})
        for fname in list(mem_factions.keys()):
            if fname in story:
                # Simple heuristic: faction mentioned → minor rep change
                # Positive tone keywords
                pos = any(kw in story for kw in ["合作", "支援", "友好", "结盟", "信任"])
                neg = any(kw in story for kw in ["敌对", "攻击", "背叛", "威胁", "警告"])
                if pos and not neg:
                    update_faction_reputation(memory, fname, 0.05, turn)
                elif neg and not pos:
                    update_faction_reputation(memory, fname, -0.05, turn)

        save_memory(memory)
    except Exception as exc:
        logger.warning("Failed to update memory: %s", exc)


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
