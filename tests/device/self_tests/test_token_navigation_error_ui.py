"""Actual Pico Python input route, with synthetic widget/listener/OS boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_modals import presented, retired
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import NavigationError
from adapters.pico4.normal_navigation_error import PicoNavigationErrorIO
from adapters.token_navigation_error_ui import TokenNavigationErrorUI
import self_tests.test_token_places_ui as places
import self_tests.test_native_navigation_modals as modals

RUN = modals.RUN


class Model(places.Widgets):
    def __init__(self, root):
        super().__init__(root)
        self.modal = modals.Boundary();self.modal.create()
        self.modal.now = lambda: self.clock;self.modal.sleep = self.sleep
        self.modal.ui_sequence = lambda: self.sequence
        self.modal_token = None
        self.retain_root = self.retain_listener = False

    def raw(self):
        value = super().raw();value['navigationErrorControlsVersion'] = 1
        row = self.modal.records[0]
        if row['rootAlive'] and row['visible']:
            signature = (row['modalId'], row['event']['eventId'], row['event']['lookupGeneration'], row['messageSha256'],
                         row['callbackFinished'], self.geometry)
            if self.modal_token is None or self.modal_token[0] != signature:
                self.modal_token = signature, str(uuid.uuid4())
            value['controls'].append(dict(id='navigation.error.ok.' + row['modalId'], token=self.modal_token[1],
                enabled=True, focused=False, inputReady=not row['callbackFinished'], modalId=row['modalId'],
                eventId=row['event']['eventId'], runId=row['event']['runId'], lookupGeneration=row['event']['lookupGeneration'],
                createdEpochMs=row['createdEpochMs'], messageSha256=row['messageSha256']))
        return value

    def send(self, command):
        if not command['controlId'].startswith('navigation.error.ok.'):
            return super().send(command)
        self.calls.append(deepcopy(command))
        if not self.ignore:
            self.sequence += 1
            if not self.ignore_effect:
                self.modal.finish(root=self.retain_root, listener=self.retain_listener)
        if self.lose_ack:
            raise NativeUIError('Synthetic lost applied OK reply')
        return dict(schemaVersion=1, bridgeId=self.bridge, commandId=command['commandId'], sequence=command['sequence'],
                    performed=True, error='', processId=123, updatedEpochMs=self.epoch()), self.epoch()


class NavigationErrorControlTests(unittest.TestCase):
    def setUp(self):
        self.fixture = places.PlacesControlTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model = Model(self.fixture.root)
        self.fixture.navigation.io = self.model
        self.original = self.fixture.original
        self.source = self.model.modal.reader()
        self.store = PrivateFeatureState(self.fixture.root / 'error-input.json')
        self.before_send = None
        self.ui = TokenNavigationErrorUI(PicoNavigationErrorIO(self.original), self.intent, RUN)

    def intent(self, value):
        before = self.store.read();self.store.write(value, before)
        if self.before_send:
            self.before_send()

    def source_packet(self):
        return self.source.read(RUN)

    def test_native_http_callback_modal_normal_ok_and_both_original_qobjects_join_separately(self):
        joined = self.model.modal.replies.join()
        original = self.source_packet()
        self.assertEqual(joined['native'], presented(original, joined['native'])['event'])
        self.ui.dismiss(original, joined['native'])
        final = self.source_packet()
        self.assertEqual(1024, retired(final, joined['native'])['selectedButton'])
        self.assertEqual(1, len(self.model.calls))
        self.assertEqual('navigation.error.ok.' + original['records'][0]['modalId'], self.store.read()['controlId'])

    def test_consumed_ack_and_hidden_root_or_retained_listener_cannot_supply_retirement(self):
        for fault in ('ignore_effect', 'retain_root', 'retain_listener'):
            self.setUp();setattr(self.model, fault, True)
            self.ui.dismiss(self.source_packet(), self.model.modal.event)
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                retired(self.source_packet(), self.model.modal.event)
            self.assertEqual(1, len(self.model.calls))

    def test_ignored_or_lost_input_has_one_send_and_keeps_its_original_intent(self):
        for fault in ('ignore', 'lose_ack'):
            self.setUp();setattr(self.model, fault, True)
            with self.subTest(fault=fault), self.assertRaises((NativeUIError, NavigationError)):
                self.ui.dismiss(self.source_packet(), self.model.modal.event)
            self.assertEqual(1, len(self.model.calls));self.assertIsNotNone(self.store.read())
            if fault == 'lose_ack':
                self.assertEqual(1024, retired(self.source_packet(), self.model.modal.event)['selectedButton'])

    def test_changed_geometry_event_or_root_between_intent_and_admission_refuses_input(self):
        for fault in ('geometry', 'event', 'root'):
            self.setUp()
            def changed():
                if fault == 'geometry':
                    self.model.geometry = (30, 50, 80, 40)
                elif fault == 'event':
                    self.model.modal.records[0]['event']['eventId'] = '5' * 32
                else:
                    self.model.modal.records[0]['modalId'] = '5' * 32
            self.before_send = changed
            with self.subTest(fault=fault), self.assertRaises((NativeUIError, NavigationError)):
                self.ui.dismiss(self.source_packet(), self.model.modal.event)
            self.assertEqual([], self.model.calls);self.assertIsNotNone(self.store.read())

    def test_wrong_original_generation_pid_source_body_and_stale_timestamp_never_click(self):
        for change in (lambda v: v.update(processId=124), lambda v: v.update(navigationModalVersion=True),
                       lambda v: v.update(uiInputSequence=1), lambda v: v.update(uiGeneration='5' * 32),
                       lambda v: v.update(capturedEpochMs=18000, uiEpochMs=18000),
                       lambda v: v['records'][0].update(createdMessageSha256='5' * 64),
                       lambda v: v['records'][0]['event'].update(lookupGeneration=3)):
            self.setUp();packet = self.source_packet();change(packet)
            with self.subTest(change=change), self.assertRaises(NativeUIError):
                self.ui.dismiss(packet, self.model.modal.event)
            self.assertEqual([], self.model.calls);self.assertIsNone(self.store.read())

    def test_actual_private_pico_factories_keep_source_file_and_existing_normal_input_binding(self):
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root / 'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        fixture = native_fixture.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter = fixture.instance()
        adapter._scripts = lambda target: SimpleNamespace(ui=SimpleNamespace(io=self.original)) if target == 'owned' else None
        native = self.model.modal.reader()
        adapter._native_feature_observer = lambda target: native if target == 'owned' else None
        def raw(target, package, filename, *, attempts):
            self.assertEqual(('owned', 'org.overte.pico', 'files/overte-e2e/feature-navigation-modals.json', 1),
                             (target, package, filename, attempts))
            return self.model.modal.original()
        adapter.adb.read_debug_app_file = raw
        reader = adapter._navigation_modals('owned')
        ui = adapter._navigation_error_controls('owned', self.intent, RUN)
        ui.dismiss(reader.read(RUN), self.model.modal.event)
        self.assertEqual(1024, retired(reader.read(RUN), self.model.modal.event)['selectedButton'])
        self.assertEqual(1, len(self.model.calls))


if __name__ == '__main__':
    unittest.main()
