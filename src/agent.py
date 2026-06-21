"""
AI Agent 骨架 — 你来把它变活。

运行方式：
    source ../.env && python agent.py

你要完成的 3 个函数在下面，每个 <10 行。
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# 自动加载 .env（不再需要手动 source）
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    load_dotenv(_env)

# 全局 LLM 客户端 — 整个文件共享这一个实例
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
)

# ============================================================
# TODO 1: 完成 call_llm()
# ============================================================
# 任务：调用 DeepSeek API，发送消息，返回回复
#
# 提示：
#   - 用 client.chat.completions.create()
#   - model="deepseek-chat"
#   - 参数: messages, tools (如果传了 tools)
#   - tools 参数格式: tools=[{"type":"function", "function":{...}}, ...]
#   - 返回 response.choices[0].message
#
# 写到下面这里 ↓
def call_llm(messages, tools=None):
    kwargs = {"model": "deepseek-chat", "messages": messages}          
    if tools:
        kwargs["tools"] = tools
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message

# ============================================================
# TODO 2: 完成 agent_loop()
# ============================================================
# 任务：实现 Agent 的 while 循环
#
# 逻辑（伪代码）：
#   for _ in range(10):
#       msg = call_llm(messages, tools)
#       if msg.tool_calls:
#           for tc in msg.tool_calls:
#               result = execute_tool(tc.function.name, json.loads(tc.function.arguments))
#               print(f"[工具 {tc.function.name}]: {result}")
#               messages.append(...)   # 把工具结果加回去
#           continue  # 继续循环
#       else:
#           return msg.content
#
# 提示：
#   - 工具调用后要往 messages 里加两条：
#     1. assistant 消息（含 tool_calls）
#     2. tool 消息（含 tool_call_id + 结果）
#   - OpenAI tool call 的消息格式：
#     {"role":"assistant", "content":None, "tool_calls":[{"id":tc.id, "type":"function", "function":{...}}]}
#     {"role":"tool", "tool_call_id":tc.id, "content":result}
#
# 写到下面这里 ↓

def agent_loop(messages, tools):
    for _ in range(10):
        msg = call_llm(messages, tools)
        if msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                yield {"type":"tool_start","name":name}
                result = execute_tool(name, args)               # 执行工具
                yield {"type": "tool_end", "name": name, "result": result}
                 # 消息 1
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}
                    }]
                })
                # 消息 2
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })   # 把工具结果加回去
            continue  # 继续循环
        else:
            yield {"type": "text", "content": msg.content}   # ← 最后才吐文字
            return
# ============================================================
# 以下是测试代码，你不需要改
# ============================================================

# 两个简单工具
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前时间",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calc",
            "description": "计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如 '3*4+2'"}
                },
                "required": ["expression"],
            },
        }
    },
]


def execute_tool(name, args):           # 执行工具
    if name == "get_time":              # 获取当前时间
        from datetime import datetime  
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")     # 返回当前时间
    elif name == "calc":
        import ast, operator
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
    return f"未知工具: {name}"


# --- 主程序 ---
SYSTEM = "你是编程助手，用中文回复，简洁。"

if __name__ == "__main__":
    # 快速测试 call_llm
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
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_input},
        ]
        for event in agent_loop(messages, TOOLS):
            if event["type"] == "tool_start":
                print(f"\n🔧 正在调用 {event['name']}...")
            elif event["type"] == "tool_end":
                print(f"✅ {event['name']} 完成")
            elif event["type"] == "text":
                print(f"AI: {event['content']}")
