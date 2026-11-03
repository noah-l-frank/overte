"""Cold Capture3 composition on the original Policy2/Role4 owner graph.

The optional shared constructor seams are required before this factory can be
used canonically. Fixed app-source wire enters the SAME range archive before
the existing controlled-debug/navigation decoders; no input is issued here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import shlex
import subprocess
import uuid
from types import MappingProxyType

from adapters.android.adapter import ANDROID_CONTROL_MARKER,ANDROID_DEBUG_PROBE
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import integer,need,number
from adapters.pico4.emote_model_draws import PicoWorldModelDraws
from adapters.pico4.emote_stream_capacity import PicoEmoteStreamCapacity
from adapters.pico4.emote_stream_capture import PicoEmoteStreamCapture
from adapters.pico4.emote_stream_cycle import PicoEmoteStreamCycle
from adapters.pico4.emote_stream_model_raw import literal
from adapters.pico4.emote_stream_wire import _BODY,physical_stamp
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.pico4.navigation import NativeNavigationIO
from adapters.pico4.probe_originals import same_callable
from adapters.script_journey.history import canonical
from adapters.world_render_evidence import NativeWorldRenderCapture
from adapters.world_render_storage import NativeWorldRenderStorage
from adapters.world_render_receipts import NativeWorldReceiptInventory

VERSION=1
LIMIT=262144
WIRE_LIMIT=LIMIT+1+4096
FILES=MappingProxyType({'control-marker':ANDROID_CONTROL_MARKER,'probe':ANDROID_DEBUG_PROBE,
    'ui-observation':NativeNavigationIO.DIRECTORY+'observation.json',
    'ui-status':NativeNavigationIO.DIRECTORY+'status.json'})
OWNED=[]
UNRESOLVED=[]
UNCONFIRMED=[]


def script(kind):
    need(type(kind) is str and kind in FILES)
    return 'stream_path='+FILES[kind]+'\n'+_BODY.replace('CHECK_SAMPLE','')


class PicoEmoteStreamFactory:
    def __init__(self,adapter,primary_target,actor_target,cycle,index):
        need(type(cycle) is PicoEmoteStreamCycle and integer(index,1,256))
        cycle.locks();cycle.identity()
        need(type(cycle.capacity) is PicoEmoteStreamCapacity and cycle.policy.capacity is cycle.capacity
            and cycle.originals.capacity is cycle.capacity and cycle.capacity.archive is cycle.originals.archive
            and cycle.policy.version==2 and cycle.originals.archive.scope['picoEmoteStreamOriginalsVersion']==2)
        roles=dict(cycle.roles);source=cycle.streams['actor']
        need(type(primary_target) is str and primary_target==roles['primary']['target']
            and type(actor_target) is str and actor_target==roles['actor']['target']
            and roles['actor']['adapter'] is adapter is source.wire.adapter
            and source.wire.target==actor_target and cycle.phase=='armed')
        self.adapter=adapter;self.targets=(primary_target,actor_target);self.cycle=cycle
        self.index=index;self.source=source;self.archive=cycle.originals.archive
        self.capture=self._capture=None;self.initialized=self._initialized=False;self.failed=False;self.active=self._active=None
        self.guarding=self._guarding=False;self.calls=self._calls=()
        self.producers=self._producers=()
        self.capture_bounds=self._capture_bounds=None
        self.navigation=self._navigation=();self.references=self._references=()
        self.world_builder=adapter._emote_world_render_capture
        self.model_builder=adapter._emote_model_draws_observer
        self.binary=adapter.adb.execute_bytes
        self.world_factory=self._world_factory=self.world
        self.model_factory=self._model_factory=self.models
        self.original_reader=self._original_reader=self.controlled_original
        self.before_native=self._before_native=self.bind_navigation
        self._pins=(adapter,self.targets,cycle,index,source,self.archive,self.world_builder,self.model_builder,self.binary,
            json_digest(source.binding),cycle.parent,cycle.capacity,FILES,tuple(FILES.items()),LIMIT,WIRE_LIMIT,script)
        OWNED.append(self) # Retain before the actual Capture3 constructor can acquire OFDs.
        try:self.guard()
        except BaseException:self.fail();raise

    def fail(self):
        self.failed=True
        if self not in UNRESOLVED:UNRESOLVED.append(self)

    def identity(self):
        p=self._pins
        need(not self.failed and self.adapter is p[0] and self.targets is p[1] and self.cycle is p[2]
            and type(self.index) is int and self.index==p[3] and self.source is p[4] and self.archive is p[5]
            and same_callable(self.world_builder,p[6]) and same_callable(self.adapter._emote_world_render_capture,p[6])
            and same_callable(self.model_builder,p[7]) and same_callable(self.adapter._emote_model_draws_observer,p[7])
            and same_callable(self.binary,p[8]) and same_callable(self.adapter.adb.execute_bytes,p[8])
            and json_digest(self.source.binding)==p[9] and self.cycle.parent is p[10] and self.cycle.capacity is p[11]
            and self.world_factory is self._world_factory and self.model_factory is self._model_factory
            and self.original_reader is self._original_reader and self.before_native is self._before_native
            and same_callable(self.world_factory,self.world) and same_callable(self.model_factory,self.models)
            and same_callable(self.original_reader,self.controlled_original) and same_callable(self.before_native,self.bind_navigation)
            and self.navigation is self._navigation and self.references is self._references
            and self.capture is self._capture and type(self.initialized) is bool and self.initialized is self._initialized
            and self.active is self._active and FILES is p[12] and tuple(FILES.items())==p[13]
            and type(LIMIT) is int and LIMIT==p[14] and type(WIRE_LIMIT) is int and WIRE_LIMIT==p[15] and script is p[16]
            and type(self.guarding) is bool and self.guarding is self._guarding and self.calls is self._calls
            and self.producers is self._producers and self.capture_bounds is self._capture_bounds)
        if self.initialized:
            need(type(self.capture_bounds) is tuple and len(self.capture_bounds)==2
                and self.capture.bound is self.capture_bounds[1] and self.capture.guard is self.capture_bounds[1])
        for reader,clock,original,wrapped in self.producers:
            need(same_callable(reader.monotonic,clock) and same_callable(clock,self.source.monotonic))
        for row in self.navigation:
            io,read,original,controller=row
            need(type(io) is NativeNavigationIO and io.adapter is self.adapter and io.target==self.targets[1]
                and io.identity==self.source.binding['processIdentity'] and io._read is read
                and same_callable(io._controller,controller)
                and getattr(io.read,'__func__',None) is NativeNavigationIO.read
                and getattr(original,'__func__',None) is NativeNavigationIO._read
                and getattr(io.guard,'__func__',None) is NativeNavigationIO.guard
                and getattr(io.bind_input,'__func__',None) is NativeNavigationIO.bind_input)
        return True

    def guard(self):
        self.identity()
        if self.guarding:self.fail();need(False)
        self.guarding=self._guarding=True
        try:
            self.cycle.locks();self.cycle.identity();self.cycle.capacity.guard()
            need(self.cycle.streams['actor'] is self.source and self.source.wire.adapter is self.adapter
                and self.source.wire.target==self.targets[1])
            for source in self.cycle.streams.values():source.guard()
            if self.initialized:
                need(type(self.capture) is PicoEmoteStreamCapture and self.capture.cycle is self.cycle
                    and self.capture.world is self.world_factory and self.capture.models is self.model_factory)
                self.capture.bound()
            self.identity();return True
        finally:self.guarding=self._guarding=False

    def matches(self,adapter,target,source):
        self.idle();need(adapter is self.adapter and target==self.targets[1] and source is self.source);self.guard()
        return True

    def idle(self):
        self.identity()
        if self.active is not None or self.guarding:self.fail();need(False)

    def create(self):
        self.guard();need(self.capture is None and not self.initialized)
        candidate=object.__new__(PicoEmoteStreamCapture);self.capture=self._capture=candidate
        try:
            PicoEmoteStreamCapture.__init__(candidate,self.cycle,self.index,self.world_factory,self.model_factory)
            original_bound=candidate.bound
            def bound():
                self.identity() # Exact clock/config checks BEFORE original SDK/source guard callbacks.
                return original_bound()
            self.capture_bounds=self._capture_bounds=(original_bound,bound)
            candidate.bound=candidate.guard=bound
            self.initialized=self._initialized=True;self.guard();return candidate
        except BaseException:self.fail();raise

    def runtime_guard(self):
        self.guard();need(self.initialized and self.capture._component_started is not None
            and self.capture.state['phase'] in ('reading','awaiting-after'))
        return True

    def binding(self,value):
        self.idle()
        self.runtime_guard();need(canonical(value)==canonical(self.source.binding));return True

    def bind_navigation(self,io):
        self.idle()
        need(type(io) is NativeNavigationIO and len(self.navigation)<16
            and not any(row[0] is io for row in self.navigation)
            and io.adapter is self.adapter and io.target==self.targets[1]
            and io.identity==self.source.binding['processIdentity']
            and getattr(io._read,'__func__',None) is NativeNavigationIO._read
            and getattr(io.read,'__func__',None) is NativeNavigationIO.read)
        self.runtime_guard()
        original=io._read
        def read(kind):
            self.idle();need(kind in ('observation','status'))
            return self.read_literal('ui-'+kind)
        io._read=read
        self.navigation=self._navigation=(*self._navigation,(io,read,original,io._controller))
        self.guard();return self.binding

    def controlled_original(self,target,package,path,*,attempts=1):
        self.idle();need(target==self.targets[1] and package=='org.overte.pico'
            and type(attempts) is int and attempts==1 and path in (ANDROID_CONTROL_MARKER,ANDROID_DEBUG_PROBE))
        return self.read_literal('control-marker' if path==ANDROID_CONTROL_MARKER else 'probe')

    def retain(self,token,wire):
        if type(wire) is not bytes or len(wire)>WIRE_LIMIT:
            UNCONFIRMED.append((self,token,wire));need(False)
        reference=self.archive.retain(token,wire)
        self.references=self._references=(*self._references,canonical(reference))
        return reference

    def read_literal(self,kind):
        # Claim ownership using ONLY exact memory/type/holder checks. No clock,
        # Native, SDK or business callback may execute before this claim.
        self.idle();need(type(kind) is str and kind in FILES and self.initialized
            and type(self.capture) is PicoEmoteStreamCapture and self.capture._component_started is not None)
        nonce=uuid.uuid4().hex;command=dict(picoEmoteStreamRuntimeOriginalVersion=VERSION,
            runId=self.source.run,captureIndex=self.index,role='actor',kind=kind,wireNonce=nonce)
        self.active=self._active=(kind,nonce,canonical(command),self.capture._component_started)
        claim=self.active;self.calls=self._calls=(*self._calls,claim)
        try:
            self.runtime_guard()
            token=self.archive.reserve('emote-stream-runtime',command,WIRE_LIMIT,side_bytes=8*WIRE_LIMIT)
            self.runtime_guard()
            now=self.capture.monotonic();start=self.capture._component_started
            need(number(now,start,start+5) and 0<start+5-now<=5)
            remote=' '.join(shlex.quote(value) for value in ('run-as','org.overte.pico','sh','-c',script(kind),
                'overte-pico-emote-runtime',nonce,str(LIMIT+1)))
            try:wire=self.binary(['exec-out',remote],target=self.targets[1],timeout=start+5-now)
            except BaseException as error:
                cause=error if isinstance(error,subprocess.TimeoutExpired) else error.__cause__
                if isinstance(cause,subprocess.TimeoutExpired) and type(cause.output) is bytes:self.retain(token,cause.output)
                raise
            self.retain(token,wire) # Resource authority only: preserve issued late/malformed returns FIRST.
            self.runtime_guard();need(self.active is claim and self.active==(kind,nonce,canonical(command),start))
            body,physical=literal(wire,nonce)
            need(physical_stamp(physical[0])[:5]==self.source.state['nativeRootNode'])
            return body.decode('utf-8',errors='strict')
        except BaseException:self.fail();raise
        finally:
            # A rejected nested call never enters this block or clears the
            # outer claim; its original anchor remains strongly retained.
            if self.active is claim:self.active=self._active=None

    def world(self):
        self.idle()
        self.runtime_guard()
        value=self.world_builder(self.targets[1],self.source,stream_factory=self)
        need(type(value) is SerializedWorldCapture and value.source_lock is self.source.lock)
        for reader,expected in ((value.capture,NativeWorldRenderCapture),(value.storage,NativeWorldRenderStorage),
                (value.receipts.cleanup,NativeWorldReceiptInventory)):
            need(type(reader) is expected);self.bind_producer(reader)
        self.guard();return value

    def models(self):
        self.idle()
        self.runtime_guard();value=self.model_builder(self.targets[1],stream_factory=self)
        need(type(value) is PicoWorldModelDraws and value.pid==self.source.pid)
        self.bind_producer(value)
        self.guard();return value

    def bind_producer(self,reader):
        self.runtime_guard();need(not any(row[0] is reader for row in self.producers)
            and same_callable(reader.monotonic,self.source.monotonic))
        original=reader.guard
        def guard():
            # Existing source/foreign-store checks remain on BOTH sides. The
            # exact original source clock is pinned before their SDK work.
            self.guard();need(original() is not False);self.guard();return True
        reader.guard=guard
        self.producers=self._producers=(*self._producers,(reader,reader.monotonic,original,guard))


def capture(adapter,primary_target,actor_target,cycle,index):
    return PicoEmoteStreamFactory(adapter,primary_target,actor_target,cycle,index).create()
