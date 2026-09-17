# -*- coding: utf-8 -*-
"""Universal Model Context Protocol (MCP) server for academic skills.

Exposes core academic verification, statistical recompute, and watch workflows
over standard JSON-RPC 2.0 stdio transport without external framework lock-in.
Compatible with Claude Code, Cursor, Codex, Gemini CLI, and Hermes.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 导入核心功能模块
sys.path.insert(0, str(ROOT / "skills/quantitative-paper-audit/scripts"))
sys.path.insert(0, str(ROOT / "skills/academic-source-verification/scripts"))
sys.path.insert(0, str(ROOT / "scripts/scfabric"))

try:
    import recompute
except Exception:
    recompute = None

try:
    import verify_work
except Exception:
    verify_work = None


TOOLS = [
    {
        "name": "academic_recompute_statistics",
        "description": "Recompute statistical claims (effect sizes, p-values, t-tests, CIs, OR/RR) to detect rounding errors or impossible figures.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "t_stat": {"type": "number", "description": "Reported t-statistic"},
                "df": {"type": "integer", "description": "Degrees of freedom"},
                "p_value": {"type": "number", "description": "Reported p-value"},
                "mean1": {"type": "number", "description": "Group 1 mean"},
                "sd1": {"type": "number", "description": "Group 1 SD"},
                "n1": {"type": "integer", "description": "Group 1 size"},
                "mean2": {"type": "number", "description": "Group 2 mean"},
                "sd2": {"type": "number", "description": "Group 2 SD"},
                "n2": {"type": "integer", "description": "Group 2 size"}
            }
        }
    },
    {
        "name": "academic_check_percentage",
        "description": "Check if a reported percentage and count can mathematically arise from a sample size.",
        "inputSchema": {
            "type": "object",
            "required": ["count", "percent"],
            "properties": {
                "count": {"type": "integer", "description": "Observed count (numerator)"},
                "percent": {"type": "number", "description": "Reported percentage (e.g. 12.5)"},
                "sample_size": {"type": "integer", "description": "Optional total sample size (denominator)"}
            }
        }
    },
    {
        "name": "academic_scfabric_hardware_probe",
        "description": "Probe local hardware accelerators (CUDA, ROCm, MPS, XPU) and execution environments.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def handle_tool_call(name: str, arguments: dict) -> dict:
    if name == "academic_recompute_statistics":
        if recompute is None:
            return {"error": "recompute module unavailable"}
        t = arguments.get("t_stat")
        df = arguments.get("df")
        p = arguments.get("p_value")
        res = {}
        if t is not None and df is not None:
            recomputed_p = recompute.p_from_t(t, df)
            res["recomputed_p"] = recomputed_p
            if p is not None:
                res["p_match"] = recompute.check_p_value_match(p, recomputed_p)
        if "mean1" in arguments and "mean2" in arguments:
            d = recompute.cohens_d(
                arguments["mean1"], arguments.get("sd1", 1.0), arguments.get("n1", 10),
                arguments["mean2"], arguments.get("sd2", 1.0), arguments.get("n2", 10)
            )
            res["cohens_d"] = d
        return res

    elif name == "academic_check_percentage":
        if recompute is None:
            return {"error": "recompute module unavailable"}
        count = arguments["count"]
        pct = arguments["percent"]
        n = arguments.get("sample_size")
        return recompute.check_percentage(count, pct, n)

    elif name == "academic_scfabric_hardware_probe":
        import hardware_probe
        return hardware_probe.probe()

    return {"error": f"Unknown tool: {name}"}


def process_message(msg: dict) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        client_version = (msg.get("params") or {}).get("protocolVersion", "2026-07-28")
        # 协商协议版本: 优先使用 2026-07-28 官方最新规范, 兼容 2024-11-05
        negotiated_version = client_version if client_version in ("2026-07-28", "2024-11-05") else "2026-07-28"
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": negotiated_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "hermes-academic-skills",
                    "version": "2.0.0"
                }
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS}
        }
    elif method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        result_data = handle_tool_call(name, arguments)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result_data, ensure_ascii=False, indent=2)
                    }
                ]
            }
        }
    elif method == "notifications/initialized":
        return None

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    }


def main():
    if sys.platform == "win32":
        for s in (sys.stdin, sys.stdout):
            if s and hasattr(s, "reconfigure"):
                s.reconfigure(encoding="utf-8")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = process_message(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"}
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
