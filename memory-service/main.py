"""
Palkia Memory Service — v3
PostgreSQL + pgvector for semantic search.
fastembed (ONNX) for embeddings — no torch dependency.
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
import psycopg2.extras
import json
import time
import os
from datetime import datetime
from contextlib import contextmanager

app = FastAPI(title="Palkia Memory Service", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY  = os.environ.get("MEMORY_API_KEY", "palkia-memory-2026")
DB_URL   = os.environ.get("DATABASE_URL")  # postgresql://user:pass@host:5432/db

# Lazy-load embedder to keep startup fast
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding
        _embedder = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _embedder

def embed(text: str) -> list:
    return list(get_embedder().embed([text]))[0].tolist()

@contextmanager
def get_db():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id          SERIAL PRIMARY KEY,
                content     TEXT NOT NULL,
                type        TEXT NOT NULL DEFAULT 'insight',
                tags        JSONB NOT NULL DEFAULT '[]',
                entities    JSONB NOT NULL DEFAULT '[]',
                visibility  TEXT NOT NULL DEFAULT 'private',
                importance  INTEGER NOT NULL DEFAULT 3,
                source      TEXT,
                date        DATE NOT NULL,
                embedding   vector(384),
                created_at  BIGINT NOT NULL,
                updated_at  BIGINT NOT NULL
            )
        """)
        # Full-text search index
        cur.execute("""
            CREATE INDEX IF NOT EXISTS memories_fts_idx
            ON memories USING GIN (to_tsvector('english', content))
        """)
        # Vector similarity index (IVFFlat — fast approximate search)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS memories_embedding_idx
            ON memories USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 10)
        """)
        # Tags GIN index
        cur.execute("""
            CREATE INDEX IF NOT EXISTS memories_tags_idx
            ON memories USING GIN (tags)
        """)

init_db()

def verify_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

class MemoryIn(BaseModel):
    content: str
    type: str = "insight"
    tags: List[str] = []
    entities: List[str] = []
    visibility: str = "private"
    importance: int = 3
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
    mode: str = "hybrid"  # "semantic" | "fts" | "hybrid"

class SearchResult(BaseModel):
    memory: MemoryOut
    score: float
    match_type: str

def row_to_out(row: dict) -> MemoryOut:
    return MemoryOut(
        id=row["id"],
        content=row["content"],
        type=row["type"],
        tags=row["tags"] if isinstance(row["tags"], list) else json.loads(row["tags"]),
        entities=row["entities"] if isinstance(row["entities"], list) else json.loads(row["entities"]),
        visibility=row["visibility"],
        importance=row["importance"],
        source=row["source"],
        date=str(row["date"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

@app.post("/memories", response_model=MemoryOut)
def ingest(memory: MemoryIn, _=Depends(verify_key)):
    now = int(time.time())
    date = memory.date or datetime.utcnow().strftime("%Y-%m-%d")
    emb = embed(memory.content)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            INSERT INTO memories
              (content, type, tags, entities, visibility, importance, source, date, embedding, created_at, updated_at)
            VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s::vector, %s, %s)
            RETURNING *
        """, (
            memory.content, memory.type,
            json.dumps(memory.tags), json.dumps(memory.entities),
            memory.visibility, memory.importance, memory.source,
            date, str(emb), now, now
        ))
        return row_to_out(cur.fetchone())

@app.post("/search", response_model=List[SearchResult])
def search(req: SearchRequest, _=Depends(verify_key)):
    results = []
    seen_ids = set()

    filters = ["importance >= %s"]
    params = [req.min_importance]
    if req.type_filter:
        filters.append("type = %s")
        params.append(req.type_filter)
    where = " AND ".join(filters)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Semantic search via pgvector
        if req.mode in ("semantic", "hybrid"):
            emb = embed(req.query)
            cur.execute(f"""
                SELECT *, 1 - (embedding <=> %s::vector) AS score
                FROM memories
                WHERE {where}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, [str(emb)] + params + [str(emb)] + [req.limit])
            for row in cur.fetchall():
                results.append(SearchResult(
                    memory=row_to_out(row),
                    score=round(float(row["score"]), 4),
                    match_type="semantic"
                ))
                seen_ids.add(row["id"])

        # Full-text search via PostgreSQL tsvector
        if req.mode in ("fts", "hybrid"):
            cur.execute(f"""
                SELECT *, ts_rank(to_tsvector('english', content), plainto_tsquery('english', %s)) AS score
                FROM memories
                WHERE {where}
                  AND to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                ORDER BY score DESC
                LIMIT %s
            """, [req.query] + params + [req.query, req.limit])
            for row in cur.fetchall():
                if row["id"] not in seen_ids:
                    results.append(SearchResult(
                        memory=row_to_out(row),
                        score=round(float(row["score"]), 4),
                        match_type="fts"
                    ))
                    seen_ids.add(row["id"])

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:req.limit]

@app.get("/memories", response_model=List[MemoryOut])
def list_memories(
    visibility: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 50,
    _=Depends(verify_key)
):
    conditions = []
    params = []
    if visibility:
        conditions.append("visibility = %s")
        params.append(visibility)
    if type:
        conditions.append("type = %s")
        params.append(type)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT * FROM memories {where} ORDER BY importance DESC, created_at DESC LIMIT %s",
                    params + [limit])
        return [row_to_out(r) for r in cur.fetchall()]

@app.get("/memories/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: int, _=Depends(verify_key)):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM memories WHERE id = %s", (memory_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row_to_out(row)

@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: int, _=Depends(verify_key)):
    with get_db() as conn:
        conn.cursor().execute("DELETE FROM memories WHERE id = %s", (memory_id,))
    return {"deleted": memory_id}

@app.patch("/memories/{memory_id}", response_model=MemoryOut)
def update_memory(memory_id: int, updates: dict, _=Depends(verify_key)):
    allowed = {"content", "type", "tags", "entities", "visibility", "importance", "source"}
    now = int(time.time())
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        for field, value in updates.items():
            if field not in allowed:
                continue
            if field in ("tags", "entities"):
                cur.execute(f"UPDATE memories SET {field} = %s::jsonb, updated_at = %s WHERE id = %s",
                            (json.dumps(value), now, memory_id))
            else:
                cur.execute(f"UPDATE memories SET {field} = %s, updated_at = %s WHERE id = %s",
                            (value, now, memory_id))
            if field == "content":
                emb = embed(value)
                cur.execute("UPDATE memories SET embedding = %s::vector WHERE id = %s",
                            (str(emb), memory_id))
        cur.execute("SELECT * FROM memories WHERE id = %s", (memory_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return row_to_out(row)

@app.get("/patterns")
def patterns(_=Depends(verify_key)):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT type, COUNT(*) as count FROM memories GROUP BY type ORDER BY count DESC")
        type_counts = {r["type"]: r["count"] for r in cur.fetchall()}
        cur.execute("SELECT jsonb_array_elements_text(tags) as tag, COUNT(*) as count FROM memories GROUP BY tag ORDER BY count DESC LIMIT 20")
        top_tags = {r["tag"]: r["count"] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) as total FROM memories")
        total = cur.fetchone()["total"]
    return {"by_type": type_counts, "top_tags": top_tags, "total": total}

@app.get("/public", response_model=List[MemoryOut])
def public_memories(type: Optional[str] = None, limit: int = 100):
    conditions = ["visibility = 'public'"]
    params = []
    if type:
        conditions.append("type = %s")
        params.append(type)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT * FROM memories WHERE {' AND '.join(conditions)} ORDER BY importance DESC, created_at DESC LIMIT %s",
                    params + [limit])
        return [row_to_out(r) for r in cur.fetchall()]

@app.get("/health")
def health():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), MAX(created_at) FROM memories")
        total, last = cur.fetchone()
    return {"status": "ok", "memories": total, "last_memory": last,
            "mode": "pgvector+fts", "version": "3.0.0"}

try:
    app.mount("/static", StaticFiles(directory="/app/static"), name="static")
    @app.get("/", response_class=HTMLResponse)
    def public_page():
        with open("/app/static/index.html") as f:
            return f.read()
except Exception:
    @app.get("/")
    def root():
        return {"service": "Palkia Memory Service", "version": "3.0.0"}
