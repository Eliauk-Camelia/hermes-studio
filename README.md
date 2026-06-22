# Camelia Studio

受 [Hermes Studio](https://github.com/EKKOLearnAI/hermes-studio) 启发，自建的本地 AI Agent 平台。

> **Camelia** = 山茶花。花语：理想、谦逊、坚韧。

## 架构

```
electron/       桌面壳 — 原生窗口 + 加密存储 + 自动更新
src/agent.py    Agent 引擎 — 单文件自包含，8 个工具 + 流式输出
src/server.py   Web 服务 — FastAPI + WebSocket 实时推送
src/static/     聊天界面 — 山茶花深色主题，响应式布局
```

### 8 个内置工具

`get_time` · `calc` · `read_file` · `write_file` · `list_dir` · `run_command` · `list_serial_ports` · `read_serial`

## 快速开始

```bash
# ── Electron 桌面应用（推荐）──
cd electron && npm install
./run-electron.sh                   # 开发模式，首次启动引导配置 API Key

# ── 纯 Python 模式 ──
pip install -r requirements.txt
cp .env.example .env                # 编辑 .env，填入 API Key
python src/server.py                # Web 界面 http://localhost:8648
python src/agent.py                 # CLI 终端模式
```

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | API 密钥（必填） | - |
| `OPENAI_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名 | `deepseek-chat` |

## 路线图

- [x] v0.0.1 Agent 核心循环（Tool Calling 引擎）
- [x] v0.0.2 Web 聊天界面（FastAPI + WebSocket + 流式输出）
- [x] v0.0.3 文件系统工具（读写文件、执行命令、路径沙箱）
- [x] v0.0.4 硬件控制（MSPM0 / STM32 串口通信）
- [ ] v0.0.5 多提供商 + Electron 桌面壳 + 会话管理 ⬅ 当前
- [ ] v0.0.6 对话记忆持久化 + 会话标题自动生成
- [ ] v0.1.0 可扩展工具插件系统

## 致谢

本项目架构受 [Hermes Studio](https://github.com/EKKOLearnAI/hermes-studio) (EKKOLearnAI) 和 [Hermes Agent](https://github.com/NousResearch/hermes-agent) (NousResearch) 启发。
