import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


class DiaryEntry:
    def __init__(self, id, created_at, content, tags, conversation_id):
        self.id = id
        self.created_at = created_at
        self.content = content
        self.tags = tags
        self.conversation_id = conversation_id


SCHEMA_SQL = """
PRAGMA journal_mode = 'wal';
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,
    conversation_id TEXT,
    source TEXT DEFAULT 'claude-code',
    embedding BLOB
);

CREATE INDEX IF NOT EXISTS idx_entries_created ON entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_entries_conversation ON entries(conversation_id);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    content,
    tags,
    content=entries,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, content, tags)
    VALUES (new.id, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, content, tags)
    VALUES ('delete', old.id, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, content, tags)
    VALUES ('delete', old.id, old.content, old.tags);
    INSERT INTO entries_fts(rowid, content, tags)
    VALUES (new.id, new.content, new.tags);
END;
"""


class DiaryDatabase:
    def __init__(self, db_path, embeddings=None):
        self._embeddings = embeddings
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA_SQL)

    def write_entry(self, content, tags=None, conversation_id=None, source="claude-code"):
        text_to_embed = f"{content}\n{tags}" if tags else content
        embedding_blob = None
        if self._embeddings and self._embeddings.is_available:
            try:
                embedding_blob = self._embeddings.serialize(
                    self._embeddings.embed(text_to_embed)
                )
            except Exception:
                pass

        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            """INSERT INTO entries (created_at, content, tags, conversation_id, source, embedding)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (now, content, tags, conversation_id, source, embedding_blob),
        )
        self._conn.commit()
        return cursor.lastrowid

    def update_entry(self, id, content, tags=None):
        row = self._conn.execute("SELECT id FROM entries WHERE id = ?", (id,)).fetchone()
        if not row:
            return False

        text_to_embed = f"{content}\n{tags}" if tags else content
        embedding_blob = None
        if self._embeddings and self._embeddings.is_available:
            try:
                embedding_blob = self._embeddings.serialize(
                    self._embeddings.embed(text_to_embed)
                )
            except Exception:
                pass

        self._conn.execute(
            "UPDATE entries SET content = ?, tags = ?, embedding = ? WHERE id = ?",
            (content, tags, embedding_blob, id),
        )
        self._conn.commit()
        return True

    def get_entry(self, id):
        row = self._conn.execute(
            "SELECT id, created_at, content, tags, conversation_id FROM entries WHERE id = ?",
            (id,),
        ).fetchone()
        if not row:
            return None
        return DiaryEntry(*row)

    def get_recent(self, count=10):
        rows = self._conn.execute(
            """SELECT id, created_at, content, tags, conversation_id
               FROM entries ORDER BY created_at DESC LIMIT ?""",
            (count,),
        ).fetchall()
        return [DiaryEntry(*r) for r in rows]

    def get_entry_count(self):
        row = self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()
        return row[0]

    def search(self, query, limit=10):
        if not query or not query.strip():
            return self.get_recent(limit)

        if self._embeddings and self._embeddings.is_available:
            try:
                return self._vector_search(query, limit)
            except Exception:
                pass

        return self._search_like(query, limit)

    def _vector_search(self, query, limit):
        query_embedding = self._embeddings.embed(query)

        rows = self._conn.execute(
            """SELECT id, created_at, content, tags, conversation_id, embedding
               FROM entries WHERE embedding IS NOT NULL"""
        ).fetchall()

        scored = []
        for row in rows:
            entry = DiaryEntry(*row[:5])
            embedding = self._embeddings.deserialize(row[5])
            score = self._embeddings.similarity(query_embedding, embedding)
            scored.append((entry, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [entry for entry, _ in scored[:limit]]

    def _search_like(self, query, limit):
        pattern = f"%{query}%"
        rows = self._conn.execute(
            """SELECT id, created_at, content, tags, conversation_id
               FROM entries
               WHERE content LIKE ? OR tags LIKE ?
               ORDER BY created_at DESC LIMIT ?""",
            (pattern, pattern, limit),
        ).fetchall()
        return [DiaryEntry(*r) for r in rows]

    def backfill_embeddings(self):
        if not self._embeddings or not self._embeddings.is_available:
            return 0

        rows = self._conn.execute(
            "SELECT id, content, tags FROM entries WHERE embedding IS NULL"
        ).fetchall()

        if not rows:
            return 0

        print(f"Backfilling embeddings for {len(rows)} entries...", file=sys.stderr)
        count = 0
        for id, content, tags in rows:
            try:
                text = f"{content}\n{tags}" if tags else content
                blob = self._embeddings.serialize(self._embeddings.embed(text))
                self._conn.execute(
                    "UPDATE entries SET embedding = ? WHERE id = ?", (blob, id)
                )
                count += 1
            except Exception as e:
                print(f"  Failed entry #{id}: {e}", file=sys.stderr)

        self._conn.commit()
        print(f"Backfilled {count}/{len(rows)} entries.", file=sys.stderr)
        return count

    def close(self):
        self._conn.close()
