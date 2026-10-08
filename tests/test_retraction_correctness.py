"""Correctness regressions; every external response here is labelled test data.

Only HTTP and clock boundaries are substituted. The watcher, state transitions,
file locks, atomic writer, diff records, and multiprocessing remain real.
"""
import importlib.util
import contextlib
import io
import json
import multiprocessing
import os
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / 'skills/retraction-watch/scripts/watch.py'


def load_watch():
    spec = importlib.util.spec_from_file_location('correctness_watch', WATCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


watch = load_watch()


def write_watchlist(path, *dois):
    path.write_text(json.dumps({'dois': list(dois)}), encoding='utf-8')


def read_state(path):
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.mark.parametrize('body', [{}, {'is_retracted': None},
                                   {'is_retracted': 'false'}, {'is_retracted': 0},
                                   {'is_retracted': []}, {'is_retracted': {}}])
def test_successful_http_invalid_boolean_remains_unknown(monkeypatch, body):
    """Fault-injected HTTP success must not invent an OpenAlex negative."""
    def external_fixture(url, timeout=20):
        if url.startswith(watch.OPENALEX):
            return body
        return {'message': {'items': [], 'total-results': 0}}
    monkeypatch.setattr(watch, 'get', external_fixture)
    assert watch.check_doi('10.1000/test-data')['is_retracted'] is None


def test_run_different_doi_interleaving_preserves_committed_update(monkeypatch, tmp_path):
    """A has read the old A/B file before B commits; A must submit only A."""
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({doi: {'is_retracted': False, 'signals': []}
                                 for doi in ('10.1000/a', '10.1000/b')}), encoding='utf-8')
    wl_a, wl_b = tmp_path / 'a.json', tmp_path / 'b.json'
    write_watchlist(wl_a, '10.1000/a')
    write_watchlist(wl_b, '10.1000/b')
    a_query = threading.Event()
    b_saved = threading.Event()
    errors = []

    def external_fixture(doi):
        if doi.endswith('/a'):
            a_query.set()
            assert b_saved.wait(10)
        return {'is_retracted': True, 'signals': []}

    def run_a():
        try:
            watch.run(wl_a, state)
        except BaseException as exc:
            errors.append(exc)

    monkeypatch.setattr(watch, 'check_doi', external_fixture)
    thread = threading.Thread(target=run_a)
    thread.start()
    assert a_query.wait(10)
    try:
        watch.run(wl_b, state)
    finally:
        b_saved.set()
        thread.join(10)
    assert not thread.is_alive()
    assert not errors
    assert read_state(state)['10.1000/b']['is_retracted'] is True


class TestHTTPResponse:
    """Synthetic response, never an online service observation."""
    __test__ = False

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps(self.body).encode('utf-8')


def install_http_fixture(module, state, value, entered=None, release=None, notices=None, monkeypatch=None):
    def external_http(request, timeout=20):
        # This process must not hold a lease during HTTP. Another process may
        # legitimately commit concurrently, including while this HTTP returns.
        try:
            lease = json.loads(state.with_name(state.name + '.lock').read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            lease = {}
        assert lease.get('pid') != os.getpid()
        if request.full_url.startswith(module.OPENALEX):
            if entered is not None:
                entered.set()
                assert release.wait(15), 'test process barrier timed out'
            return TestHTTPResponse({'is_retracted': value})
        return TestHTTPResponse({'message': {'items': notices or [], 'total-results': len(notices or [])}})
    if monkeypatch is None:
        module.urlopen = external_http
    else:
        monkeypatch.setattr(module, 'urlopen', external_http)


def process_run_http(watchlist, state, value, entered, release, output):
    """Spawn-safe worker mocks only urllib's external HTTP boundary."""
    module = load_watch()
    capture = io.StringIO()
    try:
        install_http_fixture(module, Path(state), value, entered, release)
        with contextlib.redirect_stdout(capture):
            result = module.run(watchlist, state)
        output.put({'result': result, 'events': capture.getvalue()})
    except BaseException as exc:
        output.put({'error': repr(exc)})
        raise


@pytest.mark.parametrize('same_doi', [False, True])
def test_chain_b_http_to_concurrent_commit_events_and_reload(tmp_path, capsys, same_doi, monkeypatch):
    """Real spawned process A pauses HTTP; B commits; A commits last.

    Different DOI preserves both. Same DOI uses query-start order, so B's newer
    False survives A's late True; a subsequent new True -> False also succeeds.
    """
    state = tmp_path / 'state.json'
    doi_a, doi_b = '10.1000/test-data-a', '10.1000/test-data-b'
    if same_doi:
        doi_b = doi_a
    state.write_text(json.dumps({doi: {'is_retracted': False, 'signals': []}
                                 for doi in (doi_a, doi_b)}), encoding='utf-8')
    wl_a, wl_b = tmp_path / 'a.json', tmp_path / 'b.json'
    write_watchlist(wl_a, doi_a)
    write_watchlist(wl_b, doi_b)
    context = multiprocessing.get_context('spawn')
    entered, release, output = context.Event(), context.Event(), context.Queue()
    process = context.Process(target=process_run_http,
                              args=(str(wl_a), str(state), True, entered, release, output))
    process.start()
    try:
        assert entered.wait(15), 'child must reach HTTP only after reserving version'
        install_http_fixture(watch, state, False if same_doi else True, monkeypatch=monkeypatch)
        assert watch.run(wl_b, state) == 0
        version_b = read_state(state)[doi_b]['observation_version']
    finally:
        release.set()
        process.join(15)
        if process.is_alive():
            process.terminate()
            process.join(5)
    assert process.exitcode == 0
    child = output.get(timeout=5)
    assert child.get('result') == 0, child
    reloaded = read_state(state)
    assert reloaded[doi_b]['observation_version'] == version_b
    assert reloaded[doi_b]['is_retracted'] is (False if same_doi else True)
    assert reloaded[doi_a]['is_retracted'] is (False if same_doi else True)
    if same_doi:
        assert '已被新观测取代' in child['events']
    else:
        assert 'False -> True' in child['events']
    event_records = [child['events']]

    # New unknown retains history while exposing failure for this observation.
    install_http_fixture(watch, state, None, monkeypatch=monkeypatch)
    watch.run(wl_b, state)
    unknown = read_state(state)[doi_b]
    assert unknown['current_observation'] is None
    assert unknown['verification_status'] == 'retained_prior'
    assert unknown['is_retracted'] is (False if same_doi else True)
    assert unknown['source_status']['openalex'] == 'invalid_response'
    unknown_events = capsys.readouterr().out
    event_records.append(unknown_events)
    assert '本轮无法核验' in unknown_events

    # Valid evidence after unknown recovers; genuinely new True -> False allowed.
    install_http_fixture(watch, state, True, monkeypatch=monkeypatch)
    watch.run(wl_b, state)
    assert read_state(state)[doi_b]['verification_status'] == 'verified_current'
    install_http_fixture(watch, state, False, monkeypatch=monkeypatch)
    watch.run(wl_b, state)
    assert read_state(state)[doi_b]['is_retracted'] is False
    events = capsys.readouterr().out
    event_records.append(events)
    assert '恢复本轮核验' in events or 'False -> True' in events
    assert 'True -> False' in events
    # Repeated equivalent observation updates its version without inventing changes.
    watch.run(wl_b, state)
    repeated_events = capsys.readouterr().out
    event_records.append(repeated_events)
    assert '无状态变化' in repeated_events
    # Test glue records actual watcher events, then reloads both evidence and state.
    event_file = tmp_path / 'events.json'
    event_file.write_text(json.dumps({'origin': 'synthetic HTTP test data',
                                     'events': event_records}, ensure_ascii=False), encoding='utf-8')
    replayed_events = json.loads(event_file.read_text(encoding='utf-8'))
    assert replayed_events['events'] == event_records
    assert '本轮无法核验' in ''.join(replayed_events['events'])
    assert 'True -> False' in ''.join(replayed_events['events'])
    assert read_state(state)[doi_b]['current_observation'] is False


def test_two_spawned_writers_released_together_preserve_both_doi_updates(tmp_path):
    state = tmp_path / 'state.json'
    context = multiprocessing.get_context('spawn')
    release, output = context.Event(), context.Queue()
    workers = []
    for suffix in ('a', 'b'):
        wl = tmp_path / (suffix + '.json')
        write_watchlist(wl, '10.1000/test-data-' + suffix)
        entered = context.Event()
        process = context.Process(target=process_run_http,
                                  args=(str(wl), str(state), True, entered, release, output))
        workers.append((process, entered))
        process.start()
        assert entered.wait(15)
    try:
        # Both real processes have reserved versions and are waiting at HTTP.
        release.set()
        for process, _ in workers:
            process.join(15)
            assert process.exitcode == 0
        for _ in workers:
            assert output.get(timeout=5).get('result') == 0
    finally:
        release.set()
        for process, _ in workers:
            if process.is_alive():
                process.terminate()
                process.join(5)
    reloaded = read_state(state)
    assert set(reloaded) == {'10.1000/test-data-a', '10.1000/test-data-b'}
    assert all(snapshot['is_retracted'] is True for snapshot in reloaded.values())


def test_schema_v1_accepts_legacy_and_actual_current_snapshot(monkeypatch, tmp_path):
    schema = json.loads((ROOT / 'schemas/retraction-delta.schema.json').read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema)
    validator.validate({'is_retracted': False, 'signals': []})
    state, wl = tmp_path / 'state.json', tmp_path / 'wl.json'
    doi = '10.1000/test-data'
    write_watchlist(wl, doi)
    install_http_fixture(watch, state, True, monkeypatch=monkeypatch)
    watch.run(wl, state)
    validator.validate(read_state(state)[doi])
    install_http_fixture(watch, state, None, monkeypatch=monkeypatch)
    watch.run(wl, state)
    validator.validate(read_state(state)[doi])


def test_same_doi_cas_rejects_old_and_duplicate_versions(tmp_path):
    state = tmp_path / 'state.json'
    doi = '10.1000/test-data'
    first, second = watch._reserve_observation(state), watch._reserve_observation(state)
    fresh = watch._commit_observation(state, doi, {'is_retracted': False, 'signals': []}, second)
    assert fresh['applied']
    for version in (first, second):
        event = watch._commit_observation(state, doi, {'is_retracted': True, 'signals': []}, version)
        assert not event['applied']
        assert event['changes'] == []
    assert read_state(state)[doi]['is_retracted'] is False


def test_unknown_retains_latest_committed_history_not_queried_snapshot(tmp_path):
    state = tmp_path / 'state.json'
    doi = '10.1000/test-data'
    initial = watch._reserve_observation(state)
    watch._commit_observation(state, doi, {'is_retracted': False, 'signals': []}, initial)
    earlier, later = watch._reserve_observation(state), watch._reserve_observation(state)
    watch._commit_observation(state, doi, {'is_retracted': True, 'signals': []}, earlier)
    event = watch._commit_observation(state, doi, {'is_retracted': None, 'signals': []}, later)
    assert event['new']['is_retracted'] is True
    assert event['new']['current_observation'] is None
    assert event['new']['verification_status'] == 'retained_prior'
    assert any('本轮无法核验' in value for value in event['changes'])


@pytest.mark.parametrize('late_value', [True, False])
def test_late_confirmed_evidence_improves_history_while_current_stays_unknown(tmp_path, late_value):
    state = tmp_path / 'state.json'
    doi = '10.1000/test-data'
    state.write_text(json.dumps({doi: {'is_retracted': not late_value, 'signals': []}}))
    earlier, later = watch._reserve_observation(state), watch._reserve_observation(state)
    watch._commit_observation(state, doi, {'is_retracted': None, 'signals': []}, later)
    event = watch._commit_observation(state, doi, {'is_retracted': late_value, 'signals': []}, earlier)
    assert event['applied'] and event['historical_only']
    saved = read_state(state)[doi]
    assert saved['is_retracted'] is late_value
    assert saved['current_observation'] is None
    assert saved['verification_status'] == 'retained_prior'
    assert saved['observation_version'] == later
    assert saved['confirmed_observation_version'] == earlier
    assert any('本轮观测仍无法核验' in change for change in event['changes'])
    duplicate = watch._commit_observation(state, doi, {'is_retracted': not late_value, 'signals': []}, earlier)
    assert not duplicate['applied']
    assert read_state(state)[doi] == saved


def test_late_confirmations_have_their_own_version_order(tmp_path):
    state = tmp_path / 'state.json'
    doi = '10.1000/test-data'
    oldest, middle, current = [watch._reserve_observation(state) for _ in range(3)]
    watch._commit_observation(state, doi, {'is_retracted': None, 'signals': []}, current)
    watch._atomic_write_json(state, {doi: {'is_retracted': False, 'signals': [], 'observation_version': middle}})
    event = watch._commit_observation(state, doi, {'is_retracted': True, 'signals': []}, oldest)
    assert not event['applied']
    saved = read_state(state)[doi]
    assert saved['is_retracted'] is False
    assert saved['current_observation'] is None
    assert saved['observation_version'] == current
    assert saved['confirmed_observation_version'] == middle


def test_first_unknown_is_unverified_not_verified_current(monkeypatch, tmp_path):
    state, wl = tmp_path / 'state.json', tmp_path / 'wl.json'
    write_watchlist(wl, '10.1000/test-data')
    monkeypatch.setattr(watch, 'check_doi', lambda doi: {'is_retracted': None, 'signals': []})
    watch.run(wl, state)
    assert read_state(state)['10.1000/test-data']['verification_status'] == 'unverified'


@pytest.mark.parametrize('failure', ['timeout', 'rate_limit', 'transport'])
def test_external_unavailability_is_unknown_with_machine_readable_cause(monkeypatch, failure):
    def external_fixture(url, timeout=20):
        if not url.startswith(watch.OPENALEX):
            return {'message': {'items': []}}
        if failure == 'timeout':
            raise TimeoutError('synthetic test-data timeout')
        if failure == 'transport':
            raise URLError('synthetic test-data transport failure')
        raise HTTPError(url, 429, 'synthetic test-data rate limit', None, None)
    monkeypatch.setattr(watch, 'get', external_fixture)
    result = watch.check_doi('10.1000/test-data')
    assert result['is_retracted'] is None
    assert result['source_status']['openalex'] == 'unavailable'
    assert result['source_status']['crossref'] == 'verified'
    assert result['source_errors']['openalex']


def test_get_bounded_rate_limit_retry_then_unknown(monkeypatch):
    calls, waits = [], []
    def external_http(request, timeout=20):
        calls.append(request.full_url)
        if request.full_url.startswith(watch.OPENALEX):
            raise HTTPError(request.full_url, 429, 'synthetic rate limit', {'Retry-After': '0'}, None)
        return TestHTTPResponse({'message': {'items': []}})
    monkeypatch.setattr(watch, 'urlopen', external_http)
    monkeypatch.setattr(watch.time, 'sleep', waits.append)
    result = watch.check_doi('10.1000/test-data')
    assert result['is_retracted'] is None
    assert len([url for url in calls if url.startswith(watch.OPENALEX)]) == 4
    assert waits == [0.0, 0.0, 0.0]


def test_sources_disagree_without_boolean_voting(monkeypatch):
    def external_fixture(url, timeout=20):
        if url.startswith(watch.OPENALEX):
            return {'is_retracted': False}
        return {'message': {'items': [{'DOI': '10.1000/test-notice', 'update-to': [
            {'DOI': '10.1000/test-data', 'type': 'retraction', 'source': 'publisher'}]}]}}
    monkeypatch.setattr(watch, 'get', external_fixture)
    result = watch.check_doi('10.1000/test-data')
    assert result['is_retracted'] is False
    assert result['signals'] == ['retraction(publisher) update-doi=10.1000/test-notice']
    assert result['source_status'] == {'openalex': 'verified', 'crossref': 'verified'}


def test_crossref_failure_does_not_invent_removed_notices(monkeypatch, tmp_path):
    state, wl = tmp_path / 'state.json', tmp_path / 'wl.json'
    doi = '10.1000/test-data'
    write_watchlist(wl, doi)
    state.write_text(json.dumps({doi: {'is_retracted': True, 'signals': ['test-data prior notice']}}))
    def external_fixture(url, timeout=20):
        if url.startswith(watch.OPENALEX):
            return {'is_retracted': True}
        raise TimeoutError('synthetic test-data timeout')
    monkeypatch.setattr(watch, 'get', external_fixture)
    watch.run(wl, state)
    result = read_state(state)[doi]
    assert result['signals'] == ['test-data prior notice']
    assert result['source_status']['crossref'] == 'unavailable'


@pytest.mark.parametrize('content', ['{broken', '[]', '{"10.1000/test-data": 5}',
                                     '{"10.1000/test-data": {"is_retracted": "false"}}',
                                     '{"10.1000/test-data": {"observation_version": NaN}}'])
def test_corrupt_state_is_rejected_without_clearing(content, tmp_path):
    state = tmp_path / 'state.json'
    state.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError):
        watch._atomic_write_json(state, {'10.1000/new': {'is_retracted': True}})
    assert state.read_text(encoding='utf-8') == content
    assert not state.with_name(state.name + '.lock').exists()


def test_corrupt_sequence_rejected_without_state_loss(tmp_path):
    state = tmp_path / 'state.json'
    original = '{"10.1000/test-data": {"is_retracted": true, "signals": []}}'
    state.write_text(original)
    state.with_name(state.name + '.sequence.json').write_text('{bad')
    with pytest.raises(ValueError):
        watch._reserve_observation(state)
    assert state.read_text() == original


def test_atomic_replace_failure_recovers_and_unique_temp_does_not_collide(monkeypatch, tmp_path):
    state = tmp_path / 'state.json'
    watch._atomic_write_json(state, {'10.1000/prior': {'is_retracted': False, 'signals': []}})
    original = state.read_bytes()
    legacy_tmp = state.with_suffix('.json.tmp')
    legacy_tmp.write_text('unrelated existing temporary file')
    real_replace = watch.os.replace
    def failing_replace(source, destination):
        if Path(destination) == state:
            raise OSError('synthetic test-data write failure')
        return real_replace(source, destination)
    monkeypatch.setattr(watch.os, 'replace', failing_replace)
    with pytest.raises(OSError, match='synthetic'):
        watch._atomic_write_json(state, {'10.1000/new': {'is_retracted': True, 'signals': []}})
    assert state.read_bytes() == original
    assert legacy_tmp.read_text() == 'unrelated existing temporary file'
    assert list(tmp_path.glob('state.json.*.tmp')) == []
    assert not state.with_name(state.name + '.lock').exists()
    monkeypatch.setattr(watch.os, 'replace', real_replace)
    watch._atomic_write_json(state, {'10.1000/new': {'is_retracted': True, 'signals': []}})
    assert set(read_state(state)) == {'10.1000/prior', '10.1000/new'}


def test_old_owner_cannot_release_successor_lease(tmp_path):
    state = tmp_path / 'state.json'
    lock = state.with_name(state.name + '.lock')
    successor = {'pid': os.getpid(), 'created_at': time.time(), 'token': 'successor-owner'}
    lock.write_text(json.dumps(successor))
    watch._release_lease(state, 'old-owner')
    assert json.loads(lock.read_text()) == successor
    watch._release_lease(state, 'successor-owner')
    assert not lock.exists()


def test_live_expired_owner_cannot_be_reclaimed(monkeypatch, tmp_path):
    state = tmp_path / 'state.json'
    lock = state.with_name(state.name + '.lock')
    lock.write_text(json.dumps({'pid': os.getpid(), 'created_at': 0, 'token': 'live-owner'}))
    monkeypatch.setattr(watch, 'LOCK_TIMEOUT_SECONDS', 0)
    with pytest.raises(RuntimeError, match='state lock timeout'):
        watch._atomic_write_json(state, {'10.1000/test-data': {'is_retracted': True}})
    assert json.loads(lock.read_text())['token'] == 'live-owner'


def process_abandon_lease(state, acquired):
    module = load_watch()
    with module._state_lock(Path(state)):
        acquired.set()
        os._exit(0)  # Synthetic process crash: no Python finally block runs.


def test_dead_process_expired_lease_is_recovered(monkeypatch, tmp_path):
    state = tmp_path / 'state.json'
    context = multiprocessing.get_context('spawn')
    acquired = context.Event()
    process = context.Process(target=process_abandon_lease, args=(str(state), acquired))
    process.start()
    assert acquired.wait(15)
    process.join(15)
    assert process.exitcode == 0
    current_time = time.time()
    monkeypatch.setattr(watch.time, 'time', lambda: current_time + 100)
    watch._atomic_write_json(state, {'10.1000/test-data': {'is_retracted': True, 'signals': []}})
    assert read_state(state)['10.1000/test-data']['is_retracted'] is True
    assert not state.with_name(state.name + '.lock').exists()
