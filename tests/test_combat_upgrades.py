"""Tests for the 4 real-world combat upgrades and all cross-audit counterexamples:
1. AI/CS table forensics (partition conservation, constant-offset ablation delta, storage/bandwidth bounds)
2. OpenAlex & institutional repository OA fallback when publisher returns 403 WAF
3. OpenReview API v2 submission status classifier & GitHub repository tree forensics
4. Author-side receipt-to-LaTeX booktabs generator & double-blind anonymity sanitizer
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(rel_path: str, mod_name: str):
    spec = importlib.util.spec_from_file_location(mod_name, ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
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


# ── 8. Cross-Review Counterexample Regressions (SEAT1_Astra & SEAT2_Sol) ─────

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
