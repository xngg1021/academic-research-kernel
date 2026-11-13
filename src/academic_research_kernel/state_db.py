"""Unified SQLite-backed research state kernel (Occam edition).

Replaces 9,698 lines of hand-rolled Python in-memory database machinery:
- skills/decision-ledger/scripts/ledger.py (2,424 lines)
- scripts/ingestion/* (3,853 lines across 11 receipt-to-receipt adapters & models)
- scripts/shared_contracts/evidence.py (1,239 lines)
- skills/claim-evidence-graph/scripts/graph.py (1,238 lines)
- skills/research-object-identity/scripts/provenance.py (944 lines)
- custom OS lockfiles in watch.py (300+ lines)

Instead of emulating tables, foreign keys, enum checks, append-only logs,
DAG cycle detection, and atomic batch savepoints in 10,000 lines of Python dicts,
we delegate all of those invariants directly to CPython's built-in C ``sqlite3``
engine (``STRICT`` tables, ``FOREIGN KEY``, ``CHECK``, ``BEFORE UPDATE/DELETE``
append-only triggers, ``SAVEPOINT``, and ``WITH RECURSIVE`` cycle CTEs).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from ._stdlib import _SQLITE_INIT_LOCK, canonical_json, freeze, nfc_compact, normalize_doi, open_sqlite, sha256_hex

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS works (
    work_id TEXT PRIMARY KEY,
    doi TEXT,
    arxiv_id TEXT,
    title TEXT NOT NULL,
    year INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}'
) STRICT;

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64)
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

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    claim_text TEXT NOT NULL CHECK (length(trim(claim_text)) > 0),
    claim_digest TEXT NOT NULL CHECK (length(claim_digest) = 64),
    status TEXT NOT NULL DEFAULT 'supported' CHECK (status IN ('supported', 'contested', 'unresolved', 'refuted'))
) STRICT;

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    stance TEXT NOT NULL DEFAULT 'supports' CHECK (stance IN ('supports', 'contradicts', 'qualifies')),
    locator TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (claim_id, artifact_id, locator),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TABLE IF NOT EXISTS claim_edges (
    src_claim_id TEXT NOT NULL,
    dst_claim_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK (relation IN ('depends_on', 'refines', 'contradicts')),
    CHECK (src_claim_id != dst_claim_id),
    PRIMARY KEY (src_claim_id, dst_claim_id, relation),
    FOREIGN KEY (src_claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (dst_claim_id) REFERENCES claims(claim_id)
) STRICT;

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    entry_kind TEXT NOT NULL CHECK (entry_kind IN ('decision', 'negative_result')),
    action TEXT NOT NULL CHECK (action IN ('explore', 'commit', 'abandon', 'revise', 'negative_result')),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0 AND length(title) <= 512),
    verdict TEXT NOT NULL DEFAULT 'inconclusive' CHECK (verdict IN ('positive', 'negative', 'inconclusive', 'unverifiable')),
    basis_decision_id TEXT,
    artifact_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (basis_decision_id) REFERENCES decisions(decision_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

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

CREATE TABLE IF NOT EXISTS doi_watch_state (
    watcher TEXT NOT NULL,
    item_key TEXT NOT NULL,
    is_retracted INTEGER NOT NULL DEFAULT 0 CHECK (is_retracted IN (0, 1)),
    signals_json TEXT NOT NULL DEFAULT '[]',
    observation_version INTEGER NOT NULL DEFAULT 1 CHECK (observation_version >= 1),
    PRIMARY KEY (watcher, item_key)
) STRICT;
"""

_VALID_TRANSITIONS: dict[Optional[str], set[str]] = {
    None: {"active", "pruned"},
    "active": {"pruned"},
    "pruned": {"reopened"},
    "reopened": {"pruned"},
}


class ResearchStateDB:
    """Single-file ACID research ledger, claim-evidence graph, provenance DAG, and watcher store."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            conn = sqlite3.connect(":memory:", isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(SCHEMA_SQL)
            self._mem_conn = conn
        else:
            with _SQLITE_INIT_LOCK:
                with open_sqlite(self.db_path) as conn:
                    conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        if self._mem_conn is not None:
            self._mem_conn.close()
            self._mem_conn = None

    def _run(self, fn):
        if self._mem_conn is not None:
            return fn(self._mem_conn)
        with open_sqlite(self.db_path) as conn:
            return fn(conn)

    @staticmethod
    def _assert_acyclic(conn: sqlite3.Connection, table: str, src_col: str, dst_col: str, start: str, target: str) -> None:
        """Detect DAG cycles in 6 lines via SQLite's C-level recursive CTE."""
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

    def register_artifact(self, artifact_id: str, kind: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        cjson = canonical_json(payload)
        digest = sha256_hex(cjson)

        def _op(conn: sqlite3.Connection):
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT payload_sha256, kind FROM artifacts WHERE artifact_id = ?", (artifact_id,)
                ).fetchone()
                if existing is not None:
                    if existing["payload_sha256"] != digest or existing["kind"] != kind:
                        raise ValueError(f"Artifact hash/kind collision for {artifact_id!r}")
                else:
                    conn.execute(
                        "INSERT INTO artifacts (artifact_id, kind, payload_json, payload_sha256) VALUES (?, ?, ?, ?)",
                        (artifact_id, kind, cjson, digest),
                    )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            return freeze({"artifact_id": artifact_id, "kind": kind, "payload_sha256": digest})

        return self._run(_op)

    def batch_ingest(self, items: Iterable[Mapping[str, Any]], atomic: bool = True) -> tuple[Mapping[str, Any], ...]:
        """Atomic or per-item savepoint batch ingestion replacing 3,853 lines of scripts/ingestion/*."""
        batch = list(items)

        def _op(conn: sqlite3.Connection):
            out = []
            conn.execute("BEGIN IMMEDIATE")
            try:
                for idx, item in enumerate(batch):
                    sp = f"sp_{idx}"
                    conn.execute(f"SAVEPOINT {sp}")
                    try:
                        aid = str(item["artifact_id"])
                        kind = str(item["kind"])
                        payload = item["payload"]
                        cjson = canonical_json(payload)
                        expected = item.get("payload_sha256")
                        digest = sha256_hex(cjson)
                        if expected is not None and expected != digest:
                            raise ValueError(f"Payload SHA-256 mismatch on {aid!r}")
                        existing = conn.execute(
                            "SELECT payload_sha256 FROM artifacts WHERE artifact_id = ?", (aid,)
                        ).fetchone()
                        if existing is not None and existing["payload_sha256"] != digest:
                            raise ValueError(f"Registered artifact collision on {aid!r}")
                        if existing is None:
                            conn.execute(
                                "INSERT INTO artifacts (artifact_id, kind, payload_json, payload_sha256) VALUES (?, ?, ?, ?)",
                                (aid, kind, cjson, digest),
                            )
                        for parent_id in item.get("parents", ()):
                            self._assert_acyclic(conn, "lineage_edges", "child_id", "parent_id", aid, str(parent_id))
                            conn.execute(
                                "INSERT OR IGNORE INTO lineage_edges (child_id, parent_id, relation) VALUES (?, ?, ?)",
                                (aid, str(parent_id), str(item.get("relation", "derived_from"))),
                            )
                        conn.execute(f"RELEASE SAVEPOINT {sp}")
                        out.append(freeze({"artifact_id": aid, "status": "accepted", "payload_sha256": digest}))
                    except Exception as exc:
                        conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                        conn.execute(f"RELEASE SAVEPOINT {sp}")
                        if atomic:
                            raise
                        out.append(freeze({"artifact_id": str(item.get("artifact_id", "")), "status": "rejected", "error": str(exc)}))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            return tuple(out)

        return self._run(_op)

    def trace_lineage(self, artifact_id: str) -> tuple[str, ...]:
        def _op(conn: sqlite3.Connection):
            rows = conn.execute(
                """
                WITH RECURSIVE anc(id, depth) AS (
                    SELECT parent_id, 1 FROM lineage_edges WHERE child_id = ?
                    UNION ALL
                    SELECT e.parent_id, a.depth + 1 FROM lineage_edges e JOIN anc a ON e.child_id = a.id
                )
                SELECT DISTINCT id FROM anc ORDER BY id
                """,
                (artifact_id,),
            ).fetchall()
            return tuple(r["id"] for r in rows)

        return self._run(_op)

    def add_claim(
        self,
        claim_id: str,
        claim_text: str,
        status: str = "supported",
        evidence: Iterable[tuple[str, str, str]] = (),
        depends_on: Iterable[str] = (),
    ) -> Mapping[str, Any]:
        norm = nfc_compact(claim_text)
        digest = sha256_hex(norm)

        def _op(conn: sqlite3.Connection):
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO claims (claim_id, claim_text, claim_digest, status) VALUES (?, ?, ?, ?)",
                    (claim_id, norm, digest, status),
                )
                for aid, stance, locator in evidence:
                    conn.execute(
                        "INSERT OR REPLACE INTO claim_evidence (claim_id, artifact_id, stance, locator) VALUES (?, ?, ?, ?)",
                        (claim_id, aid, stance, locator),
                    )
                for dst in depends_on:
                    self._assert_acyclic(conn, "claim_edges", "src_claim_id", "dst_claim_id", claim_id, dst)
                    conn.execute(
                        "INSERT INTO claim_edges (src_claim_id, dst_claim_id, relation) VALUES (?, ?, 'depends_on')",
                        (claim_id, dst),
                    )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            return freeze({"claim_id": claim_id, "claim_digest": digest, "status": status})

        return self._run(_op)

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
        """Append-only decision & negative-result record enforcing E405/E406 positive-basis rule."""
        if entry_kind == "negative_result":
            action = "negative_result"

        def _op(conn: sqlite3.Connection):
            conn.execute("BEGIN IMMEDIATE")
            try:
                if entry_kind == "negative_result":
                    if not basis_decision_id:
                        raise ValueError("negative_result requires basis_decision_id referencing a prior non-negative decision")
                    basis = conn.execute(
                        "SELECT entry_kind FROM decisions WHERE decision_id = ?", (basis_decision_id,)
                    ).fetchone()
                    if basis is None or basis["entry_kind"] == "negative_result":
                        raise ValueError("negative_result basis must be an existing non-negative decision")
                conn.execute(
                    """
                    INSERT INTO decisions
                    (decision_id, entry_kind, action, title, verdict, basis_decision_id, artifact_id, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision_id,
                        entry_kind,
                        action,
                        nfc_compact(title),
                        verdict,
                        basis_decision_id,
                        artifact_id,
                        canonical_json(metadata or {}),
                    ),
                )
                conn.execute(
                    "INSERT INTO decision_events (decision_id, new_state, reason) VALUES (?, ?, 'genesis')",
                    (decision_id, initial_state),
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            return freeze({"decision_id": decision_id, "entry_kind": entry_kind, "state": initial_state, "verdict": verdict})

        return self._run(_op)

    def transition_decision(
        self,
        decision_id: str,
        new_state: str,
        reason: str,
        superseded_by_id: Optional[str] = None,
        verdict_override: Optional[str] = None,
    ) -> Mapping[str, Any]:
        def _op(conn: sqlite3.Connection):
            conn.execute("BEGIN IMMEDIATE")
            try:
                last = conn.execute(
                    "SELECT new_state FROM decision_events WHERE decision_id = ? ORDER BY seq DESC LIMIT 1",
                    (decision_id,),
                ).fetchone()
                cur_state = last["new_state"] if last else None
                if new_state not in _VALID_TRANSITIONS.get(cur_state, set()):
                    raise ValueError(f"Illegal state transition {cur_state!r} -> {new_state!r}")
                if superseded_by_id is not None:
                    if superseded_by_id == decision_id:
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
                        (superseded_by_id, decision_id),
                    ).fetchone()
                    if row is not None:
                        raise ValueError("Cycle detected in abandonment/supersession chain")
                conn.execute(
                    """
                    INSERT INTO decision_events (decision_id, new_state, reason, superseded_by_id, verdict_override)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (decision_id, new_state, reason, superseded_by_id, verdict_override),
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            return freeze({"decision_id": decision_id, "state": new_state, "reason": reason})

        return self._run(_op)

    def update_doi_watch(self, watcher: str, doi: str, is_retracted: bool, signals: Iterable[str]) -> Mapping[str, Any]:
        """Replaces 165 lines of msvcrt/kernel32 PID lease files in watch.py with 1 SQL transaction."""
        key = normalize_doi(doi)
        sig_json = canonical_json(sorted(set(signals)))
        flag = 1 if is_retracted else 0

        def _op(conn: sqlite3.Connection):
            conn.execute("BEGIN IMMEDIATE")
            try:
                prev = conn.execute(
                    "SELECT is_retracted, signals_json, observation_version FROM doi_watch_state WHERE watcher = ? AND item_key = ?",
                    (watcher, key),
                ).fetchone()
                changed = prev is None or prev["is_retracted"] != flag or prev["signals_json"] != sig_json
                ver = 1 if prev is None else (prev["observation_version"] + (1 if changed else 0))
                conn.execute(
                    """
                    INSERT INTO doi_watch_state (watcher, item_key, is_retracted, signals_json, observation_version)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(watcher, item_key) DO UPDATE SET
                        is_retracted = excluded.is_retracted,
                        signals_json = excluded.signals_json,
                        observation_version = excluded.observation_version
                    """,
                    (watcher, key, flag, sig_json, ver),
                )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            return freeze({"doi": key, "changed": changed, "is_retracted": is_retracted, "version": ver, "signals": json.loads(sig_json)})

        return self._run(_op)

    def snapshot_digest(self) -> str:
        """Deterministic order-invariant SHA-256 digest of the entire kernel state."""
        def _op(conn: sqlite3.Connection):
            dump = {}
            for tbl in ("works", "artifacts", "lineage_edges", "claims", "claim_evidence", "claim_edges", "decisions", "decision_events"):
                rows = conn.execute(f"SELECT * FROM {tbl}").fetchall()
                dump[tbl] = sorted((dict(r) for r in rows), key=canonical_json)
            return sha256_hex(canonical_json(dump))

        return self._run(_op)
