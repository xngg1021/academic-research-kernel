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
    build_isolated_child_env,
)


class HermesCliReviewerAdapter(ReviewerAdapter):
    """Executes hermes chat CLI subagent processes."""

    def __init__(self, timeout_seconds: int = 2400, spawn_fn=None):
        self.timeout_seconds = timeout_seconds
        self.spawn_fn = spawn_fn

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

    @staticmethod
    def _kill_proc_tree(proc: subprocess.Popen) -> None:
        """Safely terminate and kill subprocess to prevent orphan processes."""
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass

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
        proc = None
        try:
            if self.spawn_fn is not None:
                proc = self.spawn_fn(p.id, req.task_path, str(log_path))
                if hasattr(proc, "wait"):
                    proc.wait(timeout=self.timeout_seconds)
                elif hasattr(proc, "poll"):
                    proc.poll()
                rc = getattr(proc, "returncode", 0)
                success = (rc == 0 or rc is None) and Path(req.out_path).is_file()
                err = None if success else f"Hermes process exited with code {rc}"
            else:
                with open(log_path, "wb") as log:
                    proc = subprocess.Popen(
                        cmd, stdout=log, stderr=subprocess.STDOUT,
                        cwd=os.getcwd(),
                        env=build_isolated_child_env(p),
                    )
                    proc.wait(timeout=self.timeout_seconds)
                success = proc.returncode == 0
                err = None if success else f"Hermes process exited with code {proc.returncode}"
        except subprocess.TimeoutExpired:
            success = False
            err = f"Hermes reviewer process timed out after {self.timeout_seconds}s"
            if proc and hasattr(proc, "terminate"):
                self._kill_proc_tree(proc)
        except Exception as exc:
            success = False
            err = f"Execution exception: {type(exc).__name__}: {exc}"
            if proc and hasattr(proc, "terminate"):
                self._kill_proc_tree(proc)

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
            phase="plan",
            success=success and bool(review_text or findings),
            text=review_text,
            findings=findings,
            error=err,
            wall_time_seconds=round(wall, 4),
            telemetry={"wall_time_seconds": round(wall, 4)},
        )

    def challenge(self, req: ChallengeRequest) -> ChallengeResult:
        p = req.reviewer
        provider = p.provider or "custom"
        model = p.model or p.id

        # 修复：query-file 严格使用包含质询规则与指令的 task_path
        cmd = ["hermes", "chat", "--query-file", req.task_path, "--oneshot",
               "--ignore-rules", "-m", model, "--provider", provider]
        if model == "glm-5.3":
            cmd += ["--reasoning", "low"]

        log_path = Path(req.out_path).with_suffix(".challenge-log.txt")
        t0 = time.perf_counter()
        proc = None
        try:
            if self.spawn_fn is not None:
                proc = self.spawn_fn(p.id, req.task_path, str(log_path))
                if hasattr(proc, "wait"):
                    proc.wait(timeout=self.timeout_seconds)
                elif hasattr(proc, "poll"):
                    proc.poll()
                rc = getattr(proc, "returncode", 0)
                success = (rc == 0 or rc is None) and Path(req.out_path).is_file()
                err = None if success else f"Hermes process exited with code {rc}"
            else:
                with open(log_path, "wb") as log:
                    proc = subprocess.Popen(
                        cmd, stdout=log, stderr=subprocess.STDOUT,
                        cwd=os.getcwd(),
                        env=build_isolated_child_env(p),
                    )
                    proc.wait(timeout=self.timeout_seconds)
                success = proc.returncode == 0
                err = None if success else f"Hermes process exited with code {proc.returncode}"
        except subprocess.TimeoutExpired:
            success = False
            err = f"Hermes challenge process timed out after {self.timeout_seconds}s"
            if proc and hasattr(proc, "terminate"):
                self._kill_proc_tree(proc)
        except Exception as exc:
            success = False
            err = f"Execution exception: {type(exc).__name__}: {exc}"
            if proc and hasattr(proc, "terminate"):
                self._kill_proc_tree(proc)

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
            wall_time_seconds=round(wall, 4),
            telemetry={"wall_time_seconds": round(wall, 4)},
        )
