"""Cross-thread cache invalidation for session_state reads."""
import sys
import tempfile
import threading
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import config
from engine import io_utils
from engine.state_store import RuntimeState, commit_runtime


def test_cache_invalidated_across_threads():
    """API thread must see history after SSE worker thread commits."""
    tmp = Path(tempfile.mkdtemp())
    session_path = tmp / "session_state.yaml"
    orig = config.SESSION_STATE_PATH
    config.SESSION_STATE_PATH = session_path

    try:
        io_utils.write_yaml(session_path, {"turn": 0, "history": []})
        io_utils.clear_cache()

        cached_read_done = threading.Event()
        commit_done = threading.Event()
        second_read: dict = {}

        def api_thread():
            first = io_utils.read_yaml(session_path)
            assert first.get("history") == []
            cached_read_done.set()
            commit_done.wait(timeout=5)
            second_read["state"] = io_utils.read_yaml(session_path)

        def worker_thread():
            cached_read_done.wait(timeout=5)
            rt = RuntimeState(
                session={
                    "turn": 1,
                    "history": [{"turn": 1, "story": "第一段", "options": ["A"], "choice": "A"}],
                },
                memory={"characters": {}, "world_flags": []},
                graph={"nodes": {}, "current_node": "0", "edges": []},
            )
            commit_runtime(rt)
            commit_done.set()

        t_api = threading.Thread(target=api_thread)
        t_worker = threading.Thread(target=worker_thread)
        t_api.start()
        t_worker.start()
        t_api.join(timeout=10)
        t_worker.join(timeout=10)

        assert second_read.get("state"), "second read did not run"
        history = second_read["state"].get("history", [])
        assert len(history) == 1, f"expected 1 history entry, got {len(history)}"
        assert history[0]["story"] == "第一段"
    finally:
        config.SESSION_STATE_PATH = orig
        io_utils.clear_cache()


if __name__ == "__main__":
    test_cache_invalidated_across_threads()
    print("✅ io_utils cross-thread cache: PASS")
