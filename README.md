# PromptOS v2.0.0

AI 驱动的交互式叙事引擎（Galgame Runtime）：每回合调用 DeepSeek 生成分支剧情，维护角色记忆、势力关系与剧情图。

**v2 主要变化**：分层记忆、世界状态 V2 仪表盘、生成参数与目标字数联动、成人模式与世界生成整合、打包前自动清理个人数据。

## 功能概览

- **新故事**：配置世界观、角色、势力与关系标签，一键开局
- **游戏**：回合制选项推进，多维关系指标实时展示
- **角色 / 仪表盘**：NPC 状态与出场频率、好感度曲线
- **设置**：API Key、模型参数、阅读样式等

## 开发环境运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（二选一）
#    环境变量：DEEPSEEK_API_KEY=sk-...
#    或启动后在 Web UI → 设置 中填写

# 3. 启动后端
python engine/run.py --mode web

# 4. 启动前端（另开终端）
cd frontend
npm install
npm run dev
```

| 服务 | 地址 |
|------|------|
| 后端 API | http://localhost:8000 |
| 前端 UI | http://localhost:5173（代理到后端） |

首次打开且未保存 Key 时，会弹出引导窗口；也可在「设置」页填写。

## Windows 发布包（exe）

```bash
python build_release.py
```

产物：

| 路径 | 说明 |
|------|------|
| `dist/PromptOS/PromptOS.exe` | 可执行程序（内置前端，单端口 8000） |
| `release/PromptOS-win64-v{版本}.zip` | 发给用户的压缩包（含版本号，如 `v2.0.1`） |

**版本规则**（详见 [`RELEASE_VERSIONING.md`](RELEASE_VERSIONING.md)）：

| 发布类型 | 版本示例 | 命令 |
|----------|----------|------|
| 修 bug / 小更新 | `2.0.1` | `python build_release.py` |
| 新功能（兼容） | `2.1.0` | `python build_release.py --version 2.1.0` |
| 大改版（不兼容） | `3.0.0` | `python build_release.py --version 3.0.0` |
| 重打同版本 zip | `2.0.0` | `python build_release.py --no-bump` |

**给他人使用：**

1. 只发送 `release/PromptOS-win64-v*.zip`（不要附带 `data/`）
2. 解压后双击 `PromptOS.exe`（或 `release/启动 PromptOS.bat`）
3. 首次运行按弹窗填写 **DeepSeek API Key**（保存在本机 `data/apikey.json`）
4. 在「新故事」创建世界并开始游戏

**注意：**

- 发布包内不含任何 API Key
- exe 不会读取打包者机器上的 `DEEPSEEK_API_KEY` 环境变量
- 在本机测试 zip 前，建议临时删除环境变量 `DEEPSEEK_API_KEY`，避免误判

详见 `release/使用说明.txt`。

## 测试

```bash
python -m pytest test_state_machine.py test_memory.py test_graph.py test_save.py test_events.py test_analytics.py test_api.py -q
```

## 目录

```
engine/          核心叙事引擎
ui/              FastAPI Web / CLI
frontend/        React SPA
packaging/       exe 出厂默认数据
scripts/         重置用户数据等工具
build_release.py 一键打包
launcher.py      exe 入口
data/            运行时数据（个人进度，勿提交）
data/app.log     运行日志（bat / exe 启动后自动生成）
data/error.log   错误日志（含未捕获异常）
release/         发布 zip 与使用说明
```

上级目录另有 [CONTEXT.md](../CONTEXT.md)、[PROJECT_REPORT.md](../PROJECT_REPORT.md) 供 AI 助手与架构参考。
