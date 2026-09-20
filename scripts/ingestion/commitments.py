"""Canonical commitments to retained mutations, separate from transport hashes."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from shared_contracts.evidence import _thaw_val, canonical_json_bytes, compute_sha256


MUTATION_KINDS = (
    "object", "physical_receipt", "artifact", "uncertainty", "derived_uncertainty",
    "ceg_container", "ceg_claim", "ceg_evidence", "ceg_support", "ceg_relation",
    "ledger_container", "ledger_decision", "ledger_basis", "ledger_fork",
    "ledger_state_event", "ledger_correction",
)


def record_digest(record: Any) -> str:
    return compute_sha256(canonical_json_bytes(_thaw_val(record)))


def mutation_inventory(state: Any) -> Dict[Tuple[str, str], Any]:
    """Index semantic records without mutable summaries or circular cache data.

    Containers commit their protocol and identity. Their inner records are
    committed individually so later append-only ingestions remain valid.
    Records without a separate stable ID use their complete canonical digest.
    Lineage emission timestamps are the sole physical-receipt normalization.
    """
    records: Dict[Tuple[str, str], Any] = {}
    for key, value in state.objects.items():
        records[("object", key)] = _thaw_val(value)
    for key, value in state.receipts.items():
        value = _thaw_val(value)
        if value.get("protocol") == "lineage-receipt-1.0":
            value.pop("timestamp", None)
        records[("physical_receipt", key)] = value
    for key, sha in state.ingested_artifacts.items():
        records[("artifact", key)] = {"artifact_id": key, "payload_sha256": sha}
    for value in state.uncertainties:
        raw = _thaw_val(value)
        derived = raw.get("metadata", {}).get("kernel_origin") in {
            "domain_derived", "envelope_lineage",
        }
        records[("derived_uncertainty" if derived else "uncertainty", raw["item_id"])] = raw
    for domain, obj, id_field, collections in (
        ("ceg", state.ceg, "graph_id", (
            ("claims", "claim", "id"), ("evidence_anchors", "evidence", "id"),
            ("support_edges", "support", None), ("claim_relations", "relation", None),
        )),
        ("ledger", state.ledger, "ledger_id", (
            ("decisions", "decision", "id"), ("bases", "basis", None),
            ("forks", "fork", None), ("state_events", "state_event", "event_id"),
            ("corrections", "correction", "correction_id"),
        )),
    ):
        if obj is None:
            continue
        data = obj.to_dict()
        records[(domain + "_container", data[id_field])] = {
            "protocol": data["protocol"], id_field: data[id_field],
        }
        for field, kind, identity in collections:
            for record in data[field]:
                records[(domain + "_" + kind, record[identity] if identity else record_digest(record))] = record
    return records


def bind_mutations(before: Mapping, state: Any, plan: Any) -> list:
    """Commit changes plus every existing record explicitly adopted by a plan."""
    after = mutation_inventory(state)
    selected = {key for key, value in after.items()
                if key not in before or record_digest(value) != record_digest(before[key])}
    selected.update(("object", key) for key in plan.created_objects)
    selected.update(("physical_receipt", key) for key in plan.registered_receipts)
    selected.add(("artifact", plan.envelope.artifact_id))
    # A domain mutation consumes its physical registry. Commit the available
    # evidence as well as record references, including adopted snapshots.
    if plan.has_ceg_mutations() or plan.has_ledger_mutations():
        selected.update(key for key in after if key[0] == "physical_receipt")
    ref = plan.envelope.lineage_ref
    if ref is not None and ref.receipt_id in state.receipts:
        selected.add(("physical_receipt", ref.receipt_id))
    for domain, snapshot, changes in (
        ("ceg", plan.ceg_snapshot, plan.has_ceg_mutations()),
        ("ledger", plan.ledger_snapshot, plan.has_ledger_mutations()),
    ):
        if snapshot is not None:
            selected.update(key for key in after if key[0].startswith(domain + "_"))
        elif changes:
            selected.update(key for key in after if key[0] == domain + "_container")
    selected.update(("ceg_claim", value["id"]) for value in plan.ceg_claims)
    selected.update(("ceg_evidence", value["id"]) for value in plan.ceg_evidences)
    # New records above cover relation/edge APIs; identical adopted records are
    # also committed. Content-addressed records cannot be replaced under an ID.
    if plan.ceg_edges or plan.ceg_relations:
        selected.update(key for key in after if key[0] in {"ceg_support", "ceg_relation"})
    if plan.has_ledger_mutations():
        selected.update(key for key in after if key[0].startswith("ledger_"))
    for uncertainty in plan.uncertainties:
        selected.update(key for key in after if key[0] in {"uncertainty", "derived_uncertainty"}
                        and key[1] == uncertainty["item_id"])
    return [{"kind": kind, "identity": identity, "canonical_digest": record_digest(after[(kind, identity)])}
            for kind, identity in sorted(selected)]


def commitment_errors(state: Any, inventory: Mapping) -> list:
    """Validate immutable observations and explicitly recomputable projections."""
    from .adapters import _domain_derived_uncertainties

    derived = {value["item_id"]: value for value in _domain_derived_uncertainties(state)}
    canonical_upgrades = {
        (binding["identity"], binding["canonical_digest"])
        for receipt in state.ingestion_receipts.values()
        if receipt.adapter_id == "adapter-literature-analysis" and receipt.status == "accepted"
        for binding in receipt.mutation_bindings if binding["kind"] == "object"
    }
    errors = []
    for cache_key, receipt in state.ingestion_receipts.items():
        bindings = receipt.mutation_bindings
        bound_keys = {(b["kind"], b["identity"]) for b in bindings}
        required = {("artifact", receipt.source_artifact_id)}
        required.update(("object", key) for key in receipt.created_or_reused_objects)
        for node in receipt.ceg_nodes:
            required.update(key for key in inventory if key[1] == node and key[0] in {"ceg_claim", "ceg_evidence"})
        required.update(("ceg_support", key) for key in receipt.ceg_edges)
        for value in receipt.uncertainties:
            kind = "derived_uncertainty" if value.get("metadata", {}).get("kernel_origin") in {
                "domain_derived", "envelope_lineage",
            } else "uncertainty"
            required.add((kind, value["item_id"]))
        if not required <= bound_keys:
            errors.append(f"Ingestion receipt cache {cache_key!r} lacks complete mutation bindings")
        for binding in bindings:
            kind, identity, expected = binding["kind"], binding["identity"], binding["canonical_digest"]
            actual = inventory.get((kind, identity))
            if kind == "derived_uncertainty":
                # A live projection may disappear only when its causal domain
                # condition no longer exists. History stays in the receipt.
                current = derived.get(identity)
                if current is None and actual is None:
                    continue
                if current is None or actual is None or record_digest(current) != record_digest(actual):
                    errors.append(f"Ingestion receipt cache {cache_key!r} has altered derived uncertainty {identity!r}")
                    continue
            if actual is not None and record_digest(actual) == expected:
                continue
            # The only object upgrade is the exact minimal work placeholder to
            # a schema-validated literature work, itself bound by its ingestion.
            if (kind == "object" and actual is not None
                and expected == record_digest({"id": identity, "kind": "work"})
                and all(key in actual for key in ("work_type", "title", "authors"))
                and (identity, record_digest(actual)) in canonical_upgrades):
                continue
            errors.append(f"Ingestion receipt cache {cache_key!r} mutation commitment mismatch: {kind} {identity!r}")
    return errors
