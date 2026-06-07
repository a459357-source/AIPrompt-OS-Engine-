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

from engine.constants import (
    PASSIVE_DRIFT_ALLIED_MAX, PASSIVE_DRIFT_HOSTILE_MIN,
    PASSIVE_DRIFT_NEUTRAL_RANGE, PASSIVE_DRIFT_THRESHOLD,
)

logger = logging.getLogger(__name__)

# Dedicated random instance for faction dynamics — isolated from the global
# random module so that passive drift does not pollute seed-dependent event
# generation (events.py uses random.Random(seed) for determinism).
_drift_random = random.Random()


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
        territories = data.get("controlledTerritories", [])
        orgs = data.get("subordinateOrganizations", [])
        assets = data.get("keyAssets", [])
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

        # Build the hook — now uses territories/orgs/assets for specificity
        hook = _build_hook(name, ftype, goal, resources, territories, orgs, assets,
                           rel_player, strong_targets)
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
                delta = _drift_random.uniform(0.0, PASSIVE_DRIFT_ALLIED_MAX)
            elif att <= 0.3:
                delta = _drift_random.uniform(PASSIVE_DRIFT_HOSTILE_MIN, 0.0)
            else:
                delta = _drift_random.uniform(-PASSIVE_DRIFT_NEUTRAL_RANGE, PASSIVE_DRIFT_NEUTRAL_RANGE)

            if abs(delta) > PASSIVE_DRIFT_THRESHOLD:
                update_faction_attitude(memory, a, b, round(delta, 3), turn)


def get_world_state_context(memory: dict, turn: int = 0) -> str:
    """
    Build a summary of the world's autonomous activity for the prompt.
    Tells the AI what factions are doing this turn.
    """
    hooks = generate_plot_hooks(memory, turn)
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
    territories: list[str],
    orgs: list[str],
    assets: list[str],
    rel_player: str,
    targets: list[tuple[str, float]],
) -> str | None:
    """Build a single plot hook string from faction data.

    Now uses controlledTerritories, subordinateOrganizations, and keyAssets
    to generate concrete, specific actions instead of vague ones.
    """
    loc = _pick(territories, None) or ""
    org = _pick(orgs, None) or ""
    asset = _pick(assets, None) or ""

    templates: list[str] = []

    if ftype in ("corporation",):
        if org:
            templates.append(f"{name} 通过{org}在{loc or '市场'}推进「{goal}」。")
        if asset:
            templates.append(f"{name} 动用{asset}，意图达成「{goal}」。")
        templates.append(f"{name} 正在推进「{goal}」，动用了{_pick(resources, '资源')}。")
    elif ftype in ("government",):
        if org and loc:
            templates.append(f"{org}在{loc}执行{name}的「{goal}」计划。")
        if loc:
            templates.append(f"{name} 在{loc}部署力量推进「{goal}」。")
        templates.append(f"{name} 召开秘密会议讨论「{goal}」。")
    elif ftype in ("kingdom",):
        if loc and org:
            templates.append(f"{org}在{loc}为{name}的「{goal}」而行动。")
        templates.append(f"{name} 为达成「{goal}」调动了{_pick(resources, '全国之力')}。")
    elif ftype in ("family",):
        if org:
            templates.append(f"{name} 通过{org}暗中推进「{goal}」。")
        if asset:
            templates.append(f"{name} 以{asset}为筹码，谋取「{goal}」。")
        templates.append(f"{name} 为达成「{goal}」暗中布局。")
    elif ftype in ("guild", "school", "religion"):
        if org:
            templates.append(f"{org}开始为{name}的「{goal}」而行动。")
        templates.append(f"{name} 内部正在为「{goal}」而行动。")
    else:
        templates = [f"{name} 正在推进「{goal}」。"]
        if org:
            templates.insert(0, f"{name} 通过{org}推进「{goal}」。")

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
        if org and loc:
            templates.append(f"{name} 的{org}在{loc}策划对主角不利的行动。")
        templates.append(f"{name} 正在策划对主角不利的行动：{goal}")
    elif rel_player == "ally":
        templates.append(
            f"{name} 为主角的「{goal}」提供了{_pick(resources, '支援')}。"
        )

    return _drift_random.choice(templates) if templates else None


def _pick(items: list[str], fallback: str) -> str:
    """Pick a random item or return fallback."""
    if not items:
        return fallback
    return _drift_random.choice(items)
