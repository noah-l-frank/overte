"""Durable sample + genuine PNG/GPU-owner seams; all native execution fake."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from PIL import Image
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.history import unpack
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_samples import IOSEmoteSamples,EmoteMarkerPending
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests.test_ios_emote_images import bundle,MARKER_URL,NONCE
from ios.self_tests.test_ios_graphics_measurements import NATIVE,HOST,RUN,TICKET,URL,BINDING
from self_tests.test_native_feature_observation import Boundary
from self_tests.test_native_vulkan_world_frame import World


class SamplesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.template,self.raw,self.policy=bundle();self.gpu=World();self.gpu.source_extent=[320,200];self.gpu.target_extent=[640,400]
        self.gpu.png=self.raw;self.gpu.raw_pixels=Image.open(BytesIO(self.raw)).convert('RGBA').tobytes()
        def actual_extent(value):
            if 'image' in value.get('source',{}):value['source']['image'].update(width=640,height=400)
        self.gpu.fault=actual_extent
        self.gpu.epoch=lambda:NATIVE+round(self.gpu.clock*1000)
        self.boundary=Boundary();self.world_sequence=0
        self.scope=object.__new__(IOSEmoteMarkerScope);self.scope.run,self.scope.role,self.scope.binding=RUN,'primary',deepcopy(BINDING)
        self.scope.fixture_url=URL;self.scope.state=dict(phase='ready',admission=dict(marker=dict(sourceUrl=MARKER_URL)),fileOwnership=dict(nonce=NONCE))
        self.scope.bound=lambda:self.lock.assert_held()
        self.phase=object.__new__(PhaseFixtureReader);self.phase.area,self.phase.run,self.phase.fixture_url='emotes',RUN,URL
        self.phase.read=lambda:dict(ticket=TICKET,afterEpochMs=HOST-100)
        self.runtime=object.__new__(IOSScriptRuntime);self.runtime.state_path=lambda _:self.root/'session.json';self.runtime._sources=self.sources
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def owner(self):return IOSEmoteSamples(self.runtime,'owned',self.scope,self.root,self.policy,self.phase,self.lock,
        monotonic=lambda:self.gpu.clock,epoch_ms=lambda:HOST+self.gpu.clock*1000,sleep=self.gpu.sleep)
    def sources(self,_selector):
        return dict(binding=deepcopy(BINDING),check=lambda:True,clock_source=None,observer=SimpleNamespace(
            bound_native_observer=self.native,emote_world=lambda _:SimpleNamespace(last=None,read=self.world),
            avatar_renderers=lambda _:SimpleNamespace(last=None),vulkan_world_frame=self.vulkan))
    def native(self,_clock):
        def send(query):
            if self.boundary.sequence:self.gpu.clock+=.1
            self.boundary.send(query);epoch=self.gpu.epoch();value=self.boundary.sample
            value.update(processId=42,requestedEpochMs=epoch,capturedEpochMs=epoch)
            value['animationFence']['requestedEpochMs']=epoch;value['animation']['capturedEpochMs']=epoch
            value['animation']['clip']['evaluatedEpochMs']=epoch
        return NativeFeatureObservation(send,lambda:json.dumps(self.boundary.sample),self.gpu.epoch,lambda:True,42,ios=True,
            native_clock_bound=True,monotonic=lambda:self.gpu.clock,sleep=self.gpu.sleep)
    def world(self,run):
        self.assertEqual(RUN,run);self.world_sequence+=1;self.gpu.clock+=.02
        value=deepcopy(self.template['worldBefore']);value.update(requestId='ios-'+format(self.world_sequence+6000,'032x'),sequence=self.world_sequence)
        for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=self.gpu.epoch(),monotonicMs=round(self.gpu.clock*1000))
        value['source']['scriptOriginal'].update(requestedEpochMs=self.gpu.epoch(),capturedEpochMs=self.gpu.epoch())
        return value
    def vulkan(self,intent,receipt):
        return NativeVulkanWorldFrame(self.gpu.send,self.gpu.original,self.gpu.epoch,lambda:True,42,intent,receipt=receipt,
            monotonic=lambda:self.gpu.clock,sleep=self.gpu.sleep)

    def test_real_file_owner_retains_original_png_and_reconstructs_without_new_capture(self):
        owner=self.owner();actual=owner.capture(TICKET);count=len(self.gpu.commands)
        rebuilt=self.owner();row=rebuilt.state['rows'][-1];frame,raw,result=rebuilt.archive(row)
        self.assertEqual(self.raw,raw);self.assertEqual(actual['image'],result['image']);self.assertEqual(count,len(self.gpu.commands))
        self.assertEqual('observed',row['phase']);self.assertTrue(Path(actual['imagePath']).is_file())
        self.assertEqual('released',unpack(rebuilt.record(row)['owner'])[0]['phase'])
        self.assertEqual(1,sum(q['operation']=='read' for q in self.gpu.commands))

    def test_missing_current_marker_retains_failed_original_and_actual_gpu_release(self):
        image=Image.open(BytesIO(self.raw)).convert('RGBA');image.paste((128,128,128,255),(187,70,443,134));stream=BytesIO();image.save(stream,format='PNG')
        self.gpu.png=stream.getvalue();self.gpu.raw_pixels=image.tobytes()
        with self.assertRaises(EmoteMarkerPending):self.owner().capture(TICKET)
        owner=self.owner();row=owner.state['rows'][-1];frame,raw,result=owner.archive(row)
        self.assertEqual('marker-pending',row['phase']);self.assertEqual(self.gpu.png,raw);self.assertIsNone(result)
        self.assertEqual(1,sum(q['operation']=='release' for q in self.gpu.commands))

    def test_lost_native_capture_cannot_be_replayed_and_release_remains_owned(self):
        original=self.gpu.send
        def lost(query):
            original(query)
            if query['operation']=='read':raise OSError('Synthetic lost native image return')
        self.gpu.send=lost
        with self.assertRaises(NativeUIError):self.owner().capture(TICKET)
        owner=self.owner();self.assertEqual('reading',owner.state['phase']);before=len(self.gpu.commands)
        with self.assertRaises(NativeUIError):owner.capture(TICKET)
        self.assertEqual(before,len(self.gpu.commands));self.assertEqual(1,sum(q['operation']=='read' for q in self.gpu.commands))
        self.gpu.send=original;owner.drain();self.assertEqual(1,sum(q['operation']=='release' for q in self.gpu.commands))

    def test_changed_retained_png_cannot_be_republished_after_reconstruction(self):
        owner=self.owner();value=owner.capture(TICKET);Path(value['imagePath']).write_bytes(b'foreign PNG')
        owner=self.owner()
        with self.assertRaises(NativeUIError):owner.archive(owner.state['rows'][-1])


if __name__=='__main__':unittest.main()
