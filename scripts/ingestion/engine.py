"""Transactional Ingestion Engine for scholarly research artifacts."""

from __future__ import annotations

import collections.abc
import copy
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from .models import ArtifactEnvelope, IngestionKernelState, IngestionReceipt
from .registry import AdapterRegistry, create_default_registry

MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB fail-closed boundary
MAX_BATCH_SIZE = 1000  # Maximum envelopes per batch transaction


class IngestionEngine:
    """Deterministic, transactional ingestion engine connecting artifacts to the kernel."""

    def __init__(self, registry: Optional[AdapterRegistry] = None):
        self.registry = registry or create_default_registry()
        self._ingested_artifacts: Dict[str, str] = {}  # artifact_id -> payload_sha256
        self._ingestion_receipts: Dict[str, IngestionReceipt] = {}  # artifact_id -> receipt

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

        receipts: List[IngestionReceipt] = []
        parsed_envelopes: List[ArtifactEnvelope] = []

        # 1. Parse and validate envelopes and check collision boundaries
        for idx, env_raw in enumerate(envelopes):
            if isinstance(env_raw, ArtifactEnvelope):
                env = env_raw
            else:
                env = ArtifactEnvelope.from_dict(env_raw)

            # Payload size bound check
            p_bytes = len(str(env.payload).encode("utf-8"))
            if p_bytes > MAX_PAYLOAD_BYTES:
                raise ValueError(f"Envelope {env.artifact_id} payload size ({p_bytes} bytes) exceeds limit of {MAX_PAYLOAD_BYTES} bytes.")

            # Idempotency & Collision check
            prev_sha = self._ingested_artifacts.get(env.artifact_id)
            if prev_sha is not None:
                if prev_sha != env.payload_sha256:
                    raise ValueError(
                        f"Hash collision detected for artifact '{env.artifact_id}': "
                        f"registered payload SHA {prev_sha} conflicts with incoming {env.payload_sha256}."
                    )
                # Idempotent replay: return cached receipt if state has not mutated
                if env.artifact_id in self._ingestion_receipts:
                    receipts.append(self._ingestion_receipts[env.artifact_id])
                    continue

            parsed_envelopes.append(env)

        # 2. Plan and evaluate each envelope
        plans = []
        batch_failed = False
        first_failure_error = None

        for idx, env in enumerate(parsed_envelopes):
            bindings = bindings_list[idx] if (bindings_list and idx < len(bindings_list)) else None
            adapter = self.registry.resolve(env)
            plan = adapter.plan(env, staged_state, bindings)

            if not plan.valid:
                batch_failed = True
                first_failure_error = plan.errors[0] if plan.errors else "Adapter validation failed"
                if atomic:
                    break

            plans.append((adapter, plan))

        # 3. If atomic and any failed, abort entire batch
        if atomic and batch_failed:
            # Emit rejected receipts without modifying state
            rejected_receipts = []
            for env in parsed_envelopes:
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
                rejected_receipts.append(r)
            return rejected_receipts, target_state

        # 4. Apply all plans to staged state
        for adapter, plan in plans:
            receipt = adapter.apply(plan, staged_state)
            receipts.append(receipt)
            if receipt.status == "accepted" and not dry_run:
                self._ingested_artifacts[receipt.source_artifact_id] = receipt.source_artifact_sha256
                self._ingestion_receipts[receipt.source_artifact_id] = receipt

        # 5. Commit to target_state if not dry_run
        if not dry_run:
            target_state.ceg = staged_state.ceg
            target_state.ledger = staged_state.ledger
            target_state.objects = staged_state.objects
            target_state.receipts = staged_state.receipts
            return receipts, target_state

        return receipts, staged_state
