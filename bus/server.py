"""
消息总线 — FastAPI + WebSocket 服务。

参考 Hermes Studio 的 ChatRunSocket (index.ts)：
- HTTP API：RESTful 接口（会话列表、状态查询）
- WebSocket：实时双向通信（Agent 对话、流式输出）
- 多客户端共享同一 session（多端互通的基础）
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from core.agent import Agent, AgentEvent
from core.memory import Memory
from bus.protocol import Message, MessageType, MessageSource


app = FastAPI(title="Hermes Studio", version="0.1.0")

# ─── 核心组件（单例） ────────────────────────────

agent = Agent()
memory = Memory()

# 活跃的 WebSocket 连接: {session_id: [websocket, ...]}
# 一个 session 可以有多个客户端（多端互通）
connections: dict[str, list[WebSocket]] = {}


# ─── WebSocket 端点 — 实时对话 ────────────────────

@app.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    """
    WebSocket 对话端点 — 支持流式 AI 回复。

    客户端发送 JSON:
      {"type": "chat", "content": "...", "session_id": "..."}

    服务端流式推送 JSON:
      {"type": "stream", "content": "你"}  ← 逐 token
      {"type": "stream", "content": "好"}  ← 逐 token
      {"type": "tool_start", "tool_name": "read_file", ...}
      {"type": "tool_end", "tool_name": "read_file", "tool_result": "..."}
      {"type": "done", "content": "你好！..."}
    """
    await ws.accept()
    session_id: str | None = None

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg = Message.from_json(data)

            session_id = msg.session_id or f"sess_{uuid.uuid4().hex[:12]}"

            # 将客户端注册到 session 连接池
            if session_id not in connections:
                connections[session_id] = []
            if ws not in connections[session_id]:
                connections[session_id].append(ws)

            # 处理消息
            if msg.type == MessageType.CHAT:
                await ws.send_json({
                    "type": "run_started",
                    "session_id": session_id,
                })

                # Agent 主循环 — 流式推送
                try:
                    async for event in agent.run(msg.content, session_id):
                        await ws.send_json(_event_to_json(event, session_id))
                except Exception as e:
                    await ws.send_json({
                        "type": "error",
                        "session_id": session_id,
                        "content": f"Agent 执行失败: {e}",
                    })

            elif msg.type == MessageType.SYSTEM:
                # 心跳
                await ws.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket 错误] {e}")
    finally:
        if session_id and session_id in connections:
            connections[session_id].remove(ws)


def _event_to_json(event: AgentEvent, session_id: str) -> dict[str, Any]:
    """将 AgentEvent 转为 WebSocket JSON"""
    base = {
        "type": event.type,
        "session_id": session_id,
    }
    if event.type == "text":
        base["content"] = event.content
    elif event.type == "tool_start":
        base["tool_name"] = event.tool_name
        base["tool_args"] = event.tool_args
    elif event.type == "tool_end":
        base["tool_name"] = event.tool_name
        base["tool_result"] = event.tool_result
    elif event.type == "done":
        base["content"] = event.content
    elif event.type == "error":
        base["content"] = event.content
    return base


# ─── HTTP API ────────────────────────────────────

@app.get("/api/sessions")
async def list_sessions():
    """获取所有会话列表"""
    sessions = []
    for sid in memory.list_sessions():
        msgs = memory.load(sid)
        title = msgs[0]["content"][:80] if msgs else "(空)"
        sessions.append({"id": sid, "title": title, "messages": len(msgs)})
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取指定会话的完整历史"""
    msgs = memory.load(session_id)
    return {"session_id": session_id, "messages": msgs}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    memory.clear(session_id)
    return {"ok": True}


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "clients": sum(len(v) for v in connections.values())}


# ─── Web 前端（阶段 1: 简单的聊天页面）─────────────

@app.get("/")
async def web_client():
    """简易 Web 聊天界面 — 阶段 1 的 Web 适配器"""
    return HTMLResponse(WEB_HTML)


WEB_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hermes Studio</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: system-ui, sans-serif; background: #1a1a2e; color: #eee; height:100vh; display:flex; flex-direction:column; }
  #header { padding: 12px 20px; background: #16213e; border-bottom: 1px solid #0f3460; display:flex; gap:8px; }
  #header button { padding: 6px 14px; background: #0f3460; color: #eee; border: none; border-radius: 4px; cursor:pointer; }
  #header button:hover { background: #1a5276; }
  #chat { flex:1; overflow-y:auto; padding: 16px 20px; display:flex; flex-direction:column; gap:10px; }
  .msg { max-width: 80%; padding: 10px 14px; border-radius: 8px; line-height:1.5; white-space: pre-wrap; word-break: break-word; }
  .msg.user { align-self:flex-end; background:#0f3460; }
  .msg.assistant { align-self:flex-start; background:#16213e; }
  .msg.tool { align-self:flex-start; background:#1a1a2e; border:1px solid #333; font-size:0.85em; color:#aaa; }
  #input-area { padding: 12px 20px; background: #16213e; display:flex; gap:10px; }
  #input { flex:1; padding: 10px 14px; background: #1a1a2e; border:1px solid #333; border-radius: 6px; color:#eee; font-size:14px; resize:none; }
  #send { padding: 10px 20px; background: #e94560; color:#fff; border:none; border-radius: 6px; cursor:pointer; font-weight:bold; }
  #send:hover { background: #c23152; }
</style>
</head>
<body>
<div id="header">
  <button onclick="newSession()">+ 新会话</button>
  <span style="flex:1"></span>
  <span style="font-size:0.8em; color:#666; align-self:center;" id="sessionLabel"></span>
</div>
<div id="chat"></div>
<div id="input-area">
  <textarea id="input" rows="2" placeholder="输入消息，Enter 发送，Shift+Enter 换行..." onkeydown="onKey(event)"></textarea>
  <button id="send" onclick="send()">发送</button>
</div>
<script>
let sessionId = 'sess_' + Math.random().toString(36).slice(2,10);
let ws = new WebSocket('ws://' + location.host + '/ws');
let currentAssistantDiv = null;
document.getElementById('sessionLabel').textContent = sessionId.slice(0,16);

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  const chat = document.getElementById('chat');
  if (msg.type === 'text') {
    if (!currentAssistantDiv) {
      currentAssistantDiv = addMsg('assistant', '');
    }
    currentAssistantDiv.textContent += msg.content;
    chat.scrollTop = chat.scrollHeight;
  } else if (msg.type === 'tool_start') {
    addMsg('tool', '🔧 ' + msg.tool_name + ' ' + JSON.stringify(msg.tool_args));
  } else if (msg.type === 'tool_end') {
    const preview = msg.tool_result.slice(0, 200);
    addMsg('tool', '  → ' + preview + (msg.tool_result.length > 200 ? '...' : ''));
  } else if (msg.type === 'done') {
    currentAssistantDiv = null;
  } else if (msg.type === 'error') {
    addMsg('tool', '❌ ' + msg.content);
    currentAssistantDiv = null;
  }
};

function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.textContent = text;
  document.getElementById('chat').appendChild(div);
  return div;
}

function send() {
  const input = document.getElementById('input');
  const text = input.value.trim();
  if (!text) return;
  addMsg('user', text);
  ws.send(JSON.stringify({ type:'chat', content:text, session_id:sessionId }));
  input.value = '';
  currentAssistantDiv = null;
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
}

function newSession() {
  sessionId = 'sess_' + Math.random().toString(36).slice(2,10);
  document.getElementById('sessionLabel').textContent = sessionId.slice(0,16);
  document.getElementById('chat').innerHTML = '';
  currentAssistantDiv = null;
  addMsg('tool', '新会话: ' + sessionId);
}
</script>
</body>
</html>"""


def run_server(host: str = "0.0.0.0", port: int = 8648):
    """启动消息总线服务"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")
