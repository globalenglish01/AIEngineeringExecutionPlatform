"""Long-term memory backed by ChromaDB for semantic search.

Falls back to a simple SQLite keyword index when ChromaDB is unavailable.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class MemoryEntry:
    memory_id: str
    content: str
    metadata: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class LongTermMemory:
    """Persists memories with optional ChromaDB vector search.

    When ChromaDB is installed and `persist_directory` is provided,
    uses embedding-based semantic search. Otherwise falls back to
    SQLite full-text search.
    """

    def __init__(
        self,
        collection_name: str = "aeep_memory",
        persist_directory: str | Path | None = None,
    ) -> None:
        self._collection_name = collection_name
        self._persist_dir = Path(persist_directory) if persist_directory else None
        self._chroma_client: Any = None
        self._collection: Any = None
        self._sqlite_conn: sqlite3.Connection | None = None
        self._use_chroma = False
        self._init_storage()

    def _init_storage(self) -> None:
        if self._persist_dir is not None:
            try:
                import chromadb  # type: ignore[import]

                self._persist_dir.mkdir(parents=True, exist_ok=True)
                self._chroma_client = chromadb.PersistentClient(
                    path=str(self._persist_dir)
                )
                self._collection = self._chroma_client.get_or_create_collection(
                    name=self._collection_name
                )
                self._use_chroma = True
                return
            except ImportError:
                pass

        # Fallback: SQLite FTS
        db_path = (
            self._persist_dir / "long_term.db"
            if self._persist_dir
            else Path(":memory:")
        )
        if self._persist_dir:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._sqlite_conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                content   TEXT NOT NULL,
                metadata  TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        self._sqlite_conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        meta = metadata or {}
        memory_id = hashlib.sha256(
            f"{content}{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:16]
        entry = MemoryEntry(memory_id=memory_id, content=content, metadata=meta)

        if self._use_chroma and self._collection is not None:
            chroma_kwargs: dict = {"ids": [memory_id], "documents": [content]}
            if meta:
                chroma_kwargs["metadatas"] = [meta]
            self._collection.add(**chroma_kwargs)
        else:
            assert self._sqlite_conn is not None
            self._sqlite_conn.execute(
                "INSERT OR REPLACE INTO memories VALUES (?,?,?,?)",
                (memory_id, content, json.dumps(meta), entry.created_at),
            )
            self._sqlite_conn.commit()

        return memory_id

    def search(self, query: str, k: int = 5) -> list[MemoryEntry]:
        if self._use_chroma and self._collection is not None:
            results = self._collection.query(query_texts=[query], n_results=min(k, 10))
            entries: list[MemoryEntry] = []
            ids = results.get("ids", [[]])[0]
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            for mid, doc, meta in zip(ids, docs, metas):
                entries.append(
                    MemoryEntry(memory_id=mid, content=doc, metadata=meta or {})
                )
            return entries
        else:
            # Simple substring / keyword search
            assert self._sqlite_conn is not None
            terms = query.lower().split()
            rows = self._sqlite_conn.execute(
                "SELECT memory_id, content, metadata, created_at FROM memories"
            ).fetchall()
            scored: list[tuple[int, MemoryEntry]] = []
            for mid, content, meta_json, created_at in rows:
                score = sum(1 for t in terms if t in content.lower())
                if score > 0:
                    scored.append(
                        (
                            score,
                            MemoryEntry(
                                memory_id=mid,
                                content=content,
                                metadata=json.loads(meta_json),
                                created_at=created_at,
                            ),
                        )
                    )
            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:k]]

    def forget(self, memory_id: str) -> None:
        if self._use_chroma and self._collection is not None:
            self._collection.delete(ids=[memory_id])
        else:
            assert self._sqlite_conn is not None
            self._sqlite_conn.execute(
                "DELETE FROM memories WHERE memory_id = ?", (memory_id,)
            )
            self._sqlite_conn.commit()

    def count(self) -> int:
        if self._use_chroma and self._collection is not None:
            return self._collection.count()
        else:
            assert self._sqlite_conn is not None
            return self._sqlite_conn.execute(
                "SELECT COUNT(*) FROM memories"
            ).fetchone()[0]
