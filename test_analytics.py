"""
Tests for analytics.py — metrics_curves, summary_stats, and related functions.
Run: python prompt-os-engine/test_analytics.py
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from engine.analytics import (
    metrics_curves, summary_stats, branch_stats,
    status_timeline, character_frequency, scene_summary,
)


def test_metrics_curves_type_guard():
    """metrics_curves should not crash on non-dict character entries."""
    # Patch io_utils to return a memory with a non-dict entry
    import engine.io_utils as io
    import config
    _orig_read = io.read_json

    def _mock_read(path):
        if path == config.MEMORY_PATH:
            return {
                "characters": {
                    "林夜": {"trust": 0.7, "metric_history": {"trust": [[1, 0.5], [2, 0.7]]}},
                    "bad_entry": "not a dict",  # should be skipped by type guard
                }
            }
        return _orig_read(path)

    io.read_json = _mock_read
    try:
        result = metrics_curves()
        assert "trust" in result, f"Expected 'trust' metric, got keys: {list(result.keys())}"
        # Should still have the valid character
        datasets = result["trust"]["datasets"]
        assert len(datasets) >= 1, f"Expected >= 1 dataset, got {len(datasets)}"
        print("✅ metrics_curves type guard: PASS")
    finally:
        io.read_json = _orig_read


def test_metrics_curves_multi_metric():
    """metrics_curves should detect multiple metric types."""
    import engine.io_utils as io
    import config
    _orig_read = io.read_json

    def _mock_read(path):
        if path == config.MEMORY_PATH:
            return {
                "characters": {
                    "林夜": {
                        "trust": 0.7,
                        "好感度": 0.6,
                        "fear": 0.3,
                        "metric_history": {
                            "trust": [[1, 0.5], [2, 0.7]],
                            "好感度": [[1, 0.4], [2, 0.6]],
                            "fear": [[1, 0.2], [2, 0.3]],
                        }
                    }
                }
            }
        return _orig_read(path)

    io.read_json = _mock_read
    try:
        result = metrics_curves()
        assert "trust" in result or "好感度" in result or "fear" in result, \
            f"Expected at least one metric, got: {list(result.keys())}"
        metric_count = len(result)
        assert metric_count >= 2, f"Expected >= 2 metrics, got {metric_count}"
        print(f"✅ metrics_curves multi-metric: PASS — {metric_count} metrics: {list(result.keys())}")
    finally:
        io.read_json = _orig_read


def test_summary_stats():
    """summary_stats should return expected keys."""
    result = summary_stats()
    expected_keys = {"turns", "status", "characters", "total_words", "nodes", "edges"}
    assert expected_keys.issubset(result.keys()), \
        f"Missing keys: {expected_keys - set(result.keys())}"
    assert isinstance(result["turns"], int)
    print(f"✅ summary_stats: PASS — {result['turns']} turns, {result['characters']} chars")


def test_branch_stats():
    """branch_stats should return leaf_count and max_depth."""
    result = branch_stats()
    assert "total_nodes" in result
    assert "leaf_count" in result
    assert "max_depth" in result
    assert isinstance(result["total_nodes"], int)
    print(f"✅ branch_stats: PASS — {result['total_nodes']} nodes, depth {result['max_depth']}")


if __name__ == "__main__":
    tests = [
        test_metrics_curves_type_guard,
        test_metrics_curves_multi_metric,
        test_summary_stats,
        test_branch_stats,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL: {e}")
        except Exception as e:
            print(f"💥 ERROR in {test.__name__}: {e}")
    print(f"\n🎉 {passed}/{len(tests)} tests passed!")
    sys.exit(0 if passed == len(tests) else 1)
