# Architecture Classification — Prompt Unified Architecture

## Feature

Prompt Unified Architecture (V4.0 Prompt Layer)

## Classification

Mode Layer（PromptStrategy）+ Base Prompt 模板重构

Shared System 注入模块（Memory / CharacterBrain / PlotDirector / ObjectiveSystem）**不修改内部实现**，仅保证 Base Prompt 始终注入。

## Affected Modules

- `prompt_template.yaml`
- `engine/builder.py`
- `engine/experience/prompt_strategy.py`
- `engine/experience/experience_strategy.py`
- `config.py`（`is_extreme_tier`, legacy flag, adult_* 保留供 Compliance）
- `engine/adult_content_guard.py`（Compliance Layer 门控）
- `engine/run.py`（guard 门控）
- `test_adult_extreme_prompt.py`, `test_prompt_strategy_mode_context.py`

## Notes

- 单一 Base Prompt + Mode Context；禁止双 YAML 维护（legacy flag 仅 emergency rollback）
- extreme tier 不再省略 `{{OBJECTIVES_CONTEXT}}`；JSON schema 统一含 `objective_updates`
- Builder 不读 `ADULT_MODE`；经 `PromptStrategy` 决策
- `prompt_template_adult_extreme.yaml` 已 @deprecated，删除条件见 `PROMPT_UNIFIED_DESIGN.md` §7.3
