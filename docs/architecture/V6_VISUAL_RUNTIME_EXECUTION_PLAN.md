# V6 Visual Runtime System — 最终执行版

**状态**: Approved for Implementation  
**日期**: 2026-06-08  
**定位**: 可交付、可实现；无 UI / 无 async 队列 / 无多模态扩展

---

## 唯一定义

> Narrative 对象（角色 / 地点 / 势力 / 事件）自动映射为可缓存、可复用的视觉资产。

```text
Narrative Layer（文本世界）
        ↓
Visual Runtime Core（get_visual）
        ↓
Asset System（Registry + Cache L1/L2）
        ↓
Provider Layer（Agnes / Stub）
        ↓
Visual Output（image_path）
```

---

## 四类视觉对象（V6 Freeze）

| entity_type | 说明 | 禁止扩展 |
|-------------|------|----------|
| `character` | 角色立绘 | ✅ |
| `location` | 地点 / 世界地图 | ✅ |
| `faction` | 势力视觉标识 | ✅ |
| `event` | 事件场景图 | ✅ |

---

## 模块与文件映射

| Module | 文件 |
|--------|------|
| M1 Entry | `engine/visual/visual_runtime.py` → `get_visual()` |
| M2 VisualObject | `engine/visual/visual_object.py` |
| M3 Prompt Canonical | `engine/visual/prompt_canonical.py` |
| M4 Registry | `engine/visual/visual_registry.py` |
| M5 Cache | `engine/visual/visual_cache.py` |
| M6 Provider | `engine/visual/visual_provider.py` + `provider_factory.py` + `agnes_visual_provider.py` |
| M7 Failure | `visual_runtime.py`（retry + stub fallback） |
| M8 数据流 | 仅 `get_visual` → runtime → cache/registry/provider |

---

## 固定流程

```text
get_visual(entity_type, entity_id, context)
  → build VisualObject
  → normalize_prompt → prompt_hash
  → Registry lookup（entity_id + prompt_hash）
  → L1 memory cache
  → L2 filesystem cache
  → Provider（miss only, retry, fallback stub）
  → store cache + registry
  → return { image_path, ... }
```

---

## 禁止项（V6 Freeze）

- UI / Dashboard / Gallery（V6.5+）
- async 队列
- 视频 / 音频
- graph UI / 关系图谱
- AI 自动改 prompt 风格
- Provider 直接写 Registry
- UI 直接调 Provider
- `adult_mode` / `experience_mode` / `visual_theme` 影响生成

---

## 验收清单

### 功能
- [ ] 四类对象均可 `get_visual` 生成
- [ ] cache 命中不调 provider
- [ ] registry 可复用 asset
- [ ] prompt_hash 规范化稳定
- [ ] provider 可切换 stub/agnes
- [ ] provider 失败 fallback stub
- [ ] retry 2–3 次

### 执行顺序（已完成收敛）

1. VisualObject + get_visual + normalize_prompt  
2. registry + cache  
3. provider + Agnes  
4. retry + fallback + idempotency  

---

## V6.1 预留（本版本不做）

「一致性视觉人格系统」— 角色跨回合视觉锚定；需 ADR 后再开。
