# -*- coding: utf-8 -*-
"""五人异构模型交叉编排器:kimi-k3 + deepseek-v4-pro + glm-5.3 + gemini-3.8-flash + gemini-3.1-pro.

用法:
    python orchestrate.py <stream_dir> --task <task.md> --stage plan
    python orchestrate.py <stream_dir> --stage review [--models a,b,c]
    python orchestrate.py <stream_dir> --stage status

约定:
- 一个任务流 = 一个目录,内含 task.md(任务书)、prompt-*.txt、review-*.md、log-*.txt;
- plan 阶段:每个模型拿到同一份任务书,独立产出互不可见;
- review 阶段:轮转配对,模型 i 审模型 i+1 的产出,产出互审意见;
- 完成判定靠产物文件落盘与进程退出,不依赖任何完成通知;
- 每个模型是完整 hermes 子进程,用 -m/--provider 覆盖模型,不动主配置。

模型表(短名 → provider, 官方模型名)。GLM 5.3 为始终思考推理模型,
由 hermes 的 zai provider 自动处理思考参数。
"""
import argparse
import json
import os
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

POLL_SECONDS = 15
TIMEOUT_SECONDS = 40 * 60

PLAN_PROMPT = """任务:评审任务书并独立产出方案。

您是一名独立评审者。请依次完成:

一、阅读任务书文件 {task_path}。

二、阅读任务书中指定的全部材料。

三、按任务书要求完成工作,将完整产出写入文件 {out_path}。

约束:只读任务书与指定材料,不得修改任务书指定范围之外的任何文件;不得修改其他评审者的产出文件;输出用简体中文,按您自然的文风写作;产出必须基于您实际读到的内容,不得虚构不存在的文件或接口。
"""

REVIEW_PROMPT = """任务:交叉审查另一位评审者的产出。

请依次完成:

一、阅读任务书文件 {task_path}。

二、阅读被审查的产出文件 {target_path}。

三、对被审查产出逐条给出判断:同意、反对或部分同意,每条附理由;指出事实错误、遗漏与逻辑漏洞;给出您的修正建议。

四、将完整审查意见写入文件 {out_path}。

约束:只读任务书与产出文件,不得修改任何现有文件;输出用简体中文,按您自然的文风写作;审查必须基于实际读到的内容。
"""


def pairings(model_keys):
    """轮转配对:模型 i 审模型 i+1,最后一个审第一个。"""
    n = len(model_keys)
    if n < 2:
        return []
    return [(model_keys[i], model_keys[(i + 1) % n]) for i in range(n)]


def spawn(model_key, prompt_path, log_path):
    provider, model = MODELS[model_key]
    cmd = ["hermes", "chat", "--query-file", prompt_path, "--oneshot",
           "-m", model, "--provider", provider]
    if model_key == "glm53":
        # GLM 5.3 always reasons; the server default is the max effort level,
        # which is extremely slow. Request the light level explicitly.
        cmd += ["--reasoning", "low"]
    with open(log_path, "wb") as log:
        return subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT,
            cwd=os.getcwd(),
        )


def wait_for_outputs(stream, out_paths, procs):
    """轮询产物文件与进程退出,不依赖任何完成通知。"""
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        files_ok = all(os.path.exists(p) and os.path.getsize(p) > 0 for p in out_paths)
        procs_ok = all(p.poll() is not None for p in procs)
        if files_ok and procs_ok:
            return True
        if procs_ok and not files_ok:
            return False
        time.sleep(POLL_SECONDS)
    return False


def stage_plan(stream, task_path, model_keys):
    out_paths, procs = [], []
    for k in model_keys:
        prompt_path = os.path.join(stream, f"prompt-{k}.txt")
        out_path = os.path.join(stream, f"review-{k}.md")
        log_path = os.path.join(stream, f"log-{k}.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(PLAN_PROMPT.format(task_path=task_path, out_path=out_path))
        procs.append(spawn(k, prompt_path, log_path))
        out_paths.append(out_path)
        print(f"[plan] {k} 已启动 pid={procs[-1].pid}")
    ok = wait_for_outputs(stream, out_paths, procs)
    for p in procs:
        if p.poll() is None:
            p.terminate()
    status = {os.path.basename(p): os.path.exists(p) for p in out_paths}
    print(f"[plan] {'完成' if ok else '超时或失败'} {json.dumps(status, ensure_ascii=False)}")
    return ok


def stage_review(stream, task_path, model_keys):
    out_paths, procs = [], []
    for reviewer, target in pairings(model_keys):
        out_path = os.path.join(stream, f"review-of-{target}-by-{reviewer}.md")
        target_path = os.path.join(stream, f"review-{target}.md")
        if not os.path.exists(target_path):
            print(f"[review] 跳过 {reviewer}:被审产出缺失 {target_path}")
            continue
        prompt_path = os.path.join(stream, f"prompt-review-{reviewer}-on-{target}.txt")
        log_path = os.path.join(stream, f"log-review-{reviewer}-on-{target}.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(REVIEW_PROMPT.format(task_path=task_path,
                                         target_path=target_path, out_path=out_path))
        procs.append(spawn(reviewer, prompt_path, log_path))
        out_paths.append(out_path)
        print(f"[review] {reviewer} 审 {target} pid={procs[-1].pid}")
    if not procs:
        print("[review] 无可审查项")
        return False
    ok = wait_for_outputs(stream, out_paths, procs)
    for p in procs:
        if p.poll() is None:
            p.terminate()
    status = {os.path.basename(p): os.path.exists(p) for p in out_paths}
    print(f"[review] {'完成' if ok else '超时或失败'} {json.dumps(status, ensure_ascii=False)}")
    return ok


def stage_status(stream):
    patterns = ("task.md", "review-*.md", "review-of-*.md", "log-*.txt")
    for pat in patterns:
        import glob
        found = sorted(glob.glob(os.path.join(stream, pat)))
        print(f"{pat}: {len(found)} 个")
        for p in found:
            print(f"  {os.path.basename(p)} ({os.path.getsize(p)} 字节)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="五人异构模型交叉编排器")
    parser.add_argument("stream_dir", help="任务流目录")
    parser.add_argument("--task", default="task.md", help="任务书路径(默认流目录内 task.md)")
    parser.add_argument("--stage", choices=["plan", "review", "status"], required=True)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS),
                        help=f"逗号分隔的短名子集,默认五人全上: {','.join(DEFAULT_MODELS)}")
    args = parser.parse_args(argv)

    stream = os.path.abspath(args.stream_dir)
    os.makedirs(stream, exist_ok=True)
    task_path = args.task if os.path.isabs(args.task) else os.path.join(stream, args.task)

    model_keys = [k.strip() for k in args.models.split(",") if k.strip()]
    for k in model_keys:
        if k not in MODELS:
            print(f"未知模型短名: {k},可用: {', '.join(MODELS)}", file=sys.stderr)
            return 2

    if args.stage == "status":
        stage_status(stream)
        return 0
    if not os.path.exists(task_path):
        print(f"任务书缺失: {task_path}", file=sys.stderr)
        return 2
    if args.stage == "plan":
        return 0 if stage_plan(stream, task_path, model_keys) else 1
    return 0 if stage_review(stream, task_path, model_keys) else 1


if __name__ == "__main__":
    raise SystemExit(main())
