"""Original Python restart/bookmark owners; Qt, kernel and app are host actors.

Actual one-send RestartInputs and PicoNavigation run against private files.
No device, service, subprocess, product process or VR renderer is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import sys
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.navigation_restart_proof import validate
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_location_bookmarks import NativeLocationBookmarks
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import PicoNavigation
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.restart_inputs import RestartInputs, RestartDeliveryUncertain
from adapters.token_places_ui import TokenPlacesUI
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from self_tests import test_navigation_bookmarks as bookmark_fixture
from self_tests.test_native_feature_observation import Boundary
from self_tests.test_native_process_presence import Boundary as Presence


class NavigationBookmarkRestartTests(unittest.TestCase):
    def setUp(self):
        self.f = bookmark_fixture.NavigationBookmarkTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.binding['processIdentity'] = '123:1111'
        self.widgets = self.f.widgets
        self.f.act('bookmark-add'); self.f.act('bookmark-rename')
        self.previous = self.f.owner().state
        self.paths = [self.f.path, self.f.path.with_name('restart-owner.json'), self.f.path.with_name('new-bookmarks.json')]
        self.inputs = RestartInputs(PrivateFeatureState(self.f.path.with_name('restart-inputs.json')),
            [PrivateFeatureState(path) for path in self.paths], monotonic=lambda: self.widgets.clock)
        self.old_book = self.widgets.bookmarks().read(self.f.owner().run)
        self.old_source = self.source(123, 'a' * 32, 1)
        self.old_native = self.inputs.capture(self.f.binding, self.old_source)
        self.calls = []; self.running = True
        self.new_binding = self.f.binding | dict(processIdentity='124:2222', sessionId=str(uuid.uuid4()))

    def source(self, pid, instance, launches):
        actor = Boundary()
        def modify(packet):
            packet.update(processId=pid, instance=instance, requestedEpochMs=self.widgets.epoch(),
                capturedEpochMs=self.widgets.epoch(), lifecycle=dict(backgrounds=0, activations=launches, launches=launches))
            packet['animationFence']['requestedEpochMs'] = self.widgets.epoch()
        actor.mutate = modify
        return NativeFeatureObservation(actor.send, actor.original, self.widgets.epoch, self.widgets.guard, pid,
            monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)

    def stop(self):
        self.calls.append('stop'); self.running = False

    def launch(self):
        self.calls.append('launch'); self.running = True

    def restart(self, *, lost=None):
        def stop():
            self.stop()
            if lost == 'stop': raise OSError('Lost stop response')
        def launch():
            self.launch()
            if lost == 'launch': raise OSError('Lost launch response')
        if self.inputs.read()['phase'] == 'prepared': self.inputs.stop(stop)
        if self.inputs.read()['phase'] == 'stop-issued':
            self.inputs.launch(lambda: dict(running=self.running, identity='123:1111' if self.running else None), launch)
        self.widgets.sleep(.1)
        self.new_source = self.source(124, 'b' * 32, 2)
        after = self.inputs.observe(self.new_binding, self.new_source)
        kernel = Presence(pid=124, epoch_ms=self.widgets.epoch); kernel.presence = 'absent'
        kernel.edit = lambda packet: packet.update(instance='b' * 32)
        self.presence = kernel
        exited = kernel.reader().require_absent(123)
        self.widgets.bridge = self.new_binding['sessionId']; self.widgets.generation = str(uuid.uuid4())
        self.widgets.sequence = 0; self.widgets.tokens.clear()
        def edit(packet):
            packet.update(processId=124)
            for row in packet['controls']:
                if row['id'] == 'places.page': row['rootInstance'] = '9' * 32
        self.widgets.edit = edit
        send = self.widgets.send
        def new_send(command):
            response, epoch = send(command); response['processId'] = 124; return response, epoch
        self.widgets.send = new_send
        native_send = self.widgets.native_send
        def read_book(command):
            native_send(command); self.widgets.native_packet.update(processId=124, instance='8' * 32)
        self.book = NativeLocationBookmarks(read_book, lambda: json.dumps(self.widgets.native_packet),
            self.widgets.epoch, self.widgets.guard, 124, monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)
        navigation = PicoNavigation(self.widgets, self.f.path.with_name('new-navigation.json'),
            dict(schemaVersion=1, sourceRevision='a' * 40, artifactSha256='b' * 64, installedCandidateVerified=True),
            self.new_binding['processIdentity'], 'http://controlled.invalid/scene.json',
            monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)
        original = SimpleNamespace(capture=navigation.snapshot, navigation=navigation)
        self.original = original
        self.factory = lambda intent: TokenPlacesUI(PicoPlacesIO(original), intent, self.previous['runId'],
            monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)
        ui = self.factory(lambda _: self.fail('Acquisition cannot issue input'))
        capture = ui.capture(); current = self.book.read(self.previous['runId'])
        self.sample = dict(ui=capture, page=ui.page(capture), native=current)
        self.proof = dict(navigationBookmarkRestartProofVersion=1, input=self.inputs.read(),
            oldNative=self.old_native, native=after, exit=exited, oldBookmark=self.old_book, bookmark=current)
        return self.proof

    def adopt(self):
        proposed = NavigationBookmarks.restart_record(self.previous, self.proof, self.sample)
        PrivateFeatureState(self.paths[2]).write(proposed, None)
        return self.owner()

    def owner(self):
        return NavigationBookmarks(self.factory, self.book, self.paths[2], self.previous['runId'], self.new_binding,
            monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)

    def test_original_once_restart_preserves_file_then_normal_delete_uses_new_process_and_root(self):
        old_bytes = self.f.path.read_bytes(); before = self.widgets.disk.read_bytes()
        validate(self.restart(), self.previous['runId']); owner = self.adopt()
        self.assertEqual(['stop', 'launch'], self.calls)
        self.assertEqual(old_bytes, self.f.path.read_bytes()); self.assertEqual(before, self.widgets.disk.read_bytes())
        ticket = uuid.uuid4().hex; self.assertEqual(dict(performed=True), owner.act(ticket, 'bookmark-delete'))
        self.assertFalse(self.widgets.storage()['owned']); current = self.owner().state
        self.assertEqual(self.previous['original']['storage']['mapSha256'], current['lastNative']['storage']['mapSha256'])
        self.assertEqual(7, len(current['completed'][0]['quiet']))
        calls = deepcopy(self.widgets.calls); self.owner().act(ticket, 'bookmark-delete')
        self.assertEqual(calls, self.widgets.calls); self.assertTrue(self.inputs.store.read())

    def test_applied_lost_stop_or_launch_resumes_without_input_replay(self):
        for fault in ('stop', 'launch'):
            with self.subTest(fault=fault):
                self.setUp()
                with self.assertRaises(RestartDeliveryUncertain): self.restart(lost=fault)
                self.restart(); self.adopt().act(uuid.uuid4().hex, 'bookmark-delete')
                self.assertEqual(['stop', 'launch'], self.calls)

    def test_pid_ack_unknown_kernel_or_stale_bookmark_cannot_transfer_authority(self):
        self.restart()
        for fault in ('not-observed', 'old-bridge', 'old-birth', 'unknown', 'old-book-birth', 'stale-book', 'no-file', 'file-rewrite'):
            proof = deepcopy(self.proof)
            if fault == 'not-observed': proof['input']['phase'] = 'launch-issued'
            elif fault == 'old-bridge': proof['input']['newBinding']['sessionId'] = self.f.binding['sessionId']
            elif fault == 'old-birth': proof['native']['instance'] = proof['oldNative']['instance']
            elif fault == 'unknown': proof['exit'].update(presence='unknown', nativeError=1, errorSymbol='EPERM')
            elif fault == 'old-book-birth': proof['bookmark']['instance'] = proof['oldBookmark']['instance']
            elif fault == 'stale-book': proof['bookmark']['requestedEpochMs'] = proof['exit']['capturedEpochMs'] - 1
            elif fault == 'no-file': proof['bookmark']['storage']['file'] = None
            else: proof['bookmark']['storage']['file']['revisionSha256'] = '0' * 64
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                NavigationBookmarks.restart_record(self.previous, proof, self.sample)
        self.assertFalse(self.paths[2].exists())

    def test_new_root_binding_ui_owned_rows_or_foreign_storage_cannot_borrow_old_journal(self):
        self.restart()
        for fault in ('root', 'bridge', 'owned-row', 'unowned', 'address', 'candidate', 'unfinished'):
            sample, proof, old = deepcopy(self.sample), deepcopy(self.proof), deepcopy(self.previous)
            page = next(r for r in sample['ui']['controls'] if r['id'] == 'places.page'); sample['page'] = page
            if fault == 'root': page['rootInstance'] = old['original']['rootInstance']
            elif fault == 'bridge': sample['ui']['scope']['instance'] = old['binding']['sessionId']
            elif fault == 'owned-row': page['bookmarks']['rows'] = []
            elif fault == 'unowned': page['bookmarks']['rows'][0]['bookmarkAddressSha256'] = '0' * 64
            elif fault == 'address': page['currentAddressSha256'] = '0' * 64
            elif fault == 'candidate': proof['input']['newBinding']['artifactSha256'] = '0' * 64
            else: old['completed'][-1]['verb'] = 'bookmark-add'
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): NavigationBookmarks.restart_record(old, proof, sample)

    def test_transferred_owner_refuses_add_rename_and_nested_handoff_without_input(self):
        self.restart(); owner = self.adopt(); before = deepcopy(self.widgets.calls)
        for verb in ('bookmark-add', 'bookmark-add-cancel', 'bookmark-rename', 'bookmark-rename-cancel'):
            with self.subTest(verb=verb), self.assertRaises(NativeUIError): owner.act(uuid.uuid4().hex, verb)
        with self.assertRaises(NativeUIError): NavigationBookmarks.restart_record(owner.state, self.proof, self.sample)
        self.assertEqual(before, self.widgets.calls)

    def test_lost_actual_normal_delete_reply_recovers_from_original_effect_without_replay(self):
        self.restart(); owner = self.adopt(); ticket = uuid.uuid4().hex
        self.widgets.lose_ack = True
        with self.assertRaises(NativeUIError): owner.act(ticket, 'bookmark-delete')
        calls = deepcopy(self.widgets.calls); self.widgets.lose_ack = False
        self.assertEqual(dict(performed=True), self.owner().act(ticket, 'bookmark-delete'))
        self.assertEqual(calls, self.widgets.calls)
        self.assertFalse(self.owner().state['lastNative']['storage']['owned'])

    def test_legacy_original_stays_v1_readable_and_archive_never_uses_ui_or_sources(self):
        previous = deepcopy(self.previous); previous.pop('handoff'); previous['navigationBookmarksVersion'] = 1
        self.assertEqual(previous, NavigationBookmarks.archive(previous)); self.restart()
        self.assertEqual(previous, NavigationBookmarks.archive(previous))
        value = NavigationBookmarks.restart_record(previous, self.proof, self.sample)
        self.assertEqual(2, value['navigationBookmarksVersion'])
        self.assertEqual(previous, NavigationBookmarks.archive(previous))

    def phase(self):
        client = Client('http://controlled.invalid/feature-fixture/v1', 'reader-' + 'q' * 32)
        self.phase_sequence = 0; self.phase_changed = False
        def request(path, *, phase_nonce):
            self.assertEqual('/runs/' + self.previous['runId'] + '/phase', path)
            self.phase_sequence += 1
            return dict(fixturePhaseVersion=1, instance='c' * 32, sequence=self.phase_sequence,
                requestId=phase_nonce, runId=self.previous['runId'], area='world-navigation',
                capturedEpochMs=self.widgets.epoch(), active=True, createdEpochMs=20000,
                retiredEpochMs=None, activations=[dict(sequence=1, ticket=('1' if self.phase_changed else '2') * 32,
                    activatedEpochMs=20000, stimulus=dict(verb='open', inputs={}))])
        client.request = request
        return PhaseFixtureReader(client, self.previous['runId'], 'world-navigation', epoch_ms=self.widgets.epoch,
            monotonic=lambda: self.widgets.clock)

    def actual_factory(self, source, lock):
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        sdk = native_fixture.NativeExecutionBindingTest(); sdk.setUp(); self.addCleanup(sdk.doCleanups)
        adapter = sdk.instance()
        adapter._script_journey = lambda: SimpleNamespace(_lock=lambda target, given: given)
        adapter._script_runtime = lambda target: (SimpleNamespace(io=self.original), None, self.new_binding)
        adapter._native_feature_observer = lambda target: self.new_source
        adapter._process_presence = lambda target: self.presence.reader()
        adapter._location_bookmarks = lambda target: self.book
        def acquire():
            return adapter._navigation_bookmark_adopt('owned', self.paths[2], self.paths[0], self.previous['runId'],
                self.inputs, self.old_native, self.old_book, source, source_lock=lock)
        return acquire

    def test_actual_private_factory_reacquires_originals_under_same_lock_and_phase_then_deletes(self):
        self.restart(); source = self.phase(); lock = ScriptSourceLock(self.f.path.with_name('sources.lock'))
        acquire = self.actual_factory(source, lock)
        with self.assertRaisesRegex(ValueError, 'OVT_PICO_BINDING_REJECTED'): acquire()
        self.assertFalse(self.paths[2].exists())
        with lock.held():
            owner = acquire(); self.assertEqual(dict(performed=True), owner.act(uuid.uuid4().hex, 'bookmark-delete'))
            calls = deepcopy(self.widgets.calls); recovered = acquire()
            self.assertFalse(recovered.state['lastNative']['storage']['owned'])
            self.assertEqual(calls, self.widgets.calls)
        self.assertEqual(['stop', 'launch'], self.calls)

    def test_last_guard_phase_change_or_post_cas_native_jump_refuses_with_journals_retained(self):
        for fault in ('phase', 'cas-age', 'native-age'):
            self.setUp(); self.restart(); source = self.phase(); lock = ScriptSourceLock(self.f.path.with_name('sources.lock'))
            acquire = self.actual_factory(source, lock); before = deepcopy(self.widgets.calls)
            if fault == 'phase':
                guard = self.book.guard
                def changed():
                    result = guard()
                    if self.phase_sequence: self.phase_changed = True
                    return result
                self.book.guard = changed
                with lock.held(), self.assertRaisesRegex(ValueError, 'OVT_PICO_BINDING_REJECTED'): acquire()
                self.assertFalse(self.paths[2].exists())
            else:
                write = PrivateFeatureState.write
                def delayed(store, value, previous):
                    result = write(store, value, previous)
                    if store.path == self.paths[2]:
                        if fault == 'cas-age': self.widgets.clock += 2
                        else:
                            epoch = self.widgets.epoch
                            self.widgets.epoch = lambda: epoch() + 2000
                    return result
                with patch.object(PrivateFeatureState, 'write', delayed), lock.held(), self.assertRaisesRegex(ValueError, 'OVT_PICO_BINDING_REJECTED'): acquire()
                self.assertTrue(self.paths[2].exists())
            self.assertEqual(before, self.widgets.calls)
            self.assertEqual(self.previous, NavigationBookmarks.archive(PrivateFeatureState(self.f.path).read()))
            self.assertIsNotNone(self.inputs.store.read())


if __name__ == '__main__': unittest.main()
