# -*- coding: utf-8 -*-
"""五人异构模型交叉编排器 v2 (Sparse Adaptive Deliberation):
基于信息增量、结构化 Issue 拓扑与自适应质询的稀疏通信评审系统。

核心设计原则 (v2):
1. 独立盲审 (Blind Independent Society): 五个异构模型互不可见的第一阶段；
2. 结构化 Issue 提取: 每个模型产出 Markdown 的同时强制落盘 findings sidecar JSON；
3. 本地零成本归并: 聚类 Consensus、Singleton 与 Contradiction，计算互补矩阵；
4. 匿名定向质询: 只审关键 Issue，质询者排除争议当事人，议题包匿名乱序；
5. 少数派证据保护: 有证据的少数派绝不被多数票吞没。

断言级 Issue identity:
- Issue 身份 = canonical_target + assertion_key。显式 issue_key 优先；
- 无 issue_key 时以归一化 claim 短哈希兜底 (宁拆不并, 绝不凭空合并);
- 同一模型对同一身份的多条 findings 全部保留, 不再静默丢弃;
- 多模型聚合且无互斥 polarity 的展示名一律用 "多模型互证 (Corroborated)"
  而非 "Verified Consensus" (模型共识不是证据, 出处谱系才是证据)。

canonical target (RV-02):
- 保留完整相对路径 (去盘符、行号、大小写与斜杠归一), 防止不同真实文件
  (如两个技能的 scripts/watch.py) 被归一成同一个目标;
- 复合描述 (文件名+函数+行号, 无路径前缀) 提取文件名 token;
- 绝对路径与相对路径写法不强行等价 (宁拆不并)。

运行谱系 (run lineage, RV-01):
- 每次 plan 都是新 run: run_id 与 task_sha256 强制重算, 并清理全部上轮产物;
- merge/challenge/synthesize 单阶段调用 = 恢复运行, 沿用 manifest;
- 报告头展示 run_id 与任务摘要, 缺失模型与异常退出显式列名。

证据三分 (RV-03/RV-04):
- verified: 绝对路径 (剥行号后) 存在, 或相对路径在 base 目录命中;
- missing: 绝对路径剥行号后不存在 (幽灵证据, 拒绝入账);
- unverified: 相对路径未命中, 或非文件样式的断言文本 (不冒充已验证)。

裁决语义 (RV-05/RV-06/RV-07):
- 表态逐行解析, 三类标记独立收集 (同行混合裁决不丢失);
- 引用行 (以 > 或 | 开头) 中的标签不参与裁决;
- REFUTED 仅在 singleton_audit (单断言议题) 中排除对应 issue;
  contradiction 的 REFUTED 只记录呈现, 不自动关闭整个 issue;
- 报告含收敛状态段: 未答复/被跳过/预算外/证据未验证的项全部列名,
  只有全部收敛才写 "所有分歧均已收敛达成闭环"。

进程状态 (RV-10):
- wait_for_outputs 返回逐项 {file, exit}, 非零退出与缺失文件分开列名;
- 超时 terminate 后等待确认退出。

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
import uuid

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

CANONICAL_PROVIDERS = {
    "kimi": "kimi-coding",
    "google": "gemini",
    "zai": "zai",
    "deepseek": "deepseek",
}


def resolve_provider(model_key: str) -> str:
    """优先使用环境变量指定，或按 CANONICAL_PROVIDERS 规范名解析，默认规范优先 (RV-12)。"""
    env_override = os.environ.get(f"HERMES_{model_key.upper().replace('-', '_')}_PROVIDER")
    if env_override:
        return env_override
    raw_provider, _ = MODELS[model_key]
    if os.environ.get("HERMES_USE_CANONICAL_PROVIDERS", "1").strip().lower() in ("1", "true", "yes"):
        return CANONICAL_PROVIDERS.get(raw_provider, raw_provider)
    return raw_provider

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
      "target": "涉及的具体文件路径 (请写相对仓库根目录的完整路径, 如 skills/xxx/scripts/watch.py)",
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
- issue_key 用于跨评审者的断言对齐：不同评审者对同一具体问题请使用含义相同的键；不同问题请使用不同键；
- target 请使用相对任务书所在仓库根目录的完整路径，保持同文件跨评审者路径一致。
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

第四步【裁决与表态】（逐断言表态，每个断言单独一行给出一种标记，同一答复允许出现多种标记）：
- 若对方证据确凿（有不可辩驳的代码行号、测试用例或逻辑证明），请明确标注 【CONCEDE】（认同并吸收对方观点），严禁无理辩护；
- 若确属对方错误，给出明确的反例与反证并标注 【REFUTED】，注明驳回的是哪一条 Proposal；
- 若双方各有论据且现有输入无法断定，标注 【UNRESOLVED_REQUIRES_CODE_VERIFICATION】，并提出验证该分歧所需的最小实验或测试用例；
- 严禁以多数票为由否定附有具体代码证据的少数派意见。
"""

_TARGET_BASENAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+\.(?:py|json|md|sh|ps1|yaml|yml|toml|txt|csv)$")
_FILE_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:py|json|md|sh|ps1|yaml|yml|toml|txt|csv)")
_ABS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")
_EXT_RE = re.compile(r"\.(?:py|json|md|sh|ps1|yaml|yml|toml|txt|csv)$")
OPPOSING_POLARITY = {
    ("present", "absent"), ("absent", "present"),
    ("positive", "negative"), ("negative", "positive"),
}

_STALE_OUTPUT_PATTERNS = (
    "review-*.md", "findings-*.json", "log-*.txt", "log-challenge-*.txt",
    "issue-registry.json", "graph-summary.md", "challenge-plan.json",
    "challenge-skipped.json", "bundle-*.json", "challenge-reply-*.md",
    "prompt-challenge-*.txt", "consensus-report.md", "unresolved-ledger.json",
)


def dedup_preserve_order(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _minimal_child_env(model_key):
    """构造最小 env allowlist，仅传基础系统变量与当前 provider 所需密钥 (RV-11)。"""
    base_allow = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
        "USERPROFILE", "HOME", "LANG", "LC_ALL", "SHELL", "COMSPEC",
        "HERMES_HOME", "HERMES_CONFIG_DIR", "HERMES_LOG_LEVEL",
    }
    provider_keys = {
        "kimi-k3": ["KIMI_API_KEY", "KIMI_CODING_API_KEY", "MOONSHOT_API_KEY"],
        "dsv4pro": ["DEEPSEEK_API_KEY"],
        "glm53": ["GLM_API_KEY", "ZAI_API_KEY"],
        "gemini38flash": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "gemini31pro": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    }
    allowed = base_allow | set(provider_keys.get(model_key, []))
    env = {}
    for k, v in os.environ.items():
        if k in allowed or k.startswith("HERMES_"):
            env[k] = v
    if "MOONSHOT_API_KEY" in env and "KIMI_API_KEY" not in env:
        env["KIMI_API_KEY"] = env["MOONSHOT_API_KEY"]
    return env


def spawn(model_key, prompt_path, log_path):
    raw_provider, model = MODELS[model_key]
    provider = resolve_provider(model_key)
    cmd = ["hermes", "chat", "--query-file", prompt_path, "--oneshot",
           "--ignore-rules", "-m", model, "--provider", provider]
    if model_key == "glm53":
        cmd += ["--reasoning", "low"]
    with open(log_path, "wb") as log:
        return subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT,
            cwd=os.getcwd(),
            env=_minimal_child_env(model_key),
        )


def wait_for_outputs(out_paths, procs, timeout=TIMEOUT_SECONDS):
    """轮询产物落盘与进程退出 (RV-10):
    返回 {path: {"file": bool, "exit": int|None}}; 文件存在与退出码分开记录。
    超时 terminate 后等待确认退出。采用自适应 0.2s-1.0s 间隔消除无效等待。
    """
    deadline = time.time() + timeout
    poll_interval = 0.2
    while time.time() < deadline:
        if all(p.poll() is not None for p in procs):
            break
        time.sleep(poll_interval)
        if poll_interval < 1.0:
            poll_interval = min(1.0, poll_interval * 1.5)
    for p in procs:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=10)
            except Exception:
                pass
    return {path: {"file": os.path.exists(path) and os.path.getsize(path) > 0,
                   "exit": p.returncode}
            for path, p in zip(out_paths, procs)}


def _task_digest(task_path):
    try:
        h = hashlib.sha256()
        with open(task_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()[:16]
    except OSError:
        return None


def _write_manifest(stream, task_path, model_keys, mode, missing_models=None,
                    run_id=None, started_at=None):
    """每次 plan 调用都强制重算 run_id 与 task_sha256 (RV-01: 任务变更不沿用旧身份)。
    merge/challenge/synthesize 不调用本函数, 只读 manifest = 恢复运行。
    R06: 同一 plan 阶段结束更新 missing_models 时复用已生成的 run_id 与 started_at。
    """
    manifest_path = os.path.join(stream, "run-manifest.json")
    if run_id is None:
        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    if started_at is None:
        started_at = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest = {
        "run_id": run_id,
        "task_sha256": _task_digest(task_path),
        "model_set": model_keys,
        "mode": mode,
        "started_at": started_at,
    }
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


def _clean_stale_plan_outputs(stream, model_keys, task_path=None):
    """RV-01 / R01: 新 run 开始前清理全部上轮产物, 但必须保护任务书与用户输入材料。"""
    task_abs = os.path.abspath(task_path) if task_path else None
    targets_to_clean = set()
    for k in (model_keys or []):
        for pattern in (f"review-{k}.md", f"findings-{k}.json", f"prompt-{k}.txt", f"log-{k}.txt"):
            targets_to_clean.add(os.path.join(stream, pattern))
    fixed_outputs = [
        "issue-registry.json", "graph-summary.md", "challenge-plan.json",
        "challenge-skipped.json", "consensus-report.md", "unresolved-ledger.json",
    ]
    for fn in fixed_outputs:
        targets_to_clean.add(os.path.join(stream, fn))
    for pat in ("bundle-*.json", "challenge-reply-*.md", "prompt-challenge-*.txt", "log-challenge-*.txt"):
        for p in glob.glob(os.path.join(stream, pat)):
            targets_to_clean.add(p)

    for p in targets_to_clean:
        if task_abs and os.path.abspath(p) == task_abs:
            continue
        try:
            if os.path.exists(p):
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
        claim_val = str(f.get("claim", "")).strip()
        if not claim_val:
            reasons.append("bad claim")
        kind_val = f.get("kind")
        if kind_val is not None:
            if not isinstance(kind_val, str) or kind_val.strip().lower() not in VALID_KINDS:
                reasons.append("bad kind")
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
    """canonical 目标归一 (RV-02 / R07): 保留完整相对路径段, 防止不同真实文件碰撞。
    - 路径写法: 去行号, 统一斜杠与小写, 剥除任意驱动器盘符与前导斜杠;
    - 复合描述 (文件名+函数+行号, 无路径前缀): 提取文件名 token;
    - 裸文件名与带路径写法不强行等价 (宁拆不并)。
    """
    if not target_str:
        return "general"
    s = str(target_str).strip()
    s = re.sub(r":\d+(?:-\d+)?$", "", s)
    s = s.replace("\\", "/").lower()
    s = s.strip("/")
    parts = [p for p in s.split("/") if p and not re.match(r"^[a-z]:$", p)]
    if not parts:
        return "general"
    joined = "/".join(parts)
    if "/" in joined:
        return joined
    m = _FILE_TOKEN_RE.search(joined)
    if m and m.group(0) == joined:
        return joined
    if m:
        return m.group(0)
    return joined


def _issue_identity(item):
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


def _has_claim_text_opposition(texts):
    """检测多模型主张文本是否存在明确的立场相反 (如 exists vs absent/missing)。"""
    opp_pairs = [
        ({"exists", "is present", "present"}, {"absent", "is absent", "missing", "is missing"}),
        ({"valid", "is valid", "validates"}, {"invalid", "is invalid"}),
        ({"supported", "is supported"}, {"unsupported", "not supported"}),
        ({"pass", "passes"}, {"fail", "fails"}),
    ]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            t1 = texts[i].lower()
            t2 = texts[j].lower()
            for pos_set, neg_set in opp_pairs:
                t1_pos = any(w in t1 for w in pos_set)
                t1_neg = any(w in t1 for w in neg_set)
                t2_pos = any(w in t2 for w in pos_set)
                t2_neg = any(w in t2 for w in neg_set)
                if (t1_pos and t2_neg and not t1_neg and not t2_pos) or (t1_neg and t2_pos and not t1_pos and not t2_neg):
                    return True
    return False


def _has_contradiction_or_unaligned(items):
    """R09: 判定多模型议题是否存在立场分歧或需要对立质询。
    1. 显式互斥 polarity (如 present vs absent) -> True;
    2. 缺失 polarity 时, 检查 claims 词义是否存在明确相反对立 (R09);
    3. 否则同 issue_key 视为指向同一议题并尝试聚合为 consensus。
    """
    if _has_polarity_contradiction(items):
        return True
    claim_texts = [str(x["raw"].get("claim", "")) for x in items]
    if _has_claim_text_opposition(claim_texts):
        return True
    return False


def cluster_issues(models, findings_by_model):
    """断言级聚类:
    - 身份 = (canonical_target, assertion_key), 显式 issue_key 优先, 无则 claim 哈希兜底;
    - claims 完整保留并携带 provenance (RV-08);
    - 矛盾由互斥 polarity 或未对齐主张判定 (R09); 仅严格同向才归入 consensus。
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
                   "severity": x["raw"].get("severity", "P2"),
                   "provenance": x["raw"].get("provenance", "unknown")} for x in items]
        entry = {
            "issue_id": f"I{issue_counter:02d}",
            "target": tgt,
            "assertion_key": key,
            "raised_by": raised,
            "severity": severity,
            "claims": claims,
            "provenance": "synthetic_fallback" if all(
                cl["provenance"] == "synthetic_fallback" for cl in claims) else "model_written",
            "state": "singleton" if len(raised) == 1 else
                     ("contradiction" if _has_contradiction_or_unaligned(items) else "consensus"),
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
    """Phase 1: 独立盲审与生成 (新 run: 清理全部旧产物 + 重算 manifest 身份 + 退出码判定)。"""
    _clean_stale_plan_outputs(stream, model_keys, task_path=task_path)
    manifest = _write_manifest(stream, task_path, model_keys, "plan")
    run_id = manifest["run_id"]
    started_at = manifest["started_at"]

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
    missing = [k for k, p in zip(model_keys, out_paths) if not results[p]["file"]]
    bad_exit = {k: results[p]["exit"] for k, p in zip(model_keys, out_paths)
                if results[p]["exit"] not in (0, None)}
    if missing:
        print(f"[plan-v2] 警告: 无产出模型: {', '.join(missing)}", file=sys.stderr)
    if bad_exit:
        print(f"[plan-v2] 警告: 非零退出: {bad_exit}", file=sys.stderr)
    failed_models = sorted(list(set(missing) | set(bad_exit.keys())))
    _write_manifest(stream, task_path, model_keys, "plan", missing_models=failed_models,
                    run_id=run_id, started_at=started_at)

    for k in model_keys:
        if k in bad_exit:
            continue
        extract_findings_json(stream, k)

    ok = any(r["file"] and r["exit"] in (0, None) for r in results.values())
    print(f"[plan-v2] {'完成' if ok else '全部失败'} "
          f"{json.dumps({os.path.basename(p): v['file'] for p, v in results.items()}, ensure_ascii=False)}")
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
        candidates = [m for m in model_keys if m not in set(excluded_models)]
        if not candidates:
            return None
        anchor = next((m for m in excluded_models if m in model_keys), candidates[0])
        return max(candidates, key=lambda cand: weights.get((cand, anchor), 0.0))

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
                    # RV-09: bundle 内不得携带模型短名 (内部调度 target 留在条目层)
                    "title": "针对匿名方案的互补性审查",
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
    """Phase 3: 定向匿名质询执行 (清理陈旧答复 + 退出码/文件分开判定)。"""
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
        r = results[p]
        if not r["file"]:
            print(f"[challenge-v2] 警告: 质询 {item['challenge_id']} ({item['reviewer']}) 无答复", file=sys.stderr)
        elif r["exit"] not in (0, None):
            print(f"[challenge-v2] 警告: 质询 {item['challenge_id']} 非零退出 {r['exit']}", file=sys.stderr)

    ok = any(r["file"] for r in results.values())
    print(f"[challenge-v2] {'完成' if ok else '全部失败'} "
          f"{json.dumps({os.path.basename(p): v['file'] for p, v in results.items()}, ensure_ascii=False)}")
    return ok


def _parse_stances(text):
    """RV-07 / R05: 逐行解析, 三类标记独立收集 (同行混合裁决不丢失);
    引用块 (以 > 开头) 中的标签不参与裁决;
    Markdown 表格行正常解析裁决, 仅跳过纯表头/分隔线。
    """
    conceded, refuted, unresolved = [], [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(">"):
            continue
        if re.match(r"^\|[\s\-:|]+\|$", s):
            continue
        if re.search(r"【\s*CONCEDE\s*】", s):
            conceded.append(s[:200])
        if re.search(r"【\s*REFUTED\s*】", s):
            refuted.append(s[:200])
        if re.search(r"【\s*UNRESOLVED", s):
            unresolved.append(s[:200])
    return conceded, refuted, unresolved


def _strip_line_no(s):
    return re.sub(r":\d+(?:-\d+)?$", "", str(s).strip())


def _evidence_check(evidence_list, base_dirs):
    """证据三分 (RV-03/RV-04):
    - verified: 绝对路径 (先剥行号) 真实存在, 或相对路径在 base 目录命中;
    - missing: 绝对路径剥行号后不存在 (幽灵证据);
    - unverified: 相对路径未命中, 或非文件样式的断言文本 (不冒充已验证)。
    """
    verified, missing, unverified = [], [], []
    for e in (evidence_list or []):
        e = str(e).strip()
        loc = _strip_line_no(e)
        if _ABS_PATH_RE.match(e):
            if os.path.exists(loc):
                verified.append(e)
            else:
                missing.append(e)
            continue
        if _EXT_RE.search(loc):
            if any(os.path.exists(os.path.join(b, loc)) for b in base_dirs):
                verified.append(e)
            else:
                unverified.append(e)
        else:
            unverified.append(e)
    return verified, missing, unverified


def stage_synthesize_v2(stream):
    """Phase 4: 对账、逐断言表态、少数派证据保护 (REFUTED 语义 RV-05 + 收敛状态 RV-06)。"""
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

    skip_path = os.path.join(stream, "challenge-skipped.json")
    skipped_planned = []
    if os.path.exists(skip_path):
        with open(skip_path, "r", encoding="utf-8") as f:
            skipped_planned = json.load(f)

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
    refuted_claims_by_issue = {}
    for cid, reply in replies_by_cid.items():
        conceded, refuted, unresolved = _parse_stances(reply["text"])
        for excerpt in conceded:
            conceded_items.append({"source_file": f"challenge-reply-{cid}-{reply['reviewer']}.md",
                                   "status": "conceded", "excerpt": excerpt})
        for excerpt in refuted:
            refuted_items.append({"source_file": f"challenge-reply-{cid}-{reply['reviewer']}.md",
                                  "status": "refuted", "excerpt": excerpt})
            if reply.get("issue_id") and reply.get("type") == "singleton_audit":
                m_prop = re.search(r"Proposal\s*(\d+)", excerpt, re.I)
                prop_key = m_prop.group(0).lower().replace(" ", "") if m_prop else "all"
                refuted_claims_by_issue.setdefault(reply["issue_id"], set()).add(prop_key)
        for excerpt in unresolved:
            unresolved_contested.append({"source_file": f"challenge-reply-{cid}-{reply['reviewer']}.md",
                                         "status": "unresolved_contested", "excerpt": excerpt})

    unresolved_ledger = list(unresolved_contested)
    ghost_discarded = []
    unverified_evidence = []
    for s in registry.get("singletons", []):
        iid = s.get("issue_id")
        refuted_props = refuted_claims_by_issue.get(iid, set())
        claims = s.get("claims", [])
        if "all" in refuted_props and len(claims) <= 1:
            continue
        if len(claims) > 1 and "all" not in refuted_props:
            remaining_claims = []
            for idx, cl in enumerate(claims, 1):
                prop_name = f"proposal{idx}"
                if prop_name not in refuted_props:
                    remaining_claims.append(cl)
            if not remaining_claims:
                continue
            s = dict(s)
            s["claims"] = remaining_claims
        elif "all" in refuted_props and len(claims) > 1:
            continue
        sev = s.get("severity")
        if sev not in ("P0", "P1"):
            continue
        all_evidence = []
        for cl in s.get("claims", []):
            all_evidence.extend(cl.get("evidence") or [])
        if not all_evidence:
            continue
        verified, missing, unverified = _evidence_check(all_evidence, base_dirs)
        if not verified and missing and not unverified:
            ghost_discarded.append({"issue_id": s["issue_id"], "target": s["target"],
                                    "ghost_evidence": missing})
            continue
        if unverified:
            unverified_evidence.append({"issue_id": s["issue_id"], "target": s["target"],
                                        "unverified_evidence": unverified})
        if missing:
            unverified_evidence.append({"issue_id": s["issue_id"], "target": s["target"],
                                        "unverified_evidence": [f"missing: {m}" for m in missing]})
        unresolved_ledger.append({
            "issue_id": s["issue_id"],
            "target": s["target"],
            "assertion_key": s.get("assertion_key"),
            "raised_by": s["raised_by"],
            "claims": s["claims"],
            "severity": sev,
            "provenance": s.get("provenance", "unknown"),
            "evidence_verified": verified,
            "evidence_unverified": unverified,
            "evidence_missing": missing,
            "reason": "少数派附证据独立发现 (Minority preservation: unrefuted finding with concrete locators)",
        })

    ledger_path = os.path.join(stream, "unresolved-ledger.json")
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(unresolved_ledger, f, ensure_ascii=False, indent=2)

    manifest = _read_manifest(stream) or {}
    contradictions = registry.get("contradictions", [])
    consensus = registry.get("consensus", [])
    missing_models = registry.get("metadata", {}).get("missing_models", [])

    # RV-06 / R03: 收敛状态——只有全部收敛且未决账本清空才写闭环
    uncontested_contradictions = [c for c in contradictions
                                  if not any(r.get("issue_id") == c["issue_id"]
                                             for r in replies_by_cid.values())]
    unconverged = []
    if missing_challenges:
        unconverged.append(f"质询缺失 {len(missing_challenges)} 组")
    if skipped_planned:
        unconverged.append(f"因无匿名候选跳过质询 {len(skipped_planned)} 组")
    if uncontested_contradictions:
        unconverged.append(f"对立断言未获质询答复 {len(uncontested_contradictions)} 项")
    if unverified_evidence:
        unconverged.append(f"证据未验证 {len(unverified_evidence)} 项")
    if missing_models:
        unconverged.append(f"模型缺失 {', '.join(missing_models)}")
    if ghost_discarded:
        unconverged.append(f"幽灵证据丢弃 {len(ghost_discarded)} 项")
    if unresolved_contested:
        unconverged.append(f"质询存在未决争议 {len(unresolved_contested)} 项")
    if unresolved_ledger:
        unconverged.append(f"保护账本存在未决议题 {len(unresolved_ledger)} 项")
    converged = not unconverged

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
        f.write(f"- 收敛状态: {'已闭环' if converged else '未收敛 (' + '; '.join(unconverged) + ')'}\n\n")

        f.write("## 一、多模型互证发现 (Corroborated Model Findings)\n\n")
        f.write("（注意: 模型共识不是证据, 本表只表示多个模型指向同一断言身份, 出处谱系才是证据。）\n\n")
        if not consensus:
            f.write("（无多模型一致项）\n\n")
        for it in consensus:
            f.write(f"### [{it['issue_id']}] `{it['target']}` ({it['severity']}) [provenance={it.get('provenance', 'unknown')}]\n")
            f.write(f"- 提出方: {', '.join(it['raised_by'])}\n")
            all_ev = []
            for cl in it.get("claims", []):
                f.write(f"  - {cl['model']}: {cl['claim']}\n")
                all_ev.extend(cl.get("evidence") or [])
            if not all_ev:
                f.write("- 证据状态: 无证据 (不得视为已验证)\n\n")
                continue
            verified, missing, unverified = _evidence_check(all_ev, base_dirs)
            tag_parts = []
            if verified:
                tag_parts.append(f"已验证 {len(verified)} 条")
            if unverified:
                tag_parts.append(f"未验证 {len(unverified)} 条")
            if missing:
                tag_parts.append(f"缺失 {len(missing)} 条")
            f.write(f"- 证据状态: {'; '.join(tag_parts)}\n\n")

        f.write("## 二、断言级对立与质询 (Contradictions & Cross-Examination)\n\n")
        if not contradictions and not missing_challenges and not skipped_planned:
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
        if skipped_planned:
            f.write("### 因无匿名候选跳过的质询 (SKIPPED)\n\n")
            for m in skipped_planned:
                f.write(f"- issue {m.get('issue_id', '?')} target `{m.get('target', '?')}`: {m.get('reason', '')}\n")
            f.write("\n")
        if missing_challenges:
            f.write("### 质询缺失清单 (MISSING)\n\n")
            for m in missing_challenges:
                f.write(f"- 质询 {m['challenge_id']} (issue {m.get('issue_id', '?')}, reviewer {m['reviewer']}, target `{m.get('target', '?')}`) 无答复文件\n")
            f.write("\n")

        f.write("## 三、未决项与少数派保护账本 (Unresolved Ledger)\n\n")
        if not unresolved_ledger:
            if converged:
                f.write("（所有分歧均已收敛达成闭环）\n\n")
            else:
                f.write("（账本为空, 但存在未收敛项, 见头部收敛状态与上述章节）\n\n")
        for u in unresolved_ledger:
            f.write(f"### `{u.get('target', 'General')}` [{u.get('severity', 'P1')}] [provenance={u.get('provenance', 'unknown')}]\n")
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
            if u.get("evidence_missing"):
                f.write(f"- 证据(缺失/幽灵): `{', '.join(u['evidence_missing'])}`\n")
            f.write(f"- 说明: {u.get('reason', '经质询仍存分歧，需真实测试验证')}\n\n")
        if ghost_discarded:
            f.write("## 四、幽灵证据丢弃记录 (Ghost Evidence Discarded)\n\n")
            for g in ghost_discarded:
                f.write(f"- [{g['issue_id']}] `{g['target']}`: 证据路径不存在, 已拒绝入账: {', '.join(g['ghost_evidence'])}\n")
            f.write("\n")

    print(f"[synthesize-v2] 合议报告已生成, 未决账本: {len(unresolved_ledger)} 项, "
          f"质询缺失: {len(missing_challenges)} 项, 收敛: {'是' if converged else '否'}")
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
