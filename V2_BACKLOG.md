# PromptOS v2.0.0 — 后续小版本待办

> v2.0.0 发布时已知、但不阻塞正常游玩的问题。按优先级排列，供 v2.0.x / v2.1 迭代。

## P2（体验/一致性）

| 项 | 说明 |
|---|---|
| export_format 与手动导出不联动 | Settings 可选 markdown/text/html，但 `downloadStoryExport()` 固定 GET /export（Obsidian Markdown）；自动导出走 `story_export.py` 可能尊重格式，手动按钮不一致 |
| CharacterCard 不展示 background / special_ability | NPCs 页传入字段，但卡片组件未渲染；NewStory 已可编辑，信息链断裂 |
| 设置同步失败静默 | `syncEngineSettingsToBackend`、`getAppSettings`、存档列表刷新失败多 `.catch(() => {})`，用户无感知 |

## P3（增强/工程）

| 项 | 说明 |
|---|---|
| generateNpc 无 role_hint UI | 后端支持职业提示，前端一键生成无法指定类型 |
| i18n 不完整 | 部分 UI 仍为硬编码中文 |
| POST /shutdown 无 token 校验 | 本地开发便利优先，生产/多用户场景需加固 |
| run.py 冗余 import | 代码卫生，不影响运行 |
| 前端 bundle 体积 | Vite 提示主 chunk >500KB，可后续 code-split |
| Starlette TestClient 弃用警告 | 可迁移至 httpx2 |

## 测试/CI

| 项 | 说明 |
|---|---|
| test_e2e.py | 需本地服务 `:8765`，CI 默认跳过 |
| test_e2e_data.py | 依赖运行时 session 文件，非单元测试 |
