# -*- coding: utf-8 -*-
"""Mock reviewer adapter for unit testing and offline replays."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from contracts import (
    ChallengeRequest,
    ChallengeResult,
    Finding,
    ParticipantSpec,
    ReviewerAdapter,
    ReviewerCapabilities,
    ReviewRequest,
    ReviewResult,
)


class MockReviewerAdapter(ReviewerAdapter):
    """In-memory deterministic reviewer adapter for testing deliberation engines."""

    def __init__(self, predefined_findings: Optional[Dict[str, List[Finding]]] = None):
        self.predefined_findings = predefined_findings or {}
        self.review_calls = []
        self.challenge_calls = []

    def capabilities(self, participant: ParticipantSpec) -> ReviewerCapabilities:
        return ReviewerCapabilities(
            structured_output=True,
            filesystem_read=True,
            shell=False,
            web=False,
            subagents=False,
            provider="mock",
            model=participant.model or "mock-model",
            harness="mock",
        )

    def review(self, req: ReviewRequest) -> ReviewResult:
        self.review_calls.append(req)
        pid = req.participant.id
        findings = self.predefined_findings.get(pid, [
            Finding(id="F1", target="src/main.py", claim=f"Default claim by {pid}", kind="bug", severity="P1")
        ])

        # 写出 findings 文件供后续流程消费
        f_path = Path(req.findings_path)
        f_path.parent.mkdir(parents=True, exist_ok=True)
        f_path.write_text(json.dumps({
            "findings": [f.to_dict() for f in findings],
            "unknowns": [],
            "assumptions": []
        }, indent=2), encoding="utf-8")

        # 写出 review 文本
        o_path = Path(req.out_path)
        o_path.parent.mkdir(parents=True, exist_ok=True)
        text = f"# Review by {pid}\n\n" + "\n".join([f"- {f.claim}" for f in findings])
        o_path.write_text(text, encoding="utf-8")

        return ReviewResult(
            participant_id=pid,
            success=True,
            text=text,
            findings=findings,
            wall_time_seconds=0.01,
        )

    def challenge(self, req: ChallengeRequest) -> ChallengeResult:
        self.challenge_calls.append(req)
        o_path = Path(req.out_path)
        o_path.parent.mkdir(parents=True, exist_ok=True)
        reply = f"Challenge reply by {req.reviewer.id} on target {req.target_participant_id}\n\n【CONCEDE】 Accepted."
        o_path.write_text(reply, encoding="utf-8")

        return ChallengeResult(
            reviewer_id=req.reviewer.id,
            target_id=req.target_participant_id,
            success=True,
            reply_text=reply,
            stances=["CONCEDE"],
            wall_time_seconds=0.01,
        )
