"""Transactional ingestion engine for scholarly research artifacts."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from .contracts import validate_adapter_contract
from .models import ArtifactEnvelope, IngestionKernelState, IngestionReceipt
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
        valid, state_errors = target_state.validate_invariants()
        if not valid:
            raise ValueError(
                "Cannot ingest into an invalid kernel state: " + "; ".join(state_errors)
            )

        parsed: List[ArtifactEnvelope] = []
        for raw in envelopes:
            env = raw if isinstance(raw, ArtifactEnvelope) else ArtifactEnvelope.from_dict(raw)
            env.assert_integrity()
            parsed.append(env)

        staged = target_state.clone()
        results: Dict[int, IngestionReceipt] = {}
        adapters: Dict[int, Any] = {}
        failure: Optional[Tuple[int, List[str]]] = None

        for index, env in enumerate(parsed):
            bindings = bindings_list[index] if bindings_list is not None else None
            cache_key = f"{env.artifact_id}:{env.ingestion_context_digest(bindings)}"

            registered_sha = staged.ingested_artifacts.get(env.artifact_id)
            if registered_sha is not None and registered_sha != env.payload_sha256:
                raise ValueError(
                    f"Hash collision for artifact {env.artifact_id!r}: registered "
                    f"{registered_sha}, incoming {env.payload_sha256}"
                )
            cached = staged.ingestion_receipts.get(cache_key)
            if cached is not None:
                results[index] = cached
                continue

            adapter = self.registry.resolve(env)
            adapters[index] = adapter
            contract_errors = validate_adapter_contract(env, adapter)
            if contract_errors:
                failure = (index, contract_errors)
                results[index] = self._rejected(env, adapter, staged, contract_errors)
                if atomic:
                    break
                continue

            before = staged.clone()
            try:
                plan = adapter.plan(env, staged, bindings)
                if not plan.valid:
                    raise ValueError("; ".join(plan.errors) or "Adapter validation failed")

                # The current artifact is first-class state and contributes to
                # the success receipt's output digest.
                staged.ingested_artifacts[env.artifact_id] = env.payload_sha256
                receipt = adapter.apply(plan, staged)
                if receipt.status != "accepted":
                    raise ValueError(receipt.failure_reason or "Adapter rejected the artifact")
                staged.ingestion_receipts[cache_key] = receipt

                valid, invariant_errors = staged.validate_invariants()
                if not valid:
                    raise ValueError(
                        "Post-cache kernel invariant failure: " + "; ".join(invariant_errors)
                    )
                results[index] = receipt
            except Exception as exc:
                staged = before
                errors = [str(exc)]
                results[index] = self._rejected(env, adapter, staged, errors)
                failure = (index, errors)
                if atomic:
                    break

        if atomic and failure is not None:
            failed_index, failed_errors = failure
            aborted_results: Dict[int, IngestionReceipt] = {}
            for index, env in enumerate(parsed):
                bindings = bindings_list[index] if bindings_list is not None else None
                cache_key = f"{env.artifact_id}:{env.ingestion_context_digest(bindings)}"
                cached = target_state.ingestion_receipts.get(cache_key)
                if cached is not None:
                    aborted_results[index] = cached
                    continue
                adapter = adapters.get(index) or self.registry.resolve(env)
                errors = (
                    failed_errors
                    if index == failed_index
                    else [f"Atomic batch aborted because artifact index {failed_index} failed"]
                )
                aborted_results[index] = self._rejected(env, adapter, target_state, errors)
            return [aborted_results[i] for i in range(len(parsed))], target_state

        final_state = staged if dry_run else target_state
        if not dry_run:
            self._commit(staged, target_state)
        return [results[i] for i in range(len(parsed))], final_state
