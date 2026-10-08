"""Persist explicit monitoring states independently of the CI job conclusion."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


EXIT_CODES = {'healthy': 0, 'failed': 1, 'degraded': 2}


def make_report(check, results, **metadata):
    states = [result['status'] for result in results]
    if not states or 'failed' in states:
        status = 'failed'
    elif 'degraded' in states:
        status = 'degraded'
    else:
        status = 'healthy'
    if any(state not in EXIT_CODES for state in states):
        raise ValueError('unknown monitoring status')
    return {'check': check, 'status': status,
            'checked_at': datetime.now(timezone.utc).isoformat(),
            **metadata, 'results': results}


def emit_report(report, output=None, summary=None):
    payload = json.dumps(report, indent=2, allow_nan=False)
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + '\n', encoding='utf-8')
    print(payload)
    summary = summary or os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        lines = [f"### {report['check']}: {report['status']}", '']
        if 'hermes_sha' in report:
            lines.append(f"Tested Hermes SHA: `{report['hermes_sha'] or 'unavailable'}`")
        lines += ['', '| Check | State | Reason |', '| --- | --- | --- |']
        for result in report['results']:
            # Reasons are controlled messages, never external stdout or tracebacks.
            lines.append(f"| {result['name']} | {result['status']} | {result.get('reason', '')} |")
        if not report['results']:
            lines.append('| discovery | failed | No checks discovered |')
        summary = Path(summary)
        summary.parent.mkdir(parents=True, exist_ok=True)
        with summary.open('a', encoding='utf-8') as stream:
            stream.write('\n'.join(lines) + '\n')
    return EXIT_CODES[report['status']]
