# V6 World Bootstrap（One-click IP 初始化）

**状态**: Implemented  
**日期**: 2026-06-08

## 定位

一条命令把世界骨架搭满：**角色 + 地点 + 势力 + 事件 + 关系网**，可运行叙事底座（不进入演化层）。

```text
bootstrap_input → world_seed → LLM/Cursor 生成 JSON
  → validate_bootstrap_dataset()
  → apply_bootstrap_import()
  → world_pack + content_templates + relationship_graph + world_bootstrap.json
```

## 最小输入

```json
{
  "world_name": "PROJECT_V6_WORLD",
  "genre": "dark imperial fantasy / grounded cinematic fantasy",
  "tone": "cold, restrained, political tension",
  "scale": "medium (20~30 entities total)"
}
```

## CLI

```bash
# 打印 one-click prompt（给 Cursor / Agent）
python scripts/world_bootstrap.py prompt --config bootstrap_input.json

# 一键：有 API Key 则生成→校验→导入；无 Key 则输出 prompt
python scripts/world_bootstrap.py run --config bootstrap_input.json

# 仅生成 prompt
python scripts/world_bootstrap.py run --prompt-only --output bootstrap_prompt.txt

# 校验 / 导入已有 JSON
python scripts/world_bootstrap.py validate dataset.json
python scripts/world_bootstrap.py import dataset.json
```

## 默认规模

| 实体 | 数量 |
|------|------|
| characters | 10 |
| locations | 5 |
| factions | 2 |
| events | 8 |

## 校验（STEP 7）

- 结构：event 绑定 character + location；faction 绑定角色
- 风格：Style Bible v1（无 drift marker）
- 冲突：角色 conflict_vector、faction hidden_goal、event conflict

## 输出文件

| 路径 | 内容 |
|------|------|
| `world_pack.yaml` | title/genre/tone + 实体 |
| `content_templates.json` | IP 桶 + style_bible 更新 |
| `relationship_graph.json` | 关系边 |
| `data/world_bootstrap.json` | 完整 bootstrap 快照 |

## 文件

- `engine/templates/world_bootstrap.py`
- `scripts/world_bootstrap.py`
- `packaging/defaults/world_content_pack.yaml`（`prompts.bootstrap`）
