# -*- coding: utf-8 -*-
"""五人异构模型交叉编排器 v2 (Sparse Adaptive Deliberation):
基于信息增量、结构化 Issue 拓扑与自适应质询的稀疏通信评审系统。

核心设计原则 (v2):
1. 独立盲审 (Blind Independent Society): 五个异构模型互不可见的第一阶段；
2. 结构化 Issue 提取: 每个模型产出 Markdown 的同时强制落盘 findings sidecar JSON；
3. 本地零成本归并: 聚类 Consensus、Singleton 与 Contradiction，计算互补矩阵；
4. 匿名定向质询: 只审关键 Issue，质询者排除争议当事人，议题包匿名乱序；
5. 少数派证据保护: 有证据的少数派绝不被多数票吞没。

断言级 Issue identity (第二轮裁决修复):
- Issue 身份 = canonical_target + assertion_key。显式 issue_key 优先；
- 无 issue_key 时以归一化 claim 短哈希兜底 (宁拆不并, 绝不凭空合并);
- 同一模型对同一身份的多条 findings 全部保留, 不再静默丢弃;
- 多模型聚合且无互斥 polarity 的展示名一律用 "多模型互证 (Corroborated)"
  而非 "Verified Consensus" (模型共识不是证据, 出处谱系才是证据)。

运行谱系 (run lineage):
- 每个 plan run 写入 run-manifest.json (run_id, task_sha256, model_set, missing_models);
- plan 开始前清理本轮模型的旧 review/findings/log; challenge 开始前清理旧答复与议题包;
- 报告头展示 run_id 与任务摘要, 缺失模型显式列名。

用法:
    python orchestrate_v2.py <stream_dir> --task <task.md> --stage plan [--mode standard]
    python orchestrate_v2.py <stream_dir> --stage merge [--mode standard]
    python orchestrate_v2.py <stream_dir> --stage challenge [--mode standard]
    python orchestrate_v2.py <stream_dir> --stage synthesize
    python orchestrate_v2.py <stream_dir> --stage status
    python orchestrate_v2.py <stream_dir> --task <task.md> --stage all [--mode standard]
"""
import argparse
import glob
import hashlib
import itertools
import json
import os
import random
import re
import subprocess
import sys
import time

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

MODELS = {
    "kimi-k3": ("kimi", "kimi-k3"),
    "dsv4pro": ("deepseek", "deepseek-v4-pro"),
    "glm53": ("zai", "glm-5.3"),
    "gemini38flash": ("google", "gemini-3.8-flash"),
    "gemini31pro": ("google", "gemini-3.1-pro-preview"),
}

DEFAULT_MODELS = list(MODELS)

MODE_PRESETS = {
    "economy": {
        "models": ["kimi-k3", "dsv4pro", "gemini38flash"],
        "max_challenges": 1,
        "description": "经济模式 (3 模型盲审, 最多 1 次质询, 共 3-4 次调用)",
    },
    "standard": {
        "models": ["kimi-k3", "dsv4pro", "glm53", "gemini38flash", "gemini31pro"],
        "max_challenges": 3,
        "description": "标准模式 (5 模型盲审, 最多 3 次质询, 共 5-8 次调用, 默认推荐)",
    },
    "audit": {
        "models": ["kimi-k3", "dsv4pro", "glm53", "gemini38flash", "gemini31pro"],
        "max_challenges": 5,
        "use_derangement": True,
        "description": "审计模式 (5 模型盲审, 最多 5 次质询, 配额有余时追加互补错排, 共 5-10 次调用)",
    },
}

POLL_SECONDS = 15
TIMEOUT_SECONDS = 40 * 60
RNG_SEED = 20260917

VALID_SEVERITY = {"P0", "P1", "P2"}
VALID_KINDS = {"bug", "security", "invariant", "perf", "spec_mismatch", "suggestion"}
VALID_POLARITY = {"present", "absent", "positive", "negative"}
_SEV_RANK = {"P0": 3, "P1": 2, "P2": 1}

PLAN_PROMPT_V2 = """任务：评审任务书并独立产出方案与结构化发现。

您是一名独立评审者。请在完全不参考其他任何外部评审者意见的前提下，独立完成以下工作：

一、阅读任务书文件 {task_path}。
二、阅读任务书中指定的全部材料。
三、按任务书要求完成工作，将完整文字产出写入文件 {out_path}。
四、同时将严格 JSON 格式的结构化发现**独立写入文件 {findings_path}**（必须实际写出该文件，不能只嵌在 Markdown 文本中），格式如下：

```json
{{
  "findings": [
    {{
      "id": "F1",
      "target": "涉及的具体文件路径 (尽量带父目录与行号范围)",
      "issue_key": "可选的断言身份键: 同一具体问题请用同一个简短键, 如 'cluster-consensus-rule'",
      "kind": "bug|security|invariant|perf|spec_mismatch|suggestion",
      "claim": "发现的核心断言（一两句话说明问题实体与结论）",
      "polarity": "可选：present|absent|positive|negative，表示您对该目标的主张方向",
      "evidence": ["支持该断言的具体文件行号、测试用例或逻辑推导"],
      "severity": "P0|P1|P2",
      "blocking": true
    }}
  ],
  "unknowns": ["材料中未明示或当前无法独立求证的事项"],
  "assumptions": ["您在评估中做出的关键假设"]
}}
```

约束：
- 只读任务书与指定材料，不得修改任何现有文件；不得修改其他评审者的产出文件；
- 输出用简体中文，按您自然的文风写作；
- 产出必须基于您实际读到的内容，严禁虚构不存在的文件、接口或测试结果；
- findings JSON 必须写入 {findings_path}，kind 与 severity 只能使用上述枚举值；
- issue_key 用于跨评审者的断言对齐：不同评审者对同一具体问题请使用含义相同的键；不同问题请使用不同键。
"""

CHALLENGE_PROMPT_V2 = """任务：对匿名方案的分歧点与独有发现进行定向交叉质询。

您将审查一份来自对等评审者的匿名观点摘要（包含争议项或独有高危发现）。
任务书路径: {task_path}
质询议题包: {bundle_path}
您的质询答复写入: {out_path}

匿名纪律：本任务为匿名质询。您不得读取同目录下任何 review-*.md、findings-*.json 等他人产出文件来推断观点来源身份，只依据任务书与质询议题包作答。

请严格按以下四步顺序作答，不得直接宣布同意或反对：

第一步【提取增量】：
提取议题包中对方提出、但我方此前未注意到的新事实、新证据或新分析路径。若无新事实，明确写明“无新增量”。

第二步【核验反例】：
对议题包中的每个断言，依据代码源码、规范或物理约束，尝试寻找可证伪的反例、边界条件或证据漏洞。

第三步【分歧归因】：
明确双方分歧的根因究竟是：证据不足、规范解读不一致、还是代码实现层面的确定性缺陷。

第四步【裁决与表态】（逐断言表态，同一答复允许出现多种标记）：
- 若对方证据确凿（有不可辩驳的代码行号、测试用例或逻辑证明），请明确标注 【CONCEDE】（认同并吸收对方观点），严禁无理辩护；
- 若确属对方错误，给出明确的反例与反证并标注 【REFUTED】；
- 若双方各有论据且现有输入无法断定，标注 【UNRESOLVED_REQUIRES_CODE_VERIFICATION】，并提出验证该分歧所需的最小实验或测试用例；
- 严禁以多数票为由否定附有具体代码证据的少数派意见。
"""

_TARGET_BASENAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+\.(?:py|json|md|sh|ps1|yaml|yml|toml|txt|csv)$")
_FILE_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:py|json|md|sh|ps1|yaml|yml|toml|txt|csv)")
_ABS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")
OPPOSING_POLARITY = {
    ("present", "absent"), ("absent", "present"),
    ("positive", "negative"), ("negative", "positive"),
}


def dedup_preserve_order(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def spawn(model_key, prompt_path, log_path):
    provider, model = MODELS[model_key]
    cmd = ["hermes", "chat", "--query-file", prompt_path, "--oneshot",
           "-m", model, "--provider", provider]
    if model_key == "glm53":
        cmd += ["--reasoning", "low"]
    with open(log_path, "wb") as log:
        return subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT,
            cwd=os.getcwd(),
        )


def wait_for_outputs(out_paths, procs, timeout=TIMEOUT_SECONDS):
    """轮询产物文件落盘与进程退出; 返回 {path: bool}, 单个模型失败不判负整阶段。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if all(p.poll() is not None for p in procs):
            break
        time.sleep(POLL_SECONDS)
    for p in procs:
        if p.poll() is None:
            p.terminate()
    return {p: (os.path.exists(p) and os.path.getsize(p) > 0) for p in out_paths}


def _write_manifest(stream, task_path, model_keys, mode, missing_models=None):
    """写/更新 run-manifest.json, 记录运行谱系。"""
    manifest_path = os.path.join(stream, "run-manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}
    if manifest.get("run_id") is None:
        manifest["run_id"] = time.strftime("%Y%m%d-%H%M%S")
    if manifest.get("task_sha256") is None and os.path.exists(task_path):
        with open(task_path, "rb") as f:
            manifest["task_sha256"] = hashlib.sha256(f.read()).hexdigest()[:16]
    manifest["model_set"] = model_keys
    manifest["mode"] = mode
    manifest["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if missing_models is not None:
        manifest["missing_models"] = missing_models
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def _read_manifest(stream):
    manifest_path = os.path.join(stream, "run-manifest.json")
    if not os.path.exists(manifest_path):
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _clean_stale_plan_outputs(stream, model_keys):
    """重跑防护: 清理本轮模型名下的旧 review/findings/log, 防止旧产物冒充本轮结果。"""
    for k in model_keys:
        for name in (f"review-{k}.md", f"findings-{k}.json", f"log-{k}.txt"):
            p = os.path.join(stream, name)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _clean_stale_challenge_outputs(stream):
    for pat in ("challenge-reply-*.md", "bundle-*.json", "log-challenge-*.txt",
                "prompt-challenge-*.txt"):
        for p in glob.glob(os.path.join(stream, pat)):
            try:
                os.remove(p)
            except OSError:
                pass


def _mark_provenance(data, provenance):
    for f in data.get("findings", []):
        if isinstance(f, dict):
            f.setdefault("provenance", provenance)
    data.setdefault("_meta", {})["provenance"] = provenance
    return data


def _extract_json_object_from_text(text):
    """平衡括号解析: 从文本中提取第一个含 findings 键的 JSON 对象。"""
    dec = json.JSONDecoder()
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx] not in "{[":
            idx += 1
        if idx >= n:
            break
        try:
            obj, end = dec.raw_decode(text, idx)
        except json.JSONDecodeError:
            idx += 1
            continue
        if isinstance(obj, dict) and "findings" in obj:
            return obj
        idx = end
    return None


def _is_plausible_target(t):
    return bool(_TARGET_BASENAME_RE.match(t)) and not re.search(r"[\\\[\]()*+?{}^$|]", t)


def _validate_findings(data, provenance):
    """schema 校验: 非法条目丢弃并计数, 不崩。"""
    raw = data.get("findings")
    if not isinstance(raw, list):
        data.setdefault("_meta", {})["dropped"] = [{"reason": "findings not a list"}]
        data["findings"] = []
        return data
    kept, dropped = [], []
    for i, f in enumerate(raw):
        if not isinstance(f, dict):
            dropped.append({"index": i, "reason": "not an object"})
            continue
        reasons = []
        if not isinstance(f.get("target", ""), str) or not f.get("target", "").strip():
            reasons.append("bad target")
        if str(f.get("severity", "")).upper() not in VALID_SEVERITY:
            reasons.append("bad severity")
        if not isinstance(f.get("claim", ""), str):
            reasons.append("bad claim")
        ev = f.get("evidence", [])
        if not isinstance(ev, list) or not all(isinstance(e, str) for e in ev):
            reasons.append("bad evidence")
        pol = str(f.get("polarity", "")).strip().lower()
        if pol and pol not in VALID_POLARITY:
            reasons.append("bad polarity")
        if reasons:
            dropped.append({"index": i, "reason": ",".join(reasons)})
            continue
        f2 = dict(f)
        f2["severity"] = str(f["severity"]).upper()
        f2["polarity"] = pol
        f2.setdefault("provenance", provenance)
        kept.append(f2)
    if dropped:
        print(f"[findings] schema 校验丢弃 {len(dropped)} 条非法 finding", file=sys.stderr)
        data.setdefault("_meta", {})["dropped"] = dropped
    data["findings"] = kept
    return data


def extract_findings_json(stream, model_key):
    """提取模型的结构化 findings:
    1) 优先读模型亲写 sidecar (plan 阶段已清理陈旧文件, 只可能是本轮产物);
    2) 缺失时从 review md 平衡提取 JSON 块并落盘 sidecar;
    3) 最后降级为启发式合成, 带 provenance=synthetic_fallback 标记。
    所有路径统一走 schema 校验。
    """
    json_path = os.path.join(stream, f"findings-{model_key}.json")

    if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("findings"), list):
                return _validate_findings(_mark_provenance(data, "model_written"), "model_written")
            print(f"[findings] {model_key} sidecar 非对象形状, 回退提取", file=sys.stderr)
        except Exception as e:
            print(f"[findings] {model_key} sidecar 解析失败 ({e}), 回退提取", file=sys.stderr)

    md_path = os.path.join(stream, f"review-{model_key}.md")
    content = ""
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

    obj = _extract_json_object_from_text(content) if content else None
    if obj is not None:
        data = _validate_findings(_mark_provenance(obj, "model_written"), "model_written")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return data

    fallback_findings = []
    for line in content.splitlines():
        if line.startswith("#"):
            continue
        for m in re.finditer(r"([A-Za-z0-9_.\-]+\.(?:py|json|md|sh|ps1|yaml|yml|toml|txt|csv))(?::(\d+(?:-\d+)?))?", line):
            target = m.group(1)
            if not _is_plausible_target(target):
                continue
            loc = target + ((":" + m.group(2)) if m.group(2) else "")
            sev = "P0" if any(w in line for w in ("崩溃", "误杀", "强杀", "致命", "死锁", "crash", "kill")) else (
                "P1" if any(w in line for w in ("漏洞", "盲区", "缺陷", "缺失", "逃逸", "bug", "flaw")) else "P2"
            )
            fallback_findings.append({
                "id": f"F{len(fallback_findings)+1}",
                "target": target,
                "kind": "suggestion",
                "claim": line.strip()[:140],
                "evidence": [loc],
                "severity": sev,
                "blocking": (sev == "P0"),
                "provenance": "synthetic_fallback",
            })
            break
    res = {"findings": fallback_findings[:15], "unknowns": [], "assumptions": [],
           "_meta": {"provenance": "synthetic_fallback"}}
    if fallback_findings:
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
    return res


def normalize_target(target_str):
    """canonical 目标归一: 文件名 + 最后一个父目录段 (区分 src/config.py 与 tests/config.py)。
    优先从复合描述中提取文件名 token; 裸文件名与带路径写法不再强行等价 (宁拆不并)。
    """
    if not target_str:
        return "general"
    s = str(target_str).strip()
    s = re.sub(r":\d+(?:-\d+)?$", "", s)
    s = s.replace("\\", "/").lower()
    m = _FILE_TOKEN_RE.search(s)
    if m:
        fname = m.group(0)
        prefix = s[:m.start()].rstrip("/")
        parts = [p for p in prefix.split("/") if p and p not in ("c:", "d:")]
        if parts:
            return parts[-1] + "/" + fname
        return fname
    s = s.strip("/")
    parts = [p for p in s.split("/") if p and p not in ("c:", "d:")]
    if not parts:
        return "general"
    return "/".join(parts[-2:])


def _issue_identity(item):
    """断言级 issue 身份: (canonical_target, assertion_key)。
    显式 issue_key 优先; 无 issue_key 用归一化 claim 短哈希兜底 (宁拆不并, 绝不凭空合并)。
    """
    target = normalize_target(item.get("target", ""))
    key = str(item.get("issue_key", "")).strip().lower()
    if key:
        return (target, "k:" + key)
    claim_norm = re.sub(r"\s+", "", str(item.get("claim", ""))).lower()
    if claim_norm:
        h = hashlib.sha256(claim_norm.encode("utf-8")).hexdigest()[:12]
        return (target, "c:" + h)
    return (target, "anon")


def compute_complementarity_matrix(models, findings_by_model):
    weights = {}
    targets_by_model = {
        m: {normalize_target(f.get("target", "")) for f in findings_by_model.get(m, {}).get("findings", [])}
        for m in models
    }
    for i in models:
        for j in models:
            if i == j:
                continue
            w = 1.0
            t_i = targets_by_model[i]
            t_j = targets_by_model[j]
            union = t_i | t_j
            inter = t_i & t_j
            if union:
                overlap = len(inter) / len(union)
                w += (1.0 - overlap) * 2.0
            f_j = findings_by_model.get(j, {}).get("findings", [])
            for item in f_j:
                tgt = normalize_target(item.get("target", ""))
                sev = item.get("severity", "P2").upper()
                if tgt not in t_i:
                    if sev == "P0":
                        w += 3.0
                    elif sev == "P1":
                        w += 1.5
                else:
                    w += 0.5
            weights[(i, j)] = round(w, 2)
    return weights


def max_weight_derangement(models, weights):
    n = len(models)
    if n < 2:
        return []
    best_score = -1e9
    best_perm = None
    for perm in itertools.permutations(models):
        if any(m == t for m, t in zip(models, perm)):
            continue
        score = sum(weights.get((m, t), 0.0) for m, t in zip(models, perm))
        if score > best_score:
            best_score = score
            best_perm = perm
    if best_perm is None:
        return [(models[i], models[(i + 1) % n]) for i in range(n)]
    return list(zip(models, best_perm))


def _has_polarity_contradiction(items):
    pol_by_model = {}
    for x in items:
        pol = str(x["raw"].get("polarity", "")).strip().lower()
        if not pol:
            continue
        pol_by_model.setdefault(x["model"], set()).add(pol)
    models_with_pol = list(pol_by_model)
    for a in range(len(models_with_pol)):
        for b in range(a + 1, len(models_with_pol)):
            for pa in pol_by_model[models_with_pol[a]]:
                for pb in pol_by_model[models_with_pol[b]]:
                    if (pa, pb) in OPPOSING_POLARITY:
                        return True
    return False


def cluster_issues(models, findings_by_model):
    """断言级聚类:
    - 身份 = (canonical_target, assertion_key), 显式 issue_key 优先, 无则 claim 哈希兜底;
    - 单模型多条 findings 全部保留 (claims 列表完整), 不再只取第一条;
    - 矛盾仅由互斥 polarity 判定; 其余多模型聚合为 consensus (展示名 Corroborated)。
    """
    by_identity = {}
    for m in models:
        raw_items = findings_by_model.get(m, {}).get("findings", [])
        for item in raw_items:
            ident = _issue_identity(item)
            by_identity.setdefault(ident, []).append({"model": m, "raw": item})

    consensus, singletons, contradictions = [], [], []
    issue_counter = 1
    for (tgt, key), items in by_identity.items():
        raised = dedup_preserve_order([x["model"] for x in items])
        severity = max((x["raw"].get("severity", "P2") for x in items),
                       key=lambda s: _SEV_RANK.get(s, 0))
        claims = [{"model": x["model"], "claim": x["raw"].get("claim", ""),
                   "evidence": x["raw"].get("evidence", []),
                   "polarity": x["raw"].get("polarity", ""),
                   "severity": x["raw"].get("severity", "P2")} for x in items]
        entry = {
            "issue_id": f"I{issue_counter:02d}",
            "target": tgt,
            "assertion_key": key,
            "raised_by": raised,
            "severity": severity,
            "claims": claims,
            "state": "singleton" if len(raised) == 1 else
                     ("contradiction" if _has_polarity_contradiction(items) else "consensus"),
        }
        if entry["state"] == "singleton":
            singletons.append(entry)
        elif entry["state"] == "contradiction":
            contradictions.append(entry)
        else:
            consensus.append(entry)
        issue_counter += 1

    return consensus, singletons, contradictions


def stage_plan_v2(stream, task_path, model_keys):
    """Phase 1: 独立盲审与生成 (清理陈旧产物 + manifest 谱系 + 单模型失败不判负)。"""
    _clean_stale_plan_outputs(stream, model_keys)
    _write_manifest(stream, task_path, model_keys, "plan")

    out_paths, procs = [], []
    for k in model_keys:
        prompt_path = os.path.join(stream, f"prompt-{k}.txt")
        out_path = os.path.join(stream, f"review-{k}.md")
        findings_path = os.path.join(stream, f"findings-{k}.json")
        log_path = os.path.join(stream, f"log-{k}.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(PLAN_PROMPT_V2.format(
                task_path=task_path,
                out_path=out_path,
                findings_path=findings_path
            ))
        procs.append(spawn(k, prompt_path, log_path))
        out_paths.append(out_path)
        print(f"[plan-v2] {k} 已启动 pid={procs[-1].pid}")

    results = wait_for_outputs(out_paths, procs)
    missing = [k for k, p in zip(model_keys, out_paths) if not results.get(p, False)]
    if missing:
        print(f"[plan-v2] 警告: 无产出模型: {', '.join(missing)}", file=sys.stderr)
    _write_manifest(stream, task_path, model_keys, "plan", missing_models=missing)

    for k in model_keys:
        extract_findings_json(stream, k)

    ok = any(results.values())
    print(f"[plan-v2] {'完成' if ok else '全部失败'} "
          f"{json.dumps({os.path.basename(p): v for p, v in results.items()}, ensure_ascii=False)}")
    return ok


def stage_merge_v2(stream, model_keys, mode="standard"):
    """Phase 2: 断言级聚类与质询规划 (纯本地, 零 LLM 消耗)。"""
    findings_by_model = {k: extract_findings_json(stream, k) for k in model_keys}
    consensus, singletons, contradictions = cluster_issues(model_keys, findings_by_model)
    weights = compute_complementarity_matrix(model_keys, findings_by_model)
    rng = random.Random(RNG_SEED)
    manifest = _read_manifest(stream)
    missing_models = (manifest or {}).get("missing_models", [])

    registry = {
        "metadata": {"mode": mode, "models": model_keys,
                     "missing_models": missing_models,
                     "run_id": (manifest or {}).get("run_id"),
                     "task_sha256": (manifest or {}).get("task_sha256"),
                     "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")},
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

    reg_path = os.path.join(stream, "issue-registry.json")
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    cfg = MODE_PRESETS.get(mode, MODE_PRESETS["standard"])
    max_challenges = cfg["max_challenges"]
    challenges = []
    skipped_challenges = []

    def anon_proposals(claim_items):
        props = [{"source_alias": None, "claim": x["claim"], "evidence": x.get("evidence", [])}
                 for x in claim_items]
        rng.shuffle(props)
        for i, p in enumerate(props):
            p["source_alias"] = f"Proposal-{i+1}"
        return props

    def pick_reviewer(excluded_models):
        """排除当事人后按互补权重选取; 无匿名候选时返回 None (绝不退回当事人)。"""
        candidates = [m for m in model_keys if m not in set(excluded_models)]
        if not candidates:
            return None
        anchor = next((m for m in excluded_models if m in model_keys), candidates[0])
        return max(candidates, key=lambda cand: weights.get((cand, anchor), 0.0))

    # 质询候选按 severity 排序 (P0 单例优先于 P2 矛盾), 同 severity 下矛盾优先
    ranked = []
    for c in contradictions:
        ranked.append((_SEV_RANK.get(c["severity"], 0), 2, ("contradiction", c)))
    for s in singletons:
        if s.get("severity") in ("P0", "P1"):
            ranked.append((_SEV_RANK.get(s["severity"], 0), 1, ("singleton_audit", s)))
    ranked.sort(key=lambda r: (-r[0], -r[1]))

    used_reviewers = set()
    for _, _, (ctype, obj) in ranked:
        if len(challenges) >= max_challenges:
            break
        if ctype == "contradiction":
            reviewer = pick_reviewer(obj["raised_by"])
            if reviewer is None:
                skipped_challenges.append({"challenge_id": f"C{len(challenges)+len(skipped_challenges)+1:02d}",
                                           "issue_id": obj["issue_id"], "target": obj["target"],
                                           "reason": "全部模型均为当事人, 无匿名候选"})
                continue
            challenges.append({
                "challenge_id": f"C{len(challenges)+1:02d}",
                "type": "contradiction",
                "issue_id": obj["issue_id"],
                "target": obj["target"],
                "reviewer": reviewer,
                "bundle": {
                    "title": f"关于 {obj['target']} 的对立断言裁决",
                    "target": obj["target"],
                    "proposals": anon_proposals(obj["claims"]),
                },
            })
        else:
            author = obj["raised_by"][0]
            candidates = [m for m in model_keys if m != author and m not in used_reviewers]
            if not candidates:
                candidates = [m for m in model_keys if m != author]
            if not candidates:
                skipped_challenges.append({"challenge_id": f"C{len(challenges)+len(skipped_challenges)+1:02d}",
                                           "issue_id": obj["issue_id"], "target": obj["target"],
                                           "reason": "无可用非当事人模型"})
                continue
            best_reviewer = max(candidates,
                                key=lambda cand: weights.get((cand, author), 0.0))
            used_reviewers.add(best_reviewer)
            proposals = anon_proposals(obj["claims"])
            challenges.append({
                "challenge_id": f"C{len(challenges)+1:02d}",
                "type": "singleton_audit",
                "issue_id": obj["issue_id"],
                "target": obj["target"],
                "reviewer": best_reviewer,
                "bundle": {
                    "title": f"对未覆盖单例高危断言的独立核验: {obj['target']}",
                    "target": obj["target"],
                    "proposals": proposals,
                },
            })

    if cfg.get("use_derangement") and len(challenges) < max_challenges:
        derange_pairs = max_weight_derangement(model_keys, weights)
        for reviewer, target in derange_pairs:
            if len(challenges) >= max_challenges:
                break
            proposals = anon_proposals([
                {"claim": f.get("claim", ""), "evidence": f.get("evidence", [])}
                for f in findings_by_model.get(target, {}).get("findings", [])[:5]
            ])
            challenges.append({
                "challenge_id": f"C{len(challenges)+1:02d}",
                "type": "derangement_peer",
                "reviewer": reviewer,
                "target": target,
                "bundle": {
                    "title": "针对匿名方案的互补性审查",
                    "target": target,
                    "proposals": proposals,
                },
            })

    plan_path = os.path.join(stream, "challenge-plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(challenges, f, ensure_ascii=False, indent=2)
    if skipped_challenges:
        skip_path = os.path.join(stream, "challenge-skipped.json")
        with open(skip_path, "w", encoding="utf-8") as f:
            json.dump(skipped_challenges, f, ensure_ascii=False, indent=2)

    summary_path = os.path.join(stream, "graph-summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# Issue Graph Summary ({mode})\n\n")
        f.write(f"- 参与模型: {', '.join(model_keys)}\n")
        f.write(f"- 缺失模型: {', '.join(missing_models) if missing_models else '无'}\n")
        f.write(f"- 多模型互证 (Corroborated): {len(consensus)} 项\n")
        f.write(f"- 独有发现 (Singleton): {len(singletons)} 项\n")
        f.write(f"- 断言级对立 (Contradiction): {len(contradictions)} 项\n")
        f.write(f"- 生成针对性质询任务: {len(challenges)} 组\n")
        if skipped_challenges:
            f.write(f"- 因无匿名候选跳过的质询: {len(skipped_challenges)} 组\n")
        f.write("\n")
        if contradictions:
            f.write("## 核心分歧清单\n\n")
            for c in contradictions:
                f.write(f"### [{c['issue_id']}] 目标: `{c['target']}`\n")
                for cl in c["claims"]:
                    f.write(f"- **{cl['model']}**: {cl['claim']} (证据: {', '.join(cl['evidence']) if cl['evidence'] else '无'})\n")
                f.write("\n")

    print(f"[merge-v2] 归并完成: {len(consensus)} 互证, {len(singletons)} 单例, "
          f"{len(contradictions)} 对立 -> 规划 {len(challenges)} 组质询, 跳过 {len(skipped_challenges)} 组")
    return True


def stage_challenge_v2(stream, task_path):
    """Phase 3: 定向匿名质询执行 (清理陈旧答复 + 单模型失败不判负)。"""
    plan_path = os.path.join(stream, "challenge-plan.json")
    if not os.path.exists(plan_path):
        print("[challenge-v2] 缺失质询计划，请先运行 --stage merge", file=sys.stderr)
        return False

    with open(plan_path, "r", encoding="utf-8") as f:
        challenges = json.load(f)

    if not challenges:
        print("[challenge-v2] 无需针对性质询 (零冲突或预算已饱和)")
        return True

    _clean_stale_challenge_outputs(stream)

    out_paths, procs = [], []
    for item in challenges:
        cid = item["challenge_id"]
        reviewer = item["reviewer"]
        bundle_path = os.path.join(stream, f"bundle-{cid}.json")
        out_path = os.path.join(stream, f"challenge-reply-{cid}-{reviewer}.md")
        log_path = os.path.join(stream, f"log-challenge-{cid}-{reviewer}.txt")
        prompt_path = os.path.join(stream, f"prompt-challenge-{cid}-{reviewer}.txt")

        with open(bundle_path, "w", encoding="utf-8") as f:
            json.dump(item["bundle"], f, ensure_ascii=False, indent=2)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(CHALLENGE_PROMPT_V2.format(
                task_path=task_path,
                bundle_path=bundle_path,
                out_path=out_path,
            ))
        procs.append(spawn(reviewer, prompt_path, log_path))
        out_paths.append(out_path)
        print(f"[challenge-v2] 启动质询 {cid}: 由 {reviewer} 审查 pid={procs[-1].pid}")

    results = wait_for_outputs(out_paths, procs)
    for item, p in zip(challenges, out_paths):
        if not results.get(p, False):
            print(f"[challenge-v2] 警告: 质询 {item['challenge_id']} ({item['reviewer']}) 无答复", file=sys.stderr)

    ok = any(results.values())
    print(f"[challenge-v2] {'完成' if ok else '全部失败'} "
          f"{json.dumps({os.path.basename(p): v for p, v in results.items()}, ensure_ascii=False)}")
    return ok


def _parse_stances(text):
    conceded, refuted, unresolved = [], [], []
    for line in text.splitlines():
        s = line.strip()
        if re.search(r"【\s*CONCEDE\s*】", s):
            conceded.append(s[:200])
        elif re.search(r"【\s*REFUTED\s*】", s):
            refuted.append(s[:200])
        elif re.search(r"【\s*UNRESOLVED", s):
            unresolved.append(s[:200])
    return conceded, refuted, unresolved


def _evidence_check(evidence_list, base_dirs):
    """证据校验: 绝对路径必须真实存在; 相对路径在 base_dirs/cwd 命中即 verified;
    未命中的文件样式相对引用标 unverified (不丢弃, 不冒充 verified)。"""
    verified, unverified = [], []
    for e in (evidence_list or []):
        e = str(e).strip()
        if _ABS_PATH_RE.match(e):
            (verified if os.path.exists(e) else unverified).append(e)
            continue
        loc = re.sub(r":\d+(?:-\d+)?$", "", e)
        hit = any(os.path.exists(os.path.join(b, loc)) for b in base_dirs)
        if hit or not re.search(r"\.(?:py|json|md|sh|ps1|yaml|yml|toml|txt|csv)$", loc):
            verified.append(e)
        else:
            unverified.append(e)
    return verified, unverified


def stage_synthesize_v2(stream):
    """Phase 4: 对账、逐断言表态、少数派证据保护 (与 REFUTED 联动 + 证据校验)。"""
    reg_path = os.path.join(stream, "issue-registry.json")
    if not os.path.exists(reg_path):
        print("[synthesize-v2] 缺失 issue-registry.json", file=sys.stderr)
        return False
    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    plan_path = os.path.join(stream, "challenge-plan.json")
    planned = []
    if os.path.exists(plan_path):
        with open(plan_path, "r", encoding="utf-8") as f:
            planned = json.load(f)

    base_dirs = [stream, os.getcwd()]

    replies_by_cid = {}
    missing_challenges = []
    for item in planned:
        cid = item["challenge_id"]
        reviewer = item["reviewer"]
        reply_path = os.path.join(stream, f"challenge-reply-{cid}-{reviewer}.md")
        if os.path.exists(reply_path):
            with open(reply_path, "r", encoding="utf-8") as f:
                replies_by_cid[cid] = {"issue_id": item.get("issue_id"), "type": item.get("type"),
                                       "reviewer": reviewer, "target": item.get("target"),
                                       "text": f.read()}
        else:
            missing_challenges.append({"challenge_id": cid, "reviewer": reviewer,
                                       "issue_id": item.get("issue_id"), "target": item.get("target")})

    conceded_items, refuted_items, unresolved_contested = [], [], []
    refuted_issue_ids = set()
    for cid, reply in replies_by_cid.items():
        conceded, refuted, unresolved = _parse_stances(reply["text"])
        for excerpt in conceded:
            conceded_items.append({"source_file": f"challenge-reply-{cid}-{reply['reviewer']}.md",
                                   "status": "conceded", "excerpt": excerpt})
        for excerpt in refuted:
            refuted_items.append({"source_file": f"challenge-reply-{cid}-{reply['reviewer']}.md",
                                  "status": "refuted", "excerpt": excerpt})
            if reply.get("issue_id"):
                refuted_issue_ids.add(reply["issue_id"])
        for excerpt in unresolved:
            unresolved_contested.append({"source_file": f"challenge-reply-{cid}-{reply['reviewer']}.md",
                                         "status": "unresolved_contested", "excerpt": excerpt})

    unresolved_ledger = list(unresolved_contested)
    ghost_discarded = []
    unverified_evidence = []
    for s in registry.get("singletons", []):
        if s.get("issue_id") in refuted_issue_ids:
            continue
        sev = s.get("severity")
        if sev not in ("P0", "P1"):
            continue
        all_evidence = []
        for cl in s.get("claims", []):
            all_evidence.extend(cl.get("evidence") or [])
        if not all_evidence:
            continue
        verified, unverified = _evidence_check(all_evidence, base_dirs)
        abs_ghost = [u for u in unverified if _ABS_PATH_RE.match(u)]
        rel_unverified = [u for u in unverified if not _ABS_PATH_RE.match(u)]
        if not verified and abs_ghost and not rel_unverified:
            ghost_discarded.append({"issue_id": s["issue_id"], "target": s["target"],
                                    "ghost_evidence": abs_ghost})
            continue
        if unverified:
            unverified_evidence.append({"issue_id": s["issue_id"], "target": s["target"],
                                        "unverified_evidence": unverified})
        unresolved_ledger.append({
            "issue_id": s["issue_id"],
            "target": s["target"],
            "assertion_key": s.get("assertion_key"),
            "raised_by": s["raised_by"],
            "claims": s["claims"],
            "severity": sev,
            "evidence_verified": verified,
            "evidence_unverified": unverified,
            "reason": "少数派附证据独立发现 (Minority preservation: unrefuted finding with concrete locators)",
        })

    ledger_path = os.path.join(stream, "unresolved-ledger.json")
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(unresolved_ledger, f, ensure_ascii=False, indent=2)

    manifest = _read_manifest(stream) or {}
    contradictions = registry.get("contradictions", [])
    consensus = registry.get("consensus", [])
    missing_models = registry.get("metadata", {}).get("missing_models", [])
    report_path = os.path.join(stream, "consensus-report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 五人交叉评审合议报告 (v2 Sparse Deliberation)\n\n")
        f.write(f"- 合议生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- run_id: {manifest.get('run_id', '?')}  任务摘要: {manifest.get('task_sha256', '?')[:8]}\n")
        f.write(f"- 评审模式: {registry.get('metadata', {}).get('mode', 'standard')}\n")
        f.write(f"- 模型阵容: {', '.join(registry.get('metadata', {}).get('models', []))}\n")
        if missing_models:
            f.write(f"- 缺失模型 (本轮无产出): {', '.join(missing_models)}\n")
        f.write(f"- 多模型互证 (Corroborated): {len(consensus)} 项\n")
        f.write(f"- 质询认同/认输 (Conceded): {len(conceded_items)} 项\n")
        f.write(f"- 质询证伪驳回 (Refuted): {len(refuted_items)} 项\n")
        f.write(f"- 未决保护账本 (Unresolved Ledger): {len(unresolved_ledger)} 项\n")
        f.write(f"- 质询缺失 (Missing Replies): {len(missing_challenges)} 项\n")
        if ghost_discarded:
            f.write(f"- 幽灵证据丢弃: {len(ghost_discarded)} 项\n")
        if unverified_evidence:
            f.write(f"- 证据未验证 (入账但标注): {len(unverified_evidence)} 项\n")
        f.write("\n")

        f.write("## 一、多模型互证发现 (Corroborated Model Findings)\n\n")
        f.write("（注意: 模型共识不是证据, 本表只表示多个模型指向同一断言身份, 出处谱系才是证据。）\n\n")
        if not consensus:
            f.write("（无多模型一致项）\n\n")
        for it in consensus:
            f.write(f"### [{it['issue_id']}] `{it['target']}` ({it['severity']})\n")
            f.write(f"- 提出方: {', '.join(it['raised_by'])}\n")
            all_ev = []
            for cl in it.get("claims", []):
                f.write(f"  - {cl['model']}: {cl['claim']}\n")
                all_ev.extend(cl.get("evidence") or [])
            verified, unverified = _evidence_check(all_ev, base_dirs)
            tag = "已验证" if not unverified else f"部分未验证: {len(unverified)} 条"
            f.write(f"- 证据状态: {tag}\n\n")

        f.write("## 二、断言级对立与质询 (Contradictions & Cross-Examination)\n\n")
        if not contradictions and not missing_challenges:
            f.write("（无对立断言, 质询计划全部答复）\n\n")
        for c in contradictions:
            f.write(f"### [{c['issue_id']}] `{c['target']}` (contradiction)\n")
            for cl in c.get("claims", []):
                pol = f" [polarity={cl['polarity']}]" if cl.get("polarity") else ""
                f.write(f"  - {cl['model']}{pol}: {cl['claim']}\n")
            for cid, reply in replies_by_cid.items():
                if reply.get("issue_id") == c["issue_id"]:
                    conceded, refuted, unresolved = _parse_stances(reply["text"])
                    for ex in conceded + refuted + unresolved:
                        f.write(f"    - 质询表态: {ex}\n")
            f.write("\n")
        other_replies = [r for r in replies_by_cid.values() if r.get("type") != "contradiction"]
        if other_replies:
            f.write("### 单例/互补质询答复\n\n")
            for reply in other_replies:
                conceded, refuted, unresolved = _parse_stances(reply["text"])
                f.write(f"- 质询 {reply['reviewer']} (target `{reply.get('target', '?')}`):\n")
                for ex in conceded + refuted + unresolved:
                    f.write(f"    - {ex}\n")
            f.write("\n")
        if missing_challenges:
            f.write("### 质询缺失清单 (MISSING)\n\n")
            for m in missing_challenges:
                f.write(f"- 质询 {m['challenge_id']} (issue {m.get('issue_id', '?')}, reviewer {m['reviewer']}, target `{m.get('target', '?')}`) 无答复文件\n")
            f.write("\n")

        f.write("## 三、未决项与少数派保护账本 (Unresolved Ledger)\n\n")
        if not unresolved_ledger:
            f.write("（所有分歧均已收敛达成闭环）\n\n")
        for u in unresolved_ledger:
            f.write(f"### `{u.get('target', 'General')}` [{u.get('severity', 'P1')}]\n")
            f.write(f"- 来源: {u.get('raised_by', [u.get('source_file')])}\n")
            for cl in u.get("claims", [u]):
                if isinstance(cl, dict):
                    f.write(f"- 断言 ({cl.get('model')}): {cl.get('claim', '')}\n")
                else:
                    f.write(f"- 断言: {cl}\n")
            if u.get("evidence_verified"):
                f.write(f"- 证据(已验证): `{', '.join(u['evidence_verified'])}`\n")
            if u.get("evidence_unverified"):
                f.write(f"- 证据(未验证): `{', '.join(u['evidence_unverified'])}`\n")
            f.write(f"- 说明: {u.get('reason', '经质询仍存分歧，需真实测试验证')}\n\n")
        if ghost_discarded:
            f.write("## 四、幽灵证据丢弃记录 (Ghost Evidence Discarded)\n\n")
            for g in ghost_discarded:
                f.write(f"- [{g['issue_id']}] `{g['target']}`: 证据路径不存在, 已拒绝入账: {', '.join(g['ghost_evidence'])}\n")
            f.write("\n")

    print(f"[synthesize-v2] 合议报告已生成, 未决账本: {len(unresolved_ledger)} 项, "
          f"质询缺失: {len(missing_challenges)} 项, 幽灵丢弃: {len(ghost_discarded)} 项")
    return True


def stage_status_v2(stream):
    patterns = (
        "task.md", "review-*.md", "findings-*.json", "issue-registry.json",
        "graph-summary.md", "challenge-plan.json", "bundle-*.json",
        "challenge-reply-*.md", "consensus-report.md", "unresolved-ledger.json",
        "run-manifest.json", "log-*.txt",
    )
    total_files = 0
    for pat in patterns:
        found = sorted(glob.glob(os.path.join(stream, pat)))
        if found:
            print(f"{pat}: {len(found)} 个")
            total_files += len(found)
            for p in found:
                print(f"  {os.path.basename(p)} ({os.path.getsize(p)} 字节)")
    if total_files == 0:
        print(f"[status-v2] 目录内无任务产物: {stream}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="五人异构模型交叉编排器 v2 (Sparse Adaptive Deliberation)")
    parser.add_argument("stream_dir", help="任务流目录")
    parser.add_argument("--task", default="task.md", help="任务书路径 (默认流目录内 task.md)")
    parser.add_argument("--stage", choices=["plan", "merge", "challenge", "synthesize", "status", "all"], required=True)
    parser.add_argument("--mode", choices=["economy", "standard", "audit"], default="standard",
                        help="评审拓扑与预算模式: economy (3模型/快速), standard (5模型/常规默认), audit (5模型/严格审计)")
    parser.add_argument("--models", default=None,
                        help="手动覆盖模型列表 (逗号分隔短名)")
    args = parser.parse_args(argv)

    stream = os.path.abspath(args.stream_dir)
    os.makedirs(stream, exist_ok=True)
    task_path = args.task if os.path.isabs(args.task) else os.path.join(stream, args.task)

    if args.models:
        model_keys = [k.strip() for k in args.models.split(",") if k.strip()]
    else:
        model_keys = MODE_PRESETS.get(args.mode, MODE_PRESETS["standard"])["models"]

    for k in model_keys:
        if k not in MODELS:
            print(f"未知模型短名: {k}, 可用: {', '.join(MODELS)}", file=sys.stderr)
            return 2

    if args.stage == "status":
        stage_status_v2(stream)
        return 0

    if not os.path.exists(task_path) and args.stage in ("plan", "challenge", "all"):
        print(f"任务书缺失: {task_path}", file=sys.stderr)
        return 2

    if args.stage == "plan":
        return 0 if stage_plan_v2(stream, task_path, model_keys) else 1
    elif args.stage == "merge":
        return 0 if stage_merge_v2(stream, model_keys, mode=args.mode) else 1
    elif args.stage == "challenge":
        return 0 if stage_challenge_v2(stream, task_path) else 1
    elif args.stage == "synthesize":
        return 0 if stage_synthesize_v2(stream) else 1
    elif args.stage == "all":
        print(f"=== 运行全流程 (Mode: {args.mode}) ===")
        if not stage_plan_v2(stream, task_path, model_keys):
            return 1
        if not stage_merge_v2(stream, model_keys, mode=args.mode):
            return 1
        if not stage_challenge_v2(stream, task_path):
            return 1
        if not stage_synthesize_v2(stream):
            return 1
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
