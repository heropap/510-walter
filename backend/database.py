from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings


def _connect() -> sqlite3.Connection:
    settings = get_settings()
    settings.ensure_dirs()
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def from_json(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for key in ("chapters", "metadata", "source_textbooks", "sources", "affected_nodes", "citations", "options"):
        if key in data:
            data[key] = from_json(data[key], [] if key.endswith("s") else {})
    return data


def init_db(database_path: Path | None = None) -> None:
    if database_path:
        get_settings().database_path = database_path
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS textbooks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                source_path TEXT NOT NULL,
                split_path TEXT,
                status TEXT NOT NULL DEFAULT 'ready',
                total_chars INTEGER NOT NULL DEFAULT 0,
                chapter_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT PRIMARY KEY,
                textbook_id TEXT NOT NULL,
                title TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 1,
                parent_id TEXT,
                path TEXT NOT NULL,
                content TEXT NOT NULL,
                char_count INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                metadata TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(textbook_id) REFERENCES textbooks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                textbook_id TEXT,
                name TEXT NOT NULL,
                definition TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '核心概念',
                body_system TEXT NOT NULL DEFAULT '全身/通用',
                organ TEXT NOT NULL DEFAULT '未知',
                anatomical_region TEXT NOT NULL DEFAULT '未知',
                scale_level TEXT NOT NULL DEFAULT '未知',
                stage TEXT NOT NULL DEFAULT '未知',
                importance TEXT NOT NULL DEFAULT 'medium',
                frequency INTEGER NOT NULL DEFAULT 1,
                evidence TEXT NOT NULL DEFAULT '',
                chapter_id TEXT,
                chapter_title TEXT,
                source_textbooks TEXT NOT NULL DEFAULT '[]',
                method TEXT NOT NULL DEFAULT 'rule',
                confidence REAL NOT NULL DEFAULT 0.72,
                x REAL,
                y REAL,
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                medical_relation_type TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.7,
                evidence TEXT NOT NULL DEFAULT '',
                textbook_id TEXT,
                chapter_title TEXT,
                method TEXT NOT NULL DEFAULT 'rule'
            );

            CREATE TABLE IF NOT EXISTS integration_decisions (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                affected_nodes TEXT NOT NULL DEFAULT '[]',
                result_node TEXT,
                reason TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.75,
                char_saved INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS decision_overrides (
                id TEXT PRIMARY KEY,
                status TEXT,
                reason TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rag_chunks (
                id TEXT PRIMARY KEY,
                textbook_id TEXT NOT NULL,
                chapter_id TEXT NOT NULL,
                text TEXT NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
