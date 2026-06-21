# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

Camelia Studio — 受 Hermes Studio 启发的手写 AI Agent 学习项目。**用户是大二嵌入式学生，此项目是他在 AI 领域的延伸探索。代码必须是用户自己写的，Claude 只提供思路和提示，不代写。**

## 运行方式

```bash
# .env 自动加载，无需手动 source
python src/agent.py
```

## 架构

单文件 Agent（`src/agent.py`，~160 行），三个核心函数：

```
call_llm()     → 调用 DeepSeek API（OpenAI 兼容），返回 msg.content 或 msg.tool_calls
agent_loop()   → for 循环最多 10 轮：调 LLM → 有 tool_call 则执行 → 结果追加到 messages → continue
execute_tool() → if/elif 路由到具体工具实现
```

LLM 客户端是模块级全局单例（`client = OpenAI(...)`），整个文件共享。

## 技术栈

- Python 3.14，仅依赖 `openai` + `python-dotenv`
- DeepSeek API（`deepseek-chat`），OpenAI 兼容协议
- 工具定义：OpenAI Function Calling 格式的 dict 列表
- 配置文件：`.env`（gitignored），模板在 `.env.example`

## 开发原则

- 用户自己写代码，Claude 出题、给提示、帮忙 debug
- 每次只加一个小功能，跑通后再加下一个
- 代码保持单文件直到功能明显需要拆分
- 版本号格式：v0.0.1, v0.0.2, ... 每完成一个功能打 tag

## 当前版本

v0.0.1 — Agent 核心循环跑通，内置 `get_time` 和 `calc`（AST 安全求值）两个工具
