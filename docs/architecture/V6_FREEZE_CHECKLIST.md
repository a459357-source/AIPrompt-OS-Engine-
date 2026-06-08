# V6 Freeze Checklist + Architecture Lock Rules

**用途**：PR / CI / Cursor 交付前自检  
**原则**：❄️ 冻结架构层，只允许内容层增长  
**自动化**：`python scripts/v6_freeze_check.py` · GitHub Actions `V6_Freeze_Check`

---

## Freeze Definition

V6 冻结完成 = 系统可稳定生成视觉资产 + 保持一致性 + **无需新增架构模块**。

**判断标准**：这个改动是在增强**内容**，还是在增加**系统层**？

| 类型 | 冻结期 |
|------|--------|
| 内容（角色/地点/事件/模板） | ✅ |
| 系统层（新 pipeline / governance / memory） | ❌ |

---

## 1. Architecture Lock

- [ ] 唯一入口：`get_visual()` 仅在 `visual_runtime.py` 定义一次
- [ ] 无新 visual pipeline 层
- [ ] 唯一 prompt builder 运行路径：`identity_prompt_builder.py`
- [ ] Provider 接口不变（stub / mock / agnes）
- [ ] Registry schema 稳定（仅可加 optional 字段）
- [ ] Cache 仍为 L1 内存 + L2 文件

**禁止**：新 generation framework · 新 AI evaluation 层 · world simulation · memory graph · 重复 Style Bible 系统

---

## 2. Data Flow Integrity

```text
entity → identity → prompt → provider → drift → governance → cache → registry → UI
```

**禁止**：绕过 Drift / Governance · UI 直接生图 · Provider 写 registry · cache 绕过 registry

---

## 3. Identity Stability

- [ ] 同 `entity_id` → 同 `identity_id`
- [ ] `identity_id` 创建后不变
- [ ] `visual_identity_registry` 追加式锁定

**禁止**：运行时重建 identity · 修改 `canonical_traits` · prompt 反向覆盖 identity

---

## 4. Style Bible Lock

- [ ] 单一 Style Bible v1（ENGINE）
- [ ] WORLD `content_templates.style_bible` 可扩展语义，不替换 ENGINE 桶结构
- [ ] 无 per-request 风格切换

---

## 5. Quality System Lock

- [ ] Drift 保持 prompt-proxy（无 CV）
- [ ] Governance 保持启发式（无 ML）
- [ ] `accept_weak` 仍写入 registry（带 `meta.quality_weak`）

---

## 6. Registry / Cache Immutability

- [ ] `make_asset_record` 必填字段不变（见 `freeze_check.py`）
- [ ] `prompt_hash` / `asset_id` 规则不变
- [ ] `scenes` → `events` 迁移逻辑保留

---

## 7. UI Freeze Rules

- [ ] `/api/visual/*` 仅 GET
- [ ] UI 不触发 `get_visual`（预热 API 除外，须 `feat(visual-prefetch)`）
- [ ] Narrative 层与 Visual Runtime 分离

---

## CI 命令（本地 = CI）

```bash
cd prompt-os-engine
python scripts/v6_freeze_check.py
python -m pytest test_v6_freeze.py test_visual_runtime.py test_visual_identity.py \
  test_style_drift.py test_quality_governance.py -q
```

GitHub Actions：`.github/workflows/v6_freeze_check.yml`

---

## Runtime Guard

```python
from engine.visual.freeze_guard import assert_no_arch_change

assert_no_arch_change("memory_graph layer")  # raises if V6_ARCHITECTURE_FROZEN=True
```

配置：`config.V6_ARCHITECTURE_FROZEN = True`

---

## 冻结后允许

新角色/地点/事件 · Content Template · Bootstrap · prompt 文案微调 · UI 美化 · `feat(visual-prefetch)`

## 永久禁止（审查打回）

新系统层 · 新 runtime pipeline · CV/ML 质量层 · memory/evolution · UI 一键生图

---

## 相关文档

- [V6_FREEZE_DECISION.md](./V6_FREEZE_DECISION.md)
- 实现：`engine/visual/freeze_check.py`, `engine/visual/freeze_guard.py`
