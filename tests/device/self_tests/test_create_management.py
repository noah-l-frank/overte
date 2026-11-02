"""Counterfactual normal Create journeys with real journal/protocol validation."""
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
sys.path.insert(0, str(DEVICE / 'fixture'))
from create_fixture_client import CreateFixtureClient
from create_journey import create_journey, INITIAL, EDITED
from create_observation import PREFIX
from contracts import validate_operation_arguments, validate_operation_result

spec = importlib.util.spec_from_file_location('owned_create_fixture', DEVICE / 'fixture/create_management.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class NativeBoundary:
    """Replace only ordinary UI, native entity reads, time and session endpoints."""
    def __init__(self, mutation=''):
        self.now = 0.0
        self.journal = fixture.CreateJournal(lambda: self.now)
        self.nonce = self.journal.create()
        self.prefix = PREFIX + self.nonce + '_'
        self.origin = 'http://reference.test:18080'
        self.base = self.origin + f'/create/{self.nonce}/'
        source = self.journal.resource(self.nonce, 'observer.js', self.origin)
        self.config = json.loads(source.split(b' = ', 1)[1].split(b';\n', 1)[0])
        self.mutation = mutation
        self.world = []
        self.history = [[]]
        self.cursor = 0
        self.active = False
        self.next_tick = None
        self.sequence = 0
        self.instance = '1' * 32
        self.next_id = 0
        self.undo_count = self.redo_count = 0
        self.actions, self.reports = [], []
        self.old_read = None
        if mutation == 'preexisting':
            self.world = [self.cube(self.prefix + 'cube', INITIAL)]
            self.history = [copy.deepcopy(self.world)]

    def new_id(self):
        self.next_id += 1
        return f'{self.next_id:032x}'

    def cube(self, name, properties):
        return {'id': self.new_id(), 'name': name,
                'type': 'Box' if self.mutation == 'legacy-box' else 'Shape',
                'shape': 'Sphere' if self.mutation == 'wrong-shape' else 'Cube',
                'host': 'avatar', 'ownedByCurrentAvatar': self.mutation != 'wrong-owner',
                'parentId': None, 'hasExternalParent': self.mutation == 'external-parent',
                **copy.deepcopy(properties)}

    def commit_world(self, rows):
        self.world = sorted(copy.deepcopy(rows), key=lambda row: (row['name'], row['id']))
        self.history = self.history[:self.cursor + 1] + [copy.deepcopy(self.world)]
        self.cursor += 1

    def emit(self):
        if self.mutation == 'observer-freezes' and self.sequence:
            return
        payload = {'token': self.config['receiptToken'], 'instance': self.instance,
            'sequence': self.sequence, 'complete': self.mutation != 'incomplete-observation',
            'error': 'entity-read-error' if self.mutation == 'incomplete-observation' else '',
            'queriedEntityCount': len(self.world),
            'entities': [] if self.mutation == 'incomplete-observation' else copy.deepcopy(self.world)}
        self.journal.receive(self.nonce, payload)
        self.sequence += 1

    def invoke(self, name, arguments):
        self.actions.append((name, copy.deepcopy(arguments)))
        if name == 'create.reference.open':
            if self.mutation == 'open-close-error':
                raise RuntimeError('native entry unavailable')
            self.journal.delivered(self.nonce, 'observer.js')
            self.active = True
            self.emit()
            self.next_tick = self.now + 0.25
        elif name == 'create.reference.close':
            self.active = False
            if self.mutation in {'open-close-error', 'close-error'}:
                raise RuntimeError('native close unavailable')
        elif name == 'create.cube':
            if self.mutation != 'cube-ignored':
                self.commit_world([self.cube(arguments['name'], arguments['properties'])])
        elif name == 'create.update':
            if self.mutation != 'edit-ignored':
                rows = copy.deepcopy(self.world)
                for row in rows:
                    if row['name'] == arguments['name']:
                        row.update(copy.deepcopy(arguments['properties']))
                self.commit_world(rows)
        elif name == 'create.delete':
            if self.mutation == 'cleanup-delete-error' and len(arguments['names']) > 1:
                raise RuntimeError('native owned cleanup unavailable')
            if self.mutation != 'delete-ignored':
                self.commit_world([row for row in self.world if row['name'] not in arguments['names']])
        elif name == 'create.undo':
            self.undo_count += 1
            if self.mutation != 'undo-ignored' and not (self.mutation == 'undo-import-ignored' and self.undo_count == 3):
                self.cursor = max(0, self.cursor - 1)
                self.world = copy.deepcopy(self.history[self.cursor])
        elif name == 'create.redo':
            self.redo_count += 1
            if self.mutation != 'redo-ignored':
                self.cursor = min(len(self.history) - 1, self.cursor + 1)
                self.world = copy.deepcopy(self.history[self.cursor])
        elif name == 'create.import':
            if arguments['url'].endswith('/missing.json'):
                if self.mutation != 'missing-import-ignored':
                    self.journal.delivered(self.nonce, 'missing.json')
            elif self.mutation != 'import-ignored':
                self.journal.delivered(self.nonce, 'entities.json')
                data = json.loads(self.journal.resource(self.nonce, 'entities.json', self.origin))
                imported = []
                mapping = {row['id']: self.new_id() for row in data['Entities']}
                for source in data['Entities']:
                    row = self.cube(source['name'], {key: source[key] for key in ('color', 'dimensions')})
                    row['id'] = mapping[source['id']]
                    row['parentId'] = mapping.get(source.get('parentID'))
                    if self.mutation == 'broken-import-parent':
                        row['parentId'] = None
                    if self.mutation == 'cyclic-import-parent' and source['name'].endswith('_import-parent'):
                        row['parentId'] = next(identifier for old_id, identifier in mapping.items()
                                               if old_id != source['id'])
                    imported.append(row)
                self.commit_world(imported)
        return {'performed': True}

    def sleep(self, seconds):
        if self.mutation == 'clock-backwards':
            self.now -= seconds
            return
        end = self.now + seconds
        while self.active and self.next_tick <= end:
            self.now = self.next_tick
            self.emit()
            self.next_tick += 0.25
        self.now = end

    def observe(self):
        value = self.journal.observe(self.nonce)
        if self.mutation == 'replayed-observer':
            if self.old_read is None:
                self.old_read = copy.deepcopy(value)
            return copy.deepcopy(self.old_read)
        if self.mutation == 'foreign-source':
            value['sourceSha256'] = '0' * 64
        if self.mutation == 'changed-earlier-frame' and self.cursor:
            value['frame']['entities'] = copy.deepcopy(self.world)
        return value

    def continuity(self, _phase):
        if self.mutation == 'process-restarted' and self.cursor:
            raise AssertionError('application process restarted')

    def run(self):
        return create_journey(self.base + 'observer.js', self.base + 'entities.json', self.base + 'missing.json',
            invoke=self.invoke, observe=self.observe, assert_session=self.continuity,
            monotonic=lambda: self.now, sleep=self.sleep, report=self.reports.append)


class CreateJourneyTests(unittest.TestCase):
    def test_real_state_is_required_for_cube_edit_history_delete_and_parent_child_import(self):
        native = NativeBoundary()
        result = native.run()
        self.assertEqual(['baseline-live-empty', 'create-cube', 'edit-color-and-dimensions',
            'undo-edit', 'redo-edit', 'delete', 'undo-delete', 'redo-delete',
            'json-import-parent-and-child', 'undo-import', 'redo-import',
            'remove-owned-import', 'failed-import-remains-empty'], [row['phase'] for row in result['phases']])
        self.assertTrue(native.reports[0]['sequenceCompleted'])
        self.assertTrue(all(row['stableNativeSamples'] >= 3 for row in result['phases']))
        self.assertFalse(native.reports[0]['deviceAcceptance'])
        self.assertEqual([], native.world)
        self.assertFalse(native.active)

    def test_native_legacy_box_serialization_still_requires_actual_cube_semantics(self):
        native = NativeBoundary('legacy-box')
        native.run()
        self.assertTrue(native.reports[0]['sequenceCompleted'])
        for mutation in ('wrong-owner', 'wrong-shape', 'external-parent'):
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                NativeBoundary(mutation).run()

    def test_acknowledged_but_ignored_ui_operations_and_broken_parenting_cannot_pass(self):
        for mutation in ('cube-ignored', 'edit-ignored', 'delete-ignored', 'undo-ignored',
                         'redo-ignored', 'import-ignored', 'undo-import-ignored',
                         'missing-import-ignored', 'broken-import-parent', 'cyclic-import-parent'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(AssertionError):
                    native.run()
                self.assertFalse(native.reports[0]['sequenceCompleted'])
                self.assertEqual('create.reference.close', native.actions[-1][0])

    def test_empty_incomplete_frozen_or_replayed_observers_do_not_prove_absence(self):
        for mutation in ('incomplete-observation', 'replayed-observer', 'foreign-source',
                         'changed-earlier-frame', 'clock-backwards'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(ValueError):
                    native.run()
                self.assertFalse(native.reports[0]['sequenceCompleted'])
        native = NativeBoundary('observer-freezes')
        with self.assertRaises(AssertionError):
            native.run()
        self.assertFalse(native.reports[0]['sequenceCompleted'])

    def test_preexisting_objects_never_enable_destructive_cleanup(self):
        native = NativeBoundary('preexisting')
        with self.assertRaises(AssertionError):
            native.run()
        self.assertFalse(native.reports[0]['ownedObjectCleanupEnabled'])
        self.assertFalse(any(name == 'create.delete' for name, _ in native.actions))
        self.assertEqual(1, len(native.world))

    def test_process_replacement_and_cleanup_failures_prevent_success(self):
        native = NativeBoundary('process-restarted')
        with self.assertRaisesRegex(AssertionError, 'process restarted'):
            native.run()
        for mutation in ('close-error', 'cleanup-delete-error'):
            with self.subTest(mutation=mutation):
                native = NativeBoundary(mutation)
                with self.assertRaises(RuntimeError):
                    native.run()
                self.assertFalse(native.reports[0]['cleanupInputsDelivered'])
                self.assertFalse(native.reports[0]['sequenceCompleted'])

    def test_partial_entry_keeps_primary_error_and_closes_only_its_observer(self):
        native = NativeBoundary('open-close-error')
        with self.assertRaisesRegex(RuntimeError, 'entry unavailable'):
            native.run()
        self.assertFalse(native.reports[0]['ownedObjectCleanupEnabled'])
        self.assertEqual('create.reference.close', native.actions[-1][0])

    def test_closed_contract_rejects_foreign_names_values_resources_and_verdicts(self):
        native = NativeBoundary()
        good = {'name': native.prefix + 'cube', 'properties': INITIAL}
        self.assertEqual(good, validate_operation_arguments('create.cube', good))
        for update in ({'name': 'unrelated-user-entity'}, {'properties': {'color': {}}},
                       {'properties': {'color': {'red': True, 'green': 0, 'blue': 0}, 'dimensions': INITIAL['dimensions']}},
                       {'properties': {'color': INITIAL['color'], 'dimensions': {'x': float('nan'), 'y': 1, 'z': 1}}}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_operation_arguments('create.cube', good | update)
        with self.assertRaises(ValueError):
            validate_operation_result('create.cube', {'performed': True, 'entityCreated': True})
        with self.assertRaises(ValueError):
            validate_operation_arguments('create.reference.open', {'scriptUrl': 'file:///private/observer.js'})


class CreateFixtureHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = fixture.CreateServer(('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = CreateFixtureClient(self.server.origin, self.server.control_token)
        self.registered = self.client.register()

    def tearDown(self):
        self.client.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def test_real_http_observer_and_json_resources_are_bound_without_control_credentials(self):
        with urlopen(self.registered['observerUrl'], timeout=3) as response:
            source = response.read()
        self.assertTrue(source.endswith(fixture.OBSERVER.read_bytes()))
        self.assertFalse(self.server.control_token.encode() in source)
        with urlopen(self.registered['importUrl'], timeout=3) as response:
            data = json.load(response)
        self.assertEqual(2, len(data['Entities']))
        self.assertEqual(data['Entities'][0]['id'], data['Entities'][1]['parentID'])
        self.assertTrue(all(row['name'].startswith(self.registered['prefix']) for row in data['Entities']))
        with self.assertRaises(HTTPError) as error:
            urlopen(self.registered['missingUrl'], timeout=3)
        self.assertEqual(404, error.exception.code)
        error.exception.close()
        state = self.client.observe()
        self.assertEqual((1, 1, 1), (state['sourceGets'], state['importGets'], state['missingGets']))
        self.assertIsNone(state['frame'])
        with self.assertRaises(HTTPError) as error:
            urlopen(self.server.origin + f"/create/{self.registered['nonce']}/observation", timeout=3)
        self.assertEqual(403, error.exception.code)
        error.exception.close()

    def test_private_control_token_never_reaches_real_adapter_subprocesses(self):
        from adapter_client import invoke
        import run as runner
        import verify_adapter as verifier
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            adapter = root / 'adapter.py'
            adapter.write_text('import json,os\nprint(json.dumps({"visible": "OVERTE_E2E_CREATE_CONTROL_TOKEN" in os.environ}))\n')
            manifest = root / 'adapter.json'
            manifest.write_text(json.dumps({'schemaVersion': 1, 'command': [str(adapter)]}))
            with patch.dict(os.environ, {'OVERTE_E2E_CREATE_CONTROL_TOKEN': self.server.control_token}):
                self.assertFalse(invoke(manifest, 'synthetic-target', 'create.undo')['visible'])
                self.assertFalse(runner.adapter_call([sys.executable, str(adapter)], 'describe',
                    'synthetic-target', environment=os.environ.copy())['visible'])
                self.assertFalse(verifier.call([sys.executable, str(adapter)], 'discover')['visible'])

    def test_execution_plan_requires_private_create_inputs_and_a_controlled_scene(self):
        from acceptance_policy import load_policy
        from execution_plan import compile_plan, load_profiles
        catalog = DEVICE / 'catalog.json'
        policy = load_policy(DEVICE / 'acceptance-policy.json', catalog)
        profiles = load_profiles(DEVICE / 'execution-profiles.json', catalog)
        required = {'OVERTE_E2E_CREATE_CONTROL_TOKEN', 'OVERTE_E2E_CREATE_FIXTURE_URL'}
        for provider, keys, missing in (
                ('auto', set(), required),
                ('auto', {'OVERTE_E2E_CREATE_FIXTURE_URL'}, {'OVERTE_E2E_CREATE_CONTROL_TOKEN'}),
                ('auto', required, set()),
                ('external', required, {'OVERTE_E2E_SCENE_URL'}),
                ('external', required | {'OVERTE_E2E_SCENE_URL'}, set())):
            with self.subTest(provider=provider, keys=keys):
                plan = compile_plan(policy, catalog, profiles, 'mock', ['create-management-parity'],
                                    keys, False, set(), provider)
                self.assertEqual(not missing, plan['ready'])
                self.assertEqual(sorted(missing), plan['missingInputs'])
                self.assertEqual('scene', plan['fixture'])
                self.assertEqual(['launch-smoke', 'create-management'], plan['suites'][0]['modules'])

    def test_fixture_cli_writes_private_environment_without_console_secrets(self):
        token = None
        with tempfile.TemporaryDirectory() as temporary:
            ready = Path(temporary) / 'environment.json'
            process = subprocess.Popen([sys.executable, str(DEVICE / 'fixture/create_management.py'),
                '--ready-file', str(ready)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.is_file(), 'owned Create fixture did not become ready')
                from pipeline import load_environment
                environment = load_environment(ready)
                self.assertEqual(0o600, ready.stat().st_mode & 0o777)
                token = environment['OVERTE_E2E_CREATE_CONTROL_TOKEN']
                client = CreateFixtureClient(environment['OVERTE_E2E_CREATE_FIXTURE_URL'], token)
                client.register()
                self.assertIsNone(client.observe()['frame'])
                client.close()
            finally:
                process.terminate()
                output, error = process.communicate(timeout=5)
            self.assertIsNotNone(token)
            self.assertFalse(token in output + error, 'private Create control token reached console output')

    def test_actual_served_javascript_posts_native_reads_to_the_real_http_journal(self):
        program = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');
(async function () {
    const source = await (await fetch(process.argv[1])).text();
    let ending, context, count = 0, color = 35;
    const timers = new Set(), me = randomUUID(), id = randomUUID();
    let finish;
    const finished = new Promise(resolve => { finish = resolve; });
    const deadline = setTimeout(() => { throw Error('read-only diagnostic did not complete'); }, 6000);
    const Script = {
        setInterval(callback, milliseconds) { const t = setInterval(callback, milliseconds); timers.add(t); return t; },
        clearInterval(timer) { clearInterval(timer); timers.delete(timer); },
        scriptEnding: {connect(callback) { ending = callback; }}
    };
    const Entities = {
        findEntities() { return [id]; },
        getEntityProperties() { return {name: context.OVERTE_CREATE_SESSION.prefix + 'cube',
            type: 'Box', shape: 'Cube', dimensions: {x: 0.5, y: 0.6, z: 0.7},
            color: {red: color, green: 125, blue: 220}, entityHostType: 'avatar',
            owningAvatarID: me, parentID: '{00000000-0000-0000-0000-000000000000}'}; },
        addEntity() { throw Error('diagnostic must never mutate entities'); },
        editEntity() { throw Error('diagnostic must never mutate entities'); },
        deleteEntity() { throw Error('diagnostic must never mutate entities'); }
    };
    class XMLHttpRequest {
        constructor() { this.headers = {}; this.controller = new AbortController(); }
        open(method, url) { this.method = method; this.url = url; }
        setRequestHeader(key, value) { this.headers[key] = value; }
        send(body) {
            fetch(this.url, {method: this.method, headers: this.headers, body, signal: this.controller.signal})
                .then(response => {
                    assert.equal(response.status, 200);
                    this.status = response.status; this.readyState = 4;
                    this.onreadystatechange(); color = 220; count += 1;
                    if (count === 2) { ending(); finish(); }
                }).catch(() => { process.exitCode = 1; ending(); finish(); });
        }
        abort() { this.controller.abort(); }
    }
    context = vm.createContext({Script, Entities, MyAvatar: {position: {x: 0, y: 0, z: 0},
        sessionUUID: me, SELF_ID: '{00000000-0000-0000-0000-000000000001}'},
        Uuid: {generate: randomUUID}, XMLHttpRequest});
    try {
        vm.runInContext(source, context, {timeout: 1000});
        await finished;
        assert.equal(timers.size, 0);
        console.log(JSON.stringify({posted: count, remainingTimers: timers.size}));
    } finally {
        clearTimeout(deadline);
        for (const timer of timers) clearInterval(timer);
    }
})().catch(() => { console.error('host read-only diagnostic execution failed'); process.exitCode = 1; });
'''
        result = subprocess.run(['node', '-e', program, self.registered['observerUrl']],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({'posted': 2, 'remainingTimers': 0}, json.loads(result.stdout))
        state = self.client.observe()
        self.assertEqual(1, state['sourceGets'])
        self.assertEqual(1, state['frame']['sequence'])
        self.assertEqual(220, state['frame']['entities'][0]['color']['red'])
        self.assertTrue(state['frame']['entities'][0]['ownedByCurrentAvatar'])

    def test_changed_retries_skipped_frames_and_engine_replacement_cannot_rewrite_native_history(self):
        source = urlopen(self.registered['observerUrl'], timeout=3)
        with source:
            config = json.loads(source.read().split(b' = ', 1)[1].split(b';\n', 1)[0])
        payload = {'token': config['receiptToken'], 'instance': '1' * 32, 'sequence': 0,
                   'complete': True, 'error': '', 'queriedEntityCount': 0, 'entities': []}

        def post(value):
            request = Request(config['eventsUrl'], data=json.dumps(value).encode(),
                              headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=3) as response:
                return response.status

        for update in ({'token': 'wrong'}, {'sequence': True}, {'sequence': 1},
                       {'complete': False}, {'accepted': True}):
            with self.subTest(update=update), self.assertRaises(HTTPError) as error:
                post(payload | update)
            self.assertEqual(400, error.exception.code)
            error.exception.close()
        self.assertIsNone(self.client.observe()['frame'])
        self.assertEqual(200, post(payload))
        original = self.client.observe()['frame']
        self.assertEqual(200, post(payload))  # A genuinely lost ACK may retry.
        for update in ({'queriedEntityCount': 1}, {'sequence': 2},
                       {'sequence': 1, 'instance': '2' * 32}):
            with self.subTest(update=update), self.assertRaises(HTTPError) as error:
                post(payload | update)
            self.assertEqual(400, error.exception.code)
            error.exception.close()
        self.assertEqual(original, self.client.observe()['frame'])


if __name__ == '__main__':
    unittest.main()
