import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from pathlib import Path

import catalog
import library as lib

ITEM_FIELDS = ("id", "source", "via", "url", "title", "clean_title", "author", "folder", "saved", "seen",
               "removed", "kind", "scene", "topic", "excerpt", "status")
SCHEMA = """
CREATE TABLE item (
    id TEXT PRIMARY KEY, source TEXT, via TEXT, url TEXT, title TEXT, clean_title TEXT,
    author TEXT, folder TEXT, saved TEXT, seen TEXT, removed TEXT, kind TEXT, scene TEXT,
    topic TEXT, excerpt TEXT, status TEXT
);
CREATE INDEX item_topic ON item(topic);
CREATE TABLE topic (
    id TEXT PRIMARY KEY, name TEXT, parent TEXT, summary TEXT, size INTEGER, updated TEXT, note TEXT, owner TEXT
);
CREATE INDEX topic_parent ON topic(parent);
CREATE TABLE edge (src TEXT, dst TEXT, rel TEXT, by TEXT, PRIMARY KEY (src, dst, rel));
CREATE INDEX edge_dst ON edge(dst);
CREATE TABLE entity (id TEXT PRIMARY KEY, type TEXT, name TEXT);
CREATE VIRTUAL TABLE search USING fts5(
    id UNINDEXED, clean_title, scene, excerpt, topic, entities, tokenize='trigram'
);
CREATE TABLE build (stamp TEXT);
"""


def db_path():
    return lib.state_path("starhub.db")


def signature():
    home = lib.HOME
    paths = [lib.state_path(name) for name in ("labels.jsonl", "taxonomy.json", "curation.jsonl", "notes.json")]
    paths.extend((home / "raw").glob("*.jsonl"))
    paths.extend(path for path in (home / "wiki").rglob("*.md") if path.parent != home / "wiki"
                 or path.name not in ("index.md", "log.md"))
    paths.extend((home / "raw/cache").rglob("*.md"))
    stamp = hashlib.sha256(SCHEMA.encode("utf-8"))
    for path in sorted(paths):
        if path.exists():
            info = path.stat()
            record = f"{path.relative_to(home)}\0{info.st_mtime_ns}\0{info.st_size}\0"
            stamp.update(record.encode("utf-8"))
    return stamp.hexdigest()


def write(state):
    rows, topics, wiki, entities, edges = state
    db_path().parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=db_path().parent, suffix=".db", delete=False) as file:
        temp = Path(file.name)
    try:
        with closing(sqlite3.connect(temp)) as conn, conn:
            conn.executescript(SCHEMA)
            conn.executemany("INSERT INTO item VALUES (" + ",".join("?" for _ in ITEM_FIELDS) + ")", (
                tuple(json.dumps(row[name], ensure_ascii=False) if name == "via" else row[name]
                      for name in ITEM_FIELDS) for row in rows.values()))
            conn.executemany("INSERT INTO search VALUES (?, ?, ?, ?, ?, ?)", (
                (key, row["clean_title"], row["scene"], row["excerpt"], row["topic"], " ".join(row["entities"]))
                for key, row in rows.items()))
            conn.executemany("INSERT INTO topic VALUES (?, ?, ?, ?, 0, ?, ?, ?)", (
                (key, row["name"], row.get("parent", ""), wiki.get(key, {}).get("fields", {}).get("summary", ""),
                 wiki.get(key, {}).get("fields", {}).get("updated", ""), wiki.get(key, {}).get("file", ""),
                 wiki.get(key, {}).get("owner", "ai"))
                for key, row in topics.items()))
            conn.execute("""
                WITH RECURSIVE counted(id, size) AS (
                    SELECT topic, count(*) FROM item
                    WHERE source <> 'github' AND status <> 'hidden' AND removed = '' GROUP BY topic
                    UNION ALL
                    SELECT topic.parent, counted.size FROM topic JOIN counted ON topic.id = counted.id
                    WHERE topic.parent <> ''
                ), totals(id, size) AS (SELECT id, sum(size) FROM counted GROUP BY id)
                UPDATE topic SET size = totals.size FROM totals WHERE topic.id = totals.id
            """)
            conn.executemany("INSERT INTO entity VALUES (?, ?, ?)", ((key, *value) for key, value in entities.items()))
            conn.executemany("INSERT INTO edge VALUES (?, ?, ?, ?)", ((*edge, by) for edge, by in edges.items()))
            conn.execute("INSERT INTO build VALUES (?)", (signature(),))
        os.replace(temp, db_path())
    except sqlite3.OperationalError as exc:
        if "fts5" in str(exc) or "trigram" in str(exc):
            raise lib.Error("当前 Python 的 SQLite 需要支持 FTS5 和 trigram") from exc
        raise
    finally:
        temp.unlink(missing_ok=True)


def connect():
    conn = sqlite3.connect(db_path().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def open_index():
    try:
        with closing(connect()) as conn:
            current = conn.execute("SELECT stamp FROM build").fetchone()
    except sqlite3.DatabaseError:
        current = None
    if current is None or current["stamp"] != signature():
        write(catalog.state())
    with closing(connect()) as conn:
        yield conn
