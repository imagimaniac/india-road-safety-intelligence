"""Local SQLite storage.

Design goals, adapted from ``~/Projects/unified-job-portal-automation/storage``:

* schema evolves **only** through the versioned, additive migrations below;
* every query is parameterised; identifiers are validated against the schema;
* records are append-only — history is preserved, nothing is silently deleted;
* the DB file (0600) and its directory (0700) are locked to the owner;
* a run log records per-source outcomes so a failure is never mistaken for
  "no data exists".

Tables are grouped by *evidence type*. Accident statistics, crash tests, recalls
and exposure figures live in separate tables and are never merged.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

SCHEMA_VERSION = 2

# All writable tables (guards against SQL-identifier injection).
TABLES: frozenset[str] = frozenset({
    "sources", "documents", "provenance", "accident_records",
    "vehicle_makes", "vehicle_models", "vehicle_generations", "vehicle_variants",
    "vehicle_aliases", "crash_tests", "recalls", "exposures", "run_log",
})

# Append-only tables get a content-uniqueness guard (idempotent re-ingest).
_UNIQUE_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("sources", "ux_sources_slug", "slug"),
    ("documents", "ux_documents_sha", "content_sha256"),
    ("vehicle_makes", "ux_makes_slug", "slug"),
    ("vehicle_models", "ux_models_slug", "slug"),
    ("vehicle_aliases", "ux_alias", "alias"),
)

_MIGRATIONS: dict[int, list[str]] = {
    1: [
        """
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            organization TEXT NOT NULL,
            url TEXT,
            access_method TEXT NOT NULL,
            data_type TEXT NOT NULL,
            jurisdiction TEXT,
            status TEXT NOT NULL DEFAULT 'pending_verification',
            coverage_json TEXT,
            licence TEXT,
            permitted_use TEXT,
            terms_url TEXT,
            attribution TEXT,
            verified_on TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_slug TEXT NOT NULL,
            url TEXT NOT NULL,
            title TEXT,
            doc_type TEXT,
            published_on TEXT,
            retrieved_at TEXT NOT NULL,
            content_sha256 TEXT,
            raw_path TEXT,
            meta_json TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS provenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            source_slug TEXT NOT NULL,
            source_url TEXT,
            document_id INTEGER,
            retrieved_at TEXT NOT NULL,
            method TEXT NOT NULL,
            http_status INTEGER,
            content_sha256 TEXT,
            note TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS accident_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            geography TEXT NOT NULL,
            geo_level TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER,
            road_type TEXT,
            road_user TEXT,
            severity TEXT NOT NULL,
            metric TEXT NOT NULL,
            value INTEGER,
            unit TEXT,
            source_slug TEXT NOT NULL,
            document_id INTEGER,
            evidence_class TEXT NOT NULL,
            confidence TEXT NOT NULL,
            content_hash TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS vehicle_makes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            parent TEXT,
            country TEXT,
            aliases_json TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS vehicle_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make_slug TEXT NOT NULL,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            body_style TEXT,
            segment TEXT,
            launch_year INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS vehicle_generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_slug TEXT NOT NULL,
            name TEXT NOT NULL,
            year_from INTEGER,
            year_to INTEGER,
            platform TEXT,
            structural_notes TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS vehicle_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generation_ref TEXT NOT NULL,
            name TEXT NOT NULL,
            model_year INTEGER,
            fuel TEXT,
            transmission TEXT,
            safety_equipment_json TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS vehicle_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL,
            canonical_type TEXT NOT NULL,
            canonical_id TEXT NOT NULL,
            confidence REAL,
            source_note TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS crash_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            variant_ref TEXT,
            make_slug TEXT,
            model_slug TEXT,
            program TEXT NOT NULL,
            protocol_version TEXT,
            test_date TEXT,
            market TEXT,
            adult_stars INTEGER,
            child_stars INTEGER,
            overall_stars INTEGER,
            adult_occupant_protection REAL,
            child_occupant_protection REAL,
            safety_assist REAL,
            equipment_tested TEXT,
            bodyshell TEXT,
            source_slug TEXT NOT NULL,
            document_id INTEGER,
            is_comparable INTEGER NOT NULL DEFAULT 0,
            evidence_class TEXT NOT NULL,
            confidence TEXT NOT NULL,
            content_hash TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS recalls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            make_slug TEXT NOT NULL,
            model_slug TEXT,
            year_range TEXT,
            defect TEXT NOT NULL,
            remedy TEXT,
            announced_on TEXT,
            source_slug TEXT,
            document_id INTEGER,
            confidence TEXT NOT NULL,
            content_hash TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS exposures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            geography TEXT NOT NULL,
            geo_level TEXT NOT NULL,
            year INTEGER NOT NULL,
            vehicle_category TEXT NOT NULL,
            metric TEXT NOT NULL,
            value INTEGER,
            unit TEXT,
            source_slug TEXT NOT NULL,
            document_id INTEGER,
            confidence TEXT NOT NULL,
            content_hash TEXT,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS run_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            source_slug TEXT,
            status TEXT NOT NULL,
            new_count INTEGER DEFAULT 0,
            updated_count INTEGER DEFAULT 0,
            unchanged_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            message TEXT
        )
        """,
        # Unique indexes (idempotent re-ingest by content, not by position).
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_sources_slug ON sources(slug)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_documents_sha ON documents(content_sha256) WHERE content_sha256 IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_makes_slug ON vehicle_makes(slug)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_models_slug ON vehicle_models(slug)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_alias ON vehicle_aliases(alias)",
        # Content guards for append-only fact tables.
        "CREATE INDEX IF NOT EXISTS ix_accident_content ON accident_records(content_hash)",
        "CREATE INDEX IF NOT EXISTS ix_crashtest_content ON crash_tests(content_hash)",
        "CREATE INDEX IF NOT EXISTS ix_recalls_content ON recalls(content_hash)",
        "CREATE INDEX IF NOT EXISTS ix_exposures_content ON exposures(content_hash)",
    ],
    # v2: a free-text label so a record can name the dimension it belongs to
    # (collision type, time interval, safety device, month) without overloading
    # the road_type/road_user columns. Purely additive.
    2: [
        "ALTER TABLE accident_records ADD COLUMN label TEXT",
        "CREATE INDEX IF NOT EXISTS ix_accident_label ON accident_records(label)",
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _secure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass


def _secure_file(path: Path) -> None:
    if path.exists():
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


class Store:
    """A thin, validated wrapper around a SQLite database."""

    def __init__(self, path: str | os.PathLike[str], create: bool = True):
        self.path = Path(path)
        if create:
            _secure_dir(self.path.parent)
        elif not self.path.exists():
            raise FileNotFoundError(f"database not found: {self.path}")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()
        _secure_file(self.path)

    # -- schema ------------------------------------------------------------ #
    def migrate(self) -> int:
        """Apply pending migrations. Returns the resulting schema version."""
        with self.connect() as conn:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            for version in sorted(_MIGRATIONS):
                if version <= current:
                    continue
                for stmt in _MIGRATIONS[version]:
                    conn.execute(stmt)
                conn.execute(f"PRAGMA user_version = {int(version)}")
                current = version
            conn.commit()
        _secure_file(self.path)
        return current

    def schema_version(self) -> int:
        with self.connect() as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def _columns(self, conn: sqlite3.Connection, table: str) -> list[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r["name"] for r in rows]

    # -- writes ------------------------------------------------------------ #
    def insert(self, table: str, row: dict[str, Any]) -> int:
        """Insert one row. Unknown tables/columns are rejected (injection-safe)."""
        if table not in TABLES:
            raise ValueError(f"unknown table: {table!r}")
        with self.connect() as conn:
            cols = self._columns(conn, table)
            payload = {k: _coerce(v) for k, v in row.items() if k in cols}
            if not payload:
                raise ValueError(f"no valid columns for table {table!r}")
            if "created_at" in cols:
                payload.setdefault("created_at", _now())
            names = ", ".join(payload)
            placeholders = ", ".join("?" for _ in payload)
            cur = conn.execute(
                f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
                list(payload.values()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def insert_many(self, table: str, rows: list[dict[str, Any]]) -> int:
        count = 0
        for row in rows:
            self.insert(table, row)
            count += 1
        return count

    def upsert_source(self, row: dict[str, Any]) -> int:
        """Insert or update a source keyed by ``slug`` (keeps id stable)."""
        if "slug" not in row:
            raise ValueError("source row requires 'slug'")
        with self.connect() as conn:
            cols = self._columns(conn, "sources")
            payload = {k: _coerce(v) for k, v in row.items() if k in cols}
            payload.setdefault("created_at", _now())
            existing = conn.execute(
                "SELECT id FROM sources WHERE slug = ?", (row["slug"],)
            ).fetchone()
            if existing:
                updates = {k: v for k, v in payload.items() if k != "created_at"}
                assignments = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE sources SET {assignments} WHERE slug = ?",
                    [*updates.values(), row["slug"]],
                )
                conn.commit()
                return int(existing["id"])
            names = ", ".join(payload)
            placeholders = ", ".join("?" for _ in payload)
            cur = conn.execute(
                f"INSERT INTO sources ({names}) VALUES ({placeholders})",
                list(payload.values()),
            )
            conn.commit()
            return int(cur.lastrowid)

    def record_run(
        self,
        source_slug: Optional[str],
        status: str,
        new_count: int = 0,
        updated_count: int = 0,
        unchanged_count: int = 0,
        error_count: int = 0,
        message: Optional[str] = None,
    ) -> int:
        return self.insert("run_log", {
            "run_at": _now(),
            "source_slug": source_slug,
            "status": status,
            "new_count": new_count,
            "updated_count": updated_count,
            "unchanged_count": unchanged_count,
            "error_count": error_count,
            "message": message,
        })

    def exists_by_hash(self, table: str, content_hash: str) -> bool:
        if table not in TABLES:
            raise ValueError(f"unknown table: {table!r}")
        with self.connect() as conn:
            cols = self._columns(conn, table)
            if "content_hash" not in cols:
                raise ValueError(f"table {table!r} has no content_hash column")
            row = conn.execute(
                f"SELECT 1 FROM {table} WHERE content_hash = ? LIMIT 1", (content_hash,)
            ).fetchone()
            return row is not None

    # -- reads ------------------------------------------------------------- #
    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def count(self, table: str) -> int:
        if table not in TABLES:
            raise ValueError(f"unknown table: {table!r}")
        with self.connect() as conn:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _coerce(value: Any) -> Any:
    """SQLite only stores str/int/float/bytes/None. Serialise the rest to JSON."""
    if value is None or isinstance(value, (str, int, float, bytes)):
        return value
    if isinstance(value, bool):
        return int(value)
    if hasattr(value, "value"):  # Enum
        return value.value
    if hasattr(value, "isoformat"):  # date/datetime
        return value.isoformat()
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
