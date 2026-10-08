"""Live network contracts: 0 healthy, 1 repository/contract failure, 2 degraded.

Offline tests exercise classification and subprocess execution separately from
these opt-in live probes. External output is never copied to published reports.
"""
import argparse
import re
import subprocess

from monitoring_status import emit_report, make_report
from qa import ROOT, fences, run_fence


def classify_process(process):
    if process.returncode == 0:
        if any(line.startswith('SKIP ') for line in process.stdout.splitlines()):
            return 'degraded', 'optional external check skipped; configuration unavailable'
        return 'healthy', ''
    # Use the terminal exception, not any occurrence of a network word in an
    # assertion or traceback source line. A local assertion remains failed.
    terminal = next((line.strip() for line in reversed(process.stderr.splitlines())
                     if line.strip()), '')
    http = re.match(r'^(?:urllib\.error\.)?HTTPError: HTTP Error (\d{3})\b', terminal)
    if http and (int(http[1]) in {401, 403, 408, 425, 429} or int(http[1]) >= 500):
        return 'degraded', 'external authentication, quota or service unavailable'
    if re.match(r'^(?:(?:urllib\.error|http\.client|socket|ssl|requests\.exceptions)\.)?'
                r'(?:URLError|TimeoutError|ConnectionError|ConnectionResetError|'
                r'ConnectionAbortedError|ConnectionRefusedError|RemoteDisconnected|'
                r'gaierror|SSLError|SSLCertVerificationError|SSLEOFError|'
                r'IncompleteRead|BadStatusLine|ConnectTimeout|ReadTimeout):', terminal):
        return 'degraded', 'external timeout or transport unavailable'
    return 'failed', 'schema, identity or code contract failed; inspect locally with credentials redacted'


def check_external_apis(root=ROOT):
    results = []
    for path in sorted((root / 'skills').glob('*/SKILL.md')):
        try:
            classified = list(fences(path))
        except (ValueError, SyntaxError, OSError):
            results.append({'name': path.parent.name, 'status': 'failed',
                            'reason': 'repository code fence classification invalid'})
            continue
        for i, kind, code in classified:
            if kind != 'external-test: true':
                continue
            try:
                process = run_fence(path, i, code, timeout=180)
                status, reason = classify_process(process)
            except subprocess.TimeoutExpired:
                status, reason = 'degraded', 'external check timeout'
            except OSError:
                status, reason = 'failed', 'repository subprocess could not start'
            results.append({'name': f'{path.parent.name}:{i}', 'status': status, 'reason': reason})
    return make_report('external-apis', results)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='persist machine-readable tri-state report')
    parser.add_argument('--summary', help='append a Markdown summary (defaults to GITHUB_STEP_SUMMARY)')
    args = parser.parse_args(argv)
    return emit_report(check_external_apis(), args.output, args.summary)


if __name__ == '__main__':
    raise SystemExit(main())
