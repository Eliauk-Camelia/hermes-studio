# Camelia Studio

受 [Hermes Studio](https://github.com/EKKOLearnAI/hermes-studio) 启发，自建的本地 AI Agent 平台。

> **Camelia** = 山茶花。花语：理想、谦逊、坚韧。

## 架构

```
src/agent.py  ──  单文件 Agent，自包含
    │
    ├── call_llm()      给 LLM 打电话（OpenAI 兼容 API）
    ├── agent_loop()    Agent 大脑循环（Tool Calling）
    └── execute_tool()  工具执行器
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key

# 3. 运行
python src/agent.py
```

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | API 密钥（必填） | - |
| `OPENAI_BASE_URL` | API 地址 | `https://api.deepseek.com/v1` |
| `LLM_MODEL` | 模型名 | `deepseek-chat` |

## 路线图

- [x] v0.0.1 Agent 核心循环（Tool Calling 引擎）
- [ ] v0.0.2 Web 聊天界面（FastAPI + WebSocket）
- [ ] v0.0.3 文件系统工具（读写文件、执行命令）
- [ ] v0.0.4 硬件控制（MSPM0 / STM32 串口通信）
- [ ] v0.0.5 多端互通（CLI + Web + Telegram）
- [ ] v0.0.6 对话记忆持久化
- [ ] v0.1.0 可扩展工具插件系统

## 致谢

本项目架构受 [Hermes Studio](https://github.com/EKKOLearnAI/hermes-studio) (EKKOLearnAI) 和 [Hermes Agent](https://github.com/NousResearch/hermes-agent) (NousResearch) 启发。
