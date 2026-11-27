"""Regression and capability tests for ARK v3.1 kernel trust-chain hardening.

Covers the four core structural gaps identified during the v3.0.0 external benchmark autopsy:
1. Controlled kernel execution provenance (`kernel_executions` + `execution_id` + `require_kernel_execution`).
2. Citation-vs-registry faithfulness (`cited_*` checks), `identity.resolve` ordered author conflict under shared DOI,
   and Crossref multi-date (`valid_years`) + retraction (`update-to` / `relation`) extraction.
3. Two-sided input-statistic rounding interval propagation (including `|t|` zero-crossing), inequality (`<`, `>`)
   comparators, symmetric `t`/`F`/`chi2` consistency verdicts, `df` dispatch isolation, and strict `ValueError` propagation.
4. Scoped evidence-edge semantics (`verification_scope` + `provenance_tier`) in exported Claim-Evidence Graphs.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import pytest

from academic_research_kernel import (
    identity,
    mcp_server,
    recompute,
    verify_work,
)
from academic_research_kernel._stdlib import validate_schema
from academic_research_kernel.state_db import ResearchStateDB
from academic_research_kernel.venue_template_manager import validate_ceg_semantics


# ---------------------------------------------------------------------------
# 1. Statistical interval comparator, zero-crossing, inequalities & MCP dispatch
# ---------------------------------------------------------------------------


def test_t_input_rounding_interval_rescues_legitimate_boundary_s14() -> None:
    """S14 (`t(15) = 2.3, p = .033`): point t=2.3000 gives p=0.0362, but t in [2.25, 2.35) overlaps [0.0325, 0.0335)."""
    res = recompute.check_stat_p_consistency(
        "t",
        2.3,
        15,
        reported_p=0.033,
        reported_p_literal="0.033",
        stat_literal="2.3",
    )
    assert res["point_consistent"] is False
    assert res["interval_consistent"] is True
    assert res["consistent"] is True
    assert res["status"] == "consistent_within_stat_rounding"
    lo, hi = res["recomputed_p_interval"]
    assert lo <= 0.0334 and hi >= 0.0326


def test_t_zero_crossing_interval_reaches_p_one() -> None:
    """When reported t='0.0' spans [-0.05, +0.05), |t| attains 0.0 so upper p bound must be 1.0."""
    res = recompute.check_stat_p_consistency(
        "t",
        0.0,
        24,
        reported_p=0.99,
        reported_p_literal="0.99",
        stat_literal="0.0",
    )
    lo, hi = res["recomputed_p_interval"]
    assert hi == pytest.approx(1.0, abs=1e-12)
    assert lo < 1.0
    assert res["interval_consistent"] is True


def test_inequality_p_comparator_handles_all_four_operators_and_thresholds() -> None:
    """All four inequalities (<, <=, >, >=) compare against exact threshold p_rep (not p_hi rounding bin), plus negative t."""
    # p(t=4.5, df=50) = 4.04e-5 < 0.001
    assert recompute.check_stat_p_consistency("t", 4.5, 50, reported_p=0.001, stat_literal="4.5", op="<")["consistent"] is True
    assert recompute.check_stat_p_consistency("t", -4.5, 50, reported_p=0.001, stat_literal="-4.5", op="<=")["consistent"] is True
    assert recompute.check_stat_p_consistency("t", 2.1, 50, reported_p=0.001, stat_literal="2.1", op="<")["consistent"] is False

    # Critical regression: point p ~ 0.054 (t=1.974, df=50 -> p=0.0539) MUST NOT satisfy p <= 0.05!
    not_le = recompute.check_stat_p_consistency(
        "t",
        1.974,
        50,
        reported_p=0.05,
        reported_p_literal="0.05",
        stat_literal="1.974",
        op="<=",
    )
    assert not_le["consistent"] is False
    assert not_le["point_consistent"] is False

    # > and >= checks:
    gt_ok = recompute.check_stat_p_consistency("t", 1.2, 50, reported_p=0.05, stat_literal="1.2", op=">")
    assert gt_ok["consistent"] is True
    ge_bad = recompute.check_stat_p_consistency("t", 3.5, 50, reported_p=0.05, stat_literal="3.5", op=">=")
    assert ge_bad["consistent"] is False


def test_negative_t_endpoint_inclusion_and_nan_or_operator_conflict_rejection() -> None:
    """Negative t interval [-2.35, -2.25) preserves lower-closed/upper-open endpoints, and NaN/conflicting operators raise ValueError."""
    neg_s14 = recompute.check_stat_p_consistency(
        "t",
        -2.3,
        15,
        reported_p=0.033,
        reported_p_literal="0.033",
        stat_literal="-2.3",
    )
    assert neg_s14["recomputed_p_interval_inclusive"] == [True, False]
    assert neg_s14["interval_consistent"] is True

    mcp_server.reset_session_db()
    with pytest.raises(ValueError):
        mcp_server.handle_tool_call(
            "academic_recompute_statistics",
            {"t_stat": 2.2, "df": 20, "p_value_literal": "NaN"},
        )
    with pytest.raises(ValueError, match="Conflicting p_operator"):
        mcp_server.handle_tool_call(
            "academic_recompute_statistics",
            {"t_stat": 2.2, "df": 20, "p_operator": ">", "p_value_literal": "< 0.05"},
        )


def test_mcp_chi2_with_df_does_not_leak_into_t_test_and_returns_consistent() -> None:
    """Passing chi2_stat + df must not enter the t_stat branch or emit partial_failure KeyError('t_stat')."""
    mcp_server.reset_session_db()
    out = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {
            "chi2_stat": 6.2,
            "df": 2,
            "p_value": 0.045,
            "p_value_literal": "0.045",
            "stat_literal": "6.2",
        },
    )
    assert "partial_failure" not in out
    assert out["consistent"] is True
    assert out["stat_p_consistency"]["interval_consistent"] is True
    assert str(out["execution_id"]).startswith("kexec-")


def test_mcp_f_test_returns_top_level_consistent_and_bad_p_argument_raises() -> None:
    """F-test also populates consistent/stat_p_consistency, and invalid p_value (>1) raises ValueError instead of silent False."""
    mcp_server.reset_session_db()
    f_ok = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {
            "f_stat": 4.52,
            "df1": 2,
            "df2": 57,
            "p_value": 0.015,
            "p_value_literal": "0.015",
            "stat_literal": "4.52",
        },
    )
    assert f_ok["consistent"] is True
    assert f_ok["stat_p_consistency"]["consistent"] is True

    with pytest.raises(ValueError, match="\\[0,\\s*1\\]"):
        mcp_server.handle_tool_call(
            "academic_recompute_statistics",
            {"t_stat": 2.2, "df": 20, "p_value": 1.5},
        )


# ---------------------------------------------------------------------------
# 2. Identity author conflicts, Crossref multi-year/retraction & citation checks
# ---------------------------------------------------------------------------


def test_identity_resolve_flags_stolen_doi_fabricated_authors_and_order_swap() -> None:
    """Shared DOI still identifies the target Work, but conflicting or reordered authors must surface in conflict_fields and uncertainty."""
    fabricated = identity.resolve(
        [
            {
                "identifiers": [{"type": "doi", "value": "10.1038/nature14539"}],
                "title": "Deep learning",
                "authors": ["Fake Person One", "Fake Person Two"],
                "year": 2015,
                "source": "manuscript_citation",
            },
            {
                "identifiers": [{"type": "doi", "value": "10.1038/nature14539"}],
                "title": "Deep learning",
                "authors": ["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
                "year": 2015,
                "source": "Crossref",
            },
        ]
    )
    assert fabricated["verdict"] == "EXACT"
    assert "authors" in fabricated["conflict_fields"]
    assert any(u["kind"] == "metadata_conflict" and u["needs_human"] is True for u in fabricated["uncertainty"])

    # Last, First vs First Last for the same authors in the same order must NOT false-alarm:
    same_order_diff_format = identity.resolve(
        [
            {
                "identifiers": [{"type": "doi", "value": "10.1038/nature14539"}],
                "title": "Deep learning",
                "authors": ["LeCun, Yann", "Bengio, Yoshua"],
                "year": 2015,
            },
            {
                "identifiers": [{"type": "doi", "value": "10.1038/nature14539"}],
                "title": "Deep learning",
                "authors": ["Yann LeCun", "Yoshua Bengio"],
                "year": 2015,
            },
        ]
    )
    assert "authors" not in same_order_diff_format["conflict_fields"]
    assert "author_order" not in same_order_diff_format["conflict_fields"]
    assert "authors" in same_order_diff_format["match_fields"]

    # Swapped author order preserves work-level STRONG_MATCH/EXACT deduplication while surfacing author_order_mismatch in uncertainty:
    swapped = identity.resolve(
        [
            {
                "identifiers": [{"type": "doi", "value": "10.1038/nature14539"}],
                "title": "Deep learning",
                "authors": ["Yoshua Bengio", "Yann LeCun"],
                "year": 2015,
            },
            {
                "identifiers": [{"type": "doi", "value": "10.1038/nature14539"}],
                "title": "Deep learning",
                "authors": ["Yann LeCun", "Yoshua Bengio"],
                "year": 2015,
            },
        ]
    )
    assert any(u["kind"] == "author_order_mismatch" and u["needs_human"] is True for u in swapped["uncertainty"])


def test_crossref_parser_extracts_retraction_direction_and_online_print_valid_years() -> None:
    """Crossref updated-by marks the retracted work; update-to on a separate notice DOI does NOT falsely mark the notice itself retracted."""
    cr_retracted_work = {
        "message": {
            "DOI": "10.1145/3503250",
            "title": ["NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis"],
            "published-online": {"date-parts": [[2021, 12, 17]]},
            "published-print": {"date-parts": [[2022, 1, 1]]},
            "author": [{"given": "Ben", "family": "Mildenhall"}],
            "container-title": ["Communications of the ACM"],
            "updated-by": [{"type": "retraction", "DOI": "10.1145/9999999"}],
        }
    }
    parsed_cr = verify_work.parse_crossref_work(cr_retracted_work)
    assert parsed_cr["year"] == 2022
    assert parsed_cr["valid_years"] == [2021, 2022]
    assert parsed_cr["is_retracted"] is True

    # Separate retraction notice pointing via update-to to another DOI:
    cr_notice = {
        "message": {
            "DOI": "10.1145/9999999",
            "title": ["Retraction Notice"],
            "update-to": [{"type": "retraction", "DOI": "10.1145/3503250"}],
        }
    }
    parsed_notice = verify_work.parse_crossref_work(cr_notice)
    assert parsed_notice["is_retracted"] is False
    assert parsed_notice["retraction_notices_for"] == ["10.1145/3503250"]

    with pytest.raises(ValueError, match="boolean"):
        verify_work.parse_openalex_work({"doi": "10.1/x", "is_retracted": "false"})

    oa_payload = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1145/3503250",
        "display_name": "NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis",
        "publication_year": 2021,
        "authorships": [{"author": {"display_name": "Ben Mildenhall"}}],
        "is_retracted": False,
    }
    parsed_oa = verify_work.parse_openalex_work(oa_payload)
    cmp = verify_work.compare_works([parsed_oa, parsed_cr], target_doi="10.1145/3503250")
    assert cmp["fields"]["year"]["year_compatible"] is True
    assert cmp["is_retracted"] is True

    # Missing DOI in a source record must NOT count as positively bound:
    missing_doi_res = mcp_server.handle_tool_call(
        "academic_verify_source",
        {"identifier": "10.1145/3503250", "openalex_record": {"title": "No DOI"}},
    )
    assert missing_doi_res["identifier_resolved"] is False
    assert missing_doi_res["consistent"] is False


def test_academic_verify_source_checks_cited_metadata_venues_initials_and_chimeras() -> None:
    """academic_verify_source distinguishes DOI existence from paper-side citation faithfulness, venue substrings, middle initials, et al., and chimeras."""
    mcp_server.reset_session_db()
    oa_rec = {
        "id": "https://openalex.org/W2963403868",
        "doi": "https://doi.org/10.1145/3503250",
        "display_name": "NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis",
        "publication_year": 2021,
        "primary_location": {"source": {"display_name": "Nature Communications"}},
        "authorships": [
            {"author": {"display_name": "Ben Mildenhall"}},
            {"author": {"display_name": "Pratul P. Srinivasan"}},
        ],
        "is_retracted": False,
    }
    cr_rec = {
        "message": {
            "DOI": "10.1145/3503250",
            "title": ["NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis"],
            "published-online": {"date-parts": [[2021, 12, 17]]},
            "published-print": {"date-parts": [[2022, 1, 1]]},
            "container-title": ["Nature Communications"],
            "author": [
                {"given": "Ben", "family": "Mildenhall"},
                {"given": "Pratul P.", "family": "Srinivasan"},
            ],
        }
    }

    # Stolen DOI with hallucinated title and fabricated first author:
    stolen = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.1145/3503250",
            "openalex_record": oa_rec,
            "crossref_record": cr_rec,
            "cited_title": "Completely Hallucinated Quantum Transformer Survey",
            "cited_authors": ["John Doe", "Jane Roe"],
            "cited_year": 2021,
        },
    )
    assert stolen["identifier_resolved"] is True
    assert stolen["citation_metadata_match"] is False
    assert "title" in stolen["citation_check"]["mismatched_fields"]
    assert "authors" in stolen["citation_check"]["mismatched_fields"]
    assert stolen["consistent"] is False
    assert stolen["verification_scope"] == "bibliographic_citation_faithfulness_caller_record"

    # Venue substring trap ('Nature' must NOT match 'Nature Communications') and wrong middle initial ('Pratul Q.'):
    wrong_venue_initial = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.1145/3503250",
            "openalex_record": oa_rec,
            "crossref_record": cr_rec,
            "cited_title": "NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis",
            "cited_authors": ["Ben Mildenhall", "Pratul Q. Srinivasan"],
            "cited_year": 2021,
            "cited_venue": "Nature",
        },
    )
    assert wrong_venue_initial["citation_metadata_match"] is False
    assert set(wrong_venue_initial["citation_check"]["mismatched_fields"]) >= {"authors", "venue"}

    # Truncated author list without 'et al.' fails, with 'et al.' succeeds:
    trunc_no_etal = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.1145/3503250",
            "openalex_record": oa_rec,
            "cited_authors": ["Ben Mildenhall"],
        },
    )
    assert trunc_no_etal["citation_metadata_match"] is False
    trunc_with_etal = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.1145/3503250",
            "openalex_record": oa_rec,
            "cited_authors": ["Ben Mildenhall", "et al."],
        },
    )
    assert trunc_with_etal["citation_metadata_match"] is True

    # Faithful citation citing online year 2021 (compatible with Crossref online+print [2021, 2022]):
    faithful = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.1145/3503250",
            "openalex_record": oa_rec,
            "crossref_record": cr_rec,
            "cited_title": "NeRF: Representing Scenes as Neural Radiance Fields for View Synthesis",
            "cited_authors": ["Ben Mildenhall", "Pratul P. Srinivasan"],
            "cited_year": 2021,
            "cited_venue": "Nature Communications",
        },
    )
    assert faithful["identifier_resolved"] is True
    assert faithful["citation_metadata_match"] is True
    assert faithful["consistent"] is True


# ---------------------------------------------------------------------------
# 3 & 4. Controlled kernel execution provenance & scoped CEG support edges
# ---------------------------------------------------------------------------


def test_require_kernel_execution_blocks_unexecuted_forged_audit_and_binds_real_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Caller cannot smuggle self-authored consistent=True under require_kernel_execution=True; real execution_id binds cleanly and survives DB reopen."""
    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("ARK_EXECUTION_KEY_HEX", "11" * 32)
    mcp_server.reset_session_db()
    db_file = tmp_path / "hardened.sqlite3"

    mcp_server.handle_tool_call(
        "claim_evidence_add",
        {
            "db_path": str(db_file),
            "claim_id": "c_stat_1",
            "claim_text": "Treatment group outperformed control (t(1315) = 2.43, p = 0.146).",
        },
    )

    # 1. Raw LLM-forged quantitative_audit without kernel execution MUST be rejected when require_kernel_execution=True:
    with pytest.raises(ValueError, match="execution_id"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {
                "db_path": str(db_file),
                "artifact_id": "results-forged-1",
                "kind": "quantitative_audit",
                "require_kernel_execution": True,
                "bindings": {"claim_id": "c_stat_1"},
                "payload": {
                    "assertions": [{"claim_id": "c_stat_1", "consistent": True, "discrepancy_detected": False}],
                },
            },
        )

    # 2. Forged/unknown execution_id MUST be rejected:
    with pytest.raises(ValueError, match="Unknown or expired kernel execution_id"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {
                "db_path": str(db_file),
                "artifact_id": "results-forged-2",
                "kind": "quantitative_audit",
                "execution_id": "kexec-000000000000000000000000",
                "bindings": {"claim_id": "c_stat_1"},
            },
        )

    # 3. Genuine kernel recomputation detects p-value error (recomputed p = 0.0152 != 0.146):
    exec_out = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {
            "db_path": str(db_file),
            "t_stat": 2.43,
            "df": 1315,
            "p_value": 0.146,
            "p_value_literal": "0.146",
            "stat_literal": "2.43",
        },
    )
    assert exec_out["consistent"] is False
    exec_id = exec_out["execution_id"]

    # 4. Caller trying to pass real execution_id while lying OR substituting a same-stance fabricated payload MUST be rejected (raw, dry_run, and envelope):
    for bad_payload in (
        {"assertions": [{"claim_id": "c_stat_1", "consistent": True, "discrepancy_detected": False}]},
        {"assertions": [{"claim_id": "c_stat_1", "consistent": False, "discrepancy_detected": True, "note": "forged same-stance payload"}]},
    ):
        with pytest.raises(ValueError, match="tamper|mismatch"):
            mcp_server.handle_tool_call(
                "research_artifact_ingest",
                {
                    "db_path": str(db_file),
                    "artifact_id": "results-tampered",
                    "kind": "quantitative_audit",
                    "execution_id": exec_id,
                    "dry_run": True,
                    "bindings": {"claim_id": "c_stat_1"},
                    "payload": bad_payload,
                },
            )
    bad_env_pay = {"assertions": [{"consistent": False, "discrepancy_detected": True, "note": "envelope forgery"}]}
    from academic_research_kernel._stdlib import canonical_json, sha256_hex

    bad_env_sha = sha256_hex(canonical_json(bad_env_pay))
    with pytest.raises(ValueError, match="tamper|mismatch"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {
                "db_path": str(db_file),
                "execution_id": exec_id,
                "envelope": {
                    "protocol": "artifact-envelope-1.0",
                    "artifact_id": f"art-{bad_env_sha[:32]}",
                    "artifact_kind": "quantitative_audit",
                    "producer": {"skill": "quantitative-paper-audit", "version": "1.0"},
                    "payload_schema": "quantitative-audit.schema.json",
                    "payload_sha256": bad_env_sha,
                    "payload": bad_env_pay,
                },
            },
        )

    # 4b. Cross-DB execution_id replay (:memory: receipt into db_file) MUST be rejected:
    mem_exec = mcp_server.handle_tool_call("academic_check_percentage", {"count": 5, "percent": 50.0, "n": 10})
    with pytest.raises(ValueError, match="Unknown or expired kernel execution_id"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {
                "db_path": str(db_file),
                "artifact_id": "results-cross-db",
                "kind": "quantitative_audit",
                "execution_id": mem_exec["execution_id"],
                "require_kernel_execution": True,
            },
        )

    # 4c. Rollback atomicity: dangling claim_id rolls back artifact + binding write cleanly:
    with pytest.raises(ValueError, match="claim_id|not found|Unknown"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {
                "db_path": str(db_file),
                "artifact_id": "results-should-rollback",
                "kind": "quantitative_audit",
                "execution_id": exec_id,
                "bindings": {"claim_id": "nonexistent_claim"},
            },
        )

    # 5. Ingesting directly from kernel execution_id derives authoritative payload + contradicts edge + scoped metadata:
    ing = mcp_server.handle_tool_call(
        "research_artifact_ingest",
        {
            "db_path": str(db_file),
            "artifact_id": "results-verified-s1-03",
            "kind": "quantitative_audit",
            "execution_id": exec_id,
            "require_kernel_execution": True,
            "bindings": {"claim_id": "c_stat_1"},
        },
    )
    assert ing["receipt"]["artifact_id"] == "results-verified-s1-03"

    # Attach a SECOND claim post-ingest via claim_evidence_add: must be marked bound_at_ingest=False and caller_asserted_binding:
    mcp_server.handle_tool_call(
        "claim_evidence_add",
        {
            "db_path": str(db_file),
            "claim_id": "c_unrelated_2",
            "claim_text": "A later caller-attached claim referencing the same artifact.",
            "evidence": [["results-verified-s1-03", "contradicts", "sec2"]],
        },
    )

    # Reopen from disk in read-only mode to prove persistence and honest artifact-vs-edge provenance separation:
    with ResearchStateDB(db_file, readonly=True, root=tmp_path) as ro_db:
        ceg = ro_db.export_ceg_dict()
    assert validate_schema(ceg, "claim-evidence-graph.schema.json") == []
    assert validate_ceg_semantics(ceg)["semantic_errors"] == []

    edges_by_claim = {e["claim_id"]: e for e in ceg["support_edges"]}
    edge1 = edges_by_claim["c_stat_1"]
    assert edge1["support_status"] == "contradicted"
    assert edge1["metadata"]["artifact_provenance_tier"] == "kernel_executed"
    assert edge1["metadata"]["edge_provenance_tier"] == "caller_asserted_binding"
    assert edge1["metadata"]["bound_at_ingest"] is True
    assert edge1["metadata"]["verification_scope"] == "statistical_numerical_consistency"
    assert edge1["metadata"]["execution_id"] == exec_id

    edge2 = edges_by_claim["c_unrelated_2"]
    assert edge2["metadata"]["artifact_provenance_tier"] == "kernel_executed"
    assert edge2["metadata"]["edge_provenance_tier"] == "caller_asserted_binding"
    assert edge2["metadata"]["bound_at_ingest"] is False

    # 6. Direct SQLite INSERT forgery without the kernel HMAC key MUST be rejected on lookup and downgraded on export:
    conn = sqlite3.connect(str(db_file))
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM kernel_executions")
        conn.execute(
            """
            INSERT INTO kernel_executions
            (execution_id, tool_name, kernel_version, verification_scope, consistent, executed_at, inputs_json, inputs_sha256, outputs_json, outputs_sha256, auth_hmac)
            VALUES (?, 'academic_recompute_statistics', '3.0.0', 'statistical_numerical_consistency', 1, '2026-11-23T00:00:00Z', '{}', ?, '{}', ?, ?)
            """,
            ("kexec-forgedsqlite000000000000", "a" * 64, "b" * 64, "c" * 64),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(ValueError, match="Tampered|Unauthenticated"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {
                "db_path": str(db_file),
                "artifact_id": "results-from-sqlite-forgery",
                "kind": "quantitative_audit",
                "execution_id": "kexec-forgedsqlite000000000000",
            },
        )


def test_legacy_pre_v31_sqlite_db_readonly_export_and_digest_stability(tmp_path: Path) -> None:
    """A pre-v3.1 SQLite file lacking kernel_executions/artifact_execution_bindings opens readonly, exports valid CEG, and preserves digest across upgrade."""
    legacy_db = tmp_path / "legacy_v300.sqlite3"
    with ResearchStateDB(legacy_db, root=tmp_path) as db:
        db.batch_ingest([{"artifact_id": "a_leg", "kind": "data_snapshot", "payload": {"v": 1}}])
        db.add_claim("c_leg", "Legacy claim", None, [("a_leg", "supports", "p1")])
        digest_with_empty_new_tables = db.snapshot_digest()

    # Simulate true v3.0.0 SQLite file by dropping the two v3.1 tables and triggers:
    conn = sqlite3.connect(str(legacy_db))
    try:
        conn.executescript(
            """
            DROP TRIGGER IF EXISTS trg_artifact_exec_bindings_immutable_upd;
            DROP TRIGGER IF EXISTS trg_artifact_exec_bindings_immutable_del;
            DROP TABLE IF EXISTS artifact_execution_bindings;
            DROP TRIGGER IF EXISTS trg_kernel_executions_immutable_upd;
            DROP TRIGGER IF EXISTS trg_kernel_executions_immutable_del;
            DROP TABLE IF EXISTS kernel_executions;
            """
        )
        conn.commit()
    finally:
        conn.close()

    with ResearchStateDB(legacy_db, readonly=True, root=tmp_path) as ro_leg:
        assert ro_leg.snapshot_digest() == digest_with_empty_new_tables
        ceg_leg = ro_leg.export_ceg_dict()
    assert validate_schema(ceg_leg, "claim-evidence-graph.schema.json") == []
    assert validate_ceg_semantics(ceg_leg)["semantic_errors"] == []
    assert ceg_leg["support_edges"][0]["metadata"]["artifact_provenance_tier"] == "external_unverified"


def test_jsonrpc_stdio_end_to_end_verify_source_execution_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Over full JSON-RPC stdio validation, academic_verify_source execution_id backs evidence_receipt ingest and scopes CEG edges."""
    import io
    import json

    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("ARK_EXECUTION_KEY_HEX", "33" * 32)
    mcp_server.reset_session_db()
    db_file = tmp_path / "bib_e2e.sqlite3"

    oa_rec = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1038/nature14539",
        "title": "Deep learning",
        "publication_year": 2015,
        "authorships": [{"author": {"display_name": "Yann LeCun"}}],
        "is_retracted": False,
    }
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "claim_evidence_add",
                "arguments": {
                    "db_path": str(db_file),
                    "claim_id": "c_bib_1",
                    "claim_text": "Cites LeCun et al. (2015) Deep learning (10.1038/nature14539).",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "academic_verify_source",
                "arguments": {
                    "db_path": str(db_file),
                    "identifier": "10.1038/nature14539",
                    "openalex_record": oa_rec,
                    "cited_title": "Deep learning",
                    "cited_authors": ["LeCun, Yann"],
                    "cited_year": 2015,
                },
            },
        },
    ]
    in_bytes = b"".join((json.dumps(r) + "\n").encode("utf-8") for r in requests)
    out_buf = io.BytesIO()
    assert mcp_server.serve_stream(io.BytesIO(in_bytes), out_buf) == 0
    responses = [json.loads(line) for line in out_buf.getvalue().decode("utf-8").splitlines() if line.strip()]
    assert len(responses) == 2
    vs_payload = json.loads(responses[1]["result"]["content"][0]["text"])
    assert vs_payload["consistent"] is True
    exec_id = vs_payload["execution_id"]

    # Bind via JSON-RPC research_artifact_ingest with require_kernel_execution=True:
    req3 = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "research_artifact_ingest",
            "arguments": {
                "db_path": str(db_file),
                "artifact_id": "bib-receipt-1",
                "kind": "evidence_receipt",
                "execution_id": exec_id,
                "require_kernel_execution": True,
                "bindings": {"claim_id": "c_bib_1"},
            },
        },
    }
    out_buf2 = io.BytesIO()
    assert mcp_server.serve_stream(io.BytesIO((json.dumps(req3) + "\n").encode("utf-8")), out_buf2) == 0
    resp3 = json.loads(out_buf2.getvalue().decode("utf-8").strip())
    assert "error" not in resp3
    ing_res = json.loads(resp3["result"]["content"][0]["text"])
    assert ing_res["receipt"]["status"] == "accepted"

    # Validate via full JSON-RPC tools/call (not direct Python handler):
    req4 = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "claim_evidence_validate",
            "arguments": {"db_path": str(db_file)},
        },
    }
    out_buf3 = io.BytesIO()
    assert mcp_server.serve_stream(io.BytesIO((json.dumps(req4) + "\n").encode("utf-8")), out_buf3) == 0
    resp4 = json.loads(out_buf3.getvalue().decode("utf-8").strip())
    assert "error" not in resp4
    val_res = json.loads(resp4["result"]["content"][0]["text"])
    assert val_res["valid"] is True
    traced = mcp_server.handle_tool_call("claim_evidence_trace", {"db_path": str(db_file), "claim_id": "c_bib_1"})
    edge = traced["support_edges"][0]
    assert edge["support_status"] == "supported"
    assert edge["metadata"]["artifact_provenance_tier"] == "kernel_executed"
    assert edge["metadata"]["edge_provenance_tier"] == "caller_asserted_binding"
    assert edge["metadata"]["bound_at_ingest"] is True
    assert edge["metadata"]["verification_scope"] == "bibliographic_citation_faithfulness_caller_record"


def test_round2_regressions_partial_conflict_mixed_scope_copied_db_and_zero_tail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers Round-2 findings: partial-record registry conflict, ['mismatch','uncheckable'], p <= 0 underflow, copied DB replay, and mixed live/caller scope."""
    import shutil

    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("ARK_EXECUTION_KEY_HEX", "55" * 32)
    mcp_server.reset_session_db()

    # 1. p <= 0 must be False even at extreme z=40 where IEEE-754 sf underflows to 0.0:
    z_extreme = recompute.check_stat_p_consistency("z", 40.0, reported_p=0.0, op="<=")
    assert z_extreme["consistent"] is False

    # 2. Partial-record registry conflict: Source A matches title+year, Source B contradicts title and omits year -> must NOT be True:
    oa_full = {
        "doi": "https://doi.org/10.1000/test1",
        "title": "Exact Expected Title",
        "publication_year": 2024,
        "is_retracted": False,
    }
    cr_partial_conflict = {
        "message": {
            "DOI": "10.1000/test1",
            "title": ["Completely Different Conflicting Title"],
        }
    }
    conf_res = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.1000/test1",
            "openalex_record": oa_full,
            "crossref_record": cr_partial_conflict,
            "cited_title": "Exact Expected Title",
            "cited_year": 2024,
        },
    )
    assert conf_res["citation_metadata_match"] is None
    assert "title" in conf_res["citation_check"]["conflicting_fields"]
    assert conf_res["consistent"] is None

    # 2b. ['mismatch', 'uncheckable'] across two bound sources must be mismatch (False), never True:
    oa_mismatch = {"doi": "https://doi.org/10.1000/test2", "title": "Actual Title", "publication_year": 2024}
    cr_missing_year = {"message": {"DOI": "10.1000/test2", "title": ["Actual Title"]}}
    mis_unc = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.1000/test2",
            "openalex_record": oa_mismatch,
            "crossref_record": cr_missing_year,
            "cited_year": 1999,
        },
    )
    assert mis_unc["citation_metadata_match"] is False
    assert "year" in mis_unc["citation_check"]["mismatched_fields"]
    assert mis_unc["consistent"] is False

    # 3. Mixed live + caller-record acquisition must be labeled _mixed_sources, never pure _live:
    monkeypatch.setattr(verify_work, "fetch_crossref", lambda doi: {"DOI": doi, "title": ["Actual Title"], "issued": {"date-parts": [[2024]]}})
    mixed = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.1000/test2",
            "live": True,
            "openalex_record": oa_mismatch,
            "cited_title": "Actual Title",
        },
    )
    assert mixed["verification_scope"] == "bibliographic_citation_faithfulness_mixed_sources"

    # 4. Store-scoped HMAC: copying db_a.sqlite3 to db_b.sqlite3 invalidates store-scoped execution/binding MACs on db_b:
    db_a = tmp_path / "store_a.sqlite3"
    db_b = tmp_path / "store_b.sqlite3"
    mcp_server.handle_tool_call("claim_evidence_add", {"db_path": str(db_a), "claim_id": "c1", "claim_text": "Pct check"})
    ex_a = mcp_server.handle_tool_call("academic_check_percentage", {"db_path": str(db_a), "count": 4, "percent": 40.0, "n": 10})
    mcp_server.handle_tool_call(
        "research_artifact_ingest",
        {
            "db_path": str(db_a),
            "artifact_id": "results-pct-a",
            "kind": "quantitative_audit",
            "execution_id": ex_a["execution_id"],
            "require_kernel_execution": True,
            "bindings": {"claim_id": "c1"},
        },
    )
    shutil.copy2(db_a, db_b)
    with ResearchStateDB(db_b, readonly=True, root=tmp_path) as ro_b:
        ceg_b = ro_b.export_ceg_dict()
    edge_b = ceg_b["support_edges"][0]
    assert edge_b["metadata"]["artifact_provenance_tier"] == "external_unverified"
    assert edge_b["metadata"]["unauthenticated_execution_binding"] is True


def test_db_bind_artifact_execution_rejects_noncanonical_payload_and_export_downgrades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DB signing boundary rejects noncanonical/inverted payloads and wrong kinds, and export re-verifies canonical match."""
    from academic_research_kernel import state_db as sdb_mod
    import copy

    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("ARK_EXECUTION_KEY_HEX", "22" * 32)
    db_file = tmp_path / "canonical_bind_guard.sqlite3"

    real_exec = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"db_path": str(db_file), "t_stat": 2.0, "df": 10, "p_value": 0.001},
    )
    assert real_exec["consistent"] is False
    eid = real_exec["execution_id"]

    with ResearchStateDB(db_file, root=tmp_path) as db:
        exec_rec = db.get_kernel_execution(eid)
        assert exec_rec is not None
        canonical_pay = mcp_server._canonical_payload_from_execution("quantitative_audit", exec_rec)
        forged_pay = copy.deepcopy(canonical_pay)
        forged_pay["assertions"][0]["consistent"] = True
        forged_pay["assertions"][0]["discrepancy_detected"] = False

        db.batch_ingest(
            [
                {"artifact_id": "art-canonical-ok", "kind": "quantitative_audit", "payload": canonical_pay},
                {"artifact_id": "art-forged-opposite", "kind": "quantitative_audit", "payload": forged_pay},
                {"artifact_id": "art-wrong-kind", "kind": "data_snapshot", "payload": {"v": 1}},
            ]
        )

        # Positive control: exact canonical payload binds cleanly
        db.bind_artifact_execution("art-canonical-ok", eid, "statistical_numerical_consistency")

        # Negative 1: inverted conclusion payload MUST be rejected at DB signing boundary
        with pytest.raises(ValueError, match="canonical kernel execution payload|mismatch"):
            db.bind_artifact_execution("art-forged-opposite", eid, "statistical_numerical_consistency")

        # Negative 2: wrong artifact kind MUST be rejected at DB signing boundary
        with pytest.raises(ValueError, match="cannot back|unsupported"):
            db.bind_artifact_execution("art-wrong-kind", eid, "statistical_numerical_consistency")

        db.add_claim("c_forged", "Opposite claim", None, [("art-forged-opposite", "supports", "p1")])
        store_scope = db._store_scope_id()
        forged_sha = sdb_mod.sha256_hex(sdb_mod.canonical_json(forged_pay))
        raw_bmac = sdb_mod._compute_binding_hmac(
            store_scope,
            "art-forged-opposite",
            "quantitative_audit",
            forged_sha,
            eid,
            "statistical_numerical_consistency",
            "kernel_executed",
            None,
        )

    # Negative 3: even if a raw SQLite row carries a valid binding_hmac over noncanonical payload, export MUST downgrade
    conn = sqlite3.connect(str(db_file))
    try:
        conn.execute(
            """
            INSERT INTO artifact_execution_bindings
            (artifact_id, execution_id, verification_scope, provenance_tier, ingest_bound_claim_id, binding_hmac)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "art-forged-opposite",
                eid,
                "statistical_numerical_consistency",
                "kernel_executed",
                None,
                raw_bmac,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with ResearchStateDB(db_file, readonly=True, root=tmp_path) as ro_db:
        ceg = ro_db.export_ceg_dict()
    edge = [e for e in ceg["support_edges"] if e["claim_id"] == "c_forged"][0]
    assert edge["metadata"]["artifact_provenance_tier"] == "external_unverified"
    assert edge["metadata"]["unauthenticated_execution_binding"] is True


def test_stat_p_consistency_extreme_tail_logsf_prevents_float64_underflow_misclassification() -> None:
    """Extreme tails where float64 sf underflows to 0.0 use logsf/analytic bounds or return indeterminate."""
    from decimal import Decimal
    from academic_research_kernel.recompute import check_stat_p_consistency
    # 1. When scipy chi2.logsf is -inf (x=1500, df=2), return indeterminate (None) rather than guessing
    r_chi_indet = check_stat_p_consistency(
        "chi2", 1500.0, 2.0, reported_p=Decimal("1e-330"), stat_literal="1500.0", op="<"
    )
    assert r_chi_indet["consistent"] is None
    assert r_chi_indet["status"] == "indeterminate_underflow"

    # 2. Normal two-sided z where sf underflows to 0.0 but norm.logsf is finite: z=38.70 -> False; z=40.0 -> True
    r_true = check_stat_p_consistency(
        "z", 40.0, reported_p=Decimal("1e-330"), stat_literal="40.0", op="<"
    )
    assert r_true["consistent"] is True
    assert r_true["point_consistent"] is True
    assert r_true["status"] == "consistent_exact"

    # 3. Normal two-sided z=38.70: true p ~= 3.0e-327 > 1e-330 -> MUST be False
    r_z_false = check_stat_p_consistency(
        "z", 38.70, reported_p=Decimal("1e-330"), stat_literal="38.70", op="<"
    )
    assert r_z_false["consistent"] is False
    assert r_z_false["status"] == "inconsistent"

    # 4. Finite z=40.0 strictly has p > 0 mathematically -> op='>' against 0 MUST be True
    r_z_gt0 = check_stat_p_consistency(
        "z", 40.0, reported_p=Decimal("0"), stat_literal="40.0", op=">"
    )
    assert r_z_gt0["consistent"] is True
    assert r_z_gt0["point_consistent"] is True
    assert r_z_gt0["status"] == "consistent_exact"

    # 5. Deep t/F tails where scipy logsf is -inf return indeterminate (None) rather than guessing
    r_t_deep = check_stat_p_consistency(
        "t", 1e6, 2000.0, reported_p=Decimal("1e-9000"), stat_literal="1000000.0", op="<"
    )
    assert r_t_deep["consistent"] is None

    # 6. Knife-edge threshold within float64 log tolerance returns indeterminate (consistent=None), never a false guess
    from decimal import localcontext
    with localcontext() as ctx:
        ctx.prec = 80
        knife_p = Decimal(2) * Decimal("-753.4204447172699").exp()
    r_indet = check_stat_p_consistency(
        "z", 38.70, reported_p=knife_p, stat_decimals=30, op="<"
    )
    assert r_indet["consistent"] is None
    assert r_indet["status"] == "indeterminate_underflow"
    assert r_indet["confidence"] == "low"


def test_mcp_recompute_statistics_multi_test_conflict_and_indeterminate_aggregation() -> None:
    """Multi-test dual-p conflict preserves by_test summary shape, and None consistency is not coerced to False."""
    from decimal import Decimal, localcontext

    res_conf = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"t_stat": 2.0, "chi2_stat": 4.0, "df": 2.0, "p_value": 0.05, "p_value_literal": "0.01"},
    )
    assert res_conf["consistent"] is False
    assert set(res_conf["stat_p_consistency"]["by_test"].keys()) == {"t", "chi2"}
    assert res_conf["stat_p_consistency"]["consistent"] is False
    assert set(res_conf["p_match"]["by_test"].keys()) == {"t", "chi2"}
    assert res_conf["p_match"]["consistent"] is False

    with localcontext() as ctx:
        ctx.prec = 80
        knife_str = str((-Decimal("750")).exp())
    res_indet = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {
            "chi2_stat": 1500.0,
            "df": 2.0,
            "stat_decimals": 30,
            "p_operator": "<",
            "p_value_literal": knife_str,
        },
    )
    assert res_indet.get("consistent") is None


def test_round2_comprehensive_audit_blockers_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closes JSON-null binder leak, deep-tail F tiny-clamp inversion, upper p=1 rounding, and MCP tri-state propagation."""
    from decimal import Decimal
    from academic_research_kernel import state_db as sdb_mod
    from academic_research_kernel.recompute import check_stat_p_consistency

    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("ARK_EXECUTION_KEY_HEX", "44" * 32)
    db_file = tmp_path / "r2_blockers.sqlite3"

    # 1. JSON 'null' artifact row in SQLite and explicit payload=None MUST be rejected at signing/ingest
    ex_false = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"db_path": str(db_file), "t_stat": 2.0, "df": 10, "p_value": 0.001},
    )
    with pytest.raises(ValueError, match="JSON object|payload"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {
                "db_path": str(db_file),
                "artifact_id": "art-explicit-none",
                "kind": "quantitative_audit",
                "execution_id": ex_false["execution_id"],
                "payload": None,
            },
        )

    null_sha = sdb_mod.sha256_hex("null")
    conn = sqlite3.connect(str(db_file))
    try:
        cols_info = conn.execute("PRAGMA table_info(artifacts)").fetchall()
        cols = [r[1] for r in cols_info]
        sample = {
            "artifact_id": "art-raw-null",
            "kind": "quantitative_audit",
            "payload_json": "null",
            "payload_sha256": null_sha,
        }
        row_vals = [sample.get(c, "2026-01-01T00:00:00Z" if r[3] else None) for c, r in zip(cols, cols_info)]
        conn.execute(
            f"INSERT INTO artifacts ({','.join(cols)}) VALUES ({','.join(['?'] * len(cols))})",
            row_vals,
        )
        conn.commit()
    finally:
        conn.close()

    with ResearchStateDB(db_file, root=tmp_path) as db:
        with pytest.raises(ValueError, match="JSON object"):
            db.bind_artifact_execution(
                "art-raw-null", ex_false["execution_id"], "statistical_numerical_consistency"
            )

    # 2. Unsupported extreme df (df2=1e65 > 1e8, where SciPy 1.15 Cephes returns spurious 1.0) returns None (unknown)
    for f_val in (800.0, 810.0):
        r_f_dom = check_stat_p_consistency(
            "f", f_val, 2.0, 1e65, reported_p=Decimal("1e-348"), stat_literal=str(f_val), op="<"
        )
        assert r_f_dom["consistent"] is None
        assert r_f_dom["status"] == "indeterminate_underflow"

    # Within supported df domain, underflowing tail against ordinary bound (p < .001) resolves deterministically
    r_f_ord = check_stat_p_consistency("f", 810.0, 2.0, 1000.0, reported_p=Decimal("0.001"), op="<")
    assert r_f_ord["consistent"] is True

    # Upper p=1 boundary: z='1e-20' has interval [0.5e-20, 1.5e-20) strictly > 0 -> true p < 1 strictly
    r_z_lt1 = check_stat_p_consistency("z", "1e-20", reported_p=Decimal("1"), op="<")
    assert r_z_lt1["consistent"] is True
    assert r_z_lt1["status"] == "consistent_exact"

    # Flat MCP p_match agrees with deep-tail point verdict when float64 underflows to 0.0
    r_flat_zero = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"beta": 38.70, "se": 1.0, "p_value_literal": "0e-330"},
    )
    assert r_flat_zero["consistent"] is False
    assert r_flat_zero["p_match"]["consistent"] is False
    r_flat_indet = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"chi2_stat": 1500.0, "df": 2.0, "p_value_literal": "0e-330"},
    )
    assert r_flat_indet["consistent"] is None
    assert r_flat_indet["p_match"]["consistent"] is None

    # 3. Tri-state preservation in academic_table_forensics and sample_df through CEG export
    mcp_server.handle_tool_call(
        "claim_evidence_add",
        {"db_path": str(db_file), "claim_id": "c_bw", "claim_text": "Index uses 1 MB"},
    )
    tf_indet = mcp_server.handle_tool_call(
        "academic_table_forensics",
        {
            "db_path": str(db_file),
            "storage_bandwidth": {
                "item_count": 250000,
                "vector_dim": 1,
                "bytes_per_element": 4,
                "storage_unit": "MB",
                "reported_size_mb": 1,
            },
        },
    )
    assert tf_indet["storage_bandwidth_bounds"]["consistent"] is None
    assert tf_indet.get("consistent") is None

    mcp_server.handle_tool_call(
        "research_artifact_ingest",
        {
            "db_path": str(db_file),
            "artifact_id": "results-bw-indet",
            "kind": "quantitative_audit",
            "execution_id": tf_indet["execution_id"],
            "require_kernel_execution": True,
            "bindings": {"claim_id": "c_bw"},
        },
    )
    with ResearchStateDB(db_file, readonly=True, root=tmp_path) as ro_db:
        ceg = ro_db.export_ceg_dict()
    bw_edge = [e for e in ceg["support_edges"] if e["claim_id"] == "c_bw"][0]
    assert bw_edge["support_status"] == "unverifiable"
    assert bw_edge["metadata"]["artifact_provenance_tier"] == "kernel_executed"

    rs_mixed_indet = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"sample_df": 10.5, "reported_n": 12, "check_sd": 0, "scale_min": 0, "scale_max": 1},
    )
    assert rs_mixed_indet["sample_size_from_df"]["consistent"] is None
    assert rs_mixed_indet.get("consistent") is None

    rs_mixed_false = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {"sample_df": 10.5, "reported_n": 12, "check_sd": 5.0, "scale_min": 0, "scale_max": 1},
    )
    assert rs_mixed_false["consistent"] is False


def test_round3_minimal_closures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Closes imbalanced-beta F cancellation, near-1 threshold rounding, flat Wilson CI tri-state, and mixed-mode guards."""
    from decimal import Decimal
    from academic_research_kernel.recompute import check_stat_p_consistency

    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("ARK_EXECUTION_KEY_HEX", "66" * 32)
    db_file = tmp_path / "r3.sqlite3"

    # 1. Extreme dfs outside supported IEEE-754 domain return None (unknown) rather than false verdicts
    for args_dom in (
        ("f", 1e170, 1e130, 4, Decimal("1e-400")),
        ("f", "10.000", 2e150, 2000, Decimal("1e-590")),
        ("f", "1e-400", 2e-60, 2, Decimal("0.999999999995")),
    ):
        r_dom = check_stat_p_consistency(args_dom[0], args_dom[1], args_dom[2], args_dom[3], reported_p=args_dom[4], op="<")
        assert r_dom["consistent"] is None
    with pytest.raises(ValueError, match="requires 'kind'"):
        mcp_server.handle_tool_call(
            "academic_recompute_statistics",
            {"params": {"estimate": 3, "lower": 0, "upper": 2}, "check_sd": 0, "scale_min": 0, "scale_max": 1},
        )
    r_near1 = check_stat_p_consistency(
        "z", "1e-20", reported_p=Decimal("0.999999999999999999999"), op="<"
    )
    assert r_near1["consistent"] in (True, None)
    assert r_near1["consistent"] is not False

    # 3. Flat Wilson CI (consistent=None) + passing SD MUST yield top-level consistent=None -> unverifiable CEG edge
    mcp_server.handle_tool_call(
        "claim_evidence_add",
        {"db_path": str(db_file), "claim_id": "c_wilson", "claim_text": "Wilson interval holds"},
    )
    ex_w = mcp_server.handle_tool_call(
        "academic_recompute_statistics",
        {
            "db_path": str(db_file),
            "ci_estimate": 0.5,
            "ci_lower": 0.2,
            "ci_upper": 0.8,
            "ci_method": "wilson",
            "check_sd": 0,
            "scale_min": 0,
            "scale_max": 1,
        },
    )
    assert "consistent" in ex_w and ex_w["consistent"] is None
    mcp_server.handle_tool_call(
        "research_artifact_ingest",
        {
            "db_path": str(db_file),
            "artifact_id": "results-wilson",
            "kind": "quantitative_audit",
            "execution_id": ex_w["execution_id"],
            "require_kernel_execution": True,
            "bindings": {"claim_id": "c_wilson"},
        },
    )
    with ResearchStateDB(db_file, readonly=True, root=tmp_path) as ro_db:
        ceg = ro_db.export_ceg_dict()
    w_edge = [e for e in ceg["support_edges"] if e["claim_id"] == "c_wilson"][0]
    assert w_edge["support_status"] == "unverifiable"

    # 4. Mixed-mode guards reject ambiguous dual inputs
    with pytest.raises(ValueError, match="Cannot mix|mix"):
        mcp_server.handle_tool_call(
            "academic_recompute_statistics",
            {"kind": "ci", "params": {"estimate": 1, "lower": 0, "upper": 2}, "check_sd": 5, "scale_min": 0, "scale_max": 1},
        )
    with pytest.raises(ValueError, match="Cannot mix"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {"db_path": str(db_file), "envelope": {"artifact_id": "art-x"}, "payload": {}},
        )

    # 5. A1: Persistent file-backed receipt requires explicit ARK_EXECUTION_KEY_HEX and survives fresh child process;
    #    later caller-added edge on same claim is NOT marked bound_at_ingest=True.
    import json
    import os
    import subprocess
    import sys

    unkeyed_db = tmp_path / "unkeyed.sqlite3"
    monkeypatch.delenv("ARK_EXECUTION_KEY_HEX", raising=False)
    with pytest.raises(ValueError, match="ARK_EXECUTION_KEY_HEX"):
        mcp_server.handle_tool_call(
            "academic_check_percentage",
            {"db_path": str(unkeyed_db), "count": 4, "sample_size": 10, "percent": 40},
        )

    stable_key = "77" * 32
    monkeypatch.setenv("ARK_EXECUTION_KEY_HEX", stable_key)
    cross_db = tmp_path / "cross_proc.sqlite3"
    mcp_server.handle_tool_call(
        "claim_evidence_add",
        {"db_path": str(cross_db), "claim_id": "c_cross", "claim_text": "4/10 is 40 percent"},
    )
    ex_cp = mcp_server.handle_tool_call(
        "academic_check_percentage",
        {"db_path": str(cross_db), "count": 4, "sample_size": 10, "percent": 40},
    )
    mcp_server.handle_tool_call(
        "research_artifact_ingest",
        {
            "db_path": str(cross_db),
            "execution_id": ex_cp["execution_id"],
            "require_kernel_execution": True,
            "artifact_id": "results-pct-cp",
            "bindings": {"claim_id": "c_cross"},
        },
    )
    mcp_server.handle_tool_call(
        "claim_evidence_add",
        {
            "db_path": str(cross_db),
            "claim_id": "c_cross",
            "claim_text": "4/10 is 40 percent",
            "evidence": [["results-pct-cp", "contradicts", "later-added-location"]],
        },
    )
    src_dir = str(Path(__file__).resolve().parents[1] / "src")
    child_env = {**os.environ, "PYTHONPATH": src_dir, "ARK_EXECUTION_KEY_HEX": stable_key}
    child_code = (
        "import json, sys\n"
        "from academic_research_kernel.state_db import ResearchStateDB\n"
        "with ResearchStateDB(sys.argv[1], readonly=True) as db:\n"
        "    ke = db.get_kernel_execution(sys.argv[2])\n"
        "    ceg = db.export_ceg_dict()\n"
        "print(json.dumps({'ok': ke is not None, 'edges': ceg['support_edges']}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", child_code, str(cross_db), ex_cp["execution_id"]],
        env=child_env,
        capture_output=True,
        text=True,
        check=True,
    )
    child_out = json.loads(proc.stdout)
    assert child_out["ok"] is True
    by_status = {e["support_status"]: e["metadata"] for e in child_out["edges"]}
    assert by_status["supported"]["artifact_provenance_tier"] == "kernel_executed"
    assert by_status["supported"]["bound_at_ingest"] is True
    assert by_status["contradicted"]["bound_at_ingest"] is False

    # 6. A2: Non-exact high-Jaccard title (e.g. dropped negation 'not') MUST return None (uncheckable), never True
    neg_out = mcp_server.handle_tool_call(
        "academic_verify_source",
        {
            "identifier": "10.5555/independent-audit-fixture",
            "crossref_record": {
                "DOI": "10.5555/independent-audit-fixture",
                "title": ["Treatment does not improve survival in patients with advanced lung cancer"],
            },
            "cited_title": "Treatment does improve survival in patients with advanced lung cancer",
        },
    )
    assert neg_out["citation_metadata_match"] is None
    assert neg_out["consistent"] is None
    assert (
        neg_out["citation_check"]["per_source_evaluations"]["crossref"]["details"]["title"]["status"]
        == "uncheckable"
    )


def test_package_dependency_matrix_is_strictly_lower_triangular() -> None:
    """Axiomatic Design gate: package module graph (static AST + dynamic _MODULE_MAP) has 0 cycles and 0 upper-triangular edges."""
    import ast

    from academic_research_kernel import (
        double_blind_sanitizer,
        mcp_server,
        pre_submission_linter,
        state_db,
        venue_template_manager,
    )

    pkg_dir = Path(state_db.__file__).resolve().parent
    mod_map: dict[str, Path] = {}
    for py_file in sorted(pkg_dir.rglob("*.py")):
        rel = py_file.relative_to(pkg_dir.parent).with_suffix("")
        parts = list(rel.parts)
        mod_name = ".".join(parts[:-1]) if parts[-1] == "__init__" else ".".join(parts)
        mod_map[mod_name] = py_file

    deps: dict[str, set[str]] = {m: set() for m in mod_map}
    for m, py_file in mod_map.items():
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in mod_map and alias.name != m:
                        deps[m].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    cur_parts = m.split(".") if py_file.name == "__init__.py" else m.split(".")[:-1]
                    up = node.level - 1
                    base_parts = cur_parts[: len(cur_parts) - up] if up > 0 else cur_parts
                    if node.module:
                        cand = ".".join([*base_parts, node.module])
                        if cand in mod_map and cand != m:
                            deps[m].add(cand)
                    for alias in node.names:
                        cand2 = ".".join([*base_parts, *([node.module] if node.module else []), alias.name])
                        if cand2 in mod_map and cand2 != m:
                            deps[m].add(cand2)
                elif node.module:
                    if node.module in mod_map and node.module != m:
                        deps[m].add(node.module)
                    for alias in node.names:
                        cand2 = f"{node.module}.{alias.name}"
                        if cand2 in mod_map and cand2 != m:
                            deps[m].add(cand2)

    # Include dynamic importlib routing edges declared in mcp_server._MODULE_MAP
    for dyn_target in getattr(mcp_server, "_MODULE_MAP", {}).values():
        full_dyn = f"academic_research_kernel.{dyn_target}"
        if full_dyn in mod_map:
            deps["academic_research_kernel.mcp_server"].add(full_dyn)

    index_counter = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index_counter
        index[node] = index_counter
        lowlink[node] = index_counter
        index_counter += 1
        stack.append(node)
        on_stack.add(node)
        for succ in sorted(deps[node]):
            if succ not in index:
                strongconnect(succ)
                lowlink[node] = min(lowlink[node], lowlink[succ])
            elif succ in on_stack:
                lowlink[node] = min(lowlink[node], index[succ])
        if lowlink[node] == index[node]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == node:
                    break
            sccs.append(comp)

    for m in sorted(mod_map):
        if m not in index:
            strongconnect(m)

    nontrivial_sccs = [comp for comp in sccs if len(comp) > 1]
    assert nontrivial_sccs == [], f"Cyclic module SCCs detected: {nontrivial_sccs}"

    topo_order = [n for comp in sccs for n in comp]
    pos = {n: idx for idx, n in enumerate(topo_order)}
    upper_edges = [(u, v) for u, vs in deps.items() for v in sorted(vs) if pos[u] < pos[v]]
    assert upper_edges == [], f"Upper-triangular edges detected: {upper_edges}"

    # Verify backwards-compatible re-exports remain identical callable objects
    assert venue_template_manager.validate_ceg_semantics is state_db.validate_ceg_semantics
    assert pre_submission_linter.strip_tex_comments is double_blind_sanitizer.strip_tex_comments
