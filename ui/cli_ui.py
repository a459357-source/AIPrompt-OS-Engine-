"""
cli_ui.py — Interactive CLI interface for the Galgame Runtime
===============================================================
Displays story text and choices with colored formatting,
collects player input (A/B/C/D or Q to quit).
"""

import sys


# ── ANSI color helpers ─────────────────────────────────────────────

_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_MAGENTA = "\033[35m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_DIM = "\033[2m"


def _c(text: str, color: str) -> str:
    """Wrap text in ANSI color codes (no-op if stdout is not a TTY)."""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{_RESET}"


def show_banner() -> None:
    """Display the Galgame Runtime banner."""
    print()
    print(_c("╔══════════════════════════════════════════╗", _CYAN))
    print(_c("║  🎮  Prompt OS Galgame Runtime v1      ║", _BOLD + _CYAN))
    print(_c("║  星痕纪元 — Epoch of Starlight          ║", _CYAN))
    print(_c("╚══════════════════════════════════════════╝", _CYAN))
    print()
    print(_c("  输入 A/B/C/D 选择剧情，Q 退出游戏", _DIM))
    print(_c("  S1/S2/S3 存档 | L1/L2/L3 读档 | G 分支图 | O Obsidian", _DIM))
    print()


def show_turn_header(turn: int, status: str, scene: str) -> None:
    """Display the turn number, status, and scene."""
    print()
    print(_c(f"── 第 {turn} 轮 ──", _BOLD))
    print(_c(f"   状态: {status}  |  场景: {scene}", _DIM))
    print()


def show_story(story: str) -> None:
    """Display the story text block."""
    print(story)
    print()


def show_options(options: list[str]) -> None:
    """Display the four choices with A/B/C/D labels."""
    print(_c("──── 剧情选择 ────", _BOLD))
    for i, opt in enumerate(options):
        label = chr(65 + i)  # A, B, C, D
        print(f"  {_c(f'[{label}]', _GREEN + _BOLD)} {opt}")
    print()


def get_user_choice() -> str:
    """
    Prompt the player for a choice.
    Returns 'A', 'B', 'C', 'D', 'Q', 'S1', 'S2', 'S3', 'L1', 'L2', 'L3', or 'G'.
    Retries on invalid input.
    """
    while True:
        try:
            choice = input(
                _c("请选择 (A/B/C/D, S存档 L读档 G分支图 O=Obsidian, Q=退出): ", _YELLOW)
            ).strip().upper()
        except (EOFError, KeyboardInterrupt):
            print()
            return "Q"

        valid = {"A", "B", "C", "D", "Q", "S1", "S2", "S3", "L1", "L2", "L3", "G", "O"}
        if choice in valid:
            return choice

        print(_c(f"  无效输入 '{choice}'，请输入 A/B/C/D, S1-S3, L1-L3, G, Q", _YELLOW))


def show_goodbye() -> None:
    """Display farewell message."""
    print()
    print(_c("  感谢游玩！剧情已保存。", _GREEN))
    print(_c("  章节输出 → output/chapter.md", _DIM))
    print(_c("  剧情分支 → data/story_graph.json", _DIM))
    print()


def show_divider() -> None:
    """Print a horizontal divider."""
    print(_c("─" * 50, _DIM))
