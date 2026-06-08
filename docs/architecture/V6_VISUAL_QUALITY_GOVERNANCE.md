# Visual Quality Governance Layer v1

**状态**: Implemented  
**日期**: 2026-06-08

## 定位

V6 **收口层**：生成 → 漂移检测 → **质量裁决** → 批准进入世界。

```text
Provider → Drift Detector → Quality Governance → Cache / Registry
```

## 三层治理

| 层 | 模块 | 输出 |
|----|------|------|
| L1 Structural | `validate_structure()` | structure_validity 0–1 |
| L2 Consistency | `score_consistency()` ← Drift | consistency_score 0–1 |
| L3 Aesthetic | `score_aesthetic()` heuristic | aesthetic_score 0–1 |

## 综合决策

```text
final_score = 0.4×structure + 0.3×consistency + 0.3×aesthetic
```

| final_score | 决策 |
|-------------|------|
| ≥ 0.75 | accept + cache |
| 0.5–0.75 | accept_weak（`meta.quality_weak`） |
| < 0.5 | reject → reinforce + stub 再生 |

## 配置

- `VISUAL_QUALITY_GOVERNANCE_ENABLED = True`
- `VISUAL_QUALITY_ACCEPT_THRESHOLD = 0.75`
- `VISUAL_QUALITY_WEAK_THRESHOLD = 0.5`

## 文件

- `engine/visual/quality_governance.py`
- `engine/visual/visual_runtime.py`（`_apply_quality_governance`）

结果写入 `meta.quality`，**无 UI 绑定**。

## 与 Drift Detector 分工

| 系统 | 职责 |
|------|------|
| Drift Detector | 偏没偏 |
| Quality Governance | 好不好 + 能不能进世界 |
