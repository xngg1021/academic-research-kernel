"""Real stdio sessions: protocol boundaries and statistical error semantics."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(os.environ.get('ARK_REPO', Path(__file__).resolve().parents[1]))


def session(lines):
    wire = '\n'.join(line if isinstance(line, str) else json.dumps(line) for line in lines) + '\n'
    proc = subprocess.run([sys.executable, str(ROOT / 'scripts/mcp_server.py')],
                          input=wire, text=True, encoding='utf-8', capture_output=True, timeout=90)
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines()]


def request(method, params=None, call_id=1):
    msg = {'jsonrpc': '2.0', 'id': call_id, 'method': method}
    if params is not None:
        msg['params'] = params
    return msg


def tool(arguments, name='academic_recompute_statistics', call_id=1):
    return request('tools/call', {'name': name, 'arguments': arguments}, call_id)


def test_protocol_errors_notifications_and_eof_share_one_live_session():
    replies = session([
        request('initialize', {'protocolVersion': '2024-11-05'}),
        {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
        {'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': 88}},
        {'jsonrpc': '2.0', 'method': 'unknown/notification'},
        request('ping', call_id='ping-identity'),
        '{', [], {'jsonrpc': '2.0'}, {'method': 'ping'},
        {'jsonrpc': '2.0', 'method': 'ping', 'params': 3},
        request('tools/list', [], 3), request('unknown/method', call_id=4),
        request('tools/call', {}, 5),
        {'jsonrpc': '2.0', 'id': None, 'method': 'ping'},
        request('ping', call_id=6),
    ])
    assert len(replies) == 12
    assert replies[1] == {'jsonrpc': '2.0', 'id': 'ping-identity', 'result': {}}
    assert [r['error']['code'] for r in replies[2:-1]] == [-32700, -32600, -32600, -32600, -32600, -32602, -32601, -32602, -32600]
    assert replies[-1] == {'jsonrpc': '2.0', 'id': 6, 'result': {}}


@pytest.mark.parametrize('arguments', [
    {}, {'t_stat': 1}, {'t_stat': 1, 'df': 0}, {'t_stat': 1, 'df': -1},
    {'mean1': 1, 'mean2': 2}, {'p_value': .05},
    {'t_stat': 1, 'df': 30, 'p_value': 1e-5, 'p_value_literal': '0.00010'},
    {'t_stat': 1, 'df': 30, 'p_value': .1, 'p_value_literal': '.10', 'p_value_decimals': 1},
    {'t_stat': 1, 'df': 30, 'p_value': .1, 'p_value_decimals': -1},
])
def test_failed_statistics_are_tool_errors(arguments):
    reply = session([tool(arguments)])[0]['result']
    assert reply['isError'] is True
    assert json.loads(reply['content'][0]['text'])['error']


def test_partial_failure_keeps_success_and_reports_failed_component():
    reply = session([tool({'t_stat': 1, 'df': 30, 'mean1': 1})])[0]['result']
    data = json.loads(reply['content'][0]['text'])
    assert reply['isError'] is True
    assert .32530 < data['recomputed_p'] < .32532
    assert data['status'] == 'partial_failure' and 'cohens_d' in data['failures']


def test_scientific_negative_and_validation_negative_are_successful_calls():
    replies = session([
        tool({'t_stat': 1, 'df': 30, 'p_value': .00001}),
        tool({'t_stat': 1, 'df': 30, 'p_value': .3253}, call_id=2),
        tool({'t_stat': 1, 'df': 30.5, 'p_value': .32530, 'p_value_literal': '.32530'}, call_id=3),
        tool({'envelope': {}}, name='research_artifact_validate', call_id=4),
    ])
    assert all(reply['result']['isError'] is False for reply in replies)
    data = [json.loads(reply['result']['content'][0]['text']) for reply in replies]
    assert data[0]['p_match']['consistent'] is False
    assert data[1]['p_match']['consistent'] is True
    assert data[3]['valid'] is False


def test_json_overflow_nonstandard_constants_and_bad_count_do_not_end_session():
    replies = session([
        '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"academic_recompute_statistics","arguments":{"t_stat":1e309,"df":30}}}',
        '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"academic_recompute_statistics","arguments":{"t_stat":NaN,"df":30}}}',
        tool({'count': 1001, 'sample_size': 1000, 'percent': 100}, name='academic_check_percentage', call_id=3),
        request('ping', call_id=4),
    ])
    assert replies[0]['result']['isError'] is True
    assert replies[1]['error']['code'] == -32700
    assert replies[2]['result']['isError'] is True
    assert replies[3]['result'] == {}
    for reply in replies:
        json.dumps(reply, allow_nan=False)


def test_escaped_surrogate_id_preserves_identity_and_next_request():
    replies = session([request('ping', call_id='\ud800'), request('ping', call_id='中文')])
    assert replies == [{'jsonrpc': '2.0', 'id': '\ud800', 'result': {}},
                       {'jsonrpc': '2.0', 'id': '中文', 'result': {}}]
