"""Actual named-lookup/OK histories remain mandatory in initial restoration."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.adapters.navigation_initial_restored_state import compose
from ios.self_tests import test_ios_navigation_initial_restored_image as images
from ios.self_tests.navigation_feature_missing_fixture import MissingWidget


class NavigationInitialErrorRestoreTests(unittest.TestCase):
    inputs=images.NavigationInitialRestoredImageTests.inputs
    owner=images.NavigationInitialRestoredImageTests.owner

    def setUp(self):
        images.NavigationInitialRestoredImageTests.setUp(self)
        self.widget=MissingWidget(self.h,self);self.sources['dialogs']=self.h.sources['dialogs']

    def ready(self,*,partial=False):
        h=self.h;self.whole.prepare()
        current=self.whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=0))
        for verb in ('open','close','navigate-missing'):
            ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,verb,{});h.gpu.marker=ticket
            self.whole.act(dict(contractVersion=16,runId=h.run,ticket=ticket,verb=verb,inputs={},fixtureUrl=h.fixture.fixture_url))
            current=self.whole.observe(dict(contractVersion=16,runId=h.run,afterSequence=current['sequence']))
        self.assertEqual('not-found',current['state']['error']);self.widget.partial_destroy=partial
        ticket=uuid.uuid4().hex;h.harness.client.activate(ticket,'cleanup',{})
        call=dict(iosNavigationCleanupCallVersion=1,contractVersion=16,runId=h.run,ticket=ticket,verb='cleanup',inputs={},fixtureUrl=h.fixture.fixture_url)
        with h.flow.held():
            admission=h.flow.admission();missing=h.flow.runtime._navigation_missing_actions(h.flow.selector,admission)
            self.assertIsNotNone(missing.state['proof']);missing.dismiss_cleanup(call)
            self.missing=missing
            cleared=missing.observe_cleared();self.assertTrue(cleared['ownedDialogDrained'])
            address=h.flow.runtime._navigation_address_dismiss(h.flow.selector,admission)
            address.close()
        h.flow.return_to_original()

    def acquisition(self):
        h=self.h
        with h.flow.held():
            admission=h.flow.admission();observer=h.flow.observer();prior=observer.owners()[-1];prior.archive();self.prior_owner=prior
            initial=h.flow.initial_admission();directory=h.flow.directory(observer,admission)
            window=NativeClockAcquisition(h.native,epoch_ms=h.now,monotonic=h.mono);window.begin(h.now())
            originals={name:reader.capture() if name=='ui' else reader.read(h.run) for name,reader in self.sources.items()}
            clock=window.finish(originals,[(name,key) for name,packet in originals.items()
                for key in ('capturedEpochMs','sampleEpochMs') if key in packet])
            return dict(initial=initial,originals=originals,clock_join=clock,base=h.fixture.base_scene(),
                address_owner=PrivateFeatureState(h.root/'ios-navigation-address-42-inputs.json').read(),
                surface_owner=PrivateFeatureState(h.root/'ios-navigation-surface-actions.json').read(),
                missing_owner=self.missing.store.read(),directory=directory,fixture_url=h.fixture.fixture_url,
                prior=dict(originals=deepcopy(prior.state['originals']),nativeAfter=deepcopy(prior.state['clockJoin']['nativeAfter'])))

    def test_actual_cleared_lookup_history_and_its_original_owner_qualify_restoration(self):
        self.ready();call=self.acquisition();before=deepcopy(call);proof=compose(**call)
        self.assertEqual(before,call);self.assertEqual(digest(call['missing_owner']),proof['missingOwnerSha256'])
        for fault in ('missing-owner','missing-cleared','foreign-binding'):
            broken=deepcopy(call)
            if fault=='missing-owner':broken['missing_owner']=None
            elif fault=='foreign-binding':broken['missing_owner']['binding']['processIdentity']='43'
            else:
                state=unpack(broken['missing_owner']['payload'])[0];state['cleared']=None
                broken['missing_owner']['payload']=pack([state])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):compose(**broken)
        self.inputs();h=self.h
        with h.flow.held():
            image=self.owner(call,'ios-'+uuid.uuid4().hex);_result,measured,_raw=image.acquire(h.now())
            self.assertEqual(call['missing_owner'],image.originals()['missingOwner'])
            self.assertEqual(proof['missingOwnerSha256'],measured['missingOwnerSha256'])

    def test_hidden_modal_with_actual_retained_listener_cannot_qualify_cleared_ownership(self):
        with self.assertRaises(NativeUIError):self.ready(partial=True)
        self.assertIsNotNone(self.missing.store.read());self.assertIsNone(self.missing.state['cleared'])
        self.assertEqual('delivered',self.missing.state['dismiss']['phase'])


if __name__=='__main__':unittest.main()
