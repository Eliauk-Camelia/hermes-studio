# Camelia Studio — 路线图

## 三层愿景

```
                     Camelia Studio
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    VS Code-like      Embedded          Persistent
     IDE 壳          一键烧录           记忆系统
```

### 第一层：IDE 壳 — 不只是聊天框

从单页面聊天升级为三面板 IDE：

```
┌─ 文件树 ───┬─ 编辑器区 ────┬─ AI 面板 ─┐
│            │               │           │
│ src/       │ tab: main.c   │  Camelia  │
│  main.c    │               │  Chat     │
│  Makefile  │               │           │
│            │               │           │
├────────────┴───────────────┤           │
│  终端 (xterm.js)           │           │
│  $ make flash              │           │
└────────────────────────────┴───────────┘
```

关键技术：
- **Monaco Editor** — VS Code 同款编辑器组件，MIT 协议，语法高亮 + 智能提示自带
- **xterm.js** — 终端模拟器，`@xterm/xterm` + `node-pty`
- **文件树** — Electron `dialog` + `fs` API

### 第二层：嵌入式工具链

#### 2a. 一键烧录 & 调试

基于现有 CLI 封装嵌入式工具链：

```python
TOOLS += [
    "flash_mspm0",    # 调用 MSPM0 CLI / OpenOCD 烧录固件
    "flash_stm32",    # 调用 STM32CubeProgrammer CLI / st-flash
    "build_project",  # make / cmake --build
    "debug_probe",    # OpenOCD + GDB 连接状态检查
]
```

本质是对现有 CLI 的参数模板化，核心是搞清楚各平台的命令行参数。

#### 2b. AI 调参闭环

让 Agent 像人类工程师一样"观察 → 分析 → 调整 → 再观察"：

```
        serial.read()  传感器原始数据
              │
              ▼
        ┌─ AI 分析 ─────────────────────┐
        │  超调量 σ%、稳态误差 ess      │
        │  上升时间 tr、振荡次数        │
        │  → 判定：欠阻尼/过阻尼/临界   │
        └───────────────┬───────────────┘
              │
              ▼
        ┌─ 参数计算 ────────────────────┐
        │  Kp += ΔKp, Ki += ΔKi, Kd += ΔKd │
        │  或启发式规则（Z-N 法等）        │
        └───────────────┬───────────────┘
              │
              ▼
        serial.write(新参数)
              │
              ▼
        (回到第一步，循环直到指标达标)
```

关键技术：
- `write_serial` 工具 — 当前只有 `read_serial`，双向通信是前提
- `analyze_step_response` — 解析阶跃响应，提取时域指标（超调量、稳态误差、上升时间）
- `tune_pid` — PID 参数自整定策略：Ziegler-Nichols / 内模控制 / 迭代学习
- 协议适配层 — 定义传感器数据格式和参数下发协议，对 Agent 透明

```python
# 调参工具示例
TOOLS += [
    "write_serial",          # 向设备下发命令/参数（双向通信基础）
    "analyze_step_response", # 输入波形数据，输出时域指标
    "tune_pid",              # 输入目标指标，输出 pid 参数建议
]
```

> 不止 PID：滤波器系数、PWM 占空比、传感器标定偏移等都可以走同样的闭环调参模式。
> 关键是协议层做好抽象，让 Agent 理解"调整什么参数、看什么指标"。

### 第三层：持久化记忆

RAG over conversation history，让 Agent 记住"上次那个 LED 闪烁代码"：

```
用户提到"上次的 LED 代码"
    │
    ▼
语义搜索 ──→ 找到之前 LED 相关对话
    │
    ▼
注入 System Prompt ──→ LLM 获得上下文
```

技术栈：
- **嵌入模型** — `all-MiniLM-L6-v2`（本地 CPU 可用）或 DeepSeek Embedding API
- **向量存储** — ChromaDB（Python 原生，零配置）或 LanceDB（更快）
- **检索逻辑** — 每次新对话开始，检索最近 N 条相关记忆拼入 system prompt

---

## 分阶段路线

| 版本 | 目标 | 关键技术 | 状态 |
|---|---|---|---|
| v0.0.1 | Agent 核心循环 | Tool Calling 引擎 | ✅ |
| v0.0.2 | Web 聊天界面 | FastAPI + WebSocket + 流式输出 | ✅ |
| v0.0.3 | 文件系统工具 | 读写文件、执行命令、路径沙箱 | ✅ |
| v0.0.4 | 硬件控制 | MSPM0/STM32 串口通信 | ✅ |
| v0.0.5 | 多提供商 + 桌面壳 | Electron + 加密存储 + 模型切换 | ✅ 当前 |
| v0.0.6 | 记忆持久化基础 | ChromaDB 嵌入 + RAG 检索 | ⬅ 下一步 |
| v0.0.7 | 编辑器面板 | Monaco Editor + 文件树 | |
| v0.0.8 | 终端面板 | xterm.js + node-pty | |
| v0.0.9 | 烧录工具 | OpenOCD / DSLite 封装 | |
| v0.0.10 | AI 调参闭环 | write_serial + 阶跃分析 + PID 自整定 | |
| v0.1.0 | IDE 整合 | 三面板布局 + 可扩展工具插件系统 | |

---

## 分支策略

- `main` — 稳定标签线，每个版本一个 tag（`v0.0.1`, `v0.0.2` ...）
- `dev/v0.0.X` — 功能累积分支，完成后合入 `main`
