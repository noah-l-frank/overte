"""Real private/source/image/input owners; native/GPU/SDK clocks are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_baseline_image import NavigationBaselineImage
from ios.adapters.navigation_whole_preparation import NavigationWholePreparation
from ios.self_tests.navigation_baseline_image_fixture import Baseline


class NavigationWholePreparationTests(unittest.TestCase):
    def setUp(self):
        self.base=Baseline(self);self.h=h=self.base.h;self.flow=h.flow
        # The lower fixture's immutable seed predates this whole acquisition.
        # Retain it explicitly rather than changing any original packet.
        seed=self.flow.store.path.with_name('ios-navigation-scene-admission.json')
        seed.rename(seed.with_name('modeled-native-seed-admission.json'))
        self.sources=self.base.sources
        runtime=self.flow.runtime;test=self
        runtime._sources=lambda _selector:dict(binding=deepcopy(h.binding),check=lambda:h.sdk.okay)
        def image(selector,client,run,role,request,root,lock):
            return NavigationBaselineImage(PrivateFeatureState(h.root/('ios-navigation-baseline-'+role+'-'+request[4:]+'.json')),
                root,h.binding,run,role,request,lock,lambda:h.sdk.okay,native=h.native,sources=test.sources,fixture=h.fixture,
                frame_factory=h.gpu.factory,epoch_ms=h.now,monotonic=h.mono,sleep=h.sdk.gpu.sleep)
        runtime._navigation_baseline_image=image
        def admission(selector,client,run,lock):
            return NavigationAdmissionOwner(PrivateFeatureState(h.root/'ios-navigation-scene-admission.json'),h.binding,run,lock,
                lambda:h.sdk.okay,native=h.native,sources=test.sources,fixture=h.fixture,epoch_ms=h.now,monotonic=h.mono)
        runtime._navigation_admission_owner=admission

    def owner(self):return NavigationWholePreparation(self.flow)

    def test_both_actual_untouched_images_precede_fresh_admission_and_one_normal_entry(self):
        owner=self.owner();owner.prepare();self.assertEqual('entered',owner.state['phase'])
        inputs=self.h.flow_fixture.b.inputs
        self.assertEqual(1,inputs.count('PhoneAddressGoButton'))
        with self.flow.held():
            images,admission=owner.originals()
            self.assertEqual({'primary','actor'},set(images))
            for role,image in images.items():
                self.assertEqual(role,image.role);self.assertEqual(b'\x89PNG\r\n\x1a\n',image.archive()[2][:8])
            self.assertEqual(self.flow.state['admissionSha256'],owner.state['admission']['ownerSha256'])
        before=deepcopy(inputs);files={p:(p.stat().st_ino,p.read_bytes()) for p in self.h.root.glob('navigation-baseline-*.json')}
        again=self.owner();again.prepare();self.assertEqual(before,inputs)
        self.assertEqual(files,{p:(p.stat().st_ino,p.read_bytes()) for p in files})

    def test_lost_completed_child_return_adopts_the_same_original_without_gpu_query_or_rewrite(self):
        factory=self.flow.runtime._navigation_baseline_image;lost=[]
        def image(*args,**kwargs):
            owner=factory(*args,**kwargs);capture=owner.acquire
            def acquire(barrier):
                value=capture(barrier)
                if not lost:lost.append(owner.request);raise OSError('Modeled lost completed child return')
                return value
            owner.acquire=acquire;return owner
        self.flow.runtime._navigation_baseline_image=image;owner=self.owner()
        with self.assertRaises((NativeUIError,OSError)):owner.prepare()
        self.assertEqual([],self.h.flow_fixture.b.inputs)
        with self.flow.held():
            owner.load();before=owner.baseline('primary',historical=True)
            inode=before.store.path.stat().st_ino;raw=before.store.path.read_bytes();commands=deepcopy(self.h.gpu.commands)
        self.flow.runtime._navigation_baseline_image=factory
        again=self.owner();again.prepare()
        self.assertEqual((inode,raw),(before.store.path.stat().st_ino,before.store.path.read_bytes()))
        # The first request appears once in the actual GPU read history. Other
        # commands belong to the distinct actor image and ordinary entry.
        first=[c for c in self.h.gpu.commands if c.get('requestId')==lost[0] and c.get('operation')=='read']
        self.assertEqual(1,len(first));self.assertTrue(commands)

    def test_issued_without_child_stays_unresolved_and_cannot_send_the_next_image_or_input(self):
        owner=self.owner();write=owner.store.write;lost=[]
        def save(value,previous):
            write(value,previous);state=unpack(value['payload'])[0]
            if state['baselines']['primary']['phase']=='issued' and not lost:
                lost.append(True);raise OSError('Modeled lost pre-query admission return')
        with patch.object(owner.store,'write',side_effect=save),self.assertRaises((NativeUIError,OSError)):owner.prepare()
        commands=deepcopy(self.h.gpu.commands)
        with self.assertRaises(NativeUIError):self.owner().prepare()
        self.assertEqual(commands,self.h.gpu.commands);self.assertEqual([],self.h.flow_fixture.b.inputs)

    def test_lost_whole_entry_return_reopens_the_actual_ack_without_another_capture_or_go(self):
        owner=self.owner();write=owner.store.write;lost=[]
        def save(value,previous):
            if unpack(value['payload'])[0]['phase']=='entered' and not lost:
                lost.append(True);raise OSError('Modeled lost whole entry return')
            write(value,previous)
        with patch.object(owner.store,'write',side_effect=save),self.assertRaises((NativeUIError,OSError)):owner.prepare()
        commands=deepcopy(self.h.gpu.commands);inputs=deepcopy(self.h.flow_fixture.b.inputs)
        self.assertEqual(1,inputs.count('PhoneAddressGoButton'))
        again=self.owner();again.prepare();self.assertEqual('entered',again.state['phase'])
        self.assertEqual(commands,self.h.gpu.commands);self.assertEqual(inputs,self.h.flow_fixture.b.inputs)

    def test_partial_child_and_foreign_candidate_prevent_next_query_and_preserve_responsibility(self):
        factory=self.flow.runtime._navigation_baseline_image;lost=[]
        def image(*args,**kwargs):
            owner=factory(*args,**kwargs);take=owner.take
            def actual(key,operation):
                value=take(key,operation)
                if key=='base' and not lost:lost.append(True);raise OSError('Modeled partial baseline return')
                return value
            owner.take=actual;return owner
        self.flow.runtime._navigation_baseline_image=image
        with self.assertRaises((NativeUIError,OSError)):self.owner().prepare()
        self.flow.runtime._navigation_baseline_image=factory;commands=deepcopy(self.h.gpu.commands)
        with self.assertRaises(NativeUIError):self.owner().prepare()
        self.assertEqual(commands,self.h.gpu.commands)
        self.h.sdk.okay=False
        with self.assertRaises(NativeUIError):self.owner().prepare()
        self.assertEqual([],self.h.flow_fixture.b.inputs)


if __name__=='__main__':unittest.main()
