# -*- coding: utf-8 -*-
"""Harness-neutral review panel contracts and adapter protocol.

Core abstractions:
- ParticipantSpec: declaration of a panel seat (ID, executor, model, role).
- PanelSpec: panel topology, participants, and budget constraints.
- Finding: structured finding dataclass matching review-finding.schema.json.
- ReviewRequest / ReviewResult: inputs and outputs of blind review.
- ChallengeRequest / ChallengeResult: inputs and outputs of targeted challenge.
- ReviewerAdapter: Protocol implemented by harness-specific adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@dataclass
class Finding:
    id: str
    target: str
    claim: str
    kind: str = "bug"
    issue_key: Optional[str] = None
    polarity: Optional[str] = None
    evidence: List[str] = field(default_factory=list)
    severity: str = "P1"
    blocking: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.id,
            "target": self.target,
            "kind": self.kind,
            "claim": self.claim,
            "severity": self.severity,
            "blocking": self.blocking,
        }
        if self.issue_key:
            data["issue_key"] = self.issue_key
        if self.polarity:
            data["polarity"] = self.polarity
        if self.evidence:
            data["evidence"] = self.evidence
        return data


@dataclass
class ParticipantSpec:
    id: str
    executor: str = "hermes.cli"  # hermes.cli, hermes.llm, command, api, mock
    provider: Optional[str] = None
    model: Optional[str] = None
    role: Optional[str] = None
    cmd: Optional[str] = None  # CLI template for command executor
    toolsets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"id": self.id, "executor": self.executor}
        if self.provider:
            d["provider"] = self.provider
        if self.model:
            d["model"] = self.model
        if self.role:
            d["role"] = self.role
        if self.cmd:
            d["cmd"] = self.cmd
        if self.toolsets:
            d["toolsets"] = self.toolsets
        return d


@dataclass
class PanelSpec:
    panel_id: str
    participants: List[ParticipantSpec]
    description: Optional[str] = None
    topology: str = "sparse_deliberation"
    budget_max_calls: int = 20
    budget_max_seconds: int = 3600

    def get_participant(self, participant_id: str) -> Optional[ParticipantSpec]:
        for p in self.participants:
            if p.id == participant_id:
                return p
        return None


@dataclass
class ReviewRequest:
    task_path: str
    out_path: str
    findings_path: str
    participant: ParticipantSpec


@dataclass
class ReviewResult:
    participant_id: str
    success: bool
    text: str = ""
    findings: List[Finding] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    error: Optional[str] = None
    wall_time_seconds: float = 0.0


@dataclass
class ChallengeRequest:
    task_path: str
    bundle_path: str
    out_path: str
    reviewer: ParticipantSpec
    target_participant_id: str


@dataclass
class ChallengeResult:
    reviewer_id: str
    target_id: str
    success: bool
    reply_text: str = ""
    stances: List[str] = field(default_factory=list)  # CONCEDE, REFUTED, etc.
    error: Optional[str] = None
    wall_time_seconds: float = 0.0


@dataclass
class ReviewerCapabilities:
    structured_output: bool = True
    filesystem_read: bool = True
    shell: bool = False
    web: bool = False
    subagents: bool = False
    provider: Optional[str] = None
    model: Optional[str] = None
    harness: str = "unknown"


@runtime_checkable
class ReviewerAdapter(Protocol):
    """Universal protocol implemented by harness-specific adapters."""

    def capabilities(self, participant: ParticipantSpec) -> ReviewerCapabilities:
        ...

    def review(self, req: ReviewRequest) -> ReviewResult:
        ...

    def challenge(self, req: ChallengeRequest) -> ChallengeResult:
        ...
