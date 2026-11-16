"""Regression tests closing all 18 findings (3 P0, 10 P1, 5 P2) from the 2bb0429 re-audit."""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import sqlite3
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from academic_research_kernel import (
    cross_review,
    locate_oa,
    mcp_server,
    meta_core,
    openreview_audit,
    pre_submission_linter,
    release_gate,
)
from academic_research_kernel._stdlib import canonical_json, nfc_compact, sha256_hex, thaw
from academic_research_kernel.state_db import (
    ResearchStateDB,
    validate_decision_ledger_semantics,
    validate_lineage_receipt_semantics,
)
from academic_research_kernel.venue_template_manager import validate_ceg_semantics

REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_wheel_from_source(dest: Path, *, mutate_files=None) -> Path:
    """Construct a valid synthetic wheel matching REPO_ROOT pyproject.toml, with optional mutation."""
    ver = "3.0.0"
    whl_path = dest / f"academic_research_kernel-{ver}-py3-none-any.whl"
    dist_info = f"academic_research_kernel-{ver}.dist-info"
    files: dict[str, bytes] = {}
    for src_f in sorted((REPO_ROOT / "src").rglob("*")):
        if src_f.is_file() and "__pycache__" not in src_f.parts and not src_f.name.endswith((".pyc", ".pyo")):
            rel = src_f.relative_to(REPO_ROOT / "src").as_posix()
            files[rel] = src_f.read_bytes()

    pyproj = release_gate._load_pyproject(REPO_ROOT)
    proj = pyproj["project"]
    metadata_lines = [
        "Metadata-Version: 2.4",
        "Name: academic-research-kernel",
        f"Version: {ver}",
        f"Requires-Python: {proj['requires-python']}",
        "License-Expression: LicenseRef-Source-Lineage-1.0",
    ]
    for dep in proj.get("dependencies") or []:
        metadata_lines.append(f"Requires-Dist: {dep}")
    for ext_k in sorted((proj.get("optional-dependencies") or {}).keys()):
        metadata_lines.append(f"Provides-Extra: {ext_k}")
        for dep in proj["optional-dependencies"][ext_k]:
            b_dep, sep_dep, m_dep = str(dep).partition(";")
            if sep_dep:
                metadata_lines.append(f"Requires-Dist: {b_dep.strip()}; ({m_dep.strip()}) and extra == '{ext_k}'")
            else:
                metadata_lines.append(f"Requires-Dist: {dep}; extra == '{ext_k}'")
    metadata_lines.append("")
    files[f"{dist_info}/METADATA"] = "\n".join(metadata_lines).encode("utf-8")
    files[f"{dist_info}/WHEEL"] = (
        b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    )
    files[f"{dist_info}/entry_points.txt"] = (
        b"[console_scripts]\nacademic-research-kernel = academic_research_kernel.cli:main\n"
    )
    for lic_rel in proj.get("license-files") or ():
        lic_norm = str(lic_rel).replace("\\", "/").lstrip("./")
        files[f"{dist_info}/licenses/{lic_norm}"] = (REPO_ROOT / lic_norm).read_bytes()

    if mutate_files is not None:
        mutate_files(files, dist_info)

    rec_lines: list[str] = []
    for k in sorted(files):
        if k == f"{dist_info}/RECORD":
            continue
        b = files[k]
        dg = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode("ascii").rstrip("=")
        rec_lines.append(f"{k},{dg},{len(b)}")
    rec_lines.append(f"{dist_info}/RECORD,,")
    files[f"{dist_info}/RECORD"] = ("\n".join(rec_lines) + "\n").encode("utf-8")

    with zipfile.ZipFile(whl_path, "w") as zf:
        for k, b in sorted(files.items()):
            zf.writestr(k, b)
    return whl_path


def _make_sdist_from_source(dest: Path, *, drop_rels: set[str] | None = None, pkg_info_extra: str = "") -> Path:
    ver = "3.0.0"
    sdist_path = dest / f"academic_research_kernel-{ver}.tar.gz"
    prefix = f"academic_research_kernel-{ver}"
    pyproj = release_gate._load_pyproject(REPO_ROOT)
    expected_rels = release_gate._expected_sdist_rels(REPO_ROOT, pyproj)
    drop = drop_rels or set()

    proj = pyproj["project"]
    pkg_info_lines = [
        "Metadata-Version: 2.4",
        "Name: academic-research-kernel",
        f"Version: {ver}",
        f"Requires-Python: {proj['requires-python']}",
        "License-Expression: LicenseRef-Source-Lineage-1.0",
    ]
    for dep in proj.get("dependencies") or []:
        pkg_info_lines.append(f"Requires-Dist: {dep}")
    for ext_k in sorted((proj.get("optional-dependencies") or {}).keys()):
        pkg_info_lines.append(f"Provides-Extra: {ext_k}")
        for dep in proj["optional-dependencies"][ext_k]:
            b_dep, sep_dep, m_dep = str(dep).partition(";")
            if sep_dep:
                pkg_info_lines.append(f"Requires-Dist: {b_dep.strip()}; ({m_dep.strip()}) and extra == '{ext_k}'")
            else:
                pkg_info_lines.append(f"Requires-Dist: {dep}; extra == '{ext_k}'")
    if pkg_info_extra:
        pkg_info_lines.append(pkg_info_extra)
    pkg_info_bytes = ("\n".join(pkg_info_lines) + "\n").encode("utf-8")

    with tarfile.open(sdist_path, "w:gz") as tf:
        ti_pi = tarfile.TarInfo(f"{prefix}/PKG-INFO")
        ti_pi.size = len(pkg_info_bytes)
        tf.addfile(ti_pi, io.BytesIO(pkg_info_bytes))
        for rel in sorted(expected_rels):
            if rel in drop or any(rel.startswith(d) for d in drop if d.endswith("/")):
                continue
            b = (REPO_ROOT / rel).read_bytes()
            ti = tarfile.TarInfo(f"{prefix}/{rel}")
            ti.size = len(b)
            tf.addfile(ti, io.BytesIO(b))
    return sdist_path


def _build_lineage_receipt(
    target_id: str,
    raw_bytes: bytes | None,
    *,
    verification_status: str = "intact",
    topology_status: str = "valid_dag",
    content_verification: str = "fully_verified",
    error_detail: str = "",
    check_on_disk_hashes: bool = True,
    edges: list[dict] | None = None,
    extra_entities: list[dict] | None = None,
    root_ancestors: list[str] | None = None,
) -> dict:
    ent: dict = {"id": target_id, "type": "data_snapshot"}
    if raw_bytes is not None:
        ent["sha256"] = sha256_hex(raw_bytes)
    entities = [ent, *(extra_entities or [])]
    body = {
        "protocol": "lineage-receipt-1.0",
        "target_id": target_id,
        "root_ancestors": [target_id] if root_ancestors is None else root_ancestors,
        "entities": entities,
        "activities": [],
        "edges": edges or [],
        "trace_steps": [],
    }
    ld = sha256_hex(canonical_json(body))
    rd = sha256_hex(
        canonical_json(
            {
                "lineage_digest": ld,
                "target_id": target_id,
                "verification_status": verification_status,
                "topology_status": topology_status,
                "content_verification": content_verification,
                "error_detail": error_detail,
                "check_on_disk_hashes": check_on_disk_hashes,
            }
        )
    )
    out = {
        **body,
        "lineage_digest": ld,
        "receipt_digest": rd,
        "receipt_id": "rec-" + rd[:32],
        "timestamp": "2026-11-15T00:00:00Z",
        "verification_status": verification_status,
        "topology_status": topology_status,
        "content_verification": content_verification,
    }
    if error_detail:
        out["error_detail"] = error_detail
    return out


def _run_offline_verify(*, peer_path: Path | None = None, inc_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    args: list[str] = []
    if peer_path is not None:
        args.append(f"peer_path=b.Path({str(peer_path)!r})")
    if inc_path is not None:
        args.append(f"inc_path=b.Path({str(inc_path)!r})")
    call_expr = f"b.verify_receipts_offline({', '.join(args)})"
    return subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, 'tools/benchmarks'); import run_peer_review_and_incidence_benchmarks as b; {call_expr}",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# R-P0-01: Release artifact binding (extras, markers, WHEEL tag, sdist assets)
# ---------------------------------------------------------------------------
def test_rp0_01_wheel_and_sdist_source_binding_rejects_tampering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    c_whl_dir = tmp_path / "c_whl"
    c_whl_dir.mkdir()
    ctrl_whl = _make_wheel_from_source(c_whl_dir)
    assert release_gate.inspect_artifact(ctrl_whl, "3.0.0", source_root=REPO_ROOT)["filename"].endswith(".whl")

    c_sd_dir = tmp_path / "c_sd"
    c_sd_dir.mkdir()
    ctrl_sd = _make_sdist_from_source(c_sd_dir)
    assert release_gate.inspect_artifact(ctrl_sd, "3.0.0", source_root=REPO_ROOT)["filename"].endswith(".tar.gz")

    def _strip_extras(files: dict[str, bytes], dist_info: str) -> None:
        lines = [ln for ln in files[f"{dist_info}/METADATA"].decode("utf-8").splitlines() if "extra ==" not in ln]
        files[f"{dist_info}/METADATA"] = ("\n".join(lines) + "\n").encode("utf-8")

    d1 = tmp_path / "m1"
    d1.mkdir()
    with pytest.raises(ValueError, match="extra"):
        release_gate.inspect_artifact(_make_wheel_from_source(d1, mutate_files=_strip_extras), "3.0.0", source_root=REPO_ROOT)

    def _add_extra_dep(files: dict[str, bytes], dist_info: str) -> None:
        raw = files[f"{dist_info}/METADATA"].decode("utf-8").rstrip("\n")
        files[f"{dist_info}/METADATA"] = (raw + "\nRequires-Dist: backdoor-pkg==9.9.9; extra == 'research'\n").encode("utf-8")

    d2 = tmp_path / "m2"
    d2.mkdir()
    with pytest.raises(ValueError, match="extra"):
        release_gate.inspect_artifact(_make_wheel_from_source(d2, mutate_files=_add_extra_dep), "3.0.0", source_root=REPO_ROOT)

    def _bad_tag(files: dict[str, bytes], dist_info: str) -> None:
        files[f"{dist_info}/WHEEL"] = files[f"{dist_info}/WHEEL"].replace(b"py3-none-any", b"cp312-cp312-linux_x86_64")

    d3 = tmp_path / "m3"
    d3.mkdir()
    with pytest.raises(ValueError, match="Tag"):
        release_gate.inspect_artifact(_make_wheel_from_source(d3, mutate_files=_bad_tag), "3.0.0", source_root=REPO_ROOT)

    d4 = tmp_path / "m4"
    d4.mkdir()
    with pytest.raises(ValueError, match="sdist"):
        release_gate.inspect_artifact(_make_sdist_from_source(d4, drop_rels={"skills/", "tests/"}), "3.0.0", source_root=REPO_ROOT)

    d5 = tmp_path / "m5"
    d5.mkdir()
    sdist_no_id = _make_sdist_from_source(d5, drop_rels={"REPOSITORY-IDENTITY.md"})
    with pytest.raises(ValueError, match="REPOSITORY-IDENTITY.md"):
        release_gate.inspect_artifact(sdist_no_id, "3.0.0", source_root=REPO_ROOT)
    with pytest.raises(ValueError, match="REPOSITORY-IDENTITY.md"):
        release_gate.inspect_artifact(sdist_no_id, "3.0.0", source_root=None)

    both_dir = tmp_path / "both"
    both_dir.mkdir()
    _make_wheel_from_source(both_dir)
    _make_sdist_from_source(both_dir)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="source_root"):
        release_gate.run_package_acceptance(both_dir, source_root=None, allow_unrooted=False)


# ---------------------------------------------------------------------------
# R-P0-02, R-P0-03 & R-P2-05: Strict verdict-document protocol, singleton guard, cache & envelope
# ---------------------------------------------------------------------------
def test_rp0_02_strict_verdict_protocol_and_singleton_fail_closed(tmp_path: Path) -> None:
    findings = {
        "a": [{"target": "x.py", "issue_key": "validation", "polarity": "valid", "severity": "P1", "claim": "valid", "evidence": ["x.py:1"]}],
        "b": [{"target": "x.py", "issue_key": "validation", "polarity": "invalid", "severity": "P1", "claim": "invalid", "evidence": ["x.py:1"]}],
        "c": [],
    }
    first = cross_review.deliberate_inline(findings)
    ch = first["challenge_plan"][0]

    for valid_verdict_doc in (
        "# Review\n\n[CONCEDE] Proposal-1: checked\n[REFUTED] Proposal-2: checked\n",
        "-    [CONCEDE] Proposal-1: checked\n-    [REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: `x.py:42` and ``code with ` tick``\r\n[REFUTED] Proposal-2: `x.py:43`",
    ):
        ok_res = cross_review.deliberate_inline(
            findings,
            challenge_replies={ch["challenge_id"]: {"text": valid_verdict_doc, "bundle_sha256": ch["bundle_sha256"]}},
        )
        assert ok_res["synthesis"]["convergence_status"] == "CONVERGED", valid_verdict_doc

    for non_verdict_text in (
        "Example template only:\n\n    [CONCEDE] Proposal-1: checked\n    [REFUTED] Proposal-2: checked\n",
        "Tab template:\n\n\t[CONCEDE] Proposal-1: checked\n\t[REFUTED] Proposal-2: checked\n",
        "Blockquote:\n> [CONCEDE] Proposal-1: checked\n> [REFUTED] Proposal-2: checked\n",
        "> quoted note\n- [CONCEDE] Proposal-1: checked\n- [REFUTED] Proposal-2: checked",
        "> # Heading\n[CONCEDE] Proposal-1: checked\n[REFUTED] Proposal-2: checked",
        "<!--\n[CONCEDE] Proposal-1: checked\n[REFUTED] Proposal-2: checked\n-->\nNo decision yet.",
        "```text\n[CONCEDE] Proposal-1: checked\n[REFUTED] Proposal-2: checked\n```\n",
        "   ```text\n[CONCEDE] Proposal-1: checked\n[REFUTED] Proposal-2: checked\n   ```",
        "- ```text\n  [CONCEDE] Proposal-1: checked\n  [REFUTED] Proposal-2: checked\n  ```",
        "-     [CONCEDE] Proposal-1: checked\n-     [REFUTED] Proposal-2: checked",
        "-[CONCEDE] Proposal-1: checked\n-[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: <!--rationale-->\n[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: [link](/u)\n[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: \\escaped\n[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: `unclosed\n[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: ```triple```\n[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: `[REFUTED]`\n[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: `Proposal-2`\n[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: checked\n[CONCEDE] Proposal-1: duplicate\n[REFUTED] Proposal-2: checked",
        "[CONCEDE] Proposal-1: checked\u2028[REFUTED] Proposal-2: checked",
    ):
        res = cross_review.deliberate_inline(
            findings,
            challenge_replies={ch["challenge_id"]: {"text": non_verdict_text, "bundle_sha256": ch["bundle_sha256"]}},
        )
        assert res["synthesis"]["convergence_status"] != "CONVERGED", non_verdict_text
        assert res["synthesis"]["receipt"]["convergence"]["unresolved_issues_count"] == 1

    # Singleton minority-evidence guard: conflicting or unscoped lines reject the whole reply and preserve ALL singleton claims
    real_f = tmp_path / "real_target.py"
    real_f.write_text("x = 1\n", encoding="utf-8")
    sing_findings = {
        "a": {
            "findings": [
                {"target": "real_target.py", "issue_key": "k", "severity": "P0", "claim": "Claim one", "evidence": [f"{real_f}:1"]},
                {"target": "real_target.py", "issue_key": "k", "severity": "P0", "claim": "Claim two", "evidence": [f"{real_f}:1"]},
            ]
        },
        "b": {"findings": []},
    }
    reg_s, chals_s, skip_s = cross_review.plan_challenges(["a", "b"], sing_findings, mode="standard", run_id="sing-guard")
    cid_s = chals_s[0]["challenge_id"]
    for bad_sing_reply in (
        "[REFUTED] Proposal-1: no\n[CONCEDE] Proposal-2: yes\n[REFUTED] Proposal-2: no",
        "[CONCEDE] unscoped line\n[REFUTED] Proposal-1: no",
        "Commentary prose\n[REFUTED] Proposal-1: no",
        "[REFUTED] Proposal-1: disproved\n【UNRESOLVED: [CONCEDE] Proposal-99】 Proposal-2: pending",
    ):
        syn_s = cross_review.synthesize_deliberation(reg_s, chals_s, {cid_s: bad_sing_reply}, skipped_challenges=skip_s, base_dirs=[tmp_path])
        assert syn_s["convergence_status"] != "CONVERGED", bad_sing_reply
        assert len(syn_s["unresolved_ledger"]) == 1
        assert len(syn_s["unresolved_ledger"][0]["claims"]) == 2

    with pytest.raises(ValueError, match="envelope"):
        cross_review.deliberate_inline(
            findings,
            challenge_replies={ch["challenge_id"]: "[CONCEDE] Proposal-1: ok\n[REFUTED] Proposal-2: no"},  # type: ignore[dict-item]
        )


def test_rp0_03_stale_challenge_cache_manifest_and_alias_tampering_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    findings = {
        "a": [{"target": "x.py", "issue_key": "validation", "polarity": "valid", "severity": "P1", "claim": "valid", "evidence": ["x.py:1"]}],
        "b": [{"target": "x.py", "issue_key": "validation", "polarity": "invalid", "severity": "P1", "claim": "invalid", "evidence": ["x.py:1"]}],
        "c": [],
    }
    good = "[CONCEDE] Proposal-1: checked\n[REFUTED] Proposal-2: checked"
    task = tmp_path / "task.md"
    stream = tmp_path / "stream"
    task.write_text("Task A: inspect x.py", encoding="utf-8")
    specs = [cross_review.ParticipantSpec(x, executor="mock") for x in findings]
    cross_review.stage_plan(stream, task, specs)
    for key, rows in findings.items():
        (stream / f"findings-{key}.json").write_text(json.dumps({"findings": rows}), encoding="utf-8")
    cross_review.stage_merge(stream, specs)
    worker = tmp_path / "worker.py"
    worker.write_text(f"import sys\nfrom pathlib import Path\nPath(sys.argv[1]).write_text({good!r})\n", encoding="utf-8")
    challengers = [
        cross_review.ParticipantSpec(x, executor="command", cmd=[sys.executable, str(worker), "{out_path}"])
        for x in findings
    ]
    cross_review.stage_challenge(stream, task, challengers)
    saved = {
        p.name: p.read_bytes()
        for p in stream.iterdir()
        if p.name == "challenge-plan.json" or p.name.startswith(("challenge-reply-", "challenge-meta-"))
    }

    task.write_text("Task B: inspect new.py", encoding="utf-8")
    cross_review.stage_plan(stream, task, specs)
    for key, rows in findings.items():
        (stream / f"findings-{key}.json").write_text(
            json.dumps({"findings": [{**row, "target": "new.py"} for row in rows]}), encoding="utf-8"
        )
    cross_review.stage_merge(stream, specs)
    for name, content in saved.items():
        (stream / name).write_bytes(content)
    with pytest.raises(ValueError, match="challenge-plan.json"):
        cross_review.stage_synthesize(stream)

    cross_review.stage_merge(stream, specs)
    cross_review.stage_challenge(stream, task, challengers)
    cp_orig = (stream / "challenge-plan.json").read_bytes()
    cp = json.loads(cp_orig.decode("utf-8"))
    cp[0]["bundle"]["target"] = "forged.py"
    (stream / "challenge-plan.json").write_text(json.dumps(cp), encoding="utf-8")
    with pytest.raises(ValueError, match="challenge-plan.json|bundle_sha256"):
        cross_review.stage_synthesize(stream)
    (stream / "challenge-plan.json").write_bytes(cp_orig)

    reg_orig = (stream / "issue-registry.json").read_bytes()
    reg_mut = json.loads(reg_orig.decode("utf-8"))
    reg_mut["contradictions"][0]["claims"][0]["claim"] = "mutated after challenge"
    (stream / "issue-registry.json").write_text(json.dumps(reg_mut), encoding="utf-8")
    with pytest.raises(ValueError, match="issue-registry.json|proposal"):
        cross_review.stage_synthesize(stream)
    (stream / "issue-registry.json").write_bytes(reg_orig)

    man_orig = json.loads((stream / "run-manifest.json").read_text(encoding="utf-8"))
    task.write_text("Task C: edited", encoding="utf-8")
    for del_k in ("task_path", "registry_sha256", "challenge_plan_sha256"):
        man_mut = copy.deepcopy(man_orig)
        man_mut.pop(del_k, None)
        (stream / "run-manifest.json").write_text(json.dumps(man_mut), encoding="utf-8")
        with pytest.raises(ValueError, match="run-manifest.json"):
            cross_review.stage_synthesize(stream)

    (stream / "run-manifest.json").unlink()
    with pytest.raises(FileNotFoundError, match="run-manifest.json"):
        cross_review.stage_synthesize(stream)

    reg, chals, skip = cross_review.plan_challenges(
        ["a", "b", "c"],
        {"a": {"findings": findings["a"]}, "b": {"findings": findings["b"]}, "c": {"findings": []}},
    )
    bad_ch_empty = copy.deepcopy(chals[0])
    bad_ch_empty["bundle"]["proposals"] = []
    bad_ch_empty["bundle_sha256"] = sha256_hex(canonical_json(bad_ch_empty["bundle"]))
    bad_ch_empty["proposal_map"] = {"proposal1": 999, "proposal2": -1}
    with pytest.raises(ValueError, match="bundle.proposals"):
        cross_review.synthesize_deliberation(
            reg, [bad_ch_empty], {bad_ch_empty["challenge_id"]: "[CONCEDE] Proposal-1: x\n[REFUTED] Proposal-2: y"}, skipped_challenges=skip
        )

    reg_s, chals_s, skip_s = cross_review.plan_challenges(["a", "b"], {"a": {"findings": findings["a"]}, "b": {"findings": []}})
    bad_ch_phantom = copy.deepcopy(chals_s[0])
    bad_ch_phantom["proposal_map"] = {"proposal1": 1, "proposal2": 1}
    with pytest.raises(ValueError, match="proposal_map"):
        cross_review.synthesize_deliberation(
            reg_s, [bad_ch_phantom], {bad_ch_phantom["challenge_id"]: "[REFUTED] Proposal-2: phantom"}, skipped_challenges=skip_s
        )

    bad_ch_shadow = copy.deepcopy(chals[0])
    bad_ch_shadow["bundle"]["proposals"][0]["proposal_id"] = "Proposal-1"
    bad_ch_shadow["bundle"]["proposals"][0]["source_alias"] = "Proposal-2"
    bad_ch_shadow["bundle"]["proposals"][1]["proposal_id"] = "Proposal-2"
    bad_ch_shadow["bundle"]["proposals"][1]["source_alias"] = "Proposal-1"
    bad_ch_shadow["bundle_sha256"] = sha256_hex(canonical_json(bad_ch_shadow["bundle"]))
    with pytest.raises(ValueError, match="source_alias"):
        cross_review.synthesize_deliberation(
            reg, [bad_ch_shadow], {bad_ch_shadow["challenge_id"]: "[CONCEDE] Proposal-1: x\n[REFUTED] Proposal-2: y"}, skipped_challenges=skip
        )

    der_ch = {
        "challenge_id": "C1",
        "reviewer": "c",
        "type": "derangement_peer",
        "target": "a",
        "proposal_map": {"proposal1": 1, "proposal2": 2},
        "bundle": {
            "proposals": [
                {"proposal_id": "Proposal-1", "source_alias": "Proposal-2", "claim": "1", "evidence": []},
                {"proposal_id": "Proposal-2", "source_alias": "Proposal-1", "claim": "2", "evidence": []},
            ]
        },
    }
    der_ch["bundle_sha256"] = sha256_hex(canonical_json(der_ch["bundle"]))
    with pytest.raises(ValueError, match="source_alias"):
        cross_review.synthesize_deliberation({}, [der_ch], {"C1": "[CONCEDE] Proposal-1: x\n[REFUTED] Proposal-2: y"})


# ---------------------------------------------------------------------------
# R-P1-01..04: SQLite state migration, lineage semantics, verdict enum, receipt_ref DB binding
# ---------------------------------------------------------------------------
def test_rp1_01_mixed_v3_database_backfills_per_decision_verdict_override(tmp_path: Path) -> None:
    db_file = tmp_path / "mixed_v3.sqlite3"
    with ResearchStateDB(db_file) as db:
        db.record_decision("a", "Route A", verdict="positive")
        db.record_decision("b", "Route B", verdict="positive")
        db.correct_decision_outcome("b", "inconclusive", "explicit correction on b")

    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "INSERT INTO decision_events(decision_id, new_state, reason, superseded_by_id, verdict_override) "
        "VALUES ('a', 'pruned', 'contradicted', NULL, 'negative')"
    )
    conn.execute("PRAGMA user_version = 3")
    conn.commit()
    conn.close()

    with ResearchStateDB(db_file) as migrated:
        receipt = thaw(migrated.export_decision_ledger_dict())
        by_id = {d["id"]: d for d in receipt["decisions"]}
        assert by_id["a"]["metadata"]["verdict"] == "negative"
        assert migrated.validate_decisions()["valid"] is True


def test_rp1_02_03_04_lineage_verdict_and_receipt_ref_admission_contracts(tmp_path: Path) -> None:
    with ResearchStateDB(tmp_path / "contracts.sqlite3") as db:
        bad_lineage = {
            "protocol": "lineage-receipt-1.0",
            "receipt_id": "rec-" + "0" * 32,
            "lineage_digest": "0" * 64,
            "receipt_digest": "0" * 64,
            "timestamp": "2026-11-15T00:00:00Z",
            "target_id": "ghost",
            "verification_status": "intact",
            "topology_status": "valid_dag",
            "content_verification": "fully_verified",
            "root_ancestors": [],
            "entities": [],
            "activities": [],
            "edges": [],
            "trace_steps": [],
        }
        assert validate_lineage_receipt_semantics(bad_lineage)
        with pytest.raises(ValueError, match="Lineage"):
            db.register_artifact("invented", "lineage_receipt", bad_lineage)

        rpc_schema_bypass = mcp_server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {
                    "name": "research_artifact_validate",
                    "arguments": {
                        "kind": "lineage_receipt",
                        "schema_name": "lineage-receipt.schema.json",
                        "payload": bad_lineage,
                        "content_payloads": {"t": "not-base64!"},
                    },
                },
            }
        )
        assert json.loads(rpc_schema_bypass["result"]["content"][0]["text"])["valid"] is False

        with ResearchStateDB() as seed_db:
            seed_db.record_decision("d1", "Decision 1", verdict="positive")
            doc = copy.deepcopy(thaw(seed_db.export_decision_ledger_dict()))
        doc["decisions"][0]["metadata"]["initial_verdict"] = "telepathically-verified"
        doc["decisions"][0]["metadata"]["verdict"] = "telepathically-verified"
        doc["verification_digest"] = sha256_hex(canonical_json(doc["verification_manifest"]))
        keys = ("protocol", "verification_digest", "verification_manifest", "decisions", "bases", "forks", "state_events", "corrections", "uncertainties")
        doc["ledger_digest"] = sha256_hex(canonical_json({k: doc[k] for k in keys}))
        doc["ledger_id"] = "dl-" + doc["ledger_digest"][:16]
        assert any("illegal" in e for e in validate_decision_ledger_semantics(doc))
        rpc = mcp_server.process_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "decision_ledger_validate", "arguments": {"ledger": doc}}}
        )
        assert json.loads(rpc["result"]["content"][0]["text"])["valid"] is False
        with pytest.raises(ValueError, match="illegal"):
            db.register_artifact("bad-verdict", "decision_ledger", doc)

        actual = thaw(db.register_artifact("existing-evidence", "source", {"actual": "payload"}))
        assert actual["payload_sha256"] != "0" * 64
        db.record_decision("basis", "Basis")
        db.record_decision("n", "Negative", entry_kind="negative_result", basis_decision_id="basis")
        forged_doc = copy.deepcopy(thaw(db.export_decision_ledger_dict()))
        forged_doc["uncertainties"] = []
        forged_doc["bases"][0]["receipt_ref"] = {
            "kind": "lineage",
            "schema_version": "lineage-receipt-1.0",
            "receipt_id": "existing-evidence",
            "receipt_digest": "0" * 64,
        }
        forged_doc["verification_manifest"] = {"existing-evidence": "0" * 64}
        forged_doc["verification_digest"] = sha256_hex(canonical_json(forged_doc["verification_manifest"]))
        forged_doc["ledger_digest"] = sha256_hex(canonical_json({k: forged_doc[k] for k in keys}))
        forged_doc["ledger_id"] = "dl-" + forged_doc["ledger_digest"][:16]
        with pytest.raises(ValueError, match="disagrees with stored DB artifact|payload_sha256"):
            db.register_artifact("forged-ledger", "decision_ledger", forged_doc)


def test_lineage_receipts_content_payloads_session_db_and_v24_empty_events(tmp_path: Path) -> None:
    cyc_rec = _build_lineage_receipt(
        "t",
        None,
        topology_status="cycle_detected",
        check_on_disk_hashes=False,
        root_ancestors=[],
        extra_entities=[{"id": "r", "type": "data_snapshot"}],
        edges=[
            {"type": "derived_from", "source_id": "t", "target_id": "r"},
            {"type": "derived_from", "source_id": "r", "target_id": "t"},
        ],
    )
    assert validate_lineage_receipt_semantics(cyc_rec)
    ok_rec = _build_lineage_receipt("t", b"expected")
    rd_ok = ok_rec["receipt_digest"]
    wrong_cp = {"t": base64.b64encode(b"wrong").decode("ascii")}

    with ResearchStateDB(tmp_path / "lin.sqlite3") as db:
        with pytest.raises(ValueError, match="Invalid lineage topology|Lineage"):
            db.register_artifact(cyc_rec["receipt_id"], "lineage_receipt", cyc_rec)

        db.register_artifact(ok_rec["receipt_id"], "lineage_receipt", ok_rec)
        db.record_decision("d_base", "Base")
        db.record_decision("n_res", "Neg", entry_kind="negative_result", basis_decision_id="d_base", artifact_id=ok_rec["receipt_id"])
        exported_dl = thaw(db.export_decision_ledger_dict())
        assert validate_decision_ledger_semantics(exported_dl, receipts={ok_rec["receipt_id"]: ok_rec}) == []
        assert db.register_artifact("dl-from-lineage", "decision_ledger", exported_dl)["artifact_id"] == "dl-from-lineage"
        with pytest.raises(ValueError, match="lineage|content"):
            db.register_artifact("dl-bad-cp", "decision_ledger", exported_dl, content_payloads=wrong_cp)

        ceg_ref = {
            "protocol": "claim-evidence-graph-1.0",
            "graph_id": "g-db-cp",
            "claims": [{"id": "c1", "text": "Result is 40%."}],
            "evidence_anchors": [
                {
                    "id": "e1",
                    "anchor_type": "evidence_receipt",
                    "locator": "p.1",
                    "receipt_ref": {"kind": "lineage", "schema_version": "lineage-receipt-1.0", "receipt_id": ok_rec["receipt_id"], "receipt_digest": rd_ok},
                }
            ],
            "support_edges": [{"evidence_id": "e1", "claim_id": "c1", "support_status": "supported"}],
            "claim_relations": [],
            "uncertainties": [],
        }
        sem_db_cp = validate_ceg_semantics(ceg_ref, content_payloads=wrong_cp, authoritative_artifacts=db.extract_authoritative_artifacts())
        assert sem_db_cp["semantic_errors"] and sem_db_cp["eligible_count"] == 0

        rpc_missing = mcp_server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {"name": "decision_ledger_validate", "arguments": {"ledger": exported_dl, "receipts": {"unrelated": {}}}},
            }
        )
        res_missing = json.loads(rpc_missing["result"]["content"][0]["text"])
        assert res_missing["valid"] is False and res_missing["verification_scope"] == "validation_failed"

        rpc_gen_val = mcp_server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "research_artifact_validate", "arguments": {"kind": "decision_ledger", "payload": exported_dl, "receipts": {"unrelated": {}}}},
            }
        )
        assert json.loads(rpc_gen_val["result"]["content"][0]["text"])["valid"] is False

        rref_ok = {"kind": "lineage", "schema_version": "lineage-receipt-1.0", "receipt_id": ok_rec["receipt_id"], "receipt_digest": rd_ok}
        rpc_wrong_bytes = mcp_server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {"name": "research_receipt_verify", "arguments": {"receipt_ref": rref_ok, "receipt_payload": ok_rec, "content_payloads": wrong_cp}},
            }
        )
        assert json.loads(rpc_wrong_bytes["result"]["content"][0]["text"])["valid"] is False

        rpc_bad_b64 = mcp_server.process_message(
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {"name": "research_receipt_verify", "arguments": {"receipt_ref": rref_ok, "receipt_payload": ok_rec, "content_payloads": {"t": "not-base64!"}}},
            }
        )
        assert rpc_bad_b64["result"]["isError"] is True

    v24_doc = {
        "protocol": "decision-ledger-1.0",
        "ledger_id": "legacy",
        "ledger_digest": "1f4097f8deac0e6def6d9e65293030eb0d3e64396e27144618cd41b6bb4c69a0",
        "verification_digest": "1dc0d5b76163abaf09eea248b0db91ebd97bc19102727acc87d6d390ea90bad1",
        "verification_manifest": {},
        "decisions": [
            {
                "id": "d1",
                "title": "Explore route",
                "normalized_title": "Explore route",
                "entry_kind": "decision",
                "decision_digest": "59e0c9649d02c401bde3d1674e457a3241bf9888a312fc2cf1a9a4659d625543",
                "decision_action": "explore",
                "decision_type": "explore",
            }
        ],
        "bases": [],
        "forks": [],
        "state_events": [],
        "corrections": [],
        "uncertainties": [],
    }
    assert validate_decision_ledger_semantics(v24_doc) == []

    hm_rec = _build_lineage_receipt(
        "t",
        b"expected",
        verification_status="hash_mismatch",
        content_verification="hash_mismatch",
        error_detail="mismatch",
        root_ancestors=[],
    )
    ceg_hm = {
        "protocol": "claim-evidence-graph-1.0",
        "graph_id": "g-hm",
        "claims": [{"id": "c1", "text": "Result is 40%."}],
        "evidence_anchors": [
            {
                "id": "e1",
                "anchor_type": "evidence_receipt",
                "locator": "p.1",
                "receipt_ref": {"kind": "lineage", "schema_version": "lineage-receipt-1.0", "receipt_id": hm_rec["receipt_id"], "receipt_digest": hm_rec["receipt_digest"]},
            }
        ],
        "support_edges": [{"evidence_id": "e1", "claim_id": "c1", "support_status": "supported"}],
        "claim_relations": [],
        "uncertainties": [],
    }
    assert validate_ceg_semantics(ceg_hm, receipts={hm_rec["receipt_id"]: hm_rec})["eligible_count"] == 0

    mcp_server.reset_session_db()
    sess_db = mcp_server.get_session_db()
    raw_doc = {"text": "expected"}
    raw_sha = sha256_hex(canonical_json(raw_doc))
    sess_db.register_artifact("raw-mem", "source", raw_doc)
    ceg_mem = {
        "protocol": "claim-evidence-graph-1.0",
        "graph_id": "ceg-mem",
        "claims": [{"id": "c1", "text": "Result is 40%.", "normalized_text": "Result is 40%.", "claim_type": "generic_claim", "claim_digest": sha256_hex("Result is 40%.")}],
        "evidence_anchors": [
            {"id": "e1", "anchor_type": "evidence_receipt", "locator": "p.1", "receipt_ref": {"kind": "lineage", "schema_version": "lineage-receipt-1.0", "receipt_id": "raw-mem", "receipt_digest": raw_sha}}
        ],
        "support_edges": [{"evidence_id": "e1", "claim_id": "c1", "support_status": "supported"}],
        "claim_relations": [],
        "uncertainties": [],
    }
    ceg_mem["graph_digest"] = sha256_hex(canonical_json({k: v for k, v in ceg_mem.items() if k not in ("graph_id", "graph_digest")}))
    ceg_mem["graph_id"] = "ceg-" + ceg_mem["graph_digest"][:16]
    rpc_mem = mcp_server.process_message(
        {
            "jsonrpc": "2.0",
            "id": 22,
            "method": "tools/call",
            "params": {
                "name": "research_artifact_validate",
                "arguments": {
                    "kind": "claim_evidence_graph",
                    "schema_name": "claim-evidence-graph.schema.json",
                    "payload": ceg_mem,
                    "db_path": ":memory:",
                    "content_payloads": {"raw-mem": base64.b64encode(b"wrong").decode("ascii")},
                },
            },
        }
    )
    assert json.loads(rpc_mem["result"]["content"][0]["text"])["valid"] is False

    r1_m, r2_m = _build_lineage_receipt("t1", b"one"), _build_lineage_receipt("t2", b"two")
    with ResearchStateDB(tmp_path / "multi_lin.sqlite3") as db_m:
        db_m.register_artifact(r1_m["receipt_id"], "lineage_receipt", r1_m)
        db_m.register_artifact(r2_m["receipt_id"], "lineage_receipt", r2_m)
        ceg_multi = {
            "protocol": "claim-evidence-graph-1.0",
            "graph_id": "g-multi",
            "claims": [{"id": "c1", "text": "Result is 40%.", "normalized_text": "Result is 40%.", "claim_type": "generic_claim", "claim_digest": sha256_hex("Result is 40%.")}],
            "evidence_anchors": [
                {"id": "e1", "anchor_type": "evidence_receipt", "locator": "p.1", "receipt_ref": {"kind": "lineage", "schema_version": "lineage-receipt-1.0", "receipt_id": r1_m["receipt_id"], "receipt_digest": r1_m["receipt_digest"]}},
                {"id": "e2", "anchor_type": "evidence_receipt", "locator": "p.2", "receipt_ref": {"kind": "lineage", "schema_version": "lineage-receipt-1.0", "receipt_id": r2_m["receipt_id"], "receipt_digest": r2_m["receipt_digest"]}},
            ],
            "support_edges": [
                {"evidence_id": "e1", "claim_id": "c1", "support_status": "supported"},
                {"evidence_id": "e2", "claim_id": "c1", "support_status": "supported"},
            ],
            "claim_relations": [],
            "uncertainties": [],
        }
        ceg_multi["graph_digest"] = sha256_hex(canonical_json({k: v for k, v in ceg_multi.items() if k not in ("graph_id", "graph_digest")}))
        ceg_multi["graph_id"] = "ceg-" + ceg_multi["graph_digest"][:16]
        cp_both = {"t1": base64.b64encode(b"one").decode("ascii"), "t2": base64.b64encode(b"two").decode("ascii")}
        assert db_m.register_artifact("ceg-multi-ok", "claim_evidence_graph", ceg_multi, content_payloads=cp_both)["status"] == "accepted"
        with pytest.raises(ValueError, match="unknown"):
            db_m.register_artifact("ceg-multi-ghost", "claim_evidence_graph", ceg_multi, content_payloads={**cp_both, "ghost": base64.b64encode(b"x").decode("ascii")})
        with pytest.raises(ValueError, match="unknown"):
            db_m.register_artifact(
                "ceg-rec-id-cp",
                "claim_evidence_graph",
                ceg_multi,
                content_payloads={"t1": base64.b64encode(b"one").decode("ascii"), r1_m["receipt_id"]: base64.b64encode(b"wrong").decode("ascii")},
            )

    ws_lin = copy.deepcopy(r1_m)
    ws_lin["entities"][0]["id"] = " t1 "
    assert validate_lineage_receipt_semantics(ws_lin)


# ---------------------------------------------------------------------------
# R-P1-05 & R-P1-06: TeX CEG normalization, role/direction/operator checks & recursive asset containment
# ---------------------------------------------------------------------------
def test_rp1_05_06_tex_ceg_normalization_and_recursive_asset_containment(tmp_path: Path) -> None:
    ms = tmp_path / "ms"
    ms.mkdir()
    cases = [
        ("cite", "Latency decreases by 40%.", r"Latency decreases by 40\%.\cite{ref1}", True, True),
        ("ref", "Latency decreases by 40%.", r"Latency decreases by 40\%.\ref{tab:results}", True, True),
        ("math", "Latency is 40 milliseconds.", r"Latency is $40\,\mathrm{ms}$.", True, True),
        ("nested", "Latency decreases by 40%.", r"\textbf{\emph{\textit{Latency decreases by 40\%.}}}", True, True),
        ("role_reversal", "Drug A reduces mortality by 40% compared with Drug B.", r"Drug B reduces mortality by 40\% compared with Drug A.", False, False),
    ]
    for name, claim, line, strict, expect_ok in cases:
        with ResearchStateDB() as db:
            db.register_artifact("e", "source", {"text": claim})
            db.add_claim("c", claim, evidence=[("e", "supports", "line 1")])
            graph = thaw(db.export_ceg_dict())
        ceg_p = ms / f"ceg_{name}.json"
        ceg_p.write_text(json.dumps(graph), encoding="utf-8")
        tex_p = ms / f"{name}.tex"
        tex_p.write_text(
            "\\documentclass{article}\n\\begin{document}\n"
            "\\begin{abstract}Test.\\end{abstract}\n"
            "\\label{tab:results}\n" + line + " % ark:claim=c\n"
            "\\begin{thebibliography}{1}\\bibitem{ref1} Ref.\\end{thebibliography}\n"
            "\\end{document}\n",
            encoding="utf-8",
        )
        rep = thaw(
            pre_submission_linter.lint_manuscript(
                tex_p, venue=None, double_blind=False, ceg_path=ceg_p, require_ceg_binding=strict
            )
        )
        has_mismatch = any(x["code"] == "CEG_CLAIM_TEXT_MISMATCH" for x in rep["findings"])
        if expect_ok:
            assert rep["passed"] is True and not has_mismatch, (name, rep)
        else:
            assert has_mismatch is True, (name, rep)

    with ResearchStateDB() as db:
        db.register_artifact("e1", "source", {"text": "Latency is 40 milliseconds."})
        db.add_claim("c1", "Latency is 40 milliseconds.", evidence=[("e1", "supports", "l1")])
        db.add_claim("c2", "Drug A increases survival and decreases mortality by 40%.", evidence=[("e1", "supports", "l2")])
        ceg_doc = thaw(db.export_ceg_dict())
    ceg_p = ms / "ceg_extra.json"
    ceg_p.write_text(json.dumps(ceg_doc), encoding="utf-8")

    sqrt_tex = ms / "sqrt.tex"
    sqrt_tex.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\begin{abstract}Test.\\end{abstract}\n"
        r"Latency is $\sqrt{40}\,\mathrm{ms}$. % ark:claim=c1" + "\n\\end{document}\n",
        encoding="utf-8",
    )
    rep_sqrt = thaw(pre_submission_linter.lint_manuscript(sqrt_tex, venue=None, double_blind=False, ceg_path=ceg_p, require_ceg_binding=True))
    assert any(f["code"] == "CEG_CLAIM_TEXT_MISMATCH" for f in rep_sqrt["findings"])

    dir_swap_tex = ms / "dir_swap.tex"
    dir_swap_tex.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\begin{abstract}Test.\\end{abstract}\n"
        r"Drug A decreases survival and increases mortality by 40\%. % ark:claim=c2" + "\n\\end{document}\n",
        encoding="utf-8",
    )
    rep_dir = thaw(pre_submission_linter.lint_manuscript(dir_swap_tex, venue=None, double_blind=False, ceg_path=ceg_p, require_ceg_binding=False))
    assert any(f["code"] == "CEG_CLAIM_TEXT_MISMATCH" for f in rep_dir["findings"])

    assert pre_submission_linter._statement_diverges_from_claim("Accuracy is >40%.", r"Accuracy is $<40\%$.", strict=False) is True
    assert pre_submission_linter._statement_diverges_from_claim("Drug A increases survival by 40%.", "Drug A increases survival to 40%.", strict=False) is True
    assert pre_submission_linter._statement_diverges_from_claim("Accuracy is 40%.", r"Accuracy is $\approx 40\%$.", strict=False) is True
    assert pre_submission_linter._statement_diverges_from_claim("Accuracy is 40%.", r"Accuracy is $\sim 40\%$.", strict=False) is True

    outside = tmp_path / "outside.py"
    outside.write_text("outside_fixture = True\n", encoding="utf-8")
    for idx, esc_macro in enumerate(
        (
            r"\verbatiminput{../outside.py}",
            r"\lstinputlisting[language=Python]{../outside.py}",
            r"\includegraphics{../outside.py}",
            r"\import{../}{outside.py}",
        )
    ):
        esc_p = ms / f"esc_{idx}.tex"
        esc_p.write_text(
            "\\documentclass{article}\n\\begin{document}\n\\begin{abstract}Test.\\end{abstract}\n"
            + esc_macro
            + "\n\\end{document}\n",
            encoding="utf-8",
        )
        rep_esc = thaw(pre_submission_linter.lint_manuscript(esc_p, venue=None, double_blind=False))
        assert rep_esc["passed"] is False
        assert any(f["code"] == "UNSAFE_INCLUDE_PATH" for f in rep_esc["findings"])

    (ms / "chapter.tex").write_text(r"\verbatiminput{../outside.py}" + "\n", encoding="utf-8")
    for idx, wrapper in enumerate((r"\subfile{chapter.tex}", r"\import{./}{chapter.tex}")):
        main_p = ms / f"main_{idx}.tex"
        main_p.write_text(
            "\\documentclass{article}\n\\begin{document}\n\\begin{abstract}Test.\\end{abstract}\n"
            + wrapper
            + "\n\\end{document}\n",
            encoding="utf-8",
        )
        rep_sub = thaw(pre_submission_linter.lint_manuscript(main_p, venue=None, double_blind=False))
        assert rep_sub["passed"] is False
        assert any(f["code"] == "UNSAFE_INCLUDE_PATH" for f in rep_sub["findings"])


# ---------------------------------------------------------------------------
# R-P1-07 & R-P2-01: Cancellation-free subgroup Q_between and meta-regression overflow
# ---------------------------------------------------------------------------
def test_rp1_07_and_rp2_01_subgroup_q_and_meta_regression_overflow() -> None:
    sub = meta_core.subgroup_analysis(
        [-1e9, 1e9, -1e9 + 3.0, 1e9 + 3.0],
        [1.0, 1.0, 1.0, 1.0],
        ["a", "a", "b", "b"],
    )
    assert sub["q_between"] == pytest.approx(9.0, rel=1e-12)
    assert sub["p_between"] == pytest.approx(0.0026997960632601883, rel=1e-9)

    with pytest.raises(ValueError, match="overflow|degenerate"):
        meta_core.meta_regression([-1e308, 0.0, 1e308], [5e-324, 5e-324, 5e-324], [-1.0, 0.0, 1.0])


# ---------------------------------------------------------------------------
# R-P1-08, R-P2-02 & R-P2-03: OpenReview zero-score parity, discussion denominator & Comment filtering
# ---------------------------------------------------------------------------
def test_rp1_08_rp2_02_rp2_03_openreview_entry_parity_and_official_filtering() -> None:
    rec = {"id": "p1", "rating": "0;0;2", "replies_avg": [3]}
    single = openreview_audit.parse_mirror_record(rec)
    summary = openreview_audit.summarize_venue_mirror([rec])
    assert single["review_count"] == 1
    assert single["observed_review_notes"] == 3
    assert single["mean_rating"] == pytest.approx(2.0)
    assert summary["total_reviews"] == 1
    assert summary["overall_mean_rating"] == pytest.approx(2.0)
    assert summary["non_positive_rating_anomalies"] == {"count": 2, "submissions_affected": 1}
    assert summary["review_forensics"]["zero_discussion_beyond_reviews_share"] == pytest.approx(1.0)

    notes = [
        {"id": "p", "forum": "p", "content": {"title": "Paper"}},
        {"id": "r", "forum": "p", "invitation": "Conf/Official_Review", "content": {"rating": 6}},
        {"id": "c", "forum": "p", "invitation": "Conf/Comment", "content": {"rating": 10}},
    ]
    forum_res = openreview_audit.parse_openreview_notes({"notes": notes}, forum_id="p")
    assert forum_res["review_count"] == 1
    assert forum_res["mean_rating"] == pytest.approx(6.0)


# ---------------------------------------------------------------------------
# R-P1-09: Positive-first offline receipt verification & subtable/digest tamper gates
# ---------------------------------------------------------------------------
def test_rp1_09_positive_receipts_and_subtable_tampering_rejected_offline(tmp_path: Path) -> None:
    if not (REPO_ROOT / "docs" / "benchmarks").is_dir() or not (REPO_ROOT / "tools" / "benchmarks").is_dir():
        pytest.skip("Repository-only benchmark receipt verification skipped in unpacked sdist")
    pos = _run_offline_verify()
    assert pos.returncode == 0, (pos.stdout, pos.stderr)

    peer_orig = json.loads((REPO_ROOT / "docs" / "benchmarks" / "peer-review-forensics-2025-2027-v1.json").read_text(encoding="utf-8"))
    peer_no_sha = {k: v for k, v in peer_orig.items() if k != "receipt_sha256"}
    bad_peer_p = tmp_path / "peer_no_sha.json"
    bad_peer_p.write_text(json.dumps(peer_no_sha), encoding="utf-8")
    proc_peer = _run_offline_verify(peer_path=bad_peer_p)
    assert proc_peer.returncode != 0 and "peer-review receipt_sha256" in proc_peer.stderr

    inc_orig = json.loads((REPO_ROOT / "docs" / "benchmarks" / "iclr2026-openreview-incidence-receipt.json").read_text(encoding="utf-8"))

    def _write_rehashed_inc(name: str, mutator) -> subprocess.CompletedProcess[str]:
        tampered = copy.deepcopy(inc_orig)
        mutator(tampered)
        body = {k: v for k, v in tampered.items() if k != "receipt_sha256"}
        tampered["receipt_sha256"] = sha256_hex(canonical_json(body))
        out_p = tmp_path / f"{name}.json"
        out_p.write_text(json.dumps(tampered), encoding="utf-8")
        return _run_offline_verify(inc_path=out_p)

    def _mut_subtable(d: dict) -> None:
        d["tiers"]["Oral"]["hit_any"]["k"] = 0
        d["tiers"]["Poster"]["hit_any"]["k"] += inc_orig["tiers"]["Oral"]["hit_any"]["k"]
        d["tiers"]["Oral"]["hit_dispersion"]["k"] = 999999

    p_sub = _write_rehashed_inc("subtable", _mut_subtable)
    assert p_sub.returncode != 0 and ("hit_dispersion" in p_sub.stderr or "hit_any" in p_sub.stderr)

    def _mut_bool_count(d: dict) -> None:
        d["tiers"]["Oral"]["hit_format"]["k"] = True

    p_bool = _write_rehashed_inc("bool_k", _mut_bool_count)
    assert p_bool.returncode != 0 and "integer" in p_bool.stderr

    p_flt = _write_rehashed_inc(
        "float_k",
        lambda d: d["split_half"]["split_0"]["Oral"]["hit_format"].__setitem__(
            "k", float(d["split_half"]["split_0"]["Oral"]["hit_format"]["k"]) + 0.9
        ),
    )
    assert p_flt.returncode != 0 and "integer" in p_flt.stderr

    p_mean = _write_rehashed_inc("neg_mean", lambda d: d["tiers"]["Oral"].__setitem__("mean_rating", -999.0))
    assert p_mean.returncode != 0 and "mean_rating" in p_mean.stderr

    p_pc = _write_rehashed_inc("pc_float", lambda d: d["partition_conservation"].__setitem__("total_scored_manuscripts", 19473.9))
    assert p_pc.returncode != 0 and "integer" in p_pc.stderr

    p_id = _write_rehashed_inc(
        "pc_id",
        lambda d: d["partition_conservation"]["decision_partition_identities"].__setitem__("224 + 5134 + 8453 + 4980", -1),
    )
    assert p_id.returncode != 0 and "decision_partition_identities" in p_id.stderr


# ---------------------------------------------------------------------------
# R-P1-10 & R-P2-04: Legacy v2.4 MCP compat & strict OA DOI identity
# ---------------------------------------------------------------------------
def test_rp1_10_and_rp2_04_legacy_mcp_contracts_and_strict_oa_doi() -> None:
    rpc_pow = mcp_server.process_message(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "academic_recompute_statistics", "arguments": {"effect_size_d": 0.5, "alpha": 0.05, "target_power": 0.8}}}
    )
    r_pow = json.loads(rpc_pow["result"]["content"][0]["text"])
    assert r_pow["required_sample_size"] == r_pow["required_n"]
    assert r_pow["required_n"]["recomputed"] == pytest.approx(63.7656, rel=1e-4)

    legacy_claim_text = "Method improves accuracy by 5%."
    v2_cd = sha256_hex(
        canonical_json({"claim_type": "empirical_finding", "locator": "p.1", "target_work_id": "doi:10.1000/xyz", "text": nfc_compact(legacy_claim_text)})
    )
    legacy_ceg = {
        "protocol": "claim-evidence-graph-1.0",
        "graph_id": "g-legacy",
        "claims": [
            {
                "id": "clm-1",
                "text": legacy_claim_text,
                "normalized_text": nfc_compact(legacy_claim_text),
                "claim_type": "empirical_finding",
                "target_work_id": "doi:10.1000/xyz",
                "locator": "p.1",
                "claim_digest": v2_cd,
                "metadata": {},
            }
        ],
        "evidence_anchors": [],
        "support_edges": [],
        "claim_relations": [],
        "uncertainties": [],
    }
    legacy_ceg["graph_digest"] = sha256_hex(
        canonical_json({k: v for k, v in legacy_ceg.items() if k != "graph_digest"})
    )
    assert validate_ceg_semantics(legacy_ceg)["semantic_errors"] == []
    rpc_val = mcp_server.process_message(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "claim_evidence_validate", "arguments": {"graph": legacy_ceg}}}
    )
    assert rpc_val["result"]["isError"] is False and json.loads(rpc_val["result"]["content"][0]["text"])["valid"] is True

    rpc_tr = mcp_server.process_message(
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "claim_evidence_trace", "arguments": {"graph": legacy_ceg, "claim_id": "clm-1"}}}
    )
    assert rpc_tr["result"]["isError"] is False and json.loads(rpc_tr["result"]["content"][0]["text"])["claim"]["id"] == "clm-1"

    doi = "10.1000/test"
    ident = {"type": "doi", "value": doi, "normalized": doi}
    rc_oa, rep_oa = locate_oa._build_openalex_report(doi, {"open_access": {"is_oa": True, "oa_url": "https://example.org/a.pdf"}}, "api")
    assert rc_oa == 1 and rep_oa["status"] == "failed" and rep_oa["mismatch"] is True
    with mock.patch.object(locate_oa, "live_unpaywall", return_value={"is_oa": True, "best_oa_location": {"url_for_pdf": "https://example.org/a.pdf"}}):
        rc_upw, rep_upw = locate_oa.resolve_oa(ident, email="audit@example.org", fallback_all=False)
    assert rc_upw == 1 and rep_upw["status"] == "failed" and rep_upw["is_oa"] is False


def test_cross_audit_closure_regressions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from academic_research_kernel import cross_review, release_gate
    from academic_research_kernel.state_db import canonical_evidence_claim_digest

    # 1. Smuggled stance/proposal inside fullwidth UNRESOLVED detail must fail closed
    smuggled = "[REFUTED] Proposal-1: disproved\n【UNRESOLVED: [CONCEDE] Proposal-99】 Proposal-2: pending"
    parsed_smug = cross_review._parse_structured_stances(smuggled, {"proposal1", "proposal2"})
    assert parsed_smug["conflicting_line"] is True and parsed_smug["invalid_refs"]

    # 2. Schema-invalid AcademicEvidence payload rejected across MCP, CEG, and DecisionLedger
    bad_ev = {"schema_version": "1.0", "claims": [{}]}
    bad_ev_sha = sha256_hex(canonical_json(bad_ev))
    bad_ev_cd = canonical_evidence_claim_digest({})
    bad_ev_ref = {"kind": "academic_evidence", "schema_version": "1.0", "claim_digest": bad_ev_cd, "payload_sha256": bad_ev_sha}
    res_bad_ae = mcp_server.handle_tool_call("research_receipt_verify", {"receipt_ref": bad_ev_ref, "receipt_payload": bad_ev})
    assert res_bad_ae["valid"] is False and res_bad_ae["errors"]

    valid_ev = {
        "schema_version": "1.0",
        "claims": [{"claim": "Effect holds", "evidence_type": "metadata", "source": "Crossref", "support_status": "supported"}],
    }
    valid_ev_sha = sha256_hex(canonical_json(valid_ev))
    valid_ev_cd = canonical_evidence_claim_digest(valid_ev["claims"][0])
    valid_ev_ref = {"kind": "academic_evidence", "schema_version": "1.0", "claim_digest": valid_ev_cd, "payload_sha256": valid_ev_sha}
    assert mcp_server.handle_tool_call("research_receipt_verify", {"receipt_ref": valid_ev_ref, "receipt_payload": valid_ev})["valid"] is True

    with ResearchStateDB() as db_ae:
        db_ae.register_artifact("fake-src", "source", {"claims": [{}]})
        db_ae.add_claim("c1", "Claim 1", None, [("fake-src", "supports", "p.1")])
        ceg_forged = thaw(db_ae.export_ceg_dict())
        ceg_forged["evidence_anchors"][0]["receipt_ref"] = {
            "kind": "academic_evidence",
            "schema_version": "1.0",
            "claim_digest": bad_ev_cd,
            "payload_sha256": sha256_hex(canonical_json({"claims": [{}]})),
        }
        ceg_forged["graph_digest"] = sha256_hex(canonical_json({k: v for k, v in ceg_forged.items() if k != "graph_digest"}))
        sem_forged = validate_ceg_semantics(ceg_forged, authoritative_artifacts=db_ae.extract_authoritative_artifacts())
        assert sem_forged["semantic_errors"] and sem_forged["eligible_count"] == 0
        with pytest.raises(ValueError, match="academic_evidence"):
            db_ae.register_artifact("bad-ceg", "claim_evidence_graph", ceg_forged)

    # 3. Unknown ReceiptRef kind or invalid lineage schema_version rejected
    assert mcp_server.handle_tool_call(
        "research_receipt_verify",
        {"receipt_ref": {"kind": "unknown", "receipt_digest": sha256_hex(canonical_json({}))}, "receipt_payload": {}},
    )["valid"] is False
    ok_lin = _build_lineage_receipt("t", b"valid")
    assert mcp_server.handle_tool_call(
        "research_receipt_verify",
        {
            "receipt_ref": {"kind": "lineage", "schema_version": "invalid", "receipt_id": ok_lin["receipt_id"], "receipt_digest": ok_lin["receipt_digest"]},
            "receipt_payload": ok_lin,
        },
    )["valid"] is False

    # 4. Dangling trace_steps rejected in validate_lineage_receipt_semantics
    bad_ts_body = {
        "protocol": "lineage-receipt-1.0",
        "target_id": "t",
        "root_ancestors": ["t"],
        "entities": [{"id": "t", "type": "data_snapshot", "sha256": sha256_hex(b"valid")}],
        "activities": [],
        "edges": [],
        "trace_steps": [{"step_number": 1, "activity_id": "does-not-exist", "inputs": ["missing"], "outputs": ["t"]}],
    }
    ld_ts = sha256_hex(canonical_json(bad_ts_body))
    rd_ts = sha256_hex(
        canonical_json(
            {
                "lineage_digest": ld_ts,
                "target_id": "t",
                "verification_status": "intact",
                "topology_status": "valid_dag",
                "content_verification": "fully_verified",
                "error_detail": "",
                "check_on_disk_hashes": True,
            }
        )
    )
    bad_ts_rec = {
        **bad_ts_body,
        "lineage_digest": ld_ts,
        "receipt_digest": rd_ts,
        "receipt_id": "rec-" + rd_ts[:32],
        "timestamp": "2026-11-15T00:00:00Z",
        "verification_status": "intact",
        "topology_status": "valid_dag",
        "content_verification": "fully_verified",
    }
    assert any("trace_steps" in e for e in validate_lineage_receipt_semantics(bad_ts_rec, decoded_content={"t": b"valid"}))

    # 5. Dangling MCP bindings rejected & valid binding accepted
    q_pay = {"paper_title": "Ex", "assertions": [{"statistic": "t", "reported_value": 1, "recomputed_value": 2, "discrepancy_detected": True}]}
    q_sha = sha256_hex(canonical_json(q_pay))
    q_env = {
        "protocol": "artifact-envelope-1.0",
        "artifact_id": f"art-{q_sha[:32]}",
        "artifact_kind": "quantitative_audit",
        "payload_schema": "quantitative-audit-1.0",
        "payload_sha256": q_sha,
        "producer": {"skill": "quantitative-paper-audit", "version": "3.0.0"},
        "payload": q_pay,
    }
    dangling_val = mcp_server.handle_tool_call("research_artifact_validate", {"envelope": q_env, "bindings": {"claim_id": "missing"}})
    assert dangling_val["valid"] is False and any("Dangling" in e for e in dangling_val["errors"])
    with pytest.raises(ValueError, match="Dangling"):
        mcp_server.handle_tool_call("research_artifact_ingest", {"envelope": q_env, "bindings": {"claim_id": "missing"}, "dry_run": True})
    db_bind = tmp_path / "bind.sqlite3"
    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))
    mcp_server.handle_tool_call("claim_evidence_add", {"db_path": str(db_bind), "claim_id": "c-live", "claim_text": "Claim under test"})
    assert mcp_server.handle_tool_call("research_artifact_validate", {"db_path": str(db_bind), "envelope": q_env, "bindings": {"claim_id": "c-live"}})["valid"] is True
    ing_res = mcp_server.handle_tool_call("research_artifact_ingest", {"db_path": str(db_bind), "envelope": q_env, "bindings": {"claim_id": "c-live"}})
    assert ing_res["valid"] is True
    with ResearchStateDB(db_bind, readonly=True) as db_chk:
        ceg_inline = thaw(db_chk.export_ceg_dict())
    assert mcp_server.handle_tool_call(
        "research_artifact_validate",
        {"envelope": q_env, "state": {"ceg": ceg_inline}, "bindings": {"claim_id": "c-live"}},
    )["valid"] is True
    assert mcp_server.handle_tool_call(
        "research_artifact_validate",
        {"envelope": q_env, "state": {"ceg": ceg_inline}, "bindings": {"claim_id": "missing"}},
    )["valid"] is False
    # Malformed inline state.artifacts / receipts / uncertainties rejected
    assert mcp_server.handle_tool_call(
        "research_artifact_validate",
        {"artifact_id": "q", "kind": "source", "payload": {"x": 2}, "state": {"artifacts": {"ghost": None}}, "bindings": {"artifact_id": "ghost"}},
    )["valid"] is False
    assert mcp_server.handle_tool_call(
        "research_artifact_validate",
        {"artifact_id": "q", "kind": "source", "payload": {"x": 2}, "state": {"uncertainties": "bad"}},
    )["valid"] is False
    # Generic source claim_id binding succeeds in both validate and stateful ingest
    src_ing = mcp_server.handle_tool_call(
        "research_artifact_ingest",
        {"db_path": str(db_bind), "artifact_id": "src-q", "kind": "source", "payload": {"x": 2}, "bindings": {"claim_id": "c-live"}},
    )
    assert src_ing["receipt"]["status"] == "accepted"
    # Trailing-newline 65-char digest rejected in ReceiptRef
    from academic_research_kernel.state_db import validate_receipt_ref_dict

    assert validate_receipt_ref_dict(
        {"kind": "lineage", "schema_version": "lineage-receipt-1.0", "receipt_id": "r", "receipt_digest": "a" * 64 + "\n"}
    )

    # 6. Relative Path('.') in release_gate._expected_sdist_rels
    repo_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(repo_root)
    rels_dot = release_gate._expected_sdist_rels(Path("."), release_gate._load_pyproject(Path(".")))
    rels_abs = release_gate._expected_sdist_rels(repo_root, release_gate._load_pyproject(repo_root))
    assert rels_dot == rels_abs and "pyproject.toml" in rels_dot

    # 7. Offline benchmark validator rejects histogram sum drift and out-of-range mean_soundness
    if (repo_root / "tools/benchmarks").is_dir() and (repo_root / "docs/benchmarks").is_dir():
        import importlib.util

        spec_bm = importlib.util.spec_from_file_location("bm_mod", repo_root / "tools/benchmarks/run_peer_review_and_incidence_benchmarks.py")
        assert spec_bm and spec_bm.loader
        bm_mod = importlib.util.module_from_spec(spec_bm)
        spec_bm.loader.exec_module(bm_mod)

        peer_bad = json.loads((repo_root / "docs/benchmarks/peer-review-forensics-2025-2027-v1.json").read_text(encoding="utf-8"))
        peer_bad["venues"][0]["raw_rating_histogram"]["2"] += 1
        peer_bad["receipt_sha256"] = bm_mod._canonical_body_sha256(peer_bad)
        p_bad_path = tmp_path / "peer_bad.json"
        p_bad_path.write_text(json.dumps(peer_bad), encoding="utf-8")
        with pytest.raises(ValueError, match="raw_rating_histogram"):
            bm_mod.verify_receipts_offline(peer_path=p_bad_path)

        peer_scale_bad = json.loads((repo_root / "docs/benchmarks/peer-review-forensics-2025-2027-v1.json").read_text(encoding="utf-8"))
        peer_scale_bad["venues"][3]["raw_rating_histogram"]["7"] = 1
        peer_scale_bad["venues"][3]["total_reviews"] += 1
        peer_scale_bad["totals"]["total_positive_reviews"] += 1
        peer_scale_bad["receipt_sha256"] = bm_mod._canonical_body_sha256(peer_scale_bad)
        p_scale_path = tmp_path / "peer_scale_bad.json"
        p_scale_path.write_text(json.dumps(peer_scale_bad), encoding="utf-8")
        with pytest.raises(ValueError, match="outside declared_valid_ratings"):
            bm_mod.verify_receipts_offline(peer_path=p_scale_path)

        inc_bad = json.loads((repo_root / "docs/benchmarks/iclr2026-openreview-incidence-receipt.json").read_text(encoding="utf-8"))
        inc_bad["tiers"]["Oral"]["mean_soundness"] = -999
        inc_bad["receipt_sha256"] = bm_mod._canonical_body_sha256(inc_bad)
        i_bad_path = tmp_path / "inc_bad.json"
        i_bad_path.write_text(json.dumps(inc_bad), encoding="utf-8")
        with pytest.raises(ValueError, match="mean_soundness"):
            bm_mod.verify_receipts_offline(inc_path=i_bad_path)


def test_v300_rc_closure_bindings_cohorts_and_blind_url_tiers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from academic_research_kernel import double_blind_sanitizer, recompute

    monkeypatch.setenv("ARK_WORKSPACE_ROOT", str(tmp_path))

    # 1. P1-01: Bound claim_id target enforcement, scalar/array normalization, and native consistent boolean
    good = {"reported_value": 1, "recomputed_value": 1, "discrepancy_detected": False}
    bad = {"reported_value": 1, "recomputed_value": 2, "discrepancy_detected": True}
    mixed = {"assertions": [dict(good, claim_id="c1"), dict(bad, claim_id="c2")]}

    mcp_server.reset_session_db()
    db = mcp_server.get_session_db()
    db.add_claim("c1", "Claim one is numerically correct")
    db.add_claim("c2", "Claim two is numerically correct")
    before_dig = db.snapshot_digest()

    with pytest.raises(ValueError, match="Bound claim_id mismatch"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {"artifact_id": "res-mix", "kind": "quantitative_audit", "payload": mixed, "bindings": {"claim_id": "c1"}},
        )
    with pytest.raises(ValueError, match="Bound claim_id mismatch"):
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {"artifact_id": "res-mix", "kind": "quantitative_audit", "payload": mixed, "bindings": {"claim_id": "c1"}, "dry_run": True},
        )
    val_mix = mcp_server.handle_tool_call(
        "research_artifact_validate",
        {"kind": "quantitative_audit", "payload": mixed, "bindings": {"claim_id": "c1"}},
    )
    assert val_mix["valid"] is False and any("Bound claim_id mismatch" in e for e in val_mix["errors"])

    mix_sha = sha256_hex(canonical_json(mixed))
    mix_env = {
        "protocol": "artifact-envelope-1.0",
        "artifact_id": f"art-{mix_sha[:32]}",
        "artifact_kind": "quantitative_audit",
        "payload_schema": "quantitative-audit-1.0",
        "payload_sha256": mix_sha,
        "producer": {"skill": "audit-paper", "version": "3.0.0"},
        "payload": mixed,
    }
    assert mcp_server.handle_tool_call("research_artifact_validate", {"envelope": mix_env, "bindings": {"claim_id": "c1"}})["valid"] is False
    with pytest.raises(ValueError, match="Bound claim_id mismatch"):
        mcp_server.handle_tool_call("research_artifact_ingest", {"envelope": mix_env, "bindings": {"claim_id": "c1"}})
    assert db.snapshot_digest() == before_dig
    statuses_after_reject = {c["id"]: c["metadata"]["status"] for c in thaw(db.export_ceg_dict())["claims"]}
    assert statuses_after_reject == {"c1": "unresolved", "c2": "unresolved"}

    # Artifact-only storage without outer binding continues to accept multi-claim payload without mutating claim statuses
    art_only = mcp_server.handle_tool_call(
        "research_artifact_ingest",
        {"artifact_id": "res-art-only", "kind": "quantitative_audit", "payload": mixed},
    )
    assert art_only["receipt"]["status"] == "accepted"
    assert {c["id"]: c["metadata"]["status"] for c in thaw(db.export_ceg_dict())["claims"]} == {"c1": "unresolved", "c2": "unresolved"}

    # Scalar & wrapped discrepancy_detected and native check_p_match consistent booleans map identically
    native_bad = recompute.check_p_match(0.01, 0.20, decimals=2)
    native_good = recompute.check_p_match(0.01, 0.01, decimals=2)
    for idx_case, (pay, exp_status, exp_edge) in enumerate(
        (
            (bad, "refuted", "contradicted"),
            ({"assertions": [bad]}, "refuted", "contradicted"),
            (native_bad, "refuted", "contradicted"),
            ({"assertions": [native_bad]}, "refuted", "contradicted"),
            (native_good, "supported", "supported"),
            ({"assertions": [native_good]}, "supported", "supported"),
            ({"assertions": [good]}, "supported", "supported"),
            ({"assertions": [dict(good, claim_id="c1")]}, "supported", "supported"),
        )
    ):
        mcp_server.reset_session_db()
        db_i = mcp_server.get_session_db()
        db_i.add_claim("c1", "Target claim")
        mcp_server.handle_tool_call(
            "research_artifact_ingest",
            {"artifact_id": f"q-{idx_case}", "kind": "quantitative_audit", "payload": pay, "bindings": {"claim_id": "c1"}},
        )
        ceg_i = thaw(db_i.export_ceg_dict())
        assert {c["id"]: c["metadata"]["status"] for c in ceg_i["claims"]}["c1"] == exp_status
        assert ceg_i["support_edges"][0]["support_status"] == exp_edge

    # 2. P2-02: Unimplemented bindings keys (decision_id, evidence_id, work_id) fail fast with actionable guidance
    mcp_server.reset_session_db()
    db_d = mcp_server.get_session_db()
    db_d.record_decision("d1", "Decision")
    for bad_bk in ("decision_id", "evidence_id", "work_id"):
        with pytest.raises(ValueError, match="Unsupported 'bindings' fields"):
            mcp_server.handle_tool_call(
                "research_artifact_ingest",
                {"artifact_id": "s1", "kind": "source", "payload": {"text": "x"}, "bindings": {bad_bk: "d1"}},
            )
        val_bk = mcp_server.handle_tool_call(
            "research_artifact_validate",
            {"kind": "source", "payload": {"text": "x"}, "bindings": {bad_bk: "d1"}},
        )
        assert val_bk["valid"] is False

    # 3. P2-01: Generic third-party public repo URL emits warning without blocking, while self/forbidden URL blocks
    anon_tex = tmp_path / "anon_pytorch.tex"
    anon_tex.write_text(
        "\\documentclass{article}\n\\author{Anonymous Authors}\n"
        "\\begin{document}\n\\begin{abstract}Summary.\\end{abstract}\n"
        "We implement models in PyTorch (https://github.com/pytorch/pytorch).\n\\end{document}\n",
        encoding="utf-8",
    )
    rep_third = thaw(pre_submission_linter.lint_manuscript(anon_tex, venue=None, double_blind=True))
    assert rep_third["passed"] is True and rep_third["error_count"] == 0
    assert any(f["code"] == "BLIND_URL_LEAK" and f["severity"] == "warning" for f in rep_third["findings"])
    scan_third = double_blind_sanitizer.scan_target(anon_tex)
    assert scan_third["status"] == "clean" and scan_third["leak_count"] == 0 and scan_third["warning_count"] == 1

    self_tex = tmp_path / "self_leak.tex"
    self_tex.write_text(
        "\\documentclass{article}\n\\author{Anonymous Authors}\n"
        "\\begin{document}\n\\begin{abstract}Summary.\\end{abstract}\n"
        "Our code is available at https://github.com/secretlab/method-repo.\n\\end{document}\n",
        encoding="utf-8",
    )
    rep_self = thaw(pre_submission_linter.lint_manuscript(self_tex, venue=None, double_blind=True))
    assert rep_self["passed"] is False
    assert any(f["code"] == "BLIND_URL_LEAK" and f["severity"] == "error" for f in rep_self["findings"])
    scan_self = double_blind_sanitizer.scan_target(self_tex)
    assert scan_self["status"] == "leaks_detected" and scan_self["leak_count"] >= 1

    # 4. P1-02 & P2-04: Verify stratified NeurIPS main accepted cohort, ICML 1-6 scale, and frozen 2026-11-14 date
    peer_path = Path(__file__).resolve().parents[1] / "docs" / "benchmarks" / "peer-review-forensics-2025-2027-v1.json"
    if peer_path.is_file():
        peer_doc = json.loads(peer_path.read_text(encoding="utf-8"))
        assert peer_doc["snapshot_date_utc"] == "2026-11-14"
        assert peer_doc["totals"]["conference_series_count"] == 4
        by_vid = {v["venue_id"]: v for v in peer_doc["venues"]}
        assert by_vid["ICML.cc/2026/Conference"]["declared_valid_ratings"] == [1, 2, 3, 4, 5, 6]
        assert by_vid["ICML.cc/2026/Conference"]["raw_rating_histogram"]["6"] == 334
        nips_v = by_vid["NeurIPS.cc/2025/Conference"]
        assert nips_v["paper_count"] == 5275 and nips_v["total_reviews"] == 21301
        assert nips_v["full_mirror_raw_record_count"] == 6212 and nips_v["excluded_from_primary_scope_count"] == 937
        assert nips_v["mirror_cohort_breakdown"]["ratings_above_or_outside_main_scale_in_excluded_tracks"]["rating_count"] == 125

    mcp_server.reset_session_db()
