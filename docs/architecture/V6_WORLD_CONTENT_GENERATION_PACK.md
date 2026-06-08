# V6 World Content Generation Template Pack

**状态**: Implemented  
**日期**: 2026-06-08

## 定位

不改 V6 架构，提供 **结构化 IP 批量生成** 的 prompt 模板、校验器与导入器。

```text
AI / Cursor 生成 JSON
  → validate_world_dataset()
  → apply_dataset_import() → world_pack + content_templates
  → V6 Identity / Style Bible / Visual Runtime 自动兼容
```

## 文件

| 路径 | 职责 |
|------|------|
| `packaging/defaults/world_content_pack.yaml` | Prompt 模板 + 批量规则 + Style 约束 |
| `engine/templates/world_content_pack.py` | Prompt 构建、校验、导入 |
| `scripts/world_content_batch.py` | CLI |

## CLI 用法

```bash
# 一次性完整世界骨架 prompt
python scripts/world_content_batch.py prompt --full

# 单类批量 prompt
python scripts/world_content_batch.py prompt --type character --count 10

# 校验 AI 输出 JSON
python scripts/world_content_batch.py validate dataset.json

# 导入到 world_pack + content_templates
python scripts/world_content_batch.py import dataset.json
```

## 默认批量计划

- 10 characters
- 5 locations
- 8 events
- 2 factions

## 校验规则

- 角色：archetype / conflict_vector 不重复，必须有 faction
- 地点：必须有 function，禁止 drift marker
- 事件：绑定 ≥1 角色 + 1 地点
- 全局：Style Bible 一致性（无 cyberpunk/neon 等）

## 一键 Bootstrap

完整世界初始化见 `V6_WORLD_BOOTSTRAP.md`（`scripts/world_bootstrap.py run`）。

## 与 V6 关系

| 层 | 关系 |
|----|------|
| Content Templates | 导入后自动填充 IP 桶 |
| Identity | world_pack.characters 字段 identity-ready |
| Style Bible | prompt 强制注入视觉约束 |
