"""
Camelia Studio — Web 服务 & 会话管理
=====================================
FastAPI 服务：静态文件 + HTTP API + WebSocket 聊天。
会话持久化到 ~/.camelia-studio/sessions/ (JSON 文件)。
"""

from agent import agent_loop, TOOLS, _get_client
from memory import add_session, search as search_memory, format_memories, memory_count
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from pathlib import Path
import uvicorn
import json
import traceback
import uuid
import os
import asyncio
from datetime import datetime

SYSTEM_PROMPT = "你是编程助手，用中文回复，简洁。"


app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"
SESSIONS_DIR = Path.home() / ".camelia-studio" / "sessions"
SESSION_MAX_DAYS = 30  # 会话保留天数


# ─── 会话存储 ──────────────────────────────────

def cleanup_old_sessions() -> int:
    """删除超过 SESSION_MAX_DAYS 天的旧会话，返回删除数量。"""
    if not SESSIONS_DIR.exists():
        return 0
    now = datetime.now().timestamp()
    cutoff = now - SESSION_MAX_DAYS * 86400
    deleted = 0
    for f in SESSIONS_DIR.glob("*.json"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
    return deleted

def create_session() -> str:
    return "sess_" + uuid.uuid4().hex[:12]

def _read_session_file(session_id: str) -> dict | None:
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

def save_session(session_id: str, messages: list[dict]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    existing = _read_session_file(session_id)
    starred = existing.get("starred", False) if existing else False
    title = ""
    for m in messages:
        if m["role"] == "user":
            title = m["content"][:50]
            break
    data = {"id": session_id, "title": title, "starred": starred, "messages": messages}
    (SESSIONS_DIR / f"{session_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

async def generate_title(messages: list[dict]) -> str:
    """用 LLM 根据对话内容生成简短标题（≤15字）。"""
    # 收集前几轮用户和助手消息
    sample = []
    for m in messages:
        if m["role"] in ("user", "assistant"):
            sample.append(m["content"])
            if len(sample) >= 4:
                break
    if not sample:
        return ""

    prompt = (
        "根据以下对话生成一个简短标题（不超过15个汉字），直接返回标题原文，不加任何前缀或标点：\n\n"
        + "\n---\n".join(sample[:4])
    )

    try:
        client = _get_client()
        # 在线程池中运行同步 API 调用
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "deepseek-chat"),
                messages=[
                    {"role": "system", "content": "你是标题生成器，只返回简短标题本身。"},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=30,
                temperature=0.3,
            ),
        )
        title = resp.choices[0].message.content.strip()
        # 清理：去掉引号、多余标点
        for ch in '"\'「」『』《》\n':
            title = title.replace(ch, "")
        return title[:30]
    except Exception:
        return ""


def update_session_title(session_id: str, title: str) -> None:
    """更新会话 JSON 文件中的标题字段。"""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("title", "").strip() == title.strip():
        return
    data["title"] = title
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
        result.append({
            "id": data["id"],
            "title": data.get("title", ""),
            "count": len(data.get("messages", [])),
            "starred": data.get("starred", False),
        })
    # 星标置顶
    result.sort(key=lambda s: (not s["starred"], s["id"]), reverse=False)
    # 未星标的按原始顺序 (mtime desc)，星标的在顶部
    starred = [s for s in result if s["starred"]]
    unstarred = [s for s in result if not s["starred"]]
    return starred + unstarred

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

@app.get("/api/health")
async def api_health():
    return {"status": "ok"}

@app.get("/api/config")
async def api_config():
    import os
    return {
        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
        "base_url": os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
    }

@app.post("/api/sessions/{session_id}/star")
async def api_toggle_star(session_id: str):
    data = _read_session_file(session_id)
    if not data:
        return {"ok": False, "error": "会话不存在"}
    data["starred"] = not data.get("starred", False)
    (SESSIONS_DIR / f"{session_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"ok": True, "starred": data["starred"]}

@app.get("/api/memory/search")
async def api_memory_search(q: str = "", n: int = 5):
    """语义搜索记忆库。"""
    if not q.strip():
        return {"memories": []}
    try:
        mems = search_memory(q.strip(), n=n)
        return {"memories": mems}
    except Exception as e:
        return {"memories": [], "error": str(e)}

@app.get("/api/memory/stats")
async def api_memory_stats():
    """记忆库统计。"""
    try:
        return {"count": memory_count()}
    except Exception:
        return {"count": 0}


# ─── WebSocket ─────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id: str | None = None
    messages: list[dict] = []
    memory_injected = False  # 当前会话是否已注入记忆

    while True:
        data = await websocket.receive_text()
        msg = json.loads(data)

        # ── 重连：仅加载历史，不发消息 ──
        if msg.get("type") == "reconnect":
            if msg.get("session_id"):
                session_id = msg["session_id"]
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                history = [m for m in load_session(session_id) if m["role"] != "system"]
                messages.extend(history)
                memory_injected = False  # 重连后重新注入
            await websocket.send_text(json.dumps({"type": "reconnected", "session_id": session_id}))
            continue

        # 切换或创建会话
        if msg.get("session_id") and msg["session_id"] != session_id:
            session_id = msg["session_id"]
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            history = [m for m in load_session(session_id) if m["role"] != "system"]
            messages.extend(history)
            memory_injected = False  # 切换会话后重新注入

        if not session_id:
            session_id = create_session()
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            memory_injected = False
            await websocket.send_text(json.dumps({"type": "session_created", "session_id": session_id}))

        # 空内容忽略（不发消息不调 LLM）
        content = msg.get("content", "").strip()
        if not content:
            continue

        # ── 首次对话时注入记忆上下文 ──
        if not memory_injected:
            try:
                mems = search_memory(content)
                if mems:
                    ctx = format_memories(mems)
                    messages[0]["content"] = SYSTEM_PROMPT + "\n\n" + ctx
                    await websocket.send_text(json.dumps({
                        "type": "memory_found",
                        "count": len(mems),
                    }))
            except Exception:
                pass  # 记忆检索失败不阻塞聊天
            memory_injected = True

        messages.append({"role": "user", "content": content})

        try:
            async for event in agent_loop(messages, TOOLS):
                await websocket.send_text(json.dumps(event))
                if event["type"] == "text":
                    messages.append({"role": "assistant", "content": event["content"]})
        except Exception as e:
            traceback.print_exc()
            await websocket.send_text(json.dumps({"type": "error", "content": "处理请求时出错，请查看服务端日志"}))

        # ── 保存会话 ──
        # 保存前把 system prompt 恢复为原始（不保存注入的记忆上下文）
        orig_system = messages[0]["content"]
        messages[0]["content"] = SYSTEM_PROMPT
        save_session(session_id, messages)

        # 存入记忆库（后台）
        try:
            add_session(session_id, messages)
        except Exception:
            pass

        messages[0]["content"] = orig_system  # 恢复内存中的 system prompt
        await websocket.send_text(json.dumps({"type": "session_saved", "session_id": session_id}))

        # 后台用 LLM 生成更好的会话标题
        async def _auto_title():
            try:
                title = await generate_title(messages)
                if title:
                    update_session_title(session_id, title)
                    await websocket.send_text(json.dumps({
                        "type": "session_renamed",
                        "session_id": session_id,
                        "title": title,
                    }))
            except Exception:
                pass
        asyncio.create_task(_auto_title())


# ─── 静态文件 ──────────────────────────────────

from fastapi.staticfiles import StaticFiles

@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    })

# 其他静态文件 (CSS, JS, 图标 等)
app.mount("/", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import signal, sys as _sys
    _sys.stdout.flush()
    n = cleanup_old_sessions()
    if n:
        print(f"🧹 已清理 {n} 个超过 {SESSION_MAX_DAYS} 天的旧会话")

    # 自动打开浏览器
    import webbrowser, threading
    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8648")).start()

    uvicorn.run(app, host="127.0.0.1", port=8648)
