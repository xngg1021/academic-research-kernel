# -*- coding: utf-8 -*-
"""Hermes CLI subprocess reviewer adapter.

Executes 'hermes chat' via isolated subprocesses with minimal environment
whitelisting and '--ignore-rules' guards.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

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


class HermesCliReviewerAdapter(ReviewerAdapter):
    """Executes hermes chat CLI subagent processes."""

    def __init__(self, timeout_seconds: int = 2400):
        self.timeout_seconds = timeout_seconds

    def capabilities(self, participant: ParticipantSpec) -> ReviewerCapabilities:
        return ReviewerCapabilities(
            structured_output=True,
            filesystem_read=True,
            shell=True,
            web=True,
            subagents=True,
            provider=participant.provider,
            model=participant.model or participant.id,
            harness="hermes_cli",
        )

    def _minimal_child_env(self, participant: ParticipantSpec) -> dict[str, str]:
        base_allow = {
            "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
            "USERPROFILE", "HOME", "LANG", "LC_ALL", "SHELL", "COMSPEC",
            "HERMES_HOME", "HERMES_CONFIG_DIR", "HERMES_LOG_LEVEL",
        }
        prov = (participant.provider or "").upper().replace("-", "_")
        mod_k = participant.id.upper().replace("-", "_")
        allowed_prefixes = {prov, mod_k}

        env = {}
        for k, v in os.environ.items():
            if k in base_allow or k.startswith("HERMES_"):
                env[k] = v
            elif any(k.upper().startswith(p) for p in allowed_prefixes if p):
                if any(term in k.upper() for term in ("API_KEY", "TOKEN", "SECRET")):
                    env[k] = v

        if "MOONSHOT_API_KEY" in os.environ and "KIMI_API_KEY" not in env:
            env["KIMI_API_KEY"] = os.environ["MOONSHOT_API_KEY"]
        if "GOOGLE_API_KEY" in os.environ and "GEMINI_API_KEY" not in env:
            env["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]
        return env

    def review(self, req: ReviewRequest) -> ReviewResult:
        p = req.participant
        provider = p.provider or "custom"
        model = p.model or p.id

        cmd = ["hermes", "chat", "--query-file", req.task_path, "--oneshot",
               "--ignore-rules", "-m", model, "--provider", provider]
        if model == "glm-5.3":
            cmd += ["--reasoning", "low"]

        log_path = Path(req.out_path).with_suffix(".log.txt")
        t0 = time.perf_counter()
        try:
            with open(log_path, "wb") as log:
                proc = subprocess.Popen(
                    cmd, stdout=log, stderr=subprocess.STDOUT,
                    cwd=os.getcwd(),
                    env=self._minimal_child_env(p),
                )
                proc.wait(timeout=self.timeout_seconds)
            success = proc.returncode == 0
            err = None if success else f"Hermes process exited with code {proc.returncode}"
        except Exception as exc:
            success = False
            err = f"Execution exception: {type(exc).__name__}: {exc}"

        wall = time.perf_counter() - t0
        findings_path = Path(req.findings_path)
        findings: list[Finding] = []
        if findings_path.is_file():
            try:
                data = json.loads(findings_path.read_text(encoding="utf-8"))
                for raw_f in data.get("findings") or []:
                    findings.append(Finding(
                        id=str(raw_f.get("id", f"F{len(findings)+1}")),
                        target=str(raw_f.get("target", "")),
                        claim=str(raw_f.get("claim", "")),
                        kind=str(raw_f.get("kind", "bug")),
                        issue_key=raw_f.get("issue_key"),
                        polarity=raw_f.get("polarity"),
                        evidence=raw_f.get("evidence") or [],
                        severity=raw_f.get("severity", "P1"),
                        blocking=bool(raw_f.get("blocking", False)),
                    ))
            except Exception:
                pass

        out_path = Path(req.out_path)
        review_text = out_path.read_text(encoding="utf-8") if out_path.is_file() else ""

        return ReviewResult(
            participant_id=p.id,
            success=success and bool(review_text or findings),
            text=review_text,
            findings=findings,
            error=err,
            wall_time_seconds=round(wall, 3),
        )

    def challenge(self, req: ChallengeRequest) -> ChallengeResult:
        p = req.reviewer
        provider = p.provider or "custom"
        model = p.model or p.id

        cmd = ["hermes", "chat", "--query-file", req.bundle_path, "--oneshot",
               "--ignore-rules", "-m", model, "--provider", provider]
        if model == "glm-5.3":
            cmd += ["--reasoning", "low"]

        log_path = Path(req.out_path).with_suffix(".challenge-log.txt")
        t0 = time.perf_counter()
        try:
            with open(log_path, "wb") as log:
                proc = subprocess.Popen(
                    cmd, stdout=log, stderr=subprocess.STDOUT,
                    cwd=os.getcwd(),
                    env=self._minimal_child_env(p),
                )
                proc.wait(timeout=self.timeout_seconds)
            success = proc.returncode == 0
            err = None if success else f"Hermes process exited with code {proc.returncode}"
        except Exception as exc:
            success = False
            err = f"Execution exception: {type(exc).__name__}: {exc}"

        wall = time.perf_counter() - t0
        out_path = Path(req.out_path)
        reply_text = out_path.read_text(encoding="utf-8") if out_path.is_file() else ""

        stances = []
        if "CONCEDE" in reply_text:
            stances.append("CONCEDE")
        if "REFUTED" in reply_text:
            stances.append("REFUTED")

        return ChallengeResult(
            reviewer_id=p.id,
            target_id=req.target_participant_id,
            success=success and bool(reply_text),
            reply_text=reply_text,
            stances=stances,
            error=err,
            wall_time_seconds=round(wall, 3),
        )
