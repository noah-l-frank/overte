"""Original-process normal return and independent current source admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch

from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_initial_restored_state import compose
from ios.self_tests import test_ios_navigation_whole_feature as fixture
from ios.self_tests.navigation_initial_return_fixture import InitialReturnWorld


class NavigationInitialRestoredStateTests(unittest.TestCase):
    def setUp(self):
        with patch.object(fixture,'Whole',InitialReturnWorld):fixture.NavigationWholeFeatureTests.setUp(self)

    def acquire(self):
        h=self.h;self.whole.prepare()
        current=self.whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=0))
        for verb in ('open','close'):
            ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,{});h.gpu.marker=ticket
            self.whole.act(dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs={},fixtureUrl=h.fixture.fixture_url))
            current=self.whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=current['sequence']))
        h.flow.return_to_original()
        with h.flow.held():
            h.flow.load();admission=h.flow.admission();observer=h.flow.observer();prior=observer.owners()[-1]
            prior.archive();self.prior_owner=prior;initial=h.flow.initial_admission();directory=h.flow.directory(observer,admission)
            window=NativeClockAcquisition(h.native,epoch_ms=h.now,monotonic=h.mono);window.begin(h.now())
            originals={name:reader.capture() if name=='ui' else reader.read(h.run) for name,reader in self.sources.items()}
            clock=window.finish(originals,[(name,key) for name,packet in originals.items()
                for key in ('capturedEpochMs','sampleEpochMs') if key in packet])
            return dict(initial=initial,originals=originals,clock_join=clock,base=h.fixture.base_scene(),
                address_owner=PrivateFeatureState(h.root/('ios-navigation-address-'+h.binding['processIdentity']+'-inputs.json')).read(),
                surface_owner=PrivateFeatureState(h.root/'ios-navigation-surface-actions.json').read(),
                directory=directory,fixture_url=h.fixture.fixture_url,
                prior=dict(originals=deepcopy(prior.state['originals']),nativeAfter=deepcopy(prior.state['clockJoin']['nativeAfter'])))

    def test_original_process_restoration_preserves_histories_and_retained_roots(self):
        call=self.acquire();before=deepcopy(call);value=compose(**call)
        self.assertEqual(before,call);self.assertEqual(self.h.binding,value['binding'])
        self.assertTrue(value['lifetimeEndRequired']);self.assertTrue(value['placesRoots']['roots'])
        self.assertTrue(all(not row['drained'] for row in value['placesRoots']['roots']))
        self.assertEqual('retained',value['addressRoot']['root']['status'])
        self.assertNotIn('processContextSha256',value);self.assertEqual(0,self.h.flow.state['stage'])

    def test_original_process_return_does_not_admit_changed_sources_or_unowned_roots(self):
        call=self.acquire();compose(**call)
        for fault in ('moving','preferences','foreign-address','source-rollback','foreign-pid','old-clock','base'):
            broken=deepcopy(call)
            if fault=='moving':broken['originals']['navigation']['source']['avatar']['velocity'][0]=1
            elif fault=='preferences':broken['originals']['model']['preferences']['metaverseOrigin']='http://foreign.invalid'
            elif fault=='foreign-address':broken['originals']['ui']['navigationInventory']['roots'][0]['rootId']=str(uuid.uuid4())
            elif fault=='source-rollback':broken['originals']['http']['events']=[]
            elif fault=='foreign-pid':broken['originals']['navigation']['processId']+=1
            elif fault=='old-clock':broken['clock_join']['nativeBefore']=deepcopy(broken['initial']['clockJoin']['nativeBefore'])
            else:broken['base']['sha256']='0'*64
            broken['clock_join']['originalsSha256']=digest(broken['originals'])
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):compose(**broken)


if __name__=='__main__':unittest.main()
