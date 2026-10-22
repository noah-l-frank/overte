"""Original probe plus synthetic Qt/listener boundaries; no native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_modals import NativeNavigationModals, command, presented, retired, MESSAGE_SHA256
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source
import self_tests.test_native_navigation_replies as replies

RUN = replies.RUN


class Boundary:
    def __init__(self):
        self.clock = 0.;self.now = lambda: self.clock
        self.sequence = 0;self.commands = [];self.request = None;self.cached = None
        self.ignore = False;self.alive = True;self.edit = None
        self.input_sequence = 1;self.ui_sequence = lambda: self.input_sequence
        self.ui_epoch = None;self.records = []
        self.replies = replies.Boundary(version=2);self.replies.error()
        self.event = deepcopy(self.replies.events[0])

    def epoch(self):
        return 20000 + round(self.now() * 1000)

    def sleep(self, seconds):
        self.clock += seconds

    def create(self):
        row = dict(modalId='1' * 32, sequence=len(self.records) + 1, event=deepcopy(self.event), createdEpochMs=self.epoch(),
            profile='pico-tablet-critical-v1', createdMessageSha256=MESSAGE_SHA256, messageSha256=MESSAGE_SHA256,
            rootAlive=True, listenerAlive=True, inCurrentTree=True, visible=True,
            callbackFinished=False, callbackEpochMs=0, selectedButton=None)
        self.records.append(row)
        return row

    def finish(self, *, root=False, listener=False, button=1024):
        row = self.records[-1]
        row.update(callbackFinished=True, callbackEpochMs=self.epoch(), selectedButton=button,
                   rootAlive=root, listenerAlive=listener, inCurrentTree=root, visible=False,
                   messageSha256=MESSAGE_SHA256 if root else None)

    def send(self, command):
        self.commands.append(deepcopy(command));self.request = deepcopy(command)
        if self.ignore:
            return
        self.sequence += 1
        self.cached = dict(navigationModalVersion=1, commandId=command['commandId'], runId=command['runId'], instance='2' * 32,
            sequence=self.sequence, processId=123, capturedEpochMs=self.epoch(),
            uiEpochMs=self.epoch() if self.ui_epoch is None else self.ui_epoch, uiElapsedMs=100 + round(self.now() * 1000),
            uiInputSequence=self.ui_sequence(), uiBridgeId='11111111-1111-4111-8111-111111111111',
            uiGeneration='22222222-2222-4222-8222-222222222222', tabletOpen=True, rootComplete=True,
            records=deepcopy([r for r in self.records if r['event']['runId'] == command['runId']]))
        if self.edit:
            self.edit(self.cached)

    def original(self):
        return json.dumps(self.cached) if self.cached is not None else ''

    def guard(self):
        return self.alive

    def reader(self):
        return NativeNavigationModals(self.send, self.original, self.epoch, self.guard, 123,
                                      monotonic=self.now, sleep=self.sleep)


class NativeNavigationModalTests(unittest.TestCase):
    def test_original_empty_presentation_response_and_real_resource_retirement_are_distinct(self):
        source = Boundary();reader = source.reader()
        self.assertEqual([], reader.read(RUN)['records'])
        source.create();opened = reader.read(RUN)
        self.assertEqual(source.records[0], presented(opened, source.event))
        with self.assertRaises(NativeUIError):
            retired(opened, source.event)
        source.clock += .5;source.finish(root=True, listener=True)
        with self.assertRaises(NativeUIError):
            retired(reader.read(RUN), source.event)
        source.clock += .5;source.records[0].update(rootAlive=False, inCurrentTree=False, messageSha256=None)
        with self.assertRaises(NativeUIError):
            retired(reader.read(RUN), source.event)
        source.records[0]['listenerAlive'] = False
        final = reader.read(RUN)
        self.assertEqual(1024, retired(final, source.event)['selectedButton'])
        self.assertEqual(opened['records'][0]['createdEpochMs'], final['records'][0]['createdEpochMs'])

    def test_matching_native_callback_and_actual_message_profile_and_current_tree_are_required(self):
        for edit in (lambda v: v['records'][0]['event'].update(eventId='3' * 32),
                     lambda v: v['records'][0].update(messageSha256='3' * 64),
                     lambda v: v['records'][0].update(createdMessageSha256='3' * 64),
                     lambda v: v['records'][0].update(inCurrentTree=False),
                     lambda v: v['records'][0].update(profile='unavailable'),
                     lambda v: v['records'][0].update(visible=False),
                     lambda v: v.update(tabletOpen=False)):
            source = Boundary();source.create();source.edit = edit
            with self.subTest(edit=edit), self.assertRaises(NativeUIError):
                presented(source.reader().read(RUN), source.event)
        source = Boundary();source.create();extra = deepcopy(source.records[0]);extra.update(modalId='4' * 32, sequence=2)
        source.records.append(extra)
        with self.assertRaises(NativeUIError):
            presented(source.reader().read(RUN), source.event)

    def test_missing_stale_foreign_or_incomplete_source_is_bounded_and_sends_once(self):
        for fault in ('ignore', 'nonce', 'unavailable', 'old-ui', 'incomplete', 'foreign-pid'):
            source = Boundary();source.create()
            if fault == 'ignore':
                source.ignore = True
            elif fault == 'nonce':
                source.edit = lambda v: v.update(commandId='0' * 32)
            elif fault == 'unavailable':
                source.edit = lambda v: (v.clear(), v.update(commandId=source.request['commandId'], status='unavailable'))
            elif fault == 'old-ui':
                source.ui_epoch = 18000
            elif fault == 'incomplete':
                source.edit = lambda v: v.update(rootComplete=False)
            else:
                source.edit = lambda v: v.update(processId=124)
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                source.reader().read(RUN)
            self.assertEqual(1, len(source.commands));self.assertLessEqual(source.clock, 5.01)

    def test_original_birth_callback_and_dead_qobjects_cannot_be_replaced_or_resurrected(self):
        for fault in ('drop', 'retime', 'event', 'cursor', 'instance', 'ui-clock', 'resurrect', 'result'):
            source = Boundary();source.create();reader = source.reader()
            if fault in ('resurrect', 'result'):
                source.finish()
            reader.read(RUN)
            if fault == 'drop':
                source.records = []
            elif fault == 'retime':
                source.clock += 1;source.records[0]['createdEpochMs'] += 1
            elif fault == 'event':
                source.records[0]['event']['responseId'] = '5' * 32
            elif fault == 'cursor':
                source.sequence = 0
            elif fault == 'instance':
                source.edit = lambda v: v.update(instance='5' * 32)
            elif fault == 'ui-clock':
                source.edit = lambda v: v.update(uiElapsedMs=99)
            elif fault == 'resurrect':
                source.records[0].update(rootAlive=True, inCurrentTree=True, messageSha256=MESSAGE_SHA256)
            else:
                source.records[0]['selectedButton'] = 0
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                reader.read(RUN)
        source = Boundary();source.create();reader = source.reader();reader.read(RUN);reader.read('b' * 32)
        source.records = []
        with self.assertRaises(NativeUIError):
            reader.read(RUN)

    def test_late_or_unbound_reply_cannot_become_success_after_native_or_local_time_changes(self):
        for fault in ('late', 'rewind', 'guard'):
            source = Boundary();source.create();read = source.original
            def changed():
                result = read()
                if fault == 'guard':
                    source.alive = False
                else:
                    source.clock = 6 if fault == 'late' else -1
                return result
            source.original = changed
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                source.reader().read(RUN)
            self.assertEqual(1, len(source.commands))

    def test_closed_envelope_original_callback_and_lifetime_types_reject_expected_data(self):
        source = Boundary();source.create()
        for edit in (lambda v: v.update(navigationModalVersion=True), lambda v: v.update(expected='not-found'),
                     lambda v: v['records'][0].update(rootAlive=1), lambda v: v['records'][0].update(callbackEpochMs=20001),
                     lambda v: v['records'][0]['event'].update(lookupGeneration=True),
                     lambda v: v['records'][0]['event'].update(origin='http://user:secret@owned.invalid'),
                     lambda v: v['records'][0].update(modalId='private-name'),
                     lambda v: v['records'][0].update(selectedButton=1024)):
            source.edit = edit
            with self.subTest(edit=edit), self.assertRaises(NativeUIError):
                source.reader().read(RUN)
        request = dict(schemaVersion=1, commandId='a' * 32, action='feature-navigation-modals', runId=RUN)
        fixture = FixtureState();fixture.set_client_command(request)
        for edit in ({'commandId': 'ios-' + 'a' * 32}, {'schemaVersion': True}, {'modalId': 'a' * 32},
                     {'expected': 'not-found'}, {'runId': RUN + '\n'}):
            with self.subTest(edit=edit), self.assertRaises((NativeUIError, ValueError)):
                command(request | edit)
            with self.assertRaises(ValueError):
                fixture.set_client_command(request | edit)

    def test_actual_probe_and_android_dispatch_use_original_native_packet_and_fixed_private_file(self):
        program = r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=0,files=[];const Test={featureNavigationModals:c=>{calls++;return {commandId:c.commandId,original:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'b'.repeat(32),action:'feature-navigation-modals',runId:'a'.repeat(32)};
applyAndroidControlCommand(c);if(calls!==1||!files[0].v.original||files[0].name!=='feature-navigation-modals.json')throw Error('original modal source absent');
for(const edit of [{expected:'not-found'},{modalId:c.runId},{schemaVersion:true},{commandId:'ios-'+c.commandId},{runId:c.runId+'\n'}])applyClientCommand({...c,...edit});
if(calls!==1)throw Error('unsafe command accepted');delete Test.featureNavigationModals;
applyClientCommand({...c,commandId:'c'.repeat(32)});if(files[1].v.status!=='unavailable')throw Error('missing hook became absent success');
'''.replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_reused_command_identity_cannot_be_reissued_with_a_new_source_cursor(self):
        for source in (Boundary(), replies.Boundary()):
            reader = source.reader()
            with patch('adapters.native_navigation_modals.uuid.uuid4', return_value=SimpleNamespace(hex='a' * 32)):
                reader.read(RUN)
                with self.assertRaises(NativeUIError):
                    reader.read(RUN)
            self.assertEqual(1, len(source.commands))


if __name__ == '__main__':
    unittest.main()
