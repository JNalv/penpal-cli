"""SQLite database management using stdlib sqlite3."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

from penpal.models import CostSummary, Request, Response

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        TEXT UNIQUE NOT NULL,
    custom_id       TEXT,
    model           TEXT NOT NULL,
    system_prompt   TEXT,
    skill_name      TEXT,
    user_prompt     TEXT NOT NULL,
    file_name       TEXT,
    tag             TEXT,
    max_tokens      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'processing',
    is_read         INTEGER NOT NULL DEFAULT 0,
    is_multi        INTEGER NOT NULL DEFAULT 0,
    request_count   INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    expires_at      TEXT,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    estimated_cost  REAL
);

CREATE TABLE IF NOT EXISTS responses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      INTEGER NOT NULL REFERENCES requests(id),
    custom_id       TEXT,
    file_name       TEXT,
    content         TEXT NOT NULL,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    estimated_cost  REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);
CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at);
CREATE INDEX IF NOT EXISTS idx_requests_tag ON requests(tag);
"""


@contextmanager
def get_conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        # Migration: add expires_at if not present (existing databases)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(requests)").fetchall()}
        if "expires_at" not in cols:
            conn.execute("ALTER TABLE requests ADD COLUMN expires_at TEXT")


def _row_to_request(row: sqlite3.Row) -> Request:
    return Request(
        id=row["id"],
        batch_id=row["batch_id"],
        custom_id=row["custom_id"],
        model=row["model"],
        system_prompt=row["system_prompt"],
        skill_name=row["skill_name"],
        user_prompt=row["user_prompt"],
        file_name=row["file_name"],
        tag=row["tag"],
        max_tokens=row["max_tokens"],
        status=row["status"],
        is_read=bool(row["is_read"]),
        is_multi=bool(row["is_multi"]),
        request_count=row["request_count"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        expires_at=row["expires_at"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        estimated_cost=row["estimated_cost"],
    )


def _row_to_response(row: sqlite3.Row) -> Response:
    return Response(
        id=row["id"],
        request_id=row["request_id"],
        custom_id=row["custom_id"],
        file_name=row["file_name"],
        content=row["content"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        estimated_cost=row["estimated_cost"],
        created_at=row["created_at"],
    )


def save_request(
    db_path: Path,
    batch_id: str,
    model: str,
    user_prompt: str,
    max_tokens: int,
    custom_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    skill_name: Optional[str] = None,
    file_name: Optional[str] = None,
    tag: Optional[str] = None,
    is_multi: bool = False,
    request_count: int = 1,
    expires_at: Optional[str] = None,
) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO requests
               (batch_id, custom_id, model, system_prompt, skill_name,
                user_prompt, file_name, tag, max_tokens, is_multi, request_count, expires_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (batch_id, custom_id, model, system_prompt, skill_name,
             user_prompt, file_name, tag, max_tokens, int(is_multi), request_count, expires_at),
        )
        return cur.lastrowid


def update_request_status(
    db_path: Path,
    batch_id: str,
    status: str,
    completed_at: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    estimated_cost: Optional[float] = None,
) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """UPDATE requests
               SET status=?, completed_at=?, input_tokens=?, output_tokens=?, estimated_cost=?
               WHERE batch_id=?""",
            (status, completed_at, input_tokens, output_tokens, estimated_cost, batch_id),
        )


def save_response(
    db_path: Path,
    request_id: int,
    content: str,
    custom_id: Optional[str] = None,
    file_name: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    estimated_cost: Optional[float] = None,
) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO responses
               (request_id, custom_id, file_name, content, input_tokens, output_tokens, estimated_cost)
               VALUES (?,?,?,?,?,?,?)""",
            (request_id, custom_id, file_name, content, input_tokens, output_tokens, estimated_cost),
        )
        return cur.lastrowid


def get_request_by_batch_id(db_path: Path, batch_id: str) -> Optional[Request]:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM requests WHERE batch_id=? OR batch_id LIKE ?",
            (batch_id, batch_id + "%"),
        ).fetchone()
        return _row_to_request(row) if row else None


def get_request_by_tag(db_path: Path, tag: str) -> Optional[Request]:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM requests WHERE tag=? ORDER BY created_at DESC LIMIT 1",
            (tag,),
        ).fetchone()
        return _row_to_request(row) if row else None


def get_pending_requests(db_path: Path) -> list[Request]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM requests WHERE status='processing' ORDER BY created_at"
        ).fetchall()
        return [_row_to_request(r) for r in rows]


def get_recent_requests(
    db_path: Path,
    limit: int = 10,
    include_all: bool = False,
    model_filter: Optional[str] = None,
    since: Optional[str] = None,
) -> list[Request]:
    query = "SELECT * FROM requests WHERE 1=1"
    params: list = []
    if not include_all:
        query += " AND created_at >= datetime('now', '-7 days')"
    if model_filter:
        query += " AND model LIKE ?"
        params.append(f"%{model_filter}%")
    if since:
        query += " AND created_at >= ?"
        params.append(since)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_request(r) for r in rows]


def get_responses(db_path: Path, request_id: int) -> list[Response]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM responses WHERE request_id=? ORDER BY id",
            (request_id,),
        ).fetchall()
        return [_row_to_response(r) for r in rows]


def update_expires_at(db_path: Path, batch_id: str, expires_at: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE requests SET expires_at=? WHERE batch_id=?",
            (expires_at, batch_id),
        )


def mark_as_read(db_path: Path, batch_id: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE requests SET is_read=1 WHERE batch_id=?",
            (batch_id,),
        )


def delete_request(db_path: Path, batch_id: str) -> bool:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM requests WHERE batch_id=?", (batch_id,)
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM responses WHERE request_id=?", (row["id"],))
        conn.execute("DELETE FROM requests WHERE batch_id=?", (batch_id,))
        return True


def search_requests(
    db_path: Path,
    query: str,
    model_filter: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 20,
) -> list[Request]:
    sql = "SELECT * FROM requests WHERE (user_prompt LIKE ? OR tag LIKE ?)"
    params: list = [f"%{query}%", f"%{query}%"]
    if model_filter:
        sql += " AND model LIKE ?"
        params.append(f"%{model_filter}%")
    if since:
        sql += " AND created_at >= ?"
        params.append(since)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_request(r) for r in rows]


def get_cost_summary(db_path: Path, since: Optional[str] = None) -> CostSummary:
    sql_base = "SELECT model, estimated_cost FROM requests WHERE estimated_cost IS NOT NULL"
    params: list = []
    if since:
        sql_base += " AND created_at >= ?"
        params.append(since)

    count_sql = "SELECT COUNT(*) FROM requests WHERE 1=1"
    count_params: list = []
    if since:
        count_sql += " AND created_at >= ?"
        count_params.append(since)

    with get_conn(db_path) as conn:
        rows = conn.execute(sql_base, params).fetchall()
        count = conn.execute(count_sql, count_params).fetchone()[0]

    total = 0.0
    by_model: dict[str, float] = {}
    for row in rows:
        cost = row["estimated_cost"] or 0.0
        total += cost
        model = row["model"]
        by_model[model] = by_model.get(model, 0.0) + cost

    return CostSummary(total=total, by_model=by_model, request_count=count)


def get_latest_completed(db_path: Path) -> Optional[Request]:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM requests WHERE status='completed' ORDER BY completed_at DESC LIMIT 1"
        ).fetchone()
        return _row_to_request(row) if row else None
