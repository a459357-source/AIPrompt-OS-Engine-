"""Mermaid graph source must survive special characters in story/character text."""
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from engine.dashboard import _build_mermaid, _build_faction_graph, _sanitize_mermaid


def test_sanitize_brackets_and_pipes():
    raw = '进入[危险]区#注释; opt|A'
    out = _sanitize_mermaid(raw)
    assert "[" not in out and "]" not in out
    assert "#" not in out
    assert "|" not in out
    assert ";" not in out


def test_build_mermaid_no_round_char_nodes():
    nodes = {
        "0": {"turn": 1, "text": "进入[危险]区域#测试"},
        "1": {"turn": 2, "text": "继续"},
    }
    edges = [{"from": "0", "to": "1", "choice": "前往(A)区 | 备选"}]
    chars = {"张三(主)": {"trust": 0.5}, "李四": {"trust": 0.75}}
    src = _build_mermaid(nodes, edges, chars)

    assert 'c0("' not in src
    assert 'c1("' not in src
    assert 'c0["' in src
    assert "-->|" in src or "-->|" in src
    assert "n0 -- " not in src


def test_build_faction_graph_square_nodes():
    memory = {
        "factions": {"北方[联盟]": {"reputation": 0.8}},
        "faction_attitudes": {},
    }
    src = _build_faction_graph(memory)
    assert 'f0("' not in src
    assert 'f0["' in src


if __name__ == "__main__":
    for fn in (test_sanitize_brackets_and_pipes, test_build_mermaid_no_round_char_nodes, test_build_faction_graph_square_nodes):
        fn()
        print(f"✅ {fn.__name__}")
