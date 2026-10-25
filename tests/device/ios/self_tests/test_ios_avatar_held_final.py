"""Actual paired private final owners and worldless Web; native producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.avatar_final import IOSAvatarFinal
from ios.adapters.avatar_held_final import IOSAvatarHeldFinal
from ios.adapters.avatar_held_tail import IOSAvatarHeldTail
from ios.adapters.avatar_marker_web_receipts import IOSAvatarMarkerWebReceipts
from ios.self_tests import test_ios_avatar_final as fixture
from ios.self_tests.test_ios_web_closures import ClosureBoundary,URL


class AvatarHeldFinalTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarFinalTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.web={}
        original_owned=self.f.owned
        def owned(subject,query):
            raw=PrivateFeatureState(self.f.cases[subject].f.root/'ios-avatar-primary-marker-web.json').read()
            if raw is not None:
                p=unpack(raw['payload'])[0]['pending']
                if p is not None and any(query==row['query'] for row in p['nativeQueries']):return
            return original_owned(subject,query)
        self.f.owned=owned
        for subject,config in self.f.inputs.items():
            config['markerFixtureUrl']=URL;config['paths']['web']=str(self.f.cases[subject].f.root/'ios-avatar-primary-marker-web.json')
            b=ClosureBoundary();b.version=5;b.retired=1;b.resources['policy-grant']=dict(created=1,retired=1,pending=0);self.web[subject]=b
            def mutate(value,subject=subject):
                value.update(processId=int(self.f.bindings[subject]['processIdentity']),capturedEpochMs=self.f.cases[subject].f.f.now(),
                    instance=('b' if subject=='primary' else 'd')*32)
            b.mutate=mutate
    def factory(self,subject):
        actual=self.f.factory(subject,Tail=IOSAvatarHeldTail);old=actual['tail'];config=self.f.inputs[subject];clock=actual['pointers'].native
        reader=self.web[subject].reader();reader.pid=int(self.f.bindings[subject]['processIdentity']);reader.monotonic=lambda:self.f.clock[0]
        reader.clock_ms=lambda:clock.read(clock.sequence)['capturedEpochMs']
        reader.sleep=lambda seconds:self.f.clock.__setitem__(0,self.f.clock[0]+seconds)
        actual['web']=IOSAvatarMarkerWebReceipts(PrivateFeatureState(config['paths']['web']),old.root,old.binding,old.run,old.role,old.lock,old.guard,
            native=clock,reader=reader,fixture_url=config['markerFixtureUrl'],epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
        return actual
    def owner(self):
        return IOSAvatarHeldFinal(self.f.store,self.f.root,self.f.bindings,fixture.RUN,'primary',self.f.locks,lambda:True,self.factory,
            self.f.authority,self.f.inputs,epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0],sleep=lambda n:self.f.clock.__setitem__(0,self.f.clock[0]+n))
    def archive(self,owner):
        return IOSAvatarHeldFinal.archive(owner.previous,store=owner.store,root=owner.root,bindings=owner.bindings,run=owner.run,role=owner.role,
            locks=owner.locks,authority=owner.authority,inputs=owner.inputs)
    def test_new_four_component_final_keeps_web_originals_and_actual_native_quiet_with_no_legacy_alias(self):
        owner=self.owner();refs=[]
        for sequence in (1,2,3):
            if refs:self.f.clock[0]+=1.7
            refs.append(self.f.capture(owner,sequence))
        self.assertEqual(2,owner.previous['iosAvatarFinalVersion']);proof=owner.quiet(refs,sequence=4)
        self.assertEqual(2,proof['iosAvatarFinalProofVersion']);parts=owner.group(owner.record(refs[-1]))
        self.assertEqual(4,parts['primary']['proof']['iosAvatarPostLogoutTailProofVersion'])
        self.assertTrue(parts['primary']['webReceipt']['packet']['contexts'][0]['resources']['vulkan-image']['pending'])
        counts={s:len(b.commands) for s,b in self.web.items()}
        self.assertEqual(proof,self.archive(owner).quiet(refs,sequence=4));self.assertEqual(counts,{s:len(b.commands) for s,b in self.web.items()})
        with self.assertRaises(NativeUIError):IOSAvatarFinal.archive(owner.previous,store=owner.store,root=owner.root,bindings=owner.bindings,
            run=owner.run,role=owner.role,locks=owner.locks,authority=owner.authority,inputs=owner.inputs)


if __name__=='__main__':unittest.main()
