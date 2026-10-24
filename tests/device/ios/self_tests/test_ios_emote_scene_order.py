"""Real scene HTTP ordering; native/candidate observations are explicit models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_retirement_publisher import PublicationPending
from adapters.phase_retirement_reader import PhaseRetirementReader
from feature_journeys.retirement_receipts import WEB_SCENE_STAGE,digest
from ios.adapters.emote_scene_order import IOSEmoteSceneOrder
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from self_tests.test_phase_web_marker_scene_quiet import WebMarkerSceneQuietTests


class SceneOrderTests(unittest.TestCase):
    def setUp(self):
        self.fixture=WebMarkerSceneQuietTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.f.attach('emotes')

    def reader(self,*,store=None,kind=IOSEmoteSceneOrder):
        template=self.f.primary_reader()
        return kind(store or PrivateFeatureState(self.f.root/('ios-emote-primary-scene-order-'+self.f.run+'.json')),
            template.binding,template.phase,template.guard,template.admitted_original,template.validate_admission,
            epoch_ms=lambda:self.f.now,monotonic=lambda:10.1,stage=WEB_SCENE_STAGE)

    def publish(self):
        with self.f.lock.held():self.fixture.owner().publish(self.fixture.scene())
        return self.f.adapter.request('/runs/'+self.f.run+'/retirements')['entries'][0]

    def test_later_order_reads_preserve_original_scene_clock_and_default_freshness_stays_strict(self):
        original=self.publish();self.f.now+=4000
        with self.assertRaises(NativeUIError):self.fixture.reader().read()
        first=self.reader();self.assertEqual(original,first.read()['entry'])
        self.assertEqual(1,first.previous['iosEmoteSceneOrderVersion'])
        self.assertEqual(3,first.previous['reader']['phaseRetirementReaderVersion'])
        self.f.now+=1000;second=self.reader();self.assertEqual(original,second.read()['entry'])
        self.assertEqual(2,len(second.state['records']))
        self.assertEqual(100000.,original['scene']['capturedEpochMs'])
        self.assertGreater(second.state['records'][-1]['journal']['sampleEpochMs'],original['scene']['capturedEpochMs']+1500)

    def test_explicit_metadata_does_not_enter_a_default_reader_or_accept_legacy_metadata(self):
        self.publish();reader=self.reader();reader.read()
        with self.assertRaises(NativeUIError):self.reader(store=reader.store,kind=PhaseRetirementReader)
        for fault in ('boolean','future','inner-version','unwrapped'):
            value=deepcopy(reader.previous)
            if fault=='boolean':value['iosEmoteSceneOrderVersion']=True
            elif fault=='future':value['iosEmoteSceneOrderVersion']=2
            elif fault=='inner-version':value['reader']['phaseRetirementReaderVersion']=2
            else:value=value['reader']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.decode(value)

    def test_fresh_GET_cannot_admit_a_foreign_original_even_with_a_consistent_receipt_hash(self):
        self.publish();reader=self.reader();request=reader.phase.client.request
        def foreign(path,value=None,*args,**kwargs):
            result=request(path,value,*args,**kwargs)
            if path.endswith('/retirements'):
                row=result['entries'][-1];row['binding']['targetFingerprint']='e'*64
                row['receiptSha256']=digest({key:item for key,item in row.items()
                    if key not in ('sequence','receivedEpochMs','receiptSha256')})
            return result
        with patch.object(reader.phase.client,'request',side_effect=foreign),self.assertRaises(NativeUIError):reader.read()
        self.assertIsNone(reader.store.read())

    def test_unknown_uncommitted_scene_remains_missing_and_reader_never_resends(self):
        calls,request=self.f.posts('lost-before')
        with self.f.lock.held(),patch.object(self.f.actor,'request',side_effect=request),self.assertRaises(OSError):
            self.fixture.owner().publish(self.fixture.scene())
        reader=self.reader();request=reader.phase.client.request;reads=[]
        def get_only(path,value=None,*args,**kwargs):
            self.assertIsNone(value);reads.append(path);return request(path,value,*args,**kwargs)
        with patch.object(reader.phase.client,'request',side_effect=get_only):
            for _ in range(2):
                with self.assertRaises(PublicationPending):reader.read()
        self.assertEqual(1,len(calls));self.assertTrue(reads);self.assertIsNone(reader.store.read())

    def test_phase_advance_does_not_borrow_the_previous_cleanup_scene(self):
        self.publish();reader=self.reader();reader.read();prior=deepcopy(reader.previous)
        self.f.server.journal.activate(self.f.run,uuid.uuid4().hex,'cleanup')
        with self.assertRaises((NativeUIError,PublicationPending)):reader.read()
        self.assertEqual(prior,reader.store.read())

    def test_historical_scene_does_not_relax_the_current_HTTP_acquisition_deadline(self):
        self.publish();self.f.now+=4000;reader=self.reader();request=reader.phase.client.request
        def delayed(path,value=None,*args,**kwargs):
            result=request(path,value,*args,**kwargs)
            if path.endswith('/retirements'):self.f.now+=1600
            return result
        with patch.object(reader.phase.client,'request',side_effect=delayed),self.assertRaises(NativeUIError):reader.read()
        self.assertIsNone(reader.store.read())

    def test_different_area_cannot_select_the_emote_ordering_owner(self):
        self.f.attach('world-web')
        with self.assertRaises(NativeUIError):self.reader()

    def test_coordinator_factory_selects_explicit_ordering_without_changing_legacy_freshness(self):
        original=self.publish();self.f.now+=4000;template=self.f.primary_reader()
        for kind in (IOSEmoteFeature,IOSEmoteRootedFeature):
            flow=object.__new__(kind);flow.runtime=SimpleNamespace(state_path=lambda _:self.f.root/'sdk.json')
            flow.selector='owned-primary';flow.run=self.f.run;flow.phase=template.phase
            flow.epoch_ms=lambda:self.f.now;flow.monotonic=lambda:10.1
            reader=flow.peer_retirement_reader(template.binding,template.guard,template.admitted_original,template.validate_admission)
            if kind is IOSEmoteFeature:
                self.assertEqual('complete',reader.stage)
                with self.assertRaises(PublicationPending):reader.read()
                flow.retirement_stage=WEB_SCENE_STAGE
                reader=flow.peer_retirement_reader(template.binding,template.guard,template.admitted_original,template.validate_admission)
                with self.assertRaises(NativeUIError):reader.read()
            else:
                self.assertEqual(original,reader.read()['entry'])
                self.assertEqual(1,reader.store.read()['iosEmoteSceneOrderVersion'])


if __name__=='__main__':unittest.main()
