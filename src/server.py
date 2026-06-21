from agent import agent_loop, TOOLS
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from pathlib import Path
import uvicorn
import json


app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    messages = [{"role": "system", "content": "你是编程助手，用中文回复，简洁。"}]
    while True:
        data = await websocket.receive_text()
        msg = json.loads(data)
        messages.append({"role": "user", "content": msg["content"]})
        try:
            for event in agent_loop(messages, TOOLS):
                await websocket.send_text(json.dumps(event))
                if event["type"] == "text":
                    messages.append({"role": "assistant", "content": event["content"]})
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "error", "content": f"出错了: {e}"}))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8648)
