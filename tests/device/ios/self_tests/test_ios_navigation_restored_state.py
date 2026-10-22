"""Connected normal static return and actual restored source/lifetime joins."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.adapters.navigation_restored_state import compose
from ios.self_tests import test_ios_navigation_feature_transfer as transfer
from ios.self_tests.navigation_feature_next_ui_fixture import NextUI


class NavigationRestoredStateTests(unittest.TestCase):
    setUp=transfer.NavigationFeatureTransferTests.setUp
    action=transfer.NavigationFeatureTransferTests.action
    ready=transfer.NavigationFeatureTransferTests.ready
    restart_call=transfer.NavigationFeatureTransferTests.restart_call
    install=transfer.NavigationFeatureTransferTests.install

    def acquire(self,*,retained_http=False):
        self.ready();h=self.h;self.install();h.flow.act(self.restart_call());self.ui=NextUI(self.new,self)
        self.ui.collect_http=not retained_http
        sequence=h.flow.state['observerOffsets']['primary']
        for verb,inputs in (('open',{}),('bookmark-delete',dict(name=context(h.run)['renamed'])),('close',{})):
            ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,inputs);self.new.gpu.marker=ticket
            h.flow.act(dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs=inputs,fixtureUrl=h.fixture.fixture_url))
            measured=h.flow.observe_active(sequence);sequence=measured['sequence']
        h.flow.return_to_original()
        with h.flow.held():
            h.flow.load();scope=h.flow.admission();observer=h.flow.observer()
            directory=h.flow.directory(observer,scope)
            self.prior_owner=observer.owners()[-1];self.prior_owner.archive()
            prior=dict(originals=deepcopy(self.prior_owner.state['originals']),
                nativeAfter=deepcopy(self.prior_owner.state['clockJoin']['nativeAfter']))
            window=NativeClockAcquisition(self.new.native,epoch_ms=h.now,monotonic=h.mono);window.begin(h.now())
            originals={name:reader.capture() if name=='ui' else reader.read(h.run) for name,reader in self.new.sources.items()}
            clock=window.finish(originals,[(name,key) for name,packet in originals.items()
                for key in ('capturedEpochMs','sampleEpochMs') if key in packet])
            return dict(initial=scope.original_admission(),process_context=scope.owner.archive(),owner_files=scope.owner.owner_files,
                originals=originals,clock_join=clock,base=scope.fixture.base_scene(),
                address_owner=PrivateFeatureState(h.root/'ios-navigation-address-43-inputs.json').read(),
                surface_owner=PrivateFeatureState(h.root/'ios-navigation-surface-actions-43.json').read(),directory=directory,prior=prior)

    def test_full_static_sources_keep_historical_events_and_explicit_owned_hidden_roots(self):
        call=self.acquire();before=deepcopy(call);result=compose(**call)
        self.assertEqual(before,call);self.assertTrue(result['lifetimeEndRequired'])
        self.assertTrue(result['placesRoots']['roots']);self.assertFalse(result['placesRoots']['roots'][0]['drained'])
        self.assertEqual('43',result['binding']['processIdentity'])
        self.assertTrue(call['originals']['http']['events']);self.assertTrue(call['originals']['ui']['navigationInventory']['roots'])
        self.assertNotIn('cleaned',result);self.assertNotIn('retired',result)
        for fault in ('scene-map','moving','preferences','unknown-address','base','context','source-rollback'):
            broken=deepcopy(call)
            if fault=='scene-map':broken['originals']['inventory']['source']['tree']['entities'][0]['semanticSha256']='0'*64
            elif fault=='moving':broken['originals']['navigation']['source']['avatar']['velocity'][0]=1
            elif fault=='preferences':broken['originals']['model']['preferences']['metaverseOrigin']='http://foreign.invalid'
            elif fault=='unknown-address':broken['originals']['ui']['navigationInventory']['roots'][0]['rootId']=str(uuid.uuid4())
            elif fault=='base':broken['base']['sha256']='0'*64
            elif fault=='source-rollback':broken['originals']['http']['events']=[]
            else:broken['process_context']['restart']['input']['newBinding']['processIdentity']='44'
            broken['clock_join']['originalsSha256']=digest(broken['originals'])
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):compose(**broken)

    def test_completed_normal_navigation_and_closed_tablet_cannot_hide_retained_http_resources(self):
        call=self.acquire(retained_http=True)
        self.assertFalse(call['originals']['ui']['tabletShown'])
        self.assertFalse(call['originals']['navigation']['source']['challengeMarker']['present'])
        with self.assertRaises(NativeUIError):compose(**call)


if __name__=='__main__':unittest.main()
