# V6 Visual Runtime — 收敛完成报告

**日期**: 2026-06-08  
**状态**: ✅ 已交付（工程必做层）

---

## 交付摘要

将 Phase A/B 实现收敛为**单一合法入口** `get_visual()`，补齐 `VisualObject`、`normalize_prompt`、L1 内存缓存、retry/fallback、四类 entity_type 冻结。

> V6 is a deterministic visual asset generation and reuse layer for narrative entities.

---

## 架构（已实现）

```text
get_visual(entity_type, entity_id, context)
  → VisualObject
  → normalize_prompt → prompt_hash
  → Registry lookup
  → L1 memory cache
  → L2 filesystem cache
  → Provider (miss only, retry, stub fallback)
  → store cache + registry
  → image_path
```

---

## 新增 / 重构文件

| 文件 | 职责 |
|------|------|
| `engine/visual/visual_runtime.py` | `get_visual()` 唯一入口 |
| `engine/visual/visual_object.py` | `VisualObject` + `build_visual_object()` |
| `engine/visual/prompt_canonical.py` | `normalize_prompt()` |
| `engine/visual/asset_manager.py` | 薄封装，委托 `get_visual` |
| `engine/visual/image_generation.py` | retry + fallback，不写 registry |
| `docs/architecture/V6_VISUAL_RUNTIME_EXECUTION_PLAN.md` | 最终执行计划书 |

Provider 接口统一为：`generate_character/location/faction/event`。

Registry scope：`characters / locations / factions / events`（`scenes` 自动迁移至 `events`）。

---

## 验收清单

| 项 | 状态 |
|----|------|
| 四类对象 `get_visual` 生成 | ✅ |
| cache 命中不调 provider | ✅ |
| registry 复用 asset | ✅ |
| prompt_hash 规范化稳定 | ✅ |
| provider 可切换 stub/agnes | ✅ |
| Agnes 失败 fallback stub | ✅ |
| retry 机制 | ✅ |
| Provider 不写 registry | ✅ |

---

## 自检

```text
python -m pytest test_visual_phase_a.py test_visual_provider.py test_visual_runtime.py -q
→ 33 passed

python -c "from engine.visual import get_visual; from engine.run import step"
→ OK
```

---

## 未做（按冻结）

- UI / Dashboard
- async 队列
- V6.1 视觉人格一致性
- Event Director / `run.py` 自动生图接线

---

## 向后兼容

保留 `get_or_request_character_portrait` 等四个旧 API，内部全部调用 `get_visual`。
