"""Actual durable Vulkan owner/chunks/files with synthetic native SDKs only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.evidence import MarkerNotReady
from ios.adapters.create_sample import CreateSampleOwner
from ios.adapters.create_state import IOSCreateState
from ios.self_tests.test_ios_create_world_measurements import bundle,ID,RUN,TICKET,BINDING
from self_tests.test_native_feature_observation import Boundary as ClockBoundary
from self_tests.test_native_vulkan_world_frame import World

REQUEST='ios-'+'7'*32


class CreateSampleTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.store=PrivateFeatureState(self.root/'ios-create-sample.json')
        template,raw,self.policy,self.marker=bundle();self.template=template['createBefore']
        self.sdk=World();self.sdk.source_extent=[320,200];self.sdk.target_extent=[640,400]
        image=Image.open(BytesIO(raw)).convert('RGBA');self.sdk.png=raw;self.sdk.raw_pixels=image.tobytes()
        def dimensions(value):
            if 'image' in value.get('source',{}):
                value['source']['image'].update(width=640,height=400)
                value['source']['renderTrace']['frameId']=format(self.sdk.frame_index,'032x')
        self.sdk.fault=dimensions
        self.clock=ClockBoundary();self.query=None;self.sequence=0
    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except Exception as caught:error=caught
        if error is not None:raise error
    def owner(self,request=REQUEST):
        b=self.sdk
        def stamp(value):
            b.clock+=.001;value.update(processId=42,requestedEpochMs=b.epoch(),capturedEpochMs=b.epoch(),animation={},animationFence={})
        self.clock.mutate=stamp
        native=NativeFeatureObservation(self.clock.send,self.clock.original,b.epoch,lambda:True,42,ios=True,monotonic=lambda:b.clock,sleep=b.sleep);native.native_clock_bound=True
        def send(query):self.query=deepcopy(query)
        def original():
            self.sequence+=1;b.clock+=.001;before=b.epoch();b.clock+=.001
            value=deepcopy(self.template);value.update(requestId=self.query['commandId'],sequence=self.sequence,
                clockBefore=dict(epochMs=before,monotonicMs=round(b.clock*1000)-1),clockAfter=dict(epochMs=b.epoch(),monotonicMs=round(b.clock*1000)))
            return json.dumps(value)
        source=IOSCreateState(send,original,b.epoch,lambda:True,42,monotonic=lambda:b.clock,sleep=b.sleep)
        def factory(intent,received):return NativeVulkanWorldFrame(b.send,b.original,b.epoch,lambda:True,42,intent,receipt=received,monotonic=lambda:b.clock,sleep=b.sleep)
        frame=VulkanWorldFrameOwner(PrivateFeatureState(self.root/('graphics-world-frame-primary-0-'+request[4:]+'.json')),self.root,BINDING,RUN,'primary',0,request,
            factory,lambda:True,source_lock=self.lock,monotonic=lambda:b.clock,sleep=b.sleep)
        store=self.store if request==REQUEST else PrivateFeatureState(self.root/('ios-create-sample-'+request[4:]+'.json'))
        return CreateSampleOwner(store,self.lock,BINDING,RUN,'primary',request,lambda:True,native=native,source=source,frame_owner=frame,
            epoch_ms=b.epoch,monotonic=lambda:b.clock)
    def next_gpu_request(self,*,sequence=None,reuse_frame=False,foreign_birth=False):
        previous=self.sdk;self.sdk=World();self.sdk.clock=previous.clock+.001
        self.sdk.sequence=previous.sequence if sequence is None else sequence
        self.sdk.frame_index=previous.frame_index if reuse_frame else previous.frame_index+1
        self.sdk.source_extent=deepcopy(previous.source_extent);self.sdk.target_extent=deepcopy(previous.target_extent)
        self.sdk.png=previous.png;self.sdk.raw_pixels=previous.raw_pixels
        def original(value):
            if foreign_birth:value['instance']='f'*32
            if 'image' in value.get('source',{}):
                value['source']['image'].update(width=640,height=400)
                value['source']['renderTrace']['frameId']=format(self.sdk.frame_index,'032x')
        self.sdk.fault=original
    def test_actual_chunks_private_png_native_retirement_and_historical_qualification_are_preserved(self):
        with self.held():
            owner=self.owner();owner.capture(TICKET,self.sdk.epoch());result=owner.qualify(self.policy,[ID],self.marker)
            self.assertEqual(['model'],result['state']['objects']);self.assertEqual('qualified',owner.state['phase'])
            self.assertTrue((self.root/owner.frame_owner.name).exists());self.assertFalse(owner.state['originals']['retirement']['source']['present'])
            count=len(self.sdk.commands);reconstructed=self.owner();self.assertEqual(result,reconstructed.state['qualification']);self.assertEqual(count,len(self.sdk.commands))
            tampered=deepcopy(owner.previous);from adapters.script_feature.history import unpack,pack
            state=unpack(tampered['payload'])[0];state['qualification']['state']['objects']=[];tampered['payload']=pack([state])
            with self.assertRaises(NativeUIError):owner.decode(tampered)
            with self.assertRaises(NativeUIError):reconstructed.capture(TICKET,self.sdk.epoch())
            self.assertEqual(1,sum(row['operation']=='read' for row in self.sdk.commands))
    def test_failed_original_marker_is_retained_and_never_reinterpreted_or_recaptured(self):
        with self.held():
            owner=self.owner();owner.capture('f'*32,self.sdk.epoch())
            with self.assertRaises(MarkerNotReady):owner.qualify(self.policy,[ID],self.marker)
            self.assertEqual('failed',self.owner().state['phase']);self.assertTrue((self.root/owner.frame_owner.name).exists())
            with self.assertRaises(NativeUIError):self.owner().capture(TICKET,self.sdk.epoch())
            self.assertEqual(1,sum(row['operation']=='read' for row in self.sdk.commands));owner.retire_runtime()
    def test_lost_actual_capture_is_not_reissued_and_native_cleanup_retains_host_ownership(self):
        send=self.sdk.send
        def lost(query):
            send(query)
            if query['operation']=='read':raise OSError('Lost actual native capture return')
        self.sdk.send=lost
        with self.held():
            with self.assertRaises(NativeUIError):self.owner().capture(TICKET,self.sdk.epoch())
            owner=self.owner();self.assertEqual('reading',owner.state['phase']);self.sdk.send=send;self.sdk.sleep(.2);owner.retire_runtime()
            self.assertTrue((self.root/owner.frame_owner.name).exists());self.assertEqual(1,sum(row['operation']=='read' for row in self.sdk.commands))
    def test_original_png_replacement_or_borrowed_expected_previous_subject_cannot_qualify(self):
        with self.held():
            owner=self.owner();owner.capture(TICKET,self.sdk.epoch())
            with self.assertRaises(NativeUIError):owner.qualify(self.policy,[ID],self.marker,previous=Image.new('RGB',(128,96)),changed=True)
            (self.root/owner.frame_owner.name).write_bytes(b'foreign PNG')
            with self.assertRaises(NativeUIError):self.owner()
    def test_genuine_qualified_future_sample_cannot_be_used_as_an_earlier_comparison_original(self):
        with self.held():
            first=self.owner();first.capture(TICKET,self.sdk.epoch())
            self.next_gpu_request();future=self.owner('ios-'+'8'*32);future.capture(TICKET,self.sdk.epoch());future.qualify(self.policy,[ID],self.marker)
            with self.assertRaises(NativeUIError):first.qualify(self.policy,[ID],self.marker,previous=future)
            self.assertEqual('failed',first.state['phase']);self.assertTrue((self.root/future.frame_owner.name).exists())
    def test_ordered_actual_prior_is_allowed_but_same_birth_counter_frame_reuse_and_rollover_are_not(self):
        for fault in ('none','counter','frame','birth'):
            if fault!='none':self.doCleanups();self.setUp()
            with self.subTest(fault=fault),self.held():
                first=self.owner();first.capture(TICKET,self.sdk.epoch());first.qualify(self.policy,[ID],self.marker)
                self.next_gpu_request(sequence=first.state['originals']['capture']['sequence']-2 if fault=='counter' else None,
                    reuse_frame=fault=='frame',foreign_birth=fault=='birth')
                current=self.owner('ios-'+'8'*32);current.capture(TICKET,self.sdk.epoch())
                if fault=='none':self.assertEqual(['model'],current.qualify(self.policy,[ID],self.marker,previous=first)['state']['objects'])
                else:
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):current.qualify(self.policy,[ID],self.marker,previous=first)


if __name__=='__main__':unittest.main()
