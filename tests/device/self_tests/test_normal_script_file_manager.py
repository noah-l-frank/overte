"""Real ownership/files/picker logic; native UI/service boundaries are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_script_files import OwnedScriptFiles
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUIError
from adapters.token_script_file_ui import TokenScriptFilePicker
from self_tests.test_native_script_files import Boundary as FilesBoundary, RUN
from self_tests.test_normal_script_manager import Boundary as ManagerBoundary, BINDING as URL_BINDING
from self_tests.test_token_script_file_ui import NativeBoundary as PickerBoundary

BINDING = URL_BINDING | {'processIdentity': '31:original-start'}


class ScriptFileManagerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name); os.chmod(self.path, 0o700)
        self.storage = FilesBoundary(self.path)
        self.files = OwnedScriptFiles(self.storage.native(), PrivateFeatureState(self.path / 'files.json'), BINDING)
        self.directory = self.files.stage(RUN)
        self.native = ManagerBoundary(self.path)
        self.picker_io = PickerBoundary(self.storage.root)
        original = self.picker_io.activate
        def input(identifier, **kwargs):
            before = self.native.store.read()
            if identifier == 'scripts.from-file':
                self.assertTrue(before['pickerOwned'])
                if self.picker_io.fault != 'open':
                    self.picker_io.chosen = []; self.picker_io.review = None; self.picker_io.primary = -1
            if identifier == 'script-file.confirm':
                self.assertTrue(before['loadAttempted']); self.assertIsNotNone(before['source'])
            original(identifier, **kwargs)
            if identifier == 'script-file.confirm' and self.picker_io.accepted:
                actual = self.picker_io.accepted[-1]
                self.native.rows.append(dict(url=actual, path=actual))
        self.picker_io.activate = input

    def flow(self, **changes):
        picker = TokenScriptFilePicker(self.picker_io, self.directory,
            monotonic=lambda: self.picker_io.clock, sleep=self.picker_io.sleep)
        values = dict(source_kind='script-file-bundle', file_owner=self.files, file_picker=picker,
            monotonic=lambda: self.native.clock, sleep=self.native.sleep)
        values.update(changes)
        return NormalScriptManager(self.native, self.native.observe, self.native.store, BINDING, **values)

    def opened(self):
        flow = self.flow(); flow.open(); flow.file_picker_open(); return flow

    def test_cancel_two_primary_sources_stop_and_separate_file_retirement_use_original_paths(self):
        flow = self.opened(); flow.file_picker_cancel()
        for resource in ('script.js', 'script-bundle/main.js'):
            flow = self.flow(); flow.file_picker_open(); flow.file_picker_choose(resource)
            actual = self.picker_io.accepted[-1]
            self.assertEqual(self.directory + '/' + resource, actual)
            self.assertEqual(actual, self.native.store.read()['source'])
            self.assertTrue(self.native.store.read()['loadAttempted'])
            flow = self.flow(); flow.stop_source(actual)
            self.assertFalse(self.native.store.read()['loadAttempted'])
        self.flow().close(); self.assertIsNone(self.native.store.read())
        self.assertTrue(self.storage.root.exists()); self.files.release()
        self.assertFalse(self.storage.root.exists()); self.assertIsNone(self.files.store.read())
        self.assertNotIn('submit', self.native.calls)

    def test_ignored_open_can_retire_only_after_independently_observed_picker_absence(self):
        self.picker_io.fault = 'open'; flow = self.flow(); flow.open()
        with self.assertRaises(NativeUIError): flow.file_picker_open()
        self.assertTrue(self.native.store.read()['pickerOwned'])
        self.assertFalse(self.picker_io.opened)
        self.flow().close(); self.assertIsNone(self.native.store.read())
        self.assertEqual(1, self.picker_io.actions.count('scripts.from-file'))
        self.assertGreaterEqual(self.picker_io.clock, 0.3)

    def test_owned_feature_panel_open_is_not_replayed_after_ignored_delivery(self):
        def ignored():self.native.calls.append('open-manager')
        self.native.open_manager=ignored
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.flow().open()
        self.assertEqual(1,self.native.calls.count('open-manager'))
        self.assertTrue(self.native.store.read()['managerOwned'])

    def test_owned_feature_panel_lost_ack_can_resume_only_by_reading_actual_open_ui(self):
        original=self.native.open_manager
        def lost():original();raise NativeUIError('synthetic lost open acknowledgment')
        self.native.open_manager=lost
        with self.assertRaises(NativeUIError):self.flow().open()
        self.flow().open()
        self.assertEqual(1,self.native.calls.count('open-manager'));self.assertTrue(self.native.manager)

    def test_closed_object_can_repeat_cleanup_but_cannot_reacquire_an_absent_lease(self):
        flow=self.flow();flow.open();flow.close();before=list(self.native.calls)
        flow.close()
        with self.assertRaises(NativeUIError):flow.open()
        self.assertEqual(before,self.native.calls);self.assertIsNone(self.native.store.read())

    def test_retired_object_cannot_close_a_new_scope_after_its_original_journal_was_removed(self):
        old=self.flow();old.open();old.close()
        current=self.flow();current.open();before=list(self.native.calls)
        with self.assertRaises(NativeUIError):old.close()
        self.assertEqual(before,self.native.calls);self.assertTrue(self.native.manager)

    def test_uncertain_or_ignored_selection_is_never_replayed_and_retains_load_intent(self):
        for fault in ('row', 'confirm'):
            with self.subTest(fault=fault):
                flow = self.opened(); self.picker_io.fault = fault
                with self.assertRaises(NativeUIError): flow.file_picker_choose('script.js')
                before = list(self.picker_io.actions)
                with self.assertRaises(NativeUIError): self.flow().file_picker_choose('script.js')
                self.assertEqual(before, self.picker_io.actions)
                self.assertTrue(self.native.store.read()['loadAttempted'])
                self.picker_io.fault = ''
                self.flow().file_picker_cancel()
                self.flow().stop_source(self.native.store.read()['source'])
                self.flow().close()
                self.picker_io.chosen = []

    def test_failed_cancel_keeps_a_valid_recoverable_manager_journal(self):
        flow = self.opened(); self.picker_io.fault = 'cancel'
        with self.assertRaises(NativeUIError): flow.close()
        state = self.native.store.read()
        self.assertTrue(state['pickerOwned']); self.assertTrue(state['managerOwned'])
        self.assertNotIn('close', self.native.calls)
        self.picker_io.fault = ''; self.flow().file_picker_cancel(); self.flow().close()
        self.assertIsNone(self.native.store.read())

    def test_ignored_stop_cannot_discard_or_rebind_original_file_and_script_intents(self):
        flow = self.opened(); flow.file_picker_choose('script.js'); self.native.ignore_stop = True
        with self.assertRaises(NativeUIError): flow.stop_source(self.native.store.read()['source'])
        with self.assertRaises(NativeUIError): self.flow().close()
        self.assertTrue(self.native.store.read()['loadAttempted'])
        self.assertIsNotNone(self.files.store.read()); self.assertTrue(self.storage.root.exists())
        self.native.ignore_stop = False; flow = self.flow(); flow.open()
        flow.stop_source(flow.state['source']); flow.close()

    def test_preexisting_picker_and_foreign_same_basename_are_not_adopted(self):
        flow = self.flow(); flow.open(); self.picker_io.opened = True
        with self.assertRaises(NativeUIError): flow.file_picker_open()
        self.assertFalse(self.native.store.read()['pickerOwned'])
        self.assertEqual([], self.picker_io.actions)
        self.picker_io.opened = False; flow.file_picker_open()
        self.native.rows = [dict(url='file:///foreign/SCRIPT.JS', path='foreign')]
        with self.assertRaises(NativeUIError): flow.file_picker_choose('script.js')
        self.assertFalse(self.native.store.read()['loadAttempted']); self.assertEqual([], self.picker_io.accepted)
        flow.file_picker_cancel(); flow.close()
        self.assertEqual(['file:///foreign/SCRIPT.JS'], [row['url'] for row in self.native.rows])

    def test_changed_original_bytes_block_selection_but_preserve_cancel_and_cleanup_intent(self):
        flow = self.opened(); (self.storage.root / 'companion.js').write_bytes(b'changed')
        before = list(self.picker_io.actions)
        with self.assertRaises(NativeUIError): flow.file_picker_choose('script.js')
        self.assertEqual(before, self.picker_io.actions); self.assertFalse(self.native.store.read()['loadAttempted'])
        self.flow().file_picker_cancel(); self.flow().close()
        self.storage.fault = 'ignored-release'
        with self.assertRaises(NativeUIError): self.files.release()
        self.assertIsNotNone(self.files.store.read())

    def test_guessed_root_source_owner_or_new_process_cannot_adopt_existing_intent(self):
        flow = self.opened(); state = deepcopy(self.native.store.read())
        for field, value in (('source', 'file:///foreign/script.js'),
                             ('binding', BINDING | {'processIdentity': '32:new-start'})):
            corrupt = state | {field: value}; self.native.store.write(corrupt, state)
            with self.subTest(field=field), self.assertRaises(NativeUIError): self.flow()
            self.native.store.write(state, corrupt)
        corrupt = deepcopy(state); corrupt['fileOwner']['ownerToken'] = 'f' * 64
        self.native.store.write(corrupt, state)
        with self.assertRaises(NativeUIError): self.flow()
        self.native.store.write(state, corrupt)
        self.flow().file_picker_cancel(); self.flow().close()

    def test_file_scope_cannot_bypass_picker_or_broaden_existing_public_url_operations(self):
        flow = self.opened(); before = list(self.native.calls)
        for resource in ('../script.js', 'companion.js', 'script-bundle/companion.js'):
            with self.subTest(resource=resource), self.assertRaises(NativeUIError): flow.file_picker_choose(resource)
        with self.assertRaises(NativeUIError): flow.load_source(self.directory + '/script.js')
        with self.assertRaises(NativeUIError): flow.invoke('scripts.load-url', {'url': self.directory + '/script.js'})
        self.assertEqual(before, self.native.calls)
        plain = NormalScriptManager(self.native, self.native.observe, PrivateFeatureState(self.path / 'other.json'), BINDING)
        with self.assertRaises((ValueError, NativeUIError)):
            plain.invoke('scripts.load-url', {'url': self.directory + '/script.js'})
        self.assertEqual(before, self.native.calls)


if __name__ == '__main__': unittest.main()
