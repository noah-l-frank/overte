"""One shared host callback Context and actual JS/HTTP/PNG observer fixture.

Native/SDK/GL producers remain explicit models. Real host ticket references
control pending duty; carrier reads and release never end a held callback.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from functools import partial
import uuid
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from ios.adapters.emote_callback_samples import IOSEmoteCallbackSamples
from ios.adapters.emote_callback_observation import IOSEmoteCallbackRootedObserver
from ios.self_tests import emote_active_observer_fixture as active_fixture
from ios.self_tests import emote_script_vm_fixture as vm_fixture
from ios.self_tests.emote_animation_fixture import bundled_frames
from ios.self_tests import test_ios_emote_marker_scope as marker_fixture
from ios.self_tests.emote_rooted_marker_fixture import RootedMarkerDomain
from ios.self_tests.test_ios_emote_rooted_marker_scope import rooted
from ios.self_tests.emote_completed_frame_context_fixture import FrameCallbackContext
from ios.self_tests.emote_normal_w3c_fixture import normal_tablet


class DomainContext(FrameCallbackContext):
    def __init__(self):
        self.domain=None;super().__init__(retain_trace=False)
    def set_time(self,value):
        if self.domain is not None:
            need(value>=self.domain.time)
            if value>self.domain.time:self.domain.sleep(value-self.domain.time)
        super().set_time(value)


class HostTraceConsumer:
    def __init__(self):self.active=False;self.references=[]
    def observed_ticket(self,ticket):
        if self.active:self.references.append(ticket)
    @contextmanager
    def held(self):
        need(not self.active and not self.references);self.active=True
        try:yield
        finally:self.active=False;self.references.clear()


class CallbackActiveFixture(active_fixture.ActiveObserverFixture):
    def __init__(self,*args,**kwargs):
        # Select the shared producer/actual consumer before any first capture,
        # including marker admission. Default native callback return is normal.
        self.callback_context=DomainContext()
        self.trace_consumer=HostTraceConsumer();self.frame_birth_ids={};self.callback_epoch_origin=None
        super().__init__(*args,**kwargs)

    def sync_gpu(self):
        need(self.domain.time>=self.callback_context.time)
        self.callback_context.set_time(self.domain.time)
        if self.callback_epoch_origin is not None:
            need(self.callback_epoch_origin+round(self.domain.time*1000)==self.domain.epoch())
        return self.domain.time

    def gpu_sleep(self,seconds):
        self.domain.sleep(seconds);self.sync_gpu()

    def vulkan(self,intent,receipt):
        last=[None];context=self.callback_context;context.domain=self.domain;pid=int(self.scope.binding['processIdentity'])
        if self.callback_epoch_origin is None:
            self.sync_gpu();need(not context.worlds)
            self.callback_epoch_origin=self.domain.epoch()-round(self.domain.time*1000)
            need(type(self.callback_epoch_origin) is int and self.callback_epoch_origin>0)
        def sending(query):
            self.sync_gpu();new=query['requestId'] not in context.worlds
            slot=context.world(query['requestId']);last[0]=slot
            if new:
                # Bind BOTH original Boundary.requested/event offset and its
                # completion clock before the first command for this birth.
                slot.offset=self.callback_epoch_origin;slot.epoch=self.domain.epoch
            need(slot.offset==self.callback_epoch_origin)
            if slot.request is None:
                def shape(value):
                    if 'processId' in value:value['processId']=pid
                    source=value.get('source',{})
                    if 'renderTrace' in source:
                        need(slot.request_id in self.frame_birth_ids)
                        source['renderTrace'].update(frameId=self.frame_birth_ids[slot.request_id],recordedView=self.f.recorded_view())
                    if 'image' in source:source['image'].update(width=1600,height=1000)
                slot.fault=shape;slot.source_extent=[800,500];slot.target_extent=[1600,1000]
                if query['operation']=='read':slot.png,slot.raw_pixels=self.pixels()
            before=slot.frame;result=slot.send(query)
            if query['operation']=='read' and slot.frame is not None and slot.frame is not before:
                need(slot.frame is slot.trace is slot.window and context.active==slot.request_id
                    and slot.request_id not in self.frame_birth_ids)
                self.frame_birth_ids[slot.request_id]=uuid.uuid4().hex
                self.trace_consumer.observed_ticket(slot.frame)
            return result
        def original():
            need(last[0] is not None);self.sync_gpu();return last[0].original()
        return NativeVulkanWorldFrame(sending,original,self.domain.epoch,lambda:True,pid,intent,receipt=receipt,
            monotonic=self.sync_gpu,sleep=self.gpu_sleep)


def normal_observer(test):
    # This bounded slice exercises the actual rooted observer and normal
    # actions, not paired scene/terminal coordinators or installed dispatch.
    frames=bundled_frames()
    with (patch.object(vm_fixture,'ActualEmoteVM',partial(vm_fixture.ActualEmoteVM,frame_counts=frames)),
          patch.object(active_fixture,'ActualVMRig',partial(active_fixture.ActualVMRig,pose_profile='requested-clip')),
          patch.object(marker_fixture.MarkerScopeTests,'owner',rooted),
          patch.object(active_fixture.native_fixture,'RunningDomain',RootedMarkerDomain),
          patch.object(active_fixture,'IOSEmoteSamples',IOSEmoteCallbackSamples),
          patch.object(active_fixture,'IOSEmoteObserver',IOSEmoteCallbackRootedObserver)):
        target=CallbackActiveFixture(test)
    target.w3c,target.normal=normal_tablet(target)
    return target
