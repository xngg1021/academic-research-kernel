"""Regression suite locking in all 28 counterexamples from the v3.0.0 independent source audit (3 P0, 18 P1, 7 P2)."""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tarfile
import threading
from unittest import mock
import zipfile

import pytest

from academic_research_kernel import (
    cli,
    collect_corpus,
    compute_probe,
    cross_review,
    double_blind_sanitizer,
    github_repo_forensics,
    locate_oa,
    mcp_server,
    meta_core,
    openreview_audit,
    pre_submission_linter,
    release_gate,
    venue_template_manager,
)
from academic_research_kernel._stdlib import canonical_json, sha256_hex, thaw
from academic_research_kernel.research import sources
from academic_research_kernel.state_db import (
    KIND_SCHEMA_MAP,
    ResearchStateDB,
    validate_decision_ledger_semantics,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _recompute_record_bytes(entries: dict[str, bytes], dist_info_dir: str) -> bytes:
    rec_path = f"{dist_info_dir}/RECORD"
    lines: list[str] = []
    for name in sorted(entries):
        if name == rec_path:
            continue
        raw = entries[name]
        b64 = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode("ascii")
        lines.append(f"{name},sha256={b64},{len(raw)}")
    lines.append(f"{rec_path},,")
    return ("\n".join(lines) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# P0 Blockers (P0-01 .. P0-03)
# ---------------------------------------------------------------------------


def test_p0_01_release_gate_rejects_wheel_missing_entrypoints_and_sdist_missing_sources(tmp_path: Path) -> None:
    from academic_research_kernel import __version__ as ver

    dist_info = f"academic_research_kernel-{ver}.dist-info"
    src_pkg = REPO_ROOT / "src"
    exp_wheel = {
        p.relative_to(src_pkg).as_posix(): p.read_bytes()
        for p in src_pkg.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc")
    }

    whl_entries: dict[str, bytes] = dict(exp_wheel)
    for l_rel in ("LICENSE", "LICENSE-APPLICATION.md", "LICENSE-HISTORY.md", "SOURCE-LINEAGE.md", "LICENSES/MIT-pre-SLL.txt"):
        whl_entries[f"{dist_info}/licenses/{l_rel}"] = (REPO_ROOT / l_rel).read_bytes()
    whl_entries[f"{dist_info}/METADATA"] = (
        f"Metadata-Version: 2.4\nName: academic-research-kernel\nVersion: {ver}\n"
        "Requires-Python: >=3.10,<3.15\n"
        "License-Expression: LicenseRef-Source-Lineage-1.0\n"
        "Requires-Dist: jsonschema>=4.23,<5\nRequires-Dist: numpy>=1.26,<3\n"
        "Requires-Dist: scipy>=1.11,<2\nRequires-Dist: statsmodels>=0.14,<0.16\n"
    ).encode("utf-8")
    whl_entries[f"{dist_info}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    # Intentionally omit entry_points.txt and compute valid RECORD hashes for remaining files
    whl_entries[f"{dist_info}/RECORD"] = _recompute_record_bytes(whl_entries, dist_info)

    whl_dir1 = tmp_path / "d1"
    whl_dir1.mkdir()
    bad_whl = whl_dir1 / f"academic_research_kernel-{ver}-py3-none-any.whl"
    with zipfile.ZipFile(bad_whl, "w") as zf:
        for k, v in whl_entries.items():
            zf.writestr(k, v)

    with pytest.raises(ValueError, match="entry_points.txt"):
        release_gate.inspect_artifact(bad_whl, ver, source_root=REPO_ROOT)

    # Also verify a wheel WITH entry_points.txt but missing a package module is rejected
    whl_missing_src = dict(whl_entries)
    whl_missing_src[f"{dist_info}/entry_points.txt"] = (
        b"[console_scripts]\nacademic-research-kernel = academic_research_kernel.cli:main\n"
    )
    del whl_missing_src["academic_research_kernel/compute_probe.py"]
    whl_missing_src[f"{dist_info}/RECORD"] = _recompute_record_bytes(whl_missing_src, dist_info)
    whl_dir2 = tmp_path / "d2"
    whl_dir2.mkdir()
    bad_whl2 = whl_dir2 / f"academic_research_kernel-{ver}-py3-none-any.whl"
    with zipfile.ZipFile(bad_whl2, "w") as zf:
        for k, v in whl_missing_src.items():
            zf.writestr(k, v)
    with pytest.raises(ValueError, match="wheel package member set differs"):
        release_gate.inspect_artifact(bad_whl2, ver, source_root=REPO_ROOT)

    # Build an sdist deleting all src/ members while keeping top-level metadata and skills/
    prefix = f"academic_research_kernel-{ver}"
    bad_sdist = whl_dir1 / f"academic_research_kernel-{ver}.tar.gz"
    with tarfile.open(bad_sdist, "w:gz") as tf:
        for top_name in (
            "pyproject.toml", "README.md", "LICENSE", "LICENSES/MIT-pre-SLL.txt",
            "server.json", "plugin.json", "mcp.json", "SLL-APPLICATION.json", "CHANGELOG.md", "uv.lock", "PKG-INFO",
        ):
            src_f = REPO_ROOT / top_name
            payload = src_f.read_bytes() if src_f.is_file() else f"Metadata-Version: 2.4\nName: academic-research-kernel\nVersion: {ver}\n".encode("utf-8")
            ti = tarfile.TarInfo(f"{prefix}/{top_name}")
            ti.size = len(payload)
            tf.addfile(ti, io.BytesIO(payload))

    with pytest.raises(ValueError, match="sdist missing required asset or source module"):
        release_gate.inspect_artifact(bad_sdist, ver, source_root=REPO_ROOT)


def test_p0_02_cross_review_rejects_out_of_range_and_partial_proposal_stances() -> None:
    mk = lambda pol: {
        "target": "x.py",
        "issue_key": "validation",
        "polarity": pol,
        "severity": "P1",
        "claim": "valid" if pol == "valid" else "invalid",
        "evidence": ["x.py:1"],
    }
    reg, chals, skip = cross_review.plan_challenges(
        ["a", "b", "c"],
        {"a": {"findings": [mk("valid")]}, "b": {"findings": [mk("invalid")]}, "c": {"findings": []}},
    )
    cid = chals[0]["challenge_id"]
    for bad_reply in (
        "",
        "【CONCEDE】 Proposal-999: ok",
        "【CONCEDE】 Proposal-1: ok",
        "【REFUTED】 Proposal-1: no\n【REFUTED】 Proposal-2: no",
        "【CONCEDE】 【REFUTED】 Proposal-1: mixed\n【CONCEDE】 Proposal-2: ok",
    ):
        res = cross_review.synthesize_deliberation(reg, chals, {cid: bad_reply}, skipped_challenges=skip)
        assert res["convergence_status"] != "CONVERGED"
        assert len(res["uncontested_contradictions"]) == 1

    good = cross_review.synthesize_deliberation(
        reg, chals, {cid: "【CONCEDE】 Proposal-1: verified\n【REFUTED】 Proposal-2: disproved"}, skipped_challenges=skip
    )
    assert good["convergence_status"] == "CONVERGED"

    # Singleton minority claim with evidence must NOT be deleted by Proposal-999
    reg1, chals1, skip1 = cross_review.plan_challenges(["a", "b"], {"a": {"findings": [mk("valid")]}, "b": {"findings": []}})
    res_s = cross_review.synthesize_deliberation(reg1, chals1, {chals1[0]["challenge_id"]: "【REFUTED】 Proposal-999: no"}, skipped_challenges=skip1)
    assert res_s["convergence_status"] == "PARTIAL_PROGRESS"
    assert len(res_s["unresolved_ledger"]) == 1


def test_p0_03_cross_review_invalidates_stale_challenge_replies_on_task_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    stream = tmp_path / "stream"
    task = tmp_path / "task.txt"
    task.write_text("Audit old.py", encoding="utf-8")
    spec = [cross_review.ParticipantSpec(s, executor="mock") for s in ("a", "b", "c")]

    def _seed(key: str) -> None:
        for s, pol in (("a", "valid"), ("b", "invalid"), ("c", None)):
            items = [] if pol is None else [{
                "target": f"{key}.py",
                "issue_key": key,
                "severity": "P1",
                "polarity": pol,
                "claim": f"{key} is {pol}",
                "evidence": [f"{key}.py:1"],
            }]
            (stream / f"findings-{s}.json").write_text(json.dumps({"findings": items}), encoding="utf-8")

    cross_review.stage_plan(stream, task, spec)
    _seed("old")
    cross_review.stage_merge(stream, spec)
    ch0 = json.loads((stream / "challenge-plan.json").read_text("utf-8"))[0]
    stale_reply = stream / f"challenge-reply-{ch0['challenge_id']}-{ch0['reviewer']}.md"
    stale_reply.write_text("【CONCEDE】 Proposal-1: old.py verified\n【REFUTED】 Proposal-2: old.py disproved", encoding="utf-8")

    # Change task to new.py, re-plan and re-merge WITHOUT running stage_challenge
    task.write_text("Audit new.py", encoding="utf-8")
    cross_review.stage_plan(stream, task, spec)
    assert not stale_reply.exists()
    _seed("new")
    cross_review.stage_merge(stream, spec)

    # Even if an unverified reply file is dropped in manually without matching run_id/task_sha256/reply_sha256 metadata, synthesize rejects it
    ch1 = json.loads((stream / "challenge-plan.json").read_text("utf-8"))[0]
    injected = stream / f"challenge-reply-{ch1['challenge_id']}-{ch1['reviewer']}.md"
    injected.write_text("【CONCEDE】 Proposal-1: old.py verified\n【REFUTED】 Proposal-2: old.py disproved", encoding="utf-8")
    res = cross_review.stage_synthesize(stream)
    assert res["convergence_status"] == "PARTIAL_PROGRESS"
    assert res["missing_challenges"] == 1


# ---------------------------------------------------------------------------
# P1 Important Findings (P1-01 .. P1-18)
# ---------------------------------------------------------------------------


def test_p1_01_cli_ledger_rejects_unregistered_artifact_ids(tmp_path: Path) -> None:
    db_file = tmp_path / "empty.sqlite3"
    rc_claim = cli.main([
        "ledger", "--db", str(db_file), "--action", "add-claim",
        "--claim-id", "c1", "--text", "Treatment eliminates all mortality.",
        "--artifact-id", "never_existed", "--locator", "Imaginary Table 1",
    ])
    assert rc_claim == 1

    assert cli.main(["ledger", "--db", str(db_file), "--action", "record-decision", "--decision-id", "d0", "--title", "Base"]) == 0
    rc_neg = cli.main([
        "ledger", "--db", str(db_file), "--action", "record-decision",
        "--decision-id", "n1", "--basis-decision-id", "d0", "--title", "Neg",
        "--is-negative-result", "--artifact-id", "ghost_artifact",
    ])
    assert rc_neg == 1


def test_p1_02_all_formal_artifact_kinds_enforce_packaged_json_schemas() -> None:
    schemas_dir = REPO_ROOT / "src" / "academic_research_kernel" / "schemas"
    expected_schema_files = {p.name for p in schemas_dir.glob("*.schema.json")}
    assert set(KIND_SCHEMA_MAP.values()) == expected_schema_files
    assert len(expected_schema_files) == 26

    mcp_server.reset_session_db()
    for formal_kind in ("reproduction_receipt", "lineage_receipt", "retraction_delta", "systematic_review", "compute_receipt"):
        resp = mcp_server.process_message({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "research_artifact_ingest", "arguments": {"artifact_id": f"bad-{formal_kind}", "kind": formal_kind, "payload": {}}},
        })
        assert resp["result"]["isError"] is True


def test_p1_03_contested_db_claims_export_contested_and_ineligible() -> None:
    with ResearchStateDB() as db:
        db.register_artifact("e", "source", {"value": 1})
        db.add_claim("a", "Model improves accuracy.", evidence=[("e", "supports", "1")], metadata={"status": "supported"})
        db.add_claim("b", "Model worsens accuracy.", evidence=[("e", "supports", "2")], metadata={"status": "supported"})
        db.add_claim_relation("a", "b", "contradicts")
        doc = thaw(db.export_ceg_dict())
    assert {c["id"]: c["metadata"]["status"] for c in doc["claims"]} == {"a": "contested", "b": "contested"}
    sem = venue_template_manager.validate_ceg_semantics(doc)
    assert sem["eligible_count"] == 0
    assert sem["conflicted_count"] == 2


def test_p1_04_ceg_manuscript_binding_rejects_direction_sign_and_unit_flips(tmp_path: Path) -> None:
    cases = [
        ("direction", "Latency decreases by 40%.", r"Latency increases by 40\%."),
        ("sign", "Treatment effect is -40 units.", "Treatment effect is +40 units."),
        ("unit", "Latency is 40 milliseconds.", "Latency is 40 seconds."),
    ]
    for label, claim_txt, stmt in cases:
        with ResearchStateDB() as db:
            db.register_artifact("a", "source", {"text": claim_txt})
            db.add_claim("c", claim_txt, evidence=[("a", "supports", "line 1")])
            doc = thaw(db.export_ceg_dict())
        g_path = tmp_path / f"{label}_ceg.json"
        g_path.write_text(json.dumps(doc), encoding="utf-8")
        m_path = tmp_path / f"{label}.tex"
        m_path.write_text(
            "\\documentclass{article}\n\\begin{document}\n\\begin{abstract}Study.\\end{abstract}\n"
            f"{stmt} % ark:claim=c\n\\end{{document}}\n",
            encoding="utf-8",
        )
        rep = pre_submission_linter.lint_manuscript(m_path, venue=None, double_blind=False, ceg_path=g_path, require_ceg_binding=True)
        assert rep["passed"] is False, f"{label} should fail required CEG binding"
        assert any(f["code"] == "CEG_CLAIM_TEXT_MISMATCH" for f in rep["findings"])


def test_p1_05_decision_ledger_json_validator_catches_sequence_genesis_uncertainty_and_digest_tampering() -> None:
    with ResearchStateDB() as db:
        db.record_decision("d", "Decision")
        db.record_decision("n", "Negative", entry_kind="negative_result", action="negative_result", basis_decision_id="d")
        db.correct_decision_outcome("d", "negative", "Correction 1")
        db.correct_decision_outcome("d", "positive", "Correction 2")
        ledger = thaw(db.export_decision_ledger_dict())

    assert validate_decision_ledger_semantics(ledger) == []

    c1 = copy.deepcopy(ledger)
    c1["corrections"].reverse()
    assert any("sequence" in e for e in validate_decision_ledger_semantics(c1))

    c2 = copy.deepcopy(ledger)
    c2["state_events"] = []
    assert any("genesis" in e for e in validate_decision_ledger_semantics(c2))

    c3 = copy.deepcopy(ledger)
    c3["uncertainties"] = []
    assert any("unsupported_negative_result" in e for e in validate_decision_ledger_semantics(c3))

    c4 = copy.deepcopy(ledger)
    c4["ledger_digest"] = "0" * 64
    c4["verification_digest"] = "0" * 64
    assert any("digest mismatch" in e for e in validate_decision_ledger_semantics(c4))


def test_p1_06_decision_ledger_preserves_verdict_override_and_correction_manifest_receipts() -> None:
    with ResearchStateDB() as db:
        db.record_decision("d", "Decision", verdict="positive")
        db.transition_decision("d", "pruned", "contradicted", verdict_override="negative")
        ledger_ov = thaw(db.export_decision_ledger_dict())
        assert ledger_ov["decisions"][0]["metadata"]["initial_verdict"] == "positive"
        assert ledger_ov["decisions"][0]["metadata"]["verdict"] == "negative"
        assert len(ledger_ov["corrections"]) == 1
        assert ledger_ov["corrections"][0]["verdict"] == "negative"
        assert validate_decision_ledger_semantics(ledger_ov) == []

    with ResearchStateDB() as db:
        db.register_artifact("corr-ev", "source", {"data": 42})
        db.record_decision("d", "Decision")
        db.correct_decision_outcome("d", "negative", "Evidence changed", "corr-ev")
        ledger_ce = thaw(db.export_decision_ledger_dict())
        assert "corr-ev" in ledger_ce["verification_manifest"]
        assert validate_decision_ledger_semantics(ledger_ce) == []


def test_p1_07_trace_lineage_verified_uses_single_atomic_read_snapshot(tmp_path: Path) -> None:
    db_file = tmp_path / "race.sqlite3"
    with ResearchStateDB(db_file) as db:
        for aid in ("target", "old-parent", "new-parent"):
            db.register_artifact(aid, "source", {"marker": aid})
        db.batch_ingest([{"artifact_id": "target", "kind": "source", "payload": {"marker": "target"}, "parents": ["old-parent"]}])

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("trace_lineage_verified must not open a separate trace_lineage snapshot")

        with mock.patch.object(db, "trace_lineage", side_effect=_fail_if_called):
            traced = db.trace_lineage_verified("target")
        assert traced["ancestors"] == ["old-parent"]
        assert traced["root_ancestors"] == ["old-parent"]
        assert traced["chain_length"] == 1
        assert traced["verification_status"] == "intact"


def test_p1_08_legacy_v3_sqlite_schema_migrates_claim_edges_triggers_in_place(tmp_path: Path) -> None:
    db_file = tmp_path / "legacy_v3.sqlite3"
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute("PRAGMA application_id = 0x41524B33")
        conn.execute("PRAGMA user_version = 3")
        conn.executescript(
            """
            CREATE TABLE claims (
                claim_id TEXT PRIMARY KEY,
                claim_text TEXT NOT NULL,
                claim_digest TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('supported', 'contested', 'unresolved', 'refuted')),
                metadata_json TEXT NOT NULL DEFAULT '{}'
            ) STRICT;
            CREATE TABLE claim_edges (
                src_claim_id TEXT NOT NULL,
                dst_claim_id TEXT NOT NULL,
                relation TEXT NOT NULL CHECK (relation IN ('depends_on', 'refines', 'contradicts')),
                CHECK (src_claim_id != dst_claim_id),
                PRIMARY KEY (src_claim_id, dst_claim_id, relation),
                FOREIGN KEY (src_claim_id) REFERENCES claims(claim_id),
                FOREIGN KEY (dst_claim_id) REFERENCES claims(claim_id)
            ) STRICT;
            CREATE TRIGGER trg_claim_edges_no_cycle
            BEFORE INSERT ON claim_edges
            BEGIN
                SELECT CASE WHEN EXISTS (
                    WITH RECURSIVE reach(node) AS (
                        SELECT NEW.dst_claim_id
                        UNION
                        SELECT e.dst_claim_id FROM claim_edges e JOIN reach r ON e.src_claim_id = r.node
                    )
                    SELECT 1 FROM reach WHERE node = NEW.src_claim_id
                ) THEN RAISE(ABORT, 'Cycle detected in claim_edges') END;
            END;
            INSERT INTO claims VALUES ('a', 'Claim A', 'da', 'unresolved', '{}');
            INSERT INTO claims VALUES ('b', 'Claim B', 'db', 'unresolved', '{}');
            INSERT INTO claim_edges VALUES ('a', 'b', 'contradicts');
            """
        )
        conn.commit()
    finally:
        conn.close()

    with ResearchStateDB(db_file) as db:
        r1 = thaw(db.add_claim_relation("b", "a", "contradicts"))
        r2 = thaw(db.add_claim_relation("b", "a", "corroborates"))
        assert r1["relation_type"] == "contradicts"
        assert r2["relation_type"] == "corroborates"


def test_p1_09_meta_regression_estimates_residual_tau2_and_null_qe() -> None:
    r_lin = meta_core.meta_regression([0, 1, 2, 3], [0.01] * 4, [0, 1, 2, 3], model="random")
    assert r_lin["tau2"] == pytest.approx(0.0, abs=1e-12)
    assert r_lin["se_slope"] == pytest.approx(0.044721359549995794, rel=1e-9)
    assert r_lin["p_slope"] < 1e-100

    r_qe = meta_core.meta_regression([1, -1, -1, 1], [0.01] * 4, [-1, 0, 1, 2], model="random")
    assert r_qe["q_residual"] == pytest.approx(400.0, rel=1e-9)
    assert r_qe["df_residual"] == 2
    assert r_qe["p_residual"] < 1e-80


def test_p1_10_meta_core_handles_extreme_variances_and_subnormal_se() -> None:
    _, _, _, tau2_129 = meta_core.heterogeneity([0.0] + [2.0] * 128, [1e-20] + [1.0] * 128)
    assert tau2_129 == pytest.approx(1.5, rel=1e-9)

    _, _, _, tau2_wide = meta_core.heterogeneity([0.0, 2e10], [1e-320, 1e20])
    assert tau2_wide == pytest.approx(1.5e20, rel=1e-9)

    pf = meta_core.pool_fixed([0.0, 0.0], [5e-324, 5e-324])
    assert pf.se > 1e-163 and pf.se == pytest.approx(1.5717277847e-162, rel=1e-2)


def test_p1_11_blind_gates_catch_author_after_verb_percent_and_icmlauthor(tmp_path: Path) -> None:
    tex_verb = tmp_path / "verb_leak.tex"
    tex_verb.write_text(r"\verb|%| \author{Alice Smith}" + "\n", encoding="utf-8")
    scan = double_blind_sanitizer.scan_target(tex_verb)
    assert scan["leak_count"] >= 1

    icml_tex = tmp_path / "icml.tex"
    icml_tex.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\icmlauthor{Alice Smith}{myuni}\n"
        "\\begin{abstract}Valid abstract.\\end{abstract}\n"
        "\\section{Introduction}\nBody.\n\\end{document}\n",
        encoding="utf-8",
    )
    rep = pre_submission_linter.lint_manuscript(icml_tex, venue=None, double_blind=True)
    assert rep["passed"] is False
    assert any(f["code"] == "BLIND_AUTHOR_LEAK" for f in rep["findings"])


def test_p1_12_linter_blocks_nospace_braceless_tex_input_outside_root(tmp_path: Path) -> None:
    sub = tmp_path / "manuscript"
    sub.mkdir()
    (tmp_path / "outside.tex").write_text("SECRET\n", encoding="utf-8")
    main_tex = sub / "main.tex"
    main_tex.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\begin{abstract}Study.\\end{abstract}\n"
        "\\input../outside\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep = pre_submission_linter.lint_manuscript(main_tex, venue=None, double_blind=False)
    assert rep["passed"] is False
    assert any(f["code"] == "UNSAFE_INCLUDE_PATH" for f in rep["findings"])


def test_p1_13_shared_references_page_with_short_sentence_counts_toward_body_pages(tmp_path: Path) -> None:
    pdf_f = tmp_path / "two_page.pdf"
    pdf_f.write_bytes(b"%PDF-1.4 mock")
    mock_pages = {
        "page_count": 2,
        "pages": ["1 Introduction\nFull page one text.", "Accuracy improves.\nReferences\n[1] Doe 2025."],
        "metadata": {},
        "has_xmp_stream": False,
        "xmp_xml": "",
    }
    with mock.patch("academic_research_kernel.research.sources.controlled_read_pdf_pages", return_value=mock_pages):
        errs = pre_submission_linter._check_pdf_page_limit(pdf_f, max_pages=1)
    assert any(e["code"] == "PDF_PAGE_LIMIT_EXCEEDED" for e in errs)


def test_p1_14_mcp_enforces_authorized_workspace_root_on_lint_and_sanitize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = tmp_path / "authorized"
    outside = tmp_path / "outside"
    ws.mkdir()
    outside.mkdir()
    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(ws))
    ext_tex = outside / "private.tex"
    ext_tex.write_text(r"\documentclass{article}\begin{document}\ref{OUTSIDE_SENTINEL_58291}\end{document}", encoding="utf-8")

    r_lint = mcp_server.process_message({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "academic_pre_submission_lint", "arguments": {"tex_path": str(ext_tex), "double_blind": False}},
    })
    assert r_lint["result"]["isError"] is True
    assert "OUTSIDE_SENTINEL_58291" not in json.dumps(r_lint)

    r_san = mcp_server.process_message({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "academic_double_blind_sanitize", "arguments": {"target_path": str(ext_tex), "forbidden_tokens": ["OUTSIDE_SENTINEL_58291"]}},
    })
    assert r_san["result"]["isError"] is True
    assert "OUTSIDE_SENTINEL_58291" not in json.dumps(r_san)


def test_p1_15_openreview_mirror_handles_unbalanced_word_count_slots_and_marks_partial() -> None:
    rec = {"id": "p", "rating": "6;7", "confidence": "4;5", "wc_strengths_and_weaknesses": "10;20", "wc_limitations": "5"}
    rep = openreview_audit.summarize_venue_mirror([rec])
    assert rep["review_word_count_stats"]["count"] == 1
    assert rep["review_word_count_stats"]["completeness"] == "partial"
    assert rep["review_word_count_stats"]["partial_component_slots"] == 1


def test_p1_16_restored_statistical_power_receipt_json_and_linter_hits_contracts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    stat_res = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"effect_size_d": 0.5, "target_power": 0.8, "alpha": 0.05, "sample_ratio": 1.0},
    )
    assert stat_res["required_sample_size"]["recomputed"] == pytest.approx(63.7656, rel=1e-3)

    p_res = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"t_stat": 2.2, "df": 20, "p_value": 0.04, "p_value_decimals": 2},
    )
    assert p_res["consistent"] is True

    tbl = tmp_path / "r.json"
    tbl.write_text(json.dumps({"columns": ["Model", "Value"], "rows": [["A", 1.0]]}), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["receipt-to-latex", str(tbl)]) == 0
    j_out = json.loads(capsys.readouterr().out)
    assert j_out["status"] == "ok" and "\\toprule" in j_out["latex"]

    tex = tmp_path / "m.tex"
    tex.write_text("\\documentclass{article}\n\\begin{document}\n\\begin{abstract}A.\\end{abstract}\n\\ref{missing}\n\\end{document}\n", encoding="utf-8")
    l_rep = pre_submission_linter.lint_manuscript(tex, venue=None, double_blind=False)
    assert len(l_rep["hits"]) == len(l_rep["findings"]) >= 1


def test_p1_17_compute_receipt_records_effective_dtype_validates_counts_and_rejects_unmeasured_admitted() -> None:
    rec = compute_probe.build_compute_receipt(
        operation="matmul_f32",
        scale="small",
        candidates=[{"backend": "unmeasured_gpu", "dtype": "float32", "verdict": "ADMITTED"}],
    )
    assert rec["dtype"] == "float32"
    assert rec["admitted_backends"] == []
    assert rec["candidates"][0]["verdict"] == "REFERENCE"
    assert rec["candidates"][0]["fallback_reason"] == "unverified_external_candidate"

    with pytest.raises(ValueError, match="Conflicting dtype"):
        compute_probe.build_compute_receipt(operation="matmul_f32", dtype="float64")
    with pytest.raises(ValueError, match="warmup"):
        compute_probe.build_compute_receipt(warmup=-2)
    with pytest.raises(ValueError, match="repeat"):
        compute_probe.build_compute_receipt(repeat=-3)


def test_p1_18_benchmark_receipts_bind_v300_frozen_commits_and_lexical_screening_scope() -> None:
    peer = json.loads((REPO_ROOT / "docs/benchmarks/peer-review-forensics-2025-2027-v1.json").read_text("utf-8"))
    assert peer["kernel_version"] == "3.0.0"
    assert peer["upstream_source"]["frozen_commit"] == "181a85021c63ab26745c42ed70a9d9ea7b57ad7e"
    iclr26 = next(v for v in peer["venues"] if v["venue_id"] == "ICLR.cc/2026/Conference")
    assert iclr26["non_positive_rating_anomalies"] == {"count": 1319, "submissions_affected": 1096}
    assert iclr26["paper_mean_quantiles"]["min"] >= 2.0

    inc = json.loads((REPO_ROOT / "docs/benchmarks/iclr2026-openreview-incidence-receipt.json").read_text("utf-8"))
    assert inc["measurement_scope"] == "lexical_keyword_screening_mention_rate"
    assert inc["upstream_sources"]["review_text_corpus"]["commit"] == "50507ab355c3442f7f4dd2a3df0e18aee8e0edbc"

    rw = json.loads((REPO_ROOT / "docs/benchmarks/real-world-audit-benchmark-v1.json").read_text("utf-8"))
    assert rw["kernel_version"] == "3.0.0"


# ---------------------------------------------------------------------------
# P2 Improvements (P2-01 .. P2-07)
# ---------------------------------------------------------------------------


def test_p2_01_collect_corpus_is_strictly_order_independent_under_padded_titles() -> None:
    l1 = {"text-search": [{"doi": "10.1234/a", "title": "Paper"}], "topic-cross": [{"doi": "10.1234/a", "title": "  Paper  "}]}
    l2 = {"text-search": [{"doi": "10.1234/a", "title": "  Paper  "}], "topic-cross": [{"doi": "10.1234/a", "title": "Paper"}]}
    r1 = collect_corpus.merge_candidates(l1)
    r2 = collect_corpus.merge_candidates(l2)
    assert r1["candidates"][0]["title"] == r2["candidates"][0]["title"] == "Paper"


def test_p2_02_add_claim_depends_on_and_add_claim_relation_agree_when_contradicts_present() -> None:
    with ResearchStateDB() as db:
        db.add_claim("a", "Claim A")
        db.add_claim("b", "Claim B")
        db.add_claim_relation("a", "b", "contradicts")
        db.add_claim_relation("b", "a", "contradicts")
        res = thaw(db.add_claim("a", "Claim A", depends_on=["b"]))
        assert res["claim_id"] == "a"


def test_p2_03_pinned_public_dns_is_thread_local_and_does_not_break_other_threads() -> None:
    observed: dict[str, object] = {}

    def _other_thread() -> None:
        observed["loopback"] = socket.getaddrinfo("127.0.0.1", 9999, socket.AF_INET, socket.SOCK_STREAM)

    with sources._pinned_public_dns():
        t = threading.Thread(target=_other_thread)
        t.start()
        t.join()
    assert isinstance(observed.get("loopback"), list) and len(observed["loopback"]) >= 1


def test_p2_04_repo_forensics_tree_json_ignores_directory_trees_and_preserves_tree_sha(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tj = tmp_path / "tree.json"
    tj.write_text(
        json.dumps({
            "sha": "a" * 40,
            "truncated": False,
            "tree": [
                {"path": "package.py", "type": "tree"},
                {"path": "package.py/module.py", "type": "blob", "size": 38},
            ],
        }),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert cli.main(["repo-forensics", "--tree-json", str(tj)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["total_tracked_files"] == 1
    assert out["total_python_files"] == 1
    assert out["tree_sha"] == "a" * 40


def test_p2_05_cli_aliases_relations_rollback_and_zero_dead_markdown_links(tmp_path: Path) -> None:
    assert cli.main(["check-venue", "--action", "list"]) == 0
    studies_f = tmp_path / "studies.json"
    studies_f.write_text(json.dumps([{"yi": 0.2, "vi": 0.04}, {"yi": 0.4, "vi": 0.05}]), encoding="utf-8")
    assert cli.main(["meta-pool", "--input", str(studies_f)]) == 0

    mcp_server.reset_session_db()
    before = mcp_server.get_session_db().snapshot_digest()
    failed = mcp_server.process_message({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {
            "name": "claim_evidence_add",
            "arguments": {"claim_id": "left-behind", "claim_text": "Should roll back", "relations": [{"target_claim_id": "missing", "relation": "contradicts"}]},
        },
    })
    assert failed["result"]["isError"] is True
    assert mcp_server.get_session_db().snapshot_digest() == before


def test_p2_06_openreview_separates_meta_review_ratings_from_official_reviews() -> None:
    payload = {
        "notes": [
            {"id": "f1", "forum": "f1", "content": {"title": "Paper", "venue": "ICLR 2026"}},
            {"id": "r1", "forum": "f1", "invitation": "ICLR.cc/2026/Conference/Submission1/-/Official_Review", "content": {"rating": "6: marginally above"}},
            {"id": "m1", "forum": "f1", "invitation": "ICLR.cc/2026/Conference/Submission1/-/Meta_Review", "content": {"rating": "10", "recommendation": "Accept"}},
        ]
    }
    parsed = openreview_audit.parse_openreview_notes(payload, forum_id="f1")
    assert parsed["review_count"] == 1
    assert parsed["ratings"] == [6.0]
    assert parsed["mean_rating"] == 6.0
    assert len(parsed["meta_reviews"]) == 1


def test_p2_07_locate_oa_rejects_mismatched_unpaywall_doi_response() -> None:
    with mock.patch.object(
        locate_oa,
        "live_unpaywall",
        return_value={"doi": "10.9999/wrong", "is_oa": True, "best_oa_location": {"url_for_pdf": "https://example.org/wrong.pdf"}},
    ):
        rc, rep = locate_oa.resolve_oa({"type": "doi", "value": "10.1234/requested", "normalized": "10.1234/requested"}, email="test@example.edu")
    assert rc == 1
    assert rep["status"] == "failed"
    assert rep["mismatch"] is True


def test_r3_sol_and_astra_second_order_hardening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import math
    import numpy as np

    # 1. Cross-review: Proposal-unknown, Proposal-1.5, Proposal-1e9, fenced code block, and 3-way opposing CONCEDE
    mk = lambda pol: {"target": "x.py", "issue_key": "validation", "polarity": pol, "severity": "P1", "claim": pol, "evidence": ["x.py:1"]}
    reg1, ch1, sk1 = cross_review.plan_challenges(["a", "b"], {"a": {"findings": [mk("valid")]}, "b": {"findings": []}})
    for bad_s in (
        "[REFUTED] Proposal-unknown: no",
        "```\n[REFUTED] Proposal-1: inside fence\n```",
        "````markdown\n```\n[REFUTED] Proposal-1: nested fence\n````",
    ):
        r_s = cross_review.synthesize_deliberation(reg1, ch1, {ch1[0]["challenge_id"]: bad_s}, skipped_challenges=sk1)
        assert r_s["convergence_status"] != "CONVERGED"
        assert len(r_s["unresolved_ledger"]) == 1

    reg3, ch3, sk3 = cross_review.plan_challenges(
        ["a", "b", "c", "d"],
        {"a": {"findings": [mk("valid")]}, "b": {"findings": [mk("invalid")]}, "c": {"findings": [mk("invalid")]}, "d": {"findings": []}},
    )
    cid3 = ch3[0]["challenge_id"]
    for bad_c in (
        "[CONCEDE] Proposal-1.5: ex\n[REFUTED] Proposal-2.5: ex\n[REFUTED] Proposal-3.5: ex",
        "[CONCEDE] Proposal-1e9: ok\n[REFUTED] Proposal-2e9: no\n[REFUTED] Proposal-3e9: no",
        "[CONCEDE] Proposal-1: ok\n[CONCEDE] Proposal-2: ok\n[REFUTED] Proposal-3: no",
    ):
        r_c = cross_review.synthesize_deliberation(reg3, ch3, {cid3: bad_c}, skipped_challenges=sk3)
        assert r_c["convergence_status"] != "CONVERGED"
        assert len(r_c["uncontested_contradictions"]) == 1

    # 2. deliberate_inline rejects unbound cross-task plain-string replies
    f_old = {"a": [mk("valid")], "b": [mk("invalid")], "c": []}
    f_new = {"a": [{**mk("valid"), "target": "new.py"}], "b": [{**mk("invalid"), "target": "new.py"}], "c": []}
    old_inline = cross_review.deliberate_inline(f_old)
    assert old_inline["challenge_plan"][0]["run_id"] is not None
    assert old_inline["challenge_plan"][0]["task_sha256"] is not None
    new_unbound = cross_review.deliberate_inline(
        f_new,
        challenge_replies={"C01": "[CONCEDE] Proposal-1: old verified\n[REFUTED] Proposal-2: old disproved"},
    )
    assert new_unbound["synthesis"]["convergence_status"] != "CONVERGED"

    # 3. Decision Ledger chronological interleaving + inner digest & academic_evidence binding
    body_keys = ("protocol", "verification_digest", "verification_manifest", "decisions", "bases", "forks", "state_events", "corrections", "uncertainties")
    with ResearchStateDB() as db:
        db.record_decision("d", "Decision", verdict="inconclusive")
        db.correct_decision_outcome("d", "positive", "Earlier correction")
        db.transition_decision("d", "pruned", "contradicted", verdict_override="negative")
        doc_dl = thaw(db.export_decision_ledger_dict())
        assert doc_dl["decisions"][0]["metadata"]["verdict"] == "negative"
        assert [(c["sequence"], c["verdict"]) for c in doc_dl["corrections"]] == [(1, "positive"), (2, "negative")]
        assert validate_decision_ledger_semantics(doc_dl) == []

        forged_v = copy.deepcopy(doc_dl)
        forged_v["decisions"][0]["metadata"]["verdict"] = "positive"
        forged_v["ledger_digest"] = sha256_hex(canonical_json({k: forged_v[k] for k in body_keys}))
        assert any("metadata.verdict" in e for e in validate_decision_ledger_semantics(forged_v))

    with ResearchStateDB() as db:
        db.record_decision("d", "Decision")
        db.record_decision("n", "Negative", entry_kind="negative_result", basis_decision_id="d")
        doc_neg = thaw(db.export_decision_ledger_dict())
        doc_neg["uncertainties"] = []
        doc_neg["bases"][0]["receipt_ref"] = {"kind": "academic_evidence", "schema_version": "1.0", "claim_digest": "0" * 64, "payload_sha256": "0" * 64}
        doc_neg["ledger_digest"] = sha256_hex(canonical_json({k: doc_neg[k] for k in body_keys}))
        assert any("academic_evidence" in e or "unsupported_negative_result" in e for e in validate_decision_ledger_semantics(doc_neg))

    # 4. CEG content-addressed claim_digest/graph_digest verification + MCP claim_evidence_add authoritative contested status
    with ResearchStateDB() as db:
        db.register_artifact("e", "source", {"result": "Latency decreases by 40%."})
        db.add_claim("c", "Latency decreases by 40%.", evidence=[("e", "supports", "Table 1")])
        ceg_doc = thaw(db.export_ceg_dict())
        ceg_doc["claims"][0]["text"] = "Latency increases by 400%."
        ceg_doc["claims"][0]["normalized_text"] = "Latency increases by 400%."
        sem = venue_template_manager.validate_ceg_semantics(ceg_doc)
        assert sem["eligible_count"] == 0
        assert len(sem["semantic_errors"]) >= 2

    mcp_server.reset_session_db()
    mcp_server.handle_tool_call("research_artifact_ingest", {"artifact_id": "e1", "kind": "source", "payload": {"v": 1}})
    mcp_server.handle_tool_call("claim_evidence_add", {"claim_id": "ca", "claim_text": "A holds", "evidence": [{"artifact_id": "e1", "stance": "supports", "locator": "L1"}]})
    cb_res = mcp_server.handle_tool_call(
        "claim_evidence_add",
        {
            "claim_id": "cb",
            "claim_text": "B opposes A",
            "evidence": [{"artifact_id": "e1", "stance": "supports", "locator": "L2"}],
            "relations": [{"target_claim_id": "ca", "relation": "contradicts"}],
        },
    )
    assert cb_res["status"] == "contested"

    # 5. Meta-analysis centering, subnormal DL ratio, and 1e-320 meta-regression trace(P)
    q_eq, _, i2_eq, tau2_eq = meta_core.heterogeneity([3.1] * 3, [1e-40] * 3)
    assert q_eq == pytest.approx(0.0, abs=1e-12) and i2_eq == 0.0 and tau2_eq == 0.0
    _, _, _, tau2_sub = meta_core.heterogeneity([0.0, math.sqrt(1.5)], [5e-324, 1.0])
    assert tau2_sub == pytest.approx(0.25, rel=1e-9)
    mr_tiny = meta_core.meta_regression([1e-160, -1e-160, -1e-160, 1e-160], [1e-320] * 4, [-1, 0, 1, 2])
    assert mr_tiny["tau2"] == pytest.approx(1e-320, rel=1e-6)
    assert mr_tiny["se_slope"] == pytest.approx(6.32455532e-161, rel=1e-5)

    # 6. compute_probe unrounded speedup comparison & real scipy.linalg.blas dot call + OpenReview partial wc_review
    hw = {k: ([] if k == "accelerators" else ({} if k in ("libraries", "threads") else "test")) for k in (
        "os", "architecture", "cpu_model", "python", "os_visible_cpus", "process_affinity_cpus",
        "cgroup_cpu_quota", "ram_total_bytes", "isa_hint", "accelerators", "libraries", "threads",
    )}
    with mock.patch.object(compute_probe, "probe", return_value=hw), mock.patch.object(
        compute_probe.time, "perf_counter", side_effect=[0.0, 0.0, 0.0, 1.51e-6, 1.0, 1.0, 1.0, 1.0 + 1.49e-6]
    ), mock.patch.object(np, "dot", wraps=np.dot) as spy_dot:
        cp_res = compute_probe.build_compute_receipt(operation="dot", warmup=0, repeat=1, measure_candidates=True)
    assert spy_dot.call_count == 1
    assert cp_res["admitted_backends"] == []

    or_partial = openreview_audit.summarize_venue_mirror([{"id": "p", "rating": "6;7", "confidence": "4;5", "wc_review": "10;"}])
    assert or_partial["review_forensics"]["partial_word_count_slots"] == 1

    # 7. Double-blind trailing \\ in \author{Alice Smith\\} + swapped multi-clause CEG binding + arbitrary unit mismatch
    tex_bs = tmp_path / "bs.tex"
    tex_bs.write_text("\\documentclass{article}\n\\author{Alice Smith\\\\}\n\\begin{document}\n\\begin{abstract}A.\\end{abstract}\n\\maketitle\n\\end{document}\n", encoding="utf-8")
    assert double_blind_sanitizer.scan_target(tex_bs)["leak_count"] >= 1
    assert pre_submission_linter.lint_manuscript(tex_bs, venue=None, double_blind=True)["passed"] is False

    for lbl, cl_t, ms_t in (
        ("swap", "Accuracy increases by 40%; latency decreases by 20%.", r"Accuracy decreases by 40\%; latency increases by 20\%."),
        ("mass", "Treatment is 40 milligrams.", "Treatment is 40 kilograms."),
    ):
        with ResearchStateDB() as db:
            db.register_artifact("a", "source", {"text": cl_t})
            db.add_claim("c", cl_t, evidence=[("a", "supports", "L1")])
            g_doc = thaw(db.export_ceg_dict())
        gp = tmp_path / f"{lbl}.json"
        gp.write_text(json.dumps(g_doc), encoding="utf-8")
        mp = tmp_path / f"{lbl}.tex"
        mp.write_text(f"\\documentclass{{article}}\\begin{{document}}\\begin{{abstract}}S.\\end{{abstract}}\n{ms_t} % ark:claim=c\n\\end{{document}}\n", encoding="utf-8")
        assert pre_submission_linter.lint_manuscript(mp, venue=None, double_blind=False, ceg_path=gp, require_ceg_binding=True)["passed"] is False

    # 8. Concurrent _pinned_public_dns custom resolver preservation + dual-stack IPv6->IPv4 fallback + missing OA DOI rejection
    orig_gai = socket.getaddrinfo
    custom_gai = lambda *a, **kw: orig_gai(*a, **kw)
    ev_a_in, ev_b_in, ev_a_out = threading.Event(), threading.Event(), threading.Event()

    def _ta() -> None:
        with sources._pinned_public_dns():
            ev_a_in.set()
            assert ev_b_in.wait(5)
        ev_a_out.set()

    def _tb() -> None:
        assert ev_a_in.wait(5)
        with sources._pinned_public_dns():
            ev_b_in.set()
            assert ev_a_out.wait(5)

    with mock.patch.object(socket, "getaddrinfo", custom_gai):
        t1, t2 = threading.Thread(target=_ta), threading.Thread(target=_tb)
        t1.start(); t2.start(); t1.join(); t2.join()
        assert socket.getaddrinfo is custom_gai

    class _DummySock:
        pass

    def _mock_conn(addr, *_a, **_kw):
        if ":" in addr[0]:
            raise OSError("IPv6 unreachable")
        return _DummySock()

    pins: dict = {}
    with mock.patch.object(socket, "getaddrinfo", return_value=[
        (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 80, 0, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 80)),
    ]), mock.patch.object(socket, "create_connection", side_effect=_mock_conn):
        sources._resolve_and_pin_host("http://example.org/", pins)
        conn_h = sources._PinnedHTTPConnection("example.org", pins)
        conn_h.connect()
        assert isinstance(conn_h.sock, _DummySock)

    with mock.patch.object(locate_oa, "live_unpaywall", return_value={"doi": "", "is_oa": True, "best_oa_location": {"url_for_pdf": "https://example.org/u.pdf"}}):
        rc_m, rep_m = locate_oa.resolve_oa({"type": "doi", "value": "10.1234/req", "normalized": "10.1234/req"}, email="t@example.edu")
    assert rc_m == 1 and rep_m["mismatch"] is True
