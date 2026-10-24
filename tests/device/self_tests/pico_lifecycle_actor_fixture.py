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


class LifecycleProducts(ProductSources):
    def __init__(self,case):
        self.case=case;self.native=case.editor.native;self.subject=SubjectBoundary();self.move_before_subject=False;self.fail_ui=False
        self.hold_gesture_publication=False;self.publication_host_work=0.
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
            self.case.boundary.send(value);return self.case.reader.original()
        if action=='feature':
            need(set(value)=={'schemaVersion','commandId','action'} and type(value['schemaVersion']) is int
                and value['schemaVersion']==1 and ui.nonce(value['commandId']) and value['action']=='feature-native-observe')
            self.case.native_producer.send(value);return self.case.native_producer.original()
        if action=='subject':
            subject_command(value)
            if self.move_before_subject:
                # Counter-only target physics advancement between two real
                # getter acquisitions; no accepted reply is rewritten and
                # no Actor-side pose producer exists.
                native.sleep(.01)
                native.drive.source['feetPosition'][0]+=1
                native.drive.source['bodyPosition'][0]+=1
            actual=native.drive.source
            self.subject.source.update(subjectVersion=2,sceneUrl=actual['sceneUrl'],
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


WORKER='''import json,sys
from pathlib import Path
sys.path.insert(0,DEVICE_PATH)
from adapters.normal_feature_state import PrivateFeatureState
from adapters.host_process_identity import host_identity
from feature_journeys.witness import Client
from self_tests.pico_lifecycle_actor_fixture import IndependentLifecycleSources
config=PrivateFeatureState(Path(sys.argv[2])).read()
client=Client(config['fixture'],config['actorToken'])
transport=IndependentLifecycleSources(config);source=None
print(json.dumps({'event':'waiting','host':host_identity()}),flush=True)
try:
 for line in sys.stdin:
  command=json.loads(line)
  if command=={'operation':'exit'}:break
  if command not in ({'operation':'sample'},{'operation':'sample-regress-ui'},{'operation':'sample-lost-reply'},{'operation':'sample-replace-root-exit'},{'operation':'sample-late-publication'}):raise ValueError('Source-only worker command')
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
