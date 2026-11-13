"""Unified SQLite-backed research state kernel (Occam edition, hardened).

Delegates relational, foreign-key, append-only, savepoint, and recursive-DAG
invariants to CPython's built-in C ``sqlite3`` engine (with ``PRAGMA
recursive_triggers = ON``, ``STRICT`` tables, cycle triggers, and monotonic CAS
watcher state), paired with strict semantic/schema admission at the API boundary.
"""
from __future__ import annotations

import collections.abc
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Iterable, Iterator, Mapping, Optional

from ._stdlib import (
    ARK_SQLITE_APP_ID,
    ARK_SQLITE_USER_VERSION,
    _SQLITE_INIT_LOCK,
    canonical_json,
    configure_sqlite_connection,
    freeze,
    nfc_compact,
    normalize_doi,
    run_with_sqlite_retry,
    safe_path,
    sha256_hex,
    thaw,
    validate_schema,
    verify_or_claim_sqlite_identity,
)

ALLOWED_ARTIFACT_KINDS: frozenset[str] = frozenset({
    "data_snapshot",
    "research_object",
    "research_documents",
    "lineage_receipt",
    "paper_extraction",
    "paper_comparison",
    "computed_evidence",
    "reproduction_receipt",
    "literature_delta",
    "retraction_delta",
    "systematic_review",
    "source",
    "table_cell",
    "statistic_artifact",
})

KIND_SCHEMA_MAP: Mapping[str, str] = {
    "research_object": "research-object.schema.json",
    "research_documents": "research-documents.schema.json",
    "paper_extraction": "paper-extraction.schema.json",
    "paper_comparison": "paper-comparison.schema.json",
}

ALLOWED_LINEAGE_RELATIONS: frozenset[str] = frozenset({
    "derived_from",
    "extracted_from",
    "recomputed_from",
    "verified_by",
})

ALLOWED_CLAIM_STATUSES: frozenset[str] = frozenset({"supported", "contested", "unresolved", "refuted"})
ALLOWED_EVIDENCE_STANCES: frozenset[str] = frozenset({"supports", "contradicts", "qualifies"})
ALLOWED_CLAIM_RELATIONS: frozenset[str] = frozenset({"depends_on", "refines", "contradicts"})

PRUNE_REASONS: frozenset[str] = frozenset({
    "resource_exhausted",
    "superseded",
    "contradicted",
    "out_of_scope",
    "duplicate",
    "external_constraint",
    "investigator_error",
    "other",
})
REOPEN_REASONS: frozenset[str] = frozenset({
    "new_evidence",
    "scope_change",
    "investigator_reconsideration",
    "error_correction",
    "other",
})

_VALID_TRANSITIONS: Mapping[Optional[str], frozenset[str]] = {
    None: frozenset({"active", "pruned"}),
    "active": frozenset({"pruned"}),
    "pruned": frozenset({"reopened"}),
    "reopened": frozenset({"pruned"}),
}

SCHEMA_SQL = f"""
PRAGMA application_id = {ARK_SQLITE_APP_ID};
PRAGMA user_version = {ARK_SQLITE_USER_VERSION};

CREATE TABLE IF NOT EXISTS works (
    work_id TEXT PRIMARY KEY CHECK (length(trim(work_id)) > 0),
    doi TEXT,
    arxiv_id TEXT,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    year INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{{}}'
) STRICT;

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY CHECK (length(trim(artifact_id)) > 0),
    kind TEXT NOT NULL CHECK (length(trim(kind)) > 0),
    payload_json TEXT NOT NULL CHECK (length(payload_json) >= 2),
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*')
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_artifacts_immutable_upd
BEFORE UPDATE ON artifacts
BEGIN
    SELECT RAISE(ABORT, 'artifacts table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_artifacts_immutable_del
BEFORE DELETE ON artifacts
BEGIN
    SELECT RAISE(ABORT, 'artifacts table is append-only');
END;

CREATE TABLE IF NOT EXISTS lineage_edges (
    child_id TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK (relation IN ('derived_from', 'extracted_from', 'recomputed_from', 'verified_by')),
    CHECK (child_id != parent_id),
    PRIMARY KEY (child_id, parent_id, relation),
    FOREIGN KEY (child_id) REFERENCES artifacts(artifact_id),
    FOREIGN KEY (parent_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_lineage_child ON lineage_edges(child_id);
CREATE INDEX IF NOT EXISTS idx_lineage_parent ON lineage_edges(parent_id);

CREATE TRIGGER IF NOT EXISTS trg_lineage_no_cycle
BEFORE INSERT ON lineage_edges
BEGIN
    SELECT CASE WHEN EXISTS (
        WITH RECURSIVE reach(node) AS (
            SELECT NEW.parent_id
            UNION
            SELECT e.parent_id FROM lineage_edges e JOIN reach r ON e.child_id = r.node
        )
        SELECT 1 FROM reach WHERE node = NEW.child_id
    ) THEN RAISE(ABORT, 'Cycle detected in lineage_edges') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_lineage_immutable_upd
BEFORE UPDATE ON lineage_edges
BEGIN
    SELECT RAISE(ABORT, 'lineage_edges table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_lineage_immutable_del
BEFORE DELETE ON lineage_edges
BEGIN
    SELECT RAISE(ABORT, 'lineage_edges table is append-only');
END;

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY CHECK (length(trim(claim_id)) > 0),
    claim_text TEXT NOT NULL CHECK (length(trim(claim_text)) > 0),
    claim_digest TEXT NOT NULL CHECK (length(claim_digest) = 64 AND claim_digest NOT GLOB '*[^0-9a-f]*'),
    status TEXT NOT NULL DEFAULT 'unresolved' CHECK (status IN ('supported', 'contested', 'unresolved', 'refuted')),
    metadata_json TEXT NOT NULL DEFAULT '{{}}'
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_claims_text_immutable_upd
BEFORE UPDATE ON claims
WHEN OLD.claim_id != NEW.claim_id OR OLD.claim_text != NEW.claim_text OR OLD.claim_digest != NEW.claim_digest
BEGIN
    SELECT RAISE(ABORT, 'claim identity, text, and digest are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_claims_immutable_del
BEFORE DELETE ON claims
BEGIN
    SELECT RAISE(ABORT, 'claims table is append-only');
END;

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    stance TEXT NOT NULL DEFAULT 'supports' CHECK (stance IN ('supports', 'contradicts', 'qualifies')),
    locator TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (claim_id, artifact_id, locator),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_claim_evidence_immutable_upd
BEFORE UPDATE ON claim_evidence
BEGIN
    SELECT RAISE(ABORT, 'claim_evidence table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_claim_evidence_immutable_del
BEFORE DELETE ON claim_evidence
BEGIN
    SELECT RAISE(ABORT, 'claim_evidence table is append-only');
END;

CREATE TABLE IF NOT EXISTS claim_edges (
    src_claim_id TEXT NOT NULL,
    dst_claim_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK (relation IN ('depends_on', 'refines', 'contradicts', 'corroborates', 'cites')),
    CHECK (src_claim_id != dst_claim_id),
    PRIMARY KEY (src_claim_id, dst_claim_id, relation),
    FOREIGN KEY (src_claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (dst_claim_id) REFERENCES claims(claim_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_claim_edges_no_cycle
BEFORE INSERT ON claim_edges
WHEN NEW.relation IN ('depends_on', 'refines')
BEGIN
    SELECT CASE WHEN EXISTS (
        WITH RECURSIVE reach(node) AS (
            SELECT NEW.dst_claim_id
            UNION
            SELECT e.dst_claim_id FROM claim_edges e
            JOIN reach r ON e.src_claim_id = r.node
            WHERE e.relation IN ('depends_on', 'refines')
        )
        SELECT 1 FROM reach WHERE node = NEW.src_claim_id
    ) THEN RAISE(ABORT, 'Cycle detected in claim_edges') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_claim_edges_immutable_upd
BEFORE UPDATE ON claim_edges
BEGIN
    SELECT RAISE(ABORT, 'claim_edges table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_claim_edges_immutable_del
BEFORE DELETE ON claim_edges
BEGIN
    SELECT RAISE(ABORT, 'claim_edges table is append-only');
END;

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY CHECK (length(trim(decision_id)) > 0),
    entry_kind TEXT NOT NULL CHECK (entry_kind IN ('decision', 'negative_result')),
    action TEXT NOT NULL CHECK (action IN ('explore', 'commit', 'abandon', 'revise', 'negative_result')),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0 AND length(title) <= 512),
    verdict TEXT NOT NULL DEFAULT 'inconclusive' CHECK (verdict IN ('positive', 'negative', 'inconclusive', 'unverifiable')),
    basis_decision_id TEXT,
    artifact_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{{}}',
    CHECK (
        (entry_kind = 'negative_result' AND action = 'negative_result' AND basis_decision_id IS NOT NULL AND basis_decision_id != decision_id)
        OR (entry_kind = 'decision' AND action != 'negative_result')
    ),
    FOREIGN KEY (basis_decision_id) REFERENCES decisions(decision_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_decisions_basis_check
BEFORE INSERT ON decisions
WHEN NEW.entry_kind = 'negative_result'
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM decisions WHERE decision_id = NEW.basis_decision_id AND entry_kind = 'decision'
    ) THEN RAISE(ABORT, 'negative_result basis must reference an existing non-negative decision') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_decisions_immutable_upd
BEFORE UPDATE ON decisions
BEGIN
    SELECT RAISE(ABORT, 'decisions table is append-only; record changes via decision_events');
END;

CREATE TRIGGER IF NOT EXISTS trg_decisions_immutable_del
BEFORE DELETE ON decisions
BEGIN
    SELECT RAISE(ABORT, 'decisions table is append-only');
END;

CREATE TABLE IF NOT EXISTS decision_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    new_state TEXT NOT NULL CHECK (new_state IN ('active', 'pruned', 'reopened')),
    reason TEXT NOT NULL CHECK (
        reason IN (
            'genesis', 'resource_exhausted', 'superseded', 'contradicted',
            'out_of_scope', 'duplicate', 'external_constraint', 'investigator_error',
            'new_evidence', 'scope_change', 'investigator_reconsideration', 'error_correction', 'other'
        )
    ),
    superseded_by_id TEXT,
    verdict_override TEXT CHECK (verdict_override IS NULL OR verdict_override IN ('positive', 'negative', 'inconclusive', 'unverifiable')),
    FOREIGN KEY (decision_id) REFERENCES decisions(decision_id),
    FOREIGN KEY (superseded_by_id) REFERENCES decisions(decision_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_decision_events_immutable_upd
BEFORE UPDATE ON decision_events
BEGIN
    SELECT RAISE(ABORT, 'decision_events log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_decision_events_immutable_del
BEFORE DELETE ON decision_events
BEGIN
    SELECT RAISE(ABORT, 'decision_events log is append-only');
END;

CREATE TABLE IF NOT EXISTS decision_corrections (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('positive', 'negative', 'inconclusive', 'unverifiable')),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) > 0 AND length(rationale) <= 4096),
    artifact_id TEXT,
    FOREIGN KEY (decision_id) REFERENCES decisions(decision_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_decision_corrections_immutable_upd
BEFORE UPDATE ON decision_corrections
BEGIN
    SELECT RAISE(ABORT, 'decision_corrections log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_decision_corrections_immutable_del
BEFORE DELETE ON decision_corrections
BEGIN
    SELECT RAISE(ABORT, 'decision_corrections log is append-only');
END;

CREATE TABLE IF NOT EXISTS doi_watch_state (
    watcher TEXT NOT NULL CHECK (length(trim(watcher)) > 0),
    item_key TEXT NOT NULL CHECK (length(trim(item_key)) > 0),
    current_status TEXT NOT NULL DEFAULT 'unknown' CHECK (current_status IN ('retracted', 'not_retracted', 'unknown')),
    confirmed_retracted INTEGER CHECK (confirmed_retracted IS NULL OR confirmed_retracted IN (0, 1)),
    signals_json TEXT NOT NULL DEFAULT '[]',
    reserved_seq INTEGER NOT NULL DEFAULT 0 CHECK (reserved_seq >= 0),
    applied_seq INTEGER NOT NULL DEFAULT 0 CHECK (applied_seq >= 0),
    confirmed_seq INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_seq >= 0),
    observation_version INTEGER NOT NULL DEFAULT 0 CHECK (observation_version >= 0),
    truncated INTEGER NOT NULL DEFAULT 0 CHECK (truncated IN (0, 1)),
    last_error TEXT,
    unacked_delta_json TEXT,
    PRIMARY KEY (watcher, item_key)
) STRICT;

CREATE TABLE IF NOT EXISTS doi_watch_commits (
    watcher TEXT NOT NULL CHECK (length(trim(watcher)) > 0),
    item_key TEXT NOT NULL CHECK (length(trim(item_key)) > 0),
    seq INTEGER NOT NULL CHECK (seq >= 1),
    commit_digest TEXT NOT NULL CHECK (length(commit_digest) = 64 AND commit_digest NOT GLOB '*[^0-9a-f]*'),
    snapshot_json TEXT NOT NULL CHECK (length(snapshot_json) >= 2),
    PRIMARY KEY (watcher, item_key, seq)
) STRICT;
"""


def _require_str_id(value: Any, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str, got {type(value).__name__}: {value!r}")
    if "\r" in value or "\n" in value or "\x00" in value:
        raise ValueError(f"{field_name} must not contain control/newline characters: {value!r}")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must be a non-empty string")
    return cleaned


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, collections.abc.Mapping):
        raise TypeError(f"{field_name} must be a JSON object/mapping, got {type(value).__name__}")
    return value


class ResearchStateDB:
    """Single-file ACID research ledger, claim-evidence graph, provenance DAG, and watcher store."""

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        *,
        readonly: bool = False,
        root: Optional[str | Path] = None,
    ) -> None:
        self.readonly = bool(readonly)
        self.root = Path(root) if root is not None else None
        raw_path = str(db_path)
        if raw_path == ":memory:":
            if self.readonly:
                raise ValueError("Cannot open transient ':memory:' database in read-only mode")
            self.db_path = ":memory:"
            self._resolved_path: Optional[Path] = None
        else:
            self._resolved_path = safe_path(raw_path, root=self.root)
            self.db_path = str(self._resolved_path)

        self._lock = threading.RLock()
        self._tls = threading.local()
        self._conns: list[sqlite3.Connection] = []
        self._closed = False
        self._mem_conn: Optional[sqlite3.Connection] = None

        if self.db_path == ":memory:":
            conn = sqlite3.connect(":memory:", timeout=10.0, isolation_level=None)
            configure_sqlite_connection(conn, readonly=False)
            conn.executescript(SCHEMA_SQL)
            self._mem_conn = conn
        elif self.readonly:
            # Verify database exists and carries ARK3 identity immediately without mutating anything
            conn = self._get_conn()
            assert conn is not None
        else:
            assert self._resolved_path is not None
            self._resolved_path.parent.mkdir(parents=True, exist_ok=True)
            self._resolved_path = safe_path(self._resolved_path, root=self.root)
            self.db_path = str(self._resolved_path)

            def _cold_init() -> None:
                with _SQLITE_INIT_LOCK:
                    conn = self._get_conn()
                    verify_or_claim_sqlite_identity(conn, readonly=False)
                    cur_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                    if cur_mode != "wal":
                        conn.execute("PRAGMA journal_mode = WAL")
                    conn.execute("PRAGMA synchronous = NORMAL")
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        stmt_buf = ""
                        for raw_line in SCHEMA_SQL.splitlines(keepends=True):
                            if not stmt_buf.strip() and (not raw_line.strip() or raw_line.lstrip().startswith("--")):
                                continue
                            stmt_buf += raw_line
                            if sqlite3.complete_statement(stmt_buf):
                                conn.execute(stmt_buf)
                                stmt_buf = ""
                        if stmt_buf.strip():
                            conn.execute(stmt_buf)
                        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(doi_watch_state)").fetchall()}
                        if "confirmed_seq" not in cols:
                            conn.execute("ALTER TABLE doi_watch_state ADD COLUMN confirmed_seq INTEGER NOT NULL DEFAULT 0")
                            conn.execute(
                                "UPDATE doi_watch_state SET confirmed_seq = applied_seq WHERE confirmed_retracted IS NOT NULL AND confirmed_seq = 0"
                            )
                        conn.execute("COMMIT")
                    except BaseException:
                        if conn.in_transaction:
                            conn.execute("ROLLBACK")
                        raise

            run_with_sqlite_retry(_cold_init)

    def __enter__(self) -> "ResearchStateDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _get_conn(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("ResearchStateDB is closed")
        if self._mem_conn is not None:
            configure_sqlite_connection(self._mem_conn, readonly=False)
            return self._mem_conn
        conn = getattr(self._tls, "conn", None)
        if conn is not None:
            configure_sqlite_connection(conn, readonly=self.readonly)
            return conn
        assert self._resolved_path is not None
        checked = safe_path(self._resolved_path, root=self.root)
        if self.readonly:
            if not checked.is_file():
                raise FileNotFoundError(f"Research state database not found: {checked}")
            conn = sqlite3.connect(checked.as_uri() + "?mode=ro", uri=True, timeout=10.0, isolation_level=None)
            try:
                configure_sqlite_connection(conn, readonly=True)
                verify_or_claim_sqlite_identity(conn, readonly=True)
            except BaseException:
                conn.close()
                raise
        else:
            conn = sqlite3.connect(str(checked), timeout=10.0, isolation_level=None)
            try:
                configure_sqlite_connection(conn, readonly=False)
                conn.execute("PRAGMA synchronous = NORMAL")
            except BaseException:
                conn.close()
                raise
        with self._lock:
            self._conns.append(conn)
        self._tls.conn = conn
        return conn

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if self._mem_conn is not None:
                self._mem_conn.close()
                self._mem_conn = None
            for c in self._conns:
                try:
                    c.close()
                except Exception:
                    pass
            self._conns.clear()
            if hasattr(self._tls, "conn"):
                delattr(self._tls, "conn")

    def _tx_depth(self) -> int:
        return int(getattr(self._tls, "tx_depth", 0))

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Explicit reentrant write unit-of-work; nested calls use SQLite SAVEPOINTs."""
        if self.readonly:
            raise PermissionError("Cannot start a write transaction on a read-only ResearchStateDB")
        conn = self._get_conn()
        depth = self._tx_depth()
        if depth == 0:
            run_with_sqlite_retry(lambda: conn.execute("BEGIN IMMEDIATE"))
            self._tls.tx_depth = 1
            try:
                yield conn
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            finally:
                self._tls.tx_depth = 0
        else:
            sp = f"uow_sp_{depth}"
            conn.execute(f"SAVEPOINT {sp}")
            self._tls.tx_depth = depth + 1
            try:
                yield conn
                conn.execute(f"RELEASE SAVEPOINT {sp}")
            except BaseException:
                conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                conn.execute(f"RELEASE SAVEPOINT {sp}")
                raise
            finally:
                self._tls.tx_depth = depth

    @contextmanager
    def _read_snapshot(self) -> Iterator[sqlite3.Connection]:
        """Consistent MVCC read transaction preventing torn reads across multi-table SELECTs."""
        conn = self._get_conn()
        if conn.in_transaction or self._tx_depth() > 0:
            yield conn
            return
        conn.execute("BEGIN DEFERRED")
        try:
            yield conn
        finally:
            if conn.in_transaction:
                conn.execute("COMMIT")

    @staticmethod
    def _assert_acyclic(conn: sqlite3.Connection, table: str, src_col: str, dst_col: str, start: str, target: str) -> None:
        if start == target:
            raise ValueError(f"Self-loop rejected in {table}: {start!r}")
        row = conn.execute(
            f"""
            WITH RECURSIVE reach(node) AS (
                SELECT ?
                UNION
                SELECT e.{dst_col} FROM {table} e JOIN reach r ON e.{src_col} = r.node
            )
            SELECT 1 FROM reach WHERE node = ? LIMIT 1
            """,
            (target, start),
        ).fetchone()
        if row is not None:
            raise ValueError(f"Cycle detected in {table}: adding {start!r} -> {target!r} creates a loop")

    @staticmethod
    def _validate_artifact_semantics(
        artifact_id: Any,
        kind: Any,
        payload: Any,
        expected_sha256: Optional[str] = None,
    ) -> tuple[str, str, str, str]:
        aid = _require_str_id(artifact_id, "artifact_id")
        k = _require_str_id(kind, "kind")
        if k not in ALLOWED_ARTIFACT_KINDS:
            raise ValueError(f"Unknown artifact kind {k!r}; allowed={sorted(ALLOWED_ARTIFACT_KINDS)}")
        pmap = _require_mapping(payload, "payload")
        plain_payload = thaw(pmap)
        schema_file = KIND_SCHEMA_MAP.get(k)
        if schema_file is not None:
            errs = validate_schema(plain_payload, schema_file)
            if errs:
                raise ValueError(f"Schema validation failed for {k} ({aid}): {'; '.join(errs[:5])}")
        cjson = canonical_json(plain_payload)
        digest = sha256_hex(cjson)
        if expected_sha256 is not None:
            exp = _require_str_id(expected_sha256, "payload_sha256").lower()
            if exp != digest:
                raise ValueError(f"Payload SHA-256 mismatch on {aid!r}: expected {exp}, computed {digest}")
        return aid, k, cjson, digest

    def _admit_artifact_in_tx(
        self,
        conn: sqlite3.Connection,
        artifact_id: Any,
        kind: Any,
        payload: Any,
        *,
        expected_sha256: Optional[str] = None,
        parents: Iterable[Any] = (),
        relation: Any = "derived_from",
    ) -> Mapping[str, Any]:
        aid, k, cjson, digest = self._validate_artifact_semantics(artifact_id, kind, payload, expected_sha256)
        rel = _require_str_id(relation, "relation")
        if rel not in ALLOWED_LINEAGE_RELATIONS:
            raise ValueError(f"Invalid lineage relation {rel!r}; allowed={sorted(ALLOWED_LINEAGE_RELATIONS)}")
        parent_ids = [_require_str_id(pid, "parent_id") for pid in parents]

        existing = conn.execute(
            "SELECT payload_sha256, kind FROM artifacts WHERE artifact_id = ?", (aid,)
        ).fetchone()
        replayed = existing is not None
        if existing is not None:
            if existing["payload_sha256"] != digest or existing["kind"] != k:
                raise ValueError(
                    f"Artifact collision for {aid!r}: stored kind={existing['kind']!r}/sha={existing['payload_sha256'][:12]} "
                    f"vs incoming kind={k!r}/sha={digest[:12]}"
                )
        else:
            conn.execute(
                "INSERT INTO artifacts (artifact_id, kind, payload_json, payload_sha256) VALUES (?, ?, ?, ?)",
                (aid, k, cjson, digest),
            )

        for pid in parent_ids:
            self._assert_acyclic(conn, "lineage_edges", "child_id", "parent_id", aid, pid)
            conn.execute(
                """
                INSERT INTO lineage_edges (child_id, parent_id, relation)
                VALUES (?, ?, ?)
                ON CONFLICT(child_id, parent_id, relation) DO NOTHING
                """,
                (aid, pid, rel),
            )
        return freeze({
            "artifact_id": aid,
            "kind": k,
            "status": "accepted",
            "replayed": replayed,
            "payload_sha256": digest,
        })

    def register_work(
        self,
        work_id: str,
        title: str,
        *,
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
        year: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        wid = _require_str_id(work_id, "work_id")
        clean_title = nfc_compact(_require_str_id(title, "title"))
        norm_doi = normalize_doi(doi) if doi else None
        norm_arxiv = str(arxiv_id).strip().lower() if arxiv_id else None
        if year is not None and (type(year) is not int):
            raise TypeError("year must be int or None")
        meta_json = canonical_json(metadata or {})

        with self.transaction() as conn:
            existing = conn.execute("SELECT title, doi, arxiv_id FROM works WHERE work_id = ?", (wid,)).fetchone()
            if existing is not None:
                if existing["title"] != clean_title or existing["doi"] != norm_doi or existing["arxiv_id"] != norm_arxiv:
                    raise ValueError(f"Conflicting work registration for {wid!r}")
            else:
                conn.execute(
                    "INSERT INTO works (work_id, doi, arxiv_id, title, year, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (wid, norm_doi, norm_arxiv, clean_title, year, meta_json),
                )
        return freeze({"work_id": wid, "title": clean_title, "doi": norm_doi, "arxiv_id": norm_arxiv})

    def register_artifact(self, artifact_id: str, kind: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        with self.transaction() as conn:
            return self._admit_artifact_in_tx(conn, artifact_id, kind, payload)

    def batch_ingest(self, items: Iterable[Mapping[str, Any]], atomic: bool = True) -> tuple[Mapping[str, Any], ...]:
        if type(atomic) is not bool:
            raise TypeError(f"atomic must be bool, got {type(atomic).__name__}")
        batch = list(items)
        out: list[Mapping[str, Any]] = []
        with self.transaction() as conn:
            for idx, item in enumerate(batch):
                if not isinstance(item, collections.abc.Mapping):
                    if atomic:
                        raise TypeError(f"items[{idx}] must be an object/mapping")
                    out.append(freeze({"artifact_id": "", "status": "rejected", "error": "item must be an object/mapping"}))
                    continue
                sp = f"batch_sp_{idx}"
                conn.execute(f"SAVEPOINT {sp}")
                try:
                    rec = self._admit_artifact_in_tx(
                        conn,
                        item.get("artifact_id"),
                        item.get("kind"),
                        item.get("payload"),
                        expected_sha256=item.get("payload_sha256"),
                        parents=item.get("parents") or (),
                        relation=item.get("relation", "derived_from"),
                    )
                    conn.execute(f"RELEASE SAVEPOINT {sp}")
                    out.append(rec)
                except Exception as exc:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                    conn.execute(f"RELEASE SAVEPOINT {sp}")
                    if atomic:
                        raise
                    raw_id = item.get("artifact_id")
                    safe_id = raw_id if type(raw_id) is str else ""
                    out.append(freeze({"artifact_id": safe_id, "status": "rejected", "error": str(exc)}))
        return tuple(out)

    def trace_lineage(self, artifact_id: str, *, max_vm_steps: int = 500_000) -> tuple[str, ...]:
        aid = _require_str_id(artifact_id, "artifact_id")
        with self._read_snapshot() as conn:
            steps = 0

            def _budget() -> int:
                nonlocal steps
                steps += 1
                return 1 if steps > max_vm_steps else 0

            conn.set_progress_handler(_budget, 1000)
            try:
                rows = conn.execute(
                    """
                    WITH RECURSIVE anc(id) AS (
                        SELECT parent_id FROM lineage_edges WHERE child_id = ?
                        UNION
                        SELECT e.parent_id FROM lineage_edges e JOIN anc a ON e.child_id = a.id
                    )
                    SELECT id FROM anc ORDER BY id
                    """,
                    (aid,),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "interrupted" in str(exc).lower():
                    raise RuntimeError(f"Lineage trace exceeded VM step budget for {aid!r}") from exc
                raise
            finally:
                conn.set_progress_handler(None, 0)
            return tuple(str(r["id"]) for r in rows)

    def trace_lineage_verified(self, artifact_id: str, *, max_vm_steps: int = 500_000) -> dict[str, Any]:
        """Trace ancestor DAG and verify stored payload SHA-256 integrity across target and all ancestors."""
        aid = _require_str_id(artifact_id, "artifact_id")
        ancestors = self.trace_lineage(aid, max_vm_steps=max_vm_steps)
        all_nodes = (aid, *ancestors)
        with self._read_snapshot() as conn:
            art_rows = {
                str(r["artifact_id"]): (str(r["payload_json"]), str(r["payload_sha256"]))
                for r in conn.execute(
                    f"SELECT artifact_id, payload_json, payload_sha256 FROM artifacts WHERE artifact_id IN ({','.join('?' for _ in all_nodes)})",
                    all_nodes,
                ).fetchall()
            }
            if aid not in art_rows:
                return {
                    "artifact_id": aid,
                    "ancestors": list(ancestors),
                    "root_ancestors": [],
                    "chain_length": 0,
                    "verification_status": "missing_input",
                }
            edge_rows = conn.execute(
                f"SELECT child_id, parent_id FROM lineage_edges WHERE child_id IN ({','.join('?' for _ in all_nodes)})",
                all_nodes,
            ).fetchall()

        parents_map: dict[str, list[str]] = {n: [] for n in all_nodes}
        for er in edge_rows:
            c_id, p_id = str(er["child_id"]), str(er["parent_id"])
            if c_id in parents_map:
                parents_map[c_id].append(p_id)

        missing_any = any(n not in art_rows for n in all_nodes)
        corrupted_any = False
        for n in all_nodes:
            if n in art_rows:
                p_json, p_sha = art_rows[n]
                if sha256_hex(p_json) != p_sha.lower():
                    corrupted_any = True
                    break

        if corrupted_any:
            v_status = "corrupted"
        elif missing_any:
            v_status = "missing_input"
        else:
            v_status = "intact"

        roots = sorted(n for n in ancestors if not parents_map.get(n))
        memo_depth: dict[str, int] = {}

        def _depth(node: str, visiting: set[str]) -> int:
            if node in memo_depth:
                return memo_depth[node]
            ps = parents_map.get(node) or []
            if not ps:
                memo_depth[node] = 0
                return 0
            best = 0
            for p in ps:
                if p not in visiting:
                    best = max(best, 1 + _depth(p, visiting | {p}))
            memo_depth[node] = best
            return best

        chain_len = _depth(aid, {aid})
        return {
            "artifact_id": aid,
            "ancestors": list(ancestors),
            "root_ancestors": roots,
            "chain_length": chain_len,
            "verification_status": v_status,
        }

    def add_claim(
        self,
        claim_id: str,
        claim_text: str,
        status: Optional[str] = None,
        evidence: Iterable[tuple[str, str, str]] = (),
        depends_on: Iterable[str] = (),
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        cid = _require_str_id(claim_id, "claim_id")
        if type(claim_text) is not str or not nfc_compact(claim_text):
            raise ValueError("claim_text must be a non-empty string")
        norm = nfc_compact(claim_text)
        digest = sha256_hex(norm)
        ev_list: list[tuple[str, str, str]] = []
        for idx, tup in enumerate(evidence):
            if not isinstance(tup, (list, tuple)) or len(tup) != 3:
                raise ValueError(f"evidence[{idx}] must be a 3-tuple (artifact_id, stance, locator)")
            ev_aid = _require_str_id(tup[0], f"evidence[{idx}].artifact_id")
            ev_stance = _require_str_id(tup[1], f"evidence[{idx}].stance")
            if ev_stance not in ALLOWED_EVIDENCE_STANCES:
                raise ValueError(f"Invalid evidence stance {ev_stance!r}")
            if type(tup[2]) is not str:
                raise TypeError(f"evidence[{idx}].locator must be str")
            ev_list.append((ev_aid, ev_stance, tup[2]))

        dep_list = [_require_str_id(d, "depends_on") for d in depends_on]
        meta_json = canonical_json(metadata or {})

        if status is None:
            has_contra = any(st == "contradicts" for _, st, _ in ev_list)
            has_supp = any(st == "supports" for _, st, _ in ev_list)
            if has_contra and has_supp:
                resolved_status = "contested"
            elif has_contra:
                resolved_status = "refuted"
            elif has_supp:
                resolved_status = "supported"
            else:
                resolved_status = "unresolved"
        else:
            resolved_status = _require_str_id(status, "status")
            if resolved_status not in ALLOWED_CLAIM_STATUSES:
                raise ValueError(f"Invalid claim status {resolved_status!r}")
            if resolved_status == "supported" and not any(st == "supports" for _, st, _ in ev_list):
                # Check if existing claim already has supporting evidence in DB before allowing supported
                pass

        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT claim_text, claim_digest, status FROM claims WHERE claim_id = ?", (cid,)
            ).fetchone()
            if existing is not None:
                if existing["claim_digest"] != digest:
                    raise ValueError(
                        f"Immutable claim collision for {cid!r}: cannot overwrite existing claim text {existing['claim_text']!r}"
                    )
                if status is not None and existing["status"] != resolved_status:
                    raise ValueError(
                        f"Conflicting status registration for {cid!r}: stored={existing['status']!r} vs incoming={resolved_status!r}"
                    )
            else:
                if resolved_status == "supported" and not any(st == "supports" for _, st, _ in ev_list):
                    resolved_status = "unresolved"
                conn.execute(
                    "INSERT INTO claims (claim_id, claim_text, claim_digest, status, metadata_json) VALUES (?, ?, ?, ?, ?)",
                    (cid, norm, digest, resolved_status, meta_json),
                )

            for ev_aid, ev_stance, ev_loc in ev_list:
                prev_ev = conn.execute(
                    "SELECT stance FROM claim_evidence WHERE claim_id = ? AND artifact_id = ? AND locator = ?",
                    (cid, ev_aid, ev_loc),
                ).fetchone()
                if prev_ev is not None:
                    if prev_ev["stance"] != ev_stance:
                        raise ValueError(
                            f"Conflicting evidence stance on ({cid!r}, {ev_aid!r}, {ev_loc!r}): "
                            f"stored={prev_ev['stance']!r} vs incoming={ev_stance!r}"
                        )
                else:
                    conn.execute(
                        "INSERT INTO claim_evidence (claim_id, artifact_id, stance, locator) VALUES (?, ?, ?, ?)",
                        (cid, ev_aid, ev_stance, ev_loc),
                    )

            # Reconcile derived status if contradicting/supporting evidence was newly attached without conflicting explicit override
            stances_rows = conn.execute("SELECT stance FROM claim_evidence WHERE claim_id = ?", (cid,)).fetchall()
            stances = {str(r["stance"]) for r in stances_rows}
            cur_row = conn.execute("SELECT status FROM claims WHERE claim_id = ?", (cid,)).fetchone()
            final_status = str(cur_row["status"])
            if "contradicts" in stances:
                new_st = "contested" if "supports" in stances else "refuted"
                if final_status != new_st:
                    conn.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (new_st, cid))
                    final_status = new_st
            elif "supports" in stances and final_status == "unresolved" and status is None:
                conn.execute("UPDATE claims SET status = 'supported' WHERE claim_id = ?", (cid,))
                final_status = "supported"

            for dst in dep_list:
                self._assert_acyclic(conn, "claim_edges", "src_claim_id", "dst_claim_id", cid, dst)
                conn.execute(
                    """
                    INSERT INTO claim_edges (src_claim_id, dst_claim_id, relation)
                    VALUES (?, ?, 'depends_on')
                    ON CONFLICT(src_claim_id, dst_claim_id, relation) DO NOTHING
                    """,
                    (cid, dst),
                )
        return freeze({"claim_id": cid, "claim_digest": digest, "status": final_status})

    def attach_claim_evidence(self, claim_id: str, artifact_id: str, stance: str, locator: str = "") -> Mapping[str, Any]:
        """Attach verified evidence to an existing claim and reconcile support/contestation status."""
        cid = _require_str_id(claim_id, "claim_id")
        with self.transaction() as conn:
            row = conn.execute("SELECT claim_text FROM claims WHERE claim_id = ?", (cid,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown target claim_id {cid!r}")
            return self.add_claim(cid, str(row["claim_text"]), status=None, evidence=[(artifact_id, stance, locator)])

    def add_claim_relation(self, src_claim_id: str, dst_claim_id: str, relation: str = "depends_on") -> Mapping[str, Any]:
        """Link two existing claims via depends_on, refines, contradicts, corroborates, or cites."""
        src = _require_str_id(src_claim_id, "src_claim_id")
        dst = _require_str_id(dst_claim_id, "dst_claim_id")
        rel = _require_str_id(relation, "relation")
        if rel not in ("depends_on", "refines", "contradicts", "corroborates", "cites"):
            raise ValueError(f"Invalid claim relation {rel!r}")
        if src == dst:
            raise ValueError("Claim cannot link to itself")
        with self.transaction() as conn:
            for cid in (src, dst):
                if conn.execute("SELECT 1 FROM claims WHERE claim_id = ?", (cid,)).fetchone() is None:
                    raise ValueError(f"Unknown claim_id {cid!r}")
            if rel in ("depends_on", "refines"):
                row = conn.execute(
                    """
                    WITH RECURSIVE reach(node) AS (
                        SELECT ?
                        UNION
                        SELECT e.dst_claim_id FROM claim_edges e
                        JOIN reach r ON e.src_claim_id = r.node
                        WHERE e.relation IN ('depends_on', 'refines')
                    )
                    SELECT 1 FROM reach WHERE node = ? LIMIT 1
                    """,
                    (dst, src),
                ).fetchone()
                if row is not None:
                    raise ValueError(f"Cycle detected in claim_edges: adding {src!r} -> {dst!r} ({rel}) creates a loop")
            conn.execute(
                """
                INSERT INTO claim_edges (src_claim_id, dst_claim_id, relation)
                VALUES (?, ?, ?)
                ON CONFLICT(src_claim_id, dst_claim_id, relation) DO NOTHING
                """,
                (src, dst, rel),
            )
            if rel == "contradicts":
                conn.execute(
                    "UPDATE claims SET status = 'contested' WHERE claim_id IN (?, ?) AND status = 'supported'",
                    (src, dst),
                )
        return freeze({"source_claim_id": src, "target_claim_id": dst, "relation_type": rel})

    def record_decision(
        self,
        decision_id: str,
        title: str,
        entry_kind: str = "decision",
        action: str = "explore",
        verdict: str = "inconclusive",
        basis_decision_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
        initial_state: str = "active",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        did = _require_str_id(decision_id, "decision_id")
        if type(title) is not str or not nfc_compact(title):
            raise ValueError("title must be a non-empty string")
        clean_title = nfc_compact(title)
        ek = _require_str_id(entry_kind, "entry_kind")
        act = _require_str_id(action, "action")
        verd = _require_str_id(verdict, "verdict")
        init_st = _require_str_id(initial_state, "initial_state")

        if init_st not in _VALID_TRANSITIONS[None]:
            raise ValueError(f"Invalid genesis initial_state {init_st!r}; allowed={sorted(_VALID_TRANSITIONS[None])}")

        if ek == "negative_result" or act == "negative_result":
            if ek == "decision" and act == "negative_result" and entry_kind != "negative_result":
                # Normalize only when caller omitted entry_kind? No: reject explicit mismatch, require basis either way!
                ek = "negative_result"
            act = "negative_result"
            ek = "negative_result"

        basis_id = _require_str_id(basis_decision_id, "basis_decision_id") if basis_decision_id is not None else None
        art_id = _require_str_id(artifact_id, "artifact_id") if artifact_id is not None else None
        meta_json = canonical_json(metadata or {})

        with self.transaction() as conn:
            if ek == "negative_result":
                if not basis_id:
                    raise ValueError("negative_result requires basis_decision_id referencing a prior non-negative decision")
                if basis_id == did:
                    raise ValueError("negative_result cannot reference itself as basis")
                basis = conn.execute(
                    "SELECT entry_kind FROM decisions WHERE decision_id = ?", (basis_id,)
                ).fetchone()
                if basis is None or basis["entry_kind"] == "negative_result":
                    raise ValueError("negative_result basis must be an existing non-negative decision")
            conn.execute(
                """
                INSERT INTO decisions
                (decision_id, entry_kind, action, title, verdict, basis_decision_id, artifact_id, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (did, ek, act, clean_title, verd, basis_id, art_id, meta_json),
            )
            conn.execute(
                "INSERT INTO decision_events (decision_id, new_state, reason) VALUES (?, ?, 'genesis')",
                (did, init_st),
            )
        return freeze({"decision_id": did, "entry_kind": ek, "action": act, "state": init_st, "verdict": verd})

    def transition_decision(
        self,
        decision_id: str,
        new_state: str,
        reason: str,
        superseded_by_id: Optional[str] = None,
        verdict_override: Optional[str] = None,
    ) -> Mapping[str, Any]:
        did = _require_str_id(decision_id, "decision_id")
        nst = _require_str_id(new_state, "new_state")
        rsn = _require_str_id(reason, "reason")
        sup_id = _require_str_id(superseded_by_id, "superseded_by_id") if superseded_by_id is not None else None

        if rsn == "genesis":
            raise ValueError("Reason 'genesis' is reserved exclusively for initial decision creation")
        if nst == "pruned" and rsn not in PRUNE_REASONS:
            raise ValueError(f"Invalid prune reason {rsn!r}; allowed={sorted(PRUNE_REASONS)}")
        if nst == "reopened" and rsn not in REOPEN_REASONS:
            raise ValueError(f"Invalid reopen reason {rsn!r}; allowed={sorted(REOPEN_REASONS)}")

        with self.transaction() as conn:
            last = conn.execute(
                "SELECT new_state FROM decision_events WHERE decision_id = ? ORDER BY seq DESC LIMIT 1",
                (did,),
            ).fetchone()
            if last is None:
                raise ValueError(f"Unknown decision_id {did!r}")
            cur_state = str(last["new_state"])
            if nst not in _VALID_TRANSITIONS.get(cur_state, frozenset()):
                raise ValueError(f"Illegal state transition {cur_state!r} -> {nst!r}")
            if rsn == "superseded" and sup_id is None:
                raise ValueError("Reason 'superseded' requires superseded_by_id")
            if sup_id is not None:
                if sup_id == did:
                    raise ValueError("Decision cannot supersede itself")
                row = conn.execute(
                    """
                    WITH RECURSIVE sup(node) AS (
                        SELECT ?
                        UNION
                        SELECT e.superseded_by_id FROM decision_events e
                        JOIN sup r ON e.decision_id = r.node
                        WHERE e.superseded_by_id IS NOT NULL
                    )
                    SELECT 1 FROM sup WHERE node = ? LIMIT 1
                    """,
                    (sup_id, did),
                ).fetchone()
                if row is not None:
                    raise ValueError("Cycle detected in abandonment/supersession chain")
            conn.execute(
                """
                INSERT INTO decision_events (decision_id, new_state, reason, superseded_by_id, verdict_override)
                VALUES (?, ?, ?, ?, ?)
                """,
                (did, nst, rsn, sup_id, verdict_override),
            )
        return freeze({"decision_id": did, "state": nst, "reason": rsn})

    def reserve_watch_seq(self, watcher: str, item_key: str) -> int:
        """Reserve a monotonic observation sequence BEFORE network I/O to enforce chronological CAS."""
        w = _require_str_id(watcher, "watcher")
        k = normalize_doi(item_key) if w == "retraction" else _require_str_id(item_key, "item_key")
        if not k:
            raise ValueError("Watch item_key must be non-empty")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO doi_watch_state (watcher, item_key, reserved_seq)
                VALUES (?, ?, 1)
                ON CONFLICT(watcher, item_key) DO UPDATE SET reserved_seq = doi_watch_state.reserved_seq + 1
                """,
                (w, k),
            )
            row = conn.execute(
                "SELECT reserved_seq FROM doi_watch_state WHERE watcher = ? AND item_key = ?",
                (w, k),
            ).fetchone()
            return int(row["reserved_seq"])

    def commit_watch_observation(
        self,
        watcher: str,
        item_key: str,
        *,
        seq: int,
        status: str,
        signals: Iterable[str] = (),
        signals_complete: bool = True,
        truncated: bool = False,
        error: Optional[str] = None,
    ) -> Mapping[str, Any]:
        """CAS-merge a 3-state observation ('retracted' | 'not_retracted' | 'unknown') without erasing confirmed state."""
        w = _require_str_id(watcher, "watcher")
        k = normalize_doi(item_key) if w == "retraction" else _require_str_id(item_key, "item_key")
        if not k:
            raise ValueError("Watch item_key must be non-empty")
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
            raise ValueError(f"Watch observation seq must be a positive integer, got {seq!r}")
        if status not in ("retracted", "not_retracted", "unknown"):
            raise ValueError(f"Invalid watch observation status: {status!r}")
        sig_list = sorted({str(s) for s in signals if str(s).strip()})
        sig_json = canonical_json(sig_list)
        trunc_int = 1 if truncated else 0
        commit_digest = sha256_hex(
            canonical_json(
                {
                    "status": status,
                    "signals": sig_list,
                    "signals_complete": bool(signals_complete),
                    "truncated": bool(truncated),
                }
            )
        )

        with self.transaction() as conn:
            prior_commit = conn.execute(
                "SELECT commit_digest, snapshot_json FROM doi_watch_commits WHERE watcher = ? AND item_key = ? AND seq = ?",
                (w, k, seq),
            ).fetchone()
            if prior_commit is not None:
                if str(prior_commit["commit_digest"]) != commit_digest:
                    raise ValueError(
                        f"Conflicting watch observation replay for ({w!r}, {k!r}, seq={seq})"
                    )
                idem = json.loads(str(prior_commit["snapshot_json"]))
                idem["changed"] = False
                return freeze(idem)

            prev = conn.execute(
                """
                SELECT current_status, confirmed_retracted, signals_json, reserved_seq, applied_seq,
                       confirmed_seq, observation_version, truncated, last_error, unacked_delta_json
                FROM doi_watch_state WHERE watcher = ? AND item_key = ?
                """,
                (w, k),
            ).fetchone()

            prev_applied = int(prev["applied_seq"]) if prev is not None else 0
            prev_conf_seq = int(prev["confirmed_seq"]) if prev is not None else 0
            prev_conf = prev["confirmed_retracted"] if prev is not None else None
            prev_sigs_list = json.loads(str(prev["signals_json"])) if prev is not None else []
            prev_sigs = canonical_json(prev_sigs_list)
            prev_ver = int(prev["observation_version"]) if prev is not None else 0
            prev_unacked = prev["unacked_delta_json"] if prev is not None else None
            prev_status = str(prev["current_status"]) if prev is not None else "unknown"

            is_stale = (status == "unknown" and seq < prev_applied) or (
                status != "unknown" and seq < prev_conf_seq
            )
            if prev is not None and is_stale:
                stale_obj = {
                    "doi": k,
                    "changed": False,
                    "stale_ignored": True,
                    "status": prev_status,
                    "is_retracted": bool(prev_conf) if prev_conf is not None else None,
                    "version": prev_ver,
                    "signals": prev_sigs_list,
                    "truncated": bool(trunc_int),
                }
                conn.execute(
                    "INSERT INTO doi_watch_commits (watcher, item_key, seq, commit_digest, snapshot_json) VALUES (?, ?, ?, ?, ?)",
                    (w, k, seq, commit_digest, canonical_json(stale_obj)),
                )
                return freeze(stale_obj)

            new_applied = max(prev_applied, seq)
            eff_trunc = int(prev["truncated"]) if (prev is not None and seq < prev_applied) else trunc_int
            eff_error = prev["last_error"] if (prev is not None and seq < prev_applied) else error
            if status == "unknown":
                # Offline or unavailable observation: NEVER overwrite confirmed_retracted or prior signals
                new_conf = prev_conf
                new_conf_seq = prev_conf_seq
                merged_sigs = sorted(set(prev_sigs_list) | set(sig_list)) if sig_list else prev_sigs_list
                new_sigs = canonical_json(merged_sigs)
                new_current_status = "unknown"
                changed = new_sigs != prev_sigs
                new_ver = prev_ver + 1 if changed else prev_ver
            else:
                obs_flag = 1 if status == "retracted" else 0
                # If a newer unknown observation already arrived (seq < prev_applied), keep current_status='unknown'
                # while recording the newly confirmed historical truth at confirmed_seq = seq and preserving newer diagnostics.
                new_current_status = prev_status if seq < prev_applied else status
                new_conf = obs_flag
                new_conf_seq = max(prev_conf_seq, seq)
                if seq < prev_applied or not signals_complete:
                    merged_sigs = sorted(set(prev_sigs_list) | set(sig_list))
                else:
                    merged_sigs = sig_list
                new_sigs = canonical_json(merged_sigs)
                changed = (prev_conf is None) or (int(prev_conf) != obs_flag) or (prev_sigs != new_sigs)
                new_ver = prev_ver + 1 if (changed or prev_ver == 0) else prev_ver

            delta_obj = {
                "doi": k,
                "changed": changed,
                "stale_ignored": False,
                "status": new_current_status,
                "is_retracted": bool(new_conf) if new_conf is not None else None,
                "version": new_ver,
                "signals": json.loads(new_sigs),
                "truncated": bool(eff_trunc),
                "error": eff_error,
            }
            new_unacked = canonical_json(delta_obj) if changed else prev_unacked
            new_reserved = max(seq, int(prev["reserved_seq"]) if prev is not None else seq)

            conn.execute(
                """
                INSERT INTO doi_watch_state (
                    watcher, item_key, current_status, confirmed_retracted, signals_json,
                    reserved_seq, applied_seq, confirmed_seq, observation_version, truncated, last_error, unacked_delta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(watcher, item_key) DO UPDATE SET
                    current_status = excluded.current_status,
                    confirmed_retracted = excluded.confirmed_retracted,
                    signals_json = excluded.signals_json,
                    reserved_seq = excluded.reserved_seq,
                    applied_seq = excluded.applied_seq,
                    confirmed_seq = excluded.confirmed_seq,
                    observation_version = excluded.observation_version,
                    truncated = excluded.truncated,
                    last_error = excluded.last_error,
                    unacked_delta_json = excluded.unacked_delta_json
                """,
                (
                    w, k, new_current_status, new_conf, new_sigs,
                    new_reserved, new_applied, new_conf_seq, new_ver, eff_trunc, eff_error, new_unacked,
                ),
            )
            conn.execute(
                "INSERT INTO doi_watch_commits (watcher, item_key, seq, commit_digest, snapshot_json) VALUES (?, ?, ?, ?, ?)",
                (w, k, seq, commit_digest, canonical_json(delta_obj)),
            )
            return freeze(delta_obj)

    def drain_unacked_watch_deltas(self, watcher: str, keys: Optional[Iterable[str]] = None) -> list[dict[str, Any]]:
        """Atomically fetch and acknowledge pending watch deltas so partial batch timeouts never drop alerts."""
        w = _require_str_id(watcher, "watcher")
        key_filter = [normalize_doi(k) if w == "retraction" else str(k).strip() for k in keys] if keys is not None else None
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT item_key, unacked_delta_json FROM doi_watch_state WHERE watcher = ? AND unacked_delta_json IS NOT NULL ORDER BY item_key",
                (w,),
            ).fetchall()
            deltas: list[dict[str, Any]] = []
            for r in rows:
                ik = str(r["item_key"])
                if key_filter is not None and ik not in key_filter:
                    continue
                deltas.append(json.loads(str(r["unacked_delta_json"])))
                conn.execute(
                    "UPDATE doi_watch_state SET unacked_delta_json = NULL WHERE watcher = ? AND item_key = ?",
                    (w, ik),
                )
            return deltas

    def update_doi_watch(self, watcher: str, doi: str, is_retracted: Optional[bool], signals: Iterable[str] = ()) -> Mapping[str, Any]:
        """Convenience single-step wrapper over reserve_watch_seq + commit_watch_observation."""
        seq = self.reserve_watch_seq(watcher, doi)
        status = "unknown" if is_retracted is None else ("retracted" if is_retracted else "not_retracted")
        res = self.commit_watch_observation(watcher, doi, seq=seq, status=status, signals=signals)
        if res["changed"]:
            self.drain_unacked_watch_deltas(watcher, [doi])
        return res

    def import_legacy_watch_json(self, watcher: str, legacy_payload: Mapping[str, Any]) -> dict[str, Any]:
        """One-time migration helper importing v2.4.x JSON watch state into SQLite STRICT tables."""
        w = _require_str_id(watcher, "watcher")
        imported = 0
        with self.transaction():
            if w == "retraction":
                items = legacy_payload.get("dois") or legacy_payload.get("items") or legacy_payload
                if isinstance(items, Mapping):
                    for raw_doi, entry in items.items():
                        if raw_doi in ("schema_version", "updated_at", "watcher") or not isinstance(entry, Mapping):
                            continue
                        is_ret = entry.get("is_retracted")
                        sigs = entry.get("signals") or []
                        seq = self.reserve_watch_seq("retraction", str(raw_doi))
                        st = "unknown" if is_ret is None else ("retracted" if bool(is_ret) else "not_retracted")
                        self.commit_watch_observation("retraction", str(raw_doi), seq=seq, status=st, signals=sigs)
                        self.drain_unacked_watch_deltas("retraction", [str(raw_doi)])
                        imported += 1
            else:
                seen_list = legacy_payload.get("seen_ids") or legacy_payload.get("seen") or []
                if isinstance(seen_list, Mapping):
                    seen_list = list(seen_list.keys())
                for raw_id in seen_list:
                    sid = str(raw_id).strip()
                    if not sid:
                        continue
                    seq = self.reserve_watch_seq(w, sid)
                    self.commit_watch_observation(w, sid, seq=seq, status="not_retracted", signals=["legacy_import"])
                    self.drain_unacked_watch_deltas(w, [sid])
                    imported += 1
        return {"watcher": w, "imported_count": imported}

    def export_ceg_dict(self) -> dict[str, Any]:
        """Export complete authoritative Claim-Evidence Graph in canonical claim-evidence-graph-1.0 format."""
        with self._read_snapshot() as conn:
            c_rows = conn.execute("SELECT * FROM claims ORDER BY claim_id").fetchall()
            ev_rows = conn.execute("SELECT * FROM claim_evidence ORDER BY claim_id, artifact_id, locator").fetchall()
            ce_rows = conn.execute("SELECT * FROM claim_edges ORDER BY src_claim_id, dst_claim_id, relation").fetchall()

        claims = []
        for r in c_rows:
            raw_meta = json.loads(str(r["metadata_json"]))
            meta_out = dict(raw_meta) if isinstance(raw_meta, dict) else {"value": raw_meta}
            meta_out.setdefault("status", str(r["status"]))
            txt = str(r["claim_text"])
            claims.append({
                "id": str(r["claim_id"]),
                "text": txt,
                "normalized_text": nfc_compact(txt),
                "claim_type": str(meta_out.get("claim_type") or "generic_claim")
                if meta_out.get("claim_type") in (
                    "empirical_finding", "theoretical_claim", "benchmark_result", "methodological_assertion", "generic_claim"
                )
                else "generic_claim",
                "claim_digest": str(r["claim_digest"]),
                "metadata": meta_out,
            })

        evidence_by_id: dict[str, dict[str, Any]] = {}
        support_edges = []
        stance_to_support = {"supports": "supported", "contradicts": "contradicted", "qualifies": "unverifiable"}
        for r in ev_rows:
            art_s = str(r["artifact_id"])
            loc_s = str(r["locator"])
            ev_prefix = "ev-quant-" if art_s.startswith("results-") else "ev-"
            ev_id = ev_prefix + sha256_hex(canonical_json([art_s, loc_s]))[:20]
            if ev_id not in evidence_by_id:
                evidence_by_id[ev_id] = {
                    "id": ev_id,
                    "anchor_type": "evidence_receipt",
                    "locator": loc_s,
                    "metadata": {"artifact_id": art_s, "stance": str(r["stance"])},
                }
            support_edges.append({
                "evidence_id": ev_id,
                "claim_id": str(r["claim_id"]),
                "support_status": stance_to_support[str(r["stance"])],
            })
        evidence_anchors = list(evidence_by_id.values())

        rel_map = {
            "depends_on": "depends_on",
            "supports": "corroborates",
            "corroborates": "corroborates",
            "cites": "cites",
            "refines": "refines",
            "contradicts": "contradicts",
        }
        claim_relations = [
            {
                "source_claim_id": str(r["src_claim_id"]),
                "target_claim_id": str(r["dst_claim_id"]),
                "relation_type": rel_map.get(str(r["relation"]), "depends_on"),
            }
            for r in ce_rows
        ]
        contra_claims = {
            cr["source_claim_id"] for cr in claim_relations if cr["relation_type"] == "contradicts"
        } | {
            cr["target_claim_id"] for cr in claim_relations if cr["relation_type"] == "contradicts"
        }
        uncertainties: list[dict[str, Any]] = []
        for r in c_rows:
            cid_s = str(r["claim_id"])
            st_s = str(r["status"])
            if st_s == "contested" or cid_s in contra_claims:
                uhash = sha256_hex(canonical_json(["unresolved_contradiction", cid_s]))[:16]
                uncertainties.append({
                    "item_id": f"unc-{uhash}",
                    "subject_id": cid_s,
                    "kind": "unresolved_contradiction",
                    "reason": "Claim has conflicting evidence or unresolved contradiction edges",
                    "needs_human": True,
                })
            elif st_s == "unresolved":
                uhash = sha256_hex(canonical_json(["unverifiable_claim", cid_s]))[:16]
                uncertainties.append({
                    "item_id": f"unc-{uhash}",
                    "subject_id": cid_s,
                    "kind": "unverifiable_claim",
                    "reason": "Claim has no supporting or contradicting empirical evidence attached",
                    "needs_human": True,
                })

        body_for_digest = {
            "protocol": "claim-evidence-graph-1.0",
            "claims": claims,
            "evidence_anchors": evidence_anchors,
            "support_edges": support_edges,
            "claim_relations": claim_relations,
            "uncertainties": uncertainties,
        }
        g_digest = sha256_hex(canonical_json(body_for_digest))
        return {
            "protocol": "claim-evidence-graph-1.0",
            "graph_id": f"ceg-{g_digest[:16]}",
            "graph_digest": g_digest,
            "claims": claims,
            "evidence_anchors": evidence_anchors,
            "support_edges": support_edges,
            "claim_relations": claim_relations,
            "uncertainties": uncertainties,
        }

    def correct_decision_outcome(
        self,
        decision_id: str,
        verdict: str,
        rationale: str,
        artifact_id: Optional[str] = None,
    ) -> Mapping[str, Any]:
        """Append an independent outcome correction without mutating lifecycle state."""
        did = _require_str_id(decision_id, "decision_id")
        verd = _require_str_id(verdict, "verdict")
        if verd not in ("positive", "negative", "inconclusive", "unverifiable"):
            raise ValueError(f"Invalid verdict {verd!r}")
        if type(rationale) is not str or not nfc_compact(rationale):
            raise ValueError("rationale must be a non-empty string")
        clean_rat = nfc_compact(rationale)
        art_id = _require_str_id(artifact_id, "artifact_id") if artifact_id is not None else None
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM decisions WHERE decision_id = ?", (did,)).fetchone() is None:
                raise ValueError(f"Unknown decision_id {did!r}")
            cur = conn.execute(
                "INSERT INTO decision_corrections (decision_id, verdict, rationale, artifact_id) VALUES (?, ?, ?, ?)",
                (did, verd, clean_rat, art_id),
            )
            seq = int(cur.lastrowid or 1)
        return freeze({"decision_id": did, "verdict": verd, "rationale": clean_rat, "sequence": seq})

    def export_decision_ledger_dict(self) -> dict[str, Any]:
        """Export schema-compliant decision-ledger-1.0 receipt from SQLite STRICT tables."""
        with self._read_snapshot() as conn:
            d_rows = conn.execute("SELECT * FROM decisions ORDER BY decision_id ASC").fetchall()
            e_rows = conn.execute("SELECT * FROM decision_events ORDER BY seq ASC").fetchall()
            c_rows = conn.execute("SELECT * FROM decision_corrections ORDER BY seq ASC").fetchall()
            art_shas = {
                str(r["artifact_id"]): str(r["payload_sha256"])
                for r in conn.execute("SELECT artifact_id, payload_sha256 FROM artifacts").fetchall()
            }

        decisions_out: list[dict[str, Any]] = []
        bases_out: list[dict[str, Any]] = []
        uncertainties_out: list[dict[str, Any]] = []
        v_manifest: dict[str, str] = {}

        for r in d_rows:
            did = str(r["decision_id"])
            ek = str(r["entry_kind"])
            act = str(r["action"])
            title = str(r["title"])
            ntitle = nfc_compact(title)
            art_id = str(r["artifact_id"]) if r["artifact_id"] is not None else None
            basis_id = str(r["basis_decision_id"]) if r["basis_decision_id"] is not None else None
            raw_meta = json.loads(str(r["metadata_json"]))
            meta_d = dict(raw_meta) if isinstance(raw_meta, dict) else {"value": raw_meta}
            meta_d["verdict"] = str(r["verdict"])
            if art_id:
                meta_d["artifact_id"] = art_id
                if art_id in art_shas:
                    v_manifest[art_id] = art_shas[art_id]

            d_digest = sha256_hex(canonical_json({"id": did, "entry_kind": ek, "action": act, "title": ntitle}))
            d_obj: dict[str, Any] = {
                "id": did,
                "title": title,
                "normalized_title": ntitle,
                "decision_type": "negative_result" if ek == "negative_result" else act,
                "entry_kind": ek,
                "decision_action": None if ek == "negative_result" else act,
                "decision_digest": d_digest,
                "metadata": meta_d,
            }
            decisions_out.append(d_obj)

            if basis_id:
                b_edge: dict[str, Any] = {
                    "decision_id": did,
                    "basis_kind": "decision",
                    "basis_id": basis_id,
                }
                if art_id and art_id in art_shas:
                    b_edge["receipt_ref"] = {
                        "kind": "lineage",
                        "schema_version": "lineage-receipt-1.0",
                        "receipt_id": art_id,
                        "receipt_digest": art_shas[art_id],
                    }
                bases_out.append(b_edge)

            if ek == "negative_result" and not art_id:
                uh = sha256_hex(canonical_json(["unsupported_negative_result", did]))[:16]
                uncertainties_out.append({
                    "item_id": f"unc-{uh}",
                    "subject_id": did,
                    "kind": "unsupported_negative_result",
                    "reason": "Negative result recorded without empirical artifact_id receipt",
                    "needs_human": True,
                })
            elif ek == "decision" and act in ("commit", "abandon", "revise") and not basis_id and not art_id:
                uh = sha256_hex(canonical_json(["decision_without_basis", did]))[:16]
                uncertainties_out.append({
                    "item_id": f"unc-{uh}",
                    "subject_id": did,
                    "kind": "decision_without_basis",
                    "reason": f"Decision action {act!r} recorded without basis_decision_id or artifact_id",
                    "needs_human": True,
                })

        prev_state_by_dec: dict[str, str] = {}
        events_out: list[dict[str, Any]] = []
        for er in e_rows:
            seq = int(er["seq"])
            did = str(er["decision_id"])
            to_st = str(er["new_state"])
            rsn = str(er["reason"])
            sup_id = str(er["superseded_by_id"]) if er["superseded_by_id"] is not None else None
            from_st = prev_state_by_dec.get(did)
            prev_state_by_dec[did] = to_st

            ev_hash = sha256_hex(canonical_json([seq, did, from_st, to_st, rsn, sup_id]))[:32]
            ev_obj: dict[str, Any] = {
                "event_id": f"evt-{ev_hash}",
                "decision_id": did,
                "to_state": to_st,
                "sequence": seq,
            }
            if from_st is not None:
                ev_obj["from_state"] = from_st
            if to_st in ("pruned", "reopened") and rsn != "genesis":
                ev_obj["reason"] = rsn
            elif to_st == "pruned" and rsn == "genesis":
                ev_obj["reason"] = "other"
            if sup_id is not None and to_st == "pruned":
                ev_obj["alternative_ref"] = sup_id
            events_out.append(ev_obj)

        corrections_out: list[dict[str, Any]] = []
        for cr in c_rows:
            c_seq = int(cr["seq"])
            did = str(cr["decision_id"])
            verd = str(cr["verdict"])
            rat = str(cr["rationale"])
            c_art = str(cr["artifact_id"]) if cr["artifact_id"] is not None else None
            o_dig = sha256_hex(canonical_json([did, verd, rat, c_art]))
            c_hash = sha256_hex(canonical_json([c_seq, did, o_dig]))[:32]
            c_obj: dict[str, Any] = {
                "correction_id": f"corr-{c_hash}",
                "decision_id": did,
                "verdict": verd,
                "rationale": rat,
                "outcome_digest": o_dig,
                "sequence": c_seq,
            }
            if c_art and c_art in art_shas:
                c_obj["receipt_ref"] = {
                    "kind": "lineage",
                    "schema_version": "lineage-receipt-1.0",
                    "receipt_id": c_art,
                    "receipt_digest": art_shas[c_art],
                }
            corrections_out.append(c_obj)

        v_digest = sha256_hex(canonical_json(v_manifest))
        body = {
            "protocol": "decision-ledger-1.0",
            "verification_digest": v_digest,
            "verification_manifest": v_manifest,
            "decisions": decisions_out,
            "bases": bases_out,
            "forks": [],
            "state_events": events_out,
            "corrections": corrections_out,
            "uncertainties": uncertainties_out,
        }
        l_digest = sha256_hex(canonical_json(body))
        return {
            "protocol": "decision-ledger-1.0",
            "ledger_id": f"dl-{l_digest[:16]}",
            "ledger_digest": l_digest,
            **body,
        }

    def validate_decisions(self) -> dict[str, Any]:
        """Validate raw SQLite decision tables, event transitions, referential integrity, and exported schema."""
        errors: list[str] = []
        with self._read_snapshot() as conn:
            d_rows = conn.execute("SELECT * FROM decisions ORDER BY decision_id ASC").fetchall()
            e_rows = conn.execute("SELECT * FROM decision_events ORDER BY seq ASC").fetchall()
            c_rows = conn.execute("SELECT * FROM decision_corrections ORDER BY seq ASC").fetchall()

        dec_by_id = {str(r["decision_id"]): dict(r) for r in d_rows}
        for did, d in dec_by_id.items():
            if not re.fullmatch(r"^[a-z0-9][a-z0-9._-]{0,63}$", did):
                errors.append(f"Invalid decision_id format {did!r} (must match ^[a-z0-9][a-z0-9._-]{{0,63}}$)")
            b_id = d.get("basis_decision_id")
            if d["entry_kind"] == "negative_result":
                if not b_id or str(b_id) not in dec_by_id:
                    errors.append(f"negative_result {did!r} missing valid basis_decision_id")
                elif dec_by_id[str(b_id)]["entry_kind"] != "decision":
                    errors.append(f"negative_result {did!r} basis {b_id!r} must be entry_kind='decision'")
            elif b_id is not None and str(b_id) not in dec_by_id:
                errors.append(f"decision {did!r} references unknown basis_decision_id {b_id!r}")

        seen_seqs: set[int] = set()
        last_seq = 0
        state_by_dec: dict[str, str] = {}
        sup_adj: dict[str, set[str]] = {}
        for er in e_rows:
            seq = int(er["seq"])
            if seq <= last_seq or seq in seen_seqs:
                errors.append(f"Non-monotonic or duplicate event sequence {seq}")
            seen_seqs.add(seq)
            last_seq = max(last_seq, seq)
            did = str(er["decision_id"])
            if did not in dec_by_id:
                errors.append(f"Event seq={seq} references unknown decision_id {did!r}")
                continue
            nst = str(er["new_state"])
            rsn = str(er["reason"])
            sup_id = str(er["superseded_by_id"]) if er["superseded_by_id"] is not None else None
            prev_st = state_by_dec.get(did)
            if prev_st is None:
                if rsn != "genesis":
                    errors.append(f"Initial event for {did!r} must have reason='genesis', got {rsn!r}")
                if nst not in _VALID_TRANSITIONS[None]:
                    errors.append(f"Invalid genesis state {nst!r} for {did!r}")
            else:
                if rsn == "genesis":
                    errors.append(f"Non-initial event seq={seq} for {did!r} cannot use reason='genesis'")
                if nst not in _VALID_TRANSITIONS.get(prev_st, frozenset()):
                    errors.append(f"Illegal state transition {prev_st!r} -> {nst!r} on {did!r} at seq={seq}")
                if nst == "pruned" and rsn not in PRUNE_REASONS:
                    errors.append(f"Invalid prune reason {rsn!r} on {did!r} at seq={seq}")
                if nst == "reopened" and rsn not in REOPEN_REASONS:
                    errors.append(f"Invalid reopen reason {rsn!r} on {did!r} at seq={seq}")
            if rsn == "superseded":
                if not sup_id or sup_id not in dec_by_id or sup_id == did:
                    errors.append(f"Invalid superseded_by_id {sup_id!r} on {did!r} at seq={seq}")
                else:
                    sup_adj.setdefault(did, set()).add(sup_id)
            state_by_dec[did] = nst

        for did in dec_by_id:
            if did not in state_by_dec:
                errors.append(f"Decision {did!r} has no genesis event in decision_events")

        for cr in c_rows:
            if str(cr["decision_id"]) not in dec_by_id:
                errors.append(f"Correction seq={cr['seq']} references unknown decision_id {cr['decision_id']!r}")

        if not errors:
            exported = self.export_decision_ledger_dict()
            errors.extend(validate_decision_ledger_semantics(exported))

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "decision_count": len(d_rows),
            "event_count": len(e_rows),
            "correction_count": len(c_rows),
        }

    def snapshot_digest(self) -> str:
        """Deterministic order-invariant SHA-256 digest of all authoritative tables under one read snapshot."""
        tables = (
            "works",
            "artifacts",
            "lineage_edges",
            "claims",
            "claim_evidence",
            "claim_edges",
            "decisions",
            "decision_events",
            "decision_corrections",
            "doi_watch_state",
            "doi_watch_commits",
        )
        with self._read_snapshot() as conn:
            dump: dict[str, Any] = {"schema_version": ARK_SQLITE_USER_VERSION}
            for tbl in tables:
                rows = conn.execute(f"SELECT * FROM {tbl}").fetchall()
                dump[tbl] = sorted((dict(r) for r in rows), key=canonical_json)
            return sha256_hex(canonical_json(dump))


def validate_decision_ledger_semantics(doc: Mapping[str, Any]) -> list[str]:
    """Validate schema AND referential/lifecycle invariants on a decision-ledger-1.0 JSON document."""
    errs = list(validate_schema(doc, "decision-ledger-receipt.schema.json"))
    if not isinstance(doc, Mapping):
        return errs or ["Ledger must be a JSON object"]

    decs = doc.get("decisions")
    bases = doc.get("bases")
    forks = doc.get("forks")
    events = doc.get("state_events")
    corrs = doc.get("corrections")

    dec_by_id: dict[str, Mapping[str, Any]] = {}
    if isinstance(decs, list):
        for idx, d in enumerate(decs):
            if not isinstance(d, Mapping):
                continue
            did = str(d.get("id") or "")
            if did in dec_by_id:
                errs.append(f"Duplicate decision id {did!r} at decisions[{idx}]")
            elif did:
                dec_by_id[did] = d

    neg_with_basis: set[str] = set()
    if isinstance(bases, list):
        for idx, b in enumerate(bases):
            if not isinstance(b, Mapping):
                continue
            did = str(b.get("decision_id") or "")
            bid = str(b.get("basis_id") or "")
            if did not in dec_by_id:
                errs.append(f"bases[{idx}] references unknown decision_id {did!r}")
            if bid not in dec_by_id:
                errs.append(f"bases[{idx}] references unknown basis_id {bid!r}")
            if did and did == bid:
                errs.append(f"bases[{idx}] self-basis on {did!r}")
            if did in dec_by_id and bid in dec_by_id:
                if dec_by_id[did].get("entry_kind") == "negative_result":
                    if dec_by_id[bid].get("entry_kind") != "decision":
                        errs.append(f"negative_result {did!r} basis {bid!r} must be entry_kind='decision'")
                    else:
                        neg_with_basis.add(did)

    for did, d in dec_by_id.items():
        if d.get("entry_kind") == "negative_result" and did not in neg_with_basis:
            errs.append(f"negative_result {did!r} has no valid basisEdge to a prior decision")

    if isinstance(forks, list):
        for idx, fk in enumerate(forks):
            if not isinstance(fk, Mapping):
                continue
            did = str(fk.get("decision_id") or "")
            aid = str(fk.get("alternative_id") or "")
            if did not in dec_by_id:
                errs.append(f"forks[{idx}] references unknown decision_id {did!r}")
            if aid not in dec_by_id:
                errs.append(f"forks[{idx}] references unknown alternative_id {aid!r}")
            if did and did == aid:
                errs.append(f"forks[{idx}] self-fork on {did!r}")

    if isinstance(events, list):
        seen_seq: set[int] = set()
        prev_seq = 0
        cur_state: dict[str, str] = {}
        sup_adj: dict[str, set[str]] = {}
        for idx, ev in enumerate(events):
            if not isinstance(ev, Mapping):
                continue
            seq = ev.get("sequence")
            if isinstance(seq, int) and not isinstance(seq, bool):
                if seq in seen_seq or seq <= prev_seq:
                    errs.append(f"state_events[{idx}] has non-monotonic or duplicate sequence {seq}")
                seen_seq.add(seq)
                prev_seq = max(prev_seq, seq)
            did = str(ev.get("decision_id") or "")
            if did not in dec_by_id:
                errs.append(f"state_events[{idx}] references unknown decision_id {did!r}")
                continue
            from_st = ev.get("from_state")
            to_st = str(ev.get("to_state") or "")
            prior = cur_state.get(did)
            if prior is None:
                if from_st is not None:
                    errs.append(f"Initial event for {did!r} must omit from_state, got {from_st!r}")
                if to_st not in _VALID_TRANSITIONS[None]:
                    errs.append(f"Illegal initial state {to_st!r} for {did!r}")
            else:
                if from_st != prior:
                    errs.append(f"Event state mismatch on {did!r}: expected from_state={prior!r}, got {from_st!r}")
                if to_st not in _VALID_TRANSITIONS.get(prior, frozenset()):
                    errs.append(f"Illegal transition {prior!r} -> {to_st!r} on {did!r}")
            if ev.get("reason") == "superseded":
                alt = str(ev.get("alternative_ref") or "")
                if not alt or alt not in dec_by_id or alt == did:
                    errs.append(f"Event {ev.get('event_id')!r} with reason='superseded' requires valid distinct alternative_ref")
                else:
                    sup_adj.setdefault(did, set()).add(alt)
            if ev.get("caused_by") is not None and str(ev.get("caused_by")) not in dec_by_id:
                errs.append(f"state_events[{idx}] caused_by references unknown decision {ev.get('caused_by')!r}")
            cur_state[did] = to_st

        # Check supersession cycles
        color: dict[str, int] = {}
        for start in sorted(sup_adj):
            if color.get(start, 0) != 0:
                continue
            stack = [(start, sorted(sup_adj.get(start, ())), 0)]
            color[start] = 1
            while stack:
                node, nbrs, pos = stack[-1]
                if pos >= len(nbrs):
                    color[node] = 2
                    stack.pop()
                    continue
                nxt = nbrs[pos]
                stack[-1] = (node, nbrs, pos + 1)
                st_c = color.get(nxt, 0)
                if st_c == 1:
                    errs.append(f"Cycle detected in supersession chain involving {nxt!r}")
                    break
                if st_c == 0:
                    color[nxt] = 1
                    stack.append((nxt, sorted(sup_adj.get(nxt, ())), 0))

    if isinstance(corrs, list):
        seen_cseq: set[int] = set()
        for idx, c in enumerate(corrs):
            if not isinstance(c, Mapping):
                continue
            did = str(c.get("decision_id") or "")
            if did not in dec_by_id:
                errs.append(f"corrections[{idx}] references unknown decision_id {did!r}")
            cseq = c.get("sequence")
            if isinstance(cseq, int) and not isinstance(cseq, bool):
                if cseq in seen_cseq:
                    errs.append(f"Duplicate correction sequence {cseq}")
                seen_cseq.add(cseq)

    return errs
