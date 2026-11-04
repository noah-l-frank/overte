"""Cold ordinary Emote construction on the SAME original Parent/Cycle graph.

Expected binding is execution context only. Original debug/UI initialization
runs after existing Cycle bootstrap creates the one original range archive.
This opt-in source is not yet bound publicly or a whole Common implementation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import shlex
import subprocess
import time
from types import MappingProxyType
import uuid

from adapters.android.adapter import ANDROID_CONTROL_MARKER,ANDROID_DEBUG_PROBE
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_animation_inventory import NativeAnimationInventory,FILE as INVENTORY_FILE
from adapters.native_feature_observation import NativeFeatureObservation,FILE as NATIVE_FILE,need,exact,number
from adapters.native_script_observation import NativeScriptObservation,FILE as SCRIPT_FILE
from adapters.native_script_roots import NativeScriptRoots,FILE as ROOTS_FILE
from adapters.native_script_work import NativeScriptWork,FILE as WORK_FILE
from adapters.normal_feature_state import context
from adapters.pico4.emote_common import PicoEmoteCommon
from adapters.pico4.emote_inputs import PicoEmoteInputs
from adapters.pico4.emote_lifetime import PicoEmoteLifetime
from adapters.pico4.emote_native_cycle import PicoEmoteNativeCycle
from adapters.pico4.emote_native_cycle_state import cycle_store,native_cycle_owned
from adapters.pico4.emote_sources import PicoEmoteSources
from adapters.pico4.emote_stream_capacity import PicoEmoteStreamCapacity
from adapters.pico4.emote_stream_cycle import PicoEmoteStreamCycle
from adapters.pico4.emote_stream_model_raw import literal
from adapters.pico4.emote_stream_wire import _BODY,physical_stamp
from adapters.pico4.navigation import NativeNavigationIO,PicoNavigation
from adapters.pico4.normal_emote import PicoEmoteIO
from adapters.pico4.normal_scripts import PicoScriptIO,configuration
from adapters.pico4.probe_originals import same_callable
from adapters.token_emote_ui import TokenEmoteUI

VERSION=1
LIMIT=262144
WIRE_LIMIT=LIMIT+1+4096
FILES=MappingProxyType({'marker':ANDROID_CONTROL_MARKER,'probe':ANDROID_DEBUG_PROBE,
    'observation':NativeNavigationIO.DIRECTORY+'observation.json',
    'status':NativeNavigationIO.DIRECTORY+'status.json','native':'files/overte-e2e/'+NATIVE_FILE,
    'roots':'files/overte-e2e/'+ROOTS_FILE,'script':'files/overte-e2e/'+SCRIPT_FILE,
    'inventory':'files/overte-e2e/'+INVENTORY_FILE,'work':'files/overte-e2e/'+WORK_FILE})
OWNED=[]
UNRESOLVED=[]


def script(kind):
    need(type(kind) is str and kind in FILES)
    return 'stream_path='+FILES[kind]+'\n'+_BODY.replace('CHECK_SAMPLE','')


class PicoColdScriptIO(PicoScriptIO):
    """A real original ScriptIO initialized only after original raw admission."""
    def __init__(self,navigation,runtime):
        self.navigation=self._navigation=navigation;self.runtime=self._runtime=runtime
        self.bridge=None;self.initialized=self._initialized=False

    def initialize(self):
        r=self.runtime;r.identity();r.ready()
        need(self.runtime is self._runtime and self.navigation is self._navigation
            and self.initialized is self._initialized)
        if not self.initialized:
            need(self.bridge is None);r.debug()
            try:
                PicoScriptIO.__init__(self,self.navigation) # ORIGINAL bind/snapshot/bind implementation.
                need(self.bridge==r.binding['sessionId'])
                self.initialized=self._initialized=True;r.identity()
            except BaseException:r.fail();raise

    def capture(self):
        self.initialize();value=PicoScriptIO.capture(self)
        need(value['bridgeId']==self.runtime.binding['sessionId']);return value

    def input_ready(self):
        # Reject before any inherited capture, kernel callback or input. Only
        # capture/initialize may acquire the original initial UI proof.
        need(self.runtime is self._runtime and self.navigation is self._navigation
            and self.initialized is True and self._initialized is True
            and self.runtime.debug_bound is True
            and self.runtime._debug_proof==self.runtime.binding['processIdentity']
            and self.bridge==self.runtime.binding['sessionId'])
        self.runtime.identity()

    def activate(self,identifier,*,source=None):
        self.input_ready();return PicoScriptIO.activate(self,identifier,source=source)

    def replace(self,identifier,text):
        self.input_ready();return PicoScriptIO.replace(self,identifier,text)

    def submit(self,identifier):
        self.input_ready();return PicoScriptIO.submit(self,identifier)

    def select_index(self,identifier,index):
        self.input_ready();return PicoScriptIO.select_index(self,identifier,index)

    def tablet(self,opened):
        self.input_ready();return PicoScriptIO.tablet(self,opened)

    def release(self):
        self.input_ready();return PicoScriptIO.release(self)


class PicoEmoteColdRuntime:
    def __init__(self,row,role,scene,*,monotonic=time.monotonic,sleep=time.sleep):
        exact(row,{'adapter','target','binding','phase','lock','subject'});context(row['binding'])
        need(role in ('primary','actor') and row['adapter'].kind=='pico'
            and row['adapter'].profile['package']=='org.overte.pico' and callable(monotonic) and callable(sleep))
        self.adapter,self.target,self.role=row['adapter'],row['target'],role
        self.binding=deepcopy(row['binding']);self.binding_sha=json_digest(self.binding)
        self.phase,self.lock=row['phase'],row['lock'];self.monotonic,self.sleep=monotonic,sleep
        self.cycle=self._cycle=None;self.failed=False;self.active=None;self.originals=()
        self.root_node=None;self.debug_bound=False;self._debug_proof=None;self.debug_binding=False;self.started=None;self._issued=None
        self.binary=self.adapter.adb.execute_bytes
        self._pins=(self.adapter,self.adapter.adb,self.target,role,self.phase,self.lock,
            monotonic,sleep,self.binary,self.adapter._installation,self.adapter.require_same_process,
            self.adapter.require_pico_session_identity,self.adapter.adb.foreground_package)
        self._config=self._pins
        OWNED.append(self) # Resource graph is retained before any delegated constructor.
        self.installed=self.adapter._installation(self.target);self.installed_sha=json_digest(self.installed)
        self.guard()
        self.native=self.new_native()
        controller=lambda operation:super(type(self.adapter),self.adapter).invoke(self.target,operation,{})
        self.navigation_io=NativeNavigationIO(self.adapter,self.target,self.binding['processIdentity'],controller)
        self._ui_read=self.ui_read;self.navigation_io._read=self._ui_read # Selected before original ScriptIO init.
        _state,path=self.adapter._script_paths(self.target)
        self.navigation=PicoNavigation(self.navigation_io,path,self.installed,self.binding['processIdentity'],scene,
            monotonic=self.monotonic,sleep=self.sleep)
        self.ui=PicoColdScriptIO(self.navigation,self)
        self._runtime_graph=(self.native,self.navigation_io,self._ui_read,self.navigation,self.ui)

    def fail(self):
        self.failed=True
        if self not in UNRESOLVED:UNRESOLVED.append(self)

    def identity(self):
        p=self._pins
        need(not self.failed and p is self._config and self.adapter is p[0] and self.adapter.adb is p[1]
            and (self.target,self.role)==p[2:4] and self.phase is p[4] and self.lock is p[5]
            and same_callable(self.monotonic,p[6]) and same_callable(self.sleep,p[7])
            and same_callable(self.binary,p[8]) and same_callable(self.adapter.adb.execute_bytes,p[8])
            and same_callable(self.adapter._installation,p[9]) and same_callable(self.adapter.require_same_process,p[10])
            and same_callable(self.adapter.require_pico_session_identity,p[11])
            and same_callable(self.adapter.adb.foreground_package,p[12])
            and json_digest(self.binding)==self.binding_sha and json_digest(self.installed)==self.installed_sha
            and self.cycle is self._cycle)
        if hasattr(self,'_runtime_graph'):
            native,io,reader,navigation,ui=self._runtime_graph
            need(self.native is native and self.navigation_io is io and self._ui_read is reader
                and same_callable(io._read,reader) and self.navigation is navigation and self.ui is ui
                and navigation.io is io and ui.navigation is navigation and ui.runtime is self)
        self.lock.assert_held()

    def guard(self):
        self.identity();identity=self.binding['processIdentity']
        self.adapter.require_same_process(self.target,identity,'cold ordinary Emote context')
        need(self.adapter.require_pico_session_identity(self.target)==identity
            and self.adapter.adb.foreground_package(self.target)=='org.overte.pico'
            and self.adapter._installation(self.target)==self.installed
            and all(self.installed[key]==self.binding[key] for key in ('sourceRevision','artifactSha256')))
        return True

    def bind(self,cycle):
        need(type(cycle) is PicoEmoteStreamCycle and self.cycle is None and cycle.phase=='attached')
        row=dict(cycle.roles)[self.role]
        need(row['adapter'] is self.adapter and row['target']==self.target and row['native'] is self.native
            and row['lock'] is self.lock and row['binding']==self.binding)
        self.cycle=self._cycle=cycle;self.identity()

    def ready(self):
        self.identity();need(self.cycle is not None and self.cycle.originals is not None)
        self.cycle.locks();self.cycle.identity()
        return self.cycle.originals.archive

    def fresh(self):
        self.guard();self.cycle.parent.bound();now=self.monotonic()
        need(self.started==self._read_started and number(now,self._read_started,self._read_started+5)
            and now-self._read_started<5);return now

    def retain(self,wire,issued):
        archive,token,retainer,limit=issued
        if type(wire) is not bytes or len(wire)>limit:
            UNRESOLVED.append((self,issued,wire));need(False)
        reference=retainer(token,wire);self.originals=(*self.originals,reference)
        # The actual issued owner is used even if public bookkeeping changed
        # while SDK was returning; such a change cannot permit fresh delivery.
        need(self._issued is issued);self._issued=None
        return reference

    def read(self,kind):
        self.identity();need(kind in FILES)
        if self.active is not None:self.fail();need(False)
        claim=object();self.active=claim
        try:
            archive=self.ready();self.started=self._read_started=self.monotonic();self.fresh()
            nonce=uuid.uuid4().hex
            command=dict(picoEmoteColdSourceOriginalVersion=VERSION,role=self.role,kind=kind,
                runId=self.phase.run,wireNonce=nonce,bindingSha256=self.binding_sha)
            token=archive.reserve('emote-cold-runtime',command,WIRE_LIMIT,side_bytes=8*WIRE_LIMIT)
            issued=(archive,token,archive.retain,token['limit']);self._issued=issued;now=self.fresh()
            remote=' '.join(shlex.quote(value) for value in ('run-as','org.overte.pico','sh','-c',script(kind),
                'overte-pico-emote-cold-source',nonce,str(LIMIT+1)))
            try:wire=self.binary(['exec-out',remote],target=self.target,timeout=self.started+5-now,check=False)
            except BaseException as error:
                partial=(subprocess.TimeoutExpired,subprocess.CalledProcessError)
                cause=error if isinstance(error,partial) else error.__cause__
                if isinstance(cause,partial) and type(cause.output) is bytes:self.retain(cause.output,issued)
                raise
            self.retain(wire,issued);self.fresh();need(self.active is claim)
            body,physical=literal(wire,nonce);node=physical_stamp(physical[0])[:5]
            if self.root_node is None:self.root_node=tuple(node)
            need(tuple(node)==self.root_node)
            stream=self.cycle.streams.get(self.role)
            if stream is not None and stream.state['nativeRootNode'] is not None:
                need(node==stream.state['nativeRootNode'])
            return body.decode('utf-8',errors='strict')
        except BaseException:self.fail();raise
        finally:
            if self.active is claim:self.active=None

    def original_reader(self,target,package,path,*,attempts=1):
        need(target==self.target and package=='org.overte.pico' and type(attempts) is int and attempts==1
            and path in (ANDROID_CONTROL_MARKER,ANDROID_DEBUG_PROBE))
        return self.read('marker' if path==ANDROID_CONTROL_MARKER else 'probe')

    def ui_read(self,kind):
        need(kind in ('observation','status'));return self.read(kind)

    def debug(self):
        self.ready()
        if self.debug_bound:return
        need(not self.debug_binding);self.debug_binding=True
        try:
            actual=self.adapter.require_controlled_debug_identity(self.target,original_reader=self.original_reader)
            need(actual==self.binding['processIdentity']);self._debug_proof=actual;self.debug_bound=True
        except BaseException:self.fail();raise
        finally:self.debug_binding=False

    def dispatch(self,command,observer):
        self.guard();self.debug()
        fence=getattr(observer,'phase_fence',None)
        if fence is not None and command.get('operation')!='inspect':fence.check()
        self.cycle.parent.bound() # Last source admission before the actual writer.
        self.adapter.write_control_command(self.target,self.binding['processIdentity'],'ordinary Emote source',command)

    def new_native(self):
        def send(command):return self.dispatch(command,observer)
        observer=NativeFeatureObservation(send,lambda:self.read('native'),
            lambda:self.adapter.adb.epoch_milliseconds(self.target),self.guard,
            int(self.binding['processIdentity'].split(':')[0]),monotonic=self.monotonic,sleep=self.sleep)
        return observer

    def readers(self):
        self.ready();self.debug();n=self.new_native()
        options=dict(monotonic=self.monotonic,sleep=self.sleep)
        return (NativeScriptRoots(n.send,lambda:self.read('roots'),n.clock_ms,n.guard,n.pid,**options),
            NativeScriptObservation(n.send,lambda:self.read('script'),n.clock_ms,n.guard,n.pid,**options),
            NativeAnimationInventory(n.send,lambda:self.read('inventory'),n.clock_ms,n.guard,n.pid,**options),
            self.new_native(),self.ui)

    def controls(self,intent,receipt,before_send):
        self.ui.initialize()
        return TokenEmoteUI(PicoEmoteIO(self.ui,before_send=before_send),intent,receipt=receipt,
            monotonic=self.monotonic,sleep=self.sleep)

    def work(self):
        self.ready();self.debug();n=self.new_native()
        return NativeScriptWork(n.send,lambda:self.read('work'),n.clock_ms,n.guard,n.pid,
            monotonic=self.monotonic,sleep=self.sleep)


def create_cold_common(adapter,target,roles,phase,artifact_root,source_lock,*,monotonic=time.monotonic,sleep=time.sleep,source_profile=None):
    """Explicit expected contexts without eager Native observer objects."""
    if source_profile is not None:
        from adapters.pico4.emote_source_transaction_profile import PicoEmoteSourceProfile
        need(type(source_profile) is PicoEmoteSourceProfile);source_profile.require_bootstrap()
    need(type(roles) is dict and set(roles)=={'primary','actor'})
    need(roles['primary']['adapter'] is adapter and roles['primary']['target']==target
        and roles['primary']['phase'] is phase and roles['primary']['lock'] is source_lock)
    for row in roles.values():row['lock'].assert_held()
    source_lock.assert_held();need(not native_cycle_owned(adapter,target))
    scene=configuration(os.environ);need(scene is not None)
    runtimes={role:PicoEmoteColdRuntime(roles[role],role,scene,monotonic=monotonic,sleep=sleep) for role in ('primary','actor')}
    runtime=runtimes['primary']
    source=PicoEmoteSources(adapter._emote_source_store(target,'primary'),runtime.binding,phase,'primary',source_lock,
        artifact_root,runtime.readers,runtime.guard,runtime.native.clock_ms,monotonic=monotonic)
    inputs=PicoEmoteInputs(source,adapter._emote_input_store(target),runtime.controls,runtime.ui,
        lambda:adapter._script_journey().existing_input_session(target),controller=lambda:adapter.pico_input_session(target))
    lifetime=PicoEmoteLifetime(source,runtime.work)
    parent=object.__new__(PicoEmoteNativeCycle);OWNED.append(parent)
    PicoEmoteNativeCycle.__init__(parent,cycle_store(adapter,target),inputs,lifetime,common=PicoEmoteCommon())
    configured={role:dict(row,native=runtimes[role].native) for role,row in roles.items()}
    capacity=object.__new__(PicoEmoteStreamCapacity);OWNED.append(capacity)
    PicoEmoteStreamCapacity.__init__(capacity,parent,configured,source_profile=source_profile)
    cycle=object.__new__(PicoEmoteStreamCycle);OWNED.append(cycle)
    PicoEmoteStreamCycle.__init__(cycle,parent,configured,capacity=capacity)
    for runtime in runtimes.values():runtime.bind(cycle)
    return cycle,runtimes
