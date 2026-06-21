from agent import agent_loop, TOOLS
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from pathlib import Path
import uvicorn
import json
import traceback
import uuid


app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"
SESSIONS_DIR = Path.home() / ".camelia-studio" / "sessions"


# ─── 会话存储 ──────────────────────────────────

def create_session() -> str:
    return "sess_" + uuid.uuid4().hex[:12]

def save_session(session_id: str, messages: list[dict]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    title = ""
    for m in messages:
        if m["role"] == "user":
            title = m["content"][:50]
            break
    data = {"id": session_id, "title": title, "messages": messages}
    (SESSIONS_DIR / f"{session_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

def load_session(session_id: str) -> list[dict]:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("messages", [])

def list_sessions() -> list[dict]:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = json.loads(f.read_text(encoding="utf-8"))
        result.append({"id": data["id"], "title": data.get("title", ""), "count": len(data.get("messages", []))})
    return result

def delete_session(session_id: str) -> None:
    path = SESSIONS_DIR / f"{session_id}.json"
    if path.exists():
        path.unlink()


# ─── HTTP API ──────────────────────────────────

@app.get("/api/sessions")
async def api_list_sessions():
    return {"sessions": list_sessions()}

@app.get("/api/sessions/{session_id}")
async def api_load_session(session_id: str):
    return {"session_id": session_id, "messages": load_session(session_id)}

@app.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: str):
    delete_session(session_id)
    return {"ok": True}


# ─── WebSocket ─────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id: str | None = None
    messages: list[dict] = []

    while True:
        data = await websocket.receive_text()
        msg = json.loads(data)

        # 切换或创建会话
        if msg.get("session_id") and msg["session_id"] != session_id:
            session_id = msg["session_id"]
            messages = [{"role": "system", "content": "你是编程助手，用中文回复，简洁。"}]
            history = load_session(session_id)
            messages.extend(history)

        if not session_id:
            session_id = create_session()
            messages = [{"role": "system", "content": "你是编程助手，用中文回复，简洁。"}]
            await websocket.send_text(json.dumps({"type": "session_created", "session_id": session_id}))

        messages.append({"role": "user", "content": msg["content"]})

        try:
            for event in agent_loop(messages, TOOLS):
                await websocket.send_text(json.dumps(event))
                if event["type"] == "text":
                    messages.append({"role": "assistant", "content": event["content"]})
        except Exception as e:
            traceback.print_exc()
            await websocket.send_text(json.dumps({"type": "error", "content": "处理请求时出错，请查看服务端日志"}))

        save_session(session_id, messages)
        await websocket.send_text(json.dumps({"type": "session_saved", "session_id": session_id}))


# ─── 静态文件 ──────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8648)
