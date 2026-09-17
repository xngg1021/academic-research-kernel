# -*- coding: utf-8 -*-
"""探针补充:坐实单模型双 findings 因关键词被误标 contradiction 的路径。"""
import sys
sys.path.insert(0, r"<WORKSPACE>\repos\hermes-academic-skills\skills\cross-review-five\scripts")
from orchestrate_v2 import cluster_issues

# 探针5: claim 含"不"字(对应 I06/I08 的真实 claim"不再提示"形态)
fbm5 = {
    "m1": {"findings": [
        {"target": "e.py", "claim": "后续命令都不再提示", "kind": "bug", "severity": "P0", "evidence": []},
        {"target": "e.py", "claim": "第二条同模型发现", "kind": "bug", "severity": "P0", "evidence": []},
    ]},
}
c5, s5, d5 = cluster_issues(["m1"], fbm5)
print("probe5 ('不' keyword) contradictions:", [(x["target"], x["raised_by"], x["state"]) for x in d5])
print("probe5 consensus:", [(x["target"], x["raised_by"], x["state"]) for x in c5])

# 探针6: claim 含"错"字(对应 I16 的真实 claim"目标绑定错误"形态)
fbm6 = {
    "m1": {"findings": [
        {"target": "f.py", "claim": "目标绑定错误", "kind": "bug", "severity": "P2", "evidence": []},
        {"target": "f.py", "claim": "第二条同模型发现", "kind": "bug", "severity": "P2", "evidence": []},
    ]},
}
c6, s6, d6 = cluster_issues(["m1"], fbm6)
print("probe6 ('错' keyword) contradictions:", [(x["target"], x["raised_by"], x["state"]) for x in d6])
print("probe6 consensus:", [(x["target"], x["raised_by"], x["state"]) for x in c6])
