"""Estado do simulador em SQLite: tickets, entregas, notas e controle de agenda."""
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id TEXT,
    kind TEXT,
    difficulty TEXT,
    phase INTEGER,
    persona TEXT,
    title TEXT,
    body TEXT,
    deliverable TEXT,
    notes_for_senior TEXT,
    status TEXT DEFAULT 'open',      -- open | delivered | reviewed
    source TEXT,                     -- ai | catalog
    created_at TEXT,
    deadline_at TEXT,
    delivered_at TEXT,
    doc_path TEXT,
    review TEXT,
    score REAL
);
CREATE TABLE IF NOT EXISTS slots_sent(
    day TEXT,
    slot TEXT,
    PRIMARY KEY(day, slot)
);
CREATE TABLE IF NOT EXISTS kv(
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def tx():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with tx() as c:
        c.executescript(SCHEMA)


# ---------- chave/valor ----------
def get_kv(key, default=None):
    with tx() as c:
        row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_kv(key, value):
    with tx() as c:
        c.execute(
            "INSERT INTO kv(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


def del_kv(key):
    with tx() as c:
        c.execute("DELETE FROM kv WHERE key=?", (key,))


# ---------- agenda ----------
def slot_sent(day, slot):
    with tx() as c:
        return c.execute(
            "SELECT 1 FROM slots_sent WHERE day=? AND slot=?", (day, slot)
        ).fetchone() is not None


def mark_slot(day, slot):
    with tx() as c:
        c.execute("INSERT OR IGNORE INTO slots_sent(day, slot) VALUES(?,?)", (day, slot))


# ---------- tickets ----------
def create_ticket(t):
    with tx() as c:
        cur = c.execute(
            """INSERT INTO tickets(catalog_id, kind, difficulty, phase, persona, title, body,
                                   deliverable, notes_for_senior, source, created_at, deadline_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                t.get("catalog_id"), t["kind"], t["difficulty"], t["phase"], t["persona"],
                t["title"], t["body"], t.get("deliverable", ""), t.get("notes_for_senior", ""),
                t["source"], t["created_at"], t["deadline_at"],
            ),
        )
        return cur.lastrowid


def get_ticket(tid):
    with tx() as c:
        return c.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()


def open_tickets():
    with tx() as c:
        return c.execute(
            "SELECT * FROM tickets WHERE status='open' ORDER BY id"
        ).fetchall()


def awaiting_review():
    with tx() as c:
        return c.execute(
            "SELECT * FROM tickets WHERE status='delivered' ORDER BY id"
        ).fetchall()


def used_catalog_ids():
    with tx() as c:
        rows = c.execute(
            "SELECT catalog_id FROM tickets WHERE catalog_id IS NOT NULL"
        ).fetchall()
    return [r["catalog_id"] for r in rows]


def recent_titles(n=12):
    with tx() as c:
        rows = c.execute("SELECT title FROM tickets ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [r["title"] for r in rows]


def save_delivery(tid, doc_path, when):
    with tx() as c:
        c.execute(
            "UPDATE tickets SET status='delivered', doc_path=?, delivered_at=? WHERE id=?",
            (str(doc_path), when, tid),
        )


def save_review(tid, review, score):
    with tx() as c:
        c.execute(
            "UPDATE tickets SET status='reviewed', review=?, score=? WHERE id=?",
            (review, score, tid),
        )


def set_score(tid, score):
    with tx() as c:
        c.execute("UPDATE tickets SET status='reviewed', score=? WHERE id=?", (score, tid))


def stats():
    with tx() as c:
        by_status = {
            r["status"]: r["n"]
            for r in c.execute("SELECT status, COUNT(*) n FROM tickets GROUP BY status")
        }
        by_diff = [
            dict(r)
            for r in c.execute(
                "SELECT difficulty, COUNT(score) n, AVG(score) avg "
                "FROM tickets WHERE score IS NOT NULL GROUP BY difficulty"
            )
        ]
        overall = c.execute(
            "SELECT AVG(score) a, COUNT(score) n FROM tickets WHERE score IS NOT NULL"
        ).fetchone()
        late = c.execute(
            "SELECT COUNT(*) n FROM tickets WHERE delivered_at IS NOT NULL AND delivered_at > deadline_at"
        ).fetchone()["n"]
    return {
        "by_status": by_status,
        "by_difficulty": by_diff,
        "avg": overall["a"],
        "scored": overall["n"],
        "late": late,
    }
