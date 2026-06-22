"""
记忆系统 — ChromaDB 向量存储 + 语义检索。

数据流:
  对话结束 → 提取用户消息 → 嵌入 → 存入 ChromaDB
  新对话开始 → 用户首条消息 → 语义搜索 → 注入 System Prompt
"""

import os
import json
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from datetime import datetime

# ─── 存储路径 ────────────────────────────────
MEMORY_DIR = Path.home() / ".camelia-studio" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# ─── 嵌入函数（ONNX 本地模型，首次自动下载 ~80MB）──
_ef = embedding_functions.DefaultEmbeddingFunction()

# ─── ChromaDB 客户端 ──────────────────────────
_client = chromadb.PersistentClient(
    path=str(MEMORY_DIR),
    settings=chromadb.Settings(anonymized_telemetry=False),
)

_collection = _client.get_or_create_collection(
    name="conversations",
    embedding_function=_ef,
    metadata={"description": "Camelia Studio 对话记忆"},
)


def _chunk_messages(messages: list[dict], max_chars: int = 800) -> list[str]:
    """将消息列表切成适合嵌入的小块。user 和 assistant 消息配对成块。"""
    chunks = []
    current = []
    current_len = 0

    for m in messages:
        if m["role"] == "system":
            continue
        content = m["content"]
        if current_len + len(content) > max_chars and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(f"[{m['role']}] {content}")
        current_len += len(content)

    if current:
        chunks.append("\n".join(current))

    return chunks


def add_session(session_id: str, messages: list[dict], title: str = "") -> None:
    """将一段对话存入记忆库。只存 user 和 assistant 消息，按块嵌入。"""
    chunks = _chunk_messages(messages)
    if not chunks:
        return

    # 标题：传入的优先，否则取第一条 user 消息截断
    if not title:
        for m in messages:
            if m["role"] == "user":
                title = m["content"][:50]
                break
        if not title:
            title = "未命名对话"

    timestamp = datetime.now().isoformat()

    # 去重：已存在同 session_id 的内容先删
    try:
        existing = _collection.get(where={"session_id": session_id})
        if existing["ids"]:
            _collection.delete(ids=existing["ids"])
    except Exception:
        pass

    ids = [f"{session_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {"session_id": session_id, "title": title, "timestamp": timestamp, "chunk": i}
        for i in range(len(chunks))
    ]

    _collection.add(ids=ids, documents=chunks, metadatas=metadatas)


def search(query: str, n: int = 5) -> list[dict]:
    """语义搜索记忆库，返回最相关的对话片段。"""
    if _collection.count() == 0:
        return []

    results = _collection.query(query_texts=[query], n_results=n)

    memories = []
    for i, doc_id in enumerate(results["ids"][0]):
        memories.append({
            "id": doc_id,
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
        })

    return memories


def format_memories(memories: list[dict]) -> str:
    """将检索到的记忆格式化为 System Prompt 可用的上下文字符串。"""
    if not memories:
        return ""

    lines = ["## 相关历史记忆\n"]
    for i, mem in enumerate(memories):
        title = mem.get("metadata", {}).get("title", "无标题")
        lines.append(f"### 记忆 {i + 1} — {title}")
        lines.append(mem["content"])
        lines.append("")

    return "\n".join(lines)


def memory_count() -> int:
    """返回记忆库中的文档块数量。"""
    return _collection.count()
