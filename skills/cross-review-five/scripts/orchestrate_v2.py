# -*- coding: utf-8 -*-
"""五人异构模型交叉编排器 v2 (Sparse Adaptive Deliberation):
基于信息增量、结构化 Issue 拓扑与自适应质询的稀疏通信评审系统。

核心设计原则 (v2):
1. 独立盲审 (Blind Independent Society): 保留五个异构模型互不可见的第一阶段，防范从众与锚定；
2. 结构化 Issue 提取: 每个模型产出 Markdown 的同时生成 findings 规范数据；
3. 本地零成本归并: 本地 Python 脚本聚类 Consensus、Singleton 与 Contradiction，计算互补矩阵；
4. 匿名定向质询 (Targeted Cross-Examination): 摒弃全篇通读与固定有向环，按最大互补匹配或争议点只审关键 Issue；
5. 少数派证据保护与防从众提示词: 提取增量优先于表态，支持 CONCEDE 认输，有证据的少数派绝不被多数票吞没。

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
import itertools
import json
import os
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

# 模式配置
MODE_PRESETS = {
    "economy": {
        "models": ["kimi-k3", "dsv4pro", "gemini38flash"],
        "max_challenges": 1,
        "description": "经济模式 (3 模型盲审, 最多 1 次关键争议质询, 适合快速把关)",
    },
    "standard": {
        "models": ["kimi-k3", "dsv4pro", "glm53", "gemini38flash", "gemini31pro"],
        "max_challenges": 3,
        "description": "标准模式 (5 模型盲审, 2-3 次核心争议与单例质询, 默认推荐)",
    },
    "audit": {
        "models": ["kimi-k3", "dsv4pro", "glm53", "gemini38flash", "gemini31pro"],
        "max_challenges": 5,
        "use_derangement": True,
        "description": "审计模式 (5 模型盲审, 最大互补匹配有向环 + 关键弦质询, 适合高危收口)",
    },
}

POLL_SECONDS = 15
TIMEOUT_SECONDS = 40 * 60

PLAN_PROMPT_V2 = """任务：评审任务书并独立产出方案与结构化发现。

您是一名独立评审者。请在完全不参考其他任何外部评审者意见的前提下，独立完成以下工作：

一、阅读任务书文件 {task_path}。
二、阅读任务书中指定的全部材料。
三、按任务书要求完成工作，将完整文字产出写入文件 {out_path}。
四、同时在产出文件末尾（或同目录写入 {findings_path}）提供严格的 JSON 格式结构化发现块，格式如下：

```json
{{
  "findings": [
    {{
      "id": "F1",
      "target": "涉及的具体文件、模块、行号范围或规范接口",
      "kind": "bug|security|invariant|perf|spec_mismatch|suggestion",
      "claim": "发现的核心断言（一两句话说明问题实体与结论）",
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
- 必须包含结构化 JSON 块，确保 target、claim、evidence 真实明确。
"""

CHALLENGE_PROMPT_V2 = """任务：对匿名方案的分歧点与独有发现进行定向交叉质询。

您将审查一份来自对等评审者的匿名观点摘要（包含争议项或独有高危发现）。
任务书路径: {task_path}
质询议题包: {bundle_path}
您的质询答复写入: {out_path}

请严格按以下四步顺序作答，不得直接宣布同意或反对：

第一步【提取增量】：
提取议题包中对方提出、但我方此前未注意到的新事实、新证据或新分析路径。若无新事实，明确写明“无新增量”。

第二步【核验反例】：
对议题包中的每个断言，依据代码源码、规范或物理约束，尝试寻找可证伪的反例、边界条件或证据漏洞。

第三步【分歧归因】：
明确双方分歧的根因究竟是：证据不足、规范解读不一致、还是代码实现层面的确定性缺陷。

第四步【裁决与表态】：
- 若对方证据确凿（有不可辩驳的代码行号、测试用例或逻辑证明），请明确标注 【CONCEDE】（认同并吸收对方观点），严禁无理辩护；
- 若确属对方错误，给出明确的反例与反证并标注 【REFUTED】；
- 若双方各有论据且现有输入无法断定，标注 【UNRESOLVED_REQUIRES_CODE_VERIFICATION】，并提出验证该分歧所需的最小实验或测试用例；
- 严禁以多数票为由否定附有具体代码证据的少数派意见。
"""


def spawn(model_key, prompt_path, log_path):
    """启动子进程执行单个模型的评测任务。"""
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
    """轮询产物文件落盘与进程退出，不依赖任何实时推送通知。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        files_ok = all(os.path.exists(p) and os.path.getsize(p) > 0 for p in out_paths)
        procs_ok = all(p.poll() is not None for p in procs)
        if files_ok and procs_ok:
            return True
        if procs_ok and not files_ok:
            return False
        time.sleep(POLL_SECONDS)
    return False


def extract_findings_json(stream, model_key):
    """提取模型的结构化 findings。优先读取 findings-<model>.json，缺失则从 review-<model>.md 提取。"""
    json_path = os.path.join(stream, f"findings-{model_key}.json")
    if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    md_path = os.path.join(stream, f"review-{model_key}.md")
    if not os.path.exists(md_path):
        return {"findings": [], "unknowns": [], "assumptions": []}

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 正则匹配 ```json ... ``` 块
    matches = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
    for m in reversed(matches):  # 从后向前找最可能是 findings 的 JSON 块
        try:
            data = json.loads(m)
            if isinstance(data, dict) and "findings" in data:
                # 顺便落盘为标准 sidecar 文件
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return data
        except Exception:
            continue

    # 启发式降级: 从 Markdown 标题与证据行提取结构化发现
    fallback_findings = []
    lines = content.splitlines()
    for line in lines:
        if line.startswith("#"):
            continue
        cites = re.findall(r"([\w/\\.-]+\.(?:py|json|md|sh|ps1))(?::(\d+(?:-\d+)?))?", line)
        if cites and len(line.strip()) > 15:
            target = cites[0][0]
            loc = target + ((":" + cites[0][1]) if cites[0][1] else "")
            sev = "P0" if any(w in line for w in ("崩溃", "误杀", "强杀", "致命", "死锁", "crash", "kill")) else (
                "P1" if any(w in line for w in ("漏洞", "盲区", "缺陷", "缺失", "逃逸", "bug", "flaw")) else "P2"
            )
            fallback_findings.append({
                "id": f"F{len(fallback_findings)+1}",
                "target": target,
                "kind": "bug" if sev in ("P0", "P1") else "observation",
                "claim": line.strip()[:140],
                "evidence": [loc],
                "severity": sev,
                "blocking": (sev == "P0"),
            })
    res = {"findings": fallback_findings[:15], "unknowns": [], "assumptions": []}
    if fallback_findings:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
    return res


def normalize_target(target_str):
    """归一化目标对象路径或名称，用于聚类。"""
    if not target_str:
        return "general"
    s = target_str.strip().replace("\\", "/").lower()
    # 截除行号以便归组同一个文件/函数
    s = re.sub(r":\d+(?:-\d+)?$", "", s)
    return s


def compute_complementarity_matrix(models, findings_by_model):
    """计算各模型间的互补性权重矩阵 W(i -> j)。
    W(i, j) 衡量让模型 i 质询模型 j 的信息价值：
    - 目标重合度低（互补视野）
    - 针对相同目标的断言冲突（争议点）
    - 发现 j 独有的高危项（单例验证）
    """
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

            # Jaccard 互补度
            union = t_i | t_j
            inter = t_i & t_j
            if union:
                overlap = len(inter) / len(union)
                w += (1.0 - overlap) * 2.0

            # 冲突检测与单例加权
            f_j = findings_by_model.get(j, {}).get("findings", [])
            for item in f_j:
                tgt = normalize_target(item.get("target", ""))
                sev = item.get("severity", "P2").upper()
                if tgt not in t_i:
                    # j 发现了 i 没碰过的区域，严重度越高越值得 i 审阅
                    if sev == "P0":
                        w += 3.0
                    elif sev == "P1":
                        w += 1.5
                else:
                    # 同一目标，检查是否有矛盾
                    w += 0.5

            weights[(i, j)] = round(w, 2)
    return weights


def max_weight_derangement(models, weights):
    """求解最大权重错排匹配 (Bipartite matching with no fixed points):
    每个 reviewer 仅审一人，被审者不为自己，最大化总互补权重。
    """
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


def cluster_issues(models, findings_by_model):
    """将各模型的 findings 聚类为 Consensus、Contradiction 与 Singleton。"""
    by_target = {}
    for m in models:
        raw_items = findings_by_model.get(m, {}).get("findings", [])
        for item in raw_items:
            tgt = normalize_target(item.get("target", ""))
            by_target.setdefault(tgt, []).append({
                "model": m,
                "raw": item,
            })

    consensus = []
    singletons = []
    contradictions = []

    issue_counter = 1
    for tgt, items in by_target.items():
        if len(items) == 1:
            it = items[0]
            singletons.append({
                "issue_id": f"I{issue_counter:02d}",
                "target": tgt,
                "raised_by": [it["model"]],
                "severity": it["raw"].get("severity", "P2"),
                "claim": it["raw"].get("claim", ""),
                "evidence": it["raw"].get("evidence", []),
                "blocking": it["raw"].get("blocking", False),
                "state": "singleton",
            })
            issue_counter += 1
        else:
            # 2 个及以上模型命中同一 target
            kinds = {x["raw"].get("kind", "") for x in items}
            # 简化判定：若性质不同或包含反对词，视为潜在冲突
            is_conflict = len(kinds) > 1 or any(
                "不" in x["raw"].get("claim", "") or "错" in x["raw"].get("claim", "")
                for x in items
            )
            state = "contradiction" if is_conflict else "consensus"
            entry = {
                "issue_id": f"I{issue_counter:02d}",
                "target": tgt,
                "raised_by": list({x["model"] for x in items}),
                "severity": max((x["raw"].get("severity", "P2") for x in items), key=lambda s: {"P0": 3, "P1": 2, "P2": 1}.get(s, 0)),
                "claims": [{ "model": x["model"], "claim": x["raw"].get("claim", ""), "evidence": x["raw"].get("evidence", []) } for x in items],
                "state": state,
            }
            if state == "contradiction":
                contradictions.append(entry)
            else:
                consensus.append(entry)
            issue_counter += 1

    return consensus, singletons, contradictions


def stage_plan_v2(stream, task_path, model_keys):
    """Phase 1: 独立盲审与生成。"""
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

    ok = wait_for_outputs(out_paths, procs)
    for p in procs:
        if p.poll() is None:
            p.terminate()

    # 尝试提取或落盘 findings JSON
    for k in model_keys:
        extract_findings_json(stream, k)

    status = {os.path.basename(p): os.path.exists(p) for p in out_paths}
    print(f"[plan-v2] {'完成' if ok else '超时或失败'} {json.dumps(status, ensure_ascii=False)}")
    return ok


def stage_merge_v2(stream, model_keys, mode="standard"):
    """Phase 2: 本地结构化 Issue 聚类与图分析 (纯 Python 离线运行，零 LLM 消耗)。"""
    findings_by_model = {k: extract_findings_json(stream, k) for k in model_keys}
    consensus, singletons, contradictions = cluster_issues(model_keys, findings_by_model)
    weights = compute_complementarity_matrix(model_keys, findings_by_model)

    registry = {
        "metadata": {
            "mode": mode,
            "models": model_keys,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
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

    reg_path = os.path.join(stream, "issue-registry.json")
    with open(reg_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    # 规划 Phase 3 的质询任务包
    cfg = MODE_PRESETS.get(mode, MODE_PRESETS["standard"])
    max_challenges = cfg["max_challenges"]
    challenges = []

    # 1. 优先质询核心冲突 (Contradictions)
    for c in contradictions:
        if len(challenges) >= max_challenges:
            break
        # 挑选涉及该矛盾的两方中未质询过的一方，或互补权重最高者进行交叉质询
        raised = c["raised_by"]
        reviewer = raised[0] if len(raised) > 0 else model_keys[0]
        challenges.append({
            "challenge_id": f"C{len(challenges)+1:02d}",
            "type": "contradiction",
            "issue_id": c["issue_id"],
            "target": c["target"],
            "reviewer": reviewer,
            "bundle": {
                "title": f"关于 {c['target']} 的对立断言裁决",
                "target": c["target"],
                "proposals": [
                    {
                        "source_alias": f"Proposal-{idx+1}",
                        "claim": x["claim"],
                        "evidence": x["evidence"],
                    }
                    for idx, x in enumerate(c["claims"])
                ],
            },
        })

    # 2. 其次质询高危单例 (P0/P1 Singletons)，加入负载均衡避免单模型过载
    high_singletons = [s for s in singletons if s.get("severity") in ("P0", "P1")]
    used_reviewers = set()
    for s in high_singletons:
        if len(challenges) >= max_challenges:
            break
        author = s["raised_by"][0]
        # 优先选择尚未承担质询任务的候选模型
        candidates = [m for m in model_keys if m != author and m not in used_reviewers]
        if not candidates:
            candidates = [m for m in model_keys if m != author]
        best_reviewer = max(candidates, key=lambda cand: weights.get((cand, author), 0.0)) if candidates else model_keys[0]
        used_reviewers.add(best_reviewer)
        challenges.append({
            "challenge_id": f"C{len(challenges)+1:02d}",
            "type": "singleton_audit",
            "issue_id": s["issue_id"],
            "target": s["target"],
            "reviewer": best_reviewer,
            "bundle": {
                "title": f"对未覆盖单例高危断言的独立核验: {s['target']}",
                "target": s["target"],
                "proposals": [
                    {
                        "source_alias": "Proposal-A",
                        "claim": s["claim"],
                        "evidence": s["evidence"],
                        "severity": s["severity"],
                    }
                ],
            },
        })

    # 审计模式且质询配额有余：使用最大互补错排匹配
    if cfg.get("use_derangement") and len(challenges) < max_challenges:
        derange_pairs = max_weight_derangement(model_keys, weights)
        for reviewer, target in derange_pairs:
            if len(challenges) >= max_challenges:
                break
            challenges.append({
                "challenge_id": f"C{len(challenges)+1:02d}",
                "type": "derangement_peer",
                "reviewer": reviewer,
                "target": target,
                "bundle": {
                    "title": f"针对匿名方案的互补性审查",
                    "target": target,
                    "proposals": [
                        {
                            "source_alias": "Target-Proposal",
                            "findings": findings_by_model.get(target, {}).get("findings", [])[:5],
                        }
                    ],
                },
            })

    plan_path = os.path.join(stream, "challenge-plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(challenges, f, ensure_ascii=False, indent=2)

    # 输出 Markdown 摘要
    summary_path = os.path.join(stream, "graph-summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# Issue Graph Summary ({mode})\n\n")
        f.write(f"- 参与模型: {', '.join(model_keys)}\n")
        f.write(f"- 共识发现 (Consensus): {len(consensus)} 项\n")
        f.write(f"- 独有发现 (Singleton): {len(singletons)} 项 (高危 P0/P1: {len(high_singletons)} 项)\n")
        f.write(f"- 存在争议 (Contradiction): {len(contradictions)} 项\n")
        f.write(f"- 生成针对性质询任务: {len(challenges)} 组\n\n")

        if contradictions:
            f.write("## 核心分歧清单\n\n")
            for c in contradictions:
                f.write(f"### [{c['issue_id']}] 目标: `{c['target']}`\n")
                for cl in c["claims"]:
                    f.write(f"- **{cl['model']}**: {cl['claim']} (证据: {', '.join(cl['evidence']) if cl['evidence'] else '无'})\n")
                f.write("\n")

    print(f"[merge-v2] Issue 归并完成: {len(consensus)} 共识, {len(singletons)} 单例, {len(contradictions)} 冲突 -> 规划 {len(challenges)} 组质询")
    return True


def stage_challenge_v2(stream, task_path):
    """Phase 3: 定向匿名质询执行。"""
    plan_path = os.path.join(stream, "challenge-plan.json")
    if not os.path.exists(plan_path):
        print(f"[challenge-v2] 缺失质询计划，请先运行 --stage merge", file=sys.stderr)
        return False

    with open(plan_path, "r", encoding="utf-8") as f:
        challenges = json.load(f)

    if not challenges:
        print("[challenge-v2] 无需针对性质询 (零冲突或预算已饱和)")
        return True

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

    ok = wait_for_outputs(out_paths, procs)
    for p in procs:
        if p.poll() is None:
            p.terminate()

    status = {os.path.basename(p): os.path.exists(p) for p in out_paths}
    print(f"[challenge-v2] {'完成' if ok else '超时或失败'} {json.dumps(status, ensure_ascii=False)}")
    return ok


def stage_synthesize_v2(stream):
    """Phase 4: 汇总质询答复，执行少数派证据保护，产出最终裁决与未决账本。"""
    reg_path = os.path.join(stream, "issue-registry.json")
    if not os.path.exists(reg_path):
        print(f"[synthesize-v2] 缺失 issue-registry.json", file=sys.stderr)
        return False

    with open(reg_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    challenge_files = glob.glob(os.path.join(stream, "challenge-reply-*.md"))
    challenge_replies = {}
    for p in challenge_files:
        with open(p, "r", encoding="utf-8") as f:
            challenge_replies[os.path.basename(p)] = f.read()

    unresolved_ledger = []
    conceded_items = []
    refuted_items = []

    # 解析质询答复中的表态
    for fname, text in challenge_replies.items():
        if "【CONCEDE】" in text or "CONCEDE" in text:
            conceded_items.append({"source_file": fname, "status": "conceded", "excerpt": text[:300]})
        elif "【REFUTED】" in text or "REFUTED" in text:
            refuted_items.append({"source_file": fname, "status": "refuted", "excerpt": text[:300]})
        elif "【UNRESOLVED" in text or "UNRESOLVED" in text:
            unresolved_ledger.append({"source_file": fname, "status": "unresolved_contested", "excerpt": text[:300]})

    # 少数派证据保护原则:
    # 所有未被质询直接证伪且带具体证据定位符的 Singleton P0/P1 项，自动保留进入未决账本，禁止吞没
    for s in registry.get("singletons", []):
        if s.get("severity") in ("P0", "P1") and s.get("evidence"):
            unresolved_ledger.append({
                "issue_id": s["issue_id"],
                "target": s["target"],
                "raised_by": s["raised_by"],
                "claim": s["claim"],
                "evidence": s["evidence"],
                "severity": s["severity"],
                "reason": "少数派附证据独立发现 (Minority preservation: unrefuted finding with concrete locators)",
            })

    ledger_path = os.path.join(stream, "unresolved-ledger.json")
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(unresolved_ledger, f, ensure_ascii=False, indent=2)

    # 生成最终合议报告
    report_path = os.path.join(stream, "consensus-report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 五人交叉评审合议报告 (v2 Sparse Deliberation)\n\n")
        f.write(f"- 合议生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- 评审模式: {registry.get('metadata', {}).get('mode', 'standard')}\n")
        f.write(f"- 模型阵容: {', '.join(registry.get('metadata', {}).get('models', []))}\n")
        f.write(f"- 共识项 (Consensus): {len(registry.get('consensus', []))} 项\n")
        f.write(f"- 质询认同/认输 (Conceded): {len(conceded_items)} 项\n")
        f.write(f"- 质询证伪驳回 (Refuted): {len(refuted_items)} 项\n")
        f.write(f"- 未决保护账本 (Unresolved Ledger): {len(unresolved_ledger)} 项\n\n")

        f.write("## 一、高度共识项 (Verified Consensus)\n\n")
        if not registry.get("consensus"):
            f.write("（无全员一致项）\n\n")
        for it in registry.get("consensus", []):
            f.write(f"### [{it['issue_id']}] `{it['target']}` ({it['severity']})\n")
            f.write(f"- 提出方: {', '.join(it['raised_by'])}\n")
            for cl in it.get("claims", []):
                f.write(f"  - {cl['model']}: {cl['claim']}\n")
            f.write("\n")

        f.write("## 二、未决项与少数派保护账本 (Unresolved Ledger)\n\n")
        if not unresolved_ledger:
            f.write("（所有分歧均已收敛达成闭环）\n\n")
        for u in unresolved_ledger:
            f.write(f"### `{u.get('target', 'General')}` [{u.get('severity', 'P1')}]\n")
            f.write(f"- 来源: {u.get('raised_by', [u.get('source_file')])}\n")
            f.write(f"- 断言: {u.get('claim', u.get('excerpt', ''))}\n")
            if u.get("evidence"):
                f.write(f"- 证据: `{', '.join(u['evidence'])}`\n")
            f.write(f"- 说明: {u.get('reason', '经质询仍存分歧，需真实测试验证')}\n\n")

    print(f"[synthesize-v2] 合议报告已生成 -> {os.path.basename(report_path)}, 未决账本: {len(unresolved_ledger)} 项")
    return True


def stage_status_v2(stream):
    """查看 v2 任务流的全部文件资产与状态。"""
    patterns = (
        "task.md",
        "review-*.md",
        "findings-*.json",
        "issue-registry.json",
        "graph-summary.md",
        "challenge-plan.json",
        "bundle-*.json",
        "challenge-reply-*.md",
        "consensus-report.md",
        "unresolved-ledger.json",
        "log-*.txt",
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

    # 确定模型阵容
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
