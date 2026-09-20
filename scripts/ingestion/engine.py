"""Transactional Ingestion Engine for scholarly research artifacts."""

from __future__ import annotations

import collections.abc
import copy
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from shared_contracts.evidence import canonical_json_bytes, compute_sha256, _thaw_val
from .models import ArtifactEnvelope, IngestionKernelState, IngestionReceipt
from .registry import AdapterRegistry, create_default_registry

MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB fail-closed boundary
MAX_BATCH_SIZE = 1000  # Maximum envelopes per batch transaction


class IngestionEngine:
    """Deterministic, transactional ingestion engine connecting artifacts to the kernel."""

    def __init__(self, registry: Optional[AdapterRegistry] = None):
        self.registry = registry or create_default_registry()

    def ingest(
        self,
        envelope: Union[ArtifactEnvelope, Mapping[str, Any]],
        state: Optional[IngestionKernelState] = None,
        bindings: Optional[Mapping[str, Any]] = None,
        dry_run: bool = False,
    ) -> IngestionReceipt:
        """Ingest a single scholarly artifact envelope with transaction safety."""
        receipts, _ = self.batch_ingest(
            envelopes=[envelope],
            state=state,
            bindings_list=[bindings] if bindings else None,
            dry_run=dry_run,
            atomic=True,
        )
        return receipts[0]

    def batch_ingest(
        self,
        envelopes: List[Union[ArtifactEnvelope, Mapping[str, Any]]],
        state: Optional[IngestionKernelState] = None,
        bindings_list: Optional[List[Optional[Mapping[str, Any]]]] = None,
        dry_run: bool = False,
        atomic: bool = True,
    ) -> Tuple[List[IngestionReceipt], IngestionKernelState]:
        """Ingest a batch of envelopes with strict atomicity and idempotency guarantees."""
        if len(envelopes) > MAX_BATCH_SIZE:
            raise ValueError(f"Batch size {len(envelopes)} exceeds maximum limit of {MAX_BATCH_SIZE}.")

        target_state = state if state is not None else IngestionKernelState()
        # Working clone for staging atomic transactions
        staged_state = target_state.clone()

        # Output receipts aligned with input envelopes order
        results_by_index: Dict[int, IngestionReceipt] = {}
        pending_work: List[Tuple[int, ArtifactEnvelope, str]] = []  # (orig_idx, env, cache_key)

        # 1. Parse and validate envelopes and evaluate state-scoped idempotency
        for orig_idx, env_raw in enumerate(envelopes):
            if isinstance(env_raw, ArtifactEnvelope):
                env = env_raw
            else:
                env = ArtifactEnvelope.from_dict(env_raw)

            # Payload size bound check on canonical UTF-8 bytes
            p_bytes = len(canonical_json_bytes(_thaw_val(env.payload)))
            if p_bytes > MAX_PAYLOAD_BYTES:
                raise ValueError(
                    f"Envelope {env.artifact_id} payload size ({p_bytes} bytes) exceeds limit of {MAX_PAYLOAD_BYTES} bytes."
                )

            bindings = bindings_list[orig_idx] if (bindings_list and orig_idx < len(bindings_list)) else None
            binding_sha = compute_sha256(canonical_json_bytes(_thaw_val(bindings or {})))
            cache_key = f"{env.artifact_id}:{binding_sha}"

            # Check collision: same artifact ID with differing payload in target_state
            if env.artifact_id in target_state.ingested_artifacts:
                registered_sha = target_state.ingested_artifacts[env.artifact_id]
                if registered_sha != env.payload_sha256:
                    raise ValueError(
                        f"Hash collision detected for artifact '{env.artifact_id}': "
                        f"registered payload SHA {registered_sha} conflicts with incoming {env.payload_sha256}."
                    )
                # Idempotent replay: if exact artifact + binding was already processed in this state
                if cache_key in target_state.ingestion_receipts:
                    results_by_index[orig_idx] = target_state.ingestion_receipts[cache_key]
                    continue

            pending_work.append((orig_idx, env, cache_key))

        # 2. Plan and evaluate each pending envelope
        plans = []
        batch_failed = False
        first_failure_error = None

        for orig_idx, env, cache_key in pending_work:
            bindings = bindings_list[orig_idx] if (bindings_list and orig_idx < len(bindings_list)) else None
            adapter = self.registry.resolve(env)
            plan = adapter.plan(env, staged_state, bindings)

            if not plan.valid:
                batch_failed = True
                first_failure_error = plan.errors[0] if plan.errors else "Adapter validation failed"
                if atomic:
                    break

            plans.append((orig_idx, env, cache_key, adapter, plan))

        # 3. If atomic and any failed, abort entire batch without modifying target state
        if atomic and batch_failed:
            rejected_receipts: List[IngestionReceipt] = []
            for orig_idx, env, _ in pending_work:
                adapter = self.registry.resolve(env)
                r = IngestionReceipt.create(
                    envelope=env,
                    adapter_id=adapter.adapter_id,
                    adapter_version=adapter.adapter_version,
                    status="rejected",
                    valid=False,
                    errors=[first_failure_error or "Batch transaction aborted"],
                    output_digests=target_state.compute_digests(),
                    failure_reason=first_failure_error or "Batch transaction aborted",
                )
                results_by_index[orig_idx] = r

            ordered_receipts = [results_by_index[i] for i in range(len(envelopes))]
            return ordered_receipts, target_state

        # 4. Apply all plans to staged state and stage cache updates
        staged_cache_updates: List[Tuple[str, str, str, IngestionReceipt]] = []
        for orig_idx, env, cache_key, adapter, plan in plans:
            receipt = adapter.apply(plan, staged_state)
            results_by_index[orig_idx] = receipt
            if receipt.status == "accepted":
                staged_cache_updates.append((
                    cache_key,
                    receipt.source_artifact_id,
                    receipt.source_artifact_sha256,
                    receipt,
                ))

        # 5. Commit to target_state only after all applies succeed (atomic commit)
        if not dry_run:
            target_state.ceg = staged_state.ceg
            target_state.ledger = staged_state.ledger
            target_state.objects = staged_state.objects
            target_state.receipts = staged_state.receipts
            target_state.uncertainties = staged_state.uncertainties
            for c_key, art_id, art_sha, r in staged_cache_updates:
                target_state.ingested_artifacts[art_id] = art_sha
                target_state.ingestion_receipts[c_key] = r

            ordered_receipts = [results_by_index[i] for i in range(len(envelopes))]
            return ordered_receipts, target_state

        ordered_receipts = [results_by_index[i] for i in range(len(envelopes))]
        return ordered_receipts, staged_state
