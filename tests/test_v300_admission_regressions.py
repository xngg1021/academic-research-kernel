"""Comprehensive regression suite covering all 19 v3.0.0 trunk-admission audit findings,
5 first-principles skills, release_gate invariants, and multi-venue OpenReview forensics."""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from pathlib import Path
import pytest

from academic_research_kernel import (
    cli,
    double_blind_sanitizer,
    locate_oa,
    mcp_server,
    meta_core,
    openreview_audit,
    pre_submission_linter,
    release_gate,
    watch,
)
from academic_research_kernel._stdlib import ARK_SQLITE_APP_ID
from academic_research_kernel.state_db import ResearchStateDB

ROOT = Path(__file__).resolve().parents[1]


def test_p0_01_and_p2_06_release_gate_twine_and_sdist_completeness(tmp_path: Path) -> None:
    wf = (ROOT / ".github" / "workflows" / "publish-pypi.yml").read_text(encoding="utf-8")
    assert "scripts/verify_release_assets.py" not in wf
    assert "scripts/package_smoke_check.py" not in wf
    assert "scripts/package_acceptance.py" not in wf
    assert "scripts/distribution_smoke.py" not in wf
    assert "academic_research_kernel.release_gate" in wf

    pyproj = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    req_qa = (ROOT / "requirements-qa.txt").read_text(encoding="utf-8")
    for pkg in ("twine", "pyyaml"):
        assert pkg in pyproj
        assert pkg in req_qa
    for req_asset in ("uv.lock", "requirements-qa.txt", "CHANGELOG.md", "README.zh-CN.md", "SLL-APPLICATION.json"):
        assert f'"{req_asset}"' in pyproj

    # Verify SLL preserved MIT files bit-for-bit
    verified = release_gate.verify_sll_preserved_files(ROOT)
    assert len(verified) == 5

    # Verify PyPI idempotency planner (fresh, partial resume, verify-only, and byte-conflict rejection)
    vdist = tmp_path / "verified"
    vdist.mkdir()
    whl = vdist / "academic_research_kernel-3.0.0-py3-none-any.whl"
    sdist = vdist / "academic_research_kernel-3.0.0.tar.gz"
    whl.write_bytes(b"wheel-bytes-v300")
    sdist.write_bytes(b"sdist-bytes-v300")
    whl_sha = hashlib.sha256(whl.read_bytes()).hexdigest()
    sdist_sha = hashlib.sha256(sdist.read_bytes()).hexdigest()
    manifest = {
        "version": "3.0.0",
        "git_tag": "v3.0.0",
        "artifacts": [
            {"filename": whl.name, "sha256": whl_sha, "size_bytes": whl.stat().st_size},
            {"filename": sdist.name, "sha256": sdist_sha, "size_bytes": sdist.stat().st_size},
        ],
    }

    plan_fresh = release_gate.plan_pypi_upload(manifest, vdist, tmp_path / "up1", None)
    assert plan_fresh["upload_count"] == 2

    partial_pypi = {
        "info": {"name": "academic-research-kernel", "version": "3.0.0"},
        "urls": [{"filename": whl.name, "digests": {"sha256": whl_sha}, "size": whl.stat().st_size}],
    }
    plan_resume = release_gate.plan_pypi_upload(manifest, vdist, tmp_path / "up2", partial_pypi)
    assert plan_resume["upload_count"] == 1
    assert plan_resume["missing"] == [sdist.name]

    conflict_pypi = {
        "info": {"name": "academic-research-kernel", "version": "3.0.0"},
        "urls": [{"filename": whl.name, "digests": {"sha256": "0" * 64}, "size": whl.stat().st_size}],
    }
    with pytest.raises(ValueError, match="conflict"):
        release_gate.plan_pypi_upload(manifest, vdist, tmp_path / "up3", conflict_pypi)


def test_p1_01_claim_evidence_validate_rejects_dangling_edges() -> None:
    base_ceg = {
        "protocol": "claim-evidence-graph-1.0",
        "graph_id": "g-test-1",
        "graph_digest": "a" * 64,
        "claims": [
            {
                "id": "c1",
                "text": "Accuracy is 91.2%",
                "normalized_text": "Accuracy is 91.2%",
                "claim_type": "empirical_finding",
                "claim_digest": "b" * 64,
            }
        ],
        "evidence_anchors": [{"id": "e1", "anchor_type": "table_cell", "locator": "Table 1"}],
        "claim_relations": [],
        "uncertainties": [],
    }
    bad_ceg = {
        **base_ceg,
        "support_edges": [
            {"claim_id": "missing-c", "evidence_id": "e1", "support_status": "supported"},
            {"claim_id": "c1", "evidence_id": "missing-e", "support_status": "supported"},
        ],
    }
    for key in ("ceg", "graph"):
        res = mcp_server.handle_tool_call("claim_evidence_validate", {key: bad_ceg})
        assert res["valid"] is False
        assert len(res["errors"]) >= 2

    good_ceg = {
        **base_ceg,
        "support_edges": [{"claim_id": "c1", "evidence_id": "e1", "support_status": "supported"}],
    }
    res_ok = mcp_server.handle_tool_call("claim_evidence_validate", {"ceg": good_ceg})
    assert res_ok["valid"] is True
    assert res_ok["errors"] == []


def test_p1_02_research_lineage_trace_legacy_edges_and_missing_target() -> None:
    legacy_graph = {
        "entities": [{"id": "raw-1"}, {"id": "clean-1"}],
        "edges": [{"type": "derived_from", "source_id": "clean-1", "target_id": "raw-1"}],
    }
    traced = mcp_server.handle_tool_call(
        "research_lineage_trace",
        {"lineage": legacy_graph, "target_id": "clean-1"},
    )
    assert traced["ancestors"] == ["raw-1"]
    assert traced["chain_length"] == 2
    assert traced["verification_status"] == "unchecked"

    ghost = mcp_server.handle_tool_call(
        "research_lineage_trace",
        {"lineage": legacy_graph, "target_id": "ghost"},
    )
    assert ghost["verification_status"] == "missing_input"
    assert ghost["chain_length"] == 0


def test_p1_03_retraction_watch_out_of_order_cas_and_conflict_rejection() -> None:
    with ResearchStateDB(":memory:") as db:
        doi = "10.1038/s41586-020-2649-2"
        seq1 = db.reserve_watch_seq("retraction", doi)
        seq2 = db.reserve_watch_seq("retraction", doi)
        assert (seq1, seq2) == (1, 2)

        # Newer seq=2 fails transiently with 'unknown' first
        r2 = db.commit_watch_observation("retraction", doi, seq=seq2, status="unknown", signals=[], error="timeout")
        assert r2["status"] == "unknown"

        # Late-arriving seq=1 carries confirmed retraction -> must NOT lose confirmed truth or alert
        r1 = db.commit_watch_observation(
            "retraction",
            doi,
            seq=seq1,
            status="retracted",
            signals=["crossref:update:retraction"],
        )
        assert r1["is_retracted"] is True
        assert r1["changed"] is True
        deltas = db.drain_unacked_watch_deltas("retraction", [doi])
        assert len(deltas) == 1
        assert deltas[0]["is_retracted"] is True

        # Idempotent replay of identical seq=1 succeeds, while conflicting digest at seq=1 raises ValueError
        replay = db.commit_watch_observation(
            "retraction",
            doi,
            seq=seq1,
            status="retracted",
            signals=["crossref:update:retraction"],
        )
        assert replay["is_retracted"] is True
        with pytest.raises(ValueError, match="Conflicting watch observation"):
            db.commit_watch_observation("retraction", doi, seq=seq1, status="not_retracted", signals=[])


def test_p1_04_watch_preserves_peer_signals_on_partial_failure_and_malformed_crossref(monkeypatch: pytest.MonkeyPatch) -> None:
    doi = "10.1000/partial-watch"
    with ResearchStateDB(":memory:") as db:
        s0 = db.reserve_watch_seq("retraction", doi)
        db.commit_watch_observation(
            "retraction",
            doi,
            seq=s0,
            status="retracted",
            signals=["crossref:update:retraction-1"],
            signals_complete=True,
        )
        db.drain_unacked_watch_deltas("retraction", [doi])

        # Simulate OpenAlex returning not_retracted while Crossref returns malformed {} empty dict
        def fake_fetch_json(url: str):
            if "openalex.org" in url:
                return {"id": "https://openalex.org/W1", "is_retracted": False}
            return {}

        monkeypatch.setattr(watch, "_fetch_json", fake_fetch_json)
        rep = watch.check_retraction_report([doi], live=True, db=db)
        assert len(rep["errors"]) == 1
        assert "crossref:update:retraction-1" in rep["results"][0]["signals"]


def test_p1_05_export_ceg_dict_distinct_anchors_across_artifacts() -> None:
    with ResearchStateDB(":memory:") as db:
        db.batch_ingest([
            {"artifact_id": "results-run-a", "kind": "statistic_artifact", "payload": {"checks": []}},
            {"artifact_id": "results-run-b", "kind": "statistic_artifact", "payload": {"checks": []}},
        ])
        db.add_claim(
            "C1",
            "Run A and Run B both improve accuracy",
            evidence=[
                ("results-run-a", "supports", "Table 1"),
                ("results-run-b", "supports", "Table 1"),
            ],
        )
        ceg = db.export_ceg_dict()
        assert len(ceg["evidence_anchors"]) == 2
        assert len({a["id"] for a in ceg["evidence_anchors"]}) == 2


def test_p1_06_08_09_and_p2_02_03_pre_submission_linter(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "leak.tex").write_text(r"\section{Experiments}" + "\nBody text.\n", encoding="utf-8")
    (tmp_path / "sub" / "a.tex").write_text("\\input{sub/b}\n", encoding="utf-8")
    (tmp_path / "sub" / "b.tex").write_text("Nested chapter ok.\n", encoding="utf-8")
    (tmp_path / "refs.bib").write_text(
        "@inproceedings{smith2025,\n  author={Smith, A.},\n  title={Paper},\n  year={2025},\n  crossref={proc2025}\n}\n"
        "@proceedings{proc2025,\n  title={Proc},\n  year={2025}\n}\n"
        "@article{unused2024,\n  author={Doe, B.},\n  title={Unused},\n  year={2024}\n}\n",
        encoding="utf-8",
    )
    # Unreferenced backup.bib with duplicate keys must NOT pollute declared refs.bib
    (tmp_path / "backup.bib").write_text(
        "@article{smith2025, title={Dup1}}\n@article{smith2025, title={Dup2}}\n",
        encoding="utf-8",
    )
    ceg_path = tmp_path / "ceg.json"
    ceg_path.write_text(
        json.dumps({
            "claims": [{"id": "C1", "text": "Latency is 5.0 ms", "status": "supported"}],
            "evidence_anchors": [{"id": "E1", "artifact_id": "art1", "locator": "Table 1"}],
            "support_edges": [{"claim_id": "C1", "evidence_id": "E1", "support_status": "supported"}],
        }),
        encoding="utf-8",
    )
    main_tex = tmp_path / "main.tex"
    main_tex.write_text(
        r"""\documentclass{article}
\usepackage[final]{microtype}
\usepackage[final]{hyperref}
\addbibresource[location=local]{refs.bib}
\begin{document}
\section{Introduction}
We cite \citet{smith2025}. This is universally superior.
\begin{verbatim}
\input{does_not_exist}
\end{verbatim}
\input leak
\input{sub/a}
\section{Method}
Accuracy improves by 12.5\% over baseline. % ark:claim=C1
\section{Conclusion}
Done.
\end{document}
""",
        encoding="utf-8",
    )
    rep = pre_submission_linter.lint_manuscript(
        main_tex,
        venue="neurips",
        ceg_path=ceg_path,
        require_ceg_binding=True,
        check_academic_style=True,
    )
    codes = {f["code"] for f in rep["findings"]}
    assert "MISSING_TEX_INCLUDE" not in codes
    assert "DUPLICATE_BIB_KEY" not in codes
    assert "FINAL_MODE_IN_REVIEW" not in codes
    assert "CEG_CLAIM_TEXT_MISMATCH" in codes
    assert "UNCITED_BIBLIOGRAPHY_ENTRY" in codes
    assert "OVERCLAIM_PHRASING" in codes
    # Verify crossref parent proc2025 was NOT flagged as uncited, only unused2024
    uncited_finding = [f for f in rep["findings"] if f["code"] == "UNCITED_BIBLIOGRAPHY_ENTRY"][0]
    assert "unused2024" in uncited_finding["detail"]
    assert "proc2025" not in uncited_finding["detail"]

    # Fake % ark:claim=FAKE without --ceg must NOT bypass require_ceg_binding
    rep_no_ceg = pre_submission_linter.lint_manuscript(main_tex, venue="neurips", require_ceg_binding=True)
    codes_no_ceg = {f["code"] for f in rep_no_ceg["findings"]}
    assert "UNVERIFIED_CEG_ANCHOR" in codes_no_ceg
    assert "UNGROUNDED_QUANT_CLAIM" in codes_no_ceg


def test_p1_07_and_p2_04_pdf_shared_page_limit_and_isolated_xmp_scan(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import DecodedStreamObject, NameObject

    # Build a minimal valid 2-page PDF via reportlab-free raw content stream in pypdf
    writer = pypdf.PdfWriter()
    for page_idx, text_line in enumerate([
        "Section 1 Introduction and experimental body prose on page one.",
        "Final body paragraph concluding ablation results before references.\\nReferences\\n[1] Smith 2025.",
    ]):
        page = pypdf.PageObject.create_blank_page(width=612, height=792)
        font_dict = pypdf.generic.DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = pypdf.generic.DictionaryObject({
            NameObject("/Font"): pypdf.generic.DictionaryObject({NameObject("/F1"): font_dict})
        })
        ops = ["BT /F1 12 Tf 72 720 Td"]
        for i, seg in enumerate(text_line.split("\\n")):
            if i > 0:
                ops.append("0 -20 Td")
            ops.append(f"({seg}) Tj")
        ops.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.add_page(page)

    # Attach XMP stream containing forbidden author name with standard XML namespaces
    xmp = DecodedStreamObject()
    xmp.set_data(
        b'<?xpacket begin=""?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<rdf:Description dc:creator="SecretAuthorXMP"/>'
        b'</rdf:RDF></x:xmpmeta>'
    )
    writer._root_object[NameObject("/Metadata")] = writer._add_object(xmp)

    pdf_file = tmp_path / "shared_ref.pdf"
    with pdf_file.open("wb") as fh:
        writer.write(fh)

    # Page 2 has substantive body prose BEFORE References -> body_pages == 2 (> max_pages=1)
    lim_err = pre_submission_linter._check_pdf_page_limit(pdf_file, max_pages=1)
    assert any(f["code"] == "PDF_PAGE_LIMIT_EXCEEDED" for f in lim_err)
    assert pre_submission_linter._check_pdf_page_limit(pdf_file, max_pages=2) == []

    # Double-blind sanitizer scans PDF via controlled_read_pdf_pages worker and catches XMP leak
    scan = double_blind_sanitizer.scan_target(pdf_file, forbidden_tokens=["SecretAuthorXMP"])
    assert any(
        f.get("kind") in ("forbidden_token", "non_anonymous_pdf_metadata_author")
        and "SecretAuthorXMP" in str(f.get("matched"))
        for f in scan["findings"]
    )


def test_p1_10_locate_oa_email_priority_and_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
    norm = {"type": "doi", "normalized": "10.1038/nature14539"}
    rc_missing, rep_missing = locate_oa.resolve_oa(norm, email=None, fallback_openalex=False)
    assert rc_missing == 2
    assert rep_missing["is_oa"] is None
    assert rep_missing["status"] == "skipped"

    seen_emails: list[str] = []

    def fake_unpaywall(doi: str, email: str):
        seen_emails.append(email)
        return {"is_oa": True, "best_oa_location": {"url_for_pdf": "https://example.org/oa.pdf", "host_type": "repository"}}

    monkeypatch.setattr(locate_oa, "live_unpaywall", fake_unpaywall)
    monkeypatch.setenv("UNPAYWALL_EMAIL", "env-user@university.edu")
    rc_env, rep_env = locate_oa.resolve_oa(norm, email=None, fallback_openalex=False)
    assert rc_env == 0
    assert seen_emails[-1] == "env-user@university.edu"
    assert rep_env["is_oa"] is True
    assert rep_env["oa_url"] == "https://example.org/oa.pdf"

    rc_arg, _ = locate_oa.resolve_oa(norm, email="cli-override@university.edu", fallback_openalex=False)
    assert rc_arg == 0
    assert seen_emails[-1] == "cli-override@university.edu"


def test_p1_11_legacy_watch_migration_stdin_repro_and_five_skills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    legacy_json = tmp_path / "old_watch.json"
    legacy_json.write_text(
        json.dumps({"dois": {"10.1000/ret1": {"is_retracted": True, "signals": ["crossref:update:r1"]}}}),
        encoding="utf-8",
    )
    db_file = tmp_path / "watch.sqlite3"
    rc = cli.main(["retraction-watch", "--import-legacy-json", str(legacy_json), "--state-db", str(db_file)])
    assert rc == 0
    with ResearchStateDB(db_file, readonly=True) as db:
        with db._read_snapshot() as conn:
            row = conn.execute(
                "SELECT confirmed_retracted FROM doi_watch_state WHERE watcher = 'retraction' AND item_key = '10.1000/ret1'"
            ).fetchone()
            assert row is not None and row["confirmed_retracted"] == 1

    # Passing a .json path to --state-db returns a clear migration error (exit 1)
    assert cli.main(["retraction-watch", "--dois", "10.1000/ret1", "--state-db", str(legacy_json)]) == 1

    # Verify repro-checklist accepts piped JSON via stdin (P2-04)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({"paper": {"title": "Synthetic Repro Paper"}, "stages": []})),
    )
    assert cli.main(["repro-checklist"]) == 0

    # Verify the 7 first-principles skills, metadata hygiene, and cleaned READMEs
    expected_skills = {
        "audit-paper",
        "verify-citations",
        "audit-peer-review",
        "meta-analysis",
        "check-submission",
        "cross-review",
        "compute-math",
    }
    actual_skills = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
    assert actual_skills == expected_skills
    for sp in list((ROOT / "skills").glob("*/SKILL.md")) + [ROOT / "src/academic_research_kernel/portable_skills/audit-paper/SKILL.md"]:
        stxt = sp.read_text(encoding="utf-8")
        assert "\t" not in stxt, f"Tab character found in {sp}"
        assert "author: Junfu Shi (SJF, xngg1021)" in stxt
        assert "Hermes Agent" not in stxt.splitlines()[:10]
        assert "license: LicenseRef-Source-Lineage-1.0" in stxt
    assert not (ROOT / "i18n").exists()
    for rname in ("README.md", "README.zh-CN.md"):
        rtxt = (ROOT / rname).read_text(encoding="utf-8")
        assert "3.0.0" in rtxt
        assert "==2.4.2" not in rtxt
        assert "uv run --frozen --no-dev --no-editable python scripts/" not in rtxt


def test_p2_01_sqlite_rejects_future_user_version_without_downgrade(tmp_path: Path) -> None:
    future_db = tmp_path / "future.sqlite3"
    conn = sqlite3.connect(future_db)
    conn.execute(f"PRAGMA application_id = {ARK_SQLITE_APP_ID}")
    conn.execute("PRAGMA user_version = 999")
    conn.commit()
    conn.close()

    with pytest.raises(ValueError, match="Unsupported ARK SQLite schema user_version=999"):
        ResearchStateDB(future_db)

    conn2 = sqlite3.connect(future_db)
    uv = conn2.execute("PRAGMA user_version").fetchone()[0]
    conn2.close()
    assert uv == 999


def test_p2_05_meta_core_extreme_small_variance_and_egger_zero_residual() -> None:
    yi = [0.5, 0.5, 0.5]
    vi = [1e-320, 1e-320, 2e-320]
    fe = meta_core.pool_fixed(yi, vi)
    dl = meta_core.pool_dl(yi, vi)
    q, df, i2, tau2 = meta_core.heterogeneity(yi, vi)
    assert fe.estimate == pytest.approx(0.5)
    assert dl.estimate == pytest.approx(0.5)
    assert q == pytest.approx(0.0)
    assert (df, i2, tau2) == (2, 0.0, 0.0)

    # Divergent effect estimates with 1e-320 variance exceed float64 Q range -> explicit ValueError instead of silent NaN
    with pytest.raises(ValueError, match="overflowed float64"):
        meta_core.pool_fixed([0.5, 0.7], [1e-320, 1e-320])

    with pytest.raises(ValueError, match="residual variance is zero"):
        meta_core.egger_test([0.2, 0.4, 0.6], [0.01, 0.04, 0.09])


def test_multi_venue_openreview_forensics_iclr_icml_neurips() -> None:
    records = [
        # ICLR 2027 style (rating 1-4 + informativeness + identical scores + zero discussion)
        {
            "id": "iclr27_a",
            "title": "Agent Paper A",
            "status": "Active",
            "rating": "2;2;2;2",
            "confidence": "2;4;2;4",
            "informativeness": "2;3;2;2",
            "wc_review": "490;500;492;495",
            "replies_avg": [4, 0],
        },
        # ICML / NeurIPS style (recommendation / clarity + active discussion)
        {
            "id": "icml26_b",
            "title": "Systems Paper B",
            "status": "Poster",
            "recommendation": "3;4;5",
            "confidence": "3;4;5",
            "clarity": "4;4;5",
            "wc_strengths_and_weaknesses": "400;450;500",
            "wc_limitations": "50;50;50",
            "replies_avg": [11, 2.3],
        },
    ]
    summary = openreview_audit.summarize_venue_mirror(records)
    assert summary["scored_submissions"] == 2
    forensics = summary["review_forensics"]
    assert forensics["unanimous_identical_rating_count"] == 1
    assert forensics["unanimous_identical_rating_share"] == 0.5
    assert forensics["zero_discussion_beyond_reviews_share"] == 0.5
    assert forensics["word_count_median_by_confidence"]["2"] == 491.0


def test_post_review_sol_and_astra_hardening_regressions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Sol-F5 & F6: SQLite export_ceg_dict passes claim_evidence_validate & multi-claim dependency cycles fail
    with ResearchStateDB(":memory:") as db:
        db.add_claim("c1", "Accuracy is 92.5% on 100 samples")
        exported = db.export_ceg_dict()
        v_ok = mcp_server.handle_tool_call("claim_evidence_validate", {"ceg": exported})
        assert v_ok["valid"] is True, v_ok

        cyc_ceg = {
            **exported,
            "claims": [
                *exported["claims"],
                {
                    "id": "c2",
                    "text": "Secondary claim",
                    "normalized_text": "Secondary claim",
                    "claim_type": "generic_claim",
                    "claim_digest": "c" * 64,
                },
            ],
            "claim_relations": [
                {"source_claim_id": "c1", "target_claim_id": "c2", "relation_type": "depends_on"},
                {"source_claim_id": "c2", "target_claim_id": "c1", "relation_type": "depends_on"},
            ],
        }
        v_cyc = mcp_server.handle_tool_call("claim_evidence_validate", {"ceg": cyc_ceg})
        assert v_cyc["valid"] is False
        assert any("cycle" in e for e in v_cyc["errors"])

    # 2. Sol-F8 & F9: DL variance dominance (no cancellation to 0) & large float64 pooling without premature overflow
    dl_dom = meta_core.pool_random([0.0, 2.0], [1e-20, 1.0])
    assert dl_dom.tau2 == pytest.approx(1.5, rel=1e-6)
    assert dl_dom.estimate == pytest.approx(0.75, rel=1e-6)
    big_fe = meta_core.pool_fixed([1e308, 1e308], [1e308, 1e308])
    assert big_fe.estimate == pytest.approx(1e308)

    # 3. Sol-F10 & F11: 1,200-node iterative lineage chain + activity-mediated root_ancestors
    long_edges = [{"child_id": str(i), "parent_id": str(i + 1)} for i in range(1200)]
    long_res = mcp_server.handle_tool_call("research_lineage_trace", {"lineage": {"edges": long_edges}, "target_id": "0"})
    assert long_res["chain_length"] == 1201
    assert long_res["root_ancestors"] == ["1200"]

    act_graph = {
        "entities": [{"id": "e0"}, {"id": "e1"}, {"id": "e2"}],
        "activities": [{"id": "a1"}, {"id": "a2"}],
        "edges": [
            {"type": "used", "source_id": "a1", "target_id": "e0"},
            {"type": "generated", "source_id": "a1", "target_id": "e1"},
            {"type": "used", "source_id": "a2", "target_id": "e1"},
            {"type": "generated", "source_id": "a2", "target_id": "e2"},
        ],
    }
    act_res = mcp_server.handle_tool_call("research_lineage_trace", {"lineage": act_graph, "target_id": "e2"})
    assert act_res["root_ancestors"] == ["e0"]

    # 4. Astra-1: Standard nested XMP <dc:creator><rdf:Seq><rdf:li>Alice Smith</rdf:li></rdf:Seq></dc:creator>
    xmp_seq = (
        '<?xpacket begin=""?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<rdf:Description><dc:creator><rdf:Seq><rdf:li>Alice Smith</rdf:li></rdf:Seq></dc:creator></rdf:Description>'
        '</rdf:RDF></x:xmpmeta>'
    )
    xmp_entries = double_blind_sanitizer._extract_xmp_entries(xmp_seq)
    assert any("creator" in k.lower() and v == "Alice Smith" for k, v in xmp_entries)

    # 5. Astra-2, 3, 4, 5, 11, 12: TeX percent, CEG numeric subset, local glyphtounicode.tex, mixed author, \cref{a,b}, \verb|%|
    (tmp_path / "glyphtounicode.tex").write_text(r"\author{Hidden Local Author}" + "\n", encoding="utf-8")
    tex_f = tmp_path / "m.tex"
    tex_f.write_text(
        r"""\documentclass{article}
\author{Anonymous Authors and Alice Smith}
\begin{document}
\begin{abstract}Summary.\end{abstract}
\section{Intro}
\label{sec:a}\label{sec:b}See \cref{sec:a,sec:b}.
\verb|%| \input{glyphtounicode}
Accuracy is 12.5\%.
\end{document}
""",
        encoding="utf-8",
    )
    lint_r = pre_submission_linter.lint_manuscript(tex_f, venue=None, double_blind=True, require_ceg_binding=True)
    l_codes = [f["code"] for f in lint_r["findings"]]
    assert l_codes.count("BLIND_AUTHOR_LEAK") == 2  # both main.tex mixed author and local glyphtounicode.tex
    assert "UNRESOLVED_REFERENCE" not in l_codes
    assert "UNGROUNDED_QUANT_CLAIM" in l_codes

    # 6. Astra-6, 7, 8: Meta-review not decision, forum-less note ignored, NA confidence slot alignment
    mr_payload = {
        "notes": [
            {"id": "F1", "forum": "F1", "content": {"venue": {"value": "Submitted to ICLR 2027"}, "authors": {"value": ["Anonymous"]}}},
            {"id": "M1", "forum": "F1", "invitations": ["ICLR.cc/2027/Conference/Submission1/-/Meta_Review"], "content": {"recommendation": {"value": "Accept"}}},
            {"id": "ORPHAN", "invitations": ["ICLR.cc/2027/Conference/Submission1/-/Decision"], "content": {"decision": {"value": "Accept"}}},
        ]
    }
    parsed_or = openreview_audit.parse_openreview_notes(mr_payload, forum_id="F1")
    assert parsed_or["status_classification"] == "under_review"
    aligned = openreview_audit.summarize_venue_mirror([{"id": "F2", "rating": "2;4", "confidence": "NA;4", "wc_review": "100;900"}])
    assert aligned["review_forensics"]["word_count_median_by_confidence"] == {"4": 900.0}

    # 7. Astra-9 & 10: Unpaywall network timeout falls back to OpenAlex with uniform identifier & oa_url
    monkeypatch.setattr(locate_oa, "live_unpaywall", lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("up timeout")))
    monkeypatch.setattr(
        locate_oa,
        "live_openalex_oa",
        lambda d: {"doi": d, "open_access": {"is_oa": True, "oa_url": "https://example.org/fallback.pdf"}},
    )
    rc_fb, rep_fb = locate_oa.resolve_oa({"type": "doi", "value": "10.1000/fb"}, email="u@example.edu", fallback_openalex=True)
    assert rc_fb == 0
    assert rep_fb["oa_url"] == "https://example.org/fallback.pdf"
    assert "unpaywall_error" in rep_fb

    # 8. Astra-15: Verify peer-review-forensics-2025-2027-v1.json aggregate totals equal exact sum of venues
    bench = json.loads((ROOT / "docs" / "benchmarks" / "peer-review-forensics-2025-2027-v1.json").read_text(encoding="utf-8"))
    assert sum(v["paper_count"] for v in bench["venues"]) == bench["aggregate_totals"]["total_public_records"] == 74933
    assert sum(v["total_reviews"] for v in bench["venues"]) == bench["aggregate_totals"]["total_reviews"] == 234128


def test_restored_14_to_7_skill_capabilities_and_schemas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import sys
    from jsonschema import Draft7Validator, Draft202012Validator
    from academic_research_kernel import collect_corpus, compute_probe, cross_review, github_repo_forensics

    schema_dir = ROOT / "src" / "academic_research_kernel" / "schemas"

    # 1. cross-review inline MCP + CLI 4-stage sparse deliberation + schema validation
    real_ev_file = tmp_path / "target_mod.py"
    real_ev_file.write_text("x = 1\n", encoding="utf-8")
    inline_findings = {
        "seat-a": [
            # Duplicate target+key from same model MUST stay singleton (C01)
            {"id": "A1", "target": "target_mod.py", "issue_key": "null-guard", "polarity": "present", "severity": "P0", "claim": "Null guard missing", "evidence": [f"{real_ev_file}:1"]},
            {"id": "A2", "target": "target_mod.py", "issue_key": "null-guard", "polarity": "present", "severity": "P1", "claim": "Null guard still missing", "evidence": [f"{real_ev_file}:1"]},
            {"id": "A3", "target": "src/api.py", "issue_key": "timeout", "polarity": "present", "severity": "P1", "claim": "Timeout present", "evidence": ["src/api.py:10"]},
        ],
        "seat-b": [
            # Opposing polarity on src/api.py -> contradiction (C02)
            {"id": "B1", "target": "src/api.py", "issue_key": "timeout", "polarity": "absent", "severity": "P1", "claim": "Timeout absent", "evidence": ["src/api.py:10"]},
            {"id": "B2", "target": "src/shared.py", "issue_key": "race", "polarity": "present", "severity": "P1", "claim": "Race condition", "evidence": ["src/shared.py:5"]},
        ],
        "seat-c": [
            {"id": "C1", "target": "src/shared.py", "issue_key": "race", "polarity": "present", "severity": "P0", "claim": "Race condition confirmed", "evidence": ["src/shared.py:5"]},
            # Ghost absolute evidence -> discarded during synthesis (C07)
            {"id": "C2", "target": "ghost.py", "issue_key": "ghost-bug", "severity": "P0", "claim": "Ghost claim", "evidence": [str(tmp_path / "nonexistent_ghost.py") + ":9"]},
        ],
    }
    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    mcp_cr = mcp_server.handle_tool_call("academic_cross_review", {"findings_by_model": inline_findings, "mode": "audit"})
    Draft202012Validator(json.loads((schema_dir / "cross-review-artifact.schema.json").read_text("utf-8"))).validate(mcp_cr["registry"])
    assert mcp_cr["registry"]["stats"]["consensus_count"] == 1  # src/shared.py
    assert mcp_cr["registry"]["stats"]["contradiction_count"] == 1  # src/api.py
    assert mcp_cr["registry"]["stats"]["singleton_count"] == 2  # target_mod.py + ghost.py
    # Challenger for src/api.py contradiction MUST exclude seat-a and seat-b -> must be seat-c (C06)
    c_contradict = [c for c in mcp_cr["challenge_plan"] if c["type"] == "contradiction"][0]
    assert c_contradict["reviewer"] == "seat-c"
    assert all(d["reviewer"] != d["target"] for d in mcp_cr["derangement_pairings"])

    # Synthesis with replies: C01 conceded, singleton target_mod.py unrefuted -> preserved in unresolved_ledger; ghost discarded
    replies = {c["challenge_id"]: "【CONCEDE】 Proposal-1 verified on line 10." for c in mcp_cr["challenge_plan"]}
    mcp_syn = mcp_server.handle_tool_call(
        "academic_cross_review",
        {"findings_by_model": inline_findings, "mode": "standard", "challenge_replies": replies},
    )["synthesis"]
    Draft7Validator(json.loads((schema_dir / "review-run-receipt.schema.json").read_text("utf-8"))).validate(mcp_syn["receipt"])
    assert any(u.get("target") == "target_mod.py" for u in mcp_syn["unresolved_ledger"])
    assert len(mcp_syn["ghost_discarded"]) == 1

    # End-to-end CLI cross-review stage=all in a directory with spaces in path
    spaced_dir = tmp_path / "stream with spaces"
    task_md = tmp_path / "task.md"
    task_md.write_text("Audit sample module.\n", encoding="utf-8")
    worker_script = tmp_path / "mock_worker.py"
    worker_script.write_text(
        "import json, pathlib, sys\n"
        "out_p = pathlib.Path(sys.argv[1])\n"
        "out_p.write_text('# Review\\n\\n【CONCEDE】 Proposal-1 ok.\\n', encoding='utf-8')\n"
        "if len(sys.argv) > 2 and sys.argv[2] != 'NONE':\n"
        "    pathlib.Path(sys.argv[2]).write_text(json.dumps({'findings': [{'id': 'F1', 'target': 'a.py', 'issue_key': 'k1', 'severity': 'P1', 'claim': 'Bug', 'evidence': ['a.py:1']}]}), encoding='utf-8')\n",
        encoding="utf-8",
    )
    py_exe = sys.executable.replace("\\", "/")
    w_str = str(worker_script).replace("\\", "/")
    panel_json = tmp_path / "panel.json"
    panel_json.write_text(
        json.dumps([
            {"id": "alpha", "executor": "command", "cmd": f'"{py_exe}" "{w_str}" "{{out_path}}" "{{findings_path}}"'},
            {"id": "beta", "executor": "command", "cmd": f'"{py_exe}" "{w_str}" "{{out_path}}" "{{findings_path}}"'},
        ]),
        encoding="utf-8",
    )
    assert cli.main(["cross-review", str(spaced_dir), "--models-file", str(panel_json), "--task", str(task_md), "--stage", "all"]) == 0
    assert (spaced_dir / "consensus-report.md").is_file()
    assert (spaced_dir / "review-run-receipt.json").is_file()

    # 2. compute-probe & ComputeReceipt schema validation
    cp_rep = mcp_server.handle_tool_call("academic_compute_probe", {"emit_receipt": True, "scale": "small"})
    Draft7Validator(json.loads((schema_dir / "compute-receipt.schema.json").read_text("utf-8"))).validate(cp_rep)
    cp_out = tmp_path / "comp.json"
    assert cli.main(["compute-probe", "--receipt", "--output", str(cp_out)]) == 0
    assert cp_out.is_file()

    # 3. collect-corpus Union-Find merge & DOI conflict preservation
    layers_file = tmp_path / "layers.json"
    layers_file.write_text(
        json.dumps({
            "text-search": [
                {"id": "https://openalex.org/W100", "doi": "10.1000/same", "title": "Paper Same", "relevance_score": 12.5},
                {"id": "https://openalex.org/W999", "doi": "10.1000/conflict-a", "title": "Conflict A"},
            ],
            "algorithmic-related": [
                {"id": "W100", "cited_by_count": 42},
                {"id": "W999", "doi": "10.1000/conflict-b", "title": "Conflict B"},
            ],
        }),
        encoding="utf-8",
    )
    capsys.readouterr()
    assert cli.main(["collect-corpus", "--input", str(layers_file)]) == 0
    cc_res = json.loads(capsys.readouterr().out)
    assert cc_res["count"] == 3  # W100 merged into 1, conflicting W999 DOIs kept separate!
    w100 = [c for c in cc_res["candidates"] if c["doi"] == "10.1000/same"][0]
    assert set(w100["source_layers"]) == {"text-search", "algorithmic-related"}
    assert w100["cited_by_count"] == 42

    # 4. locate-oa --fallback-all cascading to Semantic Scholar & Europe PMC
    monkeypatch.setattr(locate_oa, "live_openalex_oa", lambda d: {"doi": d, "open_access": {"is_oa": False}})
    monkeypatch.setattr(locate_oa, "live_semantic_scholar_oa", lambda _d: None)
    monkeypatch.setattr(
        locate_oa,
        "live_europe_pmc_oa",
        lambda _d: {"url_for_pdf": "https://europepmc.org/articles/PMC1/pdf/main.pdf", "url": "https://europepmc.org/articles/PMC1", "source": "Europe PMC"},
    )
    rc_all, rep_all = locate_oa.resolve_oa({"type": "doi", "value": "10.1000/epmc"}, email=None, fallback_all=True)
    assert rc_all == 0 and rep_all["mode"] == "europe-pmc-fallback"
    assert rep_all["oa_url"] == "https://europepmc.org/articles/PMC1/pdf/main.pdf"

    # 5. repo-forensics --github-repo & generate-table --rows / --cols
    monkeypatch.setattr(
        github_repo_forensics,
        "fetch_github_tree",
        lambda slug: ([{"path": "src/pkg/core.py", "size": 380}, {"path": "tests/test_core.py", "size": 190}], False, "abc1234", "github-rest"),
    )
    capsys.readouterr()
    assert cli.main(["repo-forensics", "--github-repo", "owner/repo"]) == 0
    rf_out = json.loads(capsys.readouterr().out)
    assert rf_out["mode"] == "github-rest" and rf_out["first_party_core"]["file_count"] == 1

    nested_tbl = tmp_path / "nested_table.json"
    nested_tbl.write_text(json.dumps({"exp": {"rows": [["Ours", 95.2], ["Base", 90.1]]}}), encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["generate-table", str(nested_tbl), "--rows", "exp.rows", "--cols", "Method,Acc"]) == 0
    tex_tbl = capsys.readouterr().out
    assert "Method & Acc" in tex_tbl and "95.20" in tex_tbl

    # 6. Subgroup analysis + WLS meta-regression + ledger CLI
    meta_res = mcp_server.handle_tool_call(
        "academic_meta_analyze",
        {
            "studies": [
                {"yi": 0.2, "vi": 0.04, "subgroup": "low_dose", "moderator": 10.0},
                {"yi": 0.25, "vi": 0.05, "subgroup": "low_dose", "moderator": 15.0},
                {"yi": 0.8, "vi": 0.04, "subgroup": "high_dose", "moderator": 40.0},
                {"yi": 0.9, "vi": 0.05, "subgroup": "high_dose", "moderator": 50.0},
            ]
        },
    )
    assert meta_res["subgroup_analysis"]["q_between"] > 5.0
    assert meta_res["meta_regression"]["slope"] > 0.01

    st_db = tmp_path / "ledger.sqlite3"
    ceg_out = tmp_path / "exported_ceg.json"
    assert cli.main(["ledger", "--db", str(st_db), "--action", "add-claim", "--claim-id", "c1", "--text", "Gain is 5.1%.", "--artifact-id", "art1", "--locator", "Table 1"]) == 0
    assert cli.main(["ledger", "--db", str(st_db), "--action", "export-ceg", "--output", str(ceg_out)]) == 0
    assert cli.main(["ledger", "--db", str(st_db), "--action", "validate-ceg"]) == 0
    assert cli.main(["ledger", "--db", str(st_db), "--action", "record-decision", "--decision-id", "d0", "--title", "Explore heuristic", "--rationale", "Initial run"]) == 0
    assert cli.main(["ledger", "--db", str(st_db), "--action", "record-decision", "--decision-id", "d1", "--basis-decision-id", "d0", "--title", "Drop heuristic", "--rationale", "Failed ablation", "--is-negative-result", "--artifact-id", "art1"]) == 0
    assert cli.main(["ledger", "--db", str(st_db), "--action", "transition-decision", "--decision-id", "d0", "--status", "pruned", "--reason", "contradicted"]) == 0
    assert cli.main(["ledger", "--db", str(st_db), "--action", "correct-decision", "--decision-id", "d0", "--verdict", "negative", "--rationale", "Post-hoc check", "--artifact-id", "art1"]) == 0
    assert cli.main(["ledger", "--db", str(st_db), "--action", "export-decisions", "--output", str(tmp_path / "decisions.json")]) == 0
    assert cli.main(["ledger", "--db", str(st_db), "--action", "validate-decisions"]) == 0


def test_sol_astra_r2_regression_suite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sqlite3
    import sys
    from academic_research_kernel import collect_corpus, compute_probe, cross_review, github_repo_forensics, meta_core

    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))

    # 1. Sol-1 & Sol-2 & Sol-5: Shuffled Proposal-k mapping, empty contradiction reply, and word-boundary opposition
    real_f = tmp_path / "m.py"
    real_f.write_text("y = 2\n", encoding="utf-8")
    findings = {
        "s1": {
            "findings": [
                {"target": "m.py", "issue_key": "multi", "severity": "P0", "claim": "First true claim", "evidence": [f"{real_f}:1"]},
                {"target": "m.py", "issue_key": "multi", "severity": "P0", "claim": "Second false claim", "evidence": [f"{real_f}:1"]},
                {"target": "v.py", "issue_key": "chk", "severity": "P1", "claim": "Schema is valid", "evidence": ["v.py:3"]},
            ]
        },
        "s2": {
            "findings": [
                {"target": "v.py", "issue_key": "chk", "severity": "P1", "claim": "Schema is invalid", "evidence": ["v.py:3"]},
            ]
        },
        "s3": {"findings": []},
    }
    reg, chals, _ = cross_review.plan_challenges(["s1", "s2", "s3"], findings, mode="standard", run_id="seed-shuffle-check")
    assert len(reg["contradictions"]) == 1  # "valid" vs "invalid" word-boundary opposition!
    c_contra = next(c for c in chals if c["type"] == "contradiction")
    c_sing = next(c for c in chals if c["type"] == "singleton_audit")

    # Empty reply on contradiction MUST NOT yield CONVERGED
    syn_empty = cross_review.synthesize_deliberation(
        reg,
        chals,
        {c_contra["challenge_id"]: "No tags here at all", c_sing["challenge_id"]: "【CONCEDE】 Verified."},
        base_dirs=[tmp_path],
    )
    assert syn_empty["convergence_status"] == "PARTIAL_PROGRESS"
    assert len(syn_empty["uncontested_contradictions"]) == 1

    # Refuting whichever Proposal-k corresponds to original claim 2 MUST preserve original claim 1!
    inv_map = {orig_idx: pkey for pkey, orig_idx in c_sing["proposal_map"].items()}
    prop_for_claim2 = inv_map[2].replace("proposal", "Proposal-")
    syn_ref2 = cross_review.synthesize_deliberation(
        reg,
        chals,
        {
            c_contra["challenge_id"]: "【CONCEDE】 Confirmed invalid.",
            c_sing["challenge_id"]: f"【REFUTED】 {prop_for_claim2} is wrong.",
        },
        base_dirs=[tmp_path],
    )
    kept = [u for u in syn_ref2["unresolved_ledger"] if u.get("issue_id") == c_sing["issue_id"]]
    assert len(kept) == 1
    assert [cl["claim"] for cl in kept[0]["claims"]] == ["First true claim"]

    # 2. Sol-4 & Sol-6 & Astra-5: Command argv array + stdin piping + --stage all exit code propagation
    echo_script = tmp_path / "stdin_echo.py"
    echo_script.write_text(
        "import pathlib, sys\n"
        "data = sys.stdin.read()\n"
        "out = pathlib.Path(sys.argv[1])\n"
        "out.write_text('STDIN_LEN=' + str(len(data)) + '\\n【CONCEDE】 ok\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    panel_ok = tmp_path / "panel_ok.json"
    panel_ok.write_text(
        json.dumps([
            {"id": "p1", "executor": "command", "cmd": [sys.executable, str(echo_script), "{out_path}", "-"]},
            {"id": "p2", "executor": "command", "cmd": f'"{sys.executable}" "{echo_script}" "{{out_path}}" < "{{prompt_path}}"'},
        ]),
        encoding="utf-8",
    )
    task_md = tmp_path / "t.md"
    task_md.write_text("Review task body.\n", encoding="utf-8")
    s_ok = tmp_path / "stream_ok"
    assert cli.main(["cross-review", str(s_ok), "--models-file", str(panel_ok), "--task", str(task_md), "--stage", "all"]) == 0
    assert "STDIN_LEN=" in (s_ok / "review-p1.md").read_text(encoding="utf-8")
    assert "STDIN_LEN=" in (s_ok / "review-p2.md").read_text(encoding="utf-8")

    panel_fail = tmp_path / "panel_fail.json"
    panel_fail.write_text(
        json.dumps([
            {"id": "f1", "executor": "command", "cmd": [sys.executable, "-c", "import sys; sys.exit(2)"]},
            {"id": "f2", "executor": "command", "cmd": [sys.executable, "-c", "import sys; sys.exit(2)"]},
        ]),
        encoding="utf-8",
    )
    assert cli.main(["cross-review", str(tmp_path / "stream_fail"), "--models-file", str(panel_fail), "--task", str(task_md), "--stage", "all"]) == 1

    # 3. Sol-7 & Sol-9: compute_probe operation validation + sub-cgroup quota
    svd_rec = compute_probe.build_compute_receipt(operation="svd_f64", scale="small")
    assert svd_rec["operation"] == "svd_f64"
    with pytest.raises(ValueError, match="Unsupported operation"):
        compute_probe.build_compute_receipt(operation="nonexistent_kernel")

    fake_proc = tmp_path / "proc_cgroup"
    fake_cg = tmp_path / "cgroup"
    (fake_cg / "user.slice" / "job.scope").mkdir(parents=True)
    (fake_cg / "cpu.max").write_text("max 100000\n", encoding="utf-8")
    (fake_cg / "user.slice" / "job.scope" / "cpu.max").write_text("250000 100000\n", encoding="utf-8")
    fake_proc.write_text("0::/user.slice/job.scope\n", encoding="utf-8")
    assert compute_probe._cgroup_cpu_quota(fake_proc, fake_cg) == pytest.approx(2.5)

    # 4. Sol-10 & Sol-11: collect_corpus order independence & authorships normalization
    l_a = [{"id": "https://openalex.org/W9", "doi": "10.1000/x", "title": "Short", "cited_by_count": 5}]
    l_b = [{"id": "https://openalex.org/W9", "title": "Full Canonical Paper Title", "cited_by_count": 12, "authorships": [{"name": "A. Researcher"}]}]
    m1 = collect_corpus.merge_candidates({"text-search": l_a, "citation-pool": l_b})
    m2 = collect_corpus.merge_candidates({"citation-pool": l_b, "text-search": l_a})
    assert m1 == m2
    assert m1["candidates"][0]["authors"] == [{"name": "A. Researcher"}]
    assert m1["candidates"][0]["cited_by_count"] == 12

    # 5. Sol-12 & Sol-13: URL-encoded '#' branch in fetch_github_tree + extreme 1e-320 variance in meta_regression
    seen_urls: list[str] = []

    class _FakeResp:
        def __init__(self, obj: dict) -> None:
            self._b = json.dumps(obj).encode("utf-8")

        def read(self, *_a: object) -> bytes:
            b, self._b = self._b, b""
            return b

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    def _fake_urlopen(req: object, **_kw: object) -> _FakeResp:
        url = getattr(req, "full_url", str(req))
        seen_urls.append(url)
        if url.endswith("/repos/org/repo"):
            return _FakeResp({"default_branch": "release#1"})
        return _FakeResp({"sha": "deadbeef", "truncated": False, "tree": [{"path": "src/a.py", "type": "blob", "size": 10}]})

    monkeypatch.setattr("shutil.which", lambda _x: None)
    monkeypatch.setattr("academic_research_kernel.research.sources.controlled_urlopen", _fake_urlopen)
    entries, _, _, via = github_repo_forensics.fetch_github_tree("org/repo")
    assert via == "github-rest" and len(entries) == 1
    assert any("release%231?recursive=1" in u for u in seen_urls)

    tiny_reg = meta_core.meta_regression([0.1, 0.2, 0.4], [1e-320, 1e-320, 1e-320], [1.0, 2.0, 4.0], model="fixed")
    assert tiny_reg["slope"] == pytest.approx(0.1)
    assert tiny_reg["se_slope"] > 0.0

    # 6. Sol-3 & Astra-2, 6, 7: Bidirectional CEG contradicts + SQLite hash-verified lineage + decision tamper detection
    db_p = tmp_path / "tamper.sqlite3"
    with ResearchStateDB(db_p) as db:
        db.register_artifact("root_a", "data_snapshot", {"v": 1})
        db.batch_ingest([{"artifact_id": "child_b", "kind": "computed_evidence", "payload": {"v": 2}, "parents": ["root_a"]}])
        db.add_claim("c_left", "Metric improves.", evidence=[("child_b", "supports", "T1")])
        db.add_claim("c_right", "Metric degrades.", evidence=[("child_b", "supports", "T2")])
        db.add_claim_relation("c_left", "c_right", "contradicts")
        db.add_claim_relation("c_right", "c_left", "contradicts")
        ceg = db.export_ceg_dict()
        assert len(ceg["claim_relations"]) == 2
        assert any(u["kind"] == "unresolved_contradiction" for u in ceg["uncertainties"])
        assert mcp_server.handle_tool_call("claim_evidence_validate", {"ceg": ceg})["valid"] is True

        lin_ok = mcp_server.handle_tool_call("research_lineage_trace", {"db_path": str(db_p), "artifact_id": "child_b"})
        assert lin_ok["verification_status"] == "intact" and lin_ok["root_ancestors"] == ["root_a"] and lin_ok["chain_length"] == 1
        lin_miss = mcp_server.handle_tool_call("research_lineage_trace", {"db_path": str(db_p), "artifact_id": "unknown_x"})
        assert lin_miss["verification_status"] == "missing_input"

        db.record_decision("d_base", "Initial plan")

    # Tamper payload_sha256 & inject illegal active->active event directly in SQLite to verify validators catch both!
    raw = sqlite3.connect(str(db_p))
    raw.execute("DROP TRIGGER trg_artifacts_immutable_upd")
    raw.execute("UPDATE artifacts SET payload_sha256 = ? WHERE artifact_id = 'root_a'", ("0" * 64,))
    raw.execute("INSERT INTO decision_events (decision_id, new_state, reason) VALUES ('d_base', 'active', 'other')")
    raw.commit()
    raw.close()

    lin_bad = mcp_server.handle_tool_call("research_lineage_trace", {"db_path": str(db_p), "artifact_id": "child_b"})
    assert lin_bad["verification_status"] == "corrupted"
    assert cli.main(["ledger", "--db", str(db_p), "--action", "validate-decisions"]) == 1
    assert mcp_server.handle_tool_call("decision_ledger_validate", {"db_path": str(db_p)})["valid"] is False
