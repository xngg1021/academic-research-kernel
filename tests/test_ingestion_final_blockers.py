"""Source-derived completeness and four-blocker final acceptance regressions."""
import copy
import json
from pathlib import Path

import pytest

from test_ingestion_hardening import (
    IngestionEngine, IngestionKernelState, IngestionReceipt, call_tool, ceg_mod,
    envelope, evidence_payload, kernel, ledger_mod,
)
from test_ingestion_closeout import reload_state, graph_artifact
from ingestion.adapters import QuantitativePaperAuditAdapter, _domain_derived_uncertainties
from ingestion.contracts import validate_schema
from ingestion.models import _normalise_uncertainty, VALID_KERNEL_UNCERTAINTY_KINDS
from shared_contracts.evidence import canonical_json_bytes, compute_sha256


def forge_receipt(env, old, **changes):
    args = dict(envelope=env, adapter_id=old.adapter_id, adapter_version=old.adapter_version,
                status='accepted', valid=True, errors=[], output_digests=old.output_digests,
                ingestion_context_digest=old.ingestion_context_digest,
                created_or_reused_objects=list(old.created_or_reused_objects),
                ceg_nodes=list(old.ceg_nodes), ceg_edges=list(old.ceg_edges),
                mutation_bindings=list(old.mutation_bindings), ledger_bindings=list(old.ledger_bindings),
                uncertainties=list(old.uncertainties), ignored_fields=list(old.ignored_fields))
    args.update(changes)
    return IngestionReceipt.create(**args)


@pytest.mark.parametrize('wrapper', ['direct', 'canonical_work', 'works'])
@pytest.mark.parametrize('doi,accepted', [
    ('10.1000/original', True), ('10.1000/ORIGINAL', True),
    ('https://doi.org/10.1000/Original', True), ('http://dx.doi.org/10.1000/original', True),
    ('10.1000/other', False), ('https://doi.org/10.1000/other', False),
])
def test_doi_identity_all_literature_paths_are_atomic(wrapper, doi, accepted):
    state = kernel()
    source = evidence_payload(); source['identifiers']['doi'] = '10.1000/original'
    old_env = envelope(source, 'academic-source-verification', 'evidence-receipt-1.0')
    engine = IngestionEngine()
    assert engine.ingest(old_env, state).status == 'accepted'
    work = {'work_id': 'work:doi:10.1000/ORIGINAL', 'doi': doi,
            'work_type': 'article', 'title': 'Canonical', 'authors': []}
    payload = work if wrapper == 'direct' else {wrapper: [work] if wrapper == 'works' else work}
    env = envelope(payload, 'literature-analysis', 'canonical-work-1.0')
    before = state.to_dict()
    _, preflight = call_tool('research_artifact_validate', {'envelope': env.to_dict(), 'state': before})
    assert preflight['valid'] is accepted
    result = engine.ingest(env, state)
    assert (result.status == 'accepted') is accepted, result.failure_reason
    if accepted:
        assert state.objects['work:doi:10.1000/original']['title'] == 'Canonical'
        assert engine.ingest(old_env, reload_state(state)).status == 'accepted'
    else:
        assert state.to_dict() == before


@pytest.mark.parametrize('producer', ['academic-source-verification', 'retraction-watch'])
@pytest.mark.parametrize('ref', ['work:doi:10.1000/other', 'doi:10.1000/other', 'https://doi.org/10.1000/other'])
def test_doi_conflicts_in_evidence_and_retraction_refs(producer, ref):
    payload = evidence_payload() if producer == 'academic-source-verification' else {'doi': '10.1000/example', 'is_retracted': True, 'signals': []}
    schema = 'evidence-receipt-1.0' if producer == 'academic-source-verification' else 'retraction-alert-1.0'
    state = kernel(); before = state.to_dict()
    result = IngestionEngine().ingest(envelope(payload, producer, schema, subject_refs=[ref]), state)
    assert result.status == 'rejected' and 'DOI' in result.failure_reason
    assert state.to_dict() == before


def test_doi_retraction_target_and_registry_upgrade_cannot_conflict():
    state = kernel(); before = state.to_dict()
    env = envelope({'doi': '10.1000/a', 'target_work_id': 'work:doi:10.1000/b', 'is_retracted': True, 'signals': []},
                   'retraction-watch', 'retraction-alert-1.0')
    assert IngestionEngine().ingest(env, state).status == 'rejected'
    assert state.to_dict() == before
    with pytest.raises(ValueError, match='DOI'):
        state.register_object('work:doi:10.1000/a', {'work_type': 'article', 'title': 'Wrong', 'authors': [], 'doi': '10.1000/b'})


def test_title_only_work_remains_supported():
    env = envelope({'work_type': 'article', 'title': 'Title only', 'authors': []}, 'literature-analysis', 'canonical-work-1.0')
    state = kernel()
    assert IngestionEngine().ingest(env, state).status == 'accepted'
    assert 'work:Title only' in reload_state(state).objects


MISSING = 'absent'
@pytest.mark.parametrize('wrapped', [False, True])
@pytest.mark.parametrize('discrepancy', [MISSING, True, False])
@pytest.mark.parametrize('consistent', [MISSING, None, True, False])
def test_quantitative_complete_truth_table(wrapped, discrepancy, consistent):
    result = {'reported': 1, 'recomputed': 2, 'formula': 'difference', 'library': 'manual'}
    if discrepancy != MISSING: result['discrepancy_detected'] = discrepancy
    if consistent != MISSING: result['consistent'] = consistent
    payload = {'assertions': [result]} if wrapped else result
    env = envelope(payload, 'quantitative-paper-audit', 'quantitative-audit-1.0')
    conflict = isinstance(discrepancy, bool) and isinstance(consistent, bool) and discrepancy == consistent
    assert bool(validate_schema(payload, 'quantitative-audit.schema.json')) is conflict
    assert QuantitativePaperAuditAdapter().validate(env)[0] is not conflict
    state = kernel(); state.ceg.add_claim('q', 'Claim'); before = state.to_dict()
    receipt = IngestionEngine().ingest(env, state, {'claim_id': 'q'})
    if conflict:
        assert receipt.status == 'rejected' and state.to_dict() == before
    else:
        expected = ('contradicted' if discrepancy else 'supported') if isinstance(discrepancy, bool) else (
            ('supported' if consistent else 'contradicted') if isinstance(consistent, bool) else 'unverifiable')
        assert receipt.status == 'accepted', receipt.failure_reason
        assert state.ceg.support_edges[0].support_status == expected
        assert any(u['kind'] == 'quantitative_verification_gap' for u in state.uncertainties) is (expected == 'unverifiable')
        assert IngestionEngine().ingest(env, reload_state(state), {'claim_id': 'q'}).receipt_id == receipt.receipt_id


VALID_UNCERTAINTY = {'item_id': 'unc-test', 'subject_id': 'test', 'kind': 'generic_uncertainty',
                     'reason': 'Missing evidence', 'needs_human': True, 'metadata': {}}
@pytest.mark.parametrize('malformed', [
    {}, {k:v for k,v in VALID_UNCERTAINTY.items() if k != 'item_id'},
    {**VALID_UNCERTAINTY, 'item_id': 1}, {**VALID_UNCERTAINTY, 'item_id': ' '},
    {**VALID_UNCERTAINTY, 'metadata': []}, {**VALID_UNCERTAINTY, 'kind': 'unknown'},
    {**VALID_UNCERTAINTY, 'kind': []}, {**VALID_UNCERTAINTY, 'needs_human': 1},
    {**VALID_UNCERTAINTY, 'reason': ''}, {**VALID_UNCERTAINTY, 'extra': True},
])
def test_receipt_uncertainty_fails_at_boundary(malformed):
    env = envelope({'text': 'opaque'}, 'unknown', 'opaque-1')
    old = IngestionEngine().ingest(env, kernel())
    with pytest.raises((ValueError, TypeError)):
        forge_receipt(env, old, uncertainties=[malformed])
    raw = old.to_dict(); raw['uncertainties'] = [malformed]
    assert validate_schema(raw, 'artifact-ingestion-receipt.schema.json')
    with pytest.raises((ValueError, TypeError)):
        IngestionReceipt.from_dict(raw)
    with pytest.raises((ValueError, TypeError)):
        _normalise_uncertainty(malformed)


def test_uncertainty_bounded_json_and_shared_contract():
    value = {}; current = value
    for _ in range(70): current['nested'] = {}; current = current['nested']
    with pytest.raises(ValueError, match='depth'):
        _normalise_uncertainty({**VALID_UNCERTAINTY, 'metadata': value})
    with pytest.raises(ValueError):
        _normalise_uncertainty({**VALID_UNCERTAINTY, 'metadata': {'x': float('nan')}})
    root = Path(__file__).resolve().parents[1] / 'schemas'
    contracts = [json.loads((root / name).read_text())['properties']['uncertainties']['items']
                 for name in ('artifact-ingestion-receipt.schema.json', 'ingestion-kernel-state.schema.json')]
    assert contracts[0] == contracts[1]
    assert set(contracts[0]['properties']['kind']['enum']) == VALID_KERNEL_UNCERTAINTY_KINDS


@pytest.mark.parametrize('derived', [False, True])
def test_valid_uncertainty_receipt_roundtrip(derived):
    value = {**VALID_UNCERTAINTY, 'metadata': {'kernel_origin': 'domain_derived'} if derived else {}}
    env = envelope({'text': 'opaque'}, 'unknown', 'opaque-1')
    receipt = forge_receipt(env, IngestionEngine().ingest(env, kernel()), uncertainties=[value])
    assert IngestionReceipt.from_dict(receipt.to_dict()) == receipt


def removed_mutation_case(kind):
    state = kernel()
    if kind in {'object', 'artifact', 'source'}:
        env = envelope({'text': 'opaque'}, 'unknown', 'opaque-1')
    elif kind == 'physical_receipt':
        p = evidence_payload(); p.update(claims=[], query='', identifiers={})
        env = envelope(p, 'academic-source-verification', 'evidence-receipt-1.0')
    elif kind in {'uncertainty', 'derived_uncertainty'}:
        if kind == 'uncertainty':
            env = envelope({'is_retracted': True, 'doi': '10.1000/example', 'signals': []}, 'retraction-watch', 'retraction-alert-1.0')
        else:
            p = evidence_payload(); p['claims'][0]['support_status'] = 'unverifiable'
            env = envelope(p, 'academic-source-verification', 'evidence-receipt-1.0')
    elif kind.startswith('ceg_'):
        graph = ceg_mod.ClaimEvidenceGraph('source-graph')
        graph.add_claim('a', 'A'); graph.add_claim('b', 'B')
        graph.add_evidence('e', 'direct_observation')
        if kind == 'ceg_support': graph.add_support_edge('e', 'a', 'supported')
        if kind == 'ceg_relation': graph.add_claim_relation('a', 'b', 'corroborates')
        env = envelope(graph.to_dict(), 'claim-evidence-graph', 'claim-evidence-graph-1.0')
    else:
        ledger = ledger_mod.DecisionLedger('source-ledger')
        ledger.add_decision('a', 'A'); ledger.add_decision('b', 'B')
        if kind == 'ledger_basis': ledger.add_basis('b', 'decision', 'a')
        if kind == 'ledger_fork': ledger.add_fork('a', 'b')
        if kind == 'ledger_state_event': ledger.add_state_event('a', 'active')
        if kind == 'ledger_correction': ledger.add_outcome_correction('a', 'positive', 'Confirmed')
        env = envelope(ledger.to_dict(), 'decision-ledger', 'decision-ledger-1.0')
    original = IngestionEngine().ingest(env, state)
    assert original.status == 'accepted', original.failure_reason
    original_digests = state.compute_digests()
    if kind == 'object': state.objects.clear()
    elif kind == 'artifact': state.ingested_artifacts.clear()
    elif kind == 'source': state.ingestion_sources.clear()
    elif kind == 'physical_receipt':
        state.receipts.clear(); state.ceg._receipt_registry.clear(); state.ledger._receipts.clear()
    elif kind in {'uncertainty', 'derived_uncertainty'}: state.uncertainties.clear()
    elif kind.startswith('ceg_'):
        graph = ceg_mod.ClaimEvidenceGraph('source-graph')
        if kind != 'ceg_claim': graph.add_claim('a', 'A')
        graph.add_claim('b', 'B')
        if kind != 'ceg_evidence': graph.add_evidence('e', 'direct_observation')
        state.ceg = graph
    else:
        ledger = ledger_mod.DecisionLedger('source-ledger')
        if kind != 'ledger_decision': ledger.add_decision('a', 'A')
        ledger.add_decision('b', 'B'); state.ledger = ledger
    if kind not in {'uncertainty', 'derived_uncertainty'}:
        state.uncertainties = _domain_derived_uncertainties(state)
    # Delete every human-facing mutation list too, then legitimately recompute
    # the content-addressed receipt ID. Only source semantics know what is lost.
    forged = forge_receipt(env, original, created_or_reused_objects=[], ceg_nodes=[], ceg_edges=[],
                          ledger_bindings=[], uncertainties=[],
                          mutation_bindings=[b for b in original.mutation_bindings if b['kind'] not in {kind, 'derived_uncertainty'}])
    state.ingestion_receipts[next(iter(state.ingestion_receipts))] = forged
    return env, state, original_digests


@pytest.mark.parametrize('kind', ['object', 'physical_receipt', 'uncertainty', 'derived_uncertainty',
    'ceg_claim', 'ceg_evidence', 'ceg_support', 'ceg_relation', 'ledger_decision', 'ledger_basis',
    'ledger_fork', 'ledger_state_event', 'ledger_correction', 'artifact', 'source'])
def test_removed_state_and_resigned_cache_cannot_self_certify(kind):
    env, state, original_digests = removed_mutation_case(kind)
    # to_dict re-signs domain, content and snapshot hashes. Reload must still
    # fail on semantic invariants, never on a stale outer transport digest.
    with pytest.raises(ValueError, match='invariant'):
        reload_state(state)
    with pytest.raises(ValueError, match='invalid kernel'):
        IngestionEngine().ingest(env, state)
    # Explicit recovery discards the invalid cache, then replays the intact
    # source into the valid retained prefix; no accepted cache hit is reused.
    state.ingestion_receipts.clear(); state.ingestion_sources.clear()
    state.uncertainties = _domain_derived_uncertainties(state)
    repaired = IngestionEngine().ingest(env, state)
    assert repaired.status == 'accepted', repaired.failure_reason
    assert state.compute_digests() == original_digests
    assert reload_state(state).compute_digests() == original_digests


@pytest.mark.parametrize('change', ['payload', 'bindings', 'adapter', 'source_removed'])
def test_independent_source_is_bound_to_admission_context(change):
    state = kernel(); env = envelope({'text':'original'}, 'unknown', 'opaque-1')
    old = IngestionEngine().ingest(env, state); key = next(iter(state.ingestion_sources))
    source = json.loads(canonical_json_bytes(state.ingestion_sources[key]))
    if change == 'payload': source['envelope']['payload']['text'] = 'changed'
    elif change == 'bindings': source['bindings'] = {'claim_id': 'q'}
    elif change == 'adapter': source['envelope']['producer']['skill'] = 'academic-writing'
    else: state.ingestion_sources.clear()
    if change != 'source_removed': state.ingestion_sources[key] = source
    with pytest.raises(ValueError, match='invariant'):
        reload_state(state)


def test_cache_survives_append_only_state_and_old_snapshots():
    state = kernel(); engine = IngestionEngine(); first_env = graph_artifact()
    first = engine.ingest(first_env, state); assert first.status == 'accepted'
    state.ceg.add_claim('later', 'Later independent claim')
    second_env = envelope(state.ceg.to_dict(), 'claim-evidence-graph', 'claim-evidence-graph-1.0')
    assert engine.ingest(second_env, state).status == 'accepted'
    assert engine.ingest(first_env, reload_state(state)).receipt_id == first.receipt_id
    assert 'later' in state.ceg.claims


@pytest.mark.parametrize('field,identifier,matching,conflicting', [
    ('arxiv_id', 'https://arxiv.org/abs/2106.09624', 'work:arxiv:2106.09624', 'work:arxiv:2106.09625'),
    ('pmid', 'https://pubmed.ncbi.nlm.nih.gov/123/', 'work:pmid:123', 'work:pmid:124'),
    ('openalex_id', 'https://openalex.org/w123', 'work:openalex:W123', 'work:openalex:W124'),
])
@pytest.mark.parametrize('conflict', [False, True])
def test_adjacent_external_identity_fields_must_agree(field, identifier, matching, conflicting, conflict):
    payload = evidence_payload(); payload['identifiers'] = {field: identifier}
    env = envelope(payload, 'academic-source-verification', 'evidence-receipt-1.0',
                   subject_refs=[conflicting if conflict else matching])
    state = kernel(); before = state.to_dict()
    receipt = IngestionEngine().ingest(env, state)
    assert (receipt.status == 'rejected') is conflict, receipt.failure_reason
    if conflict: assert state.to_dict() == before
    else: assert matching in state.objects


def test_resolver_url_cannot_disagree_with_canonical_work_doi():
    env = envelope({'work_type': 'article', 'title': 'Paper', 'authors': [],
                    'doi': '10.1000/a', 'url': 'https://doi.org/10.1000/b'},
                   'literature-analysis', 'canonical-work-1.0')
    result = IngestionEngine().ingest(env, kernel())
    assert result.status == 'rejected' and 'DOI' in result.failure_reason


def test_receipt_duplicate_uncertainty_and_malformed_mutation_fail_at_boundary():
    env = envelope({'text': 'opaque'}, 'unknown', 'opaque-1')
    old = IngestionEngine().ingest(env, kernel())
    with pytest.raises(ValueError, match='unique'):
        forge_receipt(env, old, uncertainties=[VALID_UNCERTAINTY, VALID_UNCERTAINTY])
    with pytest.raises(ValueError, match='require'):
        forge_receipt(env, old, mutation_bindings=[{}])


def test_cached_lineage_cannot_delete_its_independent_source_reference():
    from test_ingestion_hardening import ReceiptRef, mcp_server
    graph = mcp_server.prov_mod.LineageGraph(); graph.add_entity('entity', 'data_snapshot')
    physical = mcp_server.prov_mod.trace_origin(graph, 'entity', check_on_disk_hashes=False).to_dict()
    ref = ReceiptRef(kind='lineage', schema_version='lineage-receipt-1.0',
                     receipt_id=physical['receipt_id'], receipt_digest=physical['receipt_digest'])
    env = envelope({'text': 'opaque'}, 'unknown', 'opaque-1', lineage_ref=ref)
    state = kernel(); old = IngestionEngine().ingest(env, state)
    assert old.status == 'accepted' and state.uncertainties
    modified = env.to_dict(); modified.pop('lineage_ref')
    forged = forge_receipt(type(env).from_dict(modified), old, uncertainties=[],
                          mutation_bindings=[b for b in old.mutation_bindings if b['kind'] != 'derived_uncertainty'])
    state.ingestion_receipts[next(iter(state.ingestion_receipts))] = forged
    state.uncertainties.clear()
    with pytest.raises(ValueError, match='invariant'):
        reload_state(state)
