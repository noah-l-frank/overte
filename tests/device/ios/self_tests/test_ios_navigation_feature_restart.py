"""A lifecycle ACK cannot substitute for current-process Worlds originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.fixtures import context
from ios.self_tests.navigation_feature_restart_fixture import RestartWorld


class NavigationFeatureRestartTests(unittest.TestCase):
    def setUp(self):
        self.h=RestartWorld(self);self.h.flow.prepare();self.h.flow.observe_active(0)

    def action(self,verb,**inputs):
        h=self.h;ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,inputs);h.gpu.marker=ticket
        call=dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs=inputs,fixtureUrl=h.fixture.fixture_url)
        h.flow.act(call);return call

    def ready(self):
        h=self.h;ctx=context(h.run);h.open_directory()
        self.action('bookmark-add',name=ctx['name']);self.action('bookmark-rename',name=ctx['renamed'])
        self.action('close');h.flow.observe_active(1)
        h.flow_fixture.flow('actor').observe_active(0)

    def restart_call(self):
        h=self.h;ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'restart-app',{});h.gpu.marker=ticket
        return dict(contractVersion=16,runId=h.run,ticket=ticket,verb='restart-app',inputs={},fixtureUrl=h.fixture.fixture_url)

    def test_absent_actor_originals_block_every_normal_lifecycle_input(self):
        call=self.restart_call()
        with self.assertRaises(NativeUIError):self.h.flow.act(call)
        self.assertEqual([],self.h.lifecycle.calls)
        self.assertIsNone(PrivateFeatureState(self.h.root/'ios-navigation-restart-inputs.json').read())

    def test_actual_restart_receipt_without_new_source_group_stays_pending_and_never_repeats_lifecycle_input(self):
        self.ready();h=self.h;call=self.restart_call()
        try:h.flow.act(call)
        except NativeUIError as error:
            if 'new-process sources' not in str(error):raise
        else:self.fail('An unqualified new process became transferred')
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)
        restart=unpack(PrivateFeatureState(h.root/'ios-navigation-restart.json').read()['payload'])[0]
        self.assertEqual('observed',restart['status']);self.assertEqual('ESRCH',restart['receipt']['exit']['errorSymbol'])
        parent=unpack(h.flow.store.read()['payload'])[0]
        self.assertEqual(0,parent['stage']);self.assertEqual('42',parent['binding']['processIdentity'])
        self.assertIsNone(parent['transferSha256']);self.assertEqual('issued',parent['lastCall']['phase'])
        original=deepcopy(restart)
        with self.assertRaisesRegex(NativeUIError,'new-process sources'):h.flow_fixture.flow().act(call)
        self.assertEqual(['app.stop','app.launch'],h.lifecycle.calls)
        self.assertEqual(original,unpack(PrivateFeatureState(h.root/'ios-navigation-restart.json').read()['payload'])[0])

    def test_unowned_hidden_places_root_blocks_stop_and_cannot_be_laundered_by_closed_tablet(self):
        self.ready();h=self.h
        h.model.pages[0]['rootId']='00000000-0000-4000-8000-000000000599'
        self.assertFalse(h.model.shown)
        with self.assertRaises(NativeUIError):h.flow.act(self.restart_call())
        self.assertEqual([],h.lifecycle.calls)
        self.assertIsNone(PrivateFeatureState(h.root/'ios-navigation-restart-inputs.json').read())


if __name__=='__main__':unittest.main()
