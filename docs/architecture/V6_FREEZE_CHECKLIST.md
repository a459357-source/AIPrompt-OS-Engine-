# V6 Freeze Checklist（冻结验收清单）

**用途**：PR / 发布前自检，防止冻结后架构 drift into complexity。  
**原则**：改内容 ✅ · 改结构 ❌

---

## A. 架构边界（必过）

- [ ] 视觉生成仍只经 `get_visual()`（`visual_runtime.py`）
- [ ] 无新代码直接写 `visual_registry.json`（须经 `make_asset_record` + `save_registry`）
- [ ] Provider 仍只经 `get_visual_provider()`，业务层不直引 Agnes
- [ ] `/api/visual/*` 仍为只读，无 POST 触发生成
- [ ] `run.py` `step()` 未嵌入全回合自动生图（预热钩子除外，须独立模块）

---

## B. 冻结文件（结构变更需 ADR）

以下文件 **禁止** 行为性修改（注释/文档除外）：

| 文件 | 冻结内容 |
|------|----------|
| `engine/visual/visual_runtime.py` | `get_visual` 主流程、缓存层级顺序 |
| `engine/visual/visual_object.py` | idempotency 规则、四类 entity |
| `engine/visual/visual_registry.py` | scope 名、record schema |
| `engine/visual/style_drift.py` | 评分公式、三级策略 |
| `engine/visual/quality_governance.py` | 三层权重 0.4/0.3/0.3、阈值 |
| `engine/templates/style_bible.py` | `STYLE_BIBLE_V1` 桶结构 |
| `engine/visual/identity_prompt_builder.py` | pipeline 顺序（IP→Style Bible） |

**允许**：config 开关、阈值常量、日志文案。

---

## C. 冗余收敛（技术债，非阻塞）

- [ ] 无新 import `visual_context.py`（grep 为零新增）
- [ ] Style Bible：新语义只写 `content_templates.style_bible`，不扩 ENGINE 常量桶
- [ ] Bootstrap 输出只走 `apply_bootstrap_import`，不直写 registry

---

## D. 自检命令（交付前）

```bash
cd prompt-os-engine

# 视觉 + 质量 + 模板 + bootstrap
python -m pytest test_visual_api.py test_visual_runtime.py test_visual_identity.py \
  test_visual_provider.py test_style_bible.py test_style_drift.py test_quality_governance.py \
  test_content_templates.py test_world_content_pack.py test_world_bootstrap.py \
  test_narrative_entry.py -q

# import 冒烟
python -c "from engine.visual.visual_runtime import get_visual; from engine.templates.world_bootstrap import validate_bootstrap_dataset; print('ok')"

# 前端（动 UI 时）
cd frontend && npm run build
```

**通过标准**：上述 pytest 全绿；无新增 `visual_context` 运行路径引用。

---

## E. Config 冻结默认值（参考）

| 开关 | 冻结默认 | 说明 |
|------|----------|------|
| `VISUAL_SYSTEM_ENABLED` | True | |
| `VISUAL_PROVIDER` | stub | 生产切 agnes |
| `STYLE_BIBLE_V1_ENABLED` | True | |
| `STYLE_DRIFT_DETECTOR_ENABLED` | True | |
| `VISUAL_QUALITY_GOVERNANCE_ENABLED` | True | |
| `CONTENT_TEMPLATE_SYSTEM_ENABLED` | True | |

---

## F. PR 标题规则（建议 CI / 人工审查）

| 前缀 | 冻结期 |
|------|--------|
| `feat(visual-runtime):` | ❌ 需 ADR + 架构评审 |
| `feat(visual-ui):` | ✅ UI polish |
| `feat(visual-prefetch):` | ✅ 唯一允许的 runtime 接线 |
| `feat(content):` / `feat(bootstrap):` | ✅ 内容/IP |
| `fix(visual):` | ✅ bug，不改 schema |
| `docs(architecture):` | ✅ |

---

## G. 显式禁止项（审查打回）

- 新 governance / drift / memory / evolution 层
- ML/CV 图像分析接入 pipeline
- Registry schema 破坏性变更
- UI「一键生图」按钮调用 provider
- 删除或绕过 Drift / Quality 阶段

---

## H. 冻结解除条件（未来）

仅当以下 **全部** 满足才可讨论 V7：

1. Visual Prefetch 已接且画廊默认可用
2. `VISUAL_PROVIDER=agnes` 生产验证通过
3. 图像级 QA 有明确 ADR（非冻结期内实现）
4. 主游戏与 Visual 集成方案经单独评审
