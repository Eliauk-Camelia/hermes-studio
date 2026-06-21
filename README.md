# Hermes Studio

自建的本地 AI Agent 平台。

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

- [x] v0.1.0 Agent 核心循环（Tool Calling 引擎）
- [ ] v0.2.0 Web 聊天界面（FastAPI + WebSocket）
- [ ] v0.3.0 文件系统工具（读写文件、执行命令）
- [ ] v0.4.0 硬件控制（MSPM0 / STM32 串口通信）
- [ ] v0.5.0 多端互通（CLI + Web + Telegram）
- [ ] v0.6.0 对话记忆持久化
- [ ] v1.0.0 可扩展工具插件系统
