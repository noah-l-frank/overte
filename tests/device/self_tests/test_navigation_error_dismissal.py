"""Real durable ownership/input/HTTP joins; Qt/native/OS boundaries simulated."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.navigation_error_dismissal import NavigationErrorDismissal
from adapters.normal_ui import NativeUIError
from adapters.pico4.normal_navigation_error import PicoNavigationErrorIO
from adapters.token_navigation_error_ui import TokenNavigationErrorUI
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import NavigationResources, DIRECTORY
from feature_journeys.server import make_server
from feature_journeys.witness import Client
import self_tests.test_token_navigation_error_ui as controls
import self_tests.test_native_navigation_replies as replies

RUN, TICKET = replies.RUN, replies.TICKET
INPUTS = dict(replies.INPUTS, sourceRevision='a' * 40)


class NavigationErrorDismissalTests(unittest.TestCase):
    def setUp(self):
        self.fixture = controls.NavigationErrorControlTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model = self.fixture.model
        self.binding = dict(sourceRevision='a' * 40, artifactSha256='b' * 64, processIdentity='123:synthetic-start',
                            sessionId=self.model.bridge, generation=0, targetFingerprint='c' * 64)
        self.path = self.fixture.fixture.root / 'lookup-error-owner.json'
        self.model.modal.replies.epoch = self.model.epoch
        self.provider = self.model.modal.replies.provider();self.provider['inputs'] = deepcopy(INPUTS)

    def status(self):
        value = deepcopy(self.provider);value['capturedEpochMs'] = self.model.epoch()
        return value

    def reply_reader(self):
        boundary = self.model.modal.replies
        return NativeNavigationReplies(boundary.send, boundary.original, self.model.epoch, self.model.guard, 123,
                                        monotonic=lambda: self.model.clock, sleep=self.model.sleep)

    def owner(self, **changes):
        values = dict(ui_factory=lambda intent: TokenNavigationErrorUI(PicoNavigationErrorIO(self.fixture.original), intent, RUN),
            replies=self.reply_reader(), modals=self.model.modal.reader(), status=self.status, path=self.path, run=RUN,
            binding=self.binding, provider_instance='1' * 32, provider_inputs=INPUTS, owned_origin=replies.ORIGIN,
            guard=self.model.guard, monotonic=lambda: self.model.clock, sleep=self.model.sleep)
        values.update(changes)
        return NavigationErrorDismissal(**values)

    def test_original_http_native_callback_normal_ok_and_full_quiet_retirement_survive_recreation(self):
        self.assertEqual(dict(performed=True), self.owner().act(TICKET, 20000))
        state = self.owner().state
        self.assertEqual('complete', state['phase']);self.assertEqual(7, len(state['quiet']))
        self.assertGreaterEqual(state['quiet'][-1]['modal']['uiElapsedMs'] - state['quiet'][0]['modal']['uiElapsedMs'], 3000)
        self.assertEqual(state['original']['reply']['events'][0], state['joined']['event'])
        inputs = deepcopy(self.model.calls)
        self.assertEqual(dict(performed=True), self.owner().act(TICKET, 20000))
        self.assertEqual(inputs, self.model.calls);self.assertEqual(1, len(inputs))

    def test_applied_lost_reply_resolves_from_original_response_and_dead_qobjects_without_resending(self):
        self.model.lose_ack = True
        with self.assertRaises(NativeUIError):
            self.owner().act(TICKET, 20000)
        state = self.owner().state
        self.assertEqual('pending', state['phase']);self.assertIsNotNone(state['input'])
        self.model.lose_ack = False;inputs = deepcopy(self.model.calls)
        self.assertEqual(dict(performed=True), self.owner().act(TICKET, 20000))
        self.assertEqual(inputs, self.model.calls)

    def test_ignored_input_or_retained_resources_keep_one_pending_input_and_refuse_replacement_ticket(self):
        for fault in ('ignore', 'ignore_effect', 'retain_root', 'retain_listener'):
            self.setUp();setattr(self.model, fault, True)
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                self.owner().act(TICKET, 20000)
            self.assertEqual('pending', self.owner().state['phase'])
            self.assertEqual(1, len(self.model.calls))
            with self.assertRaises(NativeUIError):
                self.owner().act('9' * 32, 20000)
            self.assertEqual(1, len(self.model.calls))

    def test_current_generation_provider_receipt_original_barrier_and_source_identity_are_required_before_input(self):
        for fault in ('generation', 'inactive', 'response-id', 'old-receipt', 'origin', 'provider-instance', 'candidate', 'v1', 'old-capture'):
            self.setUp()
            if fault == 'generation':
                self.model.modal.replies.generation += 1
            elif fault == 'inactive':
                self.provider.update(active=False, ticket=None)
            elif fault == 'response-id':
                self.provider['responses'][0]['responseId'] = '8' * 32
            elif fault == 'old-receipt':
                self.provider['responses'][0]['completedEpochMs'] = 19000
            elif fault == 'v1':
                self.model.modal.replies.version = 1
                for key in ('replyCaptureId', 'replyCapturedEpochMs'):
                    self.model.modal.replies.events[0].pop(key)
            elif fault == 'old-capture':
                self.model.modal.replies.events[0]['replyCapturedEpochMs'] = 19000
                self.model.modal.records[0]['event']['replyCapturedEpochMs'] = 19000
            elif fault == 'origin':
                self.model.modal.replies.events[0]['origin'] = 'http://foreign.invalid'
            elif fault == 'provider-instance':
                self.provider['instance'] = '8' * 32
            else:
                self.binding['sourceRevision'] = '8' * 40
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                self.owner().act(TICKET, 20000)
            self.assertEqual([], self.model.calls)

    def test_advanced_input_lookup_or_stalled_ui_during_quiet_cannot_finish(self):
        for fault in ('input', 'lookup', 'ui'):
            self.setUp();sleep = self.model.sleep;changed = []
            def altered(seconds):
                sleep(seconds)
                if not changed:
                    changed.append(True)
                    if fault == 'input':
                        self.model.sequence += 1
                    elif fault == 'lookup':
                        self.model.modal.replies.generation += 1
                    else:
                        self.model.modal.ui_epoch = 20000
            self.model.sleep = altered
            with self.subTest(fault=fault), self.assertRaises(NativeUIError):
                self.owner().act(TICKET, 20000)
            self.assertEqual(1, len(self.model.calls));self.assertNotEqual('complete', self.owner().state['phase'])

    def test_replayed_query_identity_and_changed_archived_callbacks_fail_on_recreation(self):
        self.assertEqual(dict(performed=True), self.owner().act(TICKET, 20000))
        state = self.owner().state
        state['quiet'][1]['modal']['records'][0]['callbackEpochMs'] += 1
        self.path.write_text(json.dumps(state));self.path.chmod(0o600)
        with self.assertRaises(NativeUIError):
            self.owner()

    def test_query_identity_reused_after_adapter_recreation_cannot_borrow_a_new_cursor(self):
        self.assertEqual(dict(performed=True), self.owner().act(TICKET, 20000))
        state = self.owner().state;before = deepcopy(self.model.calls)
        with patch('adapters.native_navigation_replies.uuid.uuid4', return_value=SimpleNamespace(hex=state['queries'][0])):
            with self.assertRaises(NativeUIError):
                self.owner().act(TICKET, 20000)
        self.assertEqual(before, self.model.calls)

    def test_actual_private_pico_composition_factory_uses_both_fixed_sources_and_normal_controls(self):
        root = Path(__file__).resolve().parents[3]
        sys.path.insert(0, str(root / 'android/vr/pico/tests/device'))
        import test_native_execution_binding as native_fixture
        sdk = native_fixture.NativeExecutionBindingTest();sdk.setUp();self.addCleanup(sdk.doCleanups)
        adapter = sdk.instance()
        adapter._scripts = lambda target: SimpleNamespace(ui=SimpleNamespace(io=self.fixture.original), binding=self.binding)
        def send(command):
            if command['action'] == 'feature-navigation-modals':
                self.model.modal.send(command)
            elif command['action'] == 'feature-navigation-replies':
                self.model.modal.replies.send(command)
            else:
                raise AssertionError('Unexpected synthetic native command')
        native = SimpleNamespace(send=send, clock_ms=self.model.epoch, guard=self.model.guard, pid=123,
                                 monotonic=lambda: self.model.clock, sleep=self.model.sleep)
        adapter._native_feature_observer = lambda target: native
        def raw(target, package, filename, *, attempts):
            self.assertEqual(('owned', 'org.overte.pico', 1), (target, package, attempts))
            if filename == 'files/overte-e2e/feature-navigation-modals.json':
                return self.model.modal.original()
            self.assertEqual('files/overte-e2e/feature-navigation-replies.json', filename)
            return self.model.modal.replies.original()
        adapter.adb.read_debug_app_file = raw
        with patch('adapters.navigation_error_dismissal.NavigationErrorDismissal', partial(NavigationErrorDismissal,
                   monotonic=lambda: self.model.clock, sleep=self.model.sleep)):
            owner = adapter._navigation_error_dismissal('owned', self.path, RUN, self.status, '1' * 32,
                                                       INPUTS, replies.ORIGIN, self.model.guard)
        self.assertEqual(dict(performed=True), owner.act(TICKET, 20000))
        self.assertEqual(1, len(self.model.calls))

    def test_actual_owned_loopback_404_header_and_completed_response_join_the_synthetic_native_boundaries(self):
        provider = NavigationResources(INPUTS, clock_ms=self.model.epoch)
        server = make_server('r' * 32, 'p' * 32, navigation_resources=provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        client = None
        try:
            origin = f'http://127.0.0.1:{server.server_port}'
            client = Client(origin + '/feature-fixture/v1', 'r' * 32)
            run, _ = client.register('world-navigation');client.activate(TICKET)
            with self.assertRaises(HTTPError) as caught:
                urlopen(origin + DIRECTORY + '/' + context(run)['hidden'], timeout=2)
            try:
                caught.exception.read();response = caught.exception.headers['X-Overte-Fixture-Response']
            finally:
                caught.exception.close()
            event = self.model.modal.replies.events[0]
            event.update(runId=run, origin=origin, responseId=response)
            self.model.modal.event = deepcopy(event);self.model.modal.records[0]['event'] = deepcopy(event)
            # The actual native/Qt boundaries stay explicit simulations. Only
            # the owned HTTP write/receipt and host state/input code are real.
            owner = self.owner(run=run, ui_factory=lambda intent: TokenNavigationErrorUI(PicoNavigationErrorIO(self.fixture.original), intent, run),
                               status=client.navigation_status, provider_instance=provider.instance, owned_origin=origin)
            self.assertEqual(dict(performed=True), owner.act(TICKET, 20000))
            self.assertEqual(response, owner.state['joined']['response']['responseId'])
            client.close()
        finally:
            if client is not None and not getattr(client, 'closed', False):
                client.close()
            server.shutdown();server.server_close();thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual(0, server.internal_errors)


if __name__ == '__main__':
    unittest.main()
