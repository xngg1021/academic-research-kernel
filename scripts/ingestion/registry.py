"""Registry of deterministic scholarly artifact adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .adapters import (
    BaseArtifactAdapter,
    AcademicSourceVerificationAdapter,
    ResearchObjectIdentityAdapter,
    ClaimEvidenceGraphSnapshotAdapter,
    DecisionLedgerSnapshotAdapter,
    QuantitativePaperAuditAdapter,
    ResearchReproducibilityAdapter,
    CrossReviewAdapter,
    SystematicReviewAdapter,
    LiteratureAnalysisAdapter,
    LiteratureWatchAdapter,
    RetractionWatchAdapter,
    MathComputationAdapter,
    AcademicWritingAdapter,
    OpaqueFallbackAdapter,
)
from .models import ArtifactEnvelope


class AdapterRegistry:
    """Registry maintaining prioritized adapters for scholarly artifact ingestion."""

    def __init__(self):
        self._adapters: List[BaseArtifactAdapter] = []

    def register(self, adapter: BaseArtifactAdapter) -> None:
        if any(existing.adapter_id == adapter.adapter_id for existing in self._adapters):
            raise ValueError(f"Duplicate adapter_id registration: {adapter.adapter_id}")
        self._adapters.append(adapter)
        # Keep sorted by tier (1 before 2 before 3)
        self._adapters.sort(key=lambda a: a.tier)

    def resolve(self, envelope: ArtifactEnvelope) -> BaseArtifactAdapter:
        """Resolve deterministically, preferring declared producer then schema."""
        structured = [
            adapter for adapter in self._adapters
            if adapter.adapter_id != "adapter-opaque-fallback"
        ]
        producer = envelope.producer.get("skill")
        producer_matches = [a for a in structured if producer in a.accepted_producers]
        if len(producer_matches) > 1:
            raise ValueError(
                f"Ambiguous producer routing for {producer!r}: "
                f"{[a.adapter_id for a in producer_matches]}"
            )
        if producer_matches:
            # Return the producer owner even on a schema mismatch so runtime
            # admission rejects it instead of silently degrading to opaque.
            return producer_matches[0]

        schema_matches = [
            a for a in structured if envelope.payload_schema in a.accepted_schemas
        ]
        if len(schema_matches) > 1:
            raise ValueError(
                f"Ambiguous schema routing for {envelope.payload_schema!r}: "
                f"{[a.adapter_id for a in schema_matches]}"
            )
        if schema_matches:
            return schema_matches[0]

        legacy_matches = [a for a in structured if a.probe(envelope)]
        if len(legacy_matches) > 1:
            raise ValueError(
                f"Ambiguous legacy adapter routing: {[a.adapter_id for a in legacy_matches]}"
            )
        if legacy_matches:
            return legacy_matches[0]
        return next(
            (a for a in self._adapters if a.adapter_id == "adapter-opaque-fallback"),
            OpaqueFallbackAdapter(),
        )

    def export_matrix(self) -> List[Dict[str, Any]]:
        """Export machine-readable adapter capability matrix."""
        matrix = []
        for a in self._adapters:
            matrix.append({
                "adapter_id": a.adapter_id,
                "adapter_version": a.adapter_version,
                "tier": a.tier,
                "is_lossless": a.is_lossless,
                "accepted_producers": sorted(list(a.accepted_producers)),
                "accepted_schemas": sorted(list(a.accepted_schemas)),
            })
        return matrix


def create_default_registry() -> AdapterRegistry:
    """Create and return the standard registry with all 13 scholarly skill adapters."""
    reg = AdapterRegistry()
    # Tier 1
    reg.register(AcademicSourceVerificationAdapter())
    reg.register(ResearchObjectIdentityAdapter())
    reg.register(ClaimEvidenceGraphSnapshotAdapter())
    reg.register(DecisionLedgerSnapshotAdapter())
    # Tier 2
    reg.register(QuantitativePaperAuditAdapter())
    reg.register(ResearchReproducibilityAdapter())
    reg.register(CrossReviewAdapter())
    reg.register(SystematicReviewAdapter())
    reg.register(LiteratureAnalysisAdapter())
    reg.register(LiteratureWatchAdapter())
    reg.register(RetractionWatchAdapter())
    reg.register(MathComputationAdapter())
    # Tier 3
    reg.register(AcademicWritingAdapter())
    reg.register(OpaqueFallbackAdapter())
    return reg
