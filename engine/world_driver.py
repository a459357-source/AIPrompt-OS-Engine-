"""
world_driver.py — Faction-Driven Plot Engine
===============================================
Generates plot hooks from faction goals and inter-faction dynamics
so the world "moves" even when the player does nothing.

Each turn:
  1. Pick a faction with urgent goals
  2. Generate a plot hook based on their goals + resources + attitudes
  3. Passive drift: faction attitudes slowly shift based on relations
"""

import logging
import random

logger = logging.getLogger(__name__)


# ── Public API ──────────────────────────────────────────────────────

def generate_plot_hooks(memory: dict, turn: int) -> list[str]:
    """
    Generate 1-3 plot hook strings for the AI prompt.
    Each hook describes a faction action that should happen this turn.

    Returns list of hook strings like:
      "华尔街资本正在通过广场协议施压日本大藏省"
      "近卫家暗中向卡洛琳·福斯特传递情报"
    """
    factions = memory.get("factions", {})
    attitudes = memory.get("faction_attitudes", {})
    if not factions:
        return []

    hooks: list[str] = []

    # Sort factions by influence (more influential = more likely to act)
    ranked = sorted(factions.items(), key=lambda x: x[1].get("influence", 50), reverse=True)

    for name, data in ranked[:3]:  # top 3 most influential
        goals = data.get("goals", [])
        resources = data.get("resources", [])
        rel_player = data.get("relation_to_player", "neutral")
        ftype = data.get("type", "other")

        if not goals:
            continue

        # Pick a goal (cycle through based on turn)
        goal = goals[turn % len(goals)]

        # Look at who this faction has strong attitudes toward
        targets = attitudes.get(name, {})
        strong_targets = [
            (t, d.get("attitude", 0.5))
            for t, d in targets.items()
            if abs(d.get("attitude", 0.5) - 0.5) >= 0.2
        ]

        # Build the hook
        hook = _build_hook(name, ftype, goal, resources, rel_player, strong_targets)
        if hook:
            hooks.append(hook)

    return hooks


def passive_faction_drift(memory: dict, turn: int) -> None:
    """
    Slowly drift faction attitudes based on their relation_to_player
    and existing inter-faction dynamics.  Called once per turn.
    """
    from engine.memory import update_faction_attitude

    attitudes = memory.get("faction_attitudes", {})
    factions = memory.get("factions", {})

    for a, targets in attitudes.items():
        for b, data in targets.items():
            att = data.get("attitude", 0.5)

            # Drift toward extremes based on current value
            # If already allied (>0.7), drift slightly more allied
            # If already hostile (<0.3), drift slightly more hostile
            # Middle values drift randomly
            if att >= 0.7:
                delta = random.uniform(0.0, 0.02)
            elif att <= 0.3:
                delta = random.uniform(-0.02, 0.0)
            else:
                delta = random.uniform(-0.01, 0.01)

            if abs(delta) > 0.001:
                update_faction_attitude(memory, a, b, round(delta, 3), turn)


def get_world_state_context(memory: dict) -> str:
    """
    Build a summary of the world's autonomous activity for the prompt.
    Tells the AI what factions are doing this turn.
    """
    hooks = generate_plot_hooks(memory, 0)  # turn doesn't matter for context
    if not hooks:
        return ""

    lines: list[str] = ["【势力动向】"]
    for h in hooks[:3]:
        lines.append(f"  • {h}")

    return "\n".join(lines)


# ── Internal helpers ────────────────────────────────────────────────

def _build_hook(
    name: str,
    ftype: str,
    goal: str,
    resources: list[str],
    rel_player: str,
    targets: list[tuple[str, float]],
) -> str | None:
    """Build a single plot hook string from faction data."""

    # Templates vary by faction type and relation
    templates: list[str] = []

    if ftype in ("corporation", "kingdom"):
        templates = [
            f"{name} 正在推进「{goal}」，动用了{_pick(resources, '资源')}。",
            f"{name} 向市场释放信号，意图达成「{goal}」。",
        ]
    elif ftype in ("government", "organization"):
        templates = [
            f"{name} 召开秘密会议讨论「{goal}」。",
            f"{name} 派遣特使推进「{goal}」。",
        ]
    elif ftype in ("guild", "school", "religion"):
        templates = [
            f"{name} 内部正在为「{goal}」而行动。",
            f"{name} 的信徒/成员开始推进「{goal}」。",
        ]
    elif ftype in ("family",):
        templates = [
            f"{name} 为达成「{goal}」暗中布局。",
            f"{name} 的当家正为「{goal}」而奔走。",
        ]
    else:
        templates = [
            f"{name} 正在推进「{goal}」。",
        ]

    # If there are strong targets, add interaction hooks
    if targets:
        target_name, target_att = targets[0]
        if target_att >= 0.7:
            templates.append(
                f"{name} 与 {target_name} 密切合作推进「{goal}」。"
            )
        elif target_att <= 0.3:
            templates.append(
                f"{name} 与 {target_name} 就「{goal}」发生摩擦。"
            )

    # Player-relevant hook
    if rel_player == "enemy":
        templates.append(
            f"{name} 正在策划对主角不利的行动：{goal}"
        )
    elif rel_player == "ally":
        templates.append(
            f"{name} 为主角的「{goal}」提供了{_pick(resources, '支援')}。"
        )

    return random.choice(templates) if templates else None


def _pick(items: list[str], fallback: str) -> str:
    """Pick a random item or return fallback."""
    if not items:
        return fallback
    return random.choice(items)
