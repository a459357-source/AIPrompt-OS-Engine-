"""Regenerate player options for the current turn without advancing story."""

from __future__ import annotations

import logging

import config
from engine import io_utils

logger = logging.getLogger(__name__)


def _partner_names(characters: dict) -> list[str]:
    names: list[str] = []
    for key, ch in (characters or {}).items():
        if not isinstance(ch, dict):
            continue
        name = str(ch.get("name") or key).strip()
        if name and name not in names:
            names.append(name)
    return names[:6]


def _sync_graph_options(options: list[str]) -> None:
    try:
        graph = io_utils.read_json(config.STORY_GRAPH_PATH)
    except Exception:
        return
    current_id = graph.get("current_node")
    if not current_id:
        return
    nodes = graph.get("nodes") or {}
    node = nodes.get(current_id)
    if not isinstance(node, dict):
        return
    node["choices"] = {chr(65 + i): None for i in range(len(options))}
    io_utils.write_json(config.STORY_GRAPH_PATH, graph)


def _generate_options_via_ai(
    *,
    story: str,
    scene: str,
    characters: dict,
) -> list[str] | None:
    from engine.deepseek_client import call_deepseek, DeepSeekError

    count = config.OPTION_COUNT
    partners = _partner_names(characters)
    partner_line = "、".join(partners) if partners else "在场角色"
    story_tail = (story or "")[-2000:]

    if config.ADULT_MODE:
        from engine.adult_content_guard import regenerate_options_for_story

        tier = config.adult_intensity_tier()
        return regenerate_options_for_story(
            story=story,
            scene=scene,
            partners=partners,
            tier=tier,
        )

    system = (
        "你是 Galgame 选项设计师。用中文编写玩家可选行动。"
        f"只输出合法 JSON：{{\"options\": [...]}}，恰好 {count} 个字符串，不要其他文字。"
    )
    hint = config.adult_options_hint_text()
    user = (
        f"场景：{scene or '未知'}\n"
        f"角色：{partner_line}\n"
        f"当前轮正文（末尾）：{story_tail}\n\n"
        f"TASK: 根据上文生成 {count} 个下一行动选项。"
        "格式：行动→推测发展|态度/情绪|关系影响(如：角色名 affection+2 trust+1)，"
        "也可写为 行动|态度|关系影响 三段。"
        f"{hint}\n"
        "选项须对应当前剧情，并含关系数值变化提示。"
    )
    try:
        result = call_deepseek(system, user, skip_validation=True, stream=False)
    except DeepSeekError as exc:
        logger.warning("选项重生失败: %s", exc)
        return None
    opts = result.get("options") if isinstance(result, dict) else None
    if not isinstance(opts, list):
        return None
    cleaned = [str(o).strip() for o in opts if str(o).strip()]
    return cleaned[:count] if cleaned else None


def _normalize_option_count(options: list[str]) -> list[str]:
    count = config.OPTION_COUNT
    out = [str(o).strip() for o in options if str(o).strip()][:count]
    while len(out) < count:
        out.append("")
    return out[:count]


def regenerate_current_turn_options() -> dict:
    """
    Replace options on the latest history entry (current decision point).
    Does not advance turn or regenerate story.
    """
    config.reload_app_behavior()
    config.reload_option_count()

    try:
        state = io_utils.read_yaml(config.SESSION_STATE_PATH, use_cache=False)
    except Exception:
        return {"ok": False, "error": "无法读取游戏状态"}

    history = state.get("history") or []
    if not history:
        return {"ok": False, "error": "当前无回合历史"}

    last = history[-1]
    if last.get("choice"):
        return {"ok": False, "error": "当前轮已做出选择，无法重生选项"}

    story = str(last.get("story") or last.get("summary") or "")
    if len(story.strip()) < 20:
        return {"ok": False, "error": "当前轮正文过短，无法重生选项"}

    scene = str(state.get("scene") or last.get("scene") or "")
    characters = state.get("characters") or {}

    options = _generate_options_via_ai(story=story, scene=scene, characters=characters)
    if not options:
        return {"ok": False, "error": "AI 选项生成失败"}

    response: dict = {"story": story, "options": options, "state": {}}
    if config.ADULT_MODE:
        from engine.adult_content_guard import ensure_adult_turn_content

        response = ensure_adult_turn_content(
            response,
            scene=scene,
            characters=characters,
        )
        options = response.get("options") or options

    options = _normalize_option_count(list(options))
    history[-1]["options"] = options
    state["history"] = history
    io_utils.write_yaml(config.SESSION_STATE_PATH, state)
    _sync_graph_options(options)

    logger.info(
        "已重生当前轮 options（adult=%s, count=%d）",
        config.ADULT_MODE,
        len([o for o in options if o]),
    )
    return {"ok": True, "options": options}
