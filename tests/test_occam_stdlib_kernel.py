"""End-to-end security, semantic, and performance regression suite for the Occam stdlib-first kernel."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from types import MappingProxyType

import pytest

from academic_research_kernel import (
    cli,
    mcp_server,
    pre_submission_linter,
    recompute,
    venue_template_manager,
    watch,
)
from academic_research_kernel._stdlib import (
    ImmutableStateError,
    canonical_json,
    freeze,
    normalize_identifier,
    open_sqlite,
    safe_path,
    thaw,
)
from academic_research_kernel.research import analysis, sources
from academic_research_kernel.state_db import ResearchStateDB


def test_stdlib_deep_freeze_rejects_mutable_proxies_bools_and_key_collisions() -> None:
    inner_list = [1, 2]
    proxy_wrapping_mutable = MappingProxyType({"nested": inner_list})
    frozen = freeze({"outer": proxy_wrapping_mutable, "ok": True})
    inner_list.append(999)
    assert frozen["outer"]["nested"] == (1, 2)

    with pytest.raises(TypeError):
        frozen["outer"] = 0  # type: ignore[index]
    with pytest.raises(ValueError):
        freeze({"nan": float("nan")})
    with pytest.raises((TypeError, ValueError)):
        freeze({1: "a", "1": "b"})

    assert canonical_json(frozen) == '{"ok":true,"outer":{"nested":[1,2]}}'
    assert thaw(frozen) == {"ok": True, "outer": {"nested": [1, 2]}}


def test_safe_path_blocks_traversal_and_dangling_links_or_junctions(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside_secret"

    with pytest.raises(ValueError):
        safe_path(workspace / ".." / "escape.txt", root=workspace)

    link_path = workspace / "dangling_link"
    created_link = False
    try:
        os.symlink(outside, link_path, target_is_directory=True)
        created_link = True
    except (OSError, NotImplementedError):
        if sys.platform == "win32":
            outside.mkdir()
            cp = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(outside)],
                capture_output=True,
            )
            if cp.returncode == 0:
                outside.rmdir()
                created_link = True

    if created_link:
        with pytest.raises(ValueError, match="Symlink|reparse|escapes"):
            safe_path(link_path / "payload.json", root=workspace)


def test_sqlite_strict_append_only_recursive_triggers_and_dag_scaling(tmp_path: Path) -> None:
    db_file = tmp_path / "kernel.sqlite3"
    with ResearchStateDB(db_file) as db:
        res = db.batch_ingest(
            [
                {"artifact_id": "a1", "kind": "table_cell", "payload": {"rows": 10}},
                {"artifact_id": "a2", "kind": "computed_evidence", "payload": {"ok": True}, "parents": ["a1"]},
                {"artifact_id": "bad_hash", "kind": "computed_evidence", "payload": {"x": 1}, "payload_sha256": "0" * 64},
                {"artifact_id": "bad_kind", "kind": "bogus_kind", "payload": {"x": 1}},
            ],
            atomic=False,
        )
        assert [r["status"] for r in res] == ["accepted", "accepted", "rejected", "rejected"]
        assert db.trace_lineage("a2") == ("a1",)

        # Cycle detection
        with pytest.raises(ValueError, match="Cycle detected"):
            db.batch_ingest([{"artifact_id": "a1", "kind": "table_cell", "payload": {"rows": 10}, "parents": ["a2"]}])

        # Direct SQL DELETE AND INSERT OR REPLACE must BOTH be blocked by recursive BEFORE DELETE trigger
        with open_sqlite(db_file) as raw_conn:
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                raw_conn.execute("DELETE FROM artifacts WHERE artifact_id = 'a1'")
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                raw_conn.execute(
                    "INSERT OR REPLACE INTO artifacts(artifact_id, kind, payload_json, payload_sha256) "
                    "VALUES ('a1', 'table_cell', '{}', ?)",
                    ("f" * 64,),
                )

        # Claim idempotent replay vs conflicting mutation rejection
        c1 = db.add_claim("c1", "Sparse BM25 outperforms dense reranking", evidence=[("a2", "supports", "Table 2")])
        c1_idem = db.add_claim("c1", "Sparse BM25 outperforms dense reranking", evidence=[("a2", "supports", "Table 2")])
        assert c1_idem["claim_digest"] == c1["claim_digest"]
        with pytest.raises((ImmutableStateError, ValueError)):
            db.add_claim("c1", "Mutated opposite claim text", evidence=[("a2", "supports", "Table 2")])

        # Decisions & E405/E406 invariants
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
        db.transition_decision("d_pos", "pruned", "superseded", superseded_by_id="d_neg")
        with pytest.raises(ValueError, match="Illegal state transition"):
            db.transition_decision("d_pos", "pruned", "duplicate")
        with pytest.raises(ValueError, match="Cycle detected"):
            db.transition_decision("d_neg", "pruned", "superseded", superseded_by_id="d_pos")

        # 26-layer diamond DAG (2^25 > 33 million paths if UNION ALL; must finish in < 0.5s with UNION)
        diamond_items = [{"artifact_id": "d_0_a", "kind": "data_snapshot", "payload": {"layer": 0}},
                         {"artifact_id": "d_0_b", "kind": "data_snapshot", "payload": {"layer": 0}}]
        for lvl in range(1, 26):
            parents = [f"d_{lvl - 1}_a", f"d_{lvl - 1}_b"]
            diamond_items.append({"artifact_id": f"d_{lvl}_a", "kind": "data_snapshot", "payload": {"layer": lvl}, "parents": parents})
            diamond_items.append({"artifact_id": f"d_{lvl}_b", "kind": "data_snapshot", "payload": {"layer": lvl}, "parents": parents})
        db.batch_ingest(diamond_items, atomic=True)
        t0 = time.perf_counter()
        anc = db.trace_lineage("d_25_a")
        elapsed = time.perf_counter() - t0
        assert len(anc) == 50
        assert elapsed < 0.5

    # Unrelated SQLite file protection (ARK_SQLITE_APP_ID guard)
    foreign_db = tmp_path / "foreign.sqlite3"
    raw = sqlite3.connect(str(foreign_db))
    raw.execute("CREATE TABLE other_app(x INT)")
    raw.execute("PRAGMA application_id = 12345")
    raw.commit()
    raw.close()
    with pytest.raises(ValueError, match="application_id|not an academic-research-kernel"):
        ResearchStateDB(foreign_db)


def test_watch_three_state_offline_preservation_and_durable_outbox(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "watch.sqlite3"
    dois = ["10.1038/retracted.1", "10.1038/clean.2"]

    # 1. Confirm retraction for first DOI
    d1 = watch.check_retraction_signals(
        [dois[0]],
        db_path=db_file,
        mock_records={dois[0]: (True, ["retraction(crossref)"])},
    )
    assert len(d1) == 1 and d1[0]["is_retracted"] is True

    # 2. Offline check (live=False, no mock) MUST NOT wipe confirmed retraction to False
    d_offline = watch.check_retraction_signals([dois[0]], db_path=db_file, live=False)
    assert d_offline == []
    d_repeat = watch.check_retraction_signals(
        [dois[0]],
        db_path=db_file,
        mock_records={dois[0]: (True, ["retraction(crossref)"])},
    )
    assert d_repeat == []

    # 3. Mid-batch fatal process interruption recovery via durable outbox
    class _SimulatedProcessKill(BaseException):
        pass

    def _crashing_fetch_json(url: str) -> dict:
        if "clean.2" in url:
            if "openalex" in url:
                return {"is_retracted": True}
            return {"message": {"items": [], "total-results": 0}}
        raise _SimulatedProcessKill("aborted mid-batch before outbox drain")

    monkeypatch.setattr(watch, "_fetch_json", _crashing_fetch_json)
    with pytest.raises(_SimulatedProcessKill):
        watch.check_retraction_report([dois[1], "10.1038/timeout.3"], db_path=db_file, live=True)

    recovered = watch.check_retraction_report(
        [dois[1], "10.1038/timeout.3"],
        db_path=db_file,
        mock_records={
            dois[1]: (True, []),
            "10.1038/timeout.3": (False, []),
        },
    )
    recovered_dois = {d["doi"]: d["is_retracted"] for d in recovered["deltas"]}
    assert recovered_dois[dois[1]] is True

    # 4. Concurrent worker stress test
    batch_dois = [f"10.1038/conc.{i}" for i in range(12)]

    def _worker(i: int) -> int:
        mock = {batch_dois[i]: (i % 3 == 0, ["retraction(crossref)"] if i % 3 == 0 else [])}
        return len(watch.check_retraction_signals([batch_dois[i]], db_path=db_file, mock_records=mock))

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(_worker, range(12))) == 12
    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(_worker, range(12))) == 0


def test_mcp_bounded_frames_redaction_session_persistence_and_dual_pvalue(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    mcp_server.reset_session_db()

    # 1. Oversized frame (>10 MiB), invalid JSON, notification (no id), and Content-Length framing in one stream
    oversized = b'{"jsonrpc":"2.0","id":99,"data":"' + (b"x" * (mcp_server.MAX_MCP_FRAME_BYTES + 1024)) + b'"}\n'
    bad_json = b"{not-json}\n"
    notif = b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
    cl_body = json.dumps({"jsonrpc": "2.0", "id": 7, "method": "ping"}).encode("utf-8")
    cl_frame = f"Content-Length: {len(cl_body)}\r\n\r\n".encode("ascii") + cl_body

    in_buf = io.BytesIO(oversized + bad_json + notif + cl_frame)
    out_buf = io.BytesIO()
    rc = mcp_server.serve_stream(in_buf, out_buf)
    assert rc == 0
    raw_out = out_buf.getvalue().decode("utf-8")
    # Extract JSON objects (first two newline-delimited, third LSP Content-Length framed)
    lines = [json.loads(chunk) for chunk in raw_out.splitlines() if chunk.strip().startswith("{")]
    assert len(lines) == 3
    assert lines[0]["error"]["code"] == -32600
    assert lines[1]["error"]["code"] == -32700
    assert lines[2]["id"] == 7 and lines[2]["result"] == {}

    # 2. Session-scoped persistent :memory: DB across sequential tool calls + confined db_path guard
    try:
        r_ing = mcp_server.handle_tool_call("research_state_ingest", {
            "items": [{"artifact_id": "m1", "kind": "data_snapshot", "payload": {"k": 1}}],
        })
        assert r_ing["receipts"][0]["status"] == "accepted"
        r_claim = mcp_server.handle_tool_call("claim_evidence_add", {
            "claim_id": "mc1",
            "claim_text": "Session memory persists across calls",
            "evidence": [["m1", "supports", "sec1"]],
        })
        assert r_claim["status"] == "supported"

        with pytest.raises(ValueError):
            mcp_server.handle_tool_call("research_lineage_trace", {"artifact_id": "m1", "db_path": str(tmp_path.parent / "escape.db")})

        missing_db = tmp_path / ".ark-state" / "does_not_exist.sqlite3"
        with pytest.raises((FileNotFoundError, sqlite3.OperationalError, ValueError)):
            mcp_server.handle_tool_call("research_lineage_trace", {"artifact_id": "m1", "db_path": str(missing_db)})
        assert not missing_db.exists()

        # 3. Double-blind MCP scan MUST redact raw author names, emails, and URLs to [REDACTED]
        leak_tex = tmp_path / "leak.tex"
        leak_tex.write_text(
            "\\documentclass{article}\n\\author{ProfSecretName}\\begin{document}\n"
            "Contact secret.author@stanford.edu or https://github.com/secretuser/secretrepo\n\\end{document}\n",
            encoding="utf-8",
        )
        san = mcp_server.handle_tool_call("academic_sanitize_double_blind", {
            "target": str(leak_tex),
            "forbidden_tokens": ["ProfSecretName"],
        })
        dumped_san = json.dumps(san)
        assert "ProfSecretName" not in dumped_san
        assert "secret.author@stanford.edu" not in dumped_san
        assert "secretuser/secretrepo" not in dumped_san
        assert "[REDACTED]" in dumped_san

        # 4. Dual check of numeric p_value AND p_value_literal
        dual_bad = mcp_server.handle_tool_call("academic_recompute_stat", {
            "kind": "t_p",
            "t_stat": 2.5,
            "df": 28,
            "p_value": 0.90,
            "p_value_literal": "< 0.05",
        })
        assert dual_bad["consistent"] is False

        # 5. Meta-analysis includes leave_one_out + v2 compatibility alias works
        meta_res = mcp_server.handle_tool_call("run_meta_analysis", {
            "studies": [{"yi": 0.42, "vi": 0.04}, {"yi": 0.55, "vi": 0.05}, {"yi": 0.31, "vi": 0.03}],
        })
        assert len(meta_res["leave_one_out"]) == 3

        # 6. Work identity 5-state resolution wired properly
        wid_res = mcp_server.handle_tool_call("academic_resolve_work_identity", {
            "records": [
                {"source": "Crossref", "identifiers": [{"type": "doi", "value": "10.1145/12345.6789"}], "title": "Exact Kernel Verification", "year": 2025},
                {"source": "OpenAlex", "identifiers": [{"type": "doi", "value": "https://doi.org/10.1145/12345.6789"}], "title": "Exact Kernel Verification", "year": 2025},
            ],
        })
        assert wid_res["resolved"]["verdict"] == "EXACT"
    finally:
        mcp_server.reset_session_db()


def test_cli_exit_codes_csl_dispatch_cold_import_and_research_ceg_closed_loop(tmp_path: Path, capsys) -> None:
    proc = subprocess.run(
        [sys.executable, "-c", "import sys, academic_research_kernel.cli; assert 'scipy' not in sys.modules"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    assert cli.main(["doctor", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["status"] == "ok"
    assert doc["schema_resources"]["count"] == 26
    assert doc["research"]["portable_skill"] == "available"

    ms_dir = tmp_path / "paper"
    ms_dir.mkdir()
    (ms_dir / "refs.bib").write_text("@article{smith2024,\n  title={Clean Code}\n}\n", encoding="utf-8")
    tex_file = ms_dir / "main.tex"
    tex_file.write_text(
        "\\documentclass[final]{article}\n\\author{Real Person}\n\\begin{document}\n"
        "\\begin{abstract}Summary.\\end{abstract}\n"
        "\\section{Introduction}See \\cite{missing2026} and \\ref{sec:missing}.\n"
        "\\section*{Acknowledgments}Thanks Lab X.\n\\end{document}\n",
        encoding="utf-8",
    )
    assert cli.main(["pre-submission-lint", str(tex_file), "--venue", "iclr"]) == 1
    lint_out = json.loads(capsys.readouterr().out)
    codes = {f["code"] for f in lint_out["findings"]}
    assert {"UNDEFINED_CITATION", "UNRESOLVED_REFERENCE", "FINAL_MODE_IN_REVIEW", "BLIND_ACK_LEAK"} <= codes
    assert cli.main(["sanitize-blind", str(tex_file)]) == 1
    capsys.readouterr()

    csl_file = tmp_path / "items.csl.json"
    csl_file.write_text(
        json.dumps([{"id": "k1", "type": "article-journal", "title": "LLM Verification", "author": [{"family": "Shi", "given": "Junfu"}], "issued": {"date-parts": [[2026]]}, "DOI": "10.1000/llm"}]),
        encoding="utf-8",
    )
    assert cli.main(["bibliography", "--from", "csl", "--to", "bibtex", "--input", str(csl_file)]) == 0
    bib_txt = capsys.readouterr().out
    assert "{LLM}" in bib_txt and "10.1000/llm" in bib_txt

    src_tex = tmp_path / "study.tex"
    src_tex.write_text(
        "\\title{Statistical Audit Test}\n"
        "\\begin{abstract}\nWe evaluate N = 30 subjects with df = 28.\n\\end{abstract}\n"
        "\\section{Results}\nExperiment 1 yielded t = 2.50 with df = 28 and p = 0.0185 across N = 30 subjects "
        "in 2 groups of 15 and 15 over 3 runs, 4 metrics, 5 epochs, 6 seeds, and 7 checkpoints.\n",
        encoding="utf-8",
    )
    proj_dir = tmp_path / "research_proj"
    sources.prepare(src_tex, proj_dir)
    documents = json.loads((proj_dir / "documents.json").read_text("utf-8"))
    tex_doc = documents["documents"][0]
    doc_id = tex_doc["document_id"]
    seg_res = next(s for s in tex_doc["segments"] if "2.50" in s["text"])
    ctx = {"group": "all", "timepoint": "T1", "dataset": "synth", "analysis_set": "ITT", "condition": "main"}

    def _mk_f(fid: str, ftype: str, val: float | int, lit: str) -> dict:
        return {
            "id": fid,
            "name": fid,
            "type": ftype,
            "status": "extracted",
            "literal": lit,
            "value": val,
            "unit": None,
            "context": ctx.copy(),
            "sources": [{"document_id": doc_id, "locator": seg_res["locator"], "quote": seg_res["text"]}],
            "reason": None,
        }

    stmt = {"text": "Audit summary.", "field_ids": ["f_t", "f_df"]}
    cand_path = tmp_path / "candidate.json"
    cand_payload = {
        "schema_version": "1.0",
        "project_fingerprint": documents["fingerprint"],
        "paper": {"title": "Statistical Audit Test", "identifier": "10.1000/stat.2026", "version": "v1"},
        "producer": {"kind": "agent", "name": "pytest", "model": "test"},
        "search_scope": [doc_id],
        "fields": [
            _mk_f("f_t", "number", 2.5, "2.50"),
            _mk_f("f_df", "integer", 28, "28"),
            _mk_f("f_p", "p_value", 0.0185, "0.0185"),
            _mk_f("f_n", "integer", 30, "30"),
            _mk_f("f_g", "integer", 2, "2"),
            _mk_f("f_n1", "integer", 15, "15"),
            _mk_f("f_r", "integer", 3, "3"),
            _mk_f("f_m", "integer", 4, "4"),
            _mk_f("f_e", "integer", 5, "5"),
            _mk_f("f_s", "integer", 6, "6"),
        ],
        "summary": {"objective": stmt, "design": stmt, "main_results": stmt, "attention": stmt},
        "checks": [
            {
                "id": "chk_1",
                "kind": "t_p",
                "inputs": {"t_stat": "f_t", "df": "f_df"},
                "reported": "f_p",
                "tail": None,
                "note": "t test check",
            }
        ],
    }
    cand_path.write_text(json.dumps(cand_payload, indent=2), encoding="utf-8")

    fin = analysis.finish(proj_dir, cand_path)
    assert fin["ingestion"]["round_trip"] == "passed"
    assert fin["ingestion"]["object_count"] == 1
    run_dir = Path(fin["run_directory"])
    ceg_anchors = venue_template_manager.export_ceg_anchors(run_dir / "kernel-state.json")
    assert ceg_anchors["dangling_edges"] == []
    assert ceg_anchors["eligible_count"] >= 3

    (run_dir / "state.sqlite3").unlink()
    fin_rebuilt = analysis.finish(proj_dir, cand_path)
    assert fin_rebuilt.get("reused") is not True
    assert (run_dir / "state.sqlite3").is_file()


def test_openreview_iclr2027_schema_and_mcp_mirror_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from academic_research_kernel import cli, mcp_server, openreview_audit

    mirror_records = [
        {
            "id": "0h3CZLWS71",
            "title": "Brain-Inspired Agent Memory",
            "status": "Active",
            "primary_area": "foundation or frontier models, including LLMs",
            "rating": "3;3;4",
            "confidence": "3;4;4",
            "soundness": "2;3;3",
            "informativeness": "2;2;3",
            "presentation": "3;3;3",
            "wc_review": "480;512;610",
            "wc_summary": "80;90;100",
            "wc_strengths": "110;120;130",
            "wc_weaknesses": "190;192;240",
            "wc_questions": "100;110;140",
            "wc_reply_authors": "1250",
            "wc_reply_reviewers": "0;0;0",
        },
        {
            "id": "wxyz987654",
            "title": "Withdrawn Baseline",
            "status": "Withdraw",
            "primary_area": "reinforcement learning",
            "rating": "1;2;2",
            "confidence": "2;2;3",
            "soundness": "1;2;2",
            "informativeness": "1;1;2",
            "presentation": "2;2;2",
            "wc_review": "500;490;510",
            "wc_reply_authors": "",
            "wc_reply_reviewers": "",
        },
    ]
    mirror_file = tmp_path / "iclr2027_sample.json"
    mirror_file.write_text(json.dumps(mirror_records), encoding="utf-8")

    rc = cli.main(["openreview-audit", "--forum-id", "0h3CZLWS71", "--mirror-json", str(mirror_file)])
    assert rc == 0
    cli_out = json.loads(capsys.readouterr().out)
    assert cli_out["ratings"] == [3.0, 3.0, 4.0]
    assert cli_out["informativeness"] == [2.0, 2.0, 3.0]
    assert cli_out["contribution"] == []
    assert cli_out["review_word_counts"] == [480, 512, 610]
    assert cli_out["question_word_counts"] == [100, 110, 140]
    assert cli_out["author_rebuttal_word_counts"] == [1250]
    assert cli_out["reviewer_reply_word_counts"] == [0, 0, 0]
    assert cli_out["did_authors_rebut"] is True
    assert cli_out["did_reviewers_reply"] is False
    assert cli_out["verification_status"] == "unverified_local_mirror"

    mcp_single = mcp_server.handle_tool_call(
        "academic_openreview_audit",
        {"forum_id": "0h3CZLWS71", "notes": mirror_records},
    )
    assert mcp_single["informativeness"] == [2.0, 2.0, 3.0]
    assert mcp_single["review_word_counts"] == [480, 512, 610]

    vs = openreview_audit.summarize_venue_mirror(mirror_records)
    assert vs["total_submissions"] == 2
    assert vs["total_reviews"] == 6
    assert vs["subscore_means"]["informativeness"] == 1.833
    assert vs["subscore_means"]["contribution"] is None
    assert vs["review_word_count_stats"] == {"count": 6, "mean": 517.0, "median": 505.0}

    v2_notes = {
        "count": 3,
        "notes": [
            {"id": "f2027", "forum": "f2027", "content": {"title": {"value": "CLM"}, "venue": {"value": "Submitted to ICLR 2027"}}},
            {
                "id": "r1",
                "forum": "f2027",
                "invitations": ["ICLR.cc/2027/Conference/Submission1/-/Official_Review"],
                "content": {
                    "overall_decision": {"value": "4: Clear acceptance"},
                    "confidence": {"value": "4: Expert"},
                    "soundness": {"value": "3: Good"},
                    "informativeness": {"value": "3: High"},
                    "presentation": {"value": "3: Clear"},
                },
            },
            {
                "id": "r2",
                "forum": "f2027",
                "invitations": ["ICLR.cc/2027/Conference/Submission1/-/Official_Review"],
                "content": {
                    "overall_decision": {"value": "3: Weak acceptance"},
                    "confidence": {"value": "3: Fairly confident"},
                    "soundness": {"value": "3: Good"},
                    "informativeness": {"value": "2: Moderate"},
                    "presentation": {"value": "2: Readable"},
                },
            },
        ],
    }
    parsed_v2 = openreview_audit.parse_openreview_notes(v2_notes, forum_id="f2027")
    assert parsed_v2["ratings"] == [4.0, 3.0]
    assert parsed_v2["informativeness"] == [3.0, 2.0]
    assert parsed_v2["soundness"] == [3.0, 3.0]
    assert parsed_v2["status_classification"] == "under_review"


def test_openreview_live_403_mirror_fallback_and_reparse_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from urllib.error import HTTPError
    from academic_research_kernel import openreview_audit

    mirror_dir = tmp_path / "mirrors"
    mirror_dir.mkdir()
    snap = mirror_dir / "iclr2027_20261112.json"
    snap.write_text(
        json.dumps([{"id": "U1ObEVC4A7", "title": "Context Language Models", "status": "Active", "rating": "4;4;4", "informativeness": "3;3;2"}]),
        encoding="utf-8",
    )

    def _mock_403(forum_id: str, max_bytes: int = 16777216):
        raise HTTPError("https://api2.openreview.net/notes", 403, "Forbidden", hdrs=None, fp=None)

    monkeypatch.setattr(openreview_audit, "fetch_openreview_forum", _mock_403)
    monkeypatch.setenv("OPENREVIEW_MIRROR_DIR", str(mirror_dir))

    res = openreview_audit.audit_forum("U1ObEVC4A7")
    assert res["forum_id"] == "U1ObEVC4A7"
    assert res["ratings"] == [4.0, 4.0, 4.0]
    assert res["informativeness"] == [3.0, 3.0, 2.0]
    assert res["verification_status"] == "unverified_local_mirror"
    assert len(res["mirror_sha256"]) == 64


def test_cold_cli_import_and_manifest_version_lockstep() -> None:
    import subprocess
    import sys
    import typing
    from academic_research_kernel import __version__, _stdlib

    hints = typing.get_type_hints(_stdlib.configure_sqlite_connection)
    assert "conn" in hints

    src_root = str(Path(__file__).resolve().parents[1] / "src")
    cp = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, {src_root!r}); import academic_research_kernel.cli; "
            "assert 'scipy' not in sys.modules and 'sqlite3' not in sys.modules, [m for m in ('scipy','sqlite3') if m in sys.modules]",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert cp.returncode == 0

    repo_root = Path(__file__).resolve().parents[1]
    for manifest_name in ("plugin.json", "server.json"):
        mpath = repo_root / manifest_name
        if mpath.is_file():
            mdata = json.loads(mpath.read_text(encoding="utf-8"))
            assert mdata["version"] == __version__
            for pkg_entry in mdata.get("packages", []):
                assert pkg_entry["version"] == __version__
