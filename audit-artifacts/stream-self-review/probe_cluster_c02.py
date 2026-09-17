# -*- coding: utf-8 -*-
"""探针:核验 cluster_issues 对单模型多 findings 同 target 的聚类行为。"""
import sys
sys.path.insert(0, r"<WORKSPACE>\repos\hermes-academic-skills\skills\cross-review-five\scripts")
from orchestrate_v2 import cluster_issues

models = ["m1", "m2"]
# 探针1: 单模型对同一 target 两条 findings,kind 相同,claim 无冲突词
fbm = {
    "m1": {"findings": [
        {"target": "a.py", "claim": "x 很安全", "kind": "bug", "severity": "P2", "evidence": []},
        {"target": "a.py", "claim": "x 很安全", "kind": "bug", "severity": "P2", "evidence": []},
    ]},
    "m2": {"findings": []},
}
c, s, d = cluster_issues(models, fbm)
print("probe1 consensus:", [(x["target"], x["raised_by"], x["state"]) for x in c])
print("probe1 contradictions:", [(x["target"], x["raised_by"], x["state"]) for x in d])
print("probe1 singletons:", [(x["target"], x["raised_by"], x["state"]) for x in s])

# 探针2: 单模型双 findings,kind 不同 -> 是否误标 contradiction
fbm2 = {
    "m1": {"findings": [
        {"target": "b.py", "claim": "y 安全", "kind": "bug", "severity": "P2", "evidence": []},
        {"target": "b.py", "claim": "y 安全", "kind": "observation", "severity": "P2", "evidence": []},
    ]},
}
c2, s2, d2 = cluster_issues(["m1"], fbm2)
print("probe2 contradictions:", [(x["target"], x["raised_by"], x["state"]) for x in d2])

# 探针3: claim 含"不"字的单模型双 findings -> contradiction
fbm3 = {
    "m1": {"findings": [
        {"target": "c.py", "claim": "没有问题的代码", "kind": "bug", "severity": "P2", "evidence": []},
        {"target": "c.py", "claim": "同一模型第二条", "kind": "bug", "severity": "P2", "evidence": []},
    ]},
}
c3, s3, d3 = cluster_issues(["m1"], fbm3)
print("probe3 contradictions:", [(x["target"], x["raised_by"], x["state"]) for x in d3])

# 探针4: 真双模型同 target -> 对照正常路径
fbm4 = {
    "m1": {"findings": [{"target": "d.py", "claim": "z 安全", "kind": "bug", "severity": "P2", "evidence": []}]},
    "m2": {"findings": [{"target": "d.py", "claim": "z 安全", "kind": "bug", "severity": "P2", "evidence": []}]},
}
c4, s4, d4 = cluster_issues(["m1", "m2"], fbm4)
print("probe4 consensus:", [(x["target"], x["raised_by"], x["state"]) for x in c4])
