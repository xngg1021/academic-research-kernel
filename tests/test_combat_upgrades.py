"""Tests for the 4 real-world combat upgrades and all cross-audit counterexamples:
1. AI/CS table forensics (partition conservation, constant-offset ablation delta, storage/bandwidth bounds)
2. OpenAlex & institutional repository OA fallback when publisher returns 403 WAF
3. OpenReview API v2 submission status classifier & GitHub repository tree forensics
4. Author-side receipt-to-LaTeX booktabs generator & double-blind anonymity sanitizer
"""
from __future__ import annotations
import re
from collections import Counter

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(rel_path: str, mod_name: str):
    import sys
    spec = importlib.util.spec_from_file_location(mod_name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


recompute = _load_script("skills/quantitative-paper-audit/scripts/recompute.py", "recompute_combat")
locate_oa = _load_script("skills/academic-source-verification/scripts/locate_oa.py", "locate_oa_combat")
or_audit = _load_script("skills/academic-source-verification/scripts/openreview_audit.py", "or_audit_combat")
gh_forensics = _load_script("skills/academic-source-verification/scripts/github_repo_forensics.py", "gh_forensics_combat")
ltx_table = _load_script("skills/academic-writing/scripts/receipt_to_latex_table.py", "ltx_table_combat")
blind_san = _load_script("skills/academic-writing/scripts/double_blind_sanitizer.py", "blind_san_combat")


def test_partition_conservation_catches_missing_rows_and_share_mismatch():
    ok = recompute.check_partition_conservation(1000, [900, 100], reported_shares=[90.0, 10.0])
    assert ok["consistent"] is True
    assert ok["missing_or_excess"] == 0

    # Synthetic mismatch case: Total=500,000, Train=300,000, Test=25,000 (missing 175,000 rows, test=5.0% vs claimed 10%)
    bad = recompute.check_partition_conservation(500000, [300000, 25000], reported_shares=[90.0, 10.0])
    assert bad["consistent"] is False
    assert bad["sum_consistent"] is False
    assert bad["sum_parts"] == 325000
    assert bad["missing_or_excess"] == 175000
    assert len(bad["share_mismatches"]) == 2

    # Cross-audit counterexample: fractions summing > 1.05 (e.g. [0.80, 0.20, 0.10] on [800, 100, 100])
    frac_over = recompute.check_partition_conservation(1000, [800, 100, 100], reported_shares=[0.80, 0.20, 0.10])
    assert frac_over["resolved_share_unit"] == "fraction"
    assert frac_over["reported_shares_percent"] == pytest.approx([80.0, 20.0, 10.0])
    assert len(frac_over["share_mismatches"]) == 1 and frac_over["share_mismatches"][0]["index"] == 1

    # Cross-audit counterexample: tiny percentages [0.5, 0.5] on total=1000, parts=[5, 5]
    tiny_pct = recompute.check_partition_conservation(1000, [5, 5], reported_shares=[0.5, 0.5])
    assert tiny_pct["resolved_share_unit"] == "percent"
    assert tiny_pct["share_mismatches"] == []


def test_ablation_delta_regularity_catches_constant_offset_and_preserves_precision():
    bases = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]
    fabricated_matrix = [[round(b - 0.01, 2), b, round(b - 0.02, 2)] for b in bases]
    res = recompute.check_ablation_delta_regularity(fabricated_matrix, baseline_col=1)
    assert res["consistent"] is False
    assert res["suspicious_constant_offset"] is True
    assert len(res["constant_offset_columns"]) == 2
    assert res["constant_offset_columns"][0]["constant_delta"] == pytest.approx(-0.01)
    assert res["constant_offset_columns"][1]["constant_delta"] == pytest.approx(-0.02)
    assert res["column_deltas"]["0"]["sample_variance"] == 0.0

    # Cross-audit counterexample: small deltas [1e-7, 2e-7, 3e-7] must NOT be collapsed by pre-rounding
    micro_matrix = [[0.0, 1e-7], [0.0, 2e-7], [0.0, 3e-7]]
    micro_res = recompute.check_ablation_delta_regularity(micro_matrix, baseline_col=0)
    assert micro_res["consistent"] is True
    assert micro_res["suspicious_constant_offset"] is False
    assert micro_res["column_deltas"]["1"]["sample_variance"] > 0.0


def test_storage_bandwidth_bounds_catches_bare_vector_below_bound_and_impossible_bandwidth():
    res = recompute.check_storage_bandwidth_bounds(
        1024000, 256, bytes_per_element=4,
        reported_size_mb=1000.0, reported_latency_us=2.0, max_bandwidth_gbps=4000.0,
    )
    assert res["consistent"] is False
    assert res["bare_vector_only_match"] is True
    assert res["matched_unit"] == "MiB"
    assert res["bandwidth_exceeds_limit"] is True
    assert res["implied_fullscan_bandwidth_gbps"] > 400000.0

    # Cross-audit counterexample: reported_size_mb=1.0 (far below 1000.0 MiB physical bound) must fail!
    below = recompute.check_storage_bandwidth_bounds(
        1024000, 256, bytes_per_element=4, reported_size_mb=1.0,
    )
    assert below["below_raw_vector_bound"] is True
    assert below["consistent"] is False

    # Cross-audit counterexample: calling without any reported claim must raise ValueError
    with pytest.raises(ValueError, match="reported_size_mb"):
        recompute.check_storage_bandwidth_bounds(1000000, 384)

    # Realistic storage and latency pass
    ok = recompute.check_storage_bandwidth_bounds(
        100000, 384, bytes_per_element=4,
        reported_size_mb=420.0, reported_latency_us=12600.0, max_bandwidth_gbps=4000.0,
    )
    assert ok["consistent"] is True


def test_mcp_recompute_statistics_wires_new_forensic_checks(monkeypatch):
    import sys
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    import mcp_server
    monkeypatch.setattr(mcp_server, "_RECOMPUTE_MOD", recompute)
    out = mcp_server.handle_tool_call("academic_recompute_statistics", {
        "partition_total": 1000,
        "partition_parts": [800, 100, 100],
        "ablation_matrix": [[0.50, 0.51], [0.60, 0.61], [0.70, 0.71]],
        "ablation_baseline_col": 0,
        "bandwidth_item_count": 1024000,
        "bandwidth_vector_dim": 256,
        "bandwidth_reported_size_mb": 1000.0,
        "bandwidth_reported_latency_us": 2.0,
        "bandwidth_max_gbps": 2000.0,
    })
    assert "error" not in out
    assert out["partition_conservation"]["consistent"] is True
    assert out["ablation_delta_regularity"]["consistent"] is False
    assert out["storage_bandwidth_bounds"]["consistent"] is False
    assert out["storage_bandwidth_bounds"]["max_bandwidth_gbps"] == 2000.0


def test_locate_oa_and_sources_institutional_repository_fallback_and_closed_guard(tmp_path, monkeypatch):
    oa_work = {
        "doi": "https://doi.org/10.1000/synthetic-oa-2026",
        "open_access": {"is_oa": True, "oa_status": "gold", "oa_url": "https://publisher.example.org/2026/481/pdf"},
        "best_oa_location": {
            "is_oa": True,
            "pdf_url": "https://publisher.example.org/2026/481/pdf",
            "landing_page_url": "https://doi.org/10.1000/synthetic-oa-2026",
            "source": {"type": "journal", "display_name": "Computers"},
        },
        "locations": [
            {
                "is_oa": True,
                "pdf_url": "https://repo.university.example.edu/bitstreams/synth-01/retrieve",
                "landing_page_url": "https://repo.university.example.edu/handle/1000/synth",
                "version": "publishedVersion",
                "license": "cc-by",
                "source": {"type": "repository", "display_name": "Institutional OA Repository"},
            }
        ],
    }
    locs = locate_oa.pick_openalex_oa_locations(oa_work)
    assert len(locs) >= 2
    assert locs[0]["host_type"] == "repository"
    assert "repo.university.example.edu" in locs[0]["url_for_pdf"]

    # Cross-audit counterexample: closed/embargoed repository entry (is_oa=False) must NOT become is_oa=True
    closed_work = {
        "doi": "https://doi.org/10.1000/closed",
        "open_access": {"is_oa": False},
        "locations": [{
            "is_oa": False,
            "pdf_url": None,
            "landing_page_url": "https://repo.example.org/embargoed",
            "source": {"type": "repository"},
        }],
    }
    assert locate_oa.pick_openalex_oa_locations(closed_work) == []

    oa_json_path = tmp_path / "openalex_work.json"
    oa_json_path.write_text(json.dumps(oa_work), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = locate_oa.main(["--doi", "10.1000/synthetic-oa-2026", "--openalex-record", str(oa_json_path)])
    assert rc == 0
    rep = json.loads(buf.getvalue())
    assert rep["is_oa"] is True
    assert "repo.university.example.edu" in rep["location"]["url_for_pdf"]

    # Cross-audit counterexample: DOI mismatch in --openalex-record must fail with mismatch=True
    buf_mis = io.StringIO()
    with redirect_stdout(buf_mis):
        rc_mis = locate_oa.main(["--doi", "10.1000/other-doi", "--openalex-record", str(oa_json_path)])
    assert rc_mis == 1
    assert json.loads(buf_mis.getvalue())["mismatch"] is True

    from test_paper_research_analysis import sources
    monkeypatch.setattr(sources, "discover_oa_fallback_urls",
                        lambda doi: [("https://repo.university.example.edu/bitstreams/synth-01/retrieve", "oa-repository.pdf", "main")])
    monkeypatch.setattr(sources, "parse", lambda p: ([sources.segment("pdf:page=1", "Full text methods and results. " * 20, page_index=0)], "Paper Title"))

    def fake_fetch(url, path):
        if "doi.org" in url:
            raise HTTPError(url, 403, "Forbidden WAF", {}, None)
        Path(path).write_bytes(b"%PDF-1.4 synthetic institutional bitstream")
        return url, "application/pdf"

    monkeypatch.setattr(sources, "fetch", fake_fetch)
    state = sources.acquire("10.1000/synthetic-oa-2026", tmp_path / "acq_proj")
    assert len(state["files"]) == 1
    assert state["files"][0]["path"] == "raw/oa-repository.pdf"


def test_openreview_audit_classifies_and_handles_adversarial_cases():
    rejected_payload = {
        "notes": [
            {
                "id": "Forum_Synth_01",
                "forum": "Forum_Synth_01",
                "content": {
                    "title": {"value": "Synthetic Baseline Study on Sequence Modeling"},
                    "authors": {"value": ["Author One", "Author Two"]},
                    "venue": {"value": "Submitted to ICLR 2026"},
                    "venueid": {"value": "ICLR.cc/2026/Conference/Submission"},
                },
            },
            {
                "id": "rev1",
                "forum": "Forum_Synth_01",
                "content": {"rating": {"value": "3: reject, not good enough"}, "confidence": {"value": "4: confident"}},
            },
            {
                "id": "rev2",
                "forum": "Forum_Synth_01",
                "content": {"rating": {"value": "5: marginally below threshold"}, "confidence": {"value": "3: fairly confident"}},
            },
        ]
    }
    res_rej = or_audit.parse_openreview_notes(rejected_payload, forum_id="Forum_Synth_01")
    assert res_rej["status_classification"] == "rejected_or_unaccepted"
    assert res_rej["review_count"] == 2
    assert res_rej["mean_rating"] == pytest.approx(4.0)

    # Cross-audit counterexample 1: accepted Oral paper with one dissenting reviewer recommendation + cross-forum noise
    oral_payload = {
        "notes": [
            {
                "id": "OtherForum",
                "forum": "OtherForum",
                "content": {"title": {"value": "Wrong"}, "venue": {"value": "Rejected"}},
            },
            {
                "id": "Oral1",
                "forum": "Oral1",
                "content": {
                    "title": {"value": "Accepted Oral Paper"},
                    "authors": {"value": ["Alice", "Bob"]},
                    "venue": {"value": "ICLR 2026 Oral"},
                },
            },
            {
                "id": "rev_dissent",
                "forum": "Oral1",
                "content": {"recommendation": {"value": "3: reject, not good enough"}},
            },
            {
                "id": "rev_other_forum",
                "forum": "OtherForum",
                "content": {"decision": {"value": "Reject"}, "rating": {"value": "1: very low"}},
            },
            {
                "id": "dec1",
                "forum": "Oral1",
                "content": {"decision": {"value": "Accept (Oral)"}},
            },
        ]
    }
    res_oral = or_audit.parse_openreview_notes(oral_payload, forum_id="Oral1")
    assert res_oral["forum_id"] == "Oral1"
    assert res_oral["status_classification"] == "accepted"
    assert res_oral["ratings"] == [3.0]

    # Cross-audit counterexample 2: "Temporal" (contains "oral" substring) + "below acceptance threshold"
    temporal_payload = {
        "notes": [
            {
                "id": "SubTemp",
                "forum": "SubTemp",
                "content": {
                    "title": {"value": "Temporal Graph Model"},
                    "authors": {"value": ["Anonymous"]},
                    "venue": {"value": "Submitted to Workshop on Temporal Models"},
                },
            },
            {
                "id": "r1",
                "forum": "SubTemp",
                "content": {"recommendation": {"value": "5: marginally below acceptance threshold"}},
            },
        ]
    }
    res_temp = or_audit.parse_openreview_notes(temporal_payload, forum_id="SubTemp")
    assert res_temp["status_classification"] == "under_review"
    assert res_temp["ratings"] == [5.0]


def test_github_repo_forensics_separates_vendored_and_core():
    entries = [
        {"path": "src/my_engine/core.py", "size": 38000},
        {"path": "src/my_engine/packer.py", "size": 19000},
        {"path": "src/memory_toolkits/baseline_a.py", "size": 190000},
        {"path": "vendor_pkg/api/client.py", "size": 76000},
        {"path": "tests/test_core.py", "size": 38000},
        {"path": "benchmarks/test_throughput.py", "size": 3800},
        {"path": "my_pkg.egg-info/top_level.py", "size": 100},
    ]
    rep = gh_forensics.analyze_entries(entries, truncated=True)
    assert rep["truncated"] is True
    assert rep["first_party_core"]["file_count"] == 2
    assert rep["first_party_core"]["bytes"] == 57000
    assert rep["vendored_or_third_party"]["file_count"] == 2
    assert rep["vendored_or_third_party"]["bytes"] == 266000
    assert rep["unit_tests"]["file_count"] == 1
    assert rep["examples_or_experiments"]["file_count"] == 1
    assert rep["unit_tests"]["test_to_core_byte_ratio"] == pytest.approx(38000 / 57000)


def test_receipt_to_latex_table_and_double_blind_sanitizer(tmp_path):
    spec = {
        "caption": "Accuracy O(N^2) vs Latency ~10ms on SynthBench_A",
        "label": "tab:main_results",
        "columns": ["Method", "Recall (%)", "Latency (ms)"],
        "rows": [
            [r"TopK \input{secret}", 88.334, 25.40],
            ["BudgetPack_Ours", 88.331, 12.60],
        ],
        "decimals": 2,
        "bold_max_cols": [1],
        "bold_min_cols": [2],
    }
    tex = ltx_table.render_booktabs_table(spec, source_sha256="abc12345")
    assert r"\toprule" in tex and r"\bottomrule" in tex
    # Label underscore must NOT be escaped so \ref{tab:main_results} works!
    assert r"\label{tab:main_results}" in tex
    # Backslash, ^, and ~ in text/caption must be safely escaped!
    assert r"\textbackslash{}input\{secret\}" in tex
    assert r"\textasciicircum{}" in tex and r"\textasciitilde{}" in tex
    # Both 88.334 and 88.331 round to 88.33 at decimals=2, so both tied maxima are bolded!
    assert tex.count(r"\textbf{88.33}") == 2
    assert r"\textbf{12.60}" in tex

    # Multiline and nested-brace \author + bare github.com + WSL path + filename token
    sub_dir = tmp_path / "AliceResearcher_bundle"
    sub_dir.mkdir()
    bad_tex = sub_dir / "draft.tex"
    win_prefix = "C:\\" + "Users\\" + "alice_researcher\\repo"
    wsl_prefix = "/mnt/c/" + "Users/" + "bob_dev/work"
    bad_tex.write_text(
        "\\title{Anonymous Draft}\n"
        "\\author{\n  \\thanks{Anonymous review} Alice Researcher \\\\\n  Institute\n}\n"
        "See github.com/anonymous/secret_repo and ORCID 0009-0003-6159-7453.\n"
        f"Local path: {win_prefix} and {wsl_prefix}.\n",
        encoding="utf-8",
    )
    scan_bad = blind_san.scan_target(sub_dir, forbidden_tokens=["AliceResearcher"])
    assert scan_bad["status"] == "leaks_detected"
    kinds = {f["kind"] for f in scan_bad["findings"]}
    assert "forbidden_token_in_path" in kinds
    assert "non_anonymous_github_url" in kinds
    assert "orcid_identifier" in kinds
    assert "local_user_path" in kinds
    assert "non_anonymous_latex_author" in kinds

    # Nonexistent target must raise ValueError, and empty dir must be 'incomplete' (not 'clean')
    with pytest.raises(ValueError, match="does not exist"):
        blind_san.scan_target(tmp_path / "missing_dir")
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    assert blind_san.scan_target(empty_dir)["status"] == "incomplete"

    clean_tex = tmp_path / "clean.tex"
    clean_tex.write_text(
        "\\title{Clean Draft}\n"
        "\\author{\n  Anonymous Authors\n}\n"
        "Code at https://anonymous.4open.science/r/repro-bundle.\n",
        encoding="utf-8",
    )
    scan_ok = blind_san.scan_target(clean_tex, forbidden_tokens=["SecretProjectCodename"])
    assert scan_ok["status"] == "clean"
    assert scan_ok["leak_count"] == 0


def test_cli_new_subcommands_end_to_end(tmp_path):
    import importlib
    from test_paper_research_analysis import PACKAGE
    cli_mod = importlib.import_module(PACKAGE + ".cli")

    tf_in = tmp_path / "tf.json"
    tf_in.write_text(json.dumps({
        "partition": {"total": 100, "parts": [80, 20], "reported_shares": [80.0, 20.0]},
        "ablation_matrix": [[0.5, 0.6], [0.7, 0.9], [0.4, 0.42]],
    }), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_mod.main(["table-forensics", "--input", str(tf_in)])
    assert rc == 0
    assert json.loads(buf.getvalue())["consistent"] is True

    spec_in = tmp_path / "table_spec.json"
    spec_in.write_text(json.dumps({
        "columns": ["Model", "Score"],
        "rows": [["A", 0.75], ["B", 0.92]],
        "bold_max_cols": [1],
    }), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_mod.main(["receipt-to-latex", "--input", str(spec_in)])
    assert rc == 0
    assert "\\textbf{0.92}" in json.loads(buf.getvalue())["latex"]

    or_in = tmp_path / "or.json"
    or_in.write_text(json.dumps({
        "notes": [{
            "id": "Forum1",
            "forum": "Forum1",
            "content": {
                "title": {"value": "Test Paper"},
                "authors": {"value": ["A. Author"]},
                "venue": {"value": "ICLR 2026 Oral"},
            },
        }]
    }), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_mod.main(["openreview-audit", "--input-json", str(or_in)])
    assert rc == 0
    assert json.loads(buf.getvalue())["status_classification"] == "accepted"

    # Missing required flags on openreview-audit returns structured JSON error (rc=1)
    buf_err = io.StringIO()
    with redirect_stdout(buf_err):
        rc_err = cli_mod.main(["openreview-audit"])
    assert rc_err == 1
    assert json.loads(buf_err.getvalue())["status"] == "error"

    tree_in = tmp_path / "tree.json"
    tree_in.write_text(json.dumps({
        "tree": [
            {"path": "src/pkg/main.py", "type": "blob", "size": 7600},
            {"path": "tests/test_main.py", "type": "blob", "size": 3800},
        ]
    }), encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_mod.main(["repo-forensics", "--tree-json", str(tree_in)])
    assert rc == 0
    assert json.loads(buf.getvalue())["first_party_core"]["file_count"] == 1

    clean_md = tmp_path / "manuscript.md"
    clean_md.write_text("# Anonymous Manuscript\nAll experiments are reproducible.\n", encoding="utf-8")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli_mod.main(["sanitize-blind", "--target", str(clean_md), "--forbidden-token", "SecretName"])
    assert rc == 0
    assert json.loads(buf.getvalue())["status"] == "clean"

pre_linter = _load_script("skills/academic-writing/scripts/pre_submission_linter.py", "pre_submission_linter_combat")
venue_mgr = _load_script("skills/academic-writing/scripts/venue_template_manager.py", "venue_template_manager_combat")


def test_venue_specs_and_non_scoring_peer_review_contract():
    specs = pre_linter.load_venue_specs()
    assert specs["schema_version"] == "1.0.0"
    venues = specs["venues"]
    assert {"iclr", "neurips", "icml", "acl", "kdd", "ieee_tmm", "acm_tois", "arxiv_preprint"} <= set(venues.keys())
    assert len(specs["review_dimensions"]) == 6
    assert len(specs["methodological_lenses"]) == 4
    for lens in specs["methodological_lenses"]:
        assert lens["forbid_numeric_score"] is True
        assert len(lens["source_citations"]) >= 1
        assert len(lens["audit_questions"]) >= 3

    tpl_path = ROOT / "skills" / "literature-analysis" / "references" / "peer-review-template.md"
    tpl_text = tpl_path.read_text(encoding="utf-8")
    assert "评分:3/5" not in tpl_text
    assert "1~5 分" not in tpl_text
    assert "默认不提供主观分数或录用概率" in tpl_text


def test_pre_submission_linter_detects_blockers_and_warnings(tmp_path):
    tex = tmp_path / "main.tex"
    tex.write_text(
        "\\documentclass{article}\n"
        "\\usepackage{acl}\n"
        "\\aclfinalcopy\n"
        "\\begin{document}\n"
        "\\begin{abstract}\n"
        "Our method improves accuracy by 14.2\\% over baseline (see Section ?? and \\cite{?}).\n"
        "\\end{abstract}\n"
        "\\section{Introduction}\n"
        "TODO: refine introduction.\n"
        "\\begin{table}[t]\n"
        "\\begin{tabular}{lc}\n"
        "Model & Acc \\\\\n"
        "Ours & 91.4 \\\\\n"
        "\\end{tabular}\n"
        "\\end{table}\n"
        "\\section{Conclusion}\n"
        "Our approach reduces latency by 3.5x across benchmarks.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep = pre_linter.lint_manuscript(
        tex_path=tex,
        venue="acl",
        contribution_type="general_empirical",
        require_ceg_binding=True,
    )
    assert rep["passed"] is False
    codes = {h["code"] for h in rep["hits"]}
    assert "FORBIDDEN_REVIEW_PATTERN" in codes
    assert "MISSING_REQUIRED_SECTION" in codes
    assert "UNRESOLVED_LATEX_REFERENCE" in codes
    assert "LEFT_OVER_TODO_MARKER" in codes
    assert "TABLE_MISSING_DISPERSION" in codes
    assert "UNGROUNDED_QUANTITATIVE_CLAIM" in codes


def test_pre_submission_linter_passes_clean_scaffolded_manuscript(tmp_path):
    mdir = venue_mgr.scaffold_manuscript(
        workspace_dir=tmp_path,
        project_slug="clean-iclr-paper",
        venue="iclr",
        year=2027,
        contribution_type="systems_architecture",
    )
    assert (mdir / "main.tex").is_file()
    assert (mdir / "venue-manifest.json").is_file()

    # Verify style directory hashing and legacy macro warning detection
    (mdir / "styles" / "iclr2027_conference.sty").write_text("% official 2027 style\n", encoding="utf-8")
    manifest = venue_mgr.verify_style_directory(mdir)
    assert len(manifest["style_files"]) == 1
    assert manifest["style_warnings"] == []

    rep = pre_linter.lint_manuscript(
        tex_path=mdir / "main.tex",
        venue="iclr",
        contribution_type="systems_architecture",
        require_ceg_binding=True,
    )
    assert rep["passed"] is True
    assert rep["summary_counts"]["blockers"] == 0

    # Verify top-level CLI subcommands pre-submission-lint and venue-template
    import importlib
    from test_paper_research_analysis import PACKAGE
    ark_cli = importlib.import_module(PACKAGE + '.cli')

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc_vt = ark_cli.main(["venue-template", "--action", "list-venues"])
    assert rc_vt == 0
    vt_data = json.loads(buf.getvalue())
    assert "iclr" in vt_data["venues"]

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc_ps = ark_cli.main([
            "pre-submission-lint",
            "--tex", str(mdir / "main.tex"),
            "--venue", "iclr",
            "--contribution-type", "systems_architecture",
            "--require-ceg-binding",
        ])
    assert rc_ps == 0
    ps_data = json.loads(buf.getvalue())
    assert ps_data["passed"] is True


# ── 8. Cross-Review Counterexample Regressions ───────────────────────────────

def test_pre_submission_linter_multi_option_and_prose_section_rejection(tmp_path: Path):
    r"""Multi-option \usepackage[final,nonatbib] and prose 'limitations' must not bypass blockers."""
    p = tmp_path / "neurips_bypass.tex"
    p.write_text(
        "\\documentclass{article}\n"
        "\\usepackage[final,nonatbib]{neurips_2026}\n"
        "\\begin{document}\n"
        "\\section{Introduction}\n"
        "We discuss limitations and the NeurIPS Paper Checklist in prose only.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep = pre_linter.lint_manuscript(p, venue="neurips")
    assert rep["passed"] is False
    codes = [h["code"] for h in rep["hits"]]
    assert "FORBIDDEN_REVIEW_PATTERN" in codes
    assert codes.count("MISSING_REQUIRED_SECTION") == 2


def test_pre_submission_linter_contradicted_ceg_and_unresolved_inline_tag(tmp_path: Path):
    """Contradicted CEG support_status or unresolved % ark:claim tag must flag UNGROUNDED_QUANTITATIVE_CLAIM."""
    claim_txt = "Our method improves accuracy by 20\\% across all datasets."
    tex = tmp_path / "claim.tex"
    tex.write_text(
        "\\begin{abstract}\n"
        "% ark:claim=NON_EXISTENT\n"
        f"{claim_txt}\n"
        "\\end{abstract}\n",
        encoding="utf-8",
    )
    ceg = tmp_path / "contradicted.json"
    ceg.write_text(
        json.dumps({
            "claims": [{"id": "C1", "text": claim_txt}],
            "support_edges": [{"claim_id": "C1", "evidence_id": "E1", "support_status": "contradicted"}],
        }),
        encoding="utf-8",
    )
    assert pre_linter._load_ceg_verified_claims(ceg) == set()
    rep = pre_linter.lint_manuscript(tex, venue="arxiv_preprint", ceg_path=ceg, require_ceg_binding=True)
    assert "UNGROUNDED_QUANTITATIVE_CLAIM" in [h["code"] for h in rep["hits"]]


def test_double_blind_sanitizer_macro_author_and_unbraced_pdfauthor(tmp_path: Path):
    r"""Custom macros inside \author{\realname} and unbraced pdfauthor=... must be flagged."""
    p1 = tmp_path / "macro.tex"
    p1.write_text("\\newcommand{\\realname}{Alice Researcher}\n\\author{\\realname}\n", encoding="utf-8")
    r1 = blind_san.scan_target(p1)
    assert r1["status"] == "leaks_detected"

    p2 = tmp_path / "pdfauthor.tex"
    p2.write_text("\\hypersetup{pdfauthor=Alice Researcher,pdftitle=Study}\n", encoding="utf-8")
    r2 = blind_san.scan_target(p2)
    assert r2["status"] == "leaks_detected"


def test_openreview_audit_nan_filtering_and_reviewer_decision_isolation():
    """NaN ratings are filtered, and reviewer notes with a decision field cannot override venue acceptance."""
    summary = or_audit.summarize_venue_mirror([
        {"id": "F1", "status": "Poster", "rating": "NaN;8"},
        {"id": "F1", "status": "Poster", "rating": "8"},
        None,
    ])
    assert summary["total_submissions"] == 1
    assert summary["duplicate_records_skipped"] == 1
    assert summary["invalid_records_skipped"] == 1
    assert summary["overall_mean_rating"] == 8.0

    notes_payload = {
        "notes": [
            {"id": "F1", "forum": "F1", "content": {"venue": {"value": "ICLR 2026 Oral"}}},
            {
                "id": "R1",
                "forum": "F1",
                "invitations": ["ICLR.cc/2026/Conference/Submission1/-/Official_Review"],
                "content": {"decision": {"value": "Reject"}},
            },
        ]
    }
    parsed = or_audit.parse_openreview_notes(notes_payload)
    assert parsed["status_classification"] == "accepted"
    assert parsed["decisions"] == []
    assert parsed["reviewer_recommendations"] == ["Reject"]


def test_locate_oa_rejects_explicitly_closed_best_location():
    """When best_oa_location has is_oa=False, it must not be returned even if open_access.is_oa is True."""
    locs = locate_oa.pick_openalex_oa_locations({
        "open_access": {"is_oa": True},
        "best_oa_location": {"is_oa": False, "pdf_url": "https://example.org/closed.pdf"},
    })
    assert locs == []


# ── 9. Pre-Submission Linter Counterexample Regressions ──────────────────────

def test_slice1_pdf_exempt_statements_and_numbered_llm_section_counterexamples():
    """Verify exempt statement blocks before References do not inflate main_body_pages, while numbered method sections still count."""
    page_exempt_only = (
        "Published as a conference paper at ICLR 2026\n"
        "REPRODUCIBILITYSTATEMENT\n"
        "Code and weights are provided in the supplementary material.\n"
        "THE USE OF LARGE LANGUAGE MODELS\n"
        "LLMs were used only for minor grammar polishing.\n"
        "ACKNOWLEDGMENTS\n"
        "We thank the anonymous reviewers.\n"
        "REFERENCES\n"
        "[1] AuthorOne et al., 2026.\n"
    )
    m_ref = pre_linter.REFERENCES_HEADING_RE.search(page_exempt_only)
    assert m_ref is not None
    assert pre_linter._has_main_body_before_heading(page_exempt_only, m_ref) is False

    # Counterexample 1b: Ethics Statement followed by numbered Conclusion on the same page before References
    page_exempt_then_main = (
        "ETHICS STATEMENT\n"
        "No human subjects were involved.\n"
        "6 CONCLUSION\n"
        "We presented a deterministic verification framework.\n"
        "REFERENCES\n"
    )
    m_ref2 = pre_linter.REFERENCES_HEADING_RE.search(page_exempt_then_main)
    assert m_ref2 is not None
    assert pre_linter._has_main_body_before_heading(page_exempt_then_main, m_ref2) is True

    # Counterexample 1c: Ethics Statement followed by numbered technical section '3 The Use of Large Language Models' exits exempt zone
    page_exempt_then_numbered_llm = (
        "ETHICS STATEMENT\n"
        "No human subjects were involved.\n"
        "3 The Use of Large Language Models\n"
        "Our architecture queries a frozen teacher model.\n"
        "REFERENCES\n"
    )
    m_ref3 = pre_linter.REFERENCES_HEADING_RE.search(page_exempt_then_numbered_llm)
    assert m_ref3 is not None
    assert pre_linter._has_main_body_before_heading(page_exempt_then_numbered_llm, m_ref3) is True

    # Regression: wrapped sentence ending with 'Appendix K.\nCommonsense...' must not match APPENDIX_HEADING_RE, while standalone 'Appendix A' matches
    wrapped_prose_page = (
        "The complete keyword list used for filtering is provided in\n"
        "Appendix K.\n"
        "Commonsense Reasoning This category evaluates the model.\n"
    )
    assert pre_linter.APPENDIX_HEADING_RE.search(wrapped_prose_page) is None
    assert pre_linter.APPENDIX_HEADING_RE.search("Appendix A\nProofs and derivations.\n") is not None


def test_slice2_todo_macro_masking_and_even_backslash_comments(tmp_path: Path):
    r"""Macro definitions \newcommand{\TODO}{...} are masked, while inline TODO after macro or \todo{...} calls are caught."""
    tex = tmp_path / "todo_edge.tex"
    tex.write_text(
        "\\documentclass{article}\n"
        "\\newcommand{\\TODO}[1]{\\textcolor{red}{TODO: #1}}\n"
        "\\newcommand{\\multi}[1]{\n"
        "  {\\bf FIXME: #1}\n"
        "}\n"
        "\\def\\myfix#1{TBD: #1}\n"
        "\\begin{document}\n"
        "\\section{Introduction}\n"
        "100\\% accuracy % TODO: this is a comment after escaped percent\n"
        "Line break\\\\% TODO: comment directly after double backslash\n"
        "\\usepackage{todonotes}\n"
        "\\todolist\n"
        "\\newcommand{\\foo}{bar} TODO: real inline marker on same line\n"
        "We still need to add baselines \\verb|%| \\todo{run seed 42}.\n"
        "\\section{Limitations}\n"
        "None.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep = pre_linter.lint_manuscript(tex, venue="arxiv_preprint")
    todo_hits = [h for h in rep["hits"] if h["code"] == "LEFT_OVER_TODO_MARKER"]
    locators = [h["locator"] for h in todo_hits]
    assert locators == ["todo_edge.tex:L13", "todo_edge.tex:L14"]


def test_slice3_linear_quant_claim_scanner_no_backtracking_and_decimal_safety(tmp_path: Path):
    """Verify strict O(L) quantitative claim scanner handles dense multi-token sentences and Unicode multiplication sign."""
    import time

    long_filler = " ".join(["ExampleAuthor et al. (cf. Fig. 1) evaluated 3.14159 configurations across 20percentage points and 3xylophone tokens"] * 80)
    dense_tokens = " and ".join([f"{k}\\%" for k in range(1, 120)])
    tex = tmp_path / "fast_quant.tex"
    tex.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\begin{abstract}\n"
        f"{long_filler}.\n"
        f"14.2\\% improvement ({dense_tokens}) is achieved by our method over ExampleAuthor et al. on all tasks.\n"
        "Our solver achieves a 2.5× speedup over the baseline on all benchmarks.\n"
        "\\end{abstract}\n"
        "\\section{Introduction}\n"
        "Text.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    t0 = time.perf_counter()
    rep = pre_linter.lint_manuscript(tex, venue="arxiv_preprint", require_ceg_binding=True)
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.25
    q_hits = [h for h in rep["hits"] if h["code"] == "UNGROUNDED_QUANTITATIVE_CLAIM"]
    assert len(q_hits) == 2
    assert "14.2\\% improvement" in q_hits[0]["excerpt"]
    assert "2.5× speedup" in q_hits[1]["excerpt"]


def test_slice4_undefined_label_ref_and_author_year_cite_checks(tmp_path: Path):
    r"""Verify cross-file \ref resolution, unused \label tolerance, Author et al. \cite duplication, and bare \cite dominance."""
    main_tex = tmp_path / "main.tex"
    sub_tex = tmp_path / "sec_exp.tex"
    sub_tex.write_text(
        "\\section{Experiments}\\label{sec:unused_label}\n"
        "\\newcommand{\\deadmacro}{\\label{fig:missing_target}}\n"
        "\\begin{figure}\\caption{A}\\label{fig:valid}\\end{figure}\n"
        "\\begin{lstlisting}\n[language=YAML,caption={Example [x] label=fig:missing_target},label={example_yaml}]\nlabel=fig:missing_target\n\\end{lstlisting}\n"
        "The configuration key is \\texttt{label=fig:missing_target}.\n"
        "As shown in Figure~\\ref{fig:valid}, Listing~\\ref{example_yaml}, and Figure~\\ref{fig:missing_target}, "
        "Author et al.~\\cite{author2026} and \\cite{c1,c2} and \\cite{c3} and \\cite{c4} and \\cite{c5} and \\cite{c6}.\n",
        encoding="utf-8",
    )
    main_tex.write_text(
        "\\documentclass{article}\n"
        "\\usepackage{iclr2026_conference}\n"
        "\\begin{document}\n"
        "\\section{Introduction}\n"
        "\\input{sec_exp}\n"
        "\\section{Limitations}\n"
        "Limitation text.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep = pre_linter.lint_manuscript(main_tex, venue="iclr")
    codes = [h["code"] for h in rep["hits"]]
    assert "UNDEFINED_LATEX_LABEL_REF" in codes
    assert "AUTHOR_YEAR_CITE_DUPLICATION" in codes
    assert "NATBIB_BARE_CITE_DOMINANT" in codes
    undef_hits = [h for h in rep["hits"] if h["code"] == "UNDEFINED_LATEX_LABEL_REF"]
    assert len(undef_hits) == 1
    assert "fig:missing_target" in undef_hits[0]["message"]

    # When [numbers] option is passed on a conference/citation package, author-year cite warnings are suppressed
    main_num = tmp_path / "main_num.tex"
    main_num.write_text(
        main_tex.read_text(encoding="utf-8").replace("\\usepackage{iclr2026_conference}", "\\usepackage[numbers]{iclr2026_conference}"),
        encoding="utf-8",
    )
    rep_num = pre_linter.lint_manuscript(main_num, venue="iclr")
    num_codes = {h["code"] for h in rep_num["hits"]}
    assert "AUTHOR_YEAR_CITE_DUPLICATION" not in num_codes
    assert "NATBIB_BARE_CITE_DOMINANT" not in num_codes


def test_slice5_double_blind_acknowledgments_check_respects_phase_and_placeholder(tmp_path: Path):
    """Verify synthetic grant number in Acknowledgments is blocker in double-blind submission, but allowed in camera-ready or when anonymized."""
    tex_leak = tmp_path / "leak_acks.tex"
    tex_leak.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Introduction}\nText.\n"
        "\\section{Limitations}\nLimits.\n"
        "\\section*{Acknowledgments}\n"
        "Synthetic test fixture: supported by Grant No. TEST-GRANT-0000.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep_sub = pre_linter.lint_manuscript(tex_leak, venue="iclr", phase="submission")
    ack_hits = [h for h in rep_sub["hits"] if h["code"] == "FORBIDDEN_ACKS_IN_DOUBLE_BLIND_SUBMISSION"]
    assert len(ack_hits) == 1
    assert ack_hits[0]["severity"] == "blocker"

    rep_cam = pre_linter.lint_manuscript(tex_leak, venue="iclr", phase="camera_ready")
    assert not any(h["code"] == "FORBIDDEN_ACKS_IN_DOUBLE_BLIND_SUBMISSION" for h in rep_cam["hits"])

    tex_anon = tmp_path / "anon_acks.tex"
    tex_anon.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Introduction}\nText.\n"
        "\\section{Limitations}\nLimits.\n"
        "\\section*{Acknowledgments}\n"
        "Funding details are omitted for anonymous review.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep_anon = pre_linter.lint_manuscript(tex_anon, venue="iclr", phase="submission")
    assert not any(h["code"] == "FORBIDDEN_ACKS_IN_DOUBLE_BLIND_SUBMISSION" for h in rep_anon["hits"])

    # Mixed acknowledgment with real thank-you or semicolon clause + omitted funding must still be flagged
    tex_mixed = tmp_path / "mixed_acks.tex"
    tex_mixed.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\section{Introduction}\nText.\n"
        "\\section{Limitations}\nLimits.\n"
        "\\section*{Acknowledgments}\n"
        "Funding details are omitted for anonymous review; ExampleAuthor provided compute.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep_mixed = pre_linter.lint_manuscript(tex_mixed, venue="iclr", phase="submission")
    assert any(h["code"] == "FORBIDDEN_ACKS_IN_DOUBLE_BLIND_SUBMISSION" for h in rep_mixed["hits"])


# ── 10. 20-Item Independent Audit Regression Suite (COR/LIN/SEC/REL) ─────────

def test_audit_cor01_to_cor07_scientific_correctness_and_recompute(tmp_path: Path):
    """Verify COR-01..COR-07 scientific contract and statistical recomputation fixes."""
    import hashlib
    import numpy as np
    from test_paper_research_analysis import analysis, sources

    evidence_mod = _load_script("scripts/shared_contracts/evidence.py", "evidence_cor01")
    pr_mod = _load_script("skills/research-object-identity/scripts/provenance.py", "provenance_cor01")
    meta_mod = _load_script("skills/systematic-review-meta-analysis/scripts/meta_core.py", "meta_cor06")

    # COR-01: Entity with sha256 and no locator still verifies supplied_content and enters total_hashed
    expected_sha = hashlib.sha256(b"expected").hexdigest()
    graph = pr_mod.LineageGraph()
    graph.add_entity("ent-1", "data_snapshot", sha256=expected_sha, locator=None)
    graph.add_entity("out-1", "statistic_artifact", sha256=hashlib.sha256(b"out").hexdigest(), locator="urn:out:1")
    graph.record_derivation("out-1", "ent-1")

    ctx_mismatch = evidence_mod.LineageVerificationContext(content_by_entity_id={"ent-1": b"CHANGED", "out-1": b"out"})
    rep_mismatch = pr_mod.trace_origin(graph, "out-1", verification_context=ctx_mismatch)
    assert rep_mismatch.verification_status == "hash_mismatch"
    assert rep_mismatch.content_verification == "hash_mismatch"

    ctx_unlocated = evidence_mod.LineageVerificationContext(content_by_entity_id={"out-1": b"out"})
    rep_unlocated = pr_mod.trace_origin(graph, "out-1", verification_context=ctx_unlocated)
    assert rep_unlocated.verification_status == "partial"
    assert rep_unlocated.content_verification == "partially_verified"

    # COR-02: Unit token binding between literal/unit and source quote via validate_candidate
    import test_paper_research_analysis as tpra
    c02_dir = tmp_path / "cor02_proj"
    c02_dir.mkdir(parents=True, exist_ok=True)
    proj, docs, cand, _ = tpra.case.__wrapped__(c02_dir)
    for f in cand["fields"]:
        if f["id"] == "percent":
            f["literal"] = "25.0 ms"
            f["unit"] = "ms"
    with pytest.raises(ValueError, match="absent from quoted source|conflicts with percentage"):
        analysis.validate_candidate(proj, cand, documents=docs)

    # COR-03: Non-DOI work identity (arXiv ID and version) verification against manifest
    kern = analysis._kernel()
    manifest_ident = analysis._normalize_paper_identity("arXiv:2601.00001v1", "v1", kern)
    cand_diff_id = analysis._normalize_paper_identity("arXiv:2601.00002v1", "v1", kern)
    assert manifest_ident != cand_diff_id
    with pytest.raises(ValueError, match="Conflicting arXiv version"):
        analysis._normalize_paper_identity("arXiv:2601.00001v1", "v2", kern)

    # COR-04: Direct comparison rejects unknown unit or unknown context keys
    full_ctx = {"dataset": "D", "group": "G", "timepoint": "T", "analysis_set": "A", "condition": "C"}
    assert analysis._is_known_complete_for_direct({"unit": "unknown", "context": full_ctx}) is False
    assert analysis._is_known_complete_for_direct({"unit": "%", "context": {**full_ctx, "condition": "unknown"}}) is False
    assert analysis._is_known_complete_for_direct({"unit": "%", "context": full_ctx}) is True

    # COR-05: Asymmetric Clopper-Pearson / exact binomial CI skips symmetric midpoint check
    ci_exact = recompute.check_ci_consistency(0.1, 0.0025, 0.445, ci_method="clopper_pearson")
    assert ci_exact["consistent"] is None
    assert ci_exact["status"] == "symmetry_check_not_applicable"
    assert ci_exact["applicable"] is False

    ci_wald_bad = recompute.check_ci_consistency(0.1, 0.0025, 0.445, ci_method="wald")
    assert ci_wald_bad["consistent"] is False
    assert ci_wald_bad["implied_se"] is not None

    # COR-06: Trim-and-fill computes L0 on full sample relative to updated center (BCG 13-study reference)
    bcg_y = np.array([-.88931133, -1.58538866, -1.34807315, -1.44155119, -.21754732, -.78611559,
                      -1.62089822, .01195233, -.46941765, -1.37134480, -.33935883, .44591340, -.01731395])
    bcg_v = np.array([.325584765, .194581121, .415367965, .020010032, .051210172, .006905618,
                      .223017248, .003961579, .056434210, .073024794, .012412214, .532505845, .071404660])
    tf_res = meta_mod.trim_and_fill(bcg_y, bcg_v, side="right")
    assert tf_res["converged"] is True
    assert tf_res["k0"] == 4
    assert tf_res["adjusted"] == pytest.approx(-0.2910, abs=1e-4)

    # COR-07: Storage bounds separate MB/MiB unit and half-ULP literal rounding from below_raw_vector_bound
    sb_round = recompute.check_storage_bandwidth_bounds(
        item_count=1000, vector_dim=384, bytes_per_element=4,
        reported_size_mb=1.5, reported_literal="1.5", storage_unit="MB",
    )
    assert sb_round["below_raw_vector_bound"] is False
    assert sb_round["consistent"] is True
    assert sb_round["status"] == "ok"


def test_audit_lin01_to_lin03_ceg_binding_macro_perf_and_comment_masking(tmp_path: Path):
    """Verify LIN-01 per-claim CEG binding, LIN-02 linear \\def scan, and LIN-03 comment/verbatim masking."""
    import time

    ceg_path = tmp_path / "ceg.json"
    ceg_path.write_text(json.dumps({
        "claims": [
            {"id": "C_VALID", "text": "Our method improves accuracy by 12.4\\% on DatasetA."},
            {"id": "C_UNSUP", "text": "Latency is reduced by 30\\% on GPU."},
        ],
        "support_edges": [
            {"claim_id": "C_VALID", "evidence_id": "E1", "support_status": "supported"},
        ],
    }), encoding="utf-8")

    # LIN-01: Unanchored second quantitative claim in same file or mismatched text for C_VALID must be flagged
    tex_lin01 = tmp_path / "lin01.tex"
    tex_lin01.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\begin{abstract}\n"
        "% ark:claim=C_VALID\n"
        "Our method improves accuracy by 99.9\\% on DatasetB.\n"
        "Unanchored claim: throughput increases by 4.2x over baseline.\n"
        "\\end{abstract}\n"
        "\\section{Introduction}\nText.\n"
        "\\section{Limitations}\nLimits.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep_lin01 = pre_linter.lint_manuscript(tex_lin01, venue="iclr", ceg_path=ceg_path, require_ceg_binding=True)
    codes_lin01 = [h["code"] for h in rep_lin01["hits"]]
    assert codes_lin01.count("UNGROUNDED_QUANTITATIVE_CLAIM") == 2
    assert any("no verified ClaimEvidenceGraph support edge" in h["message"] for h in rep_lin01["hits"])

    # LIN-02: 12K nested \def macro file completes in < 0.1s
    macro_body = "\\def\\a{" + ("x" * 60) + "}\n"
    tex_lin02 = tmp_path / "lin02.tex"
    tex_lin02.write_text(
        "\\documentclass{article}\n" + (macro_body * 200) +
        "\\begin{document}\n\\section{Introduction}\nText.\n\\section{Limitations}\nLimits.\n\\end{document}\n",
        encoding="utf-8",
    )
    t0 = time.perf_counter()
    pre_linter.lint_manuscript(tex_lin02, venue="iclr")
    assert (time.perf_counter() - t0) < 0.25

    # LIN-03: Commented-out \section{Limitations} does not satisfy required section; verbatim ?? does not trigger unresolved ref
    tex_lin03 = tmp_path / "lin03.tex"
    tex_lin03.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\section{Introduction}\n"
        "% \\section{Limitations}\n"
        "\\begin{verbatim}\nSection ?? and \\ref{missing} and TODO: inside verbatim\n\\end{verbatim}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep_lin03 = pre_linter.lint_manuscript(tex_lin03, venue="neurips")
    codes_lin03 = [h["code"] for h in rep_lin03["hits"]]
    assert "MISSING_REQUIRED_SECTION" in codes_lin03
    assert "UNRESOLVED_LATEX_REFERENCE" not in codes_lin03
    assert "LEFT_OVER_TODO_MARKER" not in codes_lin03


def test_audit_sec02_to_sec07_security_boundaries_and_rel_contracts(tmp_path: Path, monkeypatch):
    """Verify SEC-02..SEC-07 security boundary fixes and REL-01..REL-03/REL-G1 release & incidence contracts."""
    import subprocess
    import sys

    # SEC-02: Non-Author PDF metadata forbidden token & incomplete status when files are unsupported
    unsupported_bin = tmp_path / "archive.bin"
    unsupported_bin.write_bytes(b"\x00\x01\x02")
    scan_dir = blind_san.scan_target(tmp_path)
    assert scan_dir["status"] == "incomplete"
    assert "archive.bin" in scan_dir["unsupported_files"]

    # SEC-03: Ambient TMPDIR mirror is ignored by openreview_audit when not explicitly configured
    fake_tmp = tmp_path / "ambient_tmp"
    fake_tmp.mkdir()
    (fake_tmp / "iclr2026.json").write_text(json.dumps([{"id": "FakeForum", "status": "Oral", "rating": "10"}]), encoding="utf-8")
    monkeypatch.setenv("TMPDIR", str(fake_tmp))
    monkeypatch.delenv("OPENREVIEW_MIRROR_DIR", raising=False)
    assert or_audit._find_local_mirror_fallback("FakeForum") is None

    # SEC-05: Venue template manager marks bundled scaffold as unverified and detects legacy style pattern
    mdir = venue_mgr.scaffold_manuscript(tmp_path, "sec05-paper", venue="iclr", year=2027)
    sty_file = mdir / "styles" / "iclr2027_conference.sty"
    sty_file.write_text("% initial style\n", encoding="utf-8")
    m1 = venue_mgr.verify_style_directory(mdir)
    assert m1["official_style_verified"] is False
    assert m1["official_style_installed"] is False
    assert m1["style_verification_status"] == "unverified_local_style"
    assert m1["style_files"][0]["verified_origin"] is False

    # SEC-07: Bounded MCP stdio frame reader rejects oversized lines & invalid UTF-8 on both text and binary .buffer streams
    mcp_mod = _load_script("scripts/mcp_server.py", "mcp_sec07")
    monkeypatch.setattr(mcp_mod, "MAX_MCP_FRAME_BYTES", 64)
    oversized_stream = io.StringIO("x" * 128 + "\n" + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n")
    frames = list(mcp_mod._iter_bounded_stdio_frames(oversized_stream))
    assert frames[0] == (None, "oversized")
    assert frames[1][1] is None and "ping" in frames[1][0]

    raw_bytes_stream = io.BytesIO(
        b"y" * 128 + b"\n"
        + b"\xff\xfe\xfd\n"
        + (json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n").encode("utf-8")
    )
    bin_wrapped = io.TextIOWrapper(raw_bytes_stream, encoding="utf-8", errors="replace")
    bin_frames = list(mcp_mod._iter_bounded_stdio_frames(bin_wrapped))
    assert bin_frames[0] == (None, "oversized")
    assert bin_frames[1] == (None, "invalid_utf8")
    assert bin_frames[2][1] is None and "ping" in bin_frames[2][0]

    # B1/B5/B6/B7: Empty sha256 rejected, unknown ci_method rejected, non-exact-bare metadata overhead rejected, commented \end{abstract} handled
    ev_mod = _load_script("scripts/shared_contracts/evidence.py", "ev_mod_b1")
    st_empty, r_empty, _ = ev_mod._replay_lineage_content_verification(
        [{"id": "e1", "sha256": ""}],
        check_on_disk_hashes=True,
        content_by_entity_id={"e1": b"abc"},
    )
    assert st_empty == "hash_mismatch" and r_empty == "hash_mismatch"
    with pytest.raises(ValueError, match="ci_method"):
        recompute.check_ci_consistency(0.5, 0.2, 0.8, ci_method="unknown_method_xyz")
    res_meta_non_exact = recompute.check_storage_bandwidth_bounds(
        item_count=1_000_000,
        vector_dim=384,
        bytes_per_element=4,
        reported_size_mb=1536.01,
        reported_literal="1536.01",
        storage_unit="MB",
        claims_full_system_storage=True,
        min_metadata_overhead_bytes=64 * 1_000_000,
    )
    assert res_meta_non_exact["consistent"] is False
    assert res_meta_non_exact["status"] == "omitted_metadata_overhead"

    # B2/B3/B5/B7/B8 additional Round-2 & Round-3 edge cases:
    from test_paper_research_analysis import analysis as analysis_r2
    import test_paper_research_analysis as tpra_r2
    assert analysis_r2._units_attached_to_number("Accuracy is 25.0 percent.", "25.0") == {"%"}
    assert analysis_r2._units_attached_to_number("Speedup is 25.0×.", "25.0") == {"x"}
    assert analysis_r2._units_attached_to_number("Gain is 25.0 percentage points.", "25.0") == {"pp"}
    c_pp_dir = tmp_path / "cor02_pp_proj"
    c_pp_dir.mkdir(parents=True, exist_ok=True)
    proj_pp, docs_pp, cand_pp, _ = tpra_r2.case.__wrapped__(c_pp_dir)
    for f in cand_pp["fields"]:
        if f["id"] == "percent":
            loc_p = f["sources"][0]["locator"]
            for seg in docs_pp["documents"][0]["segments"]:
                if seg["locator"] == loc_p:
                    seg["text"] = seg["text"] + " Accuracy improved by 25.0 percentage points. Speedup is 25.0×."
            f["sources"][0]["quote"] = "Accuracy improved by 25.0 percentage points."
            f["literal"] = "25.0"
            f["unit"] = "%"
    with pytest.raises(ValueError, match="conflicts with unit|requires '%'"):
        analysis_r2.validate_candidate(proj_pp, cand_pp, documents=docs_pp)
    for f in cand_pp["fields"]:
        if f["id"] == "percent":
            f["sources"][0]["quote"] = "Speedup is 25.0×."
            f["literal"] = "25.0"
            f["unit"] = "ms"
    with pytest.raises(ValueError, match="conflicts with unit"):
        analysis_r2.validate_candidate(proj_pp, cand_pp, documents=docs_pp)

    assert analysis_r2._normalize_paper_identity("CorpusId:12345678", "v1", analysis_r2._kernel()) == ("s2", "12345678", "v1")
    res_t_ci = recompute.check_ci_consistency(0.5, 0.2, 0.8, ci_method="t")
    assert res_t_ci["consistent"] is True and res_t_ci["implied_se"] is None
    meta_mod_r3 = _load_script("skills/systematic-review-meta-analysis/scripts/meta_core.py", "meta_cor06_r3")
    tf_nonconv = meta_mod_r3.trim_and_fill([-0.01, -0.02, 0.5, 1.0, 2.0, 5.0], [1.0, 1.0, 100.0, 100.0, 100.0, 100.0], side="left", maxiter=1)
    assert tf_nonconv["converged"] is False and tf_nonconv["k0"] is None and tf_nonconv["adjusted"] is None and tf_nonconv["se"] is None

    uv_lock_txt = (ROOT / "uv.lock").read_text(encoding="utf-8")
    assert '{ name = "sympy", marker = "extra == \'full\'", specifier = ">=1.13,<2" }' in uv_lock_txt
    assert '{ name = "sympy", marker = "extra == \'qa\'", specifier = ">=1.13,<2" }' in uv_lock_txt
    assert not any('"sympy"' in ln and '">=1.3,<2"' in ln for ln in uv_lock_txt.splitlines())

    ceg_edgeless = tmp_path / "edgeless_ceg.json"
    ceg_edgeless.write_text(json.dumps({"claims": [{"id": "C1", "text": "Accuracy improves by 10\\%.", "status": "supported"}], "support_edges": []}), encoding="utf-8")
    id_map_edgeless, _ = pre_linter._load_ceg_claim_map(ceg_edgeless)
    assert "C1" not in id_map_edgeless

    commented_verb_tex = tmp_path / "commented_verb.tex"
    commented_verb_tex.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\section{Introduction}\nText.\n"
        "% \\begin{verbatim}\n% \\section{Limitations}\n% \\end{verbatim}\n\\end{document}\n",
        encoding="utf-8",
    )
    rep_cverb = pre_linter.lint_manuscript(commented_verb_tex, venue="acl")
    assert any(h["code"] == "MISSING_REQUIRED_SECTION" for h in rep_cverb["hits"])

    xmp_entries = blind_san._extract_xmp_entries(
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMPTK_SECRET_TOKEN" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="https://github.com/secret_user/repo"><child/>TAIL_SENTINEL</rdf:Description></x:xmpmeta>'
    )
    xmp_vals = [v for _, v in xmp_entries]
    assert "https://github.com/secret_user/repo" in xmp_vals and "TAIL_SENTINEL" in xmp_vals and "XMPTK_SECRET_TOKEN" in xmp_vals

    # REL-03: release_manifest read_supported_protocols matches mcp_server.SUPPORTED_PROTOCOLS
    rel_mod = _load_script("scripts/release_manifest.py", "rel_mod_rel03")
    protocols = rel_mod.read_supported_protocols((ROOT / "scripts/mcp_server.py").read_text(encoding="utf-8"))
    assert tuple(protocols) == mcp_mod.SUPPORTED_PROTOCOLS
    assert len(protocols) == 5

    # REL-02 & REL-G1: Verify de-identified ICLR 2026 incidence receipt conservation & all 23 localized READMEs
    receipt_path = ROOT / "docs" / "benchmarks" / "iclr2026-openreview-incidence-receipt.json"
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert "\\?\\?" not in receipt["methodology"]["regex_patterns"]["format_section_page"]
    tiers = receipt["tiers"]
    assert (
        tiers["Oral"]["papers_n"]
        + tiers["Poster"]["papers_n"]
        + tiers["Rejected"]["papers_n"]
        + tiers["Withdrawn"]["papers_n"]
        == tiers["STANDARD_DECISION_TIERS"]["papers_n"]
        == 18791
    )
    assert tiers["STANDARD_DECISION_TIERS"]["papers_n"] + tiers["Desk Reject"]["papers_n"] == tiers["ALL_SCORED"]["papers_n"] == 19473
    assert (
        tiers["SOUND_HIGH(>=3.25)"]["papers_n"]
        + tiers["SOUND_MID(2.0_to_3.25)"]["papers_n"]
        + tiers["SOUND_LOW(<=2.0)"]["papers_n"]
        == 19473
    )
    sp0 = receipt["split_half"]["split_0"]["ALL_SCORED"]["papers_n"]
    sp1 = receipt["split_half"]["split_1"]["ALL_SCORED"]["papers_n"]
    assert sp0 == 9765 and sp1 == 9708 and sp0 + sp1 == 19473
    all_readmes = sorted(list(ROOT.glob("README*.md")) + list(ROOT.glob("i18n/*/README.md")))
    assert len(all_readmes) == 23
    tf_checked = 0
    for rm in all_readmes:
        rm_txt = rm.read_text(encoding="utf-8")
        rm_lines = rm_txt.splitlines()
        assert "2.4.1" in rm_txt
        assert "iclr2026-openreview-incidence-receipt.json" in rm_txt
        dr_lines = [ln for ln in rm_lines if "Desk Reject" in ln and ln.strip().startswith("|")]
        assert len(dr_lines) == 1, f"Missing or duplicate Desk Reject table row in {rm}"
        dr_cells = [c.strip() for c in dr_lines[0].strip().strip("|").split("|")]
        assert len(dr_cells) == 4, f"Expected 4 columns in Desk Reject row of {rm}: {dr_cells}"
        assert dr_cells[1] == "682", f"Expected N=682 in column 1 of {rm}: {dr_cells}"
        assert dr_cells[2] == "4.01 / 2.46", f"Expected 4.01 / 2.46 in column 2 of {rm}: {dr_cells}"
        assert "**63.6%**" in dr_cells[3] and "434" in dr_cells[3], f"Missing 63.6% or 434 in column 3 of {rm}: {dr_cells}"
        assert dr_cells[3].index("21.8%") < dr_cells[3].index("11.6%") < dr_cells[3].index("6.6%"), f"Misordered family percentages in {rm}: {dr_cells[3]}"
        fmt_lines = [ln for ln in rm_lines if "`prepare`" in ln and ".pdf" in ln]
        all_12_exts = {".pdf", ".html", ".htm", ".xml", ".docx", ".xlsx", ".tex", ".bib", ".bbl", ".md", ".txt", ".py"}
        assert len(fmt_lines) == 1, f"Expected exactly 1 prepare format line in {rm}: {fmt_lines}"
        found_exts = set(re.findall(r"`(\.[a-z0-9]+)`", fmt_lines[0]))
        assert found_exts == all_12_exts, f"Prepare line backticked extensions mismatch in {rm}: {found_exts ^ all_12_exts}"
        neg_line = fmt_lines[0].replace("`.md`", "") + " [SKILL.md](skills/paper-research/SKILL.md)"
        assert "SKILL.md" in neg_line and ".md" not in set(re.findall(r"`(\.[a-z0-9]+)`", neg_line))
        for req_cmd in (
            "--verify-pdf",
            "--check-updates",
            "--check-academic-style",
            "--from-research extraction",
            "export-ceg-anchors",
            "repro-checklist",
            "literature-watch",
            "retraction-watch",
            "--action export-bibtex",
            "--action deduplicate",
        ):
            assert req_cmd in rm_txt, f"Missing {req_cmd!r} in {rm}"
        assert any(t in rm_txt for t in ("1364", "১৩৬৪", "۱۳۶۴")), f"Missing current 1364 test count in {rm}"
        for stale_tok in ("26.04", "15-intel", "1340", "16 類", "16 类", "13 CLI", "13 组", "13 組"):
            assert stale_tok not in rm_txt, f"Stale token {stale_tok!r} in {rm}"
        for ln in rm_lines:
            ln_clean = ln.replace("3.12", "")
            if "skills/literature-analysis" not in ln_clean and "12.1%" not in ln_clean and "12.4%" not in ln_clean and "pull/12" not in ln_clean:
                for bad_mcp in (" 12 ", "12개", "ke-12", "12 個", "12 个", "১২টি", "۱۲ ابزار", "الاثنتي عشرة"):
                    assert bad_mcp not in ln_clean, f"Stale MCP count {bad_mcp!r} in {rm}: {ln}"
        tf_lines = [ln for ln in rm_lines if "table-forensics --input spec.json" in ln]
        if tf_lines:
            tf_checked += 1
            assert all("2.3.0" in ln and "2.4.1" not in ln for ln in tf_lines)
    assert tf_checked == 5


def test_stage1_and_stage2_controlled_io_and_pipeline_bridges(tmp_path):
    """Verify Stage 1 controlled I/O, idempotent acronym protection, and Stage 2 research-to-writing bridges."""
    from academic_research_kernel.research import sources
    from academic_research_kernel import cli as ark_cli

    # 1. controlled_urlopen rejects private/loopback URLs
    for bad_url in ("http://127.0.0.1:8080/api", "http://localhost/test", "http://169.254.169.254/latest"):
        with pytest.raises(ValueError, match="outside acquisition scope"):
            with sources.controlled_urlopen(bad_url):
                pass

    # 2. controlled_read_pdf_pages rejects invalid max_pages and non-PDF files
    bad_pdf = tmp_path / "fake.pdf"
    bad_pdf.write_text("<html>not a pdf</html>", encoding="utf-8")
    with pytest.raises(ValueError, match="PDF signature missing"):
        sources.controlled_read_pdf_pages(bad_pdf)
    with pytest.raises(ValueError, match="max_pages"):
        sources.controlled_read_pdf_pages(bad_pdf, max_pages=0)
    with pytest.raises(ValueError, match="max_pages"):
        sources.controlled_read_pdf_pages(bad_pdf, max_pages=True)

    # 3. export_bibtex protect_acronyms is strictly idempotent
    eb_mod = _load_script("skills/literature-analysis/scripts/export_bibtex.py", "eb_stage1")
    once = eb_mod.protect_acronyms("A Survey on {RAG} and LLM Systems")
    twice = eb_mod.protect_acronyms(once)
    assert once == "A Survey on {RAG} and {LLM} Systems"
    assert twice == once

    # 4. receipt_to_latex_table --from-research extraction / results / comparison
    r2l_mod = _load_script("skills/academic-writing/scripts/receipt_to_latex_table.py", "r2l_stage2")
    ext_data = {
        "paper": {"title": r"Study \input{secret}", "identifier": "10.1000/test"},
        "fields": [
            {
                "id": "f_zero",
                "name": "Zero Loss_Metric",
                "status": "extracted",
                "literal": "0",
                "value": 0,
                "unit": "%",
                "context": {"dataset": "EvalA"},
                "sources": [{"document_id": "doc1", "locator": "pdf:page=1"}],
            },
            {
                "id": "f_miss",
                "name": "Unreported Metric",
                "status": "not_reported",
                "literal": None,
                "value": None,
                "unit": None,
                "reason": "omitted by authors",
                "context": {},
                "sources": [],
            },
        ],
    }
    ext_spec = r2l_mod.convert_research_artifact_to_spec(ext_data, "extraction")
    ext_tex = r2l_mod.render_booktabs_table(ext_spec)
    assert r"\textbackslash{}input\{secret\}" in ext_tex
    assert "0 & \\%" in ext_tex
    assert "[not\\_reported] omitted by authors" in ext_tex

    res_data = [
        {"id": "chk1", "kind": "t_p", "reported": "0.042", "recomputed": 0.0418, "status": "computed", "consistent": True},
        {"id": "chk2", "kind": "effect_size", "reported": None, "recomputed": {"cohens_d": 0.85, "hedges_g": 0.84}, "status": "computed", "consistent": None},
    ]
    res_spec = r2l_mod.convert_research_artifact_to_spec(res_data, "results")
    res_tex = r2l_mod.render_booktabs_table(res_spec)
    assert "0.042 & 0.0418 & computed & consistent" in res_tex
    assert "unreported & cohens\\_d=0.85, hedges\\_g=0.84 & computed & uncompared" in res_tex

    comp_data = {
        "rows": [
            {
                "dimension": "Accuracy",
                "left_field_ids": ["f_zero"],
                "right_field_ids": ["f_miss"],
                "assessment": "not_comparable",
                "reason": "different split",
            }
        ]
    }
    comp_spec = r2l_mod.convert_research_artifact_to_spec(
        comp_data, "comparison", left_extraction=ext_data, right_extraction=ext_data
    )
    comp_tex = r2l_mod.render_booktabs_table(comp_spec)
    assert "not\\_comparable" in comp_tex and r"\textbf" not in comp_tex
    with pytest.raises(ValueError, match="Non-finite"):
        r2l_mod.convert_research_artifact_to_spec(
            {"fields": [{"id": "f1", "name": "Bad", "status": "extracted", "value": float("nan")}]},
            "extraction",
        )

    # 5. venue_template_manager --action export-ceg-anchors
    vtm_mod = _load_script("skills/academic-writing/scripts/venue_template_manager.py", "vtm_stage2")
    ceg_file = tmp_path / "ceg.json"
    ceg_file.write_text(
        json.dumps({
            "claims": [
                {"id": "C_OK", "text": "Our model reduces latency by 25%.", "status": "supported"},
                {"id": "C_CONFLICT", "text": "Our model reduces latency by 90%.", "status": "supported"},
                {"id": "C_UNSUP", "text": "Preliminary observation.", "status": "unverified"},
                {"id": "C_UNVER", "text": "External claim.", "status": "supported"},
                {"id": "C_NO_EVID", "text": "No evidence id edge.", "status": "supported"},
            ],
            "evidence_anchors": [{"id": "E1"}, {"id": "E2"}],
            "support_edges": [
                {"claim_id": "C_OK", "evidence_id": "E1", "status": "supported"},
                {"claim_id": "C_CONFLICT", "evidence_id": "E1", "status": "supported"},
                {"claim_id": "C_CONFLICT", "evidence_id": "E2", "status": "contradicted"},
                {"claim_id": "C_GHOST", "evidence_id": "E1", "status": "supported"},
                {"claim_id": "C_UNSUP", "evidence_id": "E_MISSING", "status": "supported"},
                {"claim_id": "C_UNVER", "evidence_id": "E1", "status": "unverifiable"},
                {"claim_id": "C_NO_EVID", "status": "supported"},
            ],
        }),
        encoding="utf-8",
    )
    exported = vtm_mod.export_ceg_anchors(ceg_file)
    assert exported["total_claims"] == 5
    assert exported["eligible_count"] == 1
    assert exported["conflicted_count"] == 1
    assert exported["unsupported_count"] == 3
    assert len(exported["dangling_edges"]) == 3
    by_cid = {a["claim_id"]: a for a in exported["anchors"]}
    assert by_cid["C_OK"]["anchor_status"] == "eligible"
    assert by_cid["C_CONFLICT"]["anchor_status"] == "conflicted"
    assert by_cid["C_UNSUP"]["anchor_status"] == "unsupported"
    assert by_cid["C_UNVER"]["anchor_status"] == "unsupported" and by_cid["C_UNVER"]["unresolved_edge_count"] == 1
    assert by_cid["C_NO_EVID"]["anchor_status"] == "unsupported" and by_cid["C_NO_EVID"]["unresolved_edge_count"] == 1
    for bad_cid in ("C1\n", "\rC1", "C\n1"):
        bad_ceg = tmp_path / "bad_ceg.json"
        bad_ceg.write_text(json.dumps({"claims": [{"id": bad_cid, "text": "x"}], "evidence_anchors": [], "support_edges": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="line breaks"):
            vtm_mod.export_ceg_anchors(bad_ceg)
        bad_ceg_dict = tmp_path / "bad_ceg_dict.json"
        bad_ceg_dict.write_text(json.dumps({"claims": {bad_cid: {"text": "x"}}, "evidence_anchors": [], "support_edges": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="line breaks"):
            vtm_mod.export_ceg_anchors(bad_ceg_dict)
    for dup_claims in ({"C1": {"text": "a"}, " C1 ": {"text": "b"}}, {" C1 ": {"text": "b"}, "C1": {"text": "a"}}):
        dup_ceg = tmp_path / "dup_ceg.json"
        dup_ceg.write_text(json.dumps({"claims": dup_claims, "evidence_anchors": [{"id": "E1"}], "support_edges": [{"claim_id": "C1", "evidence_id": "E1", "status": "supported"}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="Duplicate claim_id"):
            vtm_mod.export_ceg_anchors(dup_ceg)


def test_stage3_and_stage4_cli_wiring_and_academic_style_linter(tmp_path, capsys):
    """Verify Stage 3 CLI wiring and Stage 4 academic prose & claim-boundary linter."""
    from academic_research_kernel import cli as ark_cli
    psl_mod = _load_script("skills/academic-writing/scripts/pre_submission_linter.py", "psl_stage4")

    # 1. CLI mutual exclusion and --check-updates --offline check on verify-source
    rc_err = ark_cli.main(["verify-source", "10.1038/nature14539", "--normalize-only", "--check-updates"])
    assert rc_err == 1
    out_err = json.loads(capsys.readouterr().out)
    assert "mutually exclusive" in out_err["error"]

    rc_off = ark_cli.main(["verify-source", "10.1038/nature14539", "--check-updates", "--offline"])
    assert rc_off == 1
    out_off = json.loads(capsys.readouterr().out)
    assert "--records" in out_off["error"]

    # 2. CLI repro-checklist, literature-watch --self-test, retraction-watch --self-test
    assert ark_cli.main(["literature-watch", "--self-test"]) == 0
    assert "self-test PASS" in capsys.readouterr().out
    assert ark_cli.main(["retraction-watch", "--self-test"]) == 0
    assert "self-test PASS" in capsys.readouterr().out

    # 3. Stage 4: --check-academic-style on manuscript with positives & true negatives
    tex_file = tmp_path / "main.tex"
    tex_file.write_text(
        "\\documentclass{article}\n"
        "\\newcommand{\\mycliche}{delve into}\n"
        "\\begin{document}\n"
        "\\begin{abstract}\n"
        "We delve into optimal transport and universal approximation. % delve into comment\n"
        "We cannot prove global convergence in general.\n"
        "The difference is not statistically significant ($p = 0.42$).\n"
        "Theorem \\ref{thm:main} proves that the bound holds.\n"
        "Theorem \\ref{thm:missing} proves that the bound holds globally.\n"
        "We do not use augmentation, but we prove that the bound holds unconditionally.\n"
        "We prove that optimal transport converges.\n"
        "Our method achieves a statistically significant gain.\n"
        "Our method achieves a statistically significant gain ($p < 0.01$, $95\\%$ CI).\n"
        "\\end{abstract}\n"
        "\\section{Introduction}\n"
        "随着大模型的飞速发展，本文在此基础上展开分析。\n"
        "\\begin{quote}\n"
        " Prior authors delve into a rich tapestry and prove that everything works.\n"
        "\\end{quote}\n"
        "\\section{Method}\n"
        "\\begin{theorem}\\label{thm:main}Main bound.\\end{theorem}\n"
        "All hyperparameters were tuned appropriately.\n"
        "All hyperparameters were tuned appropriately as listed in Table \\ref{tab:res}.\n"
        "\\section{Experiments}\n"
        "\\begin{table}\\label{tab:res}\\begin{tabular}{lr}A & $1.0 \\pm 0.1$\\\\\\end{tabular}\\end{table}\n"
        "\\section{Limitations}\n"
        "Bounded scope.\n"
        "\\section{Reproducibility Statement}\n"
        "Code provided.\n"
        "\\section{Conclusion}\n"
        "Our optimal transport estimator is globally optimal.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    rep = psl_mod.lint_manuscript(tex_file, venue="iclr", check_academic_style=True)
    assert rep["passed"] is True  # Advisories never fail the gate
    assert rep["style_check"] == {"enabled": True, "custom_macros_masked": 1}
    adv_hits = [h for h in rep["hits"] if h["severity"] == "advisory"]
    codes = Counter(h["code"] for h in adv_hits)
    assert codes["ACADEMIC_AI_CLICHE_CANDIDATE"] == 2
    assert codes["VAGUE_METHOD_DESCRIPTION_CANDIDATE"] == 1
    assert codes["UNANCHORED_STRONG_CLAIM_CANDIDATE"] == 5


def test_stage5_mcp_new_tools_and_redaction(tmp_path):
    """Verify the 6 new MCP tools and strict redaction on academic_double_blind_sanitize."""
    mcp_mod = _load_script("scripts/mcp_server.py", "mcp_stage5")

    # 1. academic_double_blind_sanitize redacts forbidden tokens in MCP output
    leak_dir = tmp_path / "leak_pkg"
    leak_dir.mkdir()
    (leak_dir / "main.tex").write_text("Contact SecretAuthorName123 at LabXYZ.\n", encoding="utf-8")
    resp = mcp_mod.process_message({
        "jsonrpc": "2.0",
        "id": 501,
        "method": "tools/call",
        "params": {
            "name": "academic_double_blind_sanitize",
            "arguments": {
                "target_path": str(leak_dir),
                "forbidden_tokens": ["SecretAuthorName123"],
            },
        },
    })
    raw_json_str = resp["result"]["content"][0]["text"]
    assert "SecretAuthorName123" not in raw_json_str
    parsed = json.loads(raw_json_str)
    assert parsed["status"] == "leaks_detected"
    assert parsed["findings"][0]["matched"] == "[REDACTED]"

    # 2. academic_table_forensics, academic_meta_analyze, academic_verify_source, academic_openreview_audit
    for call_id, t_name, t_args, expected_key in [
        (502, "academic_table_forensics", {"partition": {"total": 50, "parts": [20, 30]}}, "consistent"),
        (503, "academic_meta_analyze", {"studies": [{"yi": 0.2, "vi": 0.02}, {"yi": 0.4, "vi": 0.04}]}, "random_effects_dl"),
        (504, "academic_verify_source", {"identifier": "https://doi.org/10.1038/nature14539", "normalize_only": True}, "canonical"),
        (505, "academic_openreview_audit", {"venue_records": [{"forum_id": "F1", "title": "Test", "decision": "Reject", "ratings": [4, 5]}]}, "total_submissions"),
    ]:
        r = mcp_mod.process_message({
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": t_name, "arguments": t_args},
        })
        assert r["result"]["isError"] is False
        body = json.loads(r["result"]["content"][0]["text"])
        assert expected_key in body


def test_tex_bundle_discovery_and_uncited_bibliography_and_perf_dedup(tmp_path, monkeypatch):
    """Verify multi-file TeX bundle discovery from single entry .tex, glyphtounicode & microtype[final] handling, and UNCITED_BIBLIOGRAPHY_ENTRY."""
    import time
    from academic_research_kernel.research import sources
    psl_mod = _load_script("skills/academic-writing/scripts/pre_submission_linter.py", "psl_bundle_bib")

    # 1. Single entry .tex in prepare() discovers relative \input chapters and .bib/.bbl files with distinct hashes and cycle safety
    ms_dir = tmp_path / "ms_build"
    (ms_dir / "sections").mkdir(parents=True)
    (ms_dir / "subbib").mkdir(parents=True)
    main_tex = ms_dir / "main.tex"
    sec1_tex = ms_dir / "sections" / "01_intro.tex"
    refs_bib = ms_dir / "refs.bib"
    sub_bib = ms_dir / "subbib" / "sub_refs.bib"
    inline_bbl = ms_dir / "inline refs.bbl"

    inline_bbl.write_text(
        "\\begin{thebibliography}{1}\n\\bibitem[{[1]}]{bbl_cited_key} BBL Author, 2025.\n\\end{thebibliography}\n",
        encoding="utf-8",
    )
    sub_bib.write_text(
        "@article{subbib_cited_key,\n  author = {Subbib Author},\n  title = {Subdirectory Bib Entry},\n  year = {2025}\n}\n"
        "@article{subbib_phantom_key,\n  author = {Subbib Ghost},\n  title = {Subdirectory Uncited Entry},\n  year = {2024}\n}\n",
        encoding="utf-8",
    )
    main_tex.write_text(
        "\\documentclass{article}\n\\input{glyphtounicode}\n\\usepackage[\nfinal\n]{microtype,graphicx}\n"
        "\\usepackage[pdfkeywords={x,anonymous=false,y}]{hyperref}\n"
        "\\newcommand{\\unusedprobe}[1][{\\textbf{\\emph{X}}}]{\\input{missing_inside_macro}}\n"
        "\\newcommand{\\unusedbracket}[1][[]{\\input{missing_inside_bracket_macro}}\n"
        "\\addbibresource[label={A]B}]{subbib/sub_refs.bib}\n"
        "\\title{Multi-File Proof Bundle}\n\\begin{document}\n"
        "\\begin{abstract}\nWe study prime gaps.\n\\end{abstract}\n"
        "Linebreak\\\\input{not_a_real_include} and \\\\usepackage[final]{iclr2026_conference}\n"
        "\\input \"inline refs.bbl\"\n"
        "Literal percent \\verb|%| and \\verb|\\usepackage[final]{iclr2026_conference}| in prose.\n"
        "\\begin{minted}[linenos]{tex}\n\\input{ghost_in_minted}\n\\end{minted}\n"
        "\\begin{lstlisting}[title={\\input{sections/01_intro}}]\n\\input{ignored_inside_lstlisting}\n\\end{lstlisting}\n"
        "\\bibliography{refs}\n\\end{document}\n",
        encoding="utf-8",
    )
    sec1_tex.write_text(
        "\\input{glyphtounicode-cmex}\n"
        "\\section{Introduction}\n"
        "By Theorem~\\ref{thm:main}, \\cite[see \\emph{phantom_uncited_key}] [p.~2]{opt_ws_only_key}, "
        "\\citep[see \\citealp[p.~1]{nested_prenote_only_key}]{cited_key}, \\cite{why?}, \\cite{entryset_parent}, "
        "\\cite{ids_alias_key}, \\cite{bbl_cited_key}, \\cite{subbib_cited_key}, "
        "\\footcites[p.~3]{footcite_only_k1}[p.~4]{footcite_only_k2}, "
        "and \\cites(global pre)[p1]{cited_key}[p2]{child_key}[p3]{paren_child}, the bound holds.\n"
        "\\begin{theorem}\\label{thm:main}\nEvery gap is bounded.\n\\end{theorem}\n"
        "\\input main\n"
        "\\section{Related\nWork}\nPrior bounds are reviewed.\n"
        "\\section{Limitations}\nAssumes characteristic zero.\n"
        "\\section{Reproducibility Statement}\nProofs are self-contained.\n",
        encoding="utf-8",
    )
    refs_bib.write_text(
        "% Top-level comment with fake @article{ignored_top_comment, title={x}}\n"
        "@string{j_ann = \"Annals\"}\n"
        "@comment{\n@article{fake_inside_comment,\n  author = {Should Be Ignored},\n  title = {Nested in comment},\n  year = {2020}\n}\n}\n"
        "@article{cited_key,\n  author = {Ada Lovelace},\n  title = {Cited Work on crossref = {phantom_uncited_key}},\n  year = {2025}\n}\n"
        "@article{nested_prenote_only_key,\n  author = {Nested Prenote Author},\n  title = {Cited Inside citep Prenote},\n  year = {2025}\n}\n"
        "@article{why?,\n  author = {Question Key Author},\n  title = {Why Question Mark Key},\n  year = {2025}\n}\n"
        "@set{entryset_parent,\n  entryset = {entryset_member_a, entryset_member_b}\n}\n"
        "@article{entryset_member_a,\n  author = {Set Member A},\n  title = {Part A},\n  year = {2025}\n}\n"
        "@article{entryset_member_b,\n  author = {Set Member B},\n  title = {Part B},\n  year = {2025}\n}\n"
        "@misc{ids_primary_key,\n  ids = {ids_alias_key},\n  author = {Alias Author},\n  title = {Entry Cited Via Biblatex ids Alias},\n  year = {2025}\n}\n"
        "@article{footcite_only_k1,\n  author = {Emmy Noether},\n  title = {Footcited First},\n  year = {2025}\n}\n"
        "@article{footcite_only_k2,\n  author = {Sophie Germain},\n  title = {Footcited Second},\n  year = {2025}\n}\n"
        "@inproceedings{child_key,\n  author = {Grace Hopper},\n  title = {Child Work},\n  crossref = {parent_proc},\n  year = {2025}\n}\n"
        "@proceedings{parent_proc,\n  title = {Proceedings},\n  year = {2025}\n}\n"
        "@inproceedings(paren_child,\n  author = {Alan Turing},\n  title = \"A {\"x)y\"} B\",\n  crossref = {paren_parent},\n  year = {2025}\n)\n"
        "@proceedings(paren_parent,\n  title = {Paren Proceedings},\n  year = {2025}\n)\n"
        "@misc{opt_ws_only_key, author = {Donald Knuth}, title = {Optional Whitespace Only}, year = {2025}, url = {https://example.test/a%20b}}\n"
        "@article{phantom_uncited_key,\n  author = {Ghost Writer},\n  title = {Never Cited},\n  year = {2024}\n}\n",
        encoding="utf-8",
    )

    exact_unique_bytes = sum(p.stat().st_size for p in (main_tex, sec1_tex, refs_bib, sub_bib, inline_bbl))
    monkeypatch.setattr(sources, "MAX_TOTAL", exact_unique_bytes)
    proj_dir = tmp_path / "prepared_proj"
    prep_res = sources.prepare(str(main_tex), proj_dir)
    monkeypatch.setattr(sources, "MAX_TOTAL", 50 * 1024 * 1024)
    assert prep_res["parsed"] == 5
    assert prep_res["failures"] == []
    docs_payload = json.loads((proj_dir / "documents.json").read_text(encoding="utf-8"))
    by_rel = {d["relative_path"]: d for d in docs_payload["documents"]}
    assert by_rel["raw/main.tex"]["role"] == "main"
    assert by_rel["raw/sections/01_intro.tex"]["role"] == "body"
    assert by_rel["raw/inline refs.bbl"]["role"] == "body"
    assert by_rel["raw/refs.bib"]["role"] == "supplement"
    assert by_rel["raw/subbib/sub_refs.bib"]["role"] == "supplement"
    assert by_rel["raw/main.tex"]["sha256"] != by_rel["raw/sections/01_intro.tex"]["sha256"]

    # 2. pre_submission_linter exemptions, crossref/ids closure, and advisory UNCITED_BIBLIOGRAPHY_ENTRY
    lint_rep = psl_mod.lint_manuscript(main_tex, venue="iclr", check_academic_style=True)
    assert lint_rep["passed"] is True
    assert lint_rep["files_scanned"] == 3
    assert "Related Work" in lint_rep["discovered_sections"]
    assert "RelatedWork" not in lint_rep["discovered_sections"]
    hit_codes = [h["code"] for h in lint_rep["hits"]]
    assert "UNRESOLVED_TEX_INCLUDE" not in hit_codes
    assert "FORBIDDEN_REVIEW_PATTERN" not in hit_codes
    uncited = [h for h in lint_rep["hits"] if h["code"] == "UNCITED_BIBLIOGRAPHY_ENTRY"]
    assert len(uncited) == 2
    assert all(u["severity"] == "advisory" for u in uncited)
    uncited_msgs = " | ".join(u["message"] for u in uncited)
    assert "'phantom_uncited_key'" in uncited_msgs
    assert "'subbib_phantom_key'" in uncited_msgs
    for cited_k in ("cited_key", "subbib_cited_key", "nested_prenote_only_key", "parent_proc", "paren_parent", "ids_primary_key"):
        assert f"'{cited_k}'" not in uncited_msgs

    # 3. Local glyphtounicode.tex is scanned when present; \nocite{*} and custom cite macros suppress uncited warnings
    (ms_dir / "glyphtounicode.tex").write_text("\\section*{Glyph Map}\nLocal glyph mapping.\n\\nocite{*}\n", encoding="utf-8")
    prep_res_glyph = sources.prepare(str(main_tex), tmp_path / "prepared_proj_glyph")
    assert prep_res_glyph["parsed"] == 6
    lint_rep_local = psl_mod.lint_manuscript(main_tex, venue="iclr", check_academic_style=True)
    assert lint_rep_local["files_scanned"] == 4
    assert not any(h["code"] == "UNCITED_BIBLIOGRAPHY_ENTRY" for h in lint_rep_local["hits"])
    (ms_dir / "glyphtounicode.tex").unlink()

    # 4. Missing child .tex, missing explicit .bib, and bundle file-count cap in sources.prepare are recorded in failures
    ms_missing_dir = tmp_path / "ms_missing"
    ms_missing_dir.mkdir()
    m_missing_tex = ms_missing_dir / "main.tex"
    m_missing_tex.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\section{Intro}\nMain body text.\n"
        "\\input{missing_part}\n\\bibliography{missing_bib}\n\\end{document}\n",
        encoding="utf-8",
    )
    prep_missing = sources.prepare(str(m_missing_tex), tmp_path / "proj_missing")
    assert any(f["path"] == "missing_part.tex" and f["reason"] == "source file missing" for f in prep_missing["failures"])
    assert any(f["path"] == "missing_bib.bib" and f["reason"] == "source file missing" for f in prep_missing["failures"])

    monkeypatch.setattr(sources, "_MAX_TEX_BUNDLE_FILES", 1)
    prep_capped = sources.prepare(str(main_tex), tmp_path / "proj_capped")
    assert any("tex bundle limit exceeded" in f["reason"] for f in prep_capped["failures"])

    # 5. Re-visiting visited files or missing system glyphtounicode at MAX_TEX_FILES does not falsely trigger TEX_BUNDLE_TRUNCATED
    monkeypatch.setattr(psl_mod, "MAX_TEX_FILES", 3)
    lint_rep_cap = psl_mod.lint_manuscript(main_tex, venue="iclr", check_academic_style=False)
    assert not any(h["code"] == "TEX_BUNDLE_TRUNCATED" for h in lint_rep_cap["hits"])

    # 6. Multiline package options and exact line numbers for UNGROUNDED_QUANTITATIVE_CLAIM
    quant_tex = tmp_path / "quant_line.tex"
    quant_tex.write_text(
        "\\documentclass[\nfinal\n]{article}\n"
        "\\usepackage[pdfkeywords={a,anonymous=false,b},anonymous=\n\tfalse]{iclr2026_conference}\n"
        "\\begin{document}\n"
        "\\begin{abstract}\n"
        "We reduce latency by 42.5\\%.\n"
        "\\end{abstract}\n"
        "\\section[Short]{Conclusion}\nText\\\\appendix\n"
        "\\section{Limitations}\nText.\n\\section{Reproducibility Statement}\nText.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    q_rep = psl_mod.lint_manuscript(quant_tex, venue="iclr", require_ceg_binding=True)
    assert sum(1 for h in q_rep["hits"] if h["code"] == "FORBIDDEN_REVIEW_PATTERN") == 2
    q_hits = [h for h in q_rep["hits"] if h["code"] == "UNGROUNDED_QUANTITATIVE_CLAIM"]
    assert len(q_hits) == 1 and q_hits[0]["locator"] == "quant_line.tex:L8"
