"""
Camelia Studio — AI Agent 引擎
================================
Agent 核心：LLM 调用 + Tool Calling 循环 + 工具执行器。
被 server.py (WebSocket) 和 CLI 模式 (__main__) 共用。

架构：
    call_llm()     → 给 DeepSeek 发 HTTP 请求，拿回回复
    agent_loop()   → yield 生成器：调 LLM → 执行工具 → 循环
    execute_tool() → if/elif 路由到具体工具实现
"""

import os
import json
import ast
import asyncio
import operator
import subprocess
from pathlib import Path
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv

# ─── 启动：加载配置 ────────────────────────────

_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    load_dotenv(_env)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
)

SYSTEM_PROMPT = "你是编程助手，用中文回复，简洁。"


# ══════════════════════════════════════════════════
#  LLM 调用层
# ══════════════════════════════════════════════════

def call_llm(messages: list[dict], tools: list[dict] | None = None):
    """调用 DeepSeek API (OpenAI 兼容)，返回 message 对象。

    message.content   → 文本回复 (可能为 None)
    message.tool_calls → 工具调用请求列表 (可能为 None)
    """
    kwargs = {"model": "deepseek-chat", "messages": messages}
    if tools:
        kwargs["tools"] = tools
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message


def stream_llm(messages: list[dict], tools: list[dict] | None = None):
    """流式调用 LLM — yield 逐 token 文本增量。

    和 call_llm 的区别：不返回完整 message，而是一个字一个字 yield。
    用于流式输出到前端。
    """
    kwargs = {"model": "deepseek-chat", "messages": messages, "stream": True}
    if tools:
        kwargs["tools"] = tools
    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


# ══════════════════════════════════════════════════
#  Agent 循环
# ══════════════════════════════════════════════════

async def agent_loop(messages: list[dict], tools: list[dict]):
    """Agent 主循环 — yield 生成器，逐步推送事件。

    流程：
        1. 调 LLM (非流式)
        2. 如果有 tool_call → 执行工具 → 追加结果 → 回到 1
        3. 如果没有 tool_call → 流式输出文本 → 结束

    yield 事件格式：
        {"type": "tool_start",  "name": str}
        {"type": "tool_end",    "name": str, "result": str}
        {"type": "stream",      "content": str}       ← 逐 token 增量
        {"type": "text",        "content": str}       ← 完整文本（兼容旧前端）
    """
    for _ in range(10):
        msg = call_llm(messages, tools)

        # ── 有工具调用：执行 → 追加到对话 → 继续 ──
        if msg.tool_calls:
            tool_call_entries = []
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                yield {"type": "tool_start", "name": name}

                result = execute_tool(name, args)

                yield {"type": "tool_end", "name": name, "result": result}

                # 收集 assistant 的工具调用声明（稍后统一插入 messages）
                tool_call_entries.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                })
                # 工具结果直接追加
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

            # assistant 声明插在工具结果之前
            messages.insert(
                -len(msg.tool_calls),
                {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": tool_call_entries,
                },
            )
            continue  # 回到循环开头，LLM 看到工具结果后继续

        # ── 纯文本回复：流式输出 → 结束 ──
        if msg.content:
            # 逐词 yield，模拟流式（免额外 API 调用的零成本方案）
            text = msg.content
            chunk_size = 3
            for i in range(0, len(text), chunk_size):
                yield {"type": "stream", "content": text[i:i+chunk_size]}
                await asyncio.sleep(0.02)  # 微延时，让前端有时间渲染
            yield {"type": "text", "content": text}
            return

        # 既无文本也无工具调用，结束
        return


# ══════════════════════════════════════════════════
#  工具定义 (OpenAI Function Calling 格式)
# ══════════════════════════════════════════════════

TOOLS = [
    # ── get_time：获取当前时间 ──
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前日期和时间",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    # ── calc：安全数学计算（AST 解析，禁止任意代码执行） ──
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "计算数学表达式，支持 + - * / ** 和括号",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '3*4+2' 或 '2**10'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    # ── read_file：读取文件内容 ──
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文本文件内容，用于查看代码、配置、日志等",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径（绝对或相对）"}
                },
                "required": ["path"],
            },
        },
    },
    # ── write_file：写入文件 ──
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "创建或覆盖文件，自动创建父目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    # ── list_dir：列出目录内容 ──
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出目录中的文件和子目录，目录优先排序",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "目录路径，默认当前目录"}
                },
                "required": [],
            },
        },
    },
    # ── run_command：执行 shell 命令 ──
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在终端执行 shell 命令，用于编译、git、运行脚本等。支持管道和重定向。",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"}
                },
                "required": ["command"],
            },
        },
    },
]


# ══════════════════════════════════════════════════
#  工具执行器
# ══════════════════════════════════════════════════

# 文件系统安全：仅允许操作以下目录
_SAFE_ROOTS = [str(Path.home()), "/home/arch/Desktop", "/tmp"]


def _check_path(path_str: str) -> Path | str:
    """路径安全校验：resolve() 防 ../ 逃逸，白名单防越权访问。"""
    p = Path(path_str).expanduser().resolve()
    if any(str(p).startswith(r + os.sep) or str(p) == r for r in _SAFE_ROOTS):
        return p
    return f"安全限制: 禁止访问 {path_str}"


def execute_tool(name: str, args: dict) -> str:
    """根据工具名路由到具体实现，返回执行结果字符串。"""

    # ── get_time ──
    if name == "get_time":
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── calc (AST 安全求值，拒绝任意代码) ──
    elif name == "calc":
        _OPS = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.Pow: operator.pow, ast.USub: operator.neg,
        }

        def _eval(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp):
                return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                return -_eval(node.operand)
            raise ValueError("不支持的操作")

        try:
            tree = ast.parse(args["expression"], mode="eval")
            return str(_eval(tree.body))
        except Exception as e:
            return f"计算出错: {e}"

    # ── read_file ──
    elif name == "read_file":
        p = _check_path(args["path"])
        if isinstance(p, str):
            return p
        if not p.exists():
            return f"文件不存在: {args['path']}"
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 8000:
            content = content[:8000] + f"\n... (截断，共 {len(content)} 字符)"
        return content

    # ── write_file ──
    elif name == "write_file":
        p = _check_path(args["path"])
        if isinstance(p, str):
            return p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(args["content"], encoding="utf-8")
        return f"已写入: {p} ({len(args['content'])} 字符)"

    # ── list_dir ──
    elif name == "list_dir":
        p = _check_path(args.get("path", "."))
        if isinstance(p, str):
            return p
        if not p.exists() or not p.is_dir():
            return f"目录不存在: {p}"
        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = []
        for item in items[:100]:
            suffix = "/" if item.is_dir() else ""
            size = item.stat().st_size
            lines.append(f"  {item.name}{suffix}  ({size:,} bytes)")
        result = "\n".join(lines)
        if len(items) > 100:
            result += f"\n... (共 {len(items)} 项，仅显示前 100)"
        return result or "(空目录)"

    # ── run_command ──
    elif name == "run_command":
        try:
            proc = subprocess.run(
                args["command"], shell=True, capture_output=True,
                text=True, timeout=30,
            )
            output = proc.stdout.strip() or proc.stderr.strip()
            if len(output) > 4000:
                output = output[:4000] + "\n... (截断)"
            return output or "(命令无输出)"
        except subprocess.TimeoutExpired:
            return "命令执行超时 (30s)"
        except Exception as e:
            return f"命令执行失败: {e}"

    return f"未知工具: {name}"


# ══════════════════════════════════════════════════
#  CLI 模式 (python agent.py)
# ══════════════════════════════════════════════════

async def cli_main():
    """CLI 模式入口"""
    msg = call_llm([{"role": "user", "content": "hello"}])
    print(f"测试结果: {msg.content}")

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break
        if not user_input:
            continue
        if user_input in ("/q", "/quit"):
            break

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ]
        async for event in agent_loop(messages, TOOLS):
            if event["type"] == "tool_start":
                print(f"\n🔧 正在调用 {event['name']}...")
            elif event["type"] == "tool_end":
                print(f"✅ {event['name']} 完成")
            elif event["type"] == "stream":
                print(event["content"], end="", flush=True)
            elif event["type"] == "text":
                print()

if __name__ == "__main__":
    asyncio.run(cli_main())
