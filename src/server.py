from agent import call_llm, agent_loop, execute_tool, TOOLS, client
from fastapi import FastAPI, WebSocket
import uvicorn
from fastapi.responses import HTMLResponse
import json


app = FastAPI()         # 创建 FastAPI 应用

@app.websocket("/ws")          # 定义一个 WebSocket 路由
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()        # 接受 WebSocket 连接
    while True:
        data = await websocket.receive_text()           # 接收文本消息
        msg = json.loads(data)   
        messages = [
            {"role": "system", "content": "你是编程助手，用中文回复，简洁。"},
            {"role": "user", "content": msg["content"]}
        ]
        reply = agent_loop(messages, TOOLS)
        await websocket.send_text(reply)




HTML_PAGE = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Camelia Studio</title></head>
<body>
<div id="chat"></div>
<input id="msg" type="text" placeholder="输入消息...">
<button onclick="send()">发送</button>
<script>
    const ws = new WebSocket("ws://" + location.host + "/ws");
    ws.onmessage = e => {
    const div = document.createElement("div");
    div.textContent = "AI: " + e.data;
    document.getElementById("chat").appendChild(div);
    };
    function send() {
    const input = document.getElementById("msg");
    ws.send(JSON.stringify({content: input.value}));
    const div = document.createElement("div");
    div.textContent = "你: " + input.value;
    document.getElementById("chat").appendChild(div);
    input.value = "";
    }
</script>
</body>
</html>"""

@app.get("/")
async def index():
    return HTMLResponse(HTML_PAGE)  # 需要 from fastapi.responses import HTMLResponse


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8648)



