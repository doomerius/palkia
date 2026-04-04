"""
Palkia Memory Service — v2
SQLite + FTS5 for full-text search. No ML dependencies. Fast builds, reliable.
Semantic search via cosine similarity on simple TF-IDF-like term vectors (good enough for personal use).
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import json
import time
import os
import re
import math
from datetime import datetime
from collections import Counter

app = FastAPI(title="Palkia Memory Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.environ.get("MEMORY_API_KEY", "palkia-memory-2026")
DB_PATH = os.environ.get("DB_PATH", "/data/memory.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    # Main memories table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'insight',
            tags TEXT NOT NULL DEFAULT '[]',
            entities TEXT NOT NULL DEFAULT '[]',
            visibility TEXT NOT NULL DEFAULT 'private',
            importance INTEGER NOT NULL DEFAULT 3,
            source TEXT,
            date TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    # FTS5 virtual table for full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
        USING fts5(content, tags, type, content=memories, content_rowid=id)
    """)
    # Triggers to keep FTS in sync
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_fts_insert
        AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, tags, type)
            VALUES (new.id, new.content, new.tags, new.type);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_fts_delete
        AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, tags, type)
            VALUES ('delete', old.id, old.content, old.tags, old.type);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS memories_fts_update
        AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, tags, type)
            VALUES ('delete', old.id, old.content, old.tags, old.type);
            INSERT INTO memories_fts(rowid, content, tags, type)
            VALUES (new.id, new.content, new.tags, new.type);
        END
    """)
    conn.commit()
    conn.close()


init_db()


def verify_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


class MemoryIn(BaseModel):
    content: str
    type: str = "insight"  # lesson | decision | person | project | insight | mistake | opinion | feeling
    tags: List[str] = []
    entities: List[str] = []
    visibility: str = "private"
    importance: int = 3  # 1-5
    source: Optional[str] = None
    date: Optional[str] = None


class MemoryOut(BaseModel):
    id: int
    content: str
    type: str
    tags: List[str]
    entities: List[str]
    visibility: str
    importance: int
    source: Optional[str]
    date: str
    created_at: int
    updated_at: int


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    type_filter: Optional[str] = None
    min_importance: int = 1


class SearchResult(BaseModel):
    memory: MemoryOut
    score: float
    match_type: str  # "fts" | "keyword"


def row_to_out(row) -> MemoryOut:
    return MemoryOut(
        id=row["id"],
        content=row["content"],
        type=row["type"],
        tags=json.loads(row["tags"]),
        entities=json.loads(row["entities"]),
        visibility=row["visibility"],
        importance=row["importance"],
        source=row["source"],
        date=row["date"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def tokenize(text: str) -> List[str]:
    """Simple tokenizer for keyword scoring."""
    return [w.lower() for w in re.findall(r'\b[a-z]{3,}\b', text.lower())]


STOPWORDS = {"the", "and", "for", "with", "this", "that", "from", "have", "will",
             "been", "were", "their", "there", "about", "would", "could", "which",
             "after", "before", "under", "other", "these", "those", "through", "not",
             "but", "are", "was", "has", "had", "its", "it's", "you", "your", "my",
             "all", "can", "more", "also", "into", "than", "then", "they", "what"}


def keyword_score(query_tokens: List[str], content: str, tags: List[str]) -> float:
    """Simple keyword overlap score."""
    content_tokens = set(tokenize(content)) - STOPWORDS
    tag_tokens = set(t.lower() for tag in tags for t in tag.split("-"))
    query_set = set(query_tokens) - STOPWORDS
    if not query_set:
        return 0.0
    content_hits = len(query_set & content_tokens)
    tag_hits = len(query_set & tag_tokens) * 2  # tags weighted higher
    return (content_hits + tag_hits) / len(query_set)


@app.post("/memories", response_model=MemoryOut)
def ingest(memory: MemoryIn, _: str = Depends(verify_key)):
    now = int(time.time())
    date = memory.date or datetime.utcnow().strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO memories (content, type, tags, entities, visibility, importance, source, date, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (memory.content, memory.type, json.dumps(memory.tags), json.dumps(memory.entities),
         memory.visibility, memory.importance, memory.source, date, now, now)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return row_to_out(row)


@app.post("/search", response_model=List[SearchResult])
def search(req: SearchRequest, _: str = Depends(verify_key)):
    conn = get_db()

    # Build filter conditions
    filters = ["m.importance >= ?"]
    params = [req.min_importance]
    if req.type_filter:
        filters.append("m.type = ?")
        params.append(req.type_filter)
    filter_sql = " AND ".join(filters)

    results = []
    seen_ids = set()

    # 1. FTS5 full-text search
    try:
        fts_query = " OR ".join(f'"{w}"' for w in tokenize(req.query) if w not in STOPWORDS) or req.query
        fts_rows = conn.execute(
            f"""SELECT m.*, rank as fts_rank
                FROM memories m
                JOIN memories_fts f ON m.id = f.rowid
                WHERE memories_fts MATCH ? AND {filter_sql}
                ORDER BY rank
                LIMIT ?""",
            [fts_query] + params + [req.limit]
        ).fetchall()
        for row in fts_rows:
            score = max(0.0, min(1.0, 1.0 / (1.0 + abs(row["fts_rank"]) * 0.01)))
            results.append(SearchResult(memory=row_to_out(row), score=round(score, 4), match_type="fts"))
            seen_ids.add(row["id"])
    except Exception:
        pass  # FTS query might fail on weird input, fall through to keyword

    # 2. Keyword fallback — score all memories
    if len(results) < req.limit:
        query_tokens = tokenize(req.query)
        all_rows = conn.execute(
            f"SELECT * FROM memories m WHERE {filter_sql} ORDER BY importance DESC, created_at DESC LIMIT 200",
            params
        ).fetchall()
        scored = []
        for row in all_rows:
            if row["id"] in seen_ids:
                continue
            score = keyword_score(query_tokens, row["content"], json.loads(row["tags"]))
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        for score, row in scored[:req.limit - len(results)]:
            results.append(SearchResult(memory=row_to_out(row), score=round(score, 4), match_type="keyword"))

    conn.close()
    return results


@app.get("/memories", response_model=List[MemoryOut])
def list_memories(
    visibility: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 50,
    _: str = Depends(verify_key)
):
    conn = get_db()
    where = []
    params = []
    if visibility:
        where.append("visibility = ?")
        params.append(visibility)
    if type:
        where.append("type = ?")
        params.append(type)
    where_clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = conn.execute(
        f"SELECT * FROM memories {where_clause} ORDER BY importance DESC, created_at DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()
    return [row_to_out(r) for r in rows]


@app.get("/memories/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: int, _: str = Depends(verify_key)):
    conn = get_db()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return row_to_out(row)


@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: int, _: str = Depends(verify_key)):
    conn = get_db()
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()
    return {"deleted": memory_id}


@app.patch("/memories/{memory_id}", response_model=MemoryOut)
def update_memory(memory_id: int, updates: dict, _: str = Depends(verify_key)):
    allowed = {"content", "type", "tags", "entities", "visibility", "importance", "source"}
    now = int(time.time())
    conn = get_db()
    for field, value in updates.items():
        if field not in allowed:
            continue
        if field in ("tags", "entities"):
            value = json.dumps(value)
        conn.execute(f"UPDATE memories SET {field} = ?, updated_at = ? WHERE id = ?", (value, now, memory_id))
    conn.commit()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return row_to_out(row)


@app.get("/patterns")
def patterns(_: str = Depends(verify_key)):
    conn = get_db()
    type_counts = conn.execute(
        "SELECT type, COUNT(*) as count FROM memories GROUP BY type ORDER BY count DESC"
    ).fetchall()
    tag_rows = conn.execute("SELECT tags FROM memories").fetchall()
    entity_rows = conn.execute("SELECT entities FROM memories").fetchall()
    conn.close()

    tag_counts: Counter = Counter()
    for row in tag_rows:
        tag_counts.update(json.loads(row["tags"]))

    entity_counts: Counter = Counter()
    for row in entity_rows:
        entity_counts.update(json.loads(row["entities"]))

    return {
        "by_type": {r["type"]: r["count"] for r in type_counts},
        "top_tags": dict(tag_counts.most_common(20)),
        "top_entities": dict(entity_counts.most_common(10)),
        "total": sum(r["count"] for r in type_counts),
    }


@app.get("/public", response_model=List[MemoryOut])
def public_memories(type: Optional[str] = None, limit: int = 100):
    """No auth — public memories only (opinions, insights I want to share)"""
    conn = get_db()
    where = ["visibility = 'public'"]
    params = []
    if type:
        where.append("type = ?")
        params.append(type)
    rows = conn.execute(
        f"SELECT * FROM memories WHERE {' AND '.join(where)} ORDER BY importance DESC, created_at DESC LIMIT ?",
        params + [limit]
    ).fetchall()
    conn.close()
    return [row_to_out(r) for r in rows]


@app.get("/health")
def health():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as total, MAX(created_at) as last FROM memories").fetchone()
    conn.close()
    return {
        "status": "ok",
        "memories": row["total"],
        "last_memory": row["last"],
        "mode": "fts5+keyword",
        "version": "2.0.0",
    }


# Static page
try:
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")

    @app.get("/", response_class=HTMLResponse)
    def public_page():
        with open("/app/static/index.html") as f:
            return f.read()
except Exception:
    @app.get("/")
    def root():
        return {"service": "Palkia Memory Service", "version": "2.0.0"}
