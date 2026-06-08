# V6 Freeze Decision（架构冻结决议）

**日期**: 2026-06-08  
**状态**: ❄️ **FROZEN**（结构层冻结，内容层可增长）  
**综合评分**: **80 / 100**（20 / 25）

---

## 定性结论

V6 已完成 **Controlled Visual World Runtime（可控视觉世界运行时）**：

> 架构完整 · 流程闭环 · 质量控制就位 · 只读 UI 就绪  
> 缺口在 **产品集成**（主游戏未接、`VISUAL_PROVIDER=stub` 默认），不在架构层。

**阶段**：Architecture complete · Runtime partial · Product integration missing · Evolution NOT needed

---

## 必须保留（核心骨架）

| 组件 | 路径 | 不可删原因 |
|------|------|------------|
| Visual Runtime | `engine/visual/visual_runtime.py` | 唯一合法入口 `get_visual()` |
| Identity | `visual_identity.py`, `identity_registry.py`, `identity_prompt_builder.py` | 稳定长相锚定 |
| Style Bible v1 | `engine/templates/style_bible.py` | ENGINE 层视觉 token 约束 |
| Prompt Canonical | `engine/visual/prompt_canonical.py` | 确定性 hash |
| Provider Factory | `provider_factory.py`, `agnes_visual_provider.py` | 可切换后端 |
| Registry + Cache | `visual_registry.py`, `visual_cache.py` | 资产复用与追溯 |
| Drift Detector | `engine/visual/style_drift.py` | 漂移反馈（prompt proxy v1） |
| Quality Governance | `engine/visual/quality_governance.py` | 质量门控（启发式 v1） |

---

## 建议合并（冗余收敛 — 冻结后逐步做，不改 pipeline）

### 1. Style Bible 双体系 → 分层命名，ENGINE 引用 WORLD

| 层 | 现路径 | 收敛后角色 |
|----|--------|------------|
| **ENGINE** | `style_bible.py` | 机器规则：token 注入、reinforce |
| **WORLD** | `content_templates.json` → `style_bible` | IP 语义：world_tone、visual_language |

**规则**：ENGINE 层优先读取 WORLD `style_bible` 补充语义；常量桶保留为 fallback，不再扩展新语义字段。

### 2. Prompt 双入口

| 文件 | 处置 |
|------|------|
| `identity_prompt_builder.py` | ✅ 唯一运行路径 |
| `visual_context.py` | 🟡 标记 deprecated；仅 debug/compat，禁止新引用 |

### 3. 世界内容三件套

```text
World Seed (Bootstrap)  →  world_pack + relationship_graph
Content Template        →  content_templates.json（authoring）
Visual Runtime          →  get_visual()（execution）
```

**规则**：Bootstrap 只写 Seed/Template；禁止 Bootstrap 绕过 `get_visual()` 写 registry。

---

## 冻结不动（完成态，性价比极低再改）

- Drift Detector v1（prompt proxy）
- Quality Governance v1（启发式）
- Registry schema v1
- L1/L2 Cache 策略
- Agnes provider 接口
- Visual API 只读契约（`/api/visual/*`）
- Narrative Entry 只读组装（V6.6）

---

## Freeze 后允许

- 角色 / 地点 / 事件 / 势力 **内容填充**（Bootstrap、Content Pack、手工 YAML/JSON）
- UI 体验优化（布局、文案、加载态）— **不新增生成 API**
- Prompt **微调**（token 文案，非 pipeline 结构）
- **预热钩子**（如 `/api/start` 调用 `get_or_request_character_portrait`）— 唯一推荐的 runtime 接线
- Provider 配置切换（`VISUAL_PROVIDER=agnes`）
- 测试与文档

## Freeze 后禁止

- 新 pipeline 阶段（如 CV drift、simulation layer）
- 新 runtime layer（memory graph、visual evolution、world state engine）
- 新 governance 系统
- UI 触达 `get_visual` / Provider（破坏只读原则）
- 修改 Registry 字段语义 / idempotency 规则
- `run.py` 全回合自动生图（scope 过大，冻结期不做）

---

## V6 Architecture Scoring Model

| 维度 | 分 | 满分 | 说明 |
|------|-----|------|------|
| Stability | 4.5 | 5 | pipeline 确定性、cache、fallback 完备 |
| Coherence | 4.0 | 5 | identity+style+drift+governance 协同；prompt≠image |
| Runtime Integrity | 4.0 | 5 | generate→validate→store→display 闭环；主游戏未接 |
| Extensibility | 4.5 | 5 | Provider/entity/template 易扩展 |
| Productization | 3.0 | 5 | stub 默认、画廊空直到显式生成/预热 |
| **合计** | **20** | **25** | **80 / 100** |

---

## V6 Final Form（冻结基准架构）

```text
        ┌──────────────┐
        │ World Seed   │  Bootstrap / Content Pack
        └──────┬───────┘
               ↓
   ┌────────────────────────┐
   │ Identity System        │  visual_identity_registry
   └────────┬───────────────┘
            ↓
   ┌────────────────────────┐
   │ Prompt Canonical Layer │  IP Template + Style Bible v1
   └────────┬───────────────┘
            ↓
   ┌────────────────────────┐
   │ Provider (Agnes/Stub)  │
   └────────┬───────────────┘
            ↓
   ┌────────────────────────┐
   │ Drift + Governance     │
   └────────┬───────────────┘
            ↓
   ┌────────────────────────┐
   │ Cache + Registry       │
   └────────┬───────────────┘
            ↓
   ┌────────────────────────┐
   │ Read-only UI           │
   └────────────────────────┘
```

---

## 冻结后唯一推荐 Runtime 接线

**Visual Prefetch on Start**：`/api/start` 成功后，对 `world_pack.characters` 中 NPC 调用 `get_or_request_character_portrait()`（可配置开关、可限流）。

理由：最小改动、打通「有世界 → 画廊有图」、不破坏 UI 只读、让质量闭环进入用户路径。

---

## CI / 自动化锁

```bash
python scripts/v6_freeze_check.py   # 架构锁自检
python -m pytest test_v6_freeze.py -q
```

GitHub Actions：`.github/workflows/v6_freeze_check.yml`（`V6_Freeze_Check`）

实现：`engine/visual/freeze_check.py` · `engine/visual/freeze_guard.py` · `config.V6_ARCHITECTURE_FROZEN`

## 相关文档

- 审计底稿：V6 系统报告（2026-06-08）
- 验收清单：[V6_FREEZE_CHECKLIST.md](./V6_FREEZE_CHECKLIST.md)
- 各层实现：`V6_VISUAL_RUNTIME_*`, `V6_STYLE_*`, `V6_VISUAL_QUALITY_*`, `V6_WORLD_*`
