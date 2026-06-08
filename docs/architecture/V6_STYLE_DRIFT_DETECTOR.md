# Style Drift Detector v1

**状态**: Implemented  
**日期**: 2026-06-08

## 定位

轻量 **反馈控制层**：生成后自检资产是否偏离 Style Bible 世界风格分布，并按策略 accept / retry / fallback。

```text
VisualIdentity → Prompt Builder → Style Bible → Provider
  → Drift Detector → Quality Governance → Cache / Registry
```

质量裁决见 `V6_VISUAL_QUALITY_GOVERNANCE.md`。

## 三模块（v1 无 CV/ML）

| 模块 | 实现 |
|------|------|
| Style Signature | `build_style_signature()` ← Style Bible v1 |
| Feature Extractor | `extract_features()` prompt proxy + provider metadata |
| Drift Scoring | `compute_drift()` + `classify_drift()` |

## 策略

| 分数 | 级别 | 动作 |
|------|------|------|
| 0.0–0.3 | ok | accept + cache |
| 0.3–0.6 | mild | `reinforce_style_bible()` → retry once |
| 0.6–1.0 | severe | reject → StubVisualProvider fallback |

## 配置

- `STYLE_DRIFT_DETECTOR_ENABLED = True`
- `STYLE_DRIFT_MILD_THRESHOLD = 0.3`
- `STYLE_DRIFT_SEVERE_THRESHOLD = 0.6`

## 文件

- `engine/visual/style_drift.py`
- `engine/visual/visual_runtime.py`（`_generate_with_drift_policy`）
- `engine/templates/style_bible.py`（`reinforce_style_bible`）

Drift 结果写入 registry `meta.drift`，**无 UI 绑定**。
