"""One declared host GPU Context, actual token lifetimes; no real GPU claim.

The legacy release-delay World model is untouched. Select this producer before
its first request. Frame/Trace/Window references, not release or fence ACKs,
control its callback token. Unknown submissions retain their copy responsibility.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import threading
import uuid
import weakref
from adapters.native_feature_observation import need
from adapters.native_vulkan_world_frame import command
from self_tests.test_native_vulkan_world_frame import World


class _Copy:
    def __init__(self):self.data=bytearray(262144)


class _Ticket:
    def __init__(self,copy):self.copy=copy


class FrameCallbackContext:
    """A source-model Context; this is not an adapter ownership ledger."""
    def __init__(self,*,retain_trace=False):
        need(type(retain_trace) is bool)
        self.instance=uuid.uuid4().hex;self.sequence=0;self.time=0.;self.active=None
        self.retain_trace=retain_trace;self.worlds={};self.retired=set();self.lock=threading.RLock()

    def world(self,request_id):
        need(type(request_id) is str and re.fullmatch('ios-[a-f0-9]{32}',request_id) is not None)
        with self.lock:
            if request_id not in self.worlds:self.worlds[request_id]=FrameCallbackWorld(self,request_id)
            return self.worlds[request_id]

    def all_drained(self):
        return all(not slot.gpu_pending and slot.callback() is None and slot.copy is None for slot in self.worlds.values())

    def advance(self,seconds):
        need(type(seconds) in (int,float) and seconds>=0)
        with self.lock:self.set_time(self.time+seconds)

    def set_time(self,value):
        need(type(value) in (int,float) and value>=self.time)
        self.time=value
        # Existing declared .05s fence readiness, with no extra read/release
        # requirement. Completion is a producer event, not a carrier read ACK.
        for slot in tuple(self.worlds.values()):slot.finish_if_ready()


class FrameCallbackWorld(World):
    def __init__(self,context,request_id):
        self.context=None;self.local_time=0.
        super().__init__()
        self.context=context;self.request_id=request_id
        self.frame=self.trace=self.window=None;self.copy=None;self.callback=lambda:None
        self.finished=False;self.producing=False;self.completed_original=None;self.arm=None

    @property
    def clock(self):return self.local_time if self.context is None else self.context.time
    @clock.setter
    def clock(self,value):
        if self.context is None:self.local_time=value
        else:self.context.set_time(value)

    def _header(self):
        if self.value is not None and 'requestId' in self.value:self.value['requestId']=self.request_id
        if self.value is not None and 'instance' in self.value:self.value['instance']=self.context.instance
        self.context.sequence=self.sequence

    def send(self,query):
        command(query)
        with self.context.lock:
            need(query['requestId']==self.request_id)
            self.sequence=self.context.sequence
            operation=query['operation']
            if operation=='read' and self.request is not None:
                if (self.retired or self.context.active!=self.request_id or query!=self.arm
                        or self.completed_original is None and self.clock-self.started>=1.5):
                    self.value=dict(completedFrameVersion=1,commandId=query['commandId'],requestId=self.request_id,available=False)
                else:
                    self.value=deepcopy(self.completed_original) if self.completed_original is not None else dict(completedFrameVersion=1,
                        commandId=query['commandId'],requestId=self.request_id,pending=True)
                return
            if operation=='read-bytes' and self.context.active!=self.request_id:
                self.value={};return
            if operation=='read' and self.request is None:
                if (self.request_id in self.context.retired or self.context.active is not None
                        or len(self.context.retired)>=4096 or not self.context.all_drained()):
                    self.value=dict(completedFrameVersion=1,commandId=query['commandId'],requestId=self.request_id,available=False)
                    return
                self.arm=deepcopy(query)
                self.context.active=self.request_id;self.copy=_Copy();ticket=_Ticket(self.copy)
                self.frame=self.trace=self.window=ticket;self.callback=weakref.ref(ticket)
            if operation=='release':
                if self.request_id not in self.context.retired and len(self.context.retired)>=4096:
                    self.value={};return
                self.context.retired.add(self.request_id)
                if self.context.active==self.request_id:self.context.active=None
                self.completed_original=None
            super().send(query);self._header()
            if 'source' in (self.value or {}) and 'callbacks' in self.value['source']:
                # This count observes the actual host token. A release response
                # may still have callbacks=1 even after real fence completion.
                self.value['source']['callbacks']=0 if self.callback() is None else 1
                self.value['source']['gpuBufferBytes']=0 if self.copy is None else len(self.copy.data)

    def finish_if_ready(self):
        if (self.producing or self.finished or self.request is None or self.no_fence
                or self.clock-self.started<.05):return
        self.producing=True
        try:
            # Keep a real local Window callback reference through the entire
            # producer body; its scope ends only when this method returns.
            callback=self.window
            if not self.retired and self.clock-self.started<1.5:
                self.sequence=self.context.sequence
                self.value=dict(completedFrameVersion=1,commandId=self.request['commandId'],requestId=self.request_id,pending=True)
                super().original();self._header()
                need('vulkanWorldFrameVersion' in self.value)
                self.completed_original=deepcopy(self.value)
            self.finished=True;self.gpu_pending=False
            self.copy=None
            if callback is not None:callback.copy=None
            self.frame=self.window=None
            if not self.context.retain_trace:self.trace=None
        finally:self.producing=False

    def original(self):
        with self.context.lock:
            self.finish_if_ready()
            return json.dumps(self.value) if self.value is not None else ''

    def drop_retained_trace(self):
        # Producer/lifetime seam only: no native request, timer, GPU outcome,
        # generation reset, active-context switch or original rewrite.
        with self.context.lock:self.trace=None

    def discard_callback_without_fence(self):
        # Actual callback edges can end without successful submitted GPU work.
        # The existing Context copy holder remains sticky in this model.
        with self.context.lock:self.frame=self.trace=self.window=None
