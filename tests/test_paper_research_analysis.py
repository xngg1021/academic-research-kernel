"""Source-backed mutations and independent arithmetic for the thin workflow."""
from __future__ import annotations

import copy
from decimal import Decimal, localcontext
import importlib
import json
from pathlib import Path
import shutil
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Exercise checkout sources without relying on an editable or globally installed
# kernel. All resource imports continue through the same real kernel modules.
PACKAGE = "_ark_paper_workflow_test"
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT / "src/academic_research_kernel"), str(ROOT / "scripts"), str(ROOT / "scripts/scfabric")]
    for skill in ("research-object-identity", "claim-evidence-graph", "decision-ledger", "quantitative-paper-audit"):
        package.__path__.append(str(ROOT / "skills" / skill / "scripts"))
    sys.modules[PACKAGE] = package
    sys.path.insert(0, str(ROOT / "scripts"))
analysis = importlib.import_module(PACKAGE + ".research.analysis")
sources = importlib.import_module(PACKAGE + ".research.sources")


@pytest.fixture
def case(tmp_path):
    material = tmp_path / "资料 包"
    material.mkdir()
    paper = material / "正文.txt"
    text = """Synthetic mutation-control paper (not a real research report).

Methods: 32 participants completed the randomized parallel independent-group experiment.

The main analysis reported t = 2.0, df = 30 and two-sided p = 0.0546.

Group A had mean 5.0, SD 2.0 and n = 16; group B had mean 3.0, SD 2.0 and n = 16.

Eight cases represented 25.0% of the 32 analyzed participants. Eleven professional participants were included in a separate descriptive sample.

The experiment used complete cases, no imputation and no adjusted p values. Units were scale points. Random seed was explicitly not reported.
"""
    paper.write_text(text, "utf-8")
    (material / "manifest.json").write_text(json.dumps({"title": "Synthetic mutation control", "files": [{"path": "正文.txt", "role": "main"}]}), "utf-8")
    project = tmp_path / "研究 项目"
    sources.prepare(str(material), project)
    docs = json.loads((project / "documents.json").read_text("utf-8"))
    doc = docs["documents"][0]
    common = {"group": None, "timepoint": "endpoint", "dataset": "synthetic", "analysis_set": "complete cases", "condition": "independent two-group"}
    def field(identifier, name, literal, value, kind="number", unit=None, group=None):
        segment = next(s for s in doc["segments"] if literal in s["text"] or literal.lower() in s["text"].lower())
        return {"id": identifier, "name": name, "type": kind, "status": "extracted", "literal": literal, "value": value, "unit": unit,
                "context": {**common, "group": group}, "sources": [{"document_id": doc["document_id"], "locator": segment["locator"], "quote": segment["text"]}], "reason": None}
    fields = [field("t", "t", "2.0", 2), field("df", "df", "30", 30, "integer"), field("p", "p", "0.0546", .0546, "p_value"),
              field("n", "sample size", "32", 32, "integer"), field("count", "count", "Eight", 8, "integer"), field("percent", "percentage", "25.0", 25, unit="%"),
              field("ma", "mean", "5.0", 5, unit="points", group="A"), field("sda", "SD", "2.0", 2, unit="points", group="A"), field("na", "n", "16", 16, "integer", group="A"),
              field("mb", "mean", "3.0", 3, unit="points", group="B"), field("sdb", "SD", "2.0", 2, unit="points", group="B"), field("nb", "n", "16", 16, "integer", group="B"),
              field("word_n", "word sample size", "Eleven", 11, "integer")]
    # Locate identical literals in the right group region, never infer a group
    # just because another paragraph happens to contain the same decimal.
    group_segment = next(s for s in doc["segments"] if "Group A" in s["text"])
    for f in fields[6:12]:
        f["sources"][0].update(locator=group_segment["locator"], quote=group_segment["text"])
    summary = {key: {"text": "Synthetic control only; see cited fields.", "field_ids": ["n", "p"]} for key in ("objective", "design", "main_results", "attention")}
    candidate = {"schema_version": "1.0", "project_fingerprint": docs["fingerprint"], "paper": {"title": "Synthetic mutation control", "identifier": "test-control", "version": "1"},
                 "producer": {"kind": "agent", "name": "fixture semantic producer", "model": None}, "search_scope": [doc["document_id"]],
                 "fields": fields, "summary": summary,
                 "checks": [{"id": "t-p", "kind": "t_p", "inputs": {"t_stat": "t", "df": "df"}, "reported": "p", "tail": "two", "note": "two sided"},
                            {"id": "percent", "kind": "percentage", "inputs": {"count": "count", "percent": "percent", "sample_size": "n"}, "reported": "percent", "tail": None, "note": "same analysis set"},
                            {"id": "effect", "kind": "effect_size", "inputs": {"mean1": "ma", "sd1": "sda", "n1": "na", "mean2": "mb", "sd2": "sdb", "n2": "nb"}, "reported": None, "tail": None, "note": "independent groups"}]}
    path = project / "candidate.json"
    path.write_text(json.dumps(candidate), "utf-8")
    return project, docs, candidate, path


def test_complete_round_trip_and_repeated_run(case):
    project, docs, candidate, path = case
    receipt = analysis.finish(project, path)
    assert receipt["status"] == "complete"
    assert receipt["computed_checks"] == 3
    assert receipt["discrepancies"] == 0
    assert receipt["ingestion"]["ledger_decisions"] == 0
    assert receipt["ingestion"]["round_trip"] == "passed"
    replay = analysis.finish(project, path)
    assert replay["reused"] is True
    assert replay["ingestion"] == receipt["ingestion"]
    results = json.loads(Path(receipt["results"]).read_text("utf-8"))
    assert results[0]["input_chain"]["t_stat"]["sources"][0]["sha256"] == docs["documents"][0]["sha256"]
    assert "locations.html#" in Path(receipt["report_html"]).read_text("utf-8")


def test_independent_reference_formula(case):
    _, docs, candidate, _ = case
    results = analysis.compute_checks(candidate, docs)
    # Precomputed high precision t CDF reference, independently evaluated from
    # the regularized incomplete beta expression I_(df/(df+t²))(df/2, 1/2).
    assert results[0]["recomputed"] == pytest.approx(0.05462504496298312, abs=1e-14)
    with localcontext() as context:
        context.prec = 50
        pooled = (((Decimal(16)-1)*Decimal(2)**2 + (Decimal(16)-1)*Decimal(2)**2) / Decimal(30)).sqrt()
        expected = (Decimal(5)-Decimal(3)) / pooled
        assert results[2]["recomputed"]["cohens_d"] == float(expected)
    assert results[1]["recomputed"] == float(Decimal(100)*Decimal(8)/Decimal(32))


@pytest.mark.parametrize("mutation", ["fabricated_locator", "fabricated_quote", "decimal_precision", "wrong_normalization", "stale_fingerprint", "all_missing", "missing_scope"])
def test_invalid_candidate_mutations(case, mutation):
    project, docs, candidate, _ = case
    candidate = copy.deepcopy(candidate)
    if mutation == "fabricated_locator":
        candidate["fields"][0]["sources"][0]["locator"] = "text:paragraph=9000"
    elif mutation == "fabricated_quote":
        candidate["fields"][0]["sources"][0]["quote"] = "The paper reports t = 9000."
    elif mutation == "decimal_precision":
        candidate["fields"][2]["literal"] = "0.0546000"
    elif mutation == "wrong_normalization":
        candidate["fields"][4]["value"] = 9
    elif mutation == "stale_fingerprint":
        candidate["project_fingerprint"] = "0"*64
    elif mutation == "all_missing":
        for field in candidate["fields"]:
            field.update(status="not_found", value=None, reason="not found")
    else:
        candidate["search_scope"] = ["nonexistent supplement"]
    with pytest.raises(ValueError):
        analysis.validate_candidate(project, candidate, documents=docs)


@pytest.mark.parametrize("mutation", ["wrong_denominator", "sd_se", "units", "same_name_wrong_group", "one_tail"])
def test_calculation_context_mutations(case, mutation):
    _, docs, candidate, _ = case
    candidate = copy.deepcopy(candidate)
    by_id = {f["id"]: f for f in candidate["fields"]}
    if mutation == "wrong_denominator":
        by_id["n"]["value"] = 31
    elif mutation == "sd_se":
        by_id["sda"]["name"] = "standard error (SE)"
    elif mutation == "units":
        by_id["sda"]["unit"] = "milliseconds"
    elif mutation == "same_name_wrong_group":
        by_id["count"]["context"]["group"] = "different group"
    else:
        candidate["checks"][0]["tail"] = "one"
    results = analysis.compute_checks(candidate, docs)
    if mutation == "wrong_denominator":
        assert results[1]["consistent"] is False
    else:
        result = results[2] if mutation in {"sd_se", "units"} else results[1] if mutation == "same_name_wrong_group" else results[0]
        assert result["status"] == "not_computed"
        assert result["reason"]


def test_same_condition_conflict_preserved_separate_group_not_conflict(case):
    project, docs, candidate, _ = case
    candidate = copy.deepcopy(candidate)
    first = copy.deepcopy(candidate["fields"][0])
    first.update(id="t-other", literal="3.0", value=3)
    source = next(s for s in docs["documents"][0]["segments"] if "3.0" in s["text"])
    first["sources"][0].update(locator=source["locator"], quote=source["text"])
    candidate["fields"].append(first)
    result = analysis.validate_candidate(project, candidate, documents=docs)
    assert len(result["conflicts"]) == 1
    first["context"]["group"] = "different group"
    assert not analysis.validate_candidate(project, candidate, documents=docs)["conflicts"]


def test_source_mutation_and_locator_snapshot_tamper(case):
    project, docs, candidate, path = case
    raw = project / docs["documents"][0]["relative_path"]
    raw.write_text(raw.read_text("utf-8") + "\nChanged original bytes.\n", "utf-8")
    with pytest.raises(ValueError, match="source/parser/locator changed"):
        analysis.finish(project, path)


def test_recover_after_interrupted_ingestion(case, monkeypatch):
    project, _, _, path = case
    original = analysis._ingest
    def fail_once(*args):
        raise OSError("synthetic temporary interruption")
    monkeypatch.setattr(analysis, "_ingest", fail_once)
    with pytest.raises(OSError):
        analysis.finish(project, path)
    assert list(project.glob("runs/*/results.json"))
    monkeypatch.setattr(analysis, "_ingest", original)
    assert analysis.finish(project, path)["status"] == "complete"


@pytest.mark.parametrize("t_stat,alternative,expected", [
    (2.0, "greater", 0.02731252248149156), (-2.0, "less", 0.02731252248149156),
    (2.0, "less", 0.9726874775185084), (-2.0, "greater", 0.9726874775185084),
    (0.0, "less", .5), (0.0, "greater", .5),
])
def test_declared_one_tail_sign_and_reverse_direction(case, t_stat, alternative, expected):
    _, docs, candidate, _ = case
    candidate = copy.deepcopy(candidate)
    by_id = {f["id"]: f for f in candidate["fields"]}
    by_id["t"].update(value=t_stat, literal=str(t_stat))
    by_id["p"].update(value=round(expected, 4), literal=f"{expected:.4f}")
    candidate["checks"][0].update(tail="one", alternative=alternative)
    result = analysis.compute_checks(candidate, docs)[0]
    assert result["status"] == "computed"
    assert result["recomputed"] == pytest.approx(expected, abs=1e-14)
    assert result["consistent"] is True
    assert result["tail_conversion"]["alternative"] == alternative
    assert result["raw_result"]["recomputed_p"] == pytest.approx(.05462504496298312 if t_stat else 1, abs=1e-14)
    assert "p_match" not in result["raw_result"]


@pytest.mark.parametrize("literal,value,t_stat,consistent", [
    ("p < 0.001", .001, 2, False), ("p < 0.001", .001, 10, True),
    ("0.0546000", .0546, 2, False), ("1.0e-5", .00001, 1, False),
])
def test_explicit_artificial_p_inequality_small_value_and_trailing_zero(case, literal, value, t_stat, consistent):
    _, docs, candidate, _ = case
    candidate = copy.deepcopy(candidate)
    by_id = {f["id"]: f for f in candidate["fields"]}
    by_id["p"].update(literal=literal, value=value)
    by_id["t"].update(literal=str(t_stat), value=t_stat)
    result = analysis.compute_checks(candidate, docs)[0]
    assert result["consistent"] is consistent
    if "<" in literal:
        assert result["precision"]["relation"] == "<"


def test_relocated_offline_project_and_explicit_comparison(case):
    project, docs, candidate, path = case
    analysis.finish(project, path)
    right = project.parent / "relocated paper"
    shutil.copytree(project, right)
    replay = analysis.finish(right, right / "candidate.json")
    assert replay["reused"] is True
    assert Path(replay["report_markdown"]).is_relative_to(right)
    comparison = {"schema_version": "1.0", "producer": candidate["producer"],
                  "left_project_fingerprint": docs["fingerprint"], "right_project_fingerprint": docs["fingerprint"],
                  "rows": [{"dimension": dimension, "left_field_ids": ["n", "p"], "right_field_ids": ["n", "p"],
                            "assessment": "conditional", "reason": "Synthetic source copy used only for comparison contract and provenance verification."}
                           for dimension in ("数据", "方法", "参数", "评估", "结果", "可比性")],
                  "conclusion": {"text": "This is an explicitly labeled synthetic copy comparison.", "left_field_ids": ["n"], "right_field_ids": ["n"]}}
    proposal = project.parent / "comparison.json"
    proposal.write_text(json.dumps(comparison), "utf-8")
    receipt = analysis.compare(project, right, proposal, project.parent / "comparison-result")
    assert receipt["status"] == "complete" and receipt["rows"] == 6
    markdown = Path(receipt["comparison_markdown"]).read_text("utf-8")
    assert "SHA-256" in markdown
    assert "locations.html#" in markdown and "relocated%20paper/locations.html#" in markdown
    assert "%E7%A0%94%E7%A9%B6%20%E9%A1%B9%E7%9B%AE/locations.html#" in markdown
    assert "file:///" not in markdown
    comparison["rows"][0].update(assessment="direct", left_field_ids=["ma"], right_field_ids=["mb"])
    proposal.write_text(json.dumps(comparison), "utf-8")
    with pytest.raises(ValueError, match="contexts"):
        analysis.compare(project, right, proposal, project.parent / "invalid-comparison")


def test_html_escapes_untrusted_links_and_preserves_table_columns():
    page = analysis._html("# Safe report\n[unsafe](javascript:alert(1))\n| Key | Value |\n|---|---|\n| A | B \\| C |\n", "Report")
    assert 'href="javascript:' not in page
    assert page.count("<td>") == 4
    assert "B | C" in page


def test_candidate_title_raw_text_and_p_operator_are_source_checked(case):
    project, docs, candidate, _ = case
    wrong = copy.deepcopy(candidate)
    wrong["paper"]["title"] = "A different paper"
    with pytest.raises(ValueError, match="identity"):
        analysis.validate_candidate(project, wrong, documents=docs)
    wrong = copy.deepcopy(candidate)
    wrong["fields"][2]["literal"] = "p < 0.0546"
    with pytest.raises(ValueError, match="inequality"):
        analysis.validate_candidate(project, wrong, documents=docs)
    wrong = copy.deepcopy(candidate)
    fabricated = copy.deepcopy(wrong["fields"][0])
    fabricated.update(id="fabricated_text", type="text", literal="invented raw statement", value="Invented normalized statement")
    wrong["fields"].append(fabricated)
    with pytest.raises(ValueError, match="raw text"):
        analysis.validate_candidate(project, wrong, documents=docs)


@pytest.mark.parametrize("reported", ["n", None])
def test_percentage_reported_binding_cannot_claim_false_match(case, reported):
    project, docs, candidate, _ = case
    candidate = copy.deepcopy(candidate)
    candidate["checks"][1]["reported"] = reported
    with pytest.raises(ValueError, match="percentage reported"):
        analysis.validate_candidate(project, candidate, documents=docs)
    result = analysis.compute_checks(candidate, docs)[1]
    assert result["status"] == "not_computed" and result["consistent"] is None


def test_cross_document_same_condition_conflict(case):
    project, _, candidate, _ = case
    package = project.parent / "资料 包"
    (package / "mutated-supplement.txt").write_text("Explicit synthetic mutated supplementary control: the same-condition t = 3.0. Original main source is unchanged.", "utf-8")
    manifest = json.loads((package / "manifest.json").read_text("utf-8"))
    manifest["files"].append({"path": "mutated-supplement.txt", "role": "supplement"})
    (package / "manifest.json").write_text(json.dumps(manifest), "utf-8")
    sources.prepare(str(package), project)
    docs = sources.verify(project)
    candidate = copy.deepcopy(candidate)
    candidate["project_fingerprint"] = docs["fingerprint"]
    candidate["search_scope"] = [d["document_id"] for d in docs["documents"]]
    extra = copy.deepcopy(candidate["fields"][0])
    supplement = next(d for d in docs["documents"] if d["role"] == "supplement")
    extra.update(id="t-supplement", literal="3.0", value=3,
                 sources=[{"document_id": supplement["document_id"], "locator": supplement["segments"][0]["locator"], "quote": supplement["segments"][0]["text"]}])
    candidate["fields"].append(extra)
    validation = analysis.validate_candidate(project, candidate, documents=docs)
    assert validation["conflicts"][0]["field_ids"] == ["t", "t-supplement"]
    assert candidate["fields"][0]["sources"][0]["document_id"] != extra["sources"][0]["document_id"]


def test_offline_forced_regeneration_and_extractor_invalidation(case, monkeypatch):
    project, _, candidate, path = case
    first = analysis.finish(project, path)
    Path(first["report_html"]).unlink()
    def no_network(*args, **kwargs):
        raise AssertionError("Offline replay attempted network acquisition")
    monkeypatch.setattr(sources, "fetch", no_network)
    regenerated = analysis.finish(project, path)
    assert regenerated["reused"] is False and regenerated["analysis_fingerprint"] == first["analysis_fingerprint"]
    assert Path(regenerated["report_html"]).is_file()
    candidate = copy.deepcopy(candidate)
    candidate["producer"]["name"] = "changed semantic extractor configuration"
    path.write_text(json.dumps(candidate), "utf-8")
    changed = analysis.finish(project, path)
    assert changed["analysis_fingerprint"] != first["analysis_fingerprint"]


@pytest.mark.parametrize("numeric_side", ["left", "right"])
def test_direct_comparison_requires_symmetric_numeric_metrics(case, numeric_side):
    project, docs, candidate, path = case
    candidate = copy.deepcopy(candidate)
    source = candidate["fields"][0]["sources"][0]
    extra = copy.deepcopy(candidate["fields"][0])
    extra.update(id="description", type="text", name="description", literal=source["quote"], value=source["quote"])
    candidate["fields"].append(extra)
    path.write_text(json.dumps(candidate), "utf-8")
    analysis.finish(project, path)
    row = {"dimension": "deliberately incompatible", "left_field_ids": ["n" if numeric_side == "left" else "description"],
           "right_field_ids": ["n" if numeric_side == "right" else "description"], "assessment": "direct", "reason": "Explicit synthetic text/numeric mismatch control."}
    proposal = {"schema_version": "1.0", "producer": candidate["producer"], "left_project_fingerprint": docs["fingerprint"], "right_project_fingerprint": docs["fingerprint"],
                "rows": [copy.deepcopy(row) for _ in range(6)], "conclusion": {"text": "Synthetic mismatch", "left_field_ids": ["n"], "right_field_ids": ["n"]}}
    proposal_path = project / "incompatible.json"
    proposal_path.write_text(json.dumps(proposal), "utf-8")
    with pytest.raises(ValueError, match="same named metric"):
        analysis.compare(project, project, proposal_path)


def test_sentence_punctuation_is_distinct_from_decimal_precision(case):
    project, _, candidate, _ = case
    package = project.parent / "资料 包"
    quote = "Explicit synthetic punctuation control: batch size is 256. Exact value is 1.00. Tiny p = 1.0e-5. Negative statistic = −2.0. Scientific form = 1.e-5."
    (package / "punctuation-supplement.txt").write_text(quote, "utf-8")
    manifest = json.loads((package / "manifest.json").read_text("utf-8"))
    manifest["files"].append({"path": "punctuation-supplement.txt", "role": "supplement"})
    (package / "manifest.json").write_text(json.dumps(manifest), "utf-8")
    sources.prepare(str(package), project)
    docs = sources.verify(project)
    candidate = copy.deepcopy(candidate)
    candidate["project_fingerprint"] = docs["fingerprint"]
    candidate["search_scope"] = [d["document_id"] for d in docs["documents"]]
    doc = next(d for d in docs["documents"] if "punctuation" in d["relative_path"])
    for identifier, literal, value, kind in (("batch", "256", 256, "integer"), ("precise", "1.00", 1, "number"),
                                            ("tiny", "1.0e-5", .00001, "p_value"), ("negative", "−2.0", -2, "number"),
                                            ("scientific", "1.e-5", .00001, "number")):
        field = copy.deepcopy(candidate["fields"][0])
        field.update(id=identifier, name=identifier, literal=literal, value=value, type=kind,
                     sources=[{"document_id": doc["document_id"], "locator": doc["segments"][0]["locator"], "quote": quote}])
        candidate["fields"].append(field)
    assert analysis.validate_candidate(project, candidate, documents=docs)["valid"] is True
    precise = next(f for f in candidate["fields"] if f["id"] == "precise")
    precise["literal"] = "1"
    with pytest.raises(ValueError, match="precision"):
        analysis.validate_candidate(project, candidate, documents=docs)


def test_thousands_groups_with_spaces_do_not_merge_decimal_or_count_lists(case):
    project, _, candidate, _ = case
    package = project.parent / "资料 包"
    quote = "Explicit synthetic grouped-number control: 1, 000 classes, 12, 345.00 units; p values 0.05, 0.10; separate counts 1, 2."
    (package / "grouped-number-supplement.txt").write_text(quote, "utf-8")
    manifest = json.loads((package / "manifest.json").read_text("utf-8"))
    manifest["files"].append({"path": "grouped-number-supplement.txt", "role": "supplement"})
    (package / "manifest.json").write_text(json.dumps(manifest), "utf-8")
    sources.prepare(str(package), project)
    docs = sources.verify(project)
    candidate = copy.deepcopy(candidate)
    candidate["project_fingerprint"] = docs["fingerprint"]
    candidate["search_scope"] = [d["document_id"] for d in docs["documents"]]
    doc = next(d for d in docs["documents"] if "grouped-number" in d["relative_path"])
    for identifier, literal, value, kind in (("classes", "1, 000", 1000, "integer"), ("precise_units", "12, 345.00", 12345, "number"),
                                            ("list_p", "0.05", .05, "p_value")):
        field = copy.deepcopy(candidate["fields"][0])
        field.update(id=identifier, name=identifier, literal=literal, value=value, type=kind,
                     sources=[{"document_id": doc["document_id"], "locator": doc["segments"][0]["locator"], "quote": quote}])
        candidate["fields"].append(field)
    assert analysis.validate_candidate(project, candidate, documents=docs)["valid"] is True
    assert analysis._NUMBER.findall("p=0.05, 0.10") == ["0.05", "0.10"]
    assert analysis._NUMBER.findall("counts 1, 2") == ["1", "2"]
    assert analysis._NUMBER.findall("invalid 1, 0000") == ["1", "0000"]


def test_numeric_library_version_change_invalidates_computation_cache(case, monkeypatch):
    project, _, _, path = case
    first = analysis.finish(project, path)
    assert analysis.finish(project, path)['reused'] is True
    original = analysis.metadata.version
    monkeypatch.setattr(analysis.metadata, 'version', lambda name: '999.0.synthetic' if name == 'scipy' else original(name))
    changed = analysis.finish(project, path)
    assert changed['reused'] is False
    assert changed['analysis_fingerprint'] != first['analysis_fingerprint']
    assert changed['runtime']['libraries']['scipy'] == '999.0.synthetic'
