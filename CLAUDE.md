# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

Camelia Studio — 受 Hermes Studio 启发的自建 AI Agent。山茶花 = 理想·谦逊·坚韧。
**用户是大二嵌入式学生，代码自己写，Claude 出题给提示不代写。**

## 运行方式

```bash
# ── Electron 桌面应用（推荐）──
cd electron && npm install          # 首次：安装 Node 依赖
./run-electron.sh                   # 开发模式启动

# ── 纯 Python 模式 ──
pip install -r requirements.txt     # 安装全部后端依赖
python src/server.py                # Web 服务 (http://localhost:8648)
python src/agent.py                 # CLI 终端模式

# ── 打包发布 ──
cd electron && npm run build        # 构建当前平台
cd electron && npm run build:linux  # 仅 Linux (AppImage + deb)
cd electron && npm run build:win    # 仅 Windows (NSIS)
cd electron && npm run build:mac    # 仅 macOS (DMG)
```

## 配置

**Electron 桌面模式（推荐）：**
API Key 和提供商通过设置界面管理（Electron 菜单 → 设置），加密存储于 `electron-store`。
支持多提供商：DeepSeek / 通义千问 / 自定义代理。首次启动无配置时自动进入设置引导页。

**纯 Python 模式（开发/CLI）：**
```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```
`.env` 由 `agent.py` 自动查找（`Path(__file__).parent.parent / ".env"`），
`OPENAI_BASE_URL` 默认 `https://api.deepseek.com/v1`，`LLM_MODEL` 默认 `deepseek-chat`。
端口硬编码 `8648`。Electron 模式下这三个变量由 main.js spawn 时注入。

## 架构

```
src/agent.py   Agent 引擎 — 单文件自包含
  ├── call_llm()        非流式调用 — 返回完整 message（检测 tool_call）
  ├── stream_llm()      真流式调用 — 存在但未使用，agent_loop 自己模拟流式
  ├── agent_loop()      async generator，最多 10 轮工具调用循环
  │                      流式阶段不是真流式：拿到 msg.content 后 chunk_size=3 切块
  │                      逐块 yield + asyncio.sleep(0.02)，免额外 API 调用
  ├── execute_tool()    8 个工具的 if/elif 路由
  └── TOOLS             8 个工具 (OpenAI Function Calling 格式):
                         get_time / calc / read_file / write_file / list_dir / run_command
                         list_serial_ports / read_serial (嵌入式调试)

src/server.py  Web 服务 — FastAPI, 由 agent.py 导入 agent_loop
  ├── HTTP API          GET/DELETE /api/sessions, POST /api/sessions/{id}/star
  │                     GET /api/health, GET /api/config
  ├── WebSocket /ws     收发 JSON 事件流: session_created / reconnected → tool_start
  │                     → tool_end → stream → text → session_saved → session_renamed
  │                     会话存储: ~/.camelia-studio/sessions/{id}.json
  │                     启动时清理 >30 天旧会话，自动打开浏览器
  ├── save_session()    每次 agent_loop 结束后自动保存，首条 user 消息作临时标题
  ├── generate_title()  后台 LLM 调用生成会话标题（≤15字），asyncio.create_task 不阻塞
  └── update_session_title()  更新 JSON 文件中标题字段

src/static/index.html   单文件聊天界面 — 山茶花深色主题
  ├── 模型切换器        header 下拉框，列出有 API Key 的提供商的所有模型
  │                     空闲时切换 → kill → spawn → WebSocket 重连（不刷新页面）
  │                     生成中切换 → 仅保存到 store → 回复完成后自动生效
  ├── 消息队列          send() 生成中将消息入队 → finishGeneration() 自动出队发送
  ├── 自动恢复          启动时自动打开最近一次对话，侧边栏粉红左边条标识当前会话
  ├── WebSocket 客户端  createWebSocket() 可重建，重连时发 reconnect 消息恢复历史
  ├── 流式渲染策略      stream 事件 → textContent 逐字追加（避免不完整 Markdown 被渲染）
  │                     text 事件  → renderMarkdown() 替换为完整 HTML（此时 Markdown 完整）
  ├── Markdown          仅处理 ```代码块 + `行内代码，escapeHtml 后正则替换
  ├── 会话管理          侧边栏列表 + 星标置顶 + 删除，DOM API + textContent 防 XSS
  │                     删除当前会话自动切换到最近一条
  ├── 健康检查          每 30s GET /api/health，header 圆点变色指示连接状态
  └── 响应式            移动端侧边栏滑入/遮罩层，max-width: 700px 断点

electron/               Electron 桌面壳
  ├── main.js           启动流程: 检查 electron-store 是否有活跃且 Key 完整的提供商
  │                       有 → spawn Python (注入 api_key/base_url/model) → loadURL 聊天页
  │                       无 → loadFile(settings.html) 首次引导
  │                     IPC handlers: get/add/update/delete providers,
  │                     set-active (存+重启), save-active (仅存), restart-backend
  │                     test-connection (GET /models → POST /chat/completions 容错)
  │                     get-backend-status, launch-backend
  │                     加密 key 由 SHA256(hostname+username+userData) 确定性派生
  ├── preload.js        contextBridge 暴露两个对象:
  │                     window.camelia (platform, version)
  │                     window.settings (getProviders, addProvider, setActive, saveActive,
  │                       restartBackend, testConnection, getBackendStatus, launchBackend)
  ├── settings.html     提供商管理界面 — 增/删/改 提供商和模型列表
  │                     左侧快捷配置: Ollama 本地模型 / DeepSeek / 通义千问 一键填入
  │                     通过 Electron 菜单 "设置" 进入，"← 返回聊天" 回到聊天界面
  │                     含"测试连接"功能: 调 /models → 失败回退 /chat/completions 验证
  ├── package.json      electron-builder 配置: 输出到 ../dist，
  │                     publish → GitHub Release (Eliauk-Camelia/camelia-studio)
  │                     自动更新: electron-updater，仅生产环境启用
  └── auto-update       启动 5s 后调用 checkForUpdatesAndNotify()
                        四个生命周期: checking / available / not-available / downloaded
```

## 数据流

```
浏览器/Electron → WebSocket → server.py → async for agent_loop → call_llm → DeepSeek
      ↑              ↑                           ↑                                  ↓
  WebSocket        HTTP API              agent_loop yield                  execute_tool()
  (实时推送)    (会话 CRUD)            (stream/tool/text)           (8 个工具 → 结果字符串)
                                              ↓
                                        save_session()
                                       (自动保存到JSON)
```

## agent.py 关键实现细节

### tool_call 时的 messages 顺序

LLM 返回 tool_calls 后，向 `messages` 插入两样东西：
1. **assistant 消息**（含 tool_calls 声明）→ `messages.insert(-len(tool_calls), ...)`
   插入到工具结果之前，保持 assistant → tool 的正确顺序
2. **tool 消息**（每个工具一条）→ `messages.append(...)`

### 路径安全沙箱

`_check_path()` 白名单：`Path.home()`, `/home/arch/Desktop`, `/tmp`
先用 `expanduser().resolve()` 防 `../` 逃逸，再检查是否在白名单前缀内。

### calc 工具安全

使用 Python `ast` 模块解析表达式，仅允许 `BinOp` (+-*/), `Constant`, `UnaryOp`(-) 节点。
拒绝任意代码执行。

## 技术栈

- Python 3.14: FastAPI + uvicorn + openai + python-dotenv + pyserial
- Node.js: Electron 35 + electron-builder 26 + electron-updater + electron-store 8
- LLM: 多提供商支持（DeepSeek / 通义千问 / Ollama 本地 / 自定义 OpenAI 兼容 API）
- 存储: JSON 文件 (`~/.camelia-studio/sessions/`), electron-store 加密存储 (`config.json`)

## 项目状态

当前 dev/v0.0.5（开发中）。分支策略：`main` 是稳定标签线，`dev/v0.0.X` 是功能累积线。

### 三大支柱（详见 ROADMAP.md）

1. **IDE 壳** — Monaco Editor + xterm.js + 文件树，对标 VS Code 布局
2. **嵌入式工具链**
   - 一键烧录 — OpenOCD / DSLite 封装
   - AI 调参闭环 — 读取传感器→分析响应→计算参数→写回设备（PID/滤波器/标定）
3. **持久化记忆** — ChromaDB 向量存储 + RAG 语义检索

### 版本规划

| 版本 | 目标 | 状态 |
|---|---|---|
| v0.0.1~v0.0.4 | 核心引擎 + Web 界面 + 文件工具 + 串口 | ✅ |
| v0.0.5 | 多提供商 + Electron 桌面壳 | ✅ 当前 |
| v0.0.6 | 记忆持久化 (ChromaDB + RAG) | ⬅ 下一步 |
| v0.0.7 | Monaco Editor + 文件树 | |
| v0.0.8 | xterm.js 终端面板 | |
| v0.0.9 | 烧录工具 (OpenOCD / DSLite) | |
| v0.0.10 | AI 调参闭环 (write_serial + 阶跃分析 + PID) | |
| v0.1.0 | 三面板 IDE 整合 + 可扩展插件系统 | |

注意：`requirements.txt` 已含全部后端依赖（openai + python-dotenv + fastapi + uvicorn）。
串口工具需 `pyserial`（系统已安装）。

## 安全边界

- 本地单用户 (127.0.0.1 + contextIsolation + nodeIntegration: false)，不暴露公网
- API Key 加密存储于 electron-store，加密密钥由 SHA256(机器指纹) 确定性派生，每台机器唯一
- Electron spawn 只注入 5 个白名单 env（OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, PATH, HOME）
- 文件操作 `_check_path()` 限制在 ~/、~/Desktop、/tmp
- `run_command` shell=True 是设计决策（需管道/重定向），本地工具不加固
- 前端防 XSS: textContent + DOM API（无 innerHTML）+ renderMarkdown 先 escapeHtml 后正则替换
