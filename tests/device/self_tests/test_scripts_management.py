"""Actual script journal and lifecycle engine with native input/clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE))
from contracts import validate_operation_arguments, validate_operation_result
from script_fixture_client import ScriptFixtureClient
from scripts_journey import scripts_journey

spec = importlib.util.spec_from_file_location('owned_script_fixture', DEVICE / 'fixture/script_management.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class NativeBoundary:
    def __init__(self, mutation=''):
        self.now = 0.0
        self.journal = fixture.Journal(lambda: self.now)
        self.nonce = self.journal.create()
        self.origin = 'http://reference.test:18080'
        self.source = self.origin + f'/script-management/{self.nonce}/client.js'
        self.missing = self.source.removesuffix('client.js') + 'missing.js'
        config = self.journal.source(self.nonce, 'client.js', self.origin).split(b' = ', 1)[1].split(b';\n', 1)[0]
        self.config = json.loads(config)
        self.proof = json.loads(self.journal.source(self.nonce, 'companion.js', self.origin).split(b' = ', 1)[1][:-2])
        self.mutation = mutation
        self.actions, self.reports, self.checks = [], [], []
        self.active = {}
        self.sequences = {}
        self.next_id = 0
        self.loads = 0
        self.late = []
        self.replay = None

    def emit(self, identifier):
        sequence = self.sequences.get(identifier, 0)
        self.journal.receive(self.nonce, {'token': self.config['receiptToken'],
            'instance': identifier, 'sequence': sequence,
            'kind': 'start' if sequence == 0 else 'tick', 'companionProof': self.proof})
        self.sequences[identifier] = sequence + 1

    def start(self):
        self.next_id += 1
        identifier = f'{self.next_id:032x}'
        self.emit(identifier)
        self.active[identifier] = self.now + 0.25

    def invoke(self, name, arguments):
        self.actions.append((name, arguments))
        if name == 'scripts.manager.open' and self.mutation == 'open-close-error':
            raise RuntimeError('native entry unavailable')
        if name == 'scripts.manager.close' and self.mutation in {'close-error', 'open-close-error'}:
            raise RuntimeError('native close unavailable')
        if name == 'scripts.load-url':
            if arguments['url'] == self.missing:
                if self.mutation != 'missing-load-ignored':
                    self.journal.delivered(self.nonce, 'missing.js')
            else:
                self.loads += 1
                if self.mutation == 'ack-only' or self.mutation == 'reload-ignored' and self.loads > 1:
                    return {'performed': True}
                self.journal.delivered(self.nonce, 'client.js')
                if self.mutation != 'missing-companion':
                    self.journal.delivered(self.nonce, 'companion.js')
                    self.start()
        elif name == 'scripts.restart':
            if self.mutation == 'restart-ignored':
                return {'performed': True}
            if self.mutation != 'restart-leaks-old':
                if self.mutation == 'one-late-request':
                    self.late += [(self.now + 1.75, identifier) for identifier in self.active]
                self.active.clear()
            self.start()
        elif name == 'scripts.stop' and self.mutation != 'stop-ignored':
            self.active.clear()
        return {'performed': True}

    def sleep(self, seconds):
        if self.mutation == 'clock-backwards':
            self.now -= seconds
            return
        end = self.now + seconds
        while True:
            due = [(when, identifier, False) for identifier, when in self.active.items() if when <= end]
            due += [(when, identifier, True) for when, identifier in self.late if when <= end]
            if not due:
                break
            when, identifier, late = min(due)
            self.now = when
            self.emit(identifier)
            if late:
                self.late.remove((when, identifier))
            else:
                self.active[identifier] = when + 0.25
        self.now = end
        if self.mutation == 'restarted-engine-dies' and self.next_id == 2:
            for identifier in list(self.active):
                if self.sequences.get(identifier, 0) >= 5:
                    self.active.pop(identifier)

    def observe(self):
        value = self.journal.observe(self.nonce)
        if self.mutation == 'replayed-observer':
            if self.replay is None:
                self.replay = copy.deepcopy(value)
            return copy.deepcopy(self.replay)
        if self.mutation == 'erased-history' and len(value['instances']) > 1:
            value['instances'] = value['instances'][1:]
        if self.mutation == 'foreign-fixture-source':
            value['sourceSha256'] = '0' * 64
        return value

    def continuity(self, phase):
        self.checks.append(phase)
        if self.mutation == 'process-restarted' and self.loads:
            raise AssertionError('application process restarted')

    def run(self):
        return scripts_journey(self.source, self.missing, invoke=self.invoke,
            observe=self.observe, assert_session=self.continuity,
            monotonic=lambda: self.now, sleep=self.sleep, report=self.reports.append)


class ScriptManagementJourneyTests(unittest.TestCase):
    def test_normal_url_load_restart_stop_reload_and_failure_require_actual_execution(self):
        native = NativeBoundary()
        result = native.run()
        self.assertEqual(['initial-load', 'restart', 'restart-old-stopped-new-active',
            'stop', 'load-after-stop', 'reloaded-old-stopped-new-active',
            'final-stop', 'failed-load-remains-stopped', 'cleanup-owned-execution-stopped'], [row['phase'] for row in result['phases']])
        identifiers = [row['instance'] for row in result['phases'] if 'instance' in row]
        self.assertEqual(3, len(set(identifiers)))
        self.assertTrue(native.reports[0]['lifecycleSequenceCompleted'])
        self.assertFalse(native.reports[0]['deviceAcceptance'])
        self.assertEqual({}, native.active)

    def test_acknowledged_but_ignored_controls_and_missing_companion_cannot_pass(self):
        for mutation in ('ack-only', 'restart-ignored', 'stop-ignored',
                         'reload-ignored', 'missing-load-ignored', 'missing-companion'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(AssertionError):
                    native.run()
                self.assertFalse(native.reports[0]['lifecycleSequenceCompleted'])
                self.assertEqual('scripts.manager.close', native.actions[-1][0])

    def test_restart_that_leaves_the_previous_engine_running_fails(self):
        native = NativeBoundary('restart-leaks-old')
        with self.assertRaisesRegex(AssertionError, 'stopped instances'):
            native.run()
        self.assertFalse(native.reports[0]['lifecycleSequenceCompleted'])

    def test_restarted_engine_must_still_execute_at_the_final_observation(self):
        native = NativeBoundary('restarted-engine-dies')
        with self.assertRaisesRegex(AssertionError, 'restart-old-stopped-new-active'):
            native.run()
        self.assertFalse(native.reports[0]['lifecycleSequenceCompleted'])

    def test_one_already_sent_request_can_retire_within_a_bounded_quiet_window(self):
        native = NativeBoundary('one-late-request')
        native.run()
        self.assertTrue(native.reports[0]['lifecycleSequenceCompleted'])
        self.assertTrue(all(row['quietSeconds'] >= 3 for row in native.reports[0]['phases']
                            if 'quietSeconds' in row))

    def test_replayed_or_rewritten_observations_and_clock_failures_are_rejected(self):
        for mutation in ('replayed-observer', 'erased-history', 'clock-backwards', 'foreign-fixture-source'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(ValueError):
                    native.run()
                self.assertFalse(native.reports[0]['lifecycleSequenceCompleted'])

    def test_process_continuity_and_cleanup_errors_prevent_success(self):
        native = NativeBoundary('process-restarted')
        with self.assertRaisesRegex(AssertionError, 'process restarted'):
            native.run()
        native = NativeBoundary('close-error')
        with self.assertRaisesRegex(RuntimeError, 'close unavailable'):
            native.run()
        self.assertFalse(native.reports[0]['cleanupInputsDelivered'])
        self.assertFalse(native.reports[0]['lifecycleSequenceCompleted'])

    def test_partial_entry_preserves_original_error_and_only_closes_owned_ui(self):
        native = NativeBoundary('open-close-error')
        with self.assertRaisesRegex(RuntimeError, 'entry unavailable'):
            native.run()
        self.assertEqual('scripts.manager.close', native.actions[-1][0])
        self.assertFalse(native.reports[0]['ownedScriptCleanupEnabled'])
        self.assertFalse(any(name == 'scripts.stop' for name, _ in native.actions))

    def test_cleanup_acknowledgment_cannot_hide_a_new_executing_instance(self):
        native = NativeBoundary()
        original = native.invoke
        def invoke(name, arguments):
            if name == 'scripts.stop' and native.loads >= 2 and native.observe()['missingGets']:
                native.start()
                return {'performed': True}
            return original(name, arguments)
        native.invoke = invoke
        with self.assertRaises(AssertionError):
            native.run()
        self.assertFalse(native.reports[0]['cleanupObservedStopped'])
        self.assertFalse(native.reports[0]['lifecycleSequenceCompleted'])
        self.assertEqual('scripts.manager.close', native.actions[-1][0])

    def test_used_session_and_wrong_original_source_cannot_qualify(self):
        native = NativeBoundary()
        native.journal.delivered(native.nonce, 'client.js')
        with self.assertRaisesRegex(AssertionError, 'already used'):
            native.run()
        for url in ('file:///private/client.js', 'https://foreign.test/a.js',
                    native.source + '?expected=pass', native.source.replace('http:', 'ftp:')):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_operation_arguments('scripts.load-url', {'url': url})
        with self.assertRaises(ValueError):
            validate_operation_arguments('scripts.stop', {'url': native.missing})
        with self.assertRaises(ValueError):
            validate_operation_result('scripts.restart', {'performed': True, 'executing': True})


class ScriptManagementHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = fixture.ScriptServer(('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = ScriptFixtureClient(self.server.origin, self.server.control_token)
        self.registered = self.client.register()

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def test_actual_server_source_companion_receipts_and_private_control_boundaries(self):
        source = urlopen(self.registered['scriptUrl'], timeout=3).read()
        companion_url = self.registered['scriptUrl'].removesuffix('client.js') + 'companion.js'
        companion = urlopen(companion_url, timeout=3).read()
        config = json.loads(source.split(b' = ', 1)[1].split(b';\n', 1)[0])
        proof = json.loads(companion.split(b' = ', 1)[1][:-2])
        self.assertTrue(source.endswith(fixture.CLIENT.read_bytes()))
        self.assertNotIn(self.server.control_token.encode(), source + companion)
        observation_url = self.server.origin + f"/script-management/{self.registered['nonce']}/observation"
        with self.assertRaises(HTTPError) as error:
            urlopen(observation_url, timeout=3)
        self.assertEqual(403, error.exception.code)
        payload = {'token': config['receiptToken'], 'instance': '1' * 32,
                   'sequence': 0, 'kind': 'start', 'companionProof': proof}
        request = Request(config['eventsUrl'], data=json.dumps(payload).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=3) as response:
            self.assertEqual(200, response.status)
        with urlopen(request, timeout=3) as response:
            self.assertEqual(200, response.status)  # Duplicate acknowledgment adds no activity.
        state = self.client.observe()
        self.assertEqual(1, len(state['instances'][0]['events']))
        self.assertEqual(1, state['sourceGets'])
        self.assertEqual(1, state['companionGets'])
        self.assertNotIn(config['receiptToken'], json.dumps(state))
        self.assertNotIn(proof, json.dumps(state))
        with self.assertRaises(HTTPError) as error:
            urlopen(self.registered['missingUrl'], timeout=3)
        self.assertEqual(404, error.exception.code)
        self.assertEqual(1, self.client.observe()['missingGets'])

    def test_served_client_really_executes_and_posts_ordered_events_to_actual_http_server(self):
        # Only native Script/Uuid/XMLHttpRequest endpoints are supplied. The
        # served client, include body, real timers, transport and journal run.
        program = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');
(async () => {
    const sourceUrl = process.argv[1];
    const companionUrl = new URL('companion.js', sourceUrl).href;
    const source = await (await fetch(sourceUrl)).text();
    const companion = await (await fetch(companionUrl)).text();
    const timers = new Set();
    let ending, context, posted = 0;
    let done, failed;
    const finished = new Promise((resolve, reject) => { done = resolve; failed = reject; });
    const deadline = setTimeout(() => failed(new Error('diagnostic did not execute')), 4000);
    const Script = {
        resolvePath: value => new URL(value, sourceUrl).href,
        include: value => {
            assert.equal(value, companionUrl);
            vm.runInContext(companion, context);
        },
        setInterval: (callback, interval) => {
            const timer = setInterval(callback, interval); timers.add(timer); return timer;
        },
        clearInterval: timer => { clearInterval(timer); timers.delete(timer); },
        scriptEnding: {connect: callback => { ending = callback; }}
    };
    class XMLHttpRequest {
        open(method, url) { this.method = method; this.url = url; }
        setRequestHeader() {}
        send(body) {
            this.controller = new AbortController();
            fetch(this.url, {method: this.method, body, signal: this.controller.signal,
                            headers: {'Content-Type': 'application/json'}}).then(async response => {
                await response.arrayBuffer();
                this.status = response.status; this.readyState = 4;
                this.onreadystatechange();
                if (response.status !== 200) return failed(new Error('event rejected'));
                posted++;
                if (posted === 3) { ending(); done(); }
            }).catch(error => { if (error.name !== 'AbortError') failed(error); });
        }
        abort() { this.controller.abort(); }
    }
    context = vm.createContext({Script, Uuid: {generate: randomUUID}, XMLHttpRequest});
    try {
        vm.runInContext(source, context, {timeout: 1000});
        await finished;
        assert.equal(timers.size, 0);
        console.log(JSON.stringify({posted, remainingTimers: timers.size}));
    } finally {
        clearTimeout(deadline);
        for (const timer of timers) clearInterval(timer);
    }
})().catch(() => { console.error('host diagnostic execution failed'); process.exitCode = 1; });
'''
        result = subprocess.run(['node', '-e', program, self.registered['scriptUrl']],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({'posted': 3, 'remainingTimers': 0}, json.loads(result.stdout))
        state = self.client.observe()
        self.assertEqual(1, len(state['instances']))
        self.assertEqual([0, 1, 2], [event['sequence'] for event in state['instances'][0]['events']])
        self.assertEqual(1, state['sourceGets'])
        self.assertEqual(1, state['companionGets'])

    def test_receipt_mutations_do_not_enter_execution_history(self):
        nonce = self.registered['nonce']
        source = self.server.journal.source(nonce, 'client.js', self.server.origin)
        config = json.loads(source.split(b' = ', 1)[1].split(b';\n', 1)[0])
        companion = self.server.journal.source(nonce, 'companion.js', self.server.origin)
        proof = json.loads(companion.split(b' = ', 1)[1][:-2])
        good = {'token': config['receiptToken'], 'instance': '1' * 32,
                'sequence': 0, 'kind': 'start', 'companionProof': proof}
        for update in ({'token': '0' * 64}, {'companionProof': 'wrong'},
                       {'sequence': True}, {'sequence': 1}, {'kind': 'tick'}, {'accepted': True}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.server.journal.receive(nonce, good | update)
        self.assertEqual([], self.client.observe()['instances'])

    def test_real_adapter_subprocesses_cannot_read_private_observer_control_token(self):
        from adapter_client import invoke
        import run as runner
        import verify_adapter as verifier
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = root / 'adapter.py'
            adapter.write_text('import json,os\nprint(json.dumps({"visible": "OVERTE_E2E_SCRIPTS_CONTROL_TOKEN" in os.environ}))\n')
            manifest = root / 'adapter.json'
            manifest.write_text(json.dumps({'schemaVersion': 1, 'command': [str(adapter)]}))
            with patch.dict(os.environ, {'OVERTE_E2E_SCRIPTS_CONTROL_TOKEN': self.server.control_token}):
                self.assertFalse(invoke(manifest, 'synthetic-target', 'scripts.manager.open')['visible'])
                self.assertFalse(runner.adapter_call([sys.executable, str(adapter)], 'describe',
                    'synthetic-target', environment=os.environ.copy())['visible'])
                self.assertFalse(verifier.call([sys.executable, str(adapter)], 'discover')['visible'])

    def test_execution_profile_rejects_missing_private_fixture_before_target_discovery(self):
        from acceptance_policy import load_policy
        from execution_plan import compile_plan, load_profiles
        catalog = DEVICE / 'catalog.json'
        policy = load_policy(DEVICE / 'acceptance-policy.json', catalog)
        profiles = load_profiles(DEVICE / 'execution-profiles.json', catalog)
        required = {'OVERTE_E2E_SCRIPTS_CONTROL_TOKEN', 'OVERTE_E2E_SCRIPTS_FIXTURE_URL'}
        for keys in (set(), {'OVERTE_E2E_SCRIPTS_FIXTURE_URL'}, required):
            plan = compile_plan(policy, catalog, profiles, 'mock', ['scripts-management-parity'],
                                keys, False, set(), 'external')
            self.assertEqual(keys == required, plan['ready'])
            self.assertEqual(sorted(required - keys), plan['missingInputs'])
            self.assertEqual(['launch-smoke', 'scripts-management'], plan['suites'][0]['modules'])

    def test_fixture_cli_writes_private_environment_without_printing_its_control_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready = Path(temporary) / 'environment.json'
            process = subprocess.Popen([sys.executable, str(DEVICE / 'fixture/script_management.py'),
                '--ready-file', str(ready)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.is_file(), 'owned fixture did not become ready')
                from pipeline import load_environment
                environment = load_environment(ready)
                self.assertEqual(0o600, ready.stat().st_mode & 0o777)
                token = environment['OVERTE_E2E_SCRIPTS_CONTROL_TOKEN']
                controller = ScriptFixtureClient(environment['OVERTE_E2E_SCRIPTS_FIXTURE_URL'], token)
                controller.register()
                self.assertEqual([], controller.observe()['instances'])
                controller.close()
            finally:
                process.terminate()
                output, error = process.communicate(timeout=5)
            self.assertFalse(token in output + error, 'private fixture control token reached console output')


if __name__ == '__main__':
    unittest.main()
