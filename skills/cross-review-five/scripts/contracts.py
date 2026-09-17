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

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# Canonical executor identifiers matching review-panel-spec.schema.json
CANONICAL_EXECUTORS = {
    "hermes": "hermes.cli",
    "hermes.cli": "hermes.cli",
    "hermes_cli": "hermes.cli",
    "command": "command",
    "cli": "command",
    "cmd": "command",
    "mock": "mock",
    "hermes.llm": "hermes.llm",
    "hermes.subagent": "hermes.subagent",
    "api": "api",
}


def normalize_executor(val: Optional[str]) -> str:
    """Normalize user or config runner names to canonical schema executor enum."""
    if not val:
        return "hermes.cli"
    v = str(val).strip().lower()
    return CANONICAL_EXECUTORS.get(v, v)


def validate_participant_id(key: str) -> str:
    """Strict slug validation to prevent path traversal and shell injection."""
    slug = str(key).strip()
    if not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_-]{0,63}", slug):
        raise ValueError(
            f"Invalid participant ID: {key!r}. Must match '^[a-zA-Z0-9_][a-zA-Z0-9_-]{{0,63}}$' "
            f"and not start with a hyphen or contain path separators."
        )
    return slug


PROVIDER_ALLOWED_KEYS: dict[str, list[str]] = {
    "anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"],
    "openai": ["OPENAI_API_KEY", "OPENAI_ORG_ID", "OPENAI_BASE_URL"],
    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "kimi": ["KIMI_API_KEY", "KIMI_CODING_API_KEY", "MOONSHOT_API_KEY"],
    "kimi-coding": ["KIMI_API_KEY", "KIMI_CODING_API_KEY", "MOONSHOT_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY"],
    "zai": ["GLM_API_KEY", "ZAI_API_KEY"],
}


def build_isolated_child_env(participant: ParticipantSpec) -> dict[str, str]:
    """Harness-neutral environment isolation for any subprocess or CLI runner.

    Strictly scopes environment to base OS variables and only the explicit API
    credentials required by the participant's declared provider. Does not leak
    cross-provider tokens, seat IDs, or arbitrary host secrets.
    """
    base_allow = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
        "USERPROFILE", "HOME", "LANG", "LC_ALL", "SHELL", "COMSPEC",
        "TERM", "TZ", "HERMES_HOME", "HERMES_CONFIG_DIR",
    }
    env: dict[str, str] = {}
    for k, v in os.environ.items():
        if k in base_allow:
            env[k] = v

    prov = (participant.provider or "").strip().lower()
    allowed_keys = PROVIDER_ALLOWED_KEYS.get(prov, [])
    # 自定义 Provider 仅允许严格以 PROVIDER_API_KEY 或 PROVIDER_TOKEN 命名的变量
    if not allowed_keys and prov:
        custom_prefix = prov.upper().replace("-", "_")
        allowed_keys = [f"{custom_prefix}_API_KEY", f"{custom_prefix}_TOKEN"]

    for key_name in allowed_keys:
        if key_name in os.environ:
            env[key_name] = os.environ[key_name]

    # 仅针对对应 Provider 进行向下兼容别名填充，绝不跨 Provider 注入
    if prov in ("kimi", "kimi-coding"):
        if "MOONSHOT_API_KEY" in os.environ and "KIMI_API_KEY" not in env:
            env["KIMI_API_KEY"] = os.environ["MOONSHOT_API_KEY"]
    elif prov in ("gemini", "google"):
        if "GOOGLE_API_KEY" in os.environ and "GEMINI_API_KEY" not in env:
            env["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

    return env


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

    def __post_init__(self):
        self.id = validate_participant_id(self.id)
        self.executor = normalize_executor(self.executor)

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
class PanelBudget:
    max_calls: int = 20
    max_wall_seconds: int = 3600
    max_cost_usd: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "max_calls": self.max_calls,
            "max_wall_seconds": self.max_wall_seconds,
        }
        if self.max_cost_usd is not None:
            d["max_cost_usd"] = float(self.max_cost_usd)
        return d


@dataclass
class PanelSpec:
    panel_id: str
    participants: List[ParticipantSpec]
    description: Optional[str] = None
    topology: str = "sparse_deliberation"
    budget: PanelBudget = field(default_factory=PanelBudget)
    budget_max_calls: int = 20
    budget_max_seconds: int = 3600
    budget_max_cost_usd: Optional[float] = None

    def __post_init__(self):
        # 兼容传统扁平参数注入
        if self.budget_max_calls != 20 or self.budget_max_seconds != 3600 or self.budget_max_cost_usd is not None:
            self.budget = PanelBudget(
                max_calls=self.budget_max_calls,
                max_wall_seconds=self.budget_max_seconds,
                max_cost_usd=self.budget_max_cost_usd,
            )

    def get_participant(self, participant_id: str) -> Optional[ParticipantSpec]:
        for p in self.participants:
            if p.id == participant_id:
                return p
        return None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "panel_id": self.panel_id,
            "participants": [p.to_dict() for p in self.participants],
            "topology": self.topology,
            "budget": self.budget.to_dict(),
        }
        if self.description:
            d["description"] = self.description
        return d


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
    phase: str = "plan"  # plan, challenge, synthesize
    text: str = ""
    findings: List[Finding] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    error: Optional[str] = None
    wall_time_seconds: float = 0.0
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.telemetry:
            self.telemetry = {"wall_time_seconds": round(float(self.wall_time_seconds), 4)}
        elif "wall_time_seconds" not in self.telemetry:
            self.telemetry["wall_time_seconds"] = round(float(self.wall_time_seconds), 4)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary strictly matching review-result.schema.json."""
        d: Dict[str, Any] = {
            "participant_id": self.participant_id,
            "phase": self.phase,
            "success": self.success,
            "text": self.text,
            "findings": [f.to_dict() for f in self.findings],
            "unknowns": self.unknowns,
            "assumptions": self.assumptions,
            "telemetry": self.telemetry,
        }
        if self.error:
            d["error"] = self.error
        return d


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
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.telemetry:
            self.telemetry = {"wall_time_seconds": round(float(self.wall_time_seconds), 4)}
        elif "wall_time_seconds" not in self.telemetry:
            self.telemetry["wall_time_seconds"] = round(float(self.wall_time_seconds), 4)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "reviewer_id": self.reviewer_id,
            "target_id": self.target_id,
            "success": self.success,
            "reply_text": self.reply_text,
            "stances": self.stances,
            "telemetry": self.telemetry,
        }
        if self.error:
            d["error"] = self.error
        return d


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
