# -*- coding: utf-8 -*-
"""Command-line template reviewer adapter.

Executes arbitrary subagent CLI commands (Claude Code CLI, Gemini CLI,
Codex CLI, local Python agent scripts) using user-defined command templates.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

import contracts as ct
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


class CommandReviewerAdapter(ReviewerAdapter):
    """Executes arbitrary reviewer commands via CLI formatting templates."""

    def __init__(self, default_cmd_template: str = None):
        self.default_cmd_template = default_cmd_template or "{model} --query-file {prompt_path}"

    def capabilities(self, participant: ParticipantSpec) -> ReviewerCapabilities:
        return ReviewerCapabilities(
            structured_output=True,
            filesystem_read=True,
            shell=True,
            web=False,
            subagents=False,
            provider=participant.provider,
            model=participant.model or participant.id,
            harness="command_cli",
        )

    @staticmethod
    def _safe_format_cmd(template: str, values: dict[str, str]) -> str:
        s = template
        for k, v in values.items():
            s = s.replace("{" + k + "}", str(v))
        return s

    @staticmethod
    def _split_command(command: str, windows: bool = False) -> list[str]:
        args = shlex.split(command, posix=not windows)
        # Windows shlex preserves grouping quotes; subprocess(list) adds its own.
        if windows:
            args = [a[1:-1] if len(a) >= 2 and a[0] == a[-1] and a[0] in "\"'" else a for a in args]
        return args

    def review(self, req: ReviewRequest) -> ReviewResult:
        p = req.participant
        cmd_template = p.cmd or os.environ.get(f"HERMES_REVIEW_CMD_{p.id.upper().replace('-', '_')}") or self.default_cmd_template
        prompt_path = Path(req.task_path).resolve()
        out_path = Path(req.out_path).resolve()
        findings_path = Path(req.findings_path).resolve()

        cmd_str = self._safe_format_cmd(cmd_template, {
            "model": p.model or p.id,
            "provider": p.provider or "custom",
            "prompt_path": str(prompt_path),
            "out_path": str(out_path),
            "findings_path": str(findings_path),
        })

        t0 = time.perf_counter()
        args = self._split_command(cmd_str, windows=sys.platform == "win32")
        child_env = build_isolated_child_env(p)
        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=str(prompt_path.parent),
                env=child_env,
                timeout=1800,
            )
            success = res.returncode == 0
            err = None if success else f"Command failed with exit code {res.returncode}: {res.stderr}"
        except Exception as exc:
            success = False
            err = f"Execution exception: {type(exc).__name__}: {exc}"

        wall = time.perf_counter() - t0

        # 读取可能生成的结构化 findings
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
        cmd_template = p.cmd or os.environ.get(f"HERMES_REVIEW_CMD_{p.id.upper().replace('-', '_')}") or self.default_cmd_template
        # 正确传递包含质询纪律与规范的 prompt 文件
        prompt_path = Path(req.task_path).resolve()
        bundle_path = Path(req.bundle_path).resolve()
        out_path = Path(req.out_path).resolve()

        cmd_str = self._safe_format_cmd(cmd_template, {
            "model": p.model or p.id,
            "provider": p.provider or "custom",
            "prompt_path": str(prompt_path),
            "bundle_path": str(bundle_path),
            "out_path": str(out_path),
            "findings_path": str(out_path.with_suffix(".findings.json")),
        })

        t0 = time.perf_counter()
        args = self._split_command(cmd_str, windows=sys.platform == "win32")
        child_env = build_isolated_child_env(p)
        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=str(prompt_path.parent),
                env=child_env,
                timeout=1800,
            )
            success = res.returncode == 0
            err = None if success else f"Command failed: {res.stderr}"
        except Exception as exc:
            success = False
            err = f"Execution exception: {type(exc).__name__}: {exc}"

        wall = time.perf_counter() - t0
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
