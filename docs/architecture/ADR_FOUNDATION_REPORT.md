# ADR Foundation Report — Phase 1

**版本**：Phase 1 Foundation Layer  
**日期**：2026-06-08  
**状态**：已完成，等待 Phase 2 评审  

---

## 1. 目标与范围

Phase 1 建立 ADR-001 基础设施层，**不**重构 Shared System、**不**合并 Prompt、**不**改 UI。

### 已完成

| 项 | 说明 |
|----|------|
| experience_mode 兼容层 | `story` / `adult` 双写 `adult_mode` |
| Strategy 骨架 | `engine/experience/` 三模块，stub 实现 |
| ADR Enforcement | `docs/architecture/` 分类模板与注册表 |
| Shared 边界修复 | `world_init` 含 `plot_state`；`/reset` 同步恢复 objectives |

### 本阶段未做（刻意保留）

- 合并 `prompt_template_adult_extreme.yaml`
- 删除 `adult_mode` / `adult_content_guard`
- 重构 `Game.tsx` / `NewStory.tsx`
- 修改 `builder.py` / `run.py` 生成链路
- 修改 CharacterBrain / Memory / ContextRouter 等 Shared 核心

---

## 2. experience_mode 兼容旧系统

### 语义

| experience_mode | 含义 | 内部 adult_mode |
|-----------------|------|-----------------|
| `story` | World Perspective（默认） | `false` |
| `adult` | Character Perspective | `true` |

### 兼容矩阵

| 场景 | 行为 |
|------|------|
| 旧 settings 仅含 `adult_mode: true` | `_load_experience_mode()` fallback → `"adult"` |
| 旧存档 snapshot 仅含 `adult_mode` | `save_manager.load()` fallback → `save_adult_mode()` |
| 新写入 settings | 双写 `experience_mode` + `adult_mode` |
| 新写入存档 | snapshot 含 `experience_mode`（优先）+ `adult_mode` |
| API POST `experience_mode=adult` | `save_experience_mode()`，同步 adult_mode |
| API POST `adult_mode=true`（legacy） | `save_adult_mode()`，同步 experience_mode |
| 同时传两者 | **`experience_mode` 优先**（settings.py / api.py） |
| unlock 门控 | `experience_mode=adult` 仍须 `is_adult_unlocked()` |
| 前端 | 仍读 `adult_mode`（未改 Game.tsx） |

### 实现位置

- `config.py` — `normalize_experience_mode`, `save_experience_mode`, `get_experience_mode`, `reload_experience_mode`
- `engine/save_manager.py` — snapshot 读写
- `ui/routes/settings.py` — GET/POST `experience_mode`
- `ui/routes/api.py` — `/game-settings` Form 字段

---

## 3. Strategy 骨架与 Phase 2 接入点

```
engine/experience/
├── __init__.py
├── experience_strategy.py   # get_experience_mode(), is_story(), is_adult()
├── prompt_strategy.py       # PromptStrategy stub — Phase 2 接入 builder.py
└── theme_strategy.py        # ThemeStrategy stub — Phase 3 接入 frontend
```

**Phase 1 约束**：现有 `config.adult_*`、`builder.py`、`run.py` **不 import** 上述模块，避免行为变更。

### Phase 2 接入点（规划）

| 模块 | 接入目标 |
|------|---------|
| `prompt_strategy.get_mode_context_block()` | 替代 `config.adult_*_text()` 散布注入 |
| `prompt_strategy.get_prompt_weights()` | 替代 content_weights 硬编码比例 |
| `prompt_strategy.get_template_path_hint()` | 逐步废弃双 YAML 切换 |

---

## 4. world_init / reset 边界修复

### 问题（审计）

- `world_init.json` 不含 `plot_state`
- `/reset` 不恢复 plot_state，导致 objectives 与 plot 进度漂移

### 修复

**`/new`（world.py）**：`world_init` 结构扩展为：

```json
{
  "state": { ... },
  "graph": { ... },
  "memory": { ... },
  "plot_state": { ... }
}
```

**`/reset`（game.py）**：

1. `commit_bundle(state, memory, graph)`
2. 恢复 `plot_state`（来自 world_init；legacy 无字段则 `init_plot_state(world_pack)`）
3. `ensure_objectives` + `sync_main_objective_progress`
4. 写回 `session_state.yaml`

**向后兼容**：旧 `world_init.json` 无 `plot_state` 时 fallback 初始化，不破坏现有存档。

---

## 5. 新增文件列表

| 路径 | 类型 |
|------|------|
| `engine/experience/__init__.py` | 代码 |
| `engine/experience/experience_strategy.py` | 代码 |
| `engine/experience/prompt_strategy.py` | 代码 |
| `engine/experience/theme_strategy.py` | 代码 |
| `docs/architecture/README.md` | 文档 |
| `docs/architecture/CLASSIFICATION_TEMPLATE.md` | 文档 |
| `docs/architecture/REGISTRY.md` | 文档 |
| `docs/architecture/ADR_FOUNDATION_REPORT.md` | 文档 |
| `test_experience_mode.py` | 测试 |
| `test_world_init_reset.py` | 测试 |

### 修改文件（最小）

| 路径 | 变更 |
|------|------|
| `config.py` | experience_mode API |
| `engine/save_manager.py` | snapshot 字段 |
| `ui/routes/settings.py` | GET/POST experience_mode |
| `ui/routes/api.py` | Form 字段 |
| `ui/routes/world.py` | world_init 含 plot_state |
| `ui/routes/game.py` | reset 恢复 plot_state + objectives |

---

## 6. Phase 2 准备度评估

### Readiness Checklist

| 检查项 | Phase 1 后状态 | Phase 2 要求 |
|--------|---------------|-------------|
| experience_mode 语义入口 | ✅ 已建立，双写兼容 | 可逐步退役仅读 adult_mode |
| PromptStrategy 接口 | ✅ stub 存在 | 需覆盖 config.adult_* 全量函数 |
| 双 template diff 清单 | ⚠️ 未合并 | 需逐段 diff default vs extreme |
| objectives 在 extreme 模板 | ⚠️ 仍缺失 | Phase 2 须恢复 Shared 注入 |
| adult_content_guard | ⚠️ 仍独立 | 需决策：Compliance Layer vs PromptStrategy hint |
| builder.py 接入 Strategy | ❌ 未接入 | Phase 2 核心工作 |
| CI grep 禁止 Story*/Adult* Shared | ❌ 未加 | 可选 Phase 2 |

### config.adult_* 迁移清单（Phase 2 参考）

需逐步迁入 `PromptStrategy` 的函数（config.py）：

- `adult_system_override_text`, `adult_main_goal_suffix`
- `adult_options_hint_text`, `adult_task_hint_text`, `adult_choice_execution_hint`
- `adult_extreme_*_text` 系列
- `content_preference_rules_text`, `ai_behavior_rules_text` 中的 adult 分支
- `resolve_prompt_template_path` / `use_adult_extreme_template`

### extreme vs default 模板关键 diff

| 项 | default | extreme |
|----|---------|---------|
| `{{OBJECTIVES_CONTEXT}}` | 有 | **无** |
| `{{INTIMACY_ESCALATION_HINT}}` | 无 | 有 |
| JSON schema objective_updates | 有 | **无** |
| story 色情比例要求 | 按 tier | 70%+ 硬要求 |

### Phase 2 预估 touch 范围

- `config.py`（adult_* 逐步委托 PromptStrategy）
- `engine/builder.py`（注入 Mode Context）
- `prompt_template.yaml`（统一 Base）
- `prompt_template_adult_extreme.yaml`（废弃或合并）
- `engine/adult_content_guard.py`（策略决策）
- 测试：`test_adult_extreme_prompt.py`, `test_prompt_tokens.py`

### 建议 Phase 2 入口条件

1. 本 Foundation Report 评审通过
2. Architecture Classification 流程已纳入团队习惯
3. 明确 extreme tier 与 Compliance（unlock/guard）的分层文档

---

## 7. 结论

Phase 1 已完成 ADR-001 基础设施：**experience_mode 兼容层**、**Strategy 骨架**、**分类 enforcement 文档**、**reset/plot_state 一致性**。

**暂停开发**，等待 Phase 2（Prompt Unified Architecture）评审后再继续。

**不得提前进入**：Prompt 模板合并、adult_mode 删除、UI 重构。
