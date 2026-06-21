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
    messages = [{"role": "system", "content": "你是编程助手..."}] 
    while True:
      data = await websocket.receive_text()
      msg = json.loads(data)
      messages.append({"role": "user", "content": msg["content"]})  # ← 追加，不是新建
      for event in agent_loop(messages, TOOLS):
          await websocket.send_text(json.dumps(event))
          if event["type"] == "text":
              messages.append({"role": "assistant", "content": event["content"]})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8648)
