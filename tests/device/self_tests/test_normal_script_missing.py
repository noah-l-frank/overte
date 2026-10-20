"""Actual manager/reader/journal; only native UI and load callbacks simulated."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_script_manager import NormalScriptManager, missing_script_url
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_observation import Boundary as Execution
from self_tests.test_native_script_loads import event, history
from self_tests.test_normal_script_manager import Boundary, BINDING, SOURCE

URL = 'http://fixture.test:12345/feature-fixture/v1/runs/' + 'a' * 32 + '/tickets/' + 'b' * 32 + '/missing.js'


class MissingScriptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        os.chmod(temporary.name, 0o700)
        self.ui, self.native = Boundary(temporary.name), Execution()
        self.events, self.ignore, self.lost = [], False, False
        self.native.mutate = self.observe
        self.reader = self.native.reader()
        self.binding = BINDING | {'processIdentity': '31:original'}
        submit = self.ui.submit_url
        def deliver():
            submit()
            if not self.ignore:
                self.events.append(event(len(self.events) + 1, url=self.ui.url, callbackEpochMs=20000))
            if self.lost: raise NativeUIError('Synthetic lost SDK receipt')
        self.ui.submit_url = deliver

    def observe(self, packet):
        packet['source']['engines'] = []
        history(packet, self.events)

    def flow(self, **kwargs):
        return NormalScriptManager(self.ui, self.ui.observe, self.ui.store, self.binding,
            source_kind='feature-script-missing', monotonic=lambda: self.ui.clock,
            sleep=self.ui.sleep, **kwargs)

    def load(self):
        flow = self.flow(); flow.open(); flow.load_missing(URL, self.reader)
        return flow

    def test_one_normal_submit_original_callback_and_explicit_independent_retirement(self):
        flow = self.load()
        self.assertTrue(self.ui.store.read()['loadAttempted'])
        result = self.flow().settle_missing(self.native.reader())
        self.assertEqual(self.events[0], result)
        self.assertEqual('NotFound', result['status'])
        self.assertEqual('settled', self.ui.store.read()['missingLoad']['phase'])
        self.flow().close(); self.assertIsNone(self.ui.store.read())
        self.assertEqual(1, self.ui.calls.count('submit'))
        self.assertNotIn('stop', self.ui.calls)

    def test_ignored_input_no_callback_and_incomplete_cleanup_cannot_pass_or_replay(self):
        self.ignore = True; self.load()
        for action in (lambda: self.flow().settle_missing(self.native.reader()),
                       lambda: self.flow().load_missing(URL, self.native.reader()), self.flow().close):
            with self.assertRaises(NativeUIError): action()
        self.assertEqual('issued', self.ui.store.read()['missingLoad']['phase'])
        self.assertEqual(1, self.ui.calls.count('submit'))

    def test_lost_input_ack_reconstructs_only_reads_and_closes_without_resubmission(self):
        self.lost = True
        with self.assertRaises(NativeUIError): self.load()
        self.assertTrue(self.ui.store.read()['dialogOwned'])
        self.assertEqual(self.events[0], self.flow().settle_missing(self.native.reader()))
        self.flow().close(); self.assertIsNone(self.ui.store.read())
        self.assertEqual(1, self.ui.calls.count('submit'))

    def test_historical_callback_does_not_qualify_an_ignored_current_input(self):
        self.events = [event(url=URL, callbackEpochMs=19001)]
        self.ignore = True; self.load()
        with self.assertRaises(NativeUIError): self.flow().settle_missing(self.native.reader())
        self.assertTrue(self.ui.store.read()['loadAttempted'])

    def test_reconstructed_reader_cannot_accept_rewritten_or_foreign_history(self):
        self.events = [event(url=URL.replace('missing.js', 'other.js'), callbackEpochMs=19001)]
        self.load(); original = deepcopy(self.events)
        for fault in ('rewritten', 'foreign-instance', 'new-native-birth', 'missing-extension'):
            self.events = deepcopy(original)
            def observe(packet):
                self.observe(packet)
                if fault == 'rewritten': packet['source']['loads']['events'][0]['status'] = 'Timeout'
                elif fault == 'foreign-instance': packet['source']['loads']['instance'] = 'f' * 32
                elif fault == 'new-native-birth': packet['instance'] = 'f' * 32
                else:
                    del packet['source']['loads']; del packet['source']['loadSourceVersion']
            self.native.mutate = observe
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                self.flow().settle_missing(self.native.reader())
            self.assertTrue(self.ui.store.read()['loadAttempted'])

    def test_foreign_full_url_success_multiple_callbacks_or_live_engine_retain_intent(self):
        self.load(); original = deepcopy(self.events)
        for fault in ('foreign-url', 'success', 'duplicate', 'engine'):
            self.events = deepcopy(original)
            if fault == 'foreign-url': self.events[0]['url'] = URL.replace('fixture.test', 'foreign.test')
            elif fault == 'success': self.events[0].update(success=True, status='Cached')
            elif fault == 'duplicate': self.events.append(event(2, url=URL, callbackEpochMs=20000))
            def observe(packet):
                self.observe(packet)
                if fault == 'engine': packet['source']['engines'] = [dict(self.native.engine, url=URL)]
            self.native.mutate = observe
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                self.flow().settle_missing(self.native.reader())
            self.assertTrue(self.ui.store.read()['loadAttempted'])

    def test_actual_other_terminal_failure_is_preserved_without_claiming_not_found(self):
        self.load(); self.events[0]['status'] = 'AccessDenied'
        self.assertEqual('AccessDenied', self.flow().settle_missing(self.native.reader())['status'])

    def test_settled_callback_prefix_cannot_be_replaced_on_reconstruction(self):
        self.load(); self.flow().settle_missing(self.native.reader())
        self.events[0]['status'] = 'Timeout'
        with self.assertRaises(NativeUIError): self.flow().settle_missing(self.native.reader())
        self.assertEqual('NotFound', self.ui.store.read()['missingLoad']['completed']['event']['status'])

    def test_corrupt_phase_result_or_binding_journal_is_rejected_before_io(self):
        self.load(); self.flow().settle_missing(self.native.reader())
        original = self.ui.store.read(); before = len(self.native.commands)
        for fault in ('result', 'phase', 'pid', 'version', 'scope'):
            changed = deepcopy(original)
            if fault == 'result': changed['missingLoad']['completed']['event']['status'] = 'Timeout'
            elif fault == 'phase': changed['missingLoad']['phase'] = 'issued'
            elif fault == 'pid': changed['missingLoad']['pid'] = 32
            elif fault == 'version': changed['missingLoadVersion'] = True
            else: changed['sourceKind'] = 'scripts'
            self.ui.store.write(changed, self.ui.store.read())
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.flow()
        self.assertEqual(before, len(self.native.commands))

    def test_actual_service_row_disagrees_with_empty_engine_source(self):
        self.load(); self.ui.rows = [dict(url=URL, path=URL)]
        with self.assertRaises(NativeUIError): self.flow().settle_missing(self.native.reader())
        self.assertTrue(self.ui.store.read()['loadAttempted'])

    def test_binding_pid_or_source_loss_prevents_reads_and_claims(self):
        self.load(); before = len(self.native.commands)
        for fault in ('pid', 'guard'):
            reader = self.native.reader()
            if fault == 'pid': reader.pid = 32
            else: reader.guard = lambda: False
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): self.flow().settle_missing(reader)
        self.assertEqual(before, len(self.native.commands))

    def test_missing_mode_does_not_broaden_existing_public_foundation_or_file_scope(self):
        flow = self.flow(); flow.open()
        for action in (lambda: flow.invoke('scripts.load-url', {'url': URL}),
                       lambda: flow.load_source(URL), lambda: flow.stop_source(URL),
                       lambda: flow.load_missing(SOURCE, self.reader),
                       lambda: self.ui.flow().validate_url(URL)):
            with self.assertRaises(NativeUIError): action()
        self.assertNotIn('submit', self.ui.calls)

    def test_only_closed_owned_ticket_missing_url_is_accepted(self):
        self.assertEqual(URL, missing_script_url(URL))
        for url in (URL.replace('missing.js', 'client.js'), URL.replace('/tickets/', '/current/'),
                    URL + '?', URL + '#', URL.replace('http://', 'file://'),
                    URL.replace('fixture.test', 'user:secret@fixture.test'), URL.replace('12345', '99999'),
                    URL.replace('missing', '%6dissing'), URL + '\n', URL.replace('/missing', '/../missing')):
            with self.subTest(url=url), self.assertRaises(NativeUIError): missing_script_url(url)

    def test_native_input_allowlist_includes_only_missing_feature_resource(self):
        import re
        native = (Path(__file__).resolve().parents[1] / 'native/NormalScriptControls.h').read_text()
        encoded = re.search(r'QRegularExpression\("(.*feature-fixture.*)"\)', native).group(1)
        pattern = encoded.replace('\\\\', '\\').replace('\\z', '\\Z')
        from urllib.parse import urlsplit
        self.assertIsNotNone(re.fullmatch(pattern, urlsplit(URL).path))
        for path in (urlsplit(URL.replace('missing.js', 'client.js')).path,
                     urlsplit(URL.replace('missing.js', 'script-bundle/main.js')).path):
            self.assertIsNone(re.fullmatch(pattern, path))


if __name__ == '__main__': unittest.main()
