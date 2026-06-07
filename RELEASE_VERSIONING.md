# PromptOS 发布版本规则

采用 **SemVer**：`主版本.次版本.修订号`（`MAJOR.MINOR.PATCH`），单一来源为 `config.py` 的 `APP_VERSION`（打包时同步 `engine.yaml`）。

发布包文件名：`release/PromptOS-win64-v{APP_VERSION}.zip`

## 发布类型与命令

| 发布类型 | 版本示例 | 命令 | 何时使用 |
|----------|----------|------|----------|
| 修 bug / 小更新 | `2.0.1` | `python build_release.py` | 默认：**修订号 patch +1**；BUG 修复、小优化、打包/文档调整 |
| 新功能（兼容） | `2.1.0` | `python build_release.py --version 2.1.0` | 新增功能且**旧存档/配置仍可用**；升 **次版本 MINOR** |
| 大改版（不兼容） | `3.0.0` | `python build_release.py --version 3.0.0` | 存档/API/流程不兼容；升 **主版本 MAJOR** |
| 重打同版本 zip | `2.0.0` | `python build_release.py --no-bump` | 版本号不变，仅重新打包 |

## 判断口诀

```
旧存档/旧配置会不会用不了？
  ├─ 会 → 主版本（如 3.0.0）
  └─ 不会 → 有没有新功能？
        ├─ 有 → 次版本（如 2.1.0）
        └─ 没有 → 修订号（默认 build_release.py）
```

## 当前版本

- **3.1.0** — V3.1 Plot Director：主线进度与伏笔追踪、`DIRECTOR_ADVICE` 弱约束注入、Dashboard「剧情导演」面板。

## 术语说明

| 术语 | 对应段 | 示例 |
|------|--------|------|
| 主版本 / 大版本 | MAJOR | `2.x.x` → `3.0.0` |
| 次版本 / 小版本（功能） | MINOR | `2.0.x` → `2.1.0` |
| 修订号 / 小版本（日常） | PATCH | `2.0.0` → `2.0.1`（**默认打包行为**） |

口语里的「小版本」可能指 PATCH 或 MINOR；**本仓库默认「每次打包 +1」指 PATCH（第三位）**。

## 与产品代际的关系

- **V2**（如 PromptOS v2.0.0）指产品大代际，对应 SemVer **主版本 = 2**
- 日常发布在其下递增：`2.0.1`、`2.1.0` 等

## 打包前检查

1. 交付前自检通过（见 `.cursor/rules/verification-before-delivery.mdc`）
2. `python build_release.py` 会自动清理个人数据（见 `release-build.mdc`）
3. 确认 zip 内无 `sk-` 密钥
4. 大/次版本发布后建议打 Git tag：`git tag -a v2.1.0 -m "..."` 并 push
