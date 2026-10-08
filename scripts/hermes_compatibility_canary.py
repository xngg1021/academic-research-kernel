"""Import the checked-out real Hermes loader without installing the full agent.

The pinned and latest-upstream channels produce separate reports. The canary
checks plugin manifest, skill discovery, and MCP command translation; full
runtime/CLI lifecycle checks remain in the pinned tap-lifecycle job.
"""
import argparse
import importlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from monitoring_status import emit_report, make_report


ROOT = Path(__file__).resolve().parents[1]


def check_loader(root, upstream):
    # No installed Hermes package may substitute for this checkout.
    sys.path.insert(0, str(upstream))
    try:
        loader = importlib.import_module('hermes_cli.agent_plugins')
        if not Path(loader.__file__).resolve().is_relative_to(upstream):
            raise ValueError('Hermes loader did not come from the tested checkout')
        diagnostics = []
        manifest, errors = loader._validate_manifest(root)
        if not manifest or errors:
            raise ValueError('plugin manifest rejected')
        skills = loader._discover_skills(root, diagnostics)
        expected = {path.parent.name for path in (root / 'skills').glob('*/SKILL.md')}
        if not expected or {skill.name for skill in skills} != expected:
            raise ValueError('skill discovery differs from the repository inventory')
        with tempfile.TemporaryDirectory(prefix='ark-hermes-canary-') as directory:
            mcp = loader._discover_mcp(root, Path(directory), diagnostics, create_data=False)
        config = mcp.get('academic-skills')
        if diagnostics or not config or config.get('args', [])[-1:] != ['mcp']:
            raise ValueError('MCP command translation rejected')
        return len(skills)
    finally:
        sys.path.pop(0)


def check_compatibility(upstream, channel, checkout_outcome='success', expected_sha=None, root=ROOT):
    upstream = Path(upstream).resolve()
    metadata = {'channel': channel, 'hermes_sha': None}
    if checkout_outcome != 'success':
        return make_report(f'hermes-{channel}', [{'name': 'upstream-checkout', 'status': 'degraded',
                           'reason': f'external checkout {checkout_outcome}; compatibility not tested'}], **metadata)
    try:
        revision = subprocess.run(['git', '-C', str(upstream), 'rev-parse', 'HEAD'],
                                  capture_output=True, text=True, check=True, timeout=20).stdout.strip()
        if not re.fullmatch('[0-9a-f]{40}', revision):
            raise ValueError('invalid checkout revision')
        metadata['hermes_sha'] = revision
        if expected_sha is not None and revision != expected_sha:
            raise ValueError('pinned checkout differs from the expected SHA')
        count = check_loader(Path(root).resolve(), upstream)
        results = [{'name': 'manifest-skills-mcp-loader', 'status': 'healthy', 'reason': f'{count} skills discovered'}]
    except Exception as error:
        # Import/signature/validation failures after successful checkout are a
        # compatibility failure, never relabeled as external transport trouble.
        results = [{'name': 'manifest-skills-mcp-loader', 'status': 'failed',
                    'reason': f'loader contract failed ({type(error).__name__})'}]
    return make_report(f'hermes-{channel}', results, **metadata)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', required=True, type=Path)
    parser.add_argument('--channel', required=True, choices=('pinned', 'latest-upstream'))
    parser.add_argument('--checkout-outcome', default='success')
    parser.add_argument('--expected-sha')
    parser.add_argument('--output', required=True)
    parser.add_argument('--summary', help='append a Markdown summary (defaults to GITHUB_STEP_SUMMARY)')
    args = parser.parse_args(argv)
    return emit_report(check_compatibility(args.upstream, args.channel, args.checkout_outcome,
                                          args.expected_sha), args.output, args.summary)


if __name__ == '__main__':
    raise SystemExit(main())
