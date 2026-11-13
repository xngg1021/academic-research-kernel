"""End-to-end verification suite for the Occam stdlib-first academic-research-kernel."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
from types import MappingProxyType

import pytest

from academic_research_kernel import cli, mcp_server, meta_core, pre_submission_linter, recompute, watch
from academic_research_kernel._stdlib import canonical_json, freeze, normalize_identifier, open_sqlite, thaw
from academic_research_kernel.state_db import ResearchStateDB


def test_stdlib_mapping_proxy_replaces_frozendict() -> None:
    frozen = freeze({"alpha": [1, {"beta": 2.5}], "ok": True})
    assert isinstance(frozen, MappingProxyType)
    assert isinstance(frozen["alpha"], tuple)
    assert isinstance(frozen["alpha"][1], MappingProxyType)
    with pytest.raises(TypeError):
        frozen["alpha"] = 99  # type: ignore[index]
    with pytest.raises(ValueError):
        freeze({"nan": float("nan")})
    assert canonical_json(frozen) == '{"alpha":[1,{"beta":2.5}],"ok":true}'
    assert thaw(frozen) == {"alpha": [1, {"beta": 2.5}], "ok": True}


def test_sqlite_strict_append_only_dag_and_savepoints(tmp_path: Path) -> None:
    db_file = tmp_path / "kernel.sqlite3"
    db = ResearchStateDB(db_file)
    try:
        # 1. Batch ingest with SAVEPOINT isolation (non-atomic keeps valid items, rolls back bad ones)
        res = db.batch_ingest(
            [
                {"artifact_id": "a1", "kind": "table", "payload": {"rows": 10}},
                {"artifact_id": "a2", "kind": "audit", "payload": {"ok": True}, "parents": ["a1"]},
                {"artifact_id": "bad", "kind": "audit", "payload": {"x": 1}, "payload_sha256": "0" * 64},
            ],
            atomic=False,
        )
        assert [r["status"] for r in res] == ["accepted", "accepted", "rejected"]
        assert db.trace_lineage("a2") == ("a1",)

        # 2. Cycle detection via SQLite recursive CTE
        with pytest.raises(ValueError, match="Cycle detected"):
            db.batch_ingest([{"artifact_id": "a1", "kind": "table", "payload": {"rows": 10}, "parents": ["a2"]}])

        # 3. Append-only trigger blocks direct SQL UPDATE/DELETE tampering
        with open_sqlite(db_file) as raw_conn:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                raw_conn.execute("DELETE FROM artifacts WHERE artifact_id = 'a1'")

        # 4. Decisions & E405/E406 negative-result positive-basis invariant
        with pytest.raises(ValueError, match="basis_decision_id"):
            db.record_decision("neg_orphan", "Failed route without basis", entry_kind="negative_result")

        db.record_decision("d_pos", "Explore sparse BM25", action="explore", verdict="positive", artifact_id="a1")
        neg = db.record_decision(
            "d_neg",
            "Cross-encoder reranker degraded recall",
            entry_kind="negative_result",
            verdict="negative",
            basis_decision_id="d_pos",
        )
        assert neg["entry_kind"] == "negative_result"

        # 5. State transitions & supersession cycle check
        db.transition_decision("d_pos", "pruned", "superseded", superseded_by_id="d_neg")
        with pytest.raises(ValueError, match="Illegal state transition"):
            db.transition_decision("d_pos", "pruned", "duplicate")
        with pytest.raises(ValueError, match="Cycle detected"):
            db.transition_decision("d_neg", "pruned", "superseded", superseded_by_id="d_pos")

        # 6. Claims & order-invariant snapshot digest
        c1 = db.add_claim("c1", "Sparse BM25 outperforms dense reranking", evidence=[("a2", "supports", "Table 2")])
        assert len(c1["claim_digest"]) == 64
        assert len(db.snapshot_digest()) == 64
    finally:
        db.close()


def test_sqlite_concurrent_doi_watch_replaces_os_lockfiles(tmp_path: Path) -> None:
    db_file = tmp_path / "watch.sqlite3"
    dois = [f"10.1038/test.{i}" for i in range(12)]

    def _worker(i: int) -> int:
        mock = {dois[i]: (i % 3 == 0, ["retraction(crossref)"] if i % 3 == 0 else [])}
        deltas = watch.check_retraction_signals([dois[i]], db_path=db_file, mock_records=mock)
        return len(deltas)

    with ThreadPoolExecutor(max_workers=6) as pool:
        first_counts = list(pool.map(_worker, range(12)))
    assert sum(first_counts) == 12

    # Second identical run produces 0 deltas (idempotent state)
    with ThreadPoolExecutor(max_workers=6) as pool:
        second_counts = list(pool.map(_worker, range(12)))
    assert sum(second_counts) == 0


def test_statistics_meta_lint_cli_and_mcp_end_to_end(tmp_path: Path, capsys) -> None:
    # 1. Statistical recompute & meta-analysis
    t_res = recompute.p_from_t(2.5, 28, reported=0.0185)
    assert abs(t_res["difference"]) < 1e-3
    studies = [{"yi": 0.42, "vi": 0.04}, {"yi": 0.55, "vi": 0.05}, {"yi": 0.31, "vi": 0.03}]
    meta_out = mcp_server.handle_tool_call("academic_meta_analyze", {"studies": studies})
    assert meta_out["study_count"] == 3
    assert 0.3 < meta_out["random_effects_dl"]["estimate"] < 0.6

    # 2. Pre-submission TeX linter
    ms_dir = tmp_path / "paper"
    ms_dir.mkdir()
    (ms_dir / "refs.bib").write_text("@article{smith2024,\n  title={Clean Code}\n}\n@article{unused2025,\n  title={Unused}\n}\n", encoding="utf-8")
    tex_file = ms_dir / "main.tex"
    tex_file.write_text(
        r"\documentclass{article}" + "\n"
        r"\begin{document}" + "\n"
        r"\begin{abstract}Clean summary.\end{abstract}" + "\n"
        r"\section{Introduction}See \cite{smith2024,missing2026}." + "\n"
        r"\section{Limitations}Bounded scope." + "\n"
        r"\end{document}" + "\n",
        encoding="utf-8",
    )
    lint_res = pre_submission_linter.lint_manuscript(tex_file, venue="iclr")
    codes = {f["code"] for f in lint_res["findings"]}
    assert "UNDEFINED_CITATION" in codes
    assert "UNCITED_BIB_ENTRY" in codes

    # 3. CLI doctor & MCP JSON-RPC 2.0 round-trip
    rc = cli.main(["doctor", "--json"])
    assert rc == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["status"] == "ok"

    rpc_init = mcp_server.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert rpc_init is not None and rpc_init["result"]["serverInfo"]["name"] == "academic-research-kernel"
    rpc_call = mcp_server.handle_rpc({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "academic_verify_source", "arguments": {"identifier": "https://arxiv.org/abs/2401.12345v2"}},
    })
    assert rpc_call is not None and rpc_call["result"]["isError"] is False
    assert normalize_identifier("https://doi.org/10.1145/12345.6789")["canonical"] == "doi:10.1145/12345.6789"
