"""Real private journals/fixture bytes; OS, engine and UI sources are synthetic.

No application, compiler, device, or lifecycle service is executed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_script_files import NativeScriptFiles, OwnedScriptFiles, originals
from adapters.native_script_observation import NativeScriptObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_restart_handoff import ScriptRestartHandoff
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_native_script_observation import Boundary as EngineBoundary, code_source, effect_source
from self_tests import test_normal_script_file_manager as file_tests
from self_tests.test_native_script_files import RUN

BINDING = file_tests.BINDING
NEW = BINDING | dict(processIdentity='32:new-start', sessionId='new-session', generation=2)
EFFECT = '11111111-1111-4111-8111-111111111111'


class RestartHandoffTests(unittest.TestCase):
    flow = file_tests.ScriptFileManagerTests.flow
    opened = file_tests.ScriptFileManagerTests.opened

    def setUp(self):
        file_tests.ScriptFileManagerTests.setUp(self)
        self.clock = 0.
        self.epoch = lambda: 20000 + int(self.clock * 1000)
        self.store = PrivateFeatureState(self.path / 'handoff.json')
        self.transfer = self.handoff()
        self.engine = EngineBoundary()
        self.engine.engine['url'] = self.directory + '/script-bundle/main.js'
        self.engine.engine['required']['modules'][0]['url'] = self.directory + '/script-bundle/companion.js'
        self.engine.mutate = self.enrich_old
        self.old_execution = self.execution(self.engine, 31)

    def handoff(self):
        return ScriptRestartHandoff(self.store, self.files.store, self.native.store,
            monotonic=lambda: self.clock, sleep=self.sleep)

    def sleep(self, seconds): self.clock += seconds

    def execution(self, source, pid):
        return NativeScriptObservation(source.send, source.original, self.epoch, lambda: source.okay, pid,
            monotonic=lambda: self.clock, sleep=self.sleep)

    def enrich_old(self, packet):
        packet.update(instance='d' * 32, requestedEpochMs=self.epoch(), capturedEpochMs=self.epoch())
        code_source(packet, originals(RUN)['script-bundle/main.js'].decode())
        effect_source(packet)
        row = packet['source']['effects']['entities'][0]
        row['name'] = 'e2e-' + RUN + '-script'; row['userData'] = json.dumps(dict(runId=RUN, ticks=2))
        packet['source'].update(loadSourceVersion=1, loads=dict(complete=True, instance='7' * 32, sequence=0, events=[]))

    def prepared(self):
        flow = self.opened(); flow.file_picker_choose('script-bundle/main.js')
        original = self.transfer.prepare(flow, self.old_execution)
        self.assertEqual(31, original['processId']); self.assertIsNotNone(self.store.read())
        return flow

    def new_process(self):
        # Simulate actual OS shutdown: old local heap/Qt objects are destroyed.
        # Persisted original fixture files and owner token are kept unchanged.
        self.native.tablet = self.native.manager = False
        self.native.rows = []; self.native.instance = '9' * 32; self.native.sequence = 0
        self.picker_io.opened = False
        self.new_engine = EngineBoundary()
        def enrich(packet):
            packet.update(processId=32, instance='a' * 32,
                requestedEpochMs=self.epoch(), capturedEpochMs=self.epoch())
            packet['source']['engines'] = []
            packet['source'].update(sourceIdentityVersion=1, effectSourceVersion=1,
                effects=dict(complete=True, scanRadiusMeters=64, scannedEntities=0, entities=[], absentIds=[]),
                loadSourceVersion=1, loads=dict(complete=True, instance='8' * 32, sequence=0, events=[]))
            if self.edit: self.edit(packet)
        self.edit = None; self.new_engine.mutate = enrich
        self.new_execution = self.execution(self.new_engine, 32)
        self.presence = PresenceBoundary(pid=32, epoch_ms=self.epoch); self.presence.presence = 'absent'
        self.presence_reader = self.presence.reader()
        self.presence_reader.monotonic = lambda: self.clock; self.presence_reader.sleep = self.sleep
        self.storage.mutate = lambda packet: packet.update(processId=32, instance='a' * 32,
            requestedEpochMs=self.epoch(), capturedEpochMs=self.epoch())
        self.new_files = NativeScriptFiles(self.storage.send, self.storage.read, self.epoch,
            lambda: self.storage.okay, 32, monotonic=lambda: self.clock, sleep=self.sleep)
        from adapters.token_script_file_ui import TokenScriptFilePicker
        self.new_picker = TokenScriptFilePicker(self.picker_io, self.directory,
            monotonic=lambda: self.clock, sleep=self.sleep)

    def adopt(self, binding=NEW):
        return self.handoff().adopt(binding, self.presence_reader, self.new_execution, self.new_files,
            self.native, self.native.observe, self.new_picker)

    def test_original_files_survive_and_new_closed_empty_process_gets_exact_bindings_before_normal_reopen(self):
        self.prepared(); frozen = deepcopy(self.store.read()); self.new_process()
        before_inputs = list(self.picker_io.actions); before_calls = list(self.native.calls)
        evidence = self.adopt()
        self.assertGreaterEqual(self.clock, 3)
        self.assertEqual('ESRCH', evidence['exit']['errorSymbol'])
        self.assertEqual([], evidence['execution']['source']['engines'])
        self.assertEqual(before_inputs, self.picker_io.actions); self.assertEqual(before_calls, self.native.calls)
        self.assertEqual(frozen['oldFiles'] | {'binding': NEW}, self.files.store.read())
        current = self.native.store.read()
        self.assertEqual(NEW, current['binding']); self.assertFalse(current['loadAttempted'])
        self.assertIsNone(current['source']); self.assertFalse(current['managerOwned'])
        self.assertIsNone(self.store.read()); self.assertTrue(self.storage.root.exists())
        self.assertEqual(1, sum(row['operation'] == 'stage' for row in self.storage.commands))
        adopted = OwnedScriptFiles(self.new_files, self.files.store, NEW)
        self.assertEqual(self.directory, adopted.verify())
        # Ordinary equality remains strict; the old flow cannot use the new files.
        with self.assertRaises(NativeUIError): self.files.owned()
        for name, raw in originals(RUN).items(): self.assertEqual(raw, (self.storage.root / name).read_bytes())

    def test_old_process_present_or_unknown_never_authorizes_binding_change(self):
        self.prepared(); self.new_process()
        for state in ('present', 'unknown'):
            self.presence.presence = state
            with self.subTest(state=state), self.assertRaises(NativeUIError): self.adopt()
            self.assertEqual(BINDING, self.files.store.read()['binding'])
            self.assertIsNone(self.store.read()['next'])
        self.assertEqual([], self.new_engine.commands)

    def test_candidate_target_or_source_replacement_fails_before_any_new_native_read(self):
        self.prepared(); self.new_process()
        for changed in ({'artifactSha256': 'f' * 64}, {'sourceRevision': 'f' * 40},
                        {'targetFingerprint': 'f' * 64}, {'processIdentity': BINDING['processIdentity']},
                        {'generation': 0}):
            with self.subTest(changed=changed), self.assertRaises(NativeUIError): self.adopt(NEW | changed)
        self.assertEqual([], self.presence.commands)

    def test_missing_changed_or_relocated_originals_retain_original_cleanup_intent(self):
        self.prepared(); self.new_process()
        path = self.storage.root / 'companion.js'; original = path.read_bytes()
        for fault in ('changed', 'missing', 'directory'):
            if fault == 'changed': path.write_bytes(b'changed')
            elif fault == 'missing': path.unlink()
            else:
                mutate = self.storage.mutate
                def relocate(packet):
                    mutate(packet); packet['source']['directory'] = 'file:///other/feature-script-' + RUN
                self.storage.mutate = relocate
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.adopt()
            self.assertIsNone(self.store.read()['next']); self.assertEqual(BINDING, self.files.store.read()['binding'])
            path.write_bytes(original)

    def test_retained_engine_module_load_or_old_effect_cannot_be_empty_execution(self):
        self.prepared(); self.new_process()
        for fault in ('engine', 'module', 'effect', 'old-id', 'birth'):
            def edit(packet):
                if fault == 'birth': packet['instance'] = 'd' * 32
                elif fault in ('engine', 'module'):
                    engine = deepcopy(self.engine.engine)
                    if fault == 'module': engine['url'] = 'file:///foreign/main.js'; engine['required']['instance'] = '6' * 32
                    packet['source']['engines'] = [engine]; code_source(packet)
                else:
                    effect_source(packet)
                    if fault == 'effect':
                        row = packet['source']['effects']['entities'][0]
                        row['name'] = 'e2e-' + RUN + '-script'; row['userData'] = json.dumps(dict(runId=RUN, ticks=2))
            self.edit = edit
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.adopt()
            self.assertIsNone(self.store.read()['next'])
            # A failed raw observation must not poison other independent cases.
            self.new_execution = self.execution(self.new_engine, 32)

    def test_delayed_replay_is_caught_during_full_three_second_window(self):
        self.prepared(); self.new_process()
        def replay(packet):
            if self.clock >= 1:
                packet['source']['engines'] = [deepcopy(self.engine.engine)]; code_source(packet)
        self.edit = replay
        with self.assertRaises(NativeUIError): self.adopt()
        self.assertGreaterEqual(self.clock, 1); self.assertLess(self.clock, 3)
        self.assertIsNone(self.store.read()['next']); self.assertEqual(BINDING, self.files.store.read()['binding'])

    def test_current_independent_service_ui_and_picker_cannot_hide_retained_state(self):
        self.prepared(); self.new_process()
        for fault in ('service', 'tablet', 'manager', 'picker'):
            self.native.rows = ([dict(url=self.directory + '/script.js', path=self.directory + '/script.js')]
                                if fault == 'service' else [])
            self.native.tablet = fault == 'tablet'; self.native.manager = fault == 'manager'
            self.picker_io.opened = fault == 'picker'
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.adopt()
            self.assertIsNone(self.store.read()['next'])

    def test_old_or_missing_service_observation_cannot_be_relabelled_as_a_new_empty_manager(self):
        self.prepared(); self.new_process(); original = self.native.observe
        for fault in ('old-instance', 'old-cursor', 'missing', 'incomplete'):
            def observe(after):
                value, epoch = original(after)
                if fault == 'old-instance': value['instance'] = 'e' * 32
                elif fault == 'old-cursor': value['sampleSequence'] = after
                elif fault == 'missing': value = None
                else: value['complete'] = False
                return value, epoch
            self.native.observe = observe
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.adopt()
            self.assertIsNone(self.store.read()['next'])
        self.native.observe = original

    def test_observed_failed_owned_load_is_replay_even_if_no_engine_survives(self):
        self.prepared(); self.new_process()
        from self_tests.test_native_script_loads import event
        def edit(packet):
            attempted = event(1, url=self.directory + '/script-bundle/main.js')
            packet['source']['loads'].update(sequence=1, events=[attempted])
        self.edit = edit
        with self.assertRaises(NativeUIError): self.adopt()
        self.assertIsNone(self.store.read()['next'])

    def test_partial_binding_write_recovers_only_after_new_original_observations_without_input_replay(self):
        self.prepared(); self.new_process(); original = self.native.store.write
        def interrupted(value, previous): raise OSError('synthetic interrupted second journal write')
        self.native.store.write = interrupted
        with self.assertRaises(OSError): self.adopt()
        self.assertEqual(NEW, self.files.store.read()['binding'])
        self.assertEqual(BINDING, self.native.store.read()['binding']); self.assertIsNotNone(self.store.read()['next'])
        before = len(self.new_engine.commands); started = self.clock
        self.native.store.write = original; self.adopt()
        self.assertGreater(len(self.new_engine.commands), before); self.assertGreaterEqual(self.clock - started, 3)
        self.assertEqual(NEW, self.native.store.read()['binding']); self.assertIsNone(self.store.read())
        self.assertEqual(1, sum(row['operation'] == 'stage' for row in self.storage.commands))

    def test_partial_transfer_with_foreign_record_or_new_birth_remains_recoverably_blocked(self):
        self.prepared(); self.new_process(); original = self.native.store.write
        self.native.store.write = lambda *_: (_ for _ in ()).throw(OSError('synthetic interruption'))
        with self.assertRaises(OSError): self.adopt()
        self.native.store.write = original
        before = deepcopy(self.store.read()); files = self.files.store.read()
        foreign = files | {'ownerToken': 'f' * 64}; self.files.store.write(foreign, files)
        with self.assertRaises(NativeUIError): self.adopt()
        self.assertEqual(before, self.store.read()); self.files.store.write(files, foreign)
        self.edit = lambda packet: packet.update(instance='c' * 32)
        with self.assertRaises(NativeUIError): self.adopt()
        self.assertEqual(before, self.store.read())

    def test_late_or_regressing_final_io_cannot_rebind_journals(self):
        self.prepared(); self.new_process(); original = self.native.manager_visible
        for fault in ('late', 'regressed', 'lost-guard'):
            started = self.clock
            def observed():
                result = original()
                if fault == 'late': self.clock = started + 21
                elif fault == 'regressed': self.clock = -1
                else: self.storage.okay = False
                return result
            self.native.manager_visible = observed
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.adopt()
            self.assertIsNone(self.store.read()['next']); self.assertEqual(BINDING, self.files.store.read()['binding'])
            self.clock = started; self.storage.okay = True

    def test_interruption_before_first_binding_write_preserves_verified_transaction_and_can_resume(self):
        self.prepared(); self.new_process(); original = self.files.store.write
        self.files.store.write = lambda *_: (_ for _ in ()).throw(OSError('synthetic first-write interruption'))
        with self.assertRaises(OSError): self.adopt()
        self.assertIsNotNone(self.store.read()['next'])
        self.assertEqual(BINDING, self.files.store.read()['binding'])
        self.assertEqual(BINDING, self.native.store.read()['binding'])
        self.files.store.write = original; self.adopt(); self.assertIsNone(self.store.read())

    def test_interruption_after_both_writes_rechecks_observations_and_does_not_repeat_product_input(self):
        self.prepared(); self.new_process(); original = self.store.discard
        self.store.discard = lambda *_: (_ for _ in ()).throw(OSError('synthetic final-retirement interruption'))
        with self.assertRaises(OSError): self.transfer.adopt(NEW, self.presence_reader,
            self.new_execution, self.new_files, self.native, self.native.observe, self.new_picker)
        self.assertEqual(NEW, self.files.store.read()['binding'])
        self.assertEqual(NEW, self.native.store.read()['binding'])
        self.assertIsNotNone(self.store.read()); before = self.clock
        self.store.discard = original; self.adopt()
        self.assertGreaterEqual(self.clock - before, 3); self.assertIsNone(self.store.read())

    def test_native_capture_clock_must_advance_for_the_whole_quiet_window(self):
        self.prepared(); self.new_process(); self.epoch = lambda: 20000
        self.new_execution.clock_ms = self.epoch; self.new_files.clock_ms = self.epoch
        self.presence.epoch_ms = self.epoch; self.presence_reader.clock_ms = self.epoch
        with self.assertRaises(NativeUIError): self.adopt()
        self.assertGreaterEqual(self.clock, 20); self.assertIsNone(self.store.read()['next'])

    def test_late_second_record_write_retains_recoverable_transaction_instead_of_green_completion(self):
        self.prepared(); self.new_process(); original = self.native.store.write
        def slow_write(value, previous): original(value, previous); self.clock = 21
        self.native.store.write = slow_write
        with self.assertRaises(NativeUIError): self.adopt()
        self.assertEqual(NEW, self.native.store.read()['binding']); self.assertIsNotNone(self.store.read()['next'])

    def test_prepare_refuses_wrong_code_or_incomplete_existing_ownership_before_stop(self):
        flow = self.opened(); flow.file_picker_choose('script-bundle/main.js')
        original = self.engine.mutate
        self.engine.mutate = lambda packet: (original(packet), code_source(packet, 'wrong code'))
        with self.assertRaises(NativeUIError): self.transfer.prepare(flow, self.old_execution)
        self.assertIsNone(self.store.read())
        self.engine.mutate = original; self.old_execution = self.execution(self.engine, 31)
        flow.mark(pickerOwned=True)
        with self.assertRaises(NativeUIError): self.transfer.prepare(flow, self.old_execution)
        self.assertIsNone(self.store.read())

    def test_foreign_or_boolean_substituted_journal_cannot_authorize_an_adoption(self):
        self.prepared(); self.new_process()
        frozen = deepcopy(self.store.read()); files = self.files.store.read()
        for value in (files | {'contractVersion': True}, files | {'binding': files['binding'] | {'generation': True}},
                      files | {'ownerToken': 'f' * 64}):
            self.files.store.write(value, files)
            with self.assertRaises(NativeUIError): self.adopt()
            self.assertEqual([], self.presence.commands)
            self.assertEqual(frozen, self.store.read()); self.files.store.write(files, value)

    def test_component_only_context_remains_explicit_and_cannot_upgrade_to_qualified_candidate(self):
        flow = self.opened(); flow.file_picker_choose('script-bundle/main.js')
        component = {key: BINDING[key] for key in ('processIdentity', 'sessionId', 'generation', 'targetFingerprint')}
        component['scope'] = 'NATIVE_UI_COMPONENT_ONLY'
        fs = self.files.store.read(); ms = self.native.store.read()
        self.files.store.write(fs | {'binding': component}, fs)
        self.native.store.write(ms | {'binding': component}, ms)
        owned = OwnedScriptFiles(self.files.native, self.files.store, component, component_only=True)
        from adapters.normal_script_manager import NormalScriptManager
        manager = NormalScriptManager(self.native, self.native.observe, self.native.store, component,
            component_only=True, source_kind='script-file-bundle', file_owner=owned, file_picker=flow.file_picker)
        handoff = ScriptRestartHandoff(self.store, self.files.store, self.native.store, component_only=True,
            monotonic=lambda: self.clock, sleep=self.sleep)
        handoff.prepare(manager, self.old_execution); self.new_process()
        with self.assertRaises(NativeUIError): handoff.adopt(NEW, self.presence_reader,
            self.new_execution, self.new_files, self.native, self.native.observe, self.new_picker)
        new_component = {key: NEW[key] for key in ('processIdentity', 'sessionId', 'generation', 'targetFingerprint')}
        new_component['scope'] = 'NATIVE_UI_COMPONENT_ONLY'
        handoff.adopt(new_component, self.presence_reader, self.new_execution, self.new_files,
            self.native, self.native.observe, self.new_picker)
        self.assertEqual('NATIVE_UI_COMPONENT_ONLY', self.files.store.read()['binding']['scope'])
        self.assertNotIn('artifactSha256', self.files.store.read()['binding'])


if __name__ == '__main__': unittest.main()
