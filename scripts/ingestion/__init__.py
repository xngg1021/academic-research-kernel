"""Research Artifact Ingestion Bridge for academic-research-kernel."""

from .models import (
    ArtifactEnvelope,
    IngestionReceipt,
    IngestionKernelState,
)
from .adapters import (
    BaseArtifactAdapter,
    IngestionPlan,
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
from .registry import AdapterRegistry, create_default_registry
from .engine import IngestionEngine

__all__ = [
    "ArtifactEnvelope",
    "IngestionReceipt",
    "IngestionKernelState",
    "BaseArtifactAdapter",
    "IngestionPlan",
    "AcademicSourceVerificationAdapter",
    "ResearchObjectIdentityAdapter",
    "ClaimEvidenceGraphSnapshotAdapter",
    "DecisionLedgerSnapshotAdapter",
    "QuantitativePaperAuditAdapter",
    "ResearchReproducibilityAdapter",
    "CrossReviewAdapter",
    "SystematicReviewAdapter",
    "LiteratureAnalysisAdapter",
    "LiteratureWatchAdapter",
    "RetractionWatchAdapter",
    "MathComputationAdapter",
    "AcademicWritingAdapter",
    "OpaqueFallbackAdapter",
    "AdapterRegistry",
    "create_default_registry",
    "IngestionEngine",
]
