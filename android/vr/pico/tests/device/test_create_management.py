"""No-build Pico Create owner composition; synthetic UI/native boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_management import PicoCreateManagement, configuration
from adapters.pico4.tablet_home import PicoTabletHome
from self_tests.test_normal_create_adapter import NativeCreate, BINDING, NAME, URL
from self_tests.test_pico_tablet_home import original as home_original
from self_tests.test_token_create_ui import Controls
from create_journey import INITIAL, EDITED


class Source:
    pid = 21
    def __init__(self, native):
        self.native = native
        self.sequence = 0
        self.gestures = []
    def capture(self):
        self.sequence += 1
        return home_original() | dict(processId=self.pid, sourceSequence=self.sequence,
            capturedEpochMs=self.clock_ms(), tabletShown=self.native.tablet,
            onHomeScreen=self.native.page == 'home')
    def clock_ms(self): return 10000 + round(self.native.clock * 1000)
    def monotonic(self): return self.native.clock
    def sleep(self, seconds): self.native.sleep(seconds)
    def guard(self): return True
    def stage(self, pose):
        self.gestures.append(deepcopy(pose))
        self.native.page = 'home'
        self.native.manager = False


class PicoCreateManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        os.chmod(self.temp.name, 0o700)
        self.native = NativeCreate(self.temp.name)
        self.native.page = 'home'
        self.native.monotonic = lambda: self.native.clock
        self.widget = Controls(self.native)
        self.source = Source(self.native)
        self.home = PicoTabletHome(self.source, self.source.stage)
        self.binding = deepcopy(BINDING)
        self.binding['sessionId'] = self.widget.instance
        def capture():
            value = self.widget.capture()
            original = value['scope']
            return dict(createControlsVersion=1, open=value['open'], ready=value['ready'],
                bridgeId=original['instance'], generation=original['generation'],
                lastCommandSequence=original['sequence'], elapsedMs=original['elapsedMs'],
                processId=original['processId'], controls=value['controls'])
        def input(identifier, action='activate', text=None, *, index=None, direction=None, reference):
            value = text if action == 'replace' else index if action == 'select-index' else direction
            self.widget.input(identifier, action, reference, value)
        self.native.io = SimpleNamespace(capture=capture, navigation=SimpleNamespace(input=input))
        def read(after, *, include_avatar_entities=False):
            self.assertTrue(include_avatar_entities)
            return self.native.observe(after)[0]
        self.adapter = SimpleNamespace(pico_configuration=('synthetic', Path(self.temp.name)),
            _script_paths=lambda _target: (Path(self.temp.name)/'foreign-scripts.json', None),
            _script_runtime=lambda _target: (self.native, None, deepcopy(self.binding)),
            _feature_observer=lambda _target: SimpleNamespace(read=read),
            _native_feature_observer=lambda _target: None,
            adb=SimpleNamespace(epoch_milliseconds=lambda _target:10000+self.native.sequence))
        self.owner = PicoCreateManagement(self.adapter, 'private-synthetic-target')
        boundary = patch('adapters.pico4.create_management.bind_home', return_value=self.home)
        boundary.start(); self.addCleanup(boundary.stop)
        # The widget seam itself enforces persisted intent before every input.
        self.widget.intents = IntentView(self.owner)

    def invoke(self, operation, values=None):
        return self.owner.invoke(operation, values or {})
    def open(self): return self.invoke('create.reference.open', {'scriptUrl':URL})
    def cube(self): return self.invoke('create.cube', {'name':NAME, 'properties':INITIAL})
    def close(self): return self.invoke('create.reference.close', {'scriptUrl':URL})

    def test_ordinary_cube_edit_delete_json_error_and_actual_vr_home_cleanup(self):
        self.open(); self.cube()
        self.assertEqual(NAME, self.native.entities[0]['name'])
        self.invoke('create.update', {'name':NAME, 'properties':EDITED})
        self.invoke('create.delete', {'names':[NAME]})
        self.invoke('create.import', {'url':URL.replace('observer.js','entities.json')})
        self.assertEqual(2, len(self.native.entities))
        self.invoke('create.delete', {'names':[NAME, NAME.replace('_cube','_import-parent'), NAME.replace('_cube','_import-child')]})
        self.invoke('create.import', {'url':URL.replace('observer.js','missing.json')})
        self.assertEqual([], self.native.entities)
        self.assertEqual('missing.json', self.widget.texts['create.import-url'].rsplit('/',1)[1])
        before = self.native.clock
        self.close()
        self.assertGreaterEqual(self.native.clock-before, 6)
        self.assertFalse(self.native.tablet)
        self.assertEqual([], self.native.rows)
        self.assertFalse(self.owner.owned())
        self.assertEqual(2, len(self.source.gestures))
        self.close()

    def test_uncertain_create_is_not_replayed_and_cleanup_uses_original_measured_uuid(self):
        self.open(); self.native.partial_create = True
        with self.assertRaises(NativeUIError): self.cube()
        record = self.owner.store('inputs').read()
        self.assertEqual('create.new-shape', record['last']['original']['controlId'])
        with self.assertRaises(NativeUIError): self.cube()
        self.owner.cleanup()
        self.assertFalse(self.owner.owned())
        self.assertEqual([], self.native.entities)
        self.assertEqual(1, self.native.calls.count('create-cube'))

    def test_ignored_delete_and_incomplete_inventory_retain_all_original_ownership(self):
        self.open(); self.cube(); self.native.ignored_delete = True
        with self.assertRaises((NativeUIError, RuntimeError)): self.owner.cleanup()
        self.assertTrue(self.owner.owned())
        self.assertIsNotNone(self.owner.store('owner').read())
        self.assertNotIn('stop', self.native.calls)
        self.native.ignored_delete = False; self.native.complete = False
        with self.assertRaises(NativeUIError): self.owner.cleanup()
        with self.assertRaises(NativeUIError):
            self.invoke('create.import', {'url':URL.replace('observer.js','entities.json')})
        self.assertIsNotNone(self.owner.store('inputs').read())
        self.assertNotIn('stop', self.native.calls)
        self.native.complete = True; self.owner.cleanup()
        self.assertFalse(self.owner.owned())

    def test_lost_import_result_is_never_replayed_or_forgotten(self):
        self.open(); self.native.ignore_import = True
        with self.assertRaises(NativeUIError):
            self.invoke('create.import', {'url':URL.replace('observer.js','entities.json')})
        with self.assertRaises(NativeUIError): self.owner.cleanup()
        self.assertEqual(1, self.native.calls.count('import'))
        self.assertIsNotNone(self.owner.store('owner').read()['pendingImportBeforeIds'])
        self.assertNotIn('stop', self.native.calls)

    def test_foreign_script_reservation_candidate_and_corrupt_input_refuse_mutation(self):
        foreign = PrivateFeatureState(Path(self.temp.name)/'foreign-scripts.json')
        foreign.write({'foreign':True}, None)
        with self.assertRaises(NativeUIError): self.open()
        self.assertEqual([], self.native.calls)
        foreign.discard({'foreign':True})
        self.open(); self.cube()
        before = list(self.native.calls)
        self.binding['artifactSha256'] = 'f'*64
        with self.assertRaises(NativeUIError): self.owner.cleanup()
        self.assertEqual(before, self.native.calls)
        self.binding = deepcopy(BINDING)
        self.binding['sessionId'] = self.widget.instance
        value = self.owner.store('inputs').read()
        bad = deepcopy(value); bad['last']['original']['scope']['processId'] += 1
        self.owner.store('inputs').write(bad, value)
        with self.assertRaises(NativeUIError): self.owner.cleanup()
        self.assertEqual(before, self.native.calls)

    def test_failing_private_intent_prevents_one_normal_input(self):
        self.open()
        before = len(self.widget.inputs)
        original = PrivateFeatureState.write
        def write(store, value, previous):
            if store.path == self.owner.paths['inputs']:
                raise NativeUIError('synthetic disk failure')
            return original(store, value, previous)
        with patch.object(PrivateFeatureState, 'write', write), self.assertRaises(NativeUIError): self.cube()
        self.assertEqual(before, len(self.widget.inputs))
        self.assertEqual([], self.native.entities)

    def test_refused_baseline_retires_only_unused_reader_and_preserves_foreign_entities(self):
        self.native.entities = [dict(id='{11111111-1111-1111-1111-111111111111}', name=NAME, type='Box')]
        with self.assertRaises(NativeUIError): self.open()
        self.assertNotIn('open-tablet', self.native.calls)
        self.owner.cleanup()
        self.assertFalse(self.owner.owned())
        self.assertEqual(NAME, self.native.entities[0]['name'])
        self.assertNotIn('delete-entity', self.native.calls)

    def test_uncertain_history_never_reissues_the_original_input(self):
        self.open(); self.cube()
        def uncertain(action):
            self.native.calls.append(action)
            raise NativeUIError('lost native history result')
        with patch.object(self.native, 'history', side_effect=uncertain):
            with self.assertRaises(NativeUIError): self.invoke('create.undo')
            with self.assertRaises(NativeUIError): self.invoke('create.undo')
        self.assertEqual(1, self.native.calls.count('undo'))
        self.owner.cleanup()
        self.assertFalse(self.owner.owned())

    def test_normal_configuration_requires_original_debug_openxr_and_scene(self):
        self.assertIsNone(configuration({}))
        for enabled in ('yes', True, '2'):
            with self.assertRaises(NativeUIError): configuration({'OVERTE_PICO_NORMAL_CREATE':enabled})
        with self.assertRaises((NativeUIError, RuntimeError)):
            configuration({'OVERTE_PICO_NORMAL_CREATE':'1'})


class IntentView:
    """Read the real durable input record, without giving the widget the owner."""
    def __init__(self, owner): self.owner = owner
    def __bool__(self): return self.owner.store('inputs').read() is not None
    def __getitem__(self, index):
        if index != -1: raise IndexError(index)
        value = self.owner.store('inputs').read()
        if value is None or value['last']['kind'] != 'create': raise IndexError(index)
        return value['last']['original']


if __name__ == '__main__': unittest.main()
