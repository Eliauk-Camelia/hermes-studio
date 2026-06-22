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

| 版本 | 目标 | 状态 |
|---|---|---|
| v0.0.1 ~ v0.0.4 | 核心引擎 + 聊天界面 + 文件工具 + 串口硬件 | ✅ |
| v0.0.5 | 多提供商支持 + Electron 桌面壳 | ✅ 当前 |
| v0.0.6 | 持久化记忆：向量存储 + RAG 语义检索 | 下一步 |
| v0.0.7 | Monaco Editor + 文件树 | |
| v0.0.8 | xterm.js 终端面板 | |
| v0.0.9 | 嵌入式一键烧录（OpenOCD / DSLite） | |
| v0.0.10 | AI 调参闭环（PID 自整定 / 滤波器 / 传感器标定） | |
| v0.1.0 | 三面板 IDE 整合 + 可扩展工具插件系统 | |

> 详见 [ROADMAP.md](./ROADMAP.md) — 三大支柱：IDE 壳 + 嵌入式工具链 + 持久化记忆

## 致谢

本项目架构受 [Hermes Studio](https://github.com/EKKOLearnAI/hermes-studio) (EKKOLearnAI) 和 [Hermes Agent](https://github.com/NousResearch/hermes-agent) (NousResearch) 启发。
