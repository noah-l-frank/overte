"""Actual parent/runner/controller ownership with declared native rights actor."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import test_create_journey as parent
from test_create_models import ModelBackend
from self_tests import test_pico_create_permissions as permission_fixture
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from feature_journeys.scenarios import VERSION
from adapters.normal_ui import NativeUIError


class CreateRezOwnerTests(unittest.TestCase):
    make=parent.CreateJourneyTests.make
    def setUp(self):
        parent.CreateJourneyTests.setUp(self)
        # Two real owned loopback APIs around the original Phone controller.
        self.actor=permission_fixture.PicoCreatePermissionTests();self.actor.setUp()
        self.addCleanup(lambda:(self.actor.tearDown(),self.actor.doCleanups()))
        self.provider,self.server,self.reader,self.adapter_reader=self.actor.fixture()
        self.server.journal=self.journal
        self.actor.controller.domain=self.b.native_domain if hasattr(self.b,'native_domain') else self.root.state()['baselineEntities']['source']['domainId']
        self.actor.server.domain=self.actor.controller.domain
        self.provider.config['domainId']=self.actor.controller.domain
        self.actor.controller.monotonic=self.b.now;self.actor.controller.epoch_ms=self.b.epoch
        self.provider.monotonic=self.b.now;self.provider.epoch_ms=self.b.epoch
        self.provider.provision(parent.RUN)
        self.reader.run=parent.RUN;self.reader.area='create';self.reader.closed=False
        self.follow_native=True
        class Source(Client):
            def __init__(source):super().__init__(parent.URL.split('/runs/')[0],'private-host-reader-'+'a'*32)
            def request(source,path,value=None,method=None,**kwargs):
                return self.adapter_reader.request(path,value,method,**kwargs)
        self.source=lambda:PhaseFixtureReader(Source(),parent.RUN,'create',epoch_ms=self.b.epoch,monotonic=self.b.now)
        original=ModelBackend.reader
        def reader(b,kind):
            native=original(b,kind);send=native.send
            def deliver(command):
                send(command)
                if kind=='entities' and self.follow_native:
                    packet=json.loads(b.frames[kind]);actual=self.actor.server.security['standard_permissions']
                    # Native rights remain an explicit independent source actor;
                    # no provider ACK is copied into the product observation.
                    original_rows=self.actor.original['standard_permissions']
                    rights=(True,False) if actual==original_rows else (actual[0]['id_can_rez'],actual[0]['id_can_rez_tmp'])
                    packet['source']['canRez'],packet['source']['canRezTmp']=rights;b.frames[kind]=json.dumps(packet,indent=2)+'\n'
            native.send=deliver;return native
        boundary=patch.object(ModelBackend,'reader',reader);boundary.start();self.addCleanup(boundary.stop)
        self.make()
    def act(self,verb,inputs=None):
        inputs={} if inputs is None else inputs;ticket=uuid.uuid4().hex
        self.reader.activate(ticket,verb,inputs)
        return self.root.invoke('act',dict(contractVersion=VERSION,runId=parent.RUN,ticket=ticket,
            fixtureUrl=parent.URL,verb=verb,inputs=inputs))
    def test_runner_original_settings_and_native_rights_join_restore_and_joint_cleanup(self):
        before=len(self.b.inputs);self.act('set-rez-permission',dict(allowed=False))
        self.assertFalse(self.root.invoke('sample')['entities']['source']['canRez']);self.assertEqual(before,len(self.b.inputs))
        proof=deepcopy(self.root.rez_state()['effects']);self.assertEqual(1,len(proof))
        self.make();self.act('set-rez-permission',dict(allowed=True))
        self.assertTrue(self.root.invoke('sample')['entities']['source']['canRezTmp']);self.assertEqual(2,len(self.actor.server.posts));self.assertEqual(proof,self.root.rez_state()['effects'][:1])
        self.reader.activate(uuid.uuid4().hex,'cleanup',{});self.make();self.root.invoke('cleanup')
        self.assertIsNone(self.root.store.read());self.assertEqual(self.actor.original,self.actor.server.security)
        self.assertFalse(self.root.source_store('rez').read());self.assertEqual(before,len(self.b.inputs));self.reader.close()
    def test_lost_initial_parent_readback_keeps_original_call_and_cold_reconciles_without_replay(self):
        before=len(self.b.inputs)
        with patch.object(self.root,'rez_read',side_effect=NativeUIError('declared unavailable initial readback')):
            with self.assertRaises(NativeUIError):self.act('set-rez-permission',dict(allowed=False))
        pending=self.root.state()['pending'];self.assertIsNotNone(pending);self.assertEqual(1,len(self.actor.server.posts))
        with self.assertRaises(NativeUIError):self.act('close')
        self.assertEqual(pending,self.root.state()['pending']);self.assertEqual(before,len(self.b.inputs))
        # Advance back to the original ticket is forbidden. The extra Runner
        # phase above intentionally prevents any completion or later dispatch.
        self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual(pending,self.root.state()['pending']);self.assertEqual(1,len(self.actor.server.posts))
    def test_lost_initial_parent_readback_same_ticket_cold_recovers_without_settings_or_ui_replay(self):
        before=len(self.b.inputs)
        with patch.object(self.root,'rez_read',side_effect=NativeUIError('declared unavailable initial readback')):
            with self.assertRaises(NativeUIError):self.act('set-rez-permission',dict(allowed=False))
        self.assertIsNotNone(self.root.state()['pending']);self.make();self.root.invoke('reconcile')
        self.assertIsNone(self.root.state()['pending']);self.assertEqual(1,len(self.actor.server.posts));self.assertEqual(before,len(self.b.inputs))
    def test_actual_settings_without_actual_client_effect_retains_pending_and_never_sends_ui(self):
        self.follow_native=False;before=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.act('set-rez-permission',dict(allowed=False))
        pending=self.root.state()['pending'];self.assertIsNotNone(pending);self.assertEqual(1,len(self.actor.server.posts))
        self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('reconcile')
        self.assertEqual(pending,self.root.state()['pending']);self.assertEqual(1,len(self.actor.server.posts));self.assertEqual(before,len(self.b.inputs))
        self.follow_native=True;self.make();self.root.invoke('reconcile');self.assertIsNone(self.root.state()['pending'])
        self.assertEqual(1,len(self.actor.server.posts));self.assertEqual(before,len(self.b.inputs))


if __name__=='__main__':unittest.main()
