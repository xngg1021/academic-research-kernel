"""Harness-neutral multi-model cross-review and sparse deliberation engine.

Implements both:
- v1 classic ring rotation pairings (`pairings`)
- v2 four-stage Sparse Deliberation (`plan` -> `merge` -> `challenge` -> `synthesize`),
  producing artifacts compliant with `cross-review-artifact.schema.json`,
  `review-panel-spec.schema.json`, and `review-run-receipt.schema.json`.

Participant rosters are explicitly supplied by the caller (no hardcoded vendor presets).
"""
from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shlex
import subprocess
import sys
import time
from typing import Any, Iterable, Mapping, Optional
import uuid

from ._stdlib import canonical_json, safe_path, sha256_hex

PARTICIPANT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_FILE_TOKEN_RE = re.compile(r"[a-z0-9_.-]+\.[a-z0-9]{1,8}")
_ABS_PATH_RE = re.compile(r"^(?:/|[A-Za-z]:[\\/])")
_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")

_SEV_RANK = {"P0": 3, "P1": 2, "P2": 1, "P3": 0}
RNG_SEED = 20260917

MODE_PRESETS: dict[str, dict[str, Any]] = {
    "economy": {"max_challenges": 1, "use_derangement": False},
    "standard": {"max_challenges": 3, "use_derangement": False},
    "audit": {"max_challenges": 5, "use_derangement": True},
}

OPPOSING_POLARITY = frozenset({
    ("present", "absent"),
    ("absent", "present"),
    ("positive", "negative"),
    ("negative", "positive"),
    ("valid", "invalid"),
    ("invalid", "valid"),
    ("supported", "unsupported"),
    ("unsupported", "supported"),
})

_SAFE_ENV_KEYS = (
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "TMP",
    "TEMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "PYTHONUTF8",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)

PLAN_PROMPT_TEMPLATE = """You are an independent technical reviewer in a blind multi-agent deliberation.
Read the task specification at: {task_path}

1. Write your full human-readable review report to: {out_path}
2. Write your structured findings JSON to: {findings_path}
   Required JSON object format:
   {{
     "findings": [
       {{
         "id": "F1",
         "target": "relative/path/to/file.py",
         "issue_key": "short-canonical-slug",
         "polarity": "present",
         "severity": "P0 | P1 | P2",
         "claim": "Concise falsifiable defect statement",
         "evidence": ["relative/path/to/file.py:42"]
       }}
     ]
   }}
Do NOT read or modify outputs belonging to any other reviewer seat.
"""

CHALLENGE_PROMPT_TEMPLATE = """You are an independent challenger adjudicating anonymized review proposals.
Task context: {task_path}
Anonymized challenge bundle: {bundle_path}
Write your adjudication report to: {out_path}

Do NOT inspect any other `review-*.md` or `findings-*.json` files in the directory.
For each Proposal-N in the bundle:
1. Verify concrete code/document evidence directly against the target material.
2. State an explicit verdict line containing exactly one tag per proposal:
   - `【CONCEDE】 Proposal-N: ...` when verified true;
   - `【REFUTED】 Proposal-N: ...` when disproved by direct counterexample;
   - `【UNRESOLVED】 Proposal-N: ...` when evidence is genuinely insufficient.
"""


@dataclass(frozen=True)
class ParticipantSpec:
    id: str
    executor: str = "command"
    provider: str = "custom"
    model: str = ""
    cmd: Optional[str | tuple[str, ...]] = None
    role: Optional[str] = None


def validate_participant_id(raw_id: str) -> str:
    s = str(raw_id or "").strip()
    if not PARTICIPANT_ID_RE.fullmatch(s):
        raise ValueError(f"Invalid participant/challenge identifier: {raw_id!r}")
    return s


def dedup_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def pairings(models: list[str]) -> list[tuple[str, str]]:
    """v1 classic ring rotation: seat i reviews seat (i + 1) mod N."""
    if len(models) < 2:
        raise ValueError("Ring rotation requires at least 2 distinct participants")
    return [(models[i], models[(i + 1) % len(models)]) for i in range(len(models))]


def parse_participants(
    models_arg: Optional[str] = None,
    models_file: Optional[str | Path] = None,
) -> list[ParticipantSpec]:
    specs: list[ParticipantSpec] = []
    if models_file:
        raw = json.loads(safe_path(models_file, must_exist=True).read_text(encoding="utf-8"))
        entries = raw.get("participants", []) if isinstance(raw, dict) else raw
        if not isinstance(entries, list) or not entries:
            raise ValueError("models_file must be a non-empty list or ReviewPanelSpec with 'participants'")
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError("Each participant entry must be an object")
            pid = validate_participant_id(str(item.get("id") or item.get("key") or ""))
            runner = str(item.get("executor") or item.get("runner") or ("command" if item.get("cmd") else "mock"))
            if runner == "cli":
                runner = "command"
            raw_cmd = item.get("cmd")
            if isinstance(raw_cmd, list):
                if not raw_cmd or not all(isinstance(x, str) and x for x in raw_cmd):
                    raise ValueError(f"cmd list for {pid!r} must be a non-empty list of non-empty strings")
                norm_cmd: Optional[str | tuple[str, ...]] = tuple(raw_cmd)
            elif raw_cmd:
                norm_cmd = str(raw_cmd)
            else:
                norm_cmd = None
            specs.append(
                ParticipantSpec(
                    id=pid,
                    executor=runner,
                    provider=str(item.get("provider") or "custom"),
                    model=str(item.get("model") or pid),
                    cmd=norm_cmd,
                    role=str(item["role"]) if item.get("role") else None,
                )
            )
    if models_arg:
        by_id = {s.id: s for s in specs}
        chosen: list[ParticipantSpec] = []
        for token in [t.strip() for t in models_arg.split(",") if t.strip()]:
            if ":" in token:
                parts = token.split(":", 3)
                pid = validate_participant_id(parts[0])
                prov = parts[1] if len(parts) > 1 and parts[1] else "custom"
                mod = parts[2] if len(parts) > 2 and parts[2] else pid
                exe = parts[3] if len(parts) > 3 and parts[3] else "command"
                chosen.append(ParticipantSpec(id=pid, executor=exe, provider=prov, model=mod))
            elif token in by_id:
                chosen.append(by_id[token])
            else:
                pid = validate_participant_id(token)
                chosen.append(ParticipantSpec(id=pid, executor="mock", provider="custom", model=pid))
        specs = chosen

    seen_ids: set[str] = set()
    deduped: list[ParticipantSpec] = []
    for sp in specs:
        if sp.id not in seen_ids:
            seen_ids.add(sp.id)
            deduped.append(sp)
    return deduped


def discover_stream_participants(stream_dir: Path) -> list[ParticipantSpec]:
    manifest_p = stream_dir / "run-manifest.json"
    if manifest_p.is_file():
        m = json.loads(manifest_p.read_text(encoding="utf-8"))
        if isinstance(m.get("participants"), list) and m["participants"]:
            return [
                ParticipantSpec(
                    id=validate_participant_id(p["id"]),
                    executor=str(p.get("executor") or "mock"),
                    provider=str(p.get("provider") or "custom"),
                    model=str(p.get("model") or p["id"]),
                    cmd=p.get("cmd"),
                )
                for p in m["participants"]
                if isinstance(p, dict) and p.get("id")
            ]
    ids: list[str] = []
    for fp in sorted(stream_dir.glob("findings-*.json")):
        stem = fp.stem[len("findings-") :]
        if PARTICIPANT_ID_RE.fullmatch(stem):
            ids.append(stem)
    for rp in sorted(stream_dir.glob("review-*.md")):
        if rp.name.startswith("review-of-"):
            continue
        stem = rp.stem[len("review-") :]
        if PARTICIPANT_ID_RE.fullmatch(stem) and stem not in ids:
            ids.append(stem)
    return [ParticipantSpec(id=i, executor="mock", provider="offline", model=i) for i in ids]


def normalize_target(target_str: Any) -> str:
    """Canonical target normalization preserving directory prefixes to prevent basename collisions."""
    if not target_str:
        return "general"
    s = str(target_str).strip()
    s = re.sub(r":\d+(?:-\d+)?$", "", s)
    s = s.replace("\\", "/").lower().strip("/")
    parts = [p for p in s.split("/") if p and not re.match(r"^[a-z]:$", p)]
    if not parts:
        return "general"
    joined = "/".join(parts)
    if "/" in joined:
        return joined
    m = _FILE_TOKEN_RE.search(joined)
    if m:
        return m.group(0)
    return joined


def _issue_identity(item: Mapping[str, Any]) -> tuple[str, str]:
    target = normalize_target(item.get("target", ""))
    key = str(item.get("issue_key") or "").strip().lower()
    if key:
        return (target, f"k:{key}")
    claim_norm = re.sub(r"\s+", "", str(item.get("claim") or "")).lower()
    if claim_norm:
        h = hashlib.sha256(claim_norm.encode("utf-8")).hexdigest()[:12]
        return (target, f"c:{h}")
    return (target, "anon")


def _has_polarity_contradiction(items: list[dict[str, Any]]) -> bool:
    pol_by_model: dict[str, set[str]] = {}
    for x in items:
        pol = str(x["raw"].get("polarity") or "").strip().lower()
        if pol:
            pol_by_model.setdefault(x["model"], set()).add(pol)
    models_with_pol = list(pol_by_model)
    for a in range(len(models_with_pol)):
        for b in range(a + 1, len(models_with_pol)):
            for pa in pol_by_model[models_with_pol[a]]:
                for pb in pol_by_model[models_with_pol[b]]:
                    if (pa, pb) in OPPOSING_POLARITY:
                        return True
    return False


def _has_claim_text_opposition(texts: list[str]) -> bool:
    opp_rules = (
        (r"\b(?:is\s+absent|absent|is\s+missing|missing)\b", r"\b(?:exists|is\s+present|present)\b"),
        (r"\b(?:is\s+invalid|invalid)\b", r"\b(?:is\s+valid|validates|valid)\b"),
        (r"\b(?:not\s+supported|unsupported)\b", r"\b(?:is\s+supported|supported)\b"),
        (r"\b(?:fails|fail)\b", r"\b(?:passes|pass)\b"),
    )

    def _pol(txt: str, neg_pat: str, pos_pat: str) -> tuple[bool, bool]:
        has_neg = bool(re.search(neg_pat, txt))
        scrubbed = re.sub(neg_pat, " ", txt)
        has_pos = bool(re.search(pos_pat, scrubbed))
        return has_pos, has_neg

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            t1, t2 = texts[i].lower(), texts[j].lower()
            for neg_pat, pos_pat in opp_rules:
                t1_pos, t1_neg = _pol(t1, neg_pat, pos_pat)
                t2_pos, t2_neg = _pol(t2, neg_pat, pos_pat)
                if (t1_pos and t2_neg and not t1_neg and not t2_pos) or (
                    t1_neg and t2_pos and not t1_pos and not t2_neg
                ):
                    return True
    return False


def cluster_issues(
    models: list[str],
    findings_by_model: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Cluster structured findings into (consensus, singletons, contradictions) by distinct models."""
    by_identity: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for m in models:
        raw_items = findings_by_model.get(m, {}).get("findings") or []
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            ident = _issue_identity(item)
            by_identity.setdefault(ident, []).append({"model": m, "raw": item})

    consensus: list[dict[str, Any]] = []
    singletons: list[dict[str, Any]] = []
    contradictions: list[dict[str, Any]] = []
    for idx, ((tgt, key), items) in enumerate(by_identity.items(), 1):
        raised = dedup_preserve_order([x["model"] for x in items])
        severity = max(
            (str(x["raw"].get("severity") or "P2").upper() for x in items),
            key=lambda s: _SEV_RANK.get(s, 0),
        )
        claims = [
            {
                "model": x["model"],
                "claim": str(x["raw"].get("claim") or ""),
                "evidence": list(x["raw"].get("evidence") or []),
                "polarity": str(x["raw"].get("polarity") or ""),
                "severity": str(x["raw"].get("severity") or "P2").upper(),
                "provenance": str(x["raw"].get("provenance") or "model_written"),
            }
            for x in items
        ]
        is_conflict = _has_polarity_contradiction(items) or _has_claim_text_opposition(
            [c["claim"] for c in claims]
        )
        state = "singleton" if len(raised) == 1 else ("contradiction" if is_conflict else "consensus")
        entry = {
            "issue_id": f"I{idx:02d}",
            "target": tgt,
            "assertion_key": key,
            "raised_by": raised,
            "severity": severity,
            "claims": claims,
            "provenance": (
                "synthetic_fallback"
                if all(c["provenance"] == "synthetic_fallback" for c in claims)
                else "model_written"
            ),
            "state": state,
        }
        if state == "singleton":
            singletons.append(entry)
        elif state == "contradiction":
            contradictions.append(entry)
        else:
            consensus.append(entry)
    return consensus, singletons, contradictions


def compute_complementarity_matrix(
    models: list[str],
    findings_by_model: Mapping[str, Mapping[str, Any]],
) -> dict[tuple[str, str], float]:
    weights: dict[tuple[str, str], float] = {}
    targets_by_model = {
        m: {
            normalize_target(f.get("target", ""))
            for f in (findings_by_model.get(m, {}).get("findings") or [])
            if isinstance(f, dict)
        }
        for m in models
    }
    for i in models:
        for j in models:
            if i == j:
                continue
            w = 1.0
            t_i, t_j = targets_by_model[i], targets_by_model[j]
            union = t_i | t_j
            if union:
                w += (1.0 - len(t_i & t_j) / len(union)) * 2.0
            for item in findings_by_model.get(j, {}).get("findings") or []:
                if not isinstance(item, dict):
                    continue
                tgt = normalize_target(item.get("target", ""))
                sev = str(item.get("severity") or "P2").upper()
                if tgt not in t_i:
                    if sev == "P0":
                        w += 3.0
                    elif sev == "P1":
                        w += 1.5
                else:
                    w += 0.5
            weights[(i, j)] = round(w, 2)
    return weights


def _hungarian_min_cost_assignment(cost_matrix: list[list[float]]) -> list[int]:
    n = len(cost_matrix)
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost_matrix[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    ans = [0] * n
    for j in range(1, n + 1):
        if p[j] > 0:
            ans[p[j] - 1] = j - 1
    return ans


def max_weight_derangement(models: list[str], weights: Mapping[tuple[str, str], float]) -> list[tuple[str, str]]:
    """Solve maximum-weight derangement in O(N^3) via Kuhn-Munkres without self-assignment."""
    n = len(models)
    if n < 2:
        return []
    if n == 2:
        return [(models[0], models[1]), (models[1], models[0])]
    penalty = 1e7
    cost_matrix = [
        [penalty if i == j else -float(weights.get((models[i], models[j]), 0.0)) for j in range(n)]
        for i in range(n)
    ]
    match = _hungarian_min_cost_assignment(cost_matrix)
    if all(match[i] != i for i in range(n)):
        return [(models[i], models[match[i]]) for i in range(n)]
    return [(models[i], models[(i + 1) % n]) for i in range(n)]


def _extract_json_object_from_text(text: str) -> Optional[dict[str, Any]]:
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(text[idx:])
                if isinstance(obj, dict) and isinstance(obj.get("findings"), list):
                    return obj
            except json.JSONDecodeError:
                continue
    return None


def load_or_extract_findings(stream_dir: Path, model_key: str) -> dict[str, Any]:
    """Load model-written `findings-<id>.json` sidecar or extract balanced JSON from `review-<id>.md`."""
    pid = validate_participant_id(model_key)
    sidecar = stream_dir / f"findings-{pid}.json"
    if sidecar.is_file():
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
            raise ValueError(f"Invalid findings sidecar {sidecar.name}: expected object with 'findings' list")
        normalized = []
        for idx, item in enumerate(data["findings"], 1):
            if not isinstance(item, dict):
                continue
            d = dict(item)
            d.setdefault("id", f"F{idx}")
            d.setdefault("provenance", "model_written")
            normalized.append(d)
        return {"findings": normalized}

    md_path = stream_dir / f"review-{pid}.md"
    if not md_path.is_file():
        return {"findings": []}
    md_text = md_path.read_text(encoding="utf-8")
    embedded = _extract_json_object_from_text(md_text)
    if embedded is not None:
        normalized = []
        for idx, item in enumerate(embedded["findings"], 1):
            if isinstance(item, dict):
                d = dict(item)
                d.setdefault("id", f"F{idx}")
                d["provenance"] = "model_written"
                normalized.append(d)
        out = {"findings": normalized}
        sidecar.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return out

    # Conservative fallback: extract explicit `[P0|P1|P2] path/file.py: claim` bullets only when file token is plausible
    synth: list[dict[str, Any]] = []
    pat = re.compile(r"\[(P[0-2])\]\s*`?([A-Za-z0-9_./\\-]+(?::\d+)?)`?\s*[:\-—]\s*(.+)")
    for ln in md_text.splitlines():
        m = pat.search(ln.strip())
        if not m:
            continue
        sev, raw_tgt, claim_txt = m.group(1), m.group(2), m.group(3).strip()
        norm_tgt = normalize_target(raw_tgt)
        if norm_tgt == "general" or not _EXT_RE.search(norm_tgt):
            continue
        synth.append({
            "id": f"S{len(synth) + 1}",
            "target": norm_tgt,
            "severity": sev,
            "claim": claim_txt[:240],
            "evidence": [raw_tgt],
            "provenance": "synthetic_fallback",
        })
    out = {"findings": synth}
    sidecar.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def _minimal_child_env() -> dict[str, str]:
    env = {k: os.environ[k] for k in _SAFE_ENV_KEYS if k in os.environ}
    env["PYTHONUTF8"] = "1"
    return env


def _split_command_template(template: str | tuple[str, ...] | list[str]) -> list[str]:
    if isinstance(template, (tuple, list)):
        return [str(x) for x in template]
    if sys.platform == "win32":
        import ctypes

        argc = ctypes.c_int(0)
        CommandLineToArgvW = ctypes.windll.shell32.CommandLineToArgvW
        CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
        CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
        ptr = CommandLineToArgvW(template, ctypes.byref(argc))
        if ptr:
            try:
                return [ptr[i] for i in range(argc.value)]
            finally:
                ctypes.windll.kernel32.LocalFree(ptr)
    return shlex.split(template, posix=True)


def _run_participant_command(
    spec: ParticipantSpec,
    placeholders: Mapping[str, str],
    cwd: Path,
    timeout_s: int = 900,
) -> tuple[bool, Optional[str], float]:
    t0 = time.perf_counter()
    if spec.executor == "mock":
        out_p = Path(placeholders["out_path"])
        if not out_p.is_file():
            out_p.write_text(f"# Mock output for {spec.id}\n\n【UNRESOLVED】 Mock placeholder.\n", encoding="utf-8")
        if "findings_path" in placeholders:
            fp = Path(placeholders["findings_path"])
            if not fp.is_file():
                fp.write_text(json.dumps({"findings": []}, indent=2) + "\n", encoding="utf-8")
        return True, None, round(time.perf_counter() - t0, 4)

    env_override = os.environ.get(f"ARK_REVIEW_CMD_{spec.id.upper().replace('-', '_')}")
    template = spec.cmd or env_override
    if not template:
        return False, f"Participant {spec.id!r} uses executor={spec.executor!r} without 'cmd' template", 0.0

    raw_tokens = _split_command_template(template)
    substituted: list[str] = []
    for tok in raw_tokens:
        replaced = tok
        for k, v in placeholders.items():
            replaced = replaced.replace("{" + k + "}", str(v))
        substituted.append(replaced)

    argv: list[str] = []
    stdin_text: Optional[str] = None
    idx = 0
    while idx < len(substituted):
        tok = substituted[idx]
        if tok == "<" and idx + 1 < len(substituted):
            stdin_text = Path(substituted[idx + 1]).read_text(encoding="utf-8")
            idx += 2
            continue
        if tok.startswith("<") and len(tok) > 1:
            cand_p = Path(tok[1:].strip())
            if cand_p.is_file():
                stdin_text = cand_p.read_text(encoding="utf-8")
                idx += 1
                continue
        argv.append(tok)
        idx += 1

    if stdin_text is None and "-" in argv and "prompt_path" in placeholders:
        p_in = Path(placeholders["prompt_path"])
        if p_in.is_file():
            stdin_text = p_in.read_text(encoding="utf-8")

    try:
        proc = subprocess.run(
            argv,
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd),
            env=_minimal_child_env(),
            timeout=timeout_s,
            check=False,
        )
        out_p = Path(placeholders["out_path"])
        if proc.returncode == 0 and not out_p.is_file() and proc.stdout.strip():
            out_p.write_text(proc.stdout, encoding="utf-8")
        ok = proc.returncode == 0 and out_p.is_file()
        err = None if ok else (proc.stderr.strip() or f"exit_code={proc.returncode}")
        return ok, err, round(time.perf_counter() - t0, 4)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", round(time.perf_counter() - t0, 4)


def _purge_downstream_stream_files(stream_dir: Path, *, include_plan_outputs: bool) -> None:
    patterns = [
        "issue-registry.json",
        "challenge-plan.json",
        "challenge-skipped.json",
        "graph-summary.md",
        "bundle-*.json",
        "prompt-challenge-*.txt",
        "challenge-reply-*.md",
        "challenge-meta-*.json",
        "unresolved-ledger.json",
        "review-run-receipt.json",
        "consensus-report.md",
    ]
    if include_plan_outputs:
        patterns.extend(["prompt-*.txt", "review-*.md", "findings-*.json"])
    for pat in patterns:
        for p in stream_dir.glob(pat):
            p.unlink(missing_ok=True)


def stage_plan(
    stream_dir: Path,
    task_path: Path,
    participants: list[ParticipantSpec],
    *,
    timeout_s: int = 900,
) -> dict[str, Any]:
    if len(participants) < 2:
        raise ValueError("Sparse deliberation requires at least 2 participants")
    stream_dir.mkdir(parents=True, exist_ok=True)
    task_file = safe_path(task_path, must_exist=True)
    task_sha = sha256_hex(task_file.read_bytes())
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    started_at = datetime.now(timezone.utc).isoformat()

    # Invalidate all prior run outputs and downstream deliberation artifacts
    manifest_p = stream_dir / "run-manifest.json"
    _purge_downstream_stream_files(stream_dir, include_plan_outputs=True)

    statuses: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(participants), 8)) as pool:
        futs = {}
        for sp in participants:
            prompt_p = stream_dir / f"prompt-{sp.id}.txt"
            out_p = stream_dir / f"review-{sp.id}.md"
            find_p = stream_dir / f"findings-{sp.id}.json"
            prompt_p.write_text(
                PLAN_PROMPT_TEMPLATE.format(task_path=task_file, out_path=out_p, findings_path=find_p),
                encoding="utf-8",
            )
            placeholders = {
                "model": sp.model or sp.id,
                "provider": sp.provider,
                "prompt_path": str(prompt_p),
                "out_path": str(out_p),
                "findings_path": str(find_p),
                "task_path": str(task_file),
            }
            futs[pool.submit(_run_participant_command, sp, placeholders, stream_dir, timeout_s)] = sp

        for fut in concurrent.futures.as_completed(futs):
            sp = futs[fut]
            ok, err, wall = fut.result()
            if ok:
                load_or_extract_findings(stream_dir, sp.id)
            statuses[sp.id] = {"success": ok, "error": err, "wall_seconds": wall}

    missing_models = sorted(pid for pid, st in statuses.items() if not st["success"])
    manifest = {
        "run_id": run_id,
        "started_at": started_at,
        "task_path": str(task_file),
        "task_sha256": task_sha,
        "participants": [
            {"id": s.id, "executor": s.executor, "provider": s.provider, "model": s.model, "cmd": s.cmd}
            for s in participants
        ],
        "missing_models": missing_models,
        "plan_statuses": statuses,
    }
    manifest_p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "stage": "plan",
        "run_id": run_id,
        "succeeded": [k for k, v in statuses.items() if v["success"]],
        "missing_models": missing_models,
        "statuses": statuses,
    }


def plan_challenges(
    models: list[str],
    findings_by_model: Mapping[str, Mapping[str, Any]],
    *,
    mode: str = "standard",
    seed: int = RNG_SEED,
    missing_models: Iterable[str] = (),
    run_id: Optional[str] = None,
    task_sha256: Optional[str] = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    if mode not in MODE_PRESETS:
        raise ValueError(f"Invalid deliberation mode {mode!r}; choose from {sorted(MODE_PRESETS)}")
    consensus, singletons, contradictions = cluster_issues(models, findings_by_model)
    weights = compute_complementarity_matrix(models, findings_by_model)
    rng = random.Random(seed)

    registry = {
        "metadata": {
            "mode": mode,
            "models": list(models),
            "missing_models": list(missing_models),
            "run_id": run_id,
            "task_sha256": task_sha256,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "stats": {
            "consensus_count": len(consensus),
            "singleton_count": len(singletons),
            "contradiction_count": len(contradictions),
            "total_issues": len(consensus) + len(singletons) + len(contradictions),
        },
        "consensus": consensus,
        "contradictions": contradictions,
        "singletons": singletons,
        "complementarity_weights": {f"{i}->{j}": w for (i, j), w in weights.items()},
    }

    cfg = MODE_PRESETS[mode]
    max_challenges = int(cfg["max_challenges"])
    challenges: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    def _anon_proposals(claim_items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
        indexed = [
            (orig_idx, {"source_alias": None, "claim": x.get("claim", ""), "evidence": list(x.get("evidence") or [])})
            for orig_idx, x in enumerate(claim_items, 1)
        ]
        rng.shuffle(indexed)
        props: list[dict[str, Any]] = []
        prop_map: dict[str, int] = {}
        for idx, (orig_idx, prop) in enumerate(indexed, 1):
            prop["source_alias"] = f"Proposal-{idx}"
            props.append(prop)
            prop_map[f"proposal{idx}"] = orig_idx
        return props, prop_map

    def _pick_uninvolved_reviewer(excluded: Iterable[str]) -> Optional[str]:
        excl = set(excluded)
        cands = [m for m in models if m not in excl and m not in set(missing_models)]
        if not cands:
            cands = [m for m in models if m not in excl]
        if not cands:
            return None
        anchor = next((m for m in excluded if m in models), cands[0])
        return max(cands, key=lambda c: weights.get((c, anchor), 0.0))

    ranked: list[tuple[int, int, str, dict[str, Any]]] = []
    for c in contradictions:
        ranked.append((_SEV_RANK.get(c["severity"], 0), 2, "contradiction", c))
    for s in singletons:
        if s.get("severity") in ("P0", "P1"):
            ranked.append((_SEV_RANK.get(s["severity"], 0), 1, "singleton_audit", s))
    ranked.sort(key=lambda r: (-r[0], -r[1]))

    used_reviewers: set[str] = set()
    for _, _, ctype, obj in ranked:
        if len(challenges) >= max_challenges:
            break
        if ctype == "contradiction":
            reviewer = _pick_uninvolved_reviewer(obj["raised_by"])
            if reviewer is None:
                skipped.append({
                    "challenge_id": f"C{len(challenges) + len(skipped) + 1:02d}",
                    "issue_id": obj["issue_id"],
                    "target": obj["target"],
                    "reason": "all_participants_involved",
                })
                continue
            c_props, c_map = _anon_proposals(obj["claims"])
            c_bundle = {
                "title": f"Contradiction adjudication on {obj['target']}",
                "target": obj["target"],
                "proposals": c_props,
            }
            challenges.append({
                "challenge_id": f"C{len(challenges) + 1:02d}",
                "type": "contradiction",
                "issue_id": obj["issue_id"],
                "target": obj["target"],
                "reviewer": reviewer,
                "run_id": run_id,
                "task_sha256": task_sha256,
                "bundle_sha256": sha256_hex(canonical_json(c_bundle)),
                "proposal_map": c_map,
                "bundle": c_bundle,
            })
        else:
            author = obj["raised_by"][0]
            avail = [m for m in models if m != author and m not in set(missing_models)]
            if not avail:
                avail = [m for m in models if m != author]
            fresh = [m for m in avail if m not in used_reviewers]
            pool_cands = fresh or avail
            if not pool_cands:
                skipped.append({
                    "challenge_id": f"C{len(challenges) + len(skipped) + 1:02d}",
                    "issue_id": obj["issue_id"],
                    "target": obj["target"],
                    "reason": "no_uninvolved_reviewer",
                })
                continue
            best_rev = max(pool_cands, key=lambda c: weights.get((c, author), 0.0))
            used_reviewers.add(best_rev)
            s_props, s_map = _anon_proposals(obj["claims"])
            s_bundle = {
                "title": f"Independent verification of high-severity singleton on {obj['target']}",
                "target": obj["target"],
                "proposals": s_props,
            }
            challenges.append({
                "challenge_id": f"C{len(challenges) + 1:02d}",
                "type": "singleton_audit",
                "issue_id": obj["issue_id"],
                "target": obj["target"],
                "reviewer": best_rev,
                "run_id": run_id,
                "task_sha256": task_sha256,
                "bundle_sha256": sha256_hex(canonical_json(s_bundle)),
                "proposal_map": s_map,
                "bundle": s_bundle,
            })

    if cfg.get("use_derangement") and len(challenges) < max_challenges:
        for reviewer, target_seat in max_weight_derangement(models, weights):
            if len(challenges) >= max_challenges:
                break
            seat_findings = (findings_by_model.get(target_seat, {}).get("findings") or [])[:5]
            if not seat_findings:
                continue
            d_props, d_map = _anon_proposals(
                [{"claim": f.get("claim", ""), "evidence": f.get("evidence", [])} for f in seat_findings if isinstance(f, dict)]
            )
            d_bundle = {
                "title": "Complementary peer verification of anonymized proposals",
                "proposals": d_props,
            }
            challenges.append({
                "challenge_id": f"C{len(challenges) + 1:02d}",
                "type": "derangement_peer",
                "reviewer": reviewer,
                "target": target_seat,
                "run_id": run_id,
                "task_sha256": task_sha256,
                "bundle_sha256": sha256_hex(canonical_json(d_bundle)),
                "proposal_map": d_map,
                "bundle": d_bundle,
            })

    return registry, challenges, skipped


def stage_merge(
    stream_dir: Path,
    participants: list[ParticipantSpec],
    *,
    mode: str = "standard",
) -> dict[str, Any]:
    models = [p.id for p in participants]
    if len(models) < 2:
        raise ValueError("stage merge requires at least 2 participants")
    findings_by_model = {m: load_or_extract_findings(stream_dir, m) for m in models}
    manifest_p = stream_dir / "run-manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.is_file() else {}
    _purge_downstream_stream_files(stream_dir, include_plan_outputs=False)
    registry, challenges, skipped = plan_challenges(
        models,
        findings_by_model,
        mode=mode,
        missing_models=manifest.get("missing_models", []),
        run_id=manifest.get("run_id"),
        task_sha256=manifest.get("task_sha256"),
    )
    (stream_dir / "issue-registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (stream_dir / "challenge-plan.json").write_text(
        json.dumps(challenges, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if skipped:
        (stream_dir / "challenge-skipped.json").write_text(
            json.dumps(skipped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    summary_lines = [
        f"# Issue Graph Summary ({mode})",
        "",
        f"- Participants: {', '.join(models)}",
        f"- Corroborated clusters: {len(registry['consensus'])}",
        f"- Singletons: {len(registry['singletons'])}",
        f"- Contradictions: {len(registry['contradictions'])}",
        f"- Planned challenges: {len(challenges)}",
        "",
    ]
    (stream_dir / "graph-summary.md").write_text("\n".join(summary_lines), encoding="utf-8")
    return {
        "stage": "merge",
        "stats": registry["stats"],
        "planned_challenges": len(challenges),
        "skipped_challenges": len(skipped),
    }


def stage_challenge(
    stream_dir: Path,
    task_path: Path,
    participants: list[ParticipantSpec],
    *,
    timeout_s: int = 900,
) -> dict[str, Any]:
    plan_p = stream_dir / "challenge-plan.json"
    if not plan_p.is_file():
        raise FileNotFoundError("Missing challenge-plan.json; run --stage merge first")
    challenges = json.loads(plan_p.read_text(encoding="utf-8"))
    if not challenges:
        return {"stage": "challenge", "replied": 0, "total": 0}
    spec_by_id = {p.id: p for p in participants}
    task_file = safe_path(task_path, must_exist=True)
    actual_task_sha = sha256_hex(task_file.read_bytes())

    manifest_p = stream_dir / "run-manifest.json"
    reg_p = stream_dir / "issue-registry.json"
    if not manifest_p.is_file() or not reg_p.is_file():
        raise FileNotFoundError("Missing run-manifest.json or issue-registry.json; run --stage plan and --stage merge first")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    reg_doc = json.loads(reg_p.read_text(encoding="utf-8"))
    reg_meta = reg_doc.get("metadata") if isinstance(reg_doc, Mapping) and isinstance(reg_doc.get("metadata"), Mapping) else {}
    exp_run_id = manifest.get("run_id")
    exp_task_sha = manifest.get("task_sha256")
    if not exp_run_id or exp_task_sha != actual_task_sha:
        raise ValueError("Task file SHA-256 differs from active run-manifest.json; re-run stage_plan first")
    if reg_meta.get("run_id") != exp_run_id or reg_meta.get("task_sha256") != actual_task_sha:
        raise ValueError("issue-registry.json run_id/task_sha256 disagrees with active run-manifest.json")
    for ch_item in challenges:
        if ch_item.get("run_id") != exp_run_id or ch_item.get("task_sha256") != actual_task_sha:
            raise ValueError("challenge-plan.json run_id/task_sha256 disagrees with active task file")

    for old in list(stream_dir.glob("challenge-reply-*.md")) + list(stream_dir.glob("challenge-meta-*.json")):
        old.unlink(missing_ok=True)

    item_by_key: dict[str, dict[str, Any]] = {}
    statuses: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(challenges), 8)) as pool:
        futs = {}
        for item in challenges:
            cid = validate_participant_id(item["challenge_id"])
            rev_id = validate_participant_id(item["reviewer"])
            sp = spec_by_id.get(rev_id, ParticipantSpec(id=rev_id, executor="mock", model=rev_id))
            bundle_p = stream_dir / f"bundle-{cid}.json"
            out_p = stream_dir / f"challenge-reply-{cid}-{rev_id}.md"
            prompt_p = stream_dir / f"prompt-challenge-{cid}-{rev_id}.txt"
            bundle_p.write_text(json.dumps(item["bundle"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            prompt_p.write_text(
                CHALLENGE_PROMPT_TEMPLATE.format(task_path=task_file, bundle_path=bundle_p, out_path=out_p),
                encoding="utf-8",
            )
            placeholders = {
                "model": sp.model or sp.id,
                "provider": sp.provider,
                "prompt_path": str(prompt_p),
                "bundle_path": str(bundle_p),
                "out_path": str(out_p),
                "task_path": str(task_file),
            }
            key = f"{cid}:{rev_id}"
            item_by_key[key] = item
            futs[pool.submit(_run_participant_command, sp, placeholders, stream_dir, timeout_s)] = key

        for fut in concurrent.futures.as_completed(futs):
            key = futs[fut]
            ok, err, wall = fut.result()
            if ok:
                item = item_by_key[key]
                cid = item["challenge_id"]
                rev_id = item["reviewer"]
                out_p = stream_dir / f"challenge-reply-{cid}-{rev_id}.md"
                meta_p = stream_dir / f"challenge-meta-{cid}-{rev_id}.json"
                b_sha = item.get("bundle_sha256") or sha256_hex(canonical_json(item["bundle"]))
                meta_p.write_text(
                    json.dumps(
                        {
                            "challenge_id": cid,
                            "reviewer": rev_id,
                            "run_id": item.get("run_id"),
                            "task_sha256": item.get("task_sha256"),
                            "bundle_sha256": b_sha,
                            "reply_sha256": sha256_hex(out_p.read_text(encoding="utf-8")),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            statuses[key] = {"success": ok, "error": err, "wall_seconds": wall}

    replied = sum(1 for v in statuses.values() if v["success"])
    return {"stage": "challenge", "replied": replied, "total": len(challenges), "statuses": statuses}


_STRICT_VERDICT_LINE_RE = re.compile(
    r"^(?:[-*+]\s*)?(?:【\s*(CONCEDE|REFUTED|UNRESOLVED(?:\s*:[^】]*)?)\s*】|\[(CONCEDE|REFUTED|UNRESOLVED)\])\s+"
    r"Proposal-([1-9]\d*)(?:\s*[:：\-—]\s*|\s+)(\S.*)$",
    re.I,
)


def _parse_structured_stances(
    text: str,
    valid_pkeys: set[str],
) -> dict[str, Any]:
    """Parse stance lines with strict anchored Proposal-N validation against valid_pkeys."""
    conceded: list[str] = []
    refuted: list[str] = []
    unresolved: list[str] = []
    by_proposal: dict[str, set[str]] = {}
    invalid_refs: list[str] = []
    conflicting_line = False
    unscoped_concede_or_refute = False
    fence_char: Optional[str] = None
    fence_len = 0

    for line in text.splitlines():
        s = line.strip()
        if fence_char is None:
            m_open = re.match(r"^(`{3,}|~{3,})", s)
            if m_open is not None:
                tok = m_open.group(1)
                fence_char = tok[0]
                fence_len = len(tok)
                continue
        else:
            if re.match(rf"^{re.escape(fence_char)}{{{fence_len},}}\s*$", s):
                fence_char = None
                fence_len = 0
            continue
        if not s or s.startswith(">") or re.match(r"^\|[\s\-:|]+\|$", s):
            continue
        is_c = bool(re.search(r"(?:【\s*CONCEDE\s*】|\[CONCEDE\])", s, re.I))
        is_r = bool(re.search(r"(?:【\s*REFUTED\s*】|\[REFUTED\])", s, re.I))
        is_u = bool(re.search(r"(?:【\s*UNRESOLVED|\[UNRESOLVED\])", s, re.I))
        tag_count = int(is_c) + int(is_r) + int(is_u)
        if tag_count == 0:
            continue
        if tag_count > 1:
            conflicting_line = True
            continue

        m = _STRICT_VERDICT_LINE_RE.match(s)
        if m is None:
            invalid_refs.append("malformed_verdict_line")
            unscoped_concede_or_refute = True
            continue
        # Reject lines mentioning multiple Proposal tokens in the body to keep 1 line = 1 Proposal verdict
        extra_props = re.findall(r"Proposal[-\s]*\S+", m.group(4), re.I)
        if extra_props:
            invalid_refs.append("multiple_proposals_on_line")
            continue

        raw_tag = (m.group(1) or m.group(2) or "").strip().upper()
        stance = "conceded" if raw_tag == "CONCEDE" else ("refuted" if raw_tag == "REFUTED" else "unresolved")
        pk = f"proposal{m.group(3)}"
        if pk not in valid_pkeys:
            invalid_refs.append(pk)
            continue
        by_proposal.setdefault(pk, set()).add(stance)

        excerpt = s[:240]
        if stance == "conceded":
            conceded.append(excerpt)
        elif stance == "refuted":
            refuted.append(excerpt)
        else:
            unresolved.append(excerpt)

    return {
        "conceded": conceded,
        "refuted": refuted,
        "unresolved": unresolved,
        "by_proposal": by_proposal,
        "invalid_refs": invalid_refs,
        "conflicting_line": conflicting_line,
        "unscoped_concede_or_refute": unscoped_concede_or_refute,
    }


def _evidence_check(evidence_list: Iterable[Any], base_dirs: Iterable[Path]) -> tuple[list[str], list[str], list[str]]:
    verified: list[str] = []
    missing: list[str] = []
    unverified: list[str] = []
    bases = list(base_dirs)
    for raw_e in evidence_list or []:
        e = str(raw_e).strip()
        if not e:
            continue
        loc = re.sub(r":\d+(?:-\d+)?$", "", e)
        if _ABS_PATH_RE.match(e):
            if os.path.exists(loc):
                verified.append(e)
            else:
                missing.append(e)
        elif _EXT_RE.search(loc):
            if any((b / loc).exists() for b in bases):
                verified.append(e)
            else:
                unverified.append(e)
        else:
            unverified.append(e)
    return verified, missing, unverified


def synthesize_deliberation(
    registry: Mapping[str, Any],
    planned_challenges: list[dict[str, Any]],
    replies_by_cid: Mapping[str, str],
    *,
    skipped_challenges: list[dict[str, Any]] = (),
    base_dirs: Iterable[Path] = (),
    participants_meta: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    missing_challenges: list[dict[str, Any]] = []
    conceded_items: list[dict[str, Any]] = []
    refuted_items: list[dict[str, Any]] = []
    unresolved_contested: list[dict[str, Any]] = []
    refuted_claims_by_issue: dict[str, set[int | str]] = {}
    adjudicated_contradiction_issues: set[str] = set()

    for item in planned_challenges:
        cid = item["challenge_id"]
        rev = item["reviewer"]
        if cid not in replies_by_cid:
            missing_challenges.append({
                "challenge_id": cid,
                "reviewer": rev,
                "issue_id": item.get("issue_id"),
                "target": item.get("target"),
                "reason": "missing_reply",
            })
            continue
        prop_map = dict(item.get("proposal_map")) if isinstance(item.get("proposal_map"), Mapping) else {}
        bundle_props = list((item.get("bundle") or {}).get("proposals") or [])
        valid_pkeys = set(prop_map.keys()) or {f"proposal{k}" for k in range(1, len(bundle_props) + 1)}
        parsed = _parse_structured_stances(replies_by_cid[cid], valid_pkeys)
        c_list = parsed["conceded"]
        r_list = parsed["refuted"]
        u_list = parsed["unresolved"]
        by_prop: dict[str, set[str]] = parsed["by_proposal"]

        if parsed["invalid_refs"] or parsed["conflicting_line"]:
            missing_challenges.append({
                "challenge_id": cid,
                "reviewer": rev,
                "issue_id": item.get("issue_id"),
                "target": item.get("target"),
                "reason": "invalid_proposal_reference" if parsed["invalid_refs"] else "conflicting_stance_line",
            })
            continue

        if not (c_list or r_list or u_list):
            missing_challenges.append({
                "challenge_id": cid,
                "reviewer": rev,
                "issue_id": item.get("issue_id"),
                "target": item.get("target"),
                "reason": "no_valid_stance_tag",
            })
            continue

        src_name = f"challenge-reply-{cid}-{rev}.md"
        for ex in c_list:
            conceded_items.append({"source_file": src_name, "status": "conceded", "excerpt": ex})
        for ex in r_list:
            refuted_items.append({"source_file": src_name, "status": "refuted", "excerpt": ex})
        for ex in u_list:
            unresolved_contested.append({"source_file": src_name, "status": "unresolved_contested", "excerpt": ex})

        if item.get("type") == "contradiction" and item.get("issue_id"):
            # Contradiction closes ONLY when every real Proposal in bundle has a single unambiguous verdict,
            # no UNRESOLVED tags exist, and surviving CONCEDEd proposals are mutually consistent (no opposing pair).
            all_covered = bool(valid_pkeys) and set(by_prop.keys()) == valid_pkeys
            unambiguous = all(len(st_set) == 1 and "unresolved" not in st_set for st_set in by_prop.values())
            conceded_pkeys = [pk for pk, st_set in by_prop.items() if st_set == {"conceded"}]
            has_surviving_conceded = bool(conceded_pkeys)
            not_all_conceded = len(valid_pkeys) < 2 or any("refuted" in st_set for st_set in by_prop.values())

            surviving_consistent = True
            contr_entry = next(
                (ce for ce in (registry.get("contradictions") or []) if str(ce.get("issue_id")) == str(item["issue_id"])),
                None,
            )
            orig_claims = list(contr_entry.get("claims") or []) if isinstance(contr_entry, Mapping) else []
            if orig_claims and len(conceded_pkeys) >= 2:
                surviving_claims: list[dict[str, Any]] = []
                for pk in conceded_pkeys:
                    orig_idx = int(prop_map[pk]) if pk in prop_map else int(pk.removeprefix("proposal"))
                    if 1 <= orig_idx <= len(orig_claims):
                        surviving_claims.append(orig_claims[orig_idx - 1])
                if len(surviving_claims) >= 2:
                    wrapped = [{"model": f"surv-{idx}", "raw": cl} for idx, cl in enumerate(surviving_claims)]
                    if _has_polarity_contradiction(wrapped) or _has_claim_text_opposition([str(cl.get("claim") or "") for cl in surviving_claims]):
                        surviving_consistent = False

            if (
                all_covered
                and unambiguous
                and has_surviving_conceded
                and not_all_conceded
                and surviving_consistent
                and not u_list
                and not parsed["unscoped_concede_or_refute"]
            ):
                adjudicated_contradiction_issues.add(str(item["issue_id"]))

        elif item.get("type") == "singleton_audit" and item.get("issue_id"):
            iid_s = str(item["issue_id"])
            for pk, st_set in by_prop.items():
                if st_set != {"refuted"}:
                    continue
                if pk in prop_map:
                    refuted_claims_by_issue.setdefault(iid_s, set()).add(int(prop_map[pk]))
                elif not prop_map and pk in valid_pkeys:
                    idx_num = int(pk.removeprefix("proposal"))
                    if 1 <= idx_num <= len(bundle_props):
                        refuted_claims_by_issue.setdefault(iid_s, set()).add(idx_num)

    unresolved_ledger: list[dict[str, Any]] = list(unresolved_contested)
    ghost_discarded: list[dict[str, Any]] = []

    for s in registry.get("singletons") or []:
        iid = str(s.get("issue_id") or "")
        ref_claims = refuted_claims_by_issue.get(iid, set())
        claims = list(s.get("claims") or [])
        if "all" in ref_claims:
            continue
        if ref_claims and len(claims) > 1:
            claims = [cl for idx, cl in enumerate(claims, 1) if idx not in ref_claims]
            if not claims:
                continue
        elif ref_claims and len(claims) <= 1:
            continue

        sev = str(s.get("severity") or "P2").upper()
        if sev not in ("P0", "P1"):
            continue
        all_ev: list[Any] = []
        for cl in claims:
            all_ev.extend(cl.get("evidence") or [])
        if not all_ev:
            continue
        verified, missing, unverified = _evidence_check(all_ev, base_dirs)
        if not verified and missing and not unverified:
            ghost_discarded.append({"issue_id": iid, "target": s["target"], "ghost_evidence": missing})
            continue
        unresolved_ledger.append({
            "issue_id": iid,
            "target": s["target"],
            "assertion_key": s.get("assertion_key"),
            "raised_by": s["raised_by"],
            "claims": claims,
            "severity": sev,
            "provenance": s.get("provenance", "model_written"),
            "evidence_verified": verified,
            "evidence_unverified": unverified,
            "evidence_missing": missing,
            "reason": "Minority preservation: unrefuted P0/P1 singleton with concrete locators",
        })

    contradictions = list(registry.get("contradictions") or [])
    uncontested_contradictions = [c for c in contradictions if str(c.get("issue_id")) not in adjudicated_contradiction_issues]
    missing_models = list((registry.get("metadata") or {}).get("missing_models") or [])

    if missing_challenges or missing_models:
        conv_status = "PARTIAL_PROGRESS"
    elif unresolved_ledger or uncontested_contradictions or skipped_challenges:
        conv_status = "UNRESOLVED_CONTESTED"
    else:
        conv_status = "CONVERGED"

    meta = registry.get("metadata") or {}
    models = list(meta.get("models") or [])
    p_list = participants_meta or [{"id": m, "executor": "mock"} for m in models]
    receipt = {
        "protocol": "review-run-receipt-1.0",
        "run_id": str(meta.get("run_id") or f"run-{uuid.uuid4().hex[:12]}"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "panel_id": f"panel-{meta.get('mode', 'standard')}",
        "participants": [
            {
                "id": str(p["id"]),
                "executor": str(p.get("executor") or "command"),
                "provider": str(p.get("provider") or "custom"),
                "model": str(p.get("model") or p["id"]),
            }
            for p in p_list
        ],
        "phases": {
            "plan": {"missing_models": missing_models},
            "merge": dict(registry.get("stats") or {}),
            "challenge": {
                "planned": len(planned_challenges),
                "replied": len(replies_by_cid),
                "missing": len(missing_challenges),
                "skipped": len(skipped_challenges),
            },
            "synthesize": {
                "conceded": len(conceded_items),
                "refuted": len(refuted_items),
                "ghost_discarded": len(ghost_discarded),
                "unresolved_ledger_count": len(unresolved_ledger),
            },
        },
        "convergence": {
            "status": conv_status,
            "unresolved_issues_count": len(unresolved_ledger) + len(uncontested_contradictions),
        },
    }

    return {
        "convergence_status": conv_status,
        "consensus": list(registry.get("consensus") or []),
        "contradictions": contradictions,
        "uncontested_contradictions": uncontested_contradictions,
        "conceded": conceded_items,
        "refuted": refuted_items,
        "missing_challenges": missing_challenges,
        "ghost_discarded": ghost_discarded,
        "unresolved_ledger": unresolved_ledger,
        "receipt": receipt,
    }


def stage_synthesize(stream_dir: Path) -> dict[str, Any]:
    reg_p = stream_dir / "issue-registry.json"
    if not reg_p.is_file():
        raise FileNotFoundError("Missing issue-registry.json; run --stage merge first")
    registry = json.loads(reg_p.read_text(encoding="utf-8"))
    plan_p = stream_dir / "challenge-plan.json"
    planned = json.loads(plan_p.read_text(encoding="utf-8")) if plan_p.is_file() else []
    skip_p = stream_dir / "challenge-skipped.json"
    skipped = json.loads(skip_p.read_text(encoding="utf-8")) if skip_p.is_file() else []
    manifest_p = stream_dir / "run-manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.is_file() else {}

    reg_meta = registry.get("metadata") or {}
    if manifest:
        if manifest.get("run_id") and reg_meta.get("run_id") != manifest.get("run_id"):
            raise ValueError("Stale issue-registry.json does not match current run-manifest.json run_id; re-run --stage merge")
        if manifest.get("task_sha256") and reg_meta.get("task_sha256") != manifest.get("task_sha256"):
            raise ValueError("Stale issue-registry.json does not match current run-manifest.json task_sha256; re-run --stage merge")
        if manifest.get("task_path") and Path(manifest["task_path"]).is_file():
            live_task_sha = sha256_hex(Path(manifest["task_path"]).read_bytes())
            if manifest.get("task_sha256") and live_task_sha != manifest.get("task_sha256"):
                raise ValueError("Task file changed after --stage plan; re-run --stage plan and --stage merge")

    replies_by_cid: dict[str, str] = {}
    for item in planned:
        cid = item["challenge_id"]
        rev = item["reviewer"]
        rp = stream_dir / f"challenge-reply-{cid}-{rev}.md"
        meta_rp = stream_dir / f"challenge-meta-{cid}-{rev}.json"
        if not rp.is_file() or not meta_rp.is_file():
            continue
        reply_text = rp.read_text(encoding="utf-8")
        try:
            rmeta = json.loads(meta_rp.read_text(encoding="utf-8"))
        except Exception:
            continue
        exp_b_sha = item.get("bundle_sha256") or sha256_hex(canonical_json(item["bundle"]))
        if (
            rmeta.get("challenge_id") != cid
            or rmeta.get("reviewer") != rev
            or rmeta.get("run_id") != item.get("run_id")
            or rmeta.get("task_sha256") != item.get("task_sha256")
            or rmeta.get("bundle_sha256") != exp_b_sha
            or rmeta.get("reply_sha256") != sha256_hex(reply_text)
        ):
            continue
        replies_by_cid[cid] = reply_text

    syn = synthesize_deliberation(
        registry,
        planned,
        replies_by_cid,
        skipped_challenges=skipped,
        base_dirs=[stream_dir, Path.cwd()],
        participants_meta=manifest.get("participants"),
    )

    (stream_dir / "unresolved-ledger.json").write_text(
        json.dumps(syn["unresolved_ledger"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (stream_dir / "review-run-receipt.json").write_text(
        json.dumps(syn["receipt"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    md = [
        "# Multi-Model Cross-Review Deliberation Report (v2 Sparse Deliberation)",
        "",
        f"- Convergence status: **{syn['convergence_status']}**",
        f"- Corroborated findings: {len(syn['consensus'])}",
        f"- Contradictions: {len(syn['contradictions'])}",
        f"- Challenge conceded: {len(syn['conceded'])}",
        f"- Challenge refuted: {len(syn['refuted'])}",
        f"- Missing challenge replies: {len(syn['missing_challenges'])}",
        f"- Minority-protected unresolved ledger: {len(syn['unresolved_ledger'])}",
        "",
        "## 1. Corroborated Findings",
        "",
    ]
    if not syn["consensus"]:
        md.append("None.")
    for item in syn["consensus"]:
        md.append(f"### [{item['issue_id']}] `{item['target']}` ({item['severity']}) — {', '.join(item['raised_by'])}")
        for cl in item.get("claims") or []:
            md.append(f"- **{cl['model']}**: {cl['claim']}")
    md.extend(["", "## 2. Contradictions & Challenge Verdicts", ""])
    for m_miss in syn["missing_challenges"]:
        md.append(f"- **[MISSING]** `{m_miss['challenge_id']}` assigned to `{m_miss['reviewer']}` on `{m_miss.get('target')}`")
    for c_item in syn["conceded"]:
        md.append(f"- **[CONCEDED]** ({c_item['source_file']}): {c_item['excerpt']}")
    for r_item in syn["refuted"]:
        md.append(f"- **[REFUTED]** ({r_item['source_file']}): {r_item['excerpt']}")
    md.extend(["", "## 3. Minority-Protected Unresolved Ledger", ""])
    if not syn["unresolved_ledger"]:
        md.append("Empty.")
    for u_item in syn["unresolved_ledger"]:
        if "issue_id" in u_item:
            md.append(f"- **[{u_item['issue_id']}]** `{u_item['target']}` ({u_item['severity']}) raised by {', '.join(u_item['raised_by'])}")
        else:
            md.append(f"- **[UNRESOLVED]** ({u_item.get('source_file')}): {u_item.get('excerpt')}")
    md.append("")
    (stream_dir / "consensus-report.md").write_text("\n".join(md), encoding="utf-8")
    return {
        "stage": "synthesize",
        "convergence_status": syn["convergence_status"],
        "unresolved_count": len(syn["unresolved_ledger"]),
        "missing_challenges": len(syn["missing_challenges"]),
        "receipt": syn["receipt"],
    }


def stage_status(stream_dir: Path) -> dict[str, Any]:
    files = sorted(p.name for p in stream_dir.iterdir() if p.is_file()) if stream_dir.is_dir() else []
    receipt_p = stream_dir / "review-run-receipt.json"
    receipt = json.loads(receipt_p.read_text(encoding="utf-8")) if receipt_p.is_file() else None
    return {
        "stage": "status",
        "stream_dir": str(stream_dir),
        "exists": stream_dir.is_dir(),
        "files": files,
        "convergence": receipt["convergence"] if receipt else None,
    }


def deliberate_inline(
    findings_by_model: Mapping[str, Any],
    *,
    mode: str = "standard",
    challenge_replies: Optional[Mapping[str, str]] = None,
    base_dir: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Deterministic inline MCP entry: cluster findings, plan anonymous challenges, and optionally synthesize."""
    if not isinstance(findings_by_model, Mapping) or len(findings_by_model) < 2:
        raise ValueError("findings_by_model must map at least 2 distinct participant IDs to finding lists/objects")
    models = [validate_participant_id(str(k)) for k in findings_by_model.keys()]
    normalized_map: dict[str, dict[str, Any]] = {}
    for raw_k, raw_v in findings_by_model.items():
        pid = validate_participant_id(str(raw_k))
        if isinstance(raw_v, list):
            normalized_map[pid] = {"findings": raw_v}
        elif isinstance(raw_v, dict) and isinstance(raw_v.get("findings"), list):
            normalized_map[pid] = {"findings": raw_v["findings"]}
        else:
            raise ValueError(f"Findings for {pid!r} must be a list or an object with 'findings'")

    inline_task_sha = sha256_hex(canonical_json({"mode": mode, "findings_by_model": normalized_map}))
    inline_run_id = f"inline-{inline_task_sha[:12]}"
    registry, challenges, skipped = plan_challenges(
        models,
        normalized_map,
        mode=mode,
        run_id=inline_run_id,
        task_sha256=inline_task_sha,
    )
    weights = compute_complementarity_matrix(models, normalized_map)
    derangement = max_weight_derangement(models, weights)
    out: dict[str, Any] = {
        "registry": registry,
        "challenge_plan": challenges,
        "skipped_challenges": skipped,
        "derangement_pairings": [{"reviewer": r, "target": t} for r, t in derangement],
    }
    if challenge_replies is not None:
        bases = [safe_path(base_dir, must_exist=True)] if base_dir else [Path.cwd()]
        verified_inline: dict[str, str] = {}
        by_cid = {c["challenge_id"]: c for c in challenges}
        for raw_cid, raw_rep in challenge_replies.items():
            cid = str(raw_cid)
            ch_item = by_cid.get(cid)
            if ch_item is None:
                continue
            exp_b_sha = ch_item.get("bundle_sha256")
            if isinstance(raw_rep, Mapping):
                rep_txt = str(raw_rep.get("text") if raw_rep.get("text") is not None else raw_rep.get("reply") or "")
                b_sha = raw_rep.get("bundle_sha256")
                r_id = raw_rep.get("run_id")
                t_sha = raw_rep.get("task_sha256")
                if b_sha != exp_b_sha:
                    continue
                if r_id is not None and r_id != inline_run_id:
                    continue
                if t_sha is not None and t_sha != inline_task_sha:
                    continue
                verified_inline[cid] = rep_txt
            # Unbound plain-string inline replies cannot close challenges across distinct tasks/bundles
        out["synthesis"] = synthesize_deliberation(
            registry,
            challenges,
            verified_inline,
            skipped_challenges=skipped,
            base_dirs=bases,
        )
    return out
