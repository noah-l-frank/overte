"""Whole local original cleanup join; native/Qt/GPU producers are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.native_script_files import NativeScriptFiles
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts
from ios.adapters.emote_rendered_retirement import IOSEmoteRenderedRetirement
from ios.adapters.emote_retirement import IOSEmoteRetirement
from ios.adapters.emote_retirement_scope import refresh
from ios.adapters.emote_sources import IOSEmoteSources
from ios.self_tests import test_ios_emote_restoration_journey as journey
from ios.adapters.emote_controls import project
from ios.self_tests.marker_entities_fixture import EntityDomain
from ios.self_tests.emote_pointer_fixture import PointerDomain
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,phase
from self_tests.test_native_script_files import Boundary as FileBoundary
from self_tests.test_emote_rig_measurements import RigPackets


class RenderedRetirementTests(unittest.TestCase):
    def setUp(self):
        self.fixture=journey.RestorationJourneyTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;self.scope,self.domain,self.root,self.lock=f.scope,f.domain,f.root,f.lock
        self.pointers=PointerDomain(self,self.scope,self.domain).owner();self.pointers.capture()
        self.entities=EntityDomain(self,self.scope,self.domain).owner();self.entities.capture()
        from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
        self.frames=IOSEmoteRestorationFrames(f.runtime,'owned',self.scope,self.root,self.lock,
            monotonic=self.scope.monotonic,epoch_ms=self.scope.epoch_ms,sleep=self.scope.sleep)
        self.initial=self.frames.capture('initial');self.scope.prepare();self.domain.paint();self.scope.admit_rendered();self.scope.cleanup()
        refresh(self.scope,clock=self.scope.monotonic,sleep=self.scope.sleep,pointers=self.pointers)
        if self._testMethodName=='test_new_native_override_and_restore_after_quiet_requires_a_new_quiet_interval':
            # Actual new modeled API calls occur after quiet and before the
            # later original observations. Existing packet bytes stay intact.
            epoch=self.domain.epoch();send=self.domain.native_send
            events=[dict(eventSequence=1,kind='override',overrideSequence=1,capturedEpochMs=epoch,caller=None,
                request=dict(url='file:///native/unrelated.fbx',framesPerSecond=60.,loop=False,firstFrame=0.,lastFrame=120.)),
                dict(eventSequence=2,kind='restore',overrideSequence=1,capturedEpochMs=epoch+1,caller=None)]
            def called(query):
                send(query);history=self.domain.boundary.sample['animation']['history']
                self.domain.history[-1]['overrideSequence']=1
                history.update(callSequence=2,overrideSequence=1,events=deepcopy(events),frames=deepcopy(self.domain.history[-32:]))
            self.domain.native_send=called;self.scope.native.send=called;self.domain.sleep(.002)
        self.entities.capture();self.entities.closed(self.scope)
        boundary=FileBoundary(self.root);boundary.root=self.domain.files.root
        def sending(query):
            self.domain.sleep(.001);boundary.send(query);boundary.sample.update(requestedEpochMs=self.domain.epoch(),capturedEpochMs=self.domain.epoch())
        files=NativeScriptFiles(sending,boundary.read,self.domain.epoch,lambda:True,31,ios=True,
            monotonic=self.scope.monotonic,sleep=self.scope.sleep)
        self.files=IOSEmoteFileReceipts(PrivateFeatureState(self.root/'native-files.json'),self.root,BINDING,RUN,'primary',self.lock,
            lambda:True,native=self.scope.native,files=files,epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic)
        self.files.capture('absent',self.scope.state['fileOwnership']);self.current=self.frames.capture('cleanup')
        self.sources=IOSEmoteSources(PrivateFeatureState(self.root/'ios-emote-primary-sources.json'),self.root,BINDING,RUN,'primary',self.lock,
            lambda:True,None,historical=True);self.sources.historical=False;self.sources.save();self.model=RigPackets()
        original=self.read_original()
        self.native=IOSEmoteRetirement(PrivateFeatureState(self.root/'native-retirement.json'),self.root,BINDING,BINDING,RUN,'primary',
            self.scope.fixture_url,'3'*32,self.lock,self.lock,dict(source='world-render-target'),
            dict(sources=self.sources.store.path,peers=None,files=self.files.store.path,entities=self.entities.store.path,pointers=self.pointers.store.path),lambda:True)
        self.native_reference=self.native.retain(original)

    def read_original(self):
        d=self.domain;host_before=self.scope.epoch_ms();mono_before=d.time
        before=self.scope.native.read(self.scope.native.sequence)
        group=self.model.group(self.scope.native.read(before['sequence']));widgets=d.widgets();world=d.world(RUN)
        after=self.scope.native.read(group['native']['sequence']);host_after=self.scope.epoch_ms();mono_after=d.time
        originals=dict(group,widgets=widgets,world=world)
        join=dict(clockJoinVersion=1,hostBeforeEpochMs=host_before,hostAfterEpochMs=host_after,hostBeforeMonotonic=mono_before,
            hostAfterMonotonic=mono_after,nativeBefore=before,nativeAfter=after,originalsSha256=digest(originals),sourceTimes=[
                dict(source=name,field=field,epochMs=packet[field]) for name,packet in originals.items()
                for field in ('capturedEpochMs','sampleEpochMs') if field in packet])
        start,end=phase(1,host_before),phase(2,host_after)
        for value in (start,end):value['activations'][-1]['stimulus']=dict(verb='cleanup',inputs={})
        frame=dict(group=group,widgets=widgets,ui=project(widgets),world=world,clockJoin=join,phaseBefore=start,phaseAfter=end)
        self.sources.validate_frame(frame);self.sources.state.update(phase='reading',pending=dict(original=None,manifest=None,partial={}));self.sources.save()
        item=self.sources.originals.write(1,frame);self.sources.state['manifests']=self.sources.originals.append([],item)
        self.sources.frames.append(frame);self.sources.state.update(phase='ready',revision=1,pending=None);self.sources.save()
        ref=dict(index=1,sha256=digest(frame))
        observation=dict(iosEmoteObservationOriginalVersion=1,runId=RUN,role='primary',binding=BINDING,primaryBinding=BINDING,sequence=1,
            ticket='4'*32,source=ref,sourceRecovery=None,peerRecovery=None,proof=dict(kind='idle',baseline=ref,before=None,played=None,inputBarrier=None),
            peerBefore=None,peerAfter=None,marker=None,imageBefore=None,image=None,
            acquisition={key:join[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')})
        self.pointers.capture()
        return dict(observation=observation,sources=self.sources.store.read(),peers=None,scope=self.scope.store.read(),fileReceipts=self.files.store.read(),
            entities=self.entities.store.read(),pointers=self.pointers.store.read(),sampleOwners=None,inputOwners=dict(cleanup=None,actions=None,background=None))

    def test_actual_scope_pointer_entity_file_gpu_and_pixels_join_without_product_reacquisition(self):
        owner=IOSEmoteRenderedRetirement(PrivateFeatureState(self.root/'rendered-retirement.json'),self.native,self.frames)
        write=PrivateFeatureState.write;lost=[]
        def lost_return(store,value,previous):
            write(store,value,previous)
            if store.path==owner.record_store(1).path and not lost:lost.append(True);raise OSError('Lost rendered original return')
        count=len(self.domain.history)
        with patch.object(PrivateFeatureState,'write',lost_return),self.assertRaises(OSError):
            owner.retain(dict(nativeReference=self.native_reference,frames=self.frames.store.read(),initialReference=self.initial,currentReference=self.current))
        owner=IOSEmoteRenderedRetirement(owner.store,self.native,self.frames);ref=owner.resolve();result=owner.derive(ref)
        self.assertEqual([],result['public']['resources']);self.assertEqual('ios-emote-rendered-retirement-original',result['retirement']['provenance']['namespace'])
        self.assertEqual(count,len(self.domain.history))
        rebuilt=IOSEmoteRenderedRetirement(owner.store,self.native,self.frames)
        self.assertEqual(result,rebuilt.derive(ref));self.assertEqual(count,len(self.domain.history))

    def test_later_fence_cannot_borrow_an_earlier_source_observation_or_initial_image(self):
        owner=IOSEmoteRenderedRetirement(PrivateFeatureState(self.root/'rendered-retirement.json'),self.native,self.frames)
        current=self.frames.capture('cleanup')
        cases=[dict(initialReference=self.initial,currentReference=current),
               dict(initialReference=self.current,currentReference=current),
               dict(initialReference=self.initial,currentReference=self.current)]
        for fields in cases:
            value=dict(nativeReference=self.native_reference,frames=self.frames.store.read(),**fields)
            with self.subTest(fields=fields),self.assertRaises(NativeUIError):owner.retain(value)
            self.assertTrue(owner.abandon())
        self.assertEqual(3,len(owner.state['abandoned']))

    def test_new_native_override_and_restore_after_quiet_requires_a_new_quiet_interval(self):
        owner=IOSEmoteRenderedRetirement(PrivateFeatureState(self.root/'rendered-retirement.json'),self.native,self.frames)
        self.assertEqual(2,self.sources.frames[-1]['clockJoin']['nativeAfter']['animation']['history']['callSequence'])
        with self.assertRaises(NativeUIError):owner.retain(dict(nativeReference=self.native_reference,frames=self.frames.store.read(),
            initialReference=self.initial,currentReference=self.current))
        self.assertTrue(owner.abandon())


if __name__=='__main__':unittest.main()
