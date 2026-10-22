"""Durable bookmark flow on actual Pico Python input and native-source readers.

Product Qt/OS/input/storage boundaries are synthetic; no native/device claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import uuid
from functools import partial
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import NavigationError
from adapters.pico4.normal_places import PicoPlacesIO
from adapters.token_places_ui import TokenPlacesUI, sha
from feature_journeys.fixtures import context
import self_tests.test_token_places_ui as fixture

RUN = fixture.RUN


class NavigationBookmarkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.PlacesControlTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.ui.open()
        self.widgets = self.fixture.widgets
        self.path = self.fixture.root / 'bookmark-operations.json'
        self.binding = dict(sourceRevision='a' * 40, artifactSha256='b' * 64,
            processIdentity='123:synthetic-start', sessionId=self.widgets.bridge, generation=0, targetFingerprint='c' * 64)

    def owner(self, binding=None):
        factory = lambda intent: TokenPlacesUI(PicoPlacesIO(self.fixture.original), intent, RUN,
            monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)
        return NavigationBookmarks(factory, self.widgets.bookmarks(), self.path, RUN,
            self.binding if binding is None else binding, monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)

    def act(self, verb):
        ticket = uuid.uuid4().hex
        self.assertEqual(dict(performed=True), self.owner().act(ticket, verb))
        return ticket

    def test_complete_bookmark_flow_recreates_owner_and_retains_original_quiet_storage(self):
        baseline = self.widgets.storage()
        for verb in ('bookmark-add-cancel', 'bookmark-add', 'bookmark-rename-cancel', 'bookmark-rename', 'bookmark-delete'):
            ticket = self.act(verb)
            before = deepcopy(self.widgets.calls)
            self.assertEqual(dict(performed=True), self.owner().act(ticket, verb))
            self.assertEqual(before, self.widgets.calls)
        state = self.owner().state
        self.assertIsNone(state['active'])
        self.assertEqual(5, len(state['completed']))
        for result in state['completed']:
            self.assertEqual(7, len(result['quiet']))
            self.assertGreaterEqual(result['quiet'][-1]['capturedEpochMs'] - result['quiet'][0]['capturedEpochMs'], 3000)
            self.assertEqual(baseline['unownedSha256'], result['storage']['unownedSha256'])
        self.assertEqual([], self.widgets.storage()['owned'])
        self.assertEqual(baseline['mapSha256'], self.widgets.storage()['mapSha256'])
        self.assertNotIn(fixture.OTHER_ADDRESS, self.path.read_text())

    def test_applied_lost_focus_or_save_reply_resumes_from_original_effect_without_resending(self):
        for target in ('places.bookmark.name', 'places.bookmark.save'):
            self.setUp()
            original_send = self.widgets.send
            tripped = []
            def send(command):
                selected = not tripped and command['controlId'] == target and command['action'] == 'activate'
                self.widgets.lose_ack = bool(selected)
                if selected:
                    tripped.append(True)
                try:
                    return original_send(command)
                finally:
                    self.widgets.lose_ack = False
            self.widgets.send = send
            ticket = uuid.uuid4().hex
            with self.subTest(target=target), self.assertRaises(NativeUIError):
                self.owner().act(ticket, 'bookmark-add')
            pending = self.owner().state['active']['pending']
            self.assertEqual(target, pending['controlId'])
            count = sum(c['controlId'] == target and c['action'] == 'activate' for c in self.widgets.calls)
            self.assertEqual(dict(performed=True), self.owner().act(ticket, 'bookmark-add'))
            self.assertEqual(count, sum(c['controlId'] == target and c['action'] == 'activate' for c in self.widgets.calls))
            self.assertEqual([dict(name=context(RUN)['name'], addressSha256=sha(fixture.ADDRESS))], self.widgets.storage()['owned'])

    def test_ignored_persistence_never_becomes_a_green_ack_and_new_ticket_cannot_replace_it(self):
        self.widgets.ignore_persistence = True
        ticket = uuid.uuid4().hex
        with self.assertRaises(NativeUIError):
            self.owner().act(ticket, 'bookmark-add')
        state = self.owner().state
        self.assertEqual('places.bookmark.save', state['active']['pending']['controlId'])
        self.assertEqual([], state['completed'])
        inputs = deepcopy(self.widgets.calls)
        with self.assertRaises(NativeUIError):
            self.owner().act(uuid.uuid4().hex, 'bookmark-add')
        with self.assertRaises(NativeUIError):
            self.owner().act(ticket, 'bookmark-add')
        self.assertEqual(inputs, self.widgets.calls)

    def test_same_bytes_rewrite_during_cancel_is_not_unchanged_storage(self):
        original_send = self.widgets.send
        def send(command):
            reply = original_send(command)
            if command['controlId'] == 'places.bookmark.cancel':
                self.widgets.persist()
            return reply
        self.widgets.send = send
        with self.assertRaises(NativeUIError):
            self.owner().act(uuid.uuid4().hex, 'bookmark-add-cancel')
        self.assertEqual([], self.owner().state['completed'])
        self.assertEqual(1, sum(c['controlId'] == 'places.bookmark.cancel' for c in self.widgets.calls))

    def test_unowned_mutation_or_retained_write_during_quiet_preserves_unfinished_ownership(self):
        for fault in ('unowned', 'repeat-write'):
            self.setUp()
            original_sleep = self.widgets.sleep
            fired = []
            def sleep(seconds):
                original_sleep(seconds)
                if not fired and context(RUN)['name'] in self.widgets.map:
                    fired.append(True)
                    if fault == 'unowned':
                        self.widgets.map['Private bookmark'] = 'hifi://unexpected-change.invalid'
                    self.widgets.persist()
            self.widgets.sleep = sleep
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                self.owner().act(uuid.uuid4().hex, 'bookmark-add')
            state = self.owner().state
            self.assertIsNotNone(state['active'])
            self.assertEqual([], state['completed'])

    def test_original_root_birth_candidate_and_native_cursor_survive_component_recreation(self):
        self.owner().prepare()
        before = deepcopy(self.widgets.calls)
        with self.assertRaises(NativeUIError):
            self.owner(self.binding | dict(artifactSha256='d' * 64))
        self.widgets.edit = lambda packet: packet['controls'][1].update(rootInstance='0' * 32)
        with self.assertRaises(NativeUIError):
            self.owner().prepare()
        self.widgets.edit = None
        self.widgets.native_sequence = 0
        with self.assertRaises(NativeUIError):
            self.owner().prepare()
        self.assertEqual(before, self.widgets.calls)

    def test_archive_clock_nonce_and_original_quiet_history_are_not_rewritten_on_reload(self):
        self.act('bookmark-add-cancel')
        state = json.loads(self.path.read_text())
        original = deepcopy(state['completed'][0]['quiet'])
        self.widgets.clock += 30
        self.assertEqual(original, self.owner().state['completed'][0]['quiet'])
        state['completed'][0]['quiet'][1]['sequence'] = state['completed'][0]['quiet'][0]['sequence']
        self.path.write_text(json.dumps(state));self.path.chmod(0o600)
        with self.assertRaises(NativeUIError):
            self.owner()

    def test_actual_pico_factory_connects_existing_normal_input_and_private_native_storage(self):
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root / 'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        sdk = native_fixture.NativeExecutionBindingTest();sdk.setUp();self.addCleanup(sdk.doCleanups)
        adapter = sdk.instance()
        manager = SimpleNamespace(ui=SimpleNamespace(io=self.fixture.original), binding=self.binding)
        adapter._scripts = lambda target: manager if target == 'owned' else None
        native = self.widgets.bookmarks()
        adapter._native_feature_observer = lambda target: native if target == 'owned' else None
        def raw(target, package, filename, *, attempts):
            self.assertEqual(('owned', 'org.overte.pico', 'files/overte-e2e/feature-location-bookmarks.json', 1),
                             (target, package, filename, attempts))
            return json.dumps(self.widgets.native_packet)
        adapter.adb.read_debug_app_file = raw
        with patch('adapters.navigation_bookmarks.NavigationBookmarks', partial(NavigationBookmarks,
                   monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)):
            owner = adapter._bookmark_operations('owned', self.path, RUN)
        self.assertEqual(dict(performed=True), owner.act(uuid.uuid4().hex, 'bookmark-add-cancel'))
        self.assertEqual([], self.widgets.storage()['owned'])
        self.assertTrue(self.path.is_file())

    def test_whole_operation_deadline_refuses_late_input_and_keeps_the_original_owner(self):
        read = self.widgets.read
        def slow():
            self.widgets.clock += 6
            return read()
        self.widgets.read = slow
        before = deepcopy(self.widgets.calls)
        with self.assertRaises(NativeUIError):
            self.owner().act(uuid.uuid4().hex, 'bookmark-add')
        self.assertEqual(before, self.widgets.calls)
        self.assertIsNotNone(self.owner().state['active'])

    def test_stalled_original_ui_clock_cannot_supply_a_three_second_quiet_window(self):
        self.widgets.edit = lambda packet: packet.update(updatedEpochMs=20000, elapsedMs=100)
        with self.assertRaises(NativeUIError):
            self.owner().act(uuid.uuid4().hex, 'bookmark-add')
        state = self.owner().state
        self.assertIsNotNone(state['active'])
        self.assertEqual([], state['completed'])


if __name__ == '__main__':
    unittest.main()
