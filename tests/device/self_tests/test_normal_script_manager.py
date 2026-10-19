"""Native-boundary counterexamples for ordinary script-manager adapters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.android_script_ui import AndroidScriptUI
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager, diagnostic, read_native_diagnostic
from adapters.normal_ui import NativeUI, NativeUIError, Locator

SOURCE = 'http://fixture.test/script-management/' + 'a' * 32 + '/client.js'
BINDING = dict(sourceRevision='b' * 40, artifactSha256='c' * 64,
    processIdentity='21:12', sessionId='native-session', generation=1, targetFingerprint='d' * 64)


class Boundary:
    """Only normal input/native reads are replaced; use the real flow and store."""
    def __init__(self, directory):
        self.store = PrivateFeatureState(Path(directory) / 'scripts.json')
        self.rows, self.calls = [], []
        self.tablet = self.manager = self.dialog = False
        self.sequence = 0
        self.clock = 0.0
        self.ignore_stop = self.fail_submit = self.foreign_row = False
        self.instance = 'e' * 32
        self.after_values = []

    def flow(self, binding=None):
        return NormalScriptManager(self, self.observe, self.store, binding or BINDING,
            monotonic=lambda: self.clock, sleep=self.sleep)

    def sleep(self, seconds):
        self.clock += seconds

    def observe(self, after):
        self.after_values.append(after)
        self.sequence += 1
        return dict(schemaVersion=1, instance=self.instance, sampleSequence=self.sequence,
            sampleEpochMs=10000 + self.sequence, complete=True, scripts=deepcopy(self.rows)), 10000 + self.sequence

    def tablet_visible(self): return self.tablet
    def manager_visible(self): return self.manager
    def open_tablet(self): self.tablet = True; self.calls.append('open-tablet')
    def open_manager(self): self.manager = True; self.calls.append('open-manager')
    def wait_manager(self):
        if not self.manager: raise NativeUIError('not ready')
    def open_url_dialog(self): self.dialog = True; self.calls.append('open-dialog')
    def fill_url(self, url): self.url = url; self.calls.append('fill')
    def submit_url(self):
        self.calls.append('submit')
        if not self.url.endswith('missing.js'):
            self.rows.append(dict(url=self.url, path=self.url))
        if self.fail_submit: raise NativeUIError('uncertain native response')
        self.dialog = False
    def wait_dialog_absent(self):
        if self.dialog: raise NativeUIError('dialog retained')
    def cancel_dialog(self): self.dialog = False; self.calls.append('cancel')
    def close_tablet(self): self.manager = self.tablet = False; self.calls.append('close')
    def wait_tablet_absent(self):
        if self.tablet: raise NativeUIError('panel retained')
    def release(self): self.calls.append('release')
    def check_row(self, index, name, action):
        if self.foreign_row: raise NativeUIError('foreign row')
        self.calls.append('check-row')
    def row_action(self, index, name, action):
        self.calls.append(action)
        if action == 'stop' and not self.ignore_stop: self.rows.pop(index)


class NormalScriptManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.chmod(self.temp.name, 0o700)
        self.native = Boundary(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def invoke(self, operation, arguments=None):
        return self.native.flow().invoke(operation, arguments or {})
    def load(self):
        self.invoke('scripts.manager.open')
        self.invoke('scripts.load-url', {'url': SOURCE})

    def test_actual_load_restart_stop_missing_and_idempotent_cleanup(self):
        self.load()
        self.assertEqual([dict(url=SOURCE, path=SOURCE)], self.native.rows)
        self.invoke('scripts.restart', {'url': SOURCE})
        self.invoke('scripts.stop', {'url': SOURCE})
        self.invoke('scripts.stop', {'url': SOURCE})
        self.invoke('scripts.load-url', {'url': SOURCE.replace('client.js', 'missing.js')})
        self.invoke('scripts.stop', {'url': SOURCE})
        self.assertEqual({'performed': True}, self.invoke('scripts.manager.close'))
        self.assertIsNone(self.native.store.read())
        self.invoke('scripts.manager.close')
        self.assertEqual(1, self.native.calls.count('restart'))
        self.assertEqual(1, self.native.calls.count('stop'))
        self.assertEqual(2, self.native.calls.count('submit'))

    def test_uncertain_submit_is_not_replayed_and_retains_cleanup_intent(self):
        self.native.fail_submit = True
        with self.assertRaises(NativeUIError): self.load()
        state = self.native.store.read()
        self.assertTrue(state['dialogOwned'])
        self.assertTrue(state['loadAttempted'])
        self.assertEqual(1, self.native.calls.count('submit'))
        self.invoke('scripts.stop', {'url': SOURCE})
        self.invoke('scripts.manager.close')
        self.assertIsNone(self.native.store.read())

    def test_ignored_stop_never_retires_ownership_or_returns_success(self):
        self.load()
        self.native.ignore_stop = True
        with self.assertRaises(NativeUIError): self.invoke('scripts.stop', {'url': SOURCE})
        self.assertTrue(self.native.store.read()['loadAttempted'])
        with self.assertRaises(NativeUIError): self.invoke('scripts.manager.close')
        self.assertIsNotNone(self.native.store.read())
        self.assertEqual(1, self.native.calls.count('stop'))

    def test_foreign_existing_source_or_basename_is_not_adopted(self):
        for url in (SOURCE, SOURCE.replace('fixture.test', 'other.test')):
            with self.subTest(url=url):
                self.native.rows = [dict(url=url, path=url)]
                self.invoke('scripts.manager.open')
                with self.assertRaises(NativeUIError): self.invoke('scripts.load-url', {'url': SOURCE})
                self.assertNotIn('submit', self.native.calls)
                self.invoke('scripts.manager.close')

    def test_foreign_source_after_our_stop_cannot_be_stopped_as_owned(self):
        self.load()
        self.invoke('scripts.stop', {'url': SOURCE})
        self.native.rows = [dict(url=SOURCE, path=SOURCE)]
        with self.assertRaises(NativeUIError): self.invoke('scripts.stop', {'url': SOURCE})
        self.assertEqual(1, self.native.calls.count('stop'))

    def test_row_order_ties_and_foreign_labels_fail_before_mutation(self):
        self.load()
        self.native.rows.append(dict(url='http://other/client.js', path='http://other/client.js'))
        with self.assertRaises(NativeUIError): self.invoke('scripts.restart', {'url': SOURCE})
        self.native.rows.pop()
        self.native.foreign_row = True
        with self.assertRaises(NativeUIError): self.invoke('scripts.restart', {'url': SOURCE})
        self.assertNotIn('restart', self.native.calls)

    def test_process_candidate_session_and_source_changes_are_rejected(self):
        self.load()
        for key, value in (('processIdentity', '22:12'), ('generation', 2),
                           ('artifactSha256', 'f' * 64), ('targetFingerprint', 'f' * 64)):
            with self.subTest(key=key), self.assertRaises(NativeUIError):
                self.native.flow(BINDING | {key: value})
        with self.assertRaises(NativeUIError):
            self.invoke('scripts.load-url', {'url': SOURCE.replace('a' * 32, 'f' * 32)})
        self.native.instance = 'f' * 32
        with self.assertRaises(NativeUIError): self.invoke('scripts.stop', {'url': SOURCE})

    def test_preexisting_panels_are_not_closed_or_adopted(self):
        self.native.tablet = True
        with self.assertRaises(NativeUIError): self.invoke('scripts.manager.open')
        self.assertEqual([], self.native.calls)

    def test_native_rows_must_be_complete_fresh_typed_and_unambiguous(self):
        value, epoch = self.native.observe(0)
        for changes in ({'complete': False}, {'complete': 1}, {'schemaVersion': True},
                        {'sampleEpochMs': epoch - 1501}, {'sampleEpochMs': epoch + 251},
                        {'scripts': [dict(url=SOURCE, path=SOURCE)] * 2}, {'scripts': None}):
            with self.subTest(changes=changes), self.assertRaises(NativeUIError):
                diagnostic(value | changes, epoch)

    def test_original_reader_polls_advancement_without_relabeling_old_bytes(self):
        first, epoch = self.native.observe(0)
        second = first | {'sampleSequence': first['sampleSequence'] + 1}
        captures = iter((json.dumps(first), json.dumps(first), json.dumps(second)))
        clock = [0.0]
        def sleep(seconds): clock[0] += seconds
        result, measured_epoch = read_native_diagnostic(lambda: next(captures), lambda: epoch,
            lambda: True, first['sampleSequence'], monotonic=lambda: clock[0], sleep=sleep)
        self.assertEqual(second, result)
        self.assertEqual(epoch, measured_epoch)
        self.assertGreaterEqual(clock[0], 0.2)

    def test_original_reader_rejects_nonadvancing_stale_foreign_or_failed_reads(self):
        value, epoch = self.native.observe(0)
        for mode in ('old-sequence', 'stale', 'duplicate-key', 'lost-process', 'native-error'):
            with self.subTest(mode=mode):
                clock = [0.0]
                def sleep(seconds): clock[0] += seconds
                def read():
                    if mode == 'native-error': raise RuntimeError('secret selector')
                    if mode == 'duplicate-key': return '{"schemaVersion":1,"schemaVersion":1}'
                    return json.dumps(value)
                with self.assertRaises(NativeUIError) as error:
                    read_native_diagnostic(read, lambda: epoch + (1501 if mode == 'stale' else 0),
                        lambda: mode != 'lost-process', value['sampleSequence'] if mode == 'old-sequence' else 0,
                        monotonic=lambda: clock[0], sleep=sleep)
                self.assertNotIn('secret', str(error.exception))

    def test_correlated_reader_waits_for_current_request_and_rejects_foreign_receipts(self):
        value, epoch = self.native.observe(0)
        request = '1' * 32
        captures = iter(('', json.dumps(value | {'requestId': '2' * 32, 'sampleEpochMs': 1}),
                         json.dumps(value | {'requestId': request})))
        clock = [0.0]
        def sleep(seconds): clock[0] += seconds
        result, _ = read_native_diagnostic(lambda: next(captures), lambda: epoch, lambda: True, 0,
            expected_request=request, monotonic=lambda: clock[0], sleep=sleep)
        self.assertEqual(request, result['requestId'])
        self.assertGreaterEqual(clock[0], 0.2)

    def test_nonnative_input_locator_classes_and_unmeasured_text_are_rejected(self):
        for kind in ('android.widget.Button', 'arbitrary.selector', '*'):
            with self.assertRaises(NativeUIError): Locator('class name', kind)
        class Transport:
            def call(self, method, path, body=None):
                if path.endswith('/elements'):
                    return [{'element-6066-11e4-a52e-4f735466cecf': 'actual'}]
                if path.endswith('/text'): return {'expected': 'input'}
                return True
        with self.assertRaises(NativeUIError):
            NativeUI(Transport(), 'native', lambda: True).text(Locator('id', 'actual'))

    def test_private_state_rejects_links_public_permissions_and_concurrent_change(self):
        self.invoke('scripts.manager.open')
        path = self.native.store.path
        os.chmod(path, 0o644)
        with self.assertRaises(NativeUIError): self.native.store.read()
        os.chmod(path, 0o600)
        flow = self.native.flow()
        original = self.native.store.read()
        self.native.store.write(original | {'dialogOwned': True}, original)
        with self.assertRaises(NativeUIError): flow.mark(source=SOURCE)
        path.unlink()
        path.symlink_to(Path(self.temp.name) / 'foreign')
        with self.assertRaises(NativeUIError): self.native.store.read()

    def test_android_ui_rejects_flattened_foreign_or_ambiguous_row_identity(self):
        class Transport:
            def call(self, method, path, body=None): return self.source
        transport = Transport()
        ui = AndroidScriptUI(NativeUI(transport, 'native', lambda: True), 'io.github.noah_be.overte.phone')
        package = ui.package
        transport.source = '<hierarchy><node>' + ''.join(
            '<node package="' + package + '" class="' + kind + '" text="' + text +
            '" resource-id="' + identifier + '"/>' for kind, text, identifier in (
                ('android.widget.TextView', 'client.js', ''),
                ('android.widget.Button', 'Restart', package + ':id/scriptRestart1'),
                ('android.widget.Button', 'Stop', package + ':id/scriptStop1'))) + '</node></hierarchy>'
        ui.check_row(1, 'client.js', 'stop')
        with self.assertRaises(NativeUIError): ui.check_row(1, 'foreign.js', 'stop')
        transport.source = transport.source.replace('scriptRestart1', 'scriptRestart2')
        with self.assertRaises(NativeUIError): ui.check_row(1, 'client.js', 'stop')

    def test_actual_probe_diagnostic_reads_native_service_and_marks_failures_incomplete(self):
        probe = (Path(__file__).resolve().parents[1] / 'probe/overte_e2e_probe.js').read_text()
        start = probe.index('    var normalFeatureInstance =')
        end = probe.index('    var phoneTouchHistory', start)
        program = '''const vm = require('vm'); let result;
const context = {Uuid:{generate:()=>'{aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa}'},
 Test:{saveObject:(value,name)=>{result={value,name}}},
 ScriptDiscoveryService:{getRunning:()=>[{url:'http://actual/source.js',path:'native/path'}]}};
vm.createContext(context); vm.runInContext(SOURCE, context);
context.saveNormalFeatureObservation(1234,7);
if(!result.value.complete || result.value.scripts[0].path!=='native/path' || result.value.sampleSequence!==7)process.exit(1);
context.ScriptDiscoveryService.getRunning=()=>{throw Error('native failure')};
context.saveNormalFeatureObservation(1235,8);
if(result.value.complete || result.value.scripts.length || result.name!=='normal-feature-observation.json')process.exit(2);
'''.replace('SOURCE', json.dumps(probe[start:end]))
        subprocess.run(['node', '-e', program], check=True, timeout=10, capture_output=True)

    def test_actual_read_only_command_correlates_deduplicates_and_filters_actual_avatar_ownership(self):
        probe = (Path(__file__).resolve().parents[1] / 'probe/overte_e2e_probe.js').read_text()
        start = probe.index('    var normalFeatureInstance =')
        end = probe.index('    var phoneTouchHistory', start)
        branch = probe.index('    function applyClientCommand(command)')
        branch_end = probe.index('        if (command && command.schemaVersion === 1\n                && /^ios-', branch)
        source = probe[start:end] + probe[branch:branch_end] + '\n return false; }'
        program = '''const vm=require('vm'); let result, reads=0;
const owner='{11111111-1111-1111-1111-111111111111}';
const context={Uuid:{generate:()=>owner},Test:{saveObject:v=>{result=v}},
 ScriptDiscoveryService:{getRunning:()=>{reads++;return [{url:'http://actual/a.js',path:'actual'}]}},
 MyAvatar:{position:{x:0,y:0,z:0},sessionUUID:owner,SELF_ID:owner},
 Entities:{findEntities:()=>['owned','foreign'],getEntityProperties:id=>({name:id,type:'Box',entityHostType:'avatar',owningAvatarID:id==='owned'?owner:'{22222222-1111-1111-1111-111111111111}'})},
 objectKeysMatch:(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort())};
vm.createContext(context);vm.runInContext(SOURCE,context);
const command={schemaVersion:1,commandId:'a'.repeat(32),action:'normal-feature-observe',includeAvatarEntities:true};
context.applyClientCommand(command);
if(result.requestId!==command.commandId||result.sampleSequence!==1||!result.entitiesComplete||result.avatarEntities.length!==1||result.avatarEntities[0].name!=='owned')process.exit(1);
context.applyClientCommand(command);if(reads!==1)process.exit(2);
command.commandId='b'.repeat(32);command.includeAvatarEntities=false;context.applyClientCommand(command);
if(reads!==2||result.sampleSequence!==2||'avatarEntities' in result)process.exit(3);
'''.replace('SOURCE', json.dumps(source))
        subprocess.run(['node', '-e', program], check=True, timeout=10, capture_output=True)


if __name__ == '__main__': unittest.main()
