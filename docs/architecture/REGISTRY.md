# ADR-001 System Registry

摘自 ADR-001 §四、§五，供 Architecture Classification 对照。

## Shared System（全局唯一）

| 系统 | 当前实现（Phase 1） |
|------|---------------------|
| World | `world_pack.yaml`, `ui/routes/world.py` |
| CharacterBrain | `engine/character_brain.py` |
| Memory | `engine/memory.py`, `engine/memory_layers.py` |
| StoryGraph | `engine/router.py`, `data/story_graph.json` |
| ObjectiveSystem | `engine/objective_system.py` |
| EventDirector | `engine/events.py`, `engine/world_driver.py`（部分） |
| RelationshipDynamics | `relationship_core` … `relationship_event_resolver` — **V5.1 Stable**（Final Review APPROVED，见 `V5.1_FINAL_REVIEW_REPORT.md`） |
| FactionSystem | memory factions, world_pack |
| VisualAssets | **未实现**（V6.0） |
| SaveSystem | `engine/save_manager.py` |
| ContextRouter | `engine/context_router.py` |
| PlotDirector | `engine/plot_director.py` |
| ChapterSummary | memory_layers chapter summaries |
| WorldEvents | `engine/events.py` |
| NPCRegistry / CharacterRegistry | memory + world_pack |
| ArtifactRegistry | memory artifacts |
| MapSystem | world_pack locations |

**规则**：禁止双实现；禁止 StoryWorld / AdultWorld / StoryMemory 等命名。

## Mode Layer（可因体验模式不同）

| 系统 | 当前实现（Phase 1） |
|------|---------------------|
| Theme | `frontend/src/lib/theme.ts`, `AdultThemeContext` |
| Layout | Game 页布局（部分） |
| Dashboard | `Dashboard.tsx` i18n 标签 |
| CharacterPanel | `CharacterCard.tsx` |
| RelationshipPanel | `Game.tsx` AffectionBar |
| PromptWeight | `content_weights`, `adult_profile` |
| VisualPriority | `visual_theme` |
| TransitionAnimation | 未实现 |
| ImagePresentation / ScenePresentation | 未实现 |
| ExperienceStrategy | `engine/experience/experience_strategy.py`（骨架） |
| ViewStrategy | 未实现（Game.tsx 内联） |
| ThemeStrategy | `engine/experience/theme_strategy.py`（骨架） |
| PromptStrategy | `engine/experience/prompt_strategy.py`（**Phase 2 已接入 builder**） |

**规则**：Mode Layer 可不同；Shared System 必须一致。
