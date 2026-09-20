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
        self._adapters.append(adapter)
        # Keep sorted by tier (1 before 2 before 3)
        self._adapters.sort(key=lambda a: a.tier)

    def resolve(self, envelope: ArtifactEnvelope) -> BaseArtifactAdapter:
        """Resolve the highest-priority adapter that probes positive for the envelope."""
        for adapter in self._adapters:
            if adapter.probe(envelope):
                return adapter
        return OpaqueFallbackAdapter()

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
