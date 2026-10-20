"""Original private protocol paths with deliberately synthetic GUI/settings.

These counterexamples validate test logic, not native compilation or devices.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_chat_view import NativeChatView, command, measured_view, validate
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source

RUN = 'a' * 32
TEXT = context(RUN)['unicode']


class Boundary:
    def __init__(self):
        self.clock = 0.; self.sequence = 0; self.commands = []; self.value = None
        self.ignored = False; self.alive = True; self.mutate = None
        self.source = dict(tabletShown=True, editorFocused=True, editorHasDraft=True,
            keyboard=dict(available=True, backend='native-touch-metrics', visible=True),
            ui=dict(present=True, generation='d' * 32, channel='domain', draft=TEXT,
                keyboardRequested=True, localMessages=[context(RUN)['reply']], domainMessages=[TEXT, TEXT],
                localRowCount=1, domainRowCount=2, visibleMessages=[TEXT, TEXT], visibleRowCount=2),
            storage=dict(kind='array', count=2, unowned=0,
                events=[dict(channel='domain', text=TEXT, timestamp=19000)] * 2, configSha256='b' * 64))

    def send(self, request):
        self.commands.append(deepcopy(request))
        if self.ignored: return
        self.sequence += 1
        self.value = dict(chatViewVersion=1, **{k: request[k] for k in ('commandId', 'runId')},
            instance='c' * 32, sequence=self.sequence, processId=123, capturedEpochMs=20000, source=deepcopy(self.source))
        if self.mutate: self.mutate(self.value)

    def read(self): return json.dumps(self.value) if self.value is not None else ''
    def sleep(self, value): self.clock += value
    def reader(self, **kwargs):
        return NativeChatView(self.send, self.read, lambda: 20000, lambda: self.alive, 123,
            monotonic=lambda: self.clock, sleep=self.sleep, **kwargs)


class ChatViewTests(unittest.TestCase):
    def test_actual_order_multiplicity_visible_model_and_storage_remain_separate(self):
        n = Boundary(); value = n.reader().read(RUN)
        self.assertEqual([TEXT, TEXT], measured_view(value)['messages'])
        self.assertEqual([context(RUN)['reply']], value['source']['ui']['localMessages'])
        # A wrong visible binding is retained as measured, not repaired from
        # selected Domain. The journey must fail its expected-visible check.
        n.source['ui']['visibleMessages'] = [context(RUN)['reply']]
        n.source['ui']['visibleRowCount'] = 1
        self.assertEqual([context(RUN)['reply']], measured_view(n.reader().read(RUN))['messages'])
        self.assertEqual([TEXT, TEXT], [e['text'] for e in value['source']['storage']['events']])

    def test_absence_has_no_invented_channel_and_hidden_editor_or_keyboard_blocks_closed_projection(self):
        n = Boundary(); n.source.update(ui={'present': False}, editorFocused=False, editorHasDraft=False,
            keyboard=dict(available=True, backend='native-touch-metrics', visible=False))
        self.assertEqual(dict(open=False, channel='none', draft='', focused=False, keyboard=False, messages=[]),
            measured_view(n.reader().read(RUN)))
        for edit in ({'editorFocused': True}, {'editorHasDraft': True},
                     {'keyboard': dict(available=True, backend='native-touch-metrics', visible=True)}):
            old = deepcopy(n.source); n.source.update(edit)
            with self.assertRaises(NativeUIError): measured_view(n.reader().read(RUN))
            n.source = old

    def test_keyboard_request_is_never_measured_keyboard_and_unavailable_is_not_false(self):
        n = Boundary(); n.source['ui']['keyboardRequested'] = False
        self.assertTrue(measured_view(n.reader().read(RUN))['keyboard'])
        n.source['keyboard'] = {'available': False}
        value = n.reader().read(RUN)
        with self.assertRaises(NativeUIError): measured_view(value)
        n.source['keyboard'] = dict(available=True, backend='qml-keyboardRaised', visible=True)
        with self.assertRaises(NativeUIError): n.reader().read(RUN)

    def test_closed_request_rejects_expected_values_inputs_foreign_namespace_and_newlines(self):
        request = dict(schemaVersion=1, commandId='f' * 32, action='feature-chat-view-observe', runId=RUN)
        self.assertEqual(request, command(request))
        for edit in ({'expected': []}, {'text': TEXT}, {'operation': 'clear'}, {'schemaVersion': True},
                     {'commandId': 'ios-' + 'f' * 32}, {'commandId': 'f' * 32 + '\n'}, {'runId': RUN + '\n'}):
            with self.assertRaises(NativeUIError): command(request | edit)
        self.assertEqual(request | {'commandId': 'ios-' + 'f' * 32},
            command(request | {'commandId': 'ios-' + 'f' * 32}, ios=True))

    def test_malformed_private_foreign_rows_extra_fields_and_impossible_counts_fail(self):
        n = Boundary(); value = n.reader().read(RUN); request = n.commands[-1]
        for field, edit in (
            ('ui', {'draft': 'private'}), ('ui', {'draft': context('f' * 32)['unicode']}),
            ('ui', {'domainMessages': ['private']}), ('ui', {'visibleMessages': [context('f' * 32)['reply']]}),
            ('ui', {'visibleRowCount': 1}), ('ui', {'keyboardRequested': 1}), ('ui', {'present': False}),
            ('ui', {'expected': []}), ('ui', {'generation': ''}), ('ui', {'channel': 'none'}),
            ('storage', {'count': 1}), ('storage', {'unowned': True}), ('storage', {'configSha256': 'bad'}),
            ('storage', {'kind': 'unset'}), ('storage', {'kind': 'string-list'}), ('storage', {'config': 'private'})):
            with self.subTest(field=field, edit=edit):
                changed = deepcopy(value); changed['source'][field].update(edit)
                with self.assertRaises(NativeUIError): validate(changed, request, 123, 20000)
        for edit in ({'timestamp': 20001}, {'timestamp': 0}, {'timestamp': True}, {'timestamp': '19000'},
                     {'text': 'private'}, {'channel': 'peer'}, {'sender': 'private'}):
            changed = deepcopy(value); changed['source']['storage']['events'][0].update(edit)
            with self.assertRaises(NativeUIError): validate(changed, request, 123, 20000)

    def test_original_storage_kinds_and_unowned_counts_are_preserved_without_private_content(self):
        n = Boundary()
        for kind in ('unset', 'null', 'empty-string', 'array', 'string-list'):
            n.source['storage'].update(kind=kind, events=[], count=0, unowned=0)
            self.assertEqual(kind, n.reader().read(RUN)['source']['storage']['kind'])
        n.source['storage'].update(kind='array', count=3, unowned=1,
            events=[dict(channel='domain', text=TEXT, timestamp=19000)] * 2)
        self.assertEqual(1, n.reader().read(RUN)['source']['storage']['unowned'])

    def test_missing_or_ignored_source_and_wrong_nonce_time_out_without_resending(self):
        for fault in ('ignored', 'wrong-nonce', 'missing-source'):
            n = Boundary()
            if fault == 'ignored': n.ignored = True
            elif fault == 'wrong-nonce': n.mutate = lambda v: v.update(commandId='e' * 32)
            else: n.mutate = lambda v: v.update(source={})
            with self.assertRaises(NativeUIError): n.reader().read(RUN)
            self.assertEqual(1, len(n.commands)); self.assertLessEqual(n.clock, 5)

    def test_stale_foreign_process_run_instance_and_replayed_sequence_fail(self):
        for edit in ({'processId': 124}, {'runId': 'f' * 32}, {'instance': 'f' * 32},
                     {'sequence': 1}, {'capturedEpochMs': 19999}, {'capturedEpochMs': 20251}):
            n = Boundary(); reader = n.reader(); reader.read(RUN); n.mutate = lambda v: v.update(edit)
            with self.assertRaises(NativeUIError): reader.read(RUN)
        n = Boundary(); reader = n.reader(); reader.read(RUN)
        with self.assertRaises(NativeUIError): reader.read('f' * 32)
        self.assertEqual(1, len(n.commands))

    def test_source_loss_late_transport_and_regressing_clock_are_not_fresh(self):
        for fault in ('late', 'rewind', 'dead'):
            n = Boundary(); original = n.send
            def send(request):
                original(request)
                if fault == 'dead': n.alive = False
                else: n.clock = 6 if fault == 'late' else -1
            n.send = send
            with self.assertRaises(NativeUIError): n.reader().read(RUN)

    def test_ios_preserves_native_epoch_and_rejects_native_clock_regression(self):
        n = Boundary(); reader = NativeChatView(n.send, n.read, lambda: 99900000, lambda: True, 123,
            ios=True, monotonic=lambda: n.clock, sleep=n.sleep)
        self.assertEqual(20000, reader.read(RUN)['capturedEpochMs'])
        self.assertTrue(n.commands[-1]['commandId'].startswith('ios-'))
        n.mutate = lambda v: v.update(capturedEpochMs=19999)
        with self.assertRaises(NativeUIError): reader.read(RUN)

    def test_duplicate_json_keys_and_nonfinite_sources_are_rejected(self):
        n = Boundary(); reader = n.reader(); original = n.read
        reader.original = lambda: original().replace('"processId": 123', '"processId": 123, "processId": 123')
        with self.assertRaises(NativeUIError): reader.read(RUN)
        reader = n.reader(); reader.original = lambda: original().replace('"processId": 123', '"processId": NaN')
        with self.assertRaises(NativeUIError): reader.read(RUN)

    def test_actual_fixture_admits_only_closed_ios_read_commands(self):
        state = FixtureState()
        request = dict(schemaVersion=1, commandId='ios-' + 'f' * 32, action='feature-chat-view-observe', runId=RUN)
        state.set_client_command(request)
        for edit in ({'expected': []}, {'text': 'private'}, {'runId': 'bad'}, {'commandId': 'f' * 32}):
            with self.assertRaises(ValueError): state.set_client_command(request | edit)

    def test_original_javascript_preserves_raw_native_result_and_missing_hook_is_unavailable(self):
        program = r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(value,keys)=>JSON.stringify(Object.keys(value).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];
const Test={featureChatViewObservation:c=>{calls++;return {commandId:c.commandId,source:{ui:{original:true}}};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:"a".repeat(32),action:"feature-chat-view-observe",runId:"b".repeat(32)};
applyClientCommand(c);
if(calls!==1||files.length!==1||!files[0].v.source.ui.original||files[0].name!=="feature-chat-view-observation.json")throw Error('original missing');
for(const edit of [{expected:[]},{text:'private'},{commandId:c.commandId+'\n'},{runId:c.runId+'\n'},{schemaVersion:true}])applyClientCommand({...c,...edit});
if(calls!==1)throw Error('desired state or invalid namespace accepted');
delete Test.featureChatViewObservation;applyAndroidControlCommand({...c,commandId:'c'.repeat(32)});
if(files.length!==2||files[1].v.available!==false)throw Error('missing hook green');
Test.featureChatViewObservation=c=>({commandId:'d'.repeat(32),source:{}});
applyClientCommand({...c,commandId:'ios-'+'e'.repeat(32)});
if(files.length!==3||files[2].v.available!==false)throw Error('foreign nonce accepted');
'''.replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__': unittest.main()
