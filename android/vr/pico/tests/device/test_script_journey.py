"""Pico wrapper and shared complete Script flow, with synthetic native sources.

SDK/Qt/OpenXR/process boundaries are explicit simulations. Private original
files and short-lived owned loopback HTTP responses are real. No compiler,
device discovery, ADB/Appium service, installation or native client is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen
import uuid

import test_normal_scripts as components

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tests/device'))
from adapters.pico4 import script_journey as pico
from adapters.pico4 import binding
from adapters.script_journey.feature import ScriptFeature, ScriptFixtureReader
from adapters.script_journey.history import unpack
from adapters.script_journey.files import validate as validate_ui
from adapters.script_journey.lock import ScriptSourceLock
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_script_observation import NativeScriptObservation
from adapters.native_script_files import NativeScriptFiles, originals
from adapters.script_restart_handoff import ScriptRestartHandoff
from adapters.restart_inputs import RestartInputs
from adapters.token_script_file_ui import TokenScriptFilePicker, file_url
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.scenarios import SCENARIOS, VERSION
from self_tests.test_native_script_files import Boundary as FileStorage
from self_tests.test_native_script_observation import Boundary as Execution, code_source, effect_source
from self_tests.test_native_feature_observation import Boundary as Lifecycle
from self_tests.test_native_process_presence import Boundary as Presence
from self_tests.test_native_script_loads import history, event
from self_tests.test_native_script_membership import membership_source, manager
from self_tests.test_token_script_file_ui import NativeBoundary as Picker
from self_tests.test_script_ui_inventory import inventory, picker
from self_tests.test_script_manager_status import observed

RUN = 'a' * 32


class PicoScriptJourneyTests(unittest.TestCase):
    def setUp(self):
        self.f = components.PicoNormalScriptsTests()
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.original, self.native, self.qt = self.f.instance, self.f.native, self.f.qt
        self.target = self.native.target
        self.clock = 0.0; self.birth = 'b' * 32; self.load_birth = 'c' * 32
        self.launches = self.activations = 1; self.backgrounds = 0
        self.events = []; self.engine = None; self.retired = []; self.revision = 0
        self.engine_number = 0; self.status = ''; self.loaded_epoch = 0; self.selected = None
        self.ui_sequence = 0; self.ui_packet = None; self.ui_fault = ''; self.ignored = False
        self.input_commands = []; self.lifecycle_inputs = []; self.openxr_identity = self.native.identity
        self.lost_launch = False
        self.storage = FileStorage(self.f.fixture.fixture.root)
        self.f.file_ui = Picker(self.storage.root)
        self.file_ui = self.f.file_ui
        self.execution = Execution(); self.execution.mutate = self.execution_packet
        self.lifecycle = Lifecycle(); self.lifecycle.mutate = self.lifecycle_packet
        self.presence = Presence(pid=123, epoch_ms=self.epoch)
        self.presence.presence = 'absent'
        self.presence.edit = lambda value: value.update(instance=self.birth, processId=self.pid())
        self.storage.mutate = lambda value: value.update(instance=self.birth, processId=self.pid(),
            requestedEpochMs=self.epoch(), capturedEpochMs=self.epoch())
        self.fixture = make_server(secrets.token_hex(32), secrets.token_hex(32), adapter_token=secrets.token_hex(32))
        self.fixture.script_resources.clock_ms = self.epoch; self.fixture.journal.clock = self.epoch
        self.worker = threading.Thread(target=self.fixture.serve_forever, daemon=True); self.worker.start()
        self.addCleanup(self.stop_fixture)
        self.url = 'http://127.0.0.1:' + str(self.fixture.server_port) + '/feature-fixture/v1'
        self.reader = Client(self.url, self.fixture.reader_token)
        with patch('feature_journeys.witness.secrets.token_hex', return_value=RUN):
            self.run, self.fixture_url = self.reader.register('scripts')
        config = self.f.fixture.state_root / 'adapter-access.json'
        config.write_text(json.dumps(dict(fixtureAdapterAccessVersion=1, fixtureUrl=self.url,
            adapterToken=self.fixture.adapter_token))); config.chmod(0o600)
        enabled = patch.dict(os.environ, {'OVERTE_PICO_FEATURE_SCRIPTS':'1',
            'OVERTE_PICO_FEATURE_FIXTURE_CONFIG':str(config), 'OVERTE_E2E_FEATURE_FIXTURE_URL':self.url})
        enabled.start(); self.addCleanup(enabled.stop)
        self.facade = pico.PicoScriptJourney(self.original)
        self.primary = ScriptFeature(self.facade, self.target,
            ScriptFixtureReader(self.reader, RUN, epoch_ms=self.epoch), monotonic=lambda:self.clock, sleep=self.sleep)
        self.actor = ScriptFeature(self.facade, self.target,
            ScriptFixtureReader(Client(self.url, self.fixture.actor_token), RUN, epoch_ms=self.epoch),
            role='actor', monotonic=lambda:self.clock, sleep=self.sleep)
        self.ticket_number = 0
        old_write, old_read, old_shell = self.native.write_debug_app_file, self.native.read_debug_app_file, self.native.shell
        real_run = subprocess.run
        verified = self.original._candidate()
        original_observe = self.qt.observe
        def service(after):
            packet, epoch = original_observe(after)
            packet['instance'] = 'f'*32 if self.pid() == 123 else '8'*32
            return packet, epoch
        def write(target, package, path, raw):
            command = json.loads(raw)
            action = command.get('action')
            if path == pico.COMMAND_FILE:
                self.ui_sequence += 1
                self.ui_packet = self.passive_ui(command)
                return
            if action == 'feature-script-files': return self.storage.send(command)
            if action == 'feature-script-observe': return self.execution.send(command)
            if action == 'feature-native-observe': return self.lifecycle.send(command)
            if action == 'feature-process-presence':
                self.presence.pid = self.pid(); return self.presence.send(command)
            if path.endswith('/navigation-ui-command.json'):
                self.input_commands.append(deepcopy(command))
                if self.ignored:
                    # Ignore the actual input, but retain an ordinary consumed
                    # transport ACK. Independent sources must still reject it.
                    self.native.sequence += 1
                    self.native.status = dict(schemaVersion=1, bridgeId=self.native.bridge_id,
                        commandId=command['commandId'], sequence=command['sequence'], performed=True,
                        error='', processId=self.pid(), updatedEpochMs=self.epoch())
                    return
            if path.endswith('/navigation-ui-command.json') and command.get('controlId') == 'scripts.from-file':
                self.file_ui.chosen = []
            result = old_write(target, package, path, raw)
            self.native.status['processId'] = self.pid()
            if path.endswith('/navigation-ui-command.json'):
                control = command['controlId']
                if control == 'script-file.confirm' and self.file_ui.accepted:
                    self.start_script(self.file_ui.accepted[-1])
                elif control.startswith('scripts.stop.'):
                    self.stop_script()
                elif control == 'scripts.url.submit':
                    url = self.qt.text
                    try: urlopen(url, timeout=2).close()
                    except HTTPError as error: self.assertEqual(404, error.code); error.read(); error.close()
                    self.events.append(event(len(self.events)+1, url=url, callbackEpochMs=self.epoch(), managerInstance='9'*32))
                    self.status = 'Failed to load ' + url + ': NotFound'
            return result
        def read(target, package, path, **kwargs):
            if path == components.adapter.ANDROID_CONTROL_MARKER:
                return json.dumps(components.adapter.ANDROID_CONTROL_CONTRACT | {'processId': self.pid()})
            if path.endswith('/script-file-ui.json'): return json.dumps(self.ui_packet)
            if path.endswith('/feature-script-files.json'): return self.storage.read()
            if path.endswith('/feature-script-observation.json'): return self.execution.original()
            if path.endswith('/feature-native-observation.json'): return self.lifecycle.original()
            if path.endswith('/feature-process-presence.json'): return self.presence.original()
            return old_read(target, package, path, **kwargs)
        def shell(target, *args, **kwargs):
            if args == ('am','force-stop','org.overte.pico'):
                self.lifecycle_inputs.append('stop'); self.native.running = False; self.backgrounds += 1
                return ''
            if args[:4] == ('am','start','-W','-n'):
                self.lifecycle_inputs.append('launch'); self.restart()
                if self.lost_launch: raise RuntimeError('synthetic lost ordinary launch receipt')
                return ''
            return old_shell(target, *args, **kwargs)
        def query(argv, **kwargs):
            if argv[0] != 'synthetic-adb': return real_run(argv, **kwargs)
            self.assertEqual(['synthetic-adb','-s',self.target,'exec-out','run-as','org.overte.pico',
                '/system/bin/ps','-p','123','-o','PID'], argv)
            present = self.native.running and self.pid() == 123
            return subprocess.CompletedProcess(argv, 0 if present else 1, b'PID\n123\n' if present else b'PID\n', b'')
        def controller(identity, operation, values):
            self.assertEqual(identity, self.native.identity)
            self.assertIn(operation, ('tablet.open', 'tablet.close')); self.assertEqual({'holdMilliseconds':1000}, values)
            self.native.controllers.append(operation)
            self.native.opened = operation == 'tablet.open'
            if not self.native.opened: self.qt.page = 'home'
            return {'performed': True}
        def require(identity): self.assertEqual(identity, self.openxr_identity)
        def begin(identity): self.openxr_identity = identity
        def discard(): self.openxr_identity = None
        # Candidate tooling is a declared synthetic verification boundary here;
        # actual original-byte/installed-hash and target guards stay exercised.
        globals_ = type(self.original)._script_restart_prepare.__wrapped__.__globals__
        mocks = [patch('adapters.common.time.time',side_effect=lambda:self.epoch()/1000),
            patch.object(pico,'ScriptFeature',partial(ScriptFeature,monotonic=lambda:self.clock,sleep=self.sleep)),
            patch.object(self.native,'write_debug_app_file',side_effect=write),
            patch.object(self.native,'read_debug_app_file',side_effect=read),
            patch.object(self.native,'epoch_milliseconds',side_effect=lambda *_:self.epoch()),
            patch.object(self.native,'shell',side_effect=shell),
            patch.object(self.native,'stage',side_effect=controller),
            patch.object(self.native,'command',['synthetic-adb'],create=True),
            patch.object(self.native,'require_process_identity',side_effect=require),
            patch.object(self.native,'begin',side_effect=begin,create=True),
            patch.object(self.native,'discard_local_state',side_effect=discard),
            patch.object(self.native,'is_unbound',side_effect=lambda:self.openxr_identity is None,create=True),
            patch('adapters.android_process_query.subprocess.run',side_effect=query),
            patch.object(globals_['verifier'],'verify_candidate',return_value=verified),
            patch.object(self.qt,'observe',side_effect=service),
            patch.object(self.qt,'sleep',side_effect=self.sleep),
            patch.object(self.file_ui,'sleep',side_effect=self.sleep),
            patch.dict(globals_, NativeFeatureObservation=partial(NativeFeatureObservation,monotonic=lambda:self.clock,sleep=self.sleep),
                NativeScriptObservation=partial(NativeScriptObservation,monotonic=lambda:self.clock,sleep=self.sleep),
                NativeScriptFiles=partial(NativeScriptFiles,monotonic=lambda:self.clock,sleep=self.sleep),
                TokenScriptFilePicker=partial(TokenScriptFilePicker,monotonic=lambda:self.clock,sleep=self.sleep),
                ScriptRestartHandoff=partial(ScriptRestartHandoff,monotonic=lambda:self.clock,sleep=self.sleep),
                RestartInputs=partial(RestartInputs,monotonic=lambda:self.clock))]
        for boundary in mocks: boundary.start(); self.addCleanup(boundary.stop)
        self.native.snapshot_mutation = lambda packet: packet.update(processId=self.pid())

    def epoch(self): return 20000 + round(self.clock * 1000)
    def pid(self): return int(self.native.identity.split(':')[0])
    def sleep(self, seconds):
        self.clock += seconds; self.qt.clock = self.file_ui.clock = self.clock
    def stop_fixture(self):
        self.fixture.shutdown(); self.fixture.server_close(); self.worker.join(2)
    def lifecycle_packet(self, packet):
        packet.update(instance=self.birth, processId=self.pid(), requestedEpochMs=self.epoch(), capturedEpochMs=self.epoch())
        packet['animationFence']['requestedEpochMs'] = self.epoch()
        packet['animation']['capturedEpochMs'] = self.epoch()
        packet['animation']['clip']['evaluatedEpochMs'] = self.epoch()
        packet['lifecycle'] = dict(launches=self.launches, activations=self.activations, backgrounds=self.backgrounds)
    def execution_packet(self, packet):
        packet.update(instance=self.birth, processId=self.pid(), requestedEpochMs=self.epoch(), capturedEpochMs=self.epoch())
        packet['source']['engines'] = [] if self.engine is None else [deepcopy(self.engine)]
        if self.engine is not None:
            code_source(packet, originals(RUN)[self.selected].decode(), submitted=self.loaded_epoch)
            effect_source(packet, ticks=2+round((self.epoch()-self.loaded_epoch)/250), edited=self.epoch()*1000)
            effect = packet['source']['effects']['entities'][0]
            effect['id'] = self.entity; effect['name'] = 'e2e-'+RUN+'-script'
            data = json.loads(effect['userData']); data['runId'] = RUN; effect['userData'] = json.dumps(data)
        else:
            packet['source'].update(sourceIdentityVersion=1,effectSourceVersion=1,effects=dict(
                complete=True,scanRadiusMeters=64,scannedEntities=0,entities=[],absentIds=list(self.retired)))
        packet['source']['effects']['absentIds'] = list(self.retired)
        history(packet, self.events); packet['source']['loads']['instance'] = self.load_birth
        rows = [] if self.engine is None else [manager(self.engine['required']['instance'],self.engine['url'],epoch=self.loaded_epoch)]
        membership_source(packet, rows, self.revision)
    def start_script(self, url):
        self.engine_number += 1; self.revision += 1; self.loaded_epoch = self.epoch()
        self.selected = 'script-bundle/main.js' if '/script-bundle/' in url else 'script.js'
        self.entity = str(uuid.uuid4())
        self.engine = dict(url=url, running=True, stopping=False, finished=False, required=dict(
            instance=hashlib.sha256(('manager-'+str(self.engine_number)).encode()).hexdigest()[:32],sequence=1,
            modules=[dict(url=url.rsplit('/',1)[0]+'/companion.js',loaded=True,cached=False,sequence=1,capturedEpochMs=self.epoch())]))
        self.qt.rows = [dict(url=url,path=file_url(url))]
        self.events.append(event(len(self.events)+1,url=url,callbackEpochMs=self.epoch(),managerInstance=self.engine['required']['instance'],loadGeneration=1,success=True,status='Success'))
    def stop_script(self):
        if self.engine is not None: self.retired.append(self.entity); self.engine = None; self.revision += 1
    def restart(self):
        self.native.identity = '124:new-start'; self.native.bridge_id = str(uuid.uuid4()); self.native.running = True
        self.native.opened = self.qt.opened = False; self.qt.page = 'home'; self.qt.rows = []
        self.file_ui.opened = False; self.file_ui.review = None; self.engine = None; self.retired = []
        self.birth = 'd'*32; self.load_birth = 'e'*32; self.events = []; self.revision = 0
        self.launches += 1; self.activations += 1; self.status = ''; self.ui_sequence = 0
        self.execution.sequence = self.lifecycle.sequence = self.storage.sequence = self.presence.sequence = 0
    def passive_ui(self, command):
        visible = self.native.opened and self.qt.page == 'scripts'
        status = self.status if visible else ''
        managers = [observed(statusText=status,labelText=status,labelVisible=bool(status))] if visible else []
        controls = []
        if visible:
            controls = deepcopy(self.file_ui.capture()['controls'])
            for row in controls:
                row['focused'] = self.f.file_focus == row['id']
                if row['id'] == 'scripts.from-file': row['manager'] = managers[0]
        packet = dict(schemaVersion=1,commandId=command['commandId'],action='observe',instance=self.birth,
            generation=self.birth,sourceSequence=self.ui_sequence,lastCommandSequence=self.native.sequence,
            elapsedMs=round(self.clock*1000),capturedEpochMs=self.epoch(),processId=self.pid(),
            fileControlsVersion=1,ready=True,controls=controls,
            scriptInventory=inventory(managers,[picker()] if self.file_ui.opened else [],tabletShown=self.native.opened))
        if self.ui_fault == 'hidden-picker': packet['scriptInventory']['pickers'] = [picker(visible=False)]
        if self.ui_fault == 'stale': packet['capturedEpochMs'] -= 2000
        if self.ui_fault == 'foreign': packet['processId'] += 1
        if self.ui_fault == 'incomplete': packet['scriptInventory']['complete'] = False
        return packet
    def active(self, verb, inputs=None):
        self.ticket_number += 1; self.ticket = f'{self.ticket_number:032x}'
        self.reader.activate(self.ticket,verb,inputs or {})
        return dict(contractVersion=VERSION,runId=RUN,ticket=self.ticket,fixtureUrl=self.fixture_url,verb=verb,inputs=inputs or {})
    def sample(self):
        value = self.primary.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertIsInstance(self.actor.publish(),int)
        return value
    def step(self, verb, inputs=None):
        self.primary.act(self.active(verb,inputs)); self.sleep(.25); return self.sample()

    def test_complete_v16_script_flow_joins_pico_input_two_original_readers_restart_error_and_cleanup(self):
        self.active('baseline'); initial = self.sample()
        self.assertEqual(SCENARIOS['scripts']['baseline'], initial['state'])
        for step in SCENARIOS['scripts']['steps']:
            actual = self.step(step['verb'],step.get('inputs'))
            self.assertEqual(step['state']['open'],actual['state']['open'])
            self.assertEqual(step['state']['picker'],actual['state']['picker'])
            self.assertEqual(step['state']['running'],actual['state']['running'])
        self.assertEqual(['stop','launch'],self.lifecycle_inputs)
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.storage.commands))
        self.active('cleanup'); cleanup = dict(contractVersion=VERSION,runId=RUN)
        self.primary.cleanup(cleanup); self.primary.cleanup(cleanup); self.sample()
        self.reader.close(); self.primary.finalize()
        self.assertFalse(self.storage.root.exists())
        self.assertEqual([],list(self.primary.store.path.parent.glob('*.json')))

    def test_full_owner_recovers_lost_launch_from_original_native_proof_without_input_replay(self):
        self.active('baseline'); self.sample()
        for step in SCENARIOS['scripts']['steps'][:10]:
            self.step(step['verb'],step.get('inputs'))
        call = self.active('restart-app'); self.lost_launch = True
        with self.assertRaises((NativeUIError,RuntimeError,ValueError)): self.primary.act(call)
        self.assertIsNone(self.openxr_identity)
        self.assertEqual(['stop','launch'], self.lifecycle_inputs)
        self.assertEqual('issued',self.facade._script_actions(self.target,RUN,self.fixture_url).load()['phase'])
        self.lost_launch = False
        self.assertEqual({'performed':True},self.primary.act(call))
        self.assertEqual('124:new-start',self.openxr_identity)
        self.assertEqual([],self.sample()['state']['running'])
        self.assertEqual(['stop','launch'],self.lifecycle_inputs)
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.storage.commands))

    def test_public_adapter_triple_uses_adapter_only_fixture_authority(self):
        self.active('baseline')
        sample = dict(contractVersion=VERSION,runId=RUN,afterSequence=0)
        actual = self.original.invoke(self.target, 'feature.scripts.observe', sample)
        self.assertEqual(SCENARIOS['scripts']['baseline'], actual['state'])
        self.assertIsInstance(self.actor.publish(), int)
        self.original.invoke(self.target, 'feature.scripts.act', self.active('open'))
        self.sleep(.25)
        actual = self.original.invoke(self.target, 'feature.scripts.observe', sample)
        self.assertTrue(actual['state']['open'])
        self.assertGreater(len(self.native.controllers), 0)
        self.assertGreater(len(self.input_commands), 0)
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.storage.commands))

    def test_hidden_original_picker_blocks_release_until_actual_native_retirement(self):
        self.active('baseline'); self.sample(); self.step('open'); self.step('close')
        self.active('cleanup'); self.ui_fault = 'hidden-picker'
        with self.assertRaises((NativeUIError,RuntimeError,ValueError)):
            self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual('cleaning',self.primary.control()['phase'])
        self.assertTrue(self.storage.root.exists())
        self.assertFalse(any(row['operation']=='release' for row in self.storage.commands))
        self.ui_fault = ''  # Original native boundary now independently observes retirement.
        self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN)); self.sample()
        self.assertFalse(self.storage.root.exists())

    def test_original_file_release_failure_keeps_cleanup_ownership(self):
        self.active('baseline'); self.sample(); self.step('open'); self.step('close')
        self.active('cleanup'); self.storage.fault = 'ignored-release'
        with self.assertRaises((NativeUIError,RuntimeError,ValueError)):
            self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertTrue(self.storage.root.exists())
        self.assertIsNotNone(self.facade.script_files_store(self.target).read())
        self.assertEqual('cleaning', self.primary.control()['phase'])
        with self.assertRaises((NativeUIError,RuntimeError,ValueError)): self.primary.finalize()
        self.assertIsNotNone(self.primary.store.read())

    def test_ignored_normal_input_remains_owned_and_is_not_replayed(self):
        self.active('baseline'); self.sample(); call = self.active('open'); self.ignored = True
        for _ in range(2):
            with self.assertRaises((NativeUIError,RuntimeError,ValueError)): self.primary.act(call)
        # One original pointer input, despite consumed transport ACK.
        self.assertEqual(1,len(self.input_commands))
        self.assertEqual('issued',self.facade._script_actions(self.target,RUN,self.fixture_url).load()['phase'])

    def test_foreign_stale_and_partial_passive_sources_cannot_become_current_feature_facts(self):
        self.active('baseline'); self.sample()
        for fault in ('foreign','stale','incomplete'):
            self.ui_fault = fault
            source = self.facade._script_file_io(self.target)
            with self.subTest(fault=fault), self.assertRaises((NativeUIError,RuntimeError,ValueError)):
                packet = source.capture(); from adapters.script_ui_inventory import ui_state; ui_state(packet)
        self.assertEqual([],self.input_commands)

    def test_candidate_change_rejects_observation_before_native_command(self):
        self.active('baseline'); self.sample(); before = len(self.execution.commands)
        self.native.digest = 'f'*64
        with self.assertRaises((NativeUIError,RuntimeError,ValueError)): self.primary.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertEqual(before,len(self.execution.commands))

    def test_source_channel_cannot_deliver_ui_input_or_advertise_other_feature_areas(self):
        source = self.facade._script_file_io(self.target)
        with self.assertRaises((NativeUIError,RuntimeError,ValueError)): source.input('script-file.cancel','activate')
        self.assertEqual([],self.input_commands)
        features = {name for name in self.original.capabilities(self.target) if name.startswith('feature.')}
        self.assertEqual(set(pico.OPERATIONS), features)
        with patch.dict(os.environ, {'OVERTE_PICO_FEATURE_SCRIPTS':'0'}):
            self.assertFalse(any(name.startswith('feature.') for name in self.original.capabilities(self.target)))


class PicoSharedScriptJourneyTests(unittest.TestCase):
    def test_shared_engine_executes_every_v16_checkpoint_and_both_quiet_cleanup_windows(self):
        f = PicoScriptJourneyTests()
        f.setUp(); self.addCleanup(f.doCleanups)
        from feature_journeys.engine import Journey
        reports = []
        def invoke(operation, values):
            return f.original.invoke(f.target, operation, values)
        def witness():
            f.actor.publish()
            return f.reader.observe()
        journey = Journey('scripts',RUN,f.fixture_url,invoke=invoke,witness=witness,
            activate=f.reader.activate,read_artifact=lambda _name:f.fail('No Script artifact shortcut'),
            image_policy={},continuity=lambda *_args:None,monotonic=lambda:f.clock,
            epoch_ms=f.epoch,sleep=f.sleep,report=reports.append)
        journey.execute()
        f.assertTrue(reports[-1]['sequenceCompleted'])
        f.assertTrue(reports[-1]['cleanupSucceeded'])
        f.assertEqual(21,len(reports[-1]['phases']))
        f.assertFalse(f.storage.root.exists())
        f.assertEqual(['stop','launch'],f.lifecycle_inputs)
        f.assertEqual(1,len(f.fixture.script_resources.snapshot(RUN)['responses']))
        f.assertEqual({'performed':True},f.primary.finalize())
        f.assertTrue(all(store.read() is None for store in f.primary._retirement_paths()))


if __name__ == '__main__': unittest.main()
