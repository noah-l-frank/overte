"""Original Lifecycle model producers shared through the existing raw IPC.

The target models stay in the Parent. The separate worker owns ordinary native
readers and receives original response bytes only, never Parent fact results.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path

from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.native_graphics_subject import NativeGraphicsSubject,command as subject_command
from adapters.normal_feature_state import context
from adapters.pending_commit_owner import NativePendingCommitOwner,command as pending_command
from adapters.pico4 import lifecycle_source as ui,lifecycle_gesture as gesture,lifecycle_drive as drive
from adapters.pico4.lifecycle_actor_source import PicoLifecycleActorSource
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import typed_equal
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from self_tests.pico_browser_process_fixture import ProductSources,Rpc,Clock
from self_tests.test_native_graphics_subject import Boundary as SubjectBoundary


class UnavailableLifecycleProducer:
    """Declared native missing-gate/provider model: original getter returns {}.

    TestScriptingInterface's original three getters return an empty QVariantMap
    at this boundary. This produces no accepted native packet or requested fact.
    """
    def __init__(self):self.commands=[]
    def send(self,request):self.commands.append(deepcopy(request))
    def original(self):return '{}'


class LifecycleProducts(ProductSources):
    def __init__(self,case):
        self.case=case;self.native=case.editor.native;self.subject=SubjectBoundary();self.move_before_subject=False;self.fail_ui=False
        self.hold_gesture_publication=False;self.publication_host_work=0.
        self.unavailable=None;self.unavailable_producer=UnavailableLifecycleProducer()
        # One original target physics object, read by independent native getter
        # endpoints. There is no second Actor-side pose or expected-state model.
        super().__init__(case,None)

    def configuration(self):
        return dict(port=self.server.server_address[1],token=self.token,path=str(self.case.editor.root),
            binding=deepcopy(self.case.editor.binding),run=self.case.observer.run,parentHost=host_identity())

    def dispatch(self,action,value):
        self.calls.append(action);native=self.native
        if action=='host':need(value is None);return native.clock+self.publication_host_work
        if action=='epoch':need(value is None);return native.epoch()
        if action=='sleep':
            need(type(value) in (float,int) and 0<=value<=.25);native.sleep(value);return None
        if action=='candidate':
            need(value is None);return dict(binding=deepcopy(self.case.editor.binding),alive=native.alive)
        if action=='publication-host-work':
            need(value==1.4 and self.publication_host_work==0.)
            self.publication_host_work+=value;return None
        need(type(value) is dict)
        if action in ('ui','gesture','drive','subject'):
            need(set(value)=={'schemaVersion','commandId','action','runId'} and type(value['schemaVersion']) is int
                and value['schemaVersion']==1 and ui.nonce(value['commandId']) and value['runId']==self.case.observer.run)
        if action=='ui':
            if self.fail_ui:raise RuntimeError('Original UI producer unavailable after actual Gesture and Drive')
            need(value['action']=='observe');native.ui.send(value);return native.ui.read()
        if action=='gesture':
            need(value['action']==gesture.ACTION)
            if self.hold_gesture_publication:
                # Actual earlier native OpenXR publication, sampled by the
                # original getter without publishing a new input/frame.
                native.axes.clock=native.clock;native.original_send(value)
            else:native.axes.send(value)
            return native.axes.read()
        if action=='drive':
            need(value['action']==drive.ACTION);native.drive.send(value);return native.drive.read()
        if action=='pending':
            pending_command(value);need(value['operation']=='observe')
            if self.unavailable==action:
                self.unavailable_producer.send(value);return self.unavailable_producer.original()
            self.case.boundary.send(value);return self.case.reader.original()
        if action=='feature':
            need(set(value)=={'schemaVersion','commandId','action'} and type(value['schemaVersion']) is int
                and value['schemaVersion']==1 and ui.nonce(value['commandId']) and value['action']=='feature-native-observe')
            if self.unavailable==action:
                self.unavailable_producer.send(value);return self.unavailable_producer.original()
            self.case.native_producer.send(value);return self.case.native_producer.original()
        if action=='subject':
            subject_command(value)
            if self.unavailable==action:
                self.unavailable_producer.send(value);return self.unavailable_producer.original()
            if self.move_before_subject:
                # Counter-only target physics advancement between two real
                # getter acquisitions; no accepted reply is rewritten and
                # no Actor-side pose producer exists.
                native.sleep(.01)
                native.drive.source['feetPosition'][0]+=1
                native.drive.source['bodyPosition'][0]+=1
            actual=native.drive.source
            self.subject.source.update(subjectVersion=3 if self.subject.source['subjectVersion']==3 else 2,sceneUrl=actual['sceneUrl'],
                absentIds=list(subject_ids(value['runId']).values()),avatarPose=dict(
                    feetPosition=deepcopy(actual['feetPosition']),orientation=deepcopy(actual['orientation']),modelScale=actual['modelScale']))
            self.subject.epoch=native.epoch()
            self.subject.edit=lambda packet:packet.update(processId=int(self.case.editor.binding['processIdentity'].split(':')[0]))
            self.subject.send(value);return self.subject.original()
        need(False)


class IndependentLifecycleSources:
    def __init__(self,config):
        self.config=config;self.rpc=Rpc(config);self.clock=Clock(self.rpc)
        self.binding=deepcopy(context(config['binding']));self.pid=int(self.binding['processIdentity'].split(':')[0])
        self.lock=ScriptSourceLock(Path(config['path'])/'script-sources.lock')
    def close(self):self.rpc.close()
    def guard(self):
        value=self.rpc.call('candidate');need(typed_equal(value['binding'],self.binding) and value['alive'] is True);return True
    def channel(self,name):
        raw=[None]
        def send(value):raw[0]=self.rpc.call(name,value)
        return send,lambda:raw[0]
    def source(self,client):
        options=dict(monotonic=self.clock.now,sleep=self.clock.sleep)
        ui_source=ui.PicoLifecycleSource(*self.channel('ui'),self.clock.epoch,self.guard,self.pid,source_lock=self.lock,**options)
        axes=gesture.PicoLifecycleGesture(*self.channel('gesture'),self.clock.epoch,self.guard,self.pid,source_lock=self.lock,**options)
        avatar=drive.PicoLifecycleDrive(*self.channel('drive'),self.clock.epoch,self.guard,self.pid,source_lock=self.lock,**options)
        pending=NativePendingCommitOwner(*self.channel('pending'),self.clock.epoch,self.guard,self.pid,**options)
        native=NativeFeatureObservation(*self.channel('feature'),self.clock.epoch,self.guard,self.pid,**options)
        subject=NativeGraphicsSubject(*self.channel('subject'),self.clock.epoch,self.guard,self.pid,**options)
        phases=PhaseFixtureReader(client,self.config['run'],'lifecycle-input',epoch_ms=self.clock.epoch,monotonic=self.clock.now)
        return PicoLifecycleActorSource(Path(self.config['path'])/'lifecycle-actor-originals.json',self.config['run'],self.binding,
            ui_source,axes,avatar,pending,native,subject,phases,self.guard,self.lock,self.config['parentHost'],monotonic=self.clock.now)


class CanonicalIndependentLifecycleSources(IndependentLifecycleSources):
    """Actual canonical factory, with its original synthetic APK/OS boundary.

    All six target source bytes still originate in the existing Parent target.
    The child fixture's native transport contributes candidate/OS metadata only;
    no child Qt/pose model supplies Actor facts.
    """
    def __init__(self,config):
        import hashlib,sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_normal_scripts as canonical
        super().__init__(config)
        import tempfile
        from unittest.mock import patch
        temporary=tempfile.TemporaryDirectory
        def retained(*args,**kwargs):
            result=temporary(*args,**kwargs);result._finalizer.detach();result.cleanup=lambda:None
            return result
        self.fixture=canonical.PicoNormalScriptsTests()
        with patch.object(tempfile,'TemporaryDirectory',retained):self.fixture.setUp()
        original=self.fixture.fixture.fixture.fixture.temporary
        original._finalizer.detach();original.cleanup=lambda:None
        self.adapter,self.target=self.fixture.instance,self.fixture.native.target
        # The existing generic fixture's textual synthetic-start is not a
        # native kernel start. Configure this OS model before factory/source
        # acquisition to the original target's already numeric PID:start.
        original_identity=config['binding']['processIdentity']
        self.fixture.native.identity=original_identity
        self.fixture.native.require_process_identity=lambda value:need(type(value) is str and value==original_identity)
        installed=self.adapter._installation(self.target);identity=self.adapter.require_controlled_debug_identity(self.target)
        self.binding=dict(sourceRevision=installed['sourceRevision'],artifactSha256=installed['artifactSha256'],
            processIdentity=identity,sessionId=self.fixture.native.bridge_id,generation=0,
            targetFingerprint=hashlib.sha256((self.target+'\0'+str(self.adapter.pico_configuration)).encode()).hexdigest())
        self.pid=int(identity.split(':')[0])
        self.root=self.adapter._lifecycle_world_store(self.target).path.parent
        self.lock=ScriptSourceLock(self.root/'script-sources.lock')
        self.adapter._scripts=lambda *_args:need(False)
        from adapters.native_feature_observation import FILE as NATIVE_FILE
        from adapters.native_graphics_subject import FILE as SUBJECT_FILE
        from adapters.pending_commit_owner import FILE as PENDING_FILE
        names={'ui':ui.FILE,'gesture':gesture.FILE,'drive':drive.FILE,'pending':PENDING_FILE,'feature':NATIVE_FILE,'subject':SUBJECT_FILE}
        actions={gesture.ACTION:'gesture',drive.ACTION:'drive','feature-pending-commit-owner':'pending',
            'feature-native-observe':'feature','feature-graphics-subject-observe':'subject'}
        replies={}
        def send(request):
            name=actions[request['action']];replies[names[name]]=self.rpc.call(name,request)
        original_native=self.adapter._native_feature_observer
        def native(target):
            need(target==self.target);reader=original_native(target)
            original_guard=reader.guard
            def guard():original_guard();return self.guard()
            reader.guard=guard
            reader.send=send;reader.clock_ms=self.clock.epoch;reader.monotonic=self.clock.now;reader.sleep=self.clock.sleep
            return reader
        self.adapter._native_feature_observer=native
        original_read=self.adapter.adb.read_debug_app_file;original_write=self.adapter.adb.write_debug_app_file
        def read(target,package,path,**kwargs):
            key=path.removeprefix('files/overte-e2e/')
            if key in names.values():
                need(target==self.target and package=='org.overte.pico');return replies.get(key,'')
            return original_read(target,package,path,**kwargs)
        def write(target,package,path,raw):
            if path==ui.COMMAND:
                need(target==self.target and package=='org.overte.pico')
                replies[ui.FILE]=self.rpc.call('ui',json.loads(raw));return None
            return original_write(target,package,path,raw)
        self.adapter.adb.read_debug_app_file=read;self.adapter.adb.write_debug_app_file=write

    def source(self,client):
        phases=PhaseFixtureReader(client,self.config['run'],'lifecycle-input',epoch_ms=self.clock.epoch,monotonic=self.clock.now)
        # Retain the actual inner test failure before the unchanged public
        # binding sanitizer, without bypassing any factory/guard invocation.
        import sys,traceback
        previous=sys.gettrace();recorded=[]
        def trace(frame,event,error):
            if event=='exception' and frame.f_code.co_name=='_lifecycle_actor_source' and not recorded:
                recorded.append(True);traceback.print_exception(*error,file=sys.stderr)
            return trace
        try:
            sys.settrace(trace)
            return self.adapter._lifecycle_actor_source(self.target,self.config['run'],binding=self.binding,
                phases=phases,parent_host=self.config['parentHost'],source_lock=self.lock)
        finally:sys.settrace(previous)

    def close(self):
        try:super().close()
        finally:self.fixture.doCleanups()


WORKER='''import json,sys
from pathlib import Path
sys.path.insert(0,DEVICE_PATH)
from adapters.normal_feature_state import PrivateFeatureState
from adapters.host_process_identity import host_identity
from feature_journeys.witness import Client
from self_tests.pico_lifecycle_actor_fixture import IndependentLifecycleSources,CanonicalIndependentLifecycleSources
config=PrivateFeatureState(Path(sys.argv[2])).read()
client=Client(config['fixture'],config['actorToken'])
transport=(CanonicalIndependentLifecycleSources if config.get('canonicalFactory') else IndependentLifecycleSources)(config);source=None
waiting={'event':'waiting','host':host_identity()}
if config.get('canonicalFactory'):waiting.update(binding=transport.binding,root=str(transport.root))
print(json.dumps(waiting),flush=True)
try:
 for line in sys.stdin:
  command=json.loads(line)
  if command=={'operation':'exit'}:break
  if command not in ({'operation':'sample'},{'operation':'sample-regress-ui'},{'operation':'sample-lost-reply'},{'operation':'sample-replace-root-exit'},{'operation':'sample-late-publication'},{'operation':'sample-foreign-factory-fingerprint'}):raise ValueError('Source-only worker command')
  if command['operation']=='sample-foreign-factory-fingerprint':transport.binding=dict(transport.binding,targetFingerprint='0'*64)
  if source is None:source=transport.source(client)
  if command['operation']=='sample-replace-root-exit':
   from contextlib import contextmanager
   import os,tempfile
   held=source.lock.held;depth=[0];replaced=[False]
   @contextmanager
   def replaced_exit():
    depth[0]+=1
    try:
     with held():yield
    finally:
     depth[0]-=1
    if depth[0]==0 and not replaced[0] and source.disk['records'] and source.disk['pending'] is None:
     replaced[0]=True
     fd,path=tempfile.mkstemp(dir=source.store.path.parent,prefix='owned-actor-exit-')
     with os.fdopen(fd,'wb') as stream:stream.write(source.store.path.read_bytes());stream.flush();os.fsync(stream.fileno())
     os.replace(path,source.store.path)
   source.lock.held=replaced_exit
  if command['operation']=='sample-late-publication':
   write=source.store.write;spent=[False]
   def slow_publication(value,expected):
    result=write(value,expected)
    publication=value['publication']
    if not spent[0] and publication and publication['phase']=='issued' and publication['fixture'] is not None:
     spent[0]=True;transport.rpc.call('publication-host-work',1.4)
    return result
   source.store.write=slow_publication
  if command['operation']=='sample-regress-ui':
   source.readers[0].previous=dict(source.readers[0].previous)
   source.readers[0].previous['sequence']-=1
  value=source.read();source.before_publication(value)
  reply=client.request('/runs/'+config['run']+'/samples',value)
  if command['operation']=='sample-lost-reply':
   from adapters.normal_ui import NativeUIError
   try:source.read()
   except NativeUIError:pass
   else:raise AssertionError('Uncertain publication allowed another source query')
   raise OSError('Original publication reply lost after actual fixture acceptance')
  source.delivered(reply)
  print(json.dumps({'event':'published','sequence':value['actorSequence']}),flush=True)
  if command['operation']=='sample-late-publication':break
finally:transport.close()
'''
