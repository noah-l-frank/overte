"""Declared Native/Qt model born with the ORIGINAL actual host context.

No existing model is promoted or retimed. Readers are built after selection.
Native/Qt effects remain models; host PID/start, clocks and sleeps are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import threading
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import need
from adapters.pico4.lifecycle_source import PicoLifecycleSource
from adapters.pico4.lifecycle_drive import PicoLifecycleDrive
from adapters.pico4.lifecycle_gesture import PicoLifecycleGesture
from self_tests.pico_lifecycle_ui2_fixture import SharedWeakUi2
from self_tests.test_pico_lifecycle_drive import Boundary as DriveBoundary
from self_tests.test_pico_lifecycle_gesture import Boundary as GestureBoundary
from self_tests.test_pico_lifecycle_world import Native as OriginalNative
from self_tests.test_pico_lifecycle_source import editor
from self_tests.test_pico_chat_keyboard import keyboard
from self_tests.test_token_lifecycle_ui import Boundary as FieldBoundary
from self_tests.test_token_chat_ui import Widgets
from self_tests.test_pico_lifecycle_background_source import Native as BackgroundBoundary
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_pending_commit_owner import Boundary as PendingBoundary


class OriginalHostModel:
    def __init__(self):
        self.host=self._host=host_identity();pid,birth,boot=self.host.split(':')
        self.pid=int(pid);self.process_identity=pid+':'+birth;self.boot=boot
        self.origin=time.monotonic();self.created_epoch=time.time_ns()//1000000;self.gui_lock=threading.RLock()
        self._fixed=self._original_fixed=(self.host,self.pid,self.process_identity,self.boot,self.origin,self.created_epoch)
    def guard(self):
        need(self._fixed is self._original_fixed and (self.host,self.pid,self.process_identity,self.boot,self.origin,self.created_epoch)==self._fixed
            and self.host is self._host and host_identity()==self.host);return True
    def now(self):self.guard();return time.monotonic()-self.origin
    def epoch(self):self.guard();return time.time_ns()//1000000
    def sleep(self,seconds):
        self.guard();need(type(seconds) in (int,float) and 0<=seconds<=120);time.sleep(seconds);self.guard()
    def row(self,index=1,kind='create'):
        value=editor(index,kind);value['firstObservedEpochMs']=self.epoch();return value
    def native(self):return HostNative(self)
    def field(self):return HostField(self)
    def chat(self):return HostChat(self)
    def background(self):return HostBackground(self)
    def feature(self):return HostFeature(self)
    def pending(self):return HostPending(self)
    def pending_reader(self,case,bank):return bind_pending_reader(self,case,bank)


class HostUi(SharedWeakUi2):
    def __init__(self,context):self.context=context;super().__init__();self.rows=[context.row()]
    def send(self,request):
        with self.context.gui_lock:return self._send(request)
    def _send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignore:return
        self.value=self.observe(request)
    def observe(self,request):
        # Native internal UI providers return a map. Only public SDK send
        # publishes the reply mailbox; a real model timer cannot rewrite it.
        with self.context.gui_lock:return self._observe(request)
    def _observe(self,request):
        self.context.guard();self.sequence+=1;k=keyboard(self.raised);k['sequence']=self.sequence
        selected=[row['id'] for row in self.rows if row['current']]
        value=dict(lifecycleUiVersion=2 if request.get('schemaVersion',1)==2 else 1,
            commandId=request['commandId'],runId=request['runId'],instance='c'*32,sequence=self.sequence,
            processId=self.context.pid,capturedEpochMs=self.context.epoch(),source=dict(complete=True,
                tabletShown=self.shown,onHomeScreen=self.home,current=selected[0] if selected else '',editors=deepcopy(self.rows),keyboard=k))
        if value['lifecycleUiVersion']==2:
            for row,observed in zip(self.rows,value['source']['editors']):
                token=self.token(row);live=all(row[name] for name in ('fieldAlive','windowAlive','contextAlive'))
                observed['fieldBinding']=dict(lifecycleFieldBindingVersion=1,uiFieldId=observed['fieldId'],
                    pendingFieldToken=token,weakBirth=token,status='linked' if live else 'retired' if token else 'unobserved')
        if self.mutate:self.mutate(value)
        return value
    def source(self):
        return PicoLifecycleSource(self.send,self.read,self.context.epoch,lambda:self.alive,self.context.pid,
            monotonic=self.context.now,sleep=self.context.sleep,field_bindings=True)


class HostDrive(DriveBoundary):
    def __init__(self,context):self.context=context;super().__init__()
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignore:return
        self.context.guard();self.sequence+=1
        self.value=dict(lifecycleDriveVersion=1,commandId=request['commandId'],runId=request['runId'],instance='b'*32,
            sequence=self.sequence,processId=self.context.pid,capturedEpochMs=self.context.epoch(),source=deepcopy(self.source))
        if self.mutate:self.mutate(self.value)
    def reader(self):
        return PicoLifecycleDrive(self.send,self.read,self.context.epoch,lambda:self.alive,self.context.pid,
            monotonic=self.context.now,sleep=self.context.sleep)


class HostGesture(GestureBoundary):
    def __init__(self,context):
        self.context=context;super().__init__();epoch=context.epoch()
        self.source.update(createdEpochMs=epoch,frameEpochMs=epoch);self.source['events'][0].update(occurredEpochMs=epoch,elapsedMs=0)
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignore:return
        self.context.guard();self.sequence+=1
        self.value=dict(gestureObservationVersion=1,commandId=request['commandId'],runId=request['runId'],instance='b'*32,
            sequence=self.sequence,processId=self.context.pid,capturedEpochMs=self.context.epoch(),source=deepcopy(self.source))
        if self.mutate:self.mutate(self.value)
    def reader(self):
        return PicoLifecycleGesture(self.send,self.read,self.context.epoch,lambda:self.alive,self.context.pid,
            monotonic=self.context.now,sleep=self.context.sleep)


class HostNative(OriginalNative):
    def __init__(self,context):
        self.context=context;self.alive=True;self.ui=HostUi(context);self.ui.rows=[];self.ui.raised=False;self.ui.shown=False
        self.drive=HostDrive(context);self.axes=HostGesture(context);self.axis_frame=1;self.changed=None;self.layer={}
        self.original_send=self.axes.send
        def axes(request):
            self.axes.clock=self.clock;self.axis_frame+=1
            self.axes.source.update(frameSequence=self.axis_frame,frameEpochMs=self.epoch(),frameElapsedMs=round(self.clock*1000))
            self.original_send(request)
        self.axes.send=axes
        original_drive=self.drive.send
        def drive(request):self.drive.clock=self.clock;original_drive(request)
        self.drive.send=drive
    @property
    def clock(self):return self.context.now()
    @clock.setter
    def clock(self,value):
        # Existing effects may advance real time, never reset it/skip quiet.
        need(type(value) in (int,float) and value>=0);remaining=value-self.context.now()
        if remaining>0:self.context.sleep(remaining)
    def epoch(self):return self.context.epoch()
    def sleep(self,seconds):
        self.context.sleep(seconds)
        if self.changed:self.changed(self)
    def create(self):self.ui.rows=[self.context.row()];self.ui.raised=self.ui.shown=True


class HostField(FieldBoundary):
    def __init__(self,context):self.context=context;super().__init__(pid=context.pid)
    def capture(self):
        self.clock=self.context.now();return super().capture()


class HostChat(Widgets):
    def __init__(self,context):self.context=context;super().__init__();self.pid=context.pid
    def capture(self):self.elapsed=round(self.context.now()*1000);return super().capture()


class HostBackground(BackgroundBoundary):
    def __init__(self,context):
        self.context=context;super().__init__(pid=context.pid);self.epoch=context.epoch();self.host=context.now()
        self.stop_event=threading.Event();self.timer_thread=None
    def publish(self,state):
        with self.context.gui_lock:
            self.qt=state;self.signals+=1;self.focus=False
            self.epoch=self.context.epoch();self.host=self.context.now();self.frame('application-state')
    def timer(self):
        while not self.stop_event.wait(.25):
            with self.context.gui_lock:
                if not self.active:return
                if self.context.epoch()-self.armed_epoch>20000:
                    self.expired=True;self.available=False;self.active=False;return
                if len(self.frames)>=96:self.available=False;self.active=False;return
                # This is an actual independent MODEL timer. Same original UI
                # provider, no additional SDK/native reader or requested facts.
                self.frame('timer')
    def send(self,request):
        with self.context.gui_lock:
            self.epoch=self.context.epoch();self.host=self.context.now()
            result=super().send(request)
            if request['operation']=='arm' and self.active:
                need(self.timer_thread is None)
                self.timer_thread=threading.Thread(target=self.timer,name='declared-qt250-background',daemon=False)
                self.timer_thread.start()
            if request['operation']=='release':self.stop_event.set()
        if request['operation']=='release' and self.timer_thread is not None:
            self.timer_thread.join(1);need(not self.timer_thread.is_alive())
        return result
    def close_host(self):
        self.stop_event.set()
        if self.timer_thread is not None:self.timer_thread.join(1)
        return self.timer_thread is None or not self.timer_thread.is_alive()


class HostFeature(FeatureBoundary):
    def __init__(self,context):
        self.context=context;super().__init__(pid=context.pid,epoch_ms=context.epoch)
    def reader(self,**kwargs):
        from adapters.native_feature_observation import NativeFeatureObservation
        return NativeFeatureObservation(self.send,self.original,self.context.epoch,self.guard,self.context.pid,
            monotonic=self.context.now,sleep=self.context.sleep,**kwargs)


class HostPending(PendingBoundary):
    def __init__(self,context):
        self.context=context;super().__init__(pid=context.pid);self.epoch=context.epoch


def bind_pending_reader(context,case,bank):
    # Existing real NativePending reader and SAME typed PendingRead/Raw4 bank.
    import os
    from pathlib import Path
    import tempfile
    from types import SimpleNamespace
    from adapters.native_feature_observation import NativeFeatureObservation
    from adapters.pending_commit_owner import NativePendingCommitOwner
    from adapters.pico4.lifecycle_pending_read import PicoLifecyclePendingRead,PATH,PACKAGE
    from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
    from self_tests.test_pico_lifecycle_pending_read import LocalSdkModel
    need(type(context) is OriginalHostModel and type(bank) is LifecycleSourceRaw4
        and bank.pending_read_version==1 and bank.binding['processIdentity']==context.process_identity
        and bank is case.background.originals and case.world.pid==context.pid)
    temporary=tempfile.TemporaryDirectory(prefix='lifecycle-pending-native-host-');case.addCleanup(temporary.cleanup)
    root=Path(temporary.name);root.chmod(0o700);path=root/PATH;path.parent.mkdir(parents=True,mode=0o700);path.parent.chmod(0o700)
    sdk=LocalSdkModel(root);target='explicit-pending-read-target'
    def same(actual,identity,_label):
        context.guard();need(actual==target and identity==context.process_identity)
    adapter=SimpleNamespace(kind='pico',profile={'package':PACKAGE},adb=sdk,require_same_process=same)
    transport=PicoLifecyclePendingRead(adapter,target,bank.binding,bank.archive,bank=bank,monotonic=context.now)
    writes=[]
    def original_write(wrapper):
        need(wrapper['action']=='feature-pico-pending-read' and type(wrapper['picoPendingReadVersion']) is int
            and wrapper['picoPendingReadVersion']==1)
        writes.append(deepcopy(wrapper));request=deepcopy(wrapper)
        del request['picoPendingReadVersion'];request['action']='feature-pending-commit-owner'
        case.boundary.send(request);raw=case.pending_original().encode('utf-8')
        fd,name=tempfile.mkstemp(prefix='native-model-',dir=path.parent)
        try:
            os.fchmod(fd,0o600);position=0
            while position<len(raw):
                count=os.write(fd,raw[position:]);need(type(count) is int and count>0);position+=count
            os.fsync(fd)
        finally:os.close(fd)
        os.replace(name,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        try:os.fsync(directory)
        finally:os.close(directory)
    selected=transport.dispatch
    def send(request):
        context.guard();return selected(request,original_write)
    native=NativeFeatureObservation(send,lambda:None,context.epoch,context.guard,context.pid,
        monotonic=transport.monotonic,sleep=context.sleep)
    transport.bind_native(native,original_write,selected)
    def unavailable():raise AssertionError('The explicit bounded mode cannot query an unbounded getter')
    owner=NativePendingCommitOwner(native.send,unavailable,native.clock_ms,native.guard,native.pid,
        monotonic=native.monotonic,sleep=native.sleep)
    transport.bind(owner,native=native,target=target,binding=bank.binding)
    case.pending_sdk=sdk;case.pending_wire=transport;case.pending_native=native;case.pending_writes=writes
    return owner
