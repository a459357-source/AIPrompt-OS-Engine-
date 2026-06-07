"""
router.py — Story Graph Manager
=================================
Manages the branching story graph: loads/saves story_graph.json,
routes player choices to next nodes, and appends new nodes as the
story unfolds.

The graph is a dynamic record — nodes are created as the LLM generates
each turn, and edges are drawn when the player makes a choice.
"""

import logging

import config
from engine import io_utils

logger = logging.getLogger(__name__)


def load_graph() -> dict:
    """Load the story graph from disk."""
    return io_utils.read_json(config.STORY_GRAPH_PATH)


def save_graph(graph: dict, *, persist: bool = True) -> None:
    """Persist the story graph to disk (skipped when persist=False)."""
    if persist:
        io_utils.write_json(config.STORY_GRAPH_PATH, graph)


def get_current_node(graph: dict) -> str:
    """Return the current node id."""
    return graph.get("current_node", "0")


def route(current_node: str, choice: str, graph: dict) -> str | None:
    """
    Follow a choice edge from current_node.
    Returns the destination node id, or None if the edge doesn't exist yet.
    """
    node = graph.get("nodes", {}).get(current_node, {})
    choices = node.get("choices", {})
    return choices.get(choice)


def append_node(
    graph: dict,
    parent_node: str,
    choice_taken: str,
    turn: int,
    story_snippet: str,
    scene: str,
    status: str,
    options: list[str],
) -> str:
    """
    Create a new node in the graph and wire it from parent_node via choice_taken.

    Returns the new node id.
    """
    new_id = str(len(graph.get("nodes", {})))

    graph.setdefault("nodes", {})[new_id] = {
        "turn": turn,
        "text": story_snippet[:120],
        "scene": scene,
        "status": status,
        "choices": _options_to_edge_placeholders(options),
        "parent": parent_node,
        "choice_taken": choice_taken,
    }

    # Wire the edge from parent → new node
    parent = graph.setdefault("nodes", {}).setdefault(parent_node, {})
    parent.setdefault("choices", {})[choice_taken] = new_id

    # Record the edge
    graph.setdefault("edges", []).append({
        "from": parent_node,
        "to": new_id,
        "choice": choice_taken,
        "turn": turn,
    })

    # Advance current_node pointer
    graph["current_node"] = new_id

    return new_id


def _options_to_edge_placeholders(options: list[str]) -> dict[str, str | None]:
    """Create empty choice slots for the new node's options."""
    return {chr(65 + i): None for i in range(len(options))}


def get_path_to_root(graph: dict, node_id: str) -> list[dict]:
    """Walk parents from node_id back to root, returning the path."""
    path = []
    current = node_id
    nodes = graph.get("nodes", {})
    while current is not None:
        node = nodes.get(current)
        if node is None:
            break
        path.append({"id": current, **node})
        current = node.get("parent")
    path.reverse()
    return path


def get_leaf_count(graph: dict) -> int:
    """Count the number of leaf nodes (nodes with no outgoing edges)."""
    nodes = graph.get("nodes", {})
    count = 0
    for nid, node in nodes.items():
        choices = node.get("choices", {})
        if not choices or all(v is None for v in choices.values()):
            count += 1
    return count
