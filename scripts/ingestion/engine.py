"""Transactional ingestion engine for scholarly research artifacts."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

if __package__ and __package__.startswith("academic_research_kernel"):
    from academic_research_kernel.shared_contracts.evidence import FrozenJSONMap, validate_lineage_receipt_contract
else:
    from shared_contracts.evidence import FrozenJSONMap, validate_lineage_receipt_contract

from .contracts import validate_adapter_contract
from .models import (
    ArtifactEnvelope,
    IngestionKernelState,
    IngestionReceipt,
    lineage_ref_uncertainty_dict,
)
from .registry import AdapterRegistry, create_default_registry


MAX_BATCH_SIZE = 1000


class IngestionEngine:
    """Deterministic, fail-closed bridge from artifacts to kernel state."""

    def __init__(self, registry: Optional[AdapterRegistry] = None):
        self.registry = registry or create_default_registry()

    def ingest(
        self,
        envelope: Union[ArtifactEnvelope, Mapping[str, Any]],
        state: Optional[IngestionKernelState] = None,
        bindings: Optional[Mapping[str, Any]] = None,
        dry_run: bool = False,
    ) -> IngestionReceipt:
        receipts, _ = self.batch_ingest(
            envelopes=[envelope],
            state=state,
            bindings_list=[bindings],
            dry_run=dry_run,
            atomic=True,
        )
        return receipts[0]

    @staticmethod
    def _rejected(
        envelope: ArtifactEnvelope,
        adapter: Any,
        state: IngestionKernelState,
        errors: List[str],
        ingestion_context_digest: Optional[str] = None,
    ) -> IngestionReceipt:
        reason = "; ".join(errors) or "Artifact ingestion rejected"
        return IngestionReceipt.create(
            envelope=envelope,
            adapter_id=adapter.adapter_id,
            adapter_version=adapter.adapter_version,
            status="rejected",
            valid=False,
            errors=errors or [reason],
            output_digests=state.compute_digests(),
            ingestion_context_digest=ingestion_context_digest,
            failure_reason=reason,
            caller_metadata=envelope.caller_metadata,
        )

    @staticmethod
    def _commit(source: IngestionKernelState, target: IngestionKernelState) -> None:
        target.ceg = source.ceg
        target.ledger = source.ledger
        target.objects = source.objects
        target.receipts = source.receipts
        target.uncertainties = source.uncertainties
        target.ingested_artifacts = source.ingested_artifacts
        target.ingestion_receipts = source.ingestion_receipts
        target.ingestion_sources = source.ingestion_sources

    def batch_ingest(
        self,
        envelopes: List[Union[ArtifactEnvelope, Mapping[str, Any]]],
        state: Optional[IngestionKernelState] = None,
        bindings_list: Optional[List[Optional[Mapping[str, Any]]]] = None,
        dry_run: bool = False,
        atomic: bool = True,
    ) -> Tuple[List[IngestionReceipt], IngestionKernelState]:
        """Ingest a bounded batch, committing only invariant-valid state."""
        if len(envelopes) > MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(envelopes)} exceeds maximum limit of {MAX_BATCH_SIZE}"
            )
        if bindings_list is not None and len(bindings_list) != len(envelopes):
            raise ValueError("bindings_list length must exactly match envelopes length")

        target_state = state if state is not None else IngestionKernelState()
        staged = target_state.clone()
        valid, state_errors = staged.validate_invariants()
        if not valid:
            raise ValueError(
                "Cannot ingest into an invalid kernel state: " + "; ".join(state_errors)
            )

        parsed: List[ArtifactEnvelope] = []
        for raw in envelopes:
            env = raw if isinstance(raw, ArtifactEnvelope) else ArtifactEnvelope.from_dict(raw)
            env.assert_integrity()
            parsed.append(env)

        results: Dict[int, IngestionReceipt] = {}
        adapters: Dict[int, Any] = {}
        cache_keys: Dict[int, str] = {}
        context_digests: Dict[int, str] = {}
        failure: Optional[Tuple[int, List[str]]] = None

        for index, env in enumerate(parsed):
            raw_bindings = bindings_list[index] if bindings_list is not None else None
            adapter = self.registry.resolve(env)
            adapters[index] = adapter
            registered_sha = staged.ingested_artifacts.get(env.artifact_id)
            if registered_sha is not None and registered_sha != env.payload_sha256:
                raise ValueError(
                    f"Hash collision for artifact {env.artifact_id!r}: registered "
                    f"{registered_sha}, incoming {env.payload_sha256}"
                )
            try:
                bindings = adapter.normalize_bindings(raw_bindings)
            except Exception as exc:
                errors = [str(exc)]
                results[index] = self._rejected(env, adapter, staged, errors)
                failure = (index, errors)
                if atomic:
                    break
                continue
            context_digest = env.ingestion_context_digest(bindings)
            context_digests[index] = context_digest
            cache_key = f"{env.artifact_id}:{context_digest}"
            cache_keys[index] = cache_key

            cached = staged.ingestion_receipts.get(cache_key)
            if cached is not None:
                results[index] = cached.with_caller_metadata(env.caller_metadata)
                continue

            contract_errors = validate_adapter_contract(env, adapter)
            if contract_errors:
                failure = (index, contract_errors)
                results[index] = self._rejected(
                    env,
                    adapter,
                    staged,
                    contract_errors,
                    context_digest,
                )
                if atomic:
                    break
                continue

            before = staged.clone()
            try:
                plan = adapter.plan(env, staged, bindings)
                if not plan.valid:
                    raise ValueError("; ".join(plan.errors) or "Adapter validation failed")

                if env.lineage_ref is not None:
                    receipt_id = env.lineage_ref.receipt_id
                    if receipt_id in plan.registered_receipts:
                        physical = plan.registered_receipts[receipt_id]
                    elif receipt_id in staged.receipts:
                        physical = staged.receipts[receipt_id]
                    else:
                        physical = None
                    if physical is None:
                        plan.uncertainties.append(
                            lineage_ref_uncertainty_dict(
                                env.artifact_id,
                                env.lineage_ref,
                            )
                        )
                    else:
                        lineage_ok, lineage_error = validate_lineage_receipt_contract(
                            env.lineage_ref,
                            physical,
                            verification_context=staged.verification_context,
                        )
                        if not lineage_ok:
                            raise ValueError(
                                "Envelope lineage_ref verification failed: "
                                f"{lineage_error}"
                            )

                # The current artifact is first-class state and contributes to
                # the success receipt's output digest.
                staged.ingested_artifacts[env.artifact_id] = env.payload_sha256
                receipt = adapter.apply(plan, staged, context_digest)
                if receipt.status != "accepted":
                    raise ValueError(receipt.failure_reason or "Adapter rejected the artifact")
                staged.ingestion_receipts[cache_key] = receipt
                source_envelope = env.to_dict()
                source_envelope.pop("caller_metadata", None)
                staged.ingestion_sources[cache_key] = FrozenJSONMap({
                    "envelope": source_envelope, "bindings": bindings or {},
                })

                valid, invariant_errors = staged.validate_invariants()
                if not valid:
                    raise ValueError(
                        "Post-cache kernel invariant failure: " + "; ".join(invariant_errors)
                    )
                results[index] = receipt
            except Exception as exc:
                staged = before
                errors = [str(exc)]
                results[index] = self._rejected(
                    env,
                    adapter,
                    staged,
                    errors,
                    context_digest,
                )
                failure = (index, errors)
                if atomic:
                    break

        if atomic and failure is not None:
            failed_index, failed_errors = failure
            aborted_results: Dict[int, IngestionReceipt] = {}
            for index, env in enumerate(parsed):
                adapter = adapters.get(index) or self.registry.resolve(env)
                adapters[index] = adapter
                cache_key = cache_keys.get(index)
                if cache_key is None and index != failed_index:
                    raw_bindings = bindings_list[index] if bindings_list is not None else None
                    try:
                        bindings = adapter.normalize_bindings(raw_bindings)
                    except Exception:
                        bindings = None
                    else:
                        context_digest = env.ingestion_context_digest(bindings)
                        context_digests[index] = context_digest
                        cache_key = f"{env.artifact_id}:{context_digest}"
                cached = (
                    target_state.ingestion_receipts.get(cache_key)
                    if cache_key is not None
                    else None
                )
                if cached is not None:
                    aborted_results[index] = cached.with_caller_metadata(
                        env.caller_metadata
                    )
                    continue
                errors = (
                    failed_errors
                    if index == failed_index
                    else [f"Atomic batch aborted because artifact index {failed_index} failed"]
                )
                aborted_results[index] = self._rejected(
                    env,
                    adapter,
                    target_state,
                    errors,
                    context_digests.get(index),
                )
            return [aborted_results[i] for i in range(len(parsed))], target_state

        final_state = staged if dry_run else target_state
        if not dry_run:
            self._commit(staged, target_state)
        return [results[i] for i in range(len(parsed))], final_state
