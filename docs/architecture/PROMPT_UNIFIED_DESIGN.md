# V4.0 Prompt Unified Architecture Design

**项目**：PromptOS  
**版本**：V4.0 Hybrid Model Pipeline — Prompt Layer  
**状态**：Phase 2a/2b 已实现（2026-06-08）  
**前置**：[ADR Foundation Report](ADR_FOUNDATION_REPORT.md)  
**Classification**：[classifications/prompt-unified.md](classifications/prompt-unified.md)

---

## 1. 目标

将 Dual Prompt Architecture（`prompt_template.yaml` + `prompt_template_adult_extreme.yaml`）迁移为：

```
Base Prompt（单一 YAML，Shared 注入）
+
Mode Context（PromptStrategy，体验模式差异）
```

Builder **不读** `ADULT_MODE`；经 `PromptStrategy` 决策。

---

## 2. 已实现变更摘要

| 组件 | 变更 |
|------|------|
| [`prompt_template.yaml`](../prompt_template.yaml) | 统一 Base + `{{MODE_CONTEXT_*}}` / `{{BEHAVIOR_RULES}}` |
| [`engine/experience/prompt_strategy.py`](../engine/experience/prompt_strategy.py) | `ModeContext` + `build_mode_context()` |
| [`engine/builder.py`](../engine/builder.py) | `_build_prompt_unified()` 默认路径；legacy 回退 |
| [`config.py`](../config.py) | `is_extreme_tier()`, `use_legacy_extreme_template_file()` |
| [`engine/run.py`](../engine/run.py) | Compliance guard 经 `requires_content_guard()` 门控 |
| [`prompt_template_adult_extreme.yaml`](../prompt_template_adult_extreme.yaml) | @deprecated，保留至 §7 删除条件满足 |

---

## 3. Base Prompt（Shared 注入，所有模式一致）

- World / Memory（long_term, recent, hot）
- Character Brain / Objectives / Plot Director
- Relationship System / Characters / Engine Rules / Force Event
- 静态规则（状态机、角色分级、物品、势力）
- **统一 JSON schema**（含 `objective_updates`）

---

## 4. Mode Context（PromptStrategy）

### 4.1 ADR 权重

| 维度 | Story | Adult |
|------|-------|-------|
| World | 0.45 | 0.20 |
| Plot | 0.35 | 0.25 |
| Relationship | 0.20 | 0.55 |

### 4.2 层级

```
experience_mode (story | adult)
  └─ PromptWeights (world/plot/relationship)
       └─ content_weights (story/romance/adult)
            └─ intensity tier (low/medium/high/extreme)
```

### 4.3 ModeContext 字段

- `system_block` — 权重、成人铁律、extreme 优先级与内容规则
- `user_block` — intimacy escalation（extreme）
- `behavior_rules` — 文风/表达/内容偏好
- `task_hint` / `options_hint` / `main_goal_suffix` / `narrative_style_line`

---

## 5. adult_content_guard

**决策**：降级为 **Compliance Layer**（保留，不废弃）。

- PromptStrategy 表达期望；guard 作 options 质量兜底
- 不 post-patch `story` 正文
- `run.py` 经 `requires_content_guard()` 门控

---

## 6. prompt_template_adult_extreme.yaml

| 项 | 说明 |
|----|------|
| 当前状态 | @deprecated，仍打包 |
| 回退 | `PROMPTOS_USE_LEGACY_EXTREME_TEMPLATE=1` |
| 删除条件 | 见下方 §7（尚未满足，文件保留） |

---

## 7. 删除条件（Phase 2c，未执行）

1. 统一架构默认启用 ≥ 2 个小版本，无 rollback
2. `test_adult_extreme_prompt_unified` + guard + token 测试全通过
3. 人工抽检 adult_first extreme 10 局
4. Token ±10% 内
5. REGISTRY 更新

---

## 8. 风险与测试

- **存档**：无 schema 变更；兼容风险低
- **质量**：extreme 70% 从 schema 改为文本指令 — Compliance 保留 + 测试覆盖
- **Token**：净变化目标 ±10%

**必跑测试**：`test_adult_extreme_prompt.py`, `test_prompt_strategy_mode_context.py`, `test_builder_no_adult_mode_import.py`, `test_adult_content_guard.py`, `test_prompt_tokens.py`

---

## 9. 相关文档

- [ADR-001](../../doc/#%20ADR-001%20—%20Experience%20Mode%20Archite.txt)
- [REGISTRY.md](REGISTRY.md)
