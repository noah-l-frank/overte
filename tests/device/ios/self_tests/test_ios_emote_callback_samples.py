"""Actual Sample3/PNG/PFS callback duty; native/SDK sources remain models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os
import uuid
import unittest
from unittest.mock import patch
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame,absent
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.adapters.emote_callback_samples import IOSEmoteCallbackSamples,EmoteCallbacksPending,archived_sample
from ios.adapters.emote_samples import IOSEmoteSamples,archived_sample as legacy_archive
from ios.self_tests import test_ios_emote_samples as sample_fixture
from ios.self_tests.emote_completed_frame_context_fixture import FrameCallbackContext
from ios.self_tests.test_ios_emote_images import MARKER_URL,NONCE
from ios.self_tests.test_ios_graphics_measurements import NATIVE,HOST,RUN,TICKET,BINDING


class Clock:
    def __init__(self,context):self.context=context
    @property
    def clock(self):return self.context.time
    @clock.setter
    def clock(self,value):self.context.set_time(value)
    def epoch(self):return NATIVE+round(self.clock*1000)
    def sleep(self,seconds):self.context.advance(seconds)
    @property
    def commands(self):return [value for slot in self.context.worlds.values() for value in slot.commands]


class CallbackSamplesTests(unittest.TestCase):
    # Reuse the actual existing typed Source/Marker/Native/PNG sample fixture;
    # the shared callback producer is selected before ANY first capture.
    sources=sample_fixture.SamplesTests.sources
    native=sample_fixture.SamplesTests.native
    world=sample_fixture.SamplesTests.world
    renderers=sample_fixture.SamplesTests.renderers
    tearDown=sample_fixture.SamplesTests.tearDown
    def setUp(self):
        sample_fixture.SamplesTests.setUp(self)
        original=self.gpu;self.context=FrameCallbackContext(retain_trace=True)
        self.gpu=Clock(self.context);self.selected_png=original.png;self.selected_pixels=original.raw_pixels
        self.extent_fault=original.fault;self.no_fence=False;self.frame_birth_ids={}
    def owner(self):
        return IOSEmoteCallbackSamples(self.runtime,'owned',self.scope,self.root,self.policy,self.phase,self.lock,
            monotonic=lambda:self.gpu.clock,epoch_ms=lambda:HOST+self.gpu.clock*1000,sleep=self.gpu.sleep)
    def vulkan(self,intent,receipt):
        last=[None]
        def send(query):
            # NativeCompletedFrame already persisted intent(query) before send.
            # Route the actual command, never treat its intent callback as a DTO.
            slot=self.context.world(query['requestId'])
            if slot.request is None:
                slot.png=self.selected_png;slot.raw_pixels=self.selected_pixels
                def original_shape(value):
                    self.extent_fault(value)
                    if 'renderTrace' in value.get('source',{}):
                        self.assertIn(slot.request_id,self.frame_birth_ids)
                        value['source']['renderTrace']['frameId']=self.frame_birth_ids[slot.request_id]
                slot.fault=original_shape
                slot.source_extent=[320,200];slot.target_extent=[640,400];slot.epoch=self.gpu.epoch
                slot.no_fence=self.no_fence
            before=slot.frame;last[0]=slot;result=slot.send(query)
            if query['operation']=='read' and slot.frame is not None and slot.frame is not before:
                # A new actual Context callback ticket was allocated by the
                # original admitted read. The fixture producer assigns its
                # fresh Frame identity before any completion/original exists.
                self.assertIs(slot.frame,slot.trace);self.assertIs(slot.frame,slot.window)
                self.assertEqual(slot.request_id,self.context.active)
                self.assertNotIn(slot.request_id,self.frame_birth_ids)
                self.frame_birth_ids[slot.request_id]=uuid.uuid4().hex
            return result
        def original():
            self.assertIsNotNone(last[0]);return last[0].original()
        return NativeVulkanWorldFrame(send,original,self.gpu.epoch,lambda:True,42,intent,receipt=receipt,
            monotonic=lambda:self.gpu.clock,sleep=self.gpu.sleep)
    def archive(self,value):
        return archived_sample(value,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock,
            policy=self.policy,marker_nonce=NONCE,marker_url=MARKER_URL)

    def test_fresh_sample_persists_callback_duty_before_return_and_actual_drain_remains_required(self):
        owner=self.owner();actual=owner.capture(TICKET);row=owner.state['rows'][-1]
        sample=owner.record(row);frame,raw,image=owner.archive(row);slot=self.context.world(row['requestId'])
        self.assertEqual(3,sample['iosEmoteSampleVersion']);self.assertEqual(3,image['iosEmoteImageVersion'])
        self.assertTrue(image['callbackPending']);self.assertFalse(absent(frame['retirement']))
        self.assertEqual(self.raw,raw);self.assertEqual(actual['image'],image['image'])
        self.assertIsNotNone(slot.callback());self.assertFalse(self.context.all_drained())
        self.assertEqual('ready',owner.state['phase']);self.assertEqual('observed',row['phase'])
        self.assertEqual(1,sum(c['operation']=='release' for c in slot.commands))
        slot.drop_retained_trace();proofs=owner.drain();self.assertTrue(all(absent(x) for x in proofs))
        self.assertTrue(self.context.all_drained());self.assertTrue(owner.archive(row)[2]['callbackPending'])
        # The saved cut stays historical; draining never rewrites its receipt.
        self.assertEqual(sample,owner.record(row))

    def test_cold_profile3_reopens_original_without_query_and_default_profile_cannot_adopt_it(self):
        original=self.owner();original.capture(TICKET);before=deepcopy(self.gpu.commands)
        rebuilt=self.owner();row=rebuilt.state['rows'][-1];self.assertEqual(self.raw,rebuilt.archive(row)[1])
        self.assertEqual(before,self.gpu.commands)
        with self.assertRaises(NativeUIError):IOSEmoteSamples(self.runtime,'owned',self.scope,self.root,self.policy,self.phase,self.lock,
            monotonic=lambda:self.gpu.clock,epoch_ms=lambda:HOST+self.gpu.clock*1000,sleep=self.gpu.sleep)
        sample=rebuilt.record(row)
        with self.assertRaises(NativeUIError):legacy_archive(sample,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock,
            policy=self.policy,marker_nonce=NONCE,marker_url=MARKER_URL)
        self.assertEqual(before,self.gpu.commands)

    def test_pending_callback_refuses_new_nonce_slot_and_capture_until_real_token_death(self):
        owner=self.owner();first=owner.capture(TICKET);rows=deepcopy(owner.state['rows'])
        slot=self.context.world(rows[-1]['requestId']);births=set(self.context.worlds)
        with self.assertRaises(EmoteCallbacksPending):owner.capture(TICKET)
        self.assertEqual(rows,owner.state['rows']);self.assertEqual(births,set(self.context.worlds))
        self.assertEqual(1,sum(c['operation']=='read' for c in self.gpu.commands))
        slot.drop_retained_trace();second=owner.capture(TICKET)
        self.assertNotEqual(first['requestId'],second['requestId'])
        self.assertEqual(2,sum(c['operation']=='read' for c in self.gpu.commands))
        self.assertEqual(1,sum(c['operation']=='release' for c in slot.commands))
        self.assertTrue(absent(owner.owner(rows[-1]).store.read()['absence']))

    def test_same_byte_png_inode_replacement_cannot_republish_sample3_after_cold_reopen(self):
        owner=self.owner();value=owner.capture(TICKET);path=Path(value['imagePath'])
        raw=path.read_bytes();before=path.stat().st_ino;replacement=path.with_suffix('.replacement')
        replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
        self.assertEqual(raw,path.read_bytes());self.assertNotEqual(before,path.stat().st_ino)
        rebuilt=self.owner();commands=deepcopy(self.gpu.commands)
        with self.assertRaises(NativeUIError):rebuilt.archive(rebuilt.state['rows'][-1])
        self.assertEqual(commands,self.gpu.commands)

    def test_unknown_gpu_work_never_becomes_callback_only_sample_or_replayed_capture(self):
        self.no_fence=True;owner=self.owner()
        with self.assertRaises(NativeUIError):owner.capture(TICKET)
        state=deepcopy(owner.state);self.assertEqual('reading',state['phase'])
        self.assertIsNone(state['rows'][-1]['sampleSha256']);before=deepcopy(self.gpu.commands)
        with self.assertRaises(NativeUIError):self.owner().capture(TICKET)
        self.assertEqual(before,self.gpu.commands);self.assertEqual(1,sum(c['operation']=='read' for c in before))
        self.assertFalse(self.context.all_drained())

    def test_historical_receipt_cannot_hide_gpu_copy_or_borrow_old_png_as_new_capture(self):
        owner=self.owner();owner.capture(TICKET);sample=owner.record(owner.state['rows'][-1]);commands=deepcopy(self.gpu.commands)
        for field,value in (('gpuPending',True),('gpuBufferBytes',1),('metadataBytes',1),('callbacks',0)):
            changed=deepcopy(sample);frame=unpack(changed['payload'])[0]
            frame['retirement']['source'][field]=value;changed['payload']=pack([frame])
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.archive(changed)
        old=deepcopy(sample);old['iosEmoteSampleVersion']=2
        with self.assertRaises(NativeUIError):legacy_archive(old,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock,
            policy=self.policy,marker_nonce=NONCE,marker_url=MARKER_URL)
        self.assertEqual(commands,self.gpu.commands)


if __name__=='__main__':unittest.main()
