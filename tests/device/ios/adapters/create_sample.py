"""Durable one-attempt Create Vulkan acquisition, never a recipe retry."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation
from ios.adapters import create_state
from ios.adapters.create_world_measurements import originals,compose

VERSION = 1


class CreateSampleOwner:
    def __init__(self,store,lock,binding,run,role,request_id,guard,*,native,source,frame_owner,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard)
             and isinstance(native,NativeFeatureObservation) and native.ios and isinstance(source,create_state.IOSCreateState)
             and isinstance(frame_owner,VulkanWorldFrameOwner) and role in ('primary','actor')
             and request_id.startswith('ios-') and callable(epoch_ms) and callable(monotonic))
        identifier(request_id[4:]);self.store,self.lock,self.binding,self.run,self.role=store,lock,deepcopy(context(binding)),identifier(run),role
        self.request,self.guard,self.native,self.source,self.frame_owner=request_id,guard,native,source,frame_owner
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        need(str(native.pid)==str(source.pid)==binding['processIdentity'] and frame_owner.request_id==request_id
             and same(frame_owner.binding,binding) and frame_owner.lock is lock and frame_owner.run==run and frame_owner.role==role)
        lock.assert_held();self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)

    def envelope(self):
        return dict(iosCreateSampleVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,requestId=self.request,payload=pack([self.state]))
    def decode(self,value):
        exact(value,{'iosCreateSampleVersion','binding','runId','role','requestId','payload'})
        need(type(value['iosCreateSampleVersion']) is int and value['iosCreateSampleVersion']==VERSION
             and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role and value['requestId']==self.request)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','ticket','hostBarrier','start','originals','clockJoin','frameOwnership','qualificationInputs','qualification'})
        identifier(state['ticket']);need(state['phase'] in ('reading','captured','qualified','failed') and type(state['originals']) is dict
            and set(state['originals'])<={'createBefore','capture','retirement','createAfter'})
        if state['phase']!='reading':
            validate_join(state['clockJoin'],state['originals'])
            need(same(state['originals'],originals(dict(state['originals'],clockJoin=state['clockJoin'])))
                 and state['originals']['capture']['requestId']==self.request)
            raw=VulkanWorldFrameOwner.archive_original(state['frameOwnership'],self.frame_owner.root,self.binding,self.run,self.role,0,self.request,self.lock)
            need(same(state['frameOwnership']['frame'],state['originals']['capture']) and same(state['frameOwnership']['absence'],state['originals']['retirement']))
        if state['qualificationInputs'] is not None:
            supplied=state['qualificationInputs'];exact(supplied,{'policy','ownedIds','marker','voxelBaseline','previous','changed'})
            need(type(supplied['changed']) is bool and type(supplied['ownedIds']) is list)
            if supplied['previous'] is not None:
                old=supplied['previous'];exact(old,{'requestId','ticket','frameOwnership'});identifier(old['requestId'][4:]);identifier(old['ticket'])
                need(old['requestId'].startswith('ios-') and old['frameOwnership']['ticket']==old['ticket'])
        if state['phase']=='qualified':
            need(type(state['qualification']) is dict and state['qualificationInputs'] is not None)
            recomposed=self.measure(state,raw);need(same(recomposed,state['qualification']))
        return state
    def save(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=self.envelope();self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def remember(self,name,value):
        need(self.state['phase']=='reading' and name not in self.state['originals'])
        self.state['originals'][name]=deepcopy(value);self.save()
    def capture(self,ticket,host_barrier):
        self.lock.assert_held();need(self.state is None);identifier(ticket)
        self.state=dict(phase='reading',ticket=ticket,hostBarrier=host_barrier,start=None,originals={},clockJoin=None,frameOwnership=None,qualificationInputs=None,qualification=None);self.save()
        clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(host_barrier)
        self.state['start']=deepcopy(clock.started);self.save()
        self.remember('createBefore',self.source.read(self.run))
        capture,_raw=self.frame_owner.capture(ticket);self.remember('capture',capture)
        self.remember('retirement',self.frame_owner.release())
        self.remember('createAfter',self.source.read(self.run))
        fields=[(name,'capturedEpochMs') for name in ('capture','retirement')]
        self.state['clockJoin']=clock.finish(self.state['originals'],fields)
        self.state['frameOwnership']=deepcopy(self.frame_owner.store.read());self.state['phase']='captured';self.save()
        return deepcopy(dict(self.state['originals'],clockJoin=self.state['clockJoin']))
    def qualify(self,policy,owned_ids,marker,*,voxel_baseline=None,previous=None,changed=False):
        need(self.state is not None and self.state['phase']=='captured')
        need(previous is None or isinstance(previous,CreateSampleOwner) and previous.run==self.run and previous.role==self.role
             and same(previous.binding,self.binding) and previous.frame_owner.root==self.frame_owner.root and previous.state is not None
             and previous.state['phase']=='qualified' and previous.request!=self.request)
        prior=None if previous is None else dict(requestId=previous.request,ticket=previous.state['ticket'],frameOwnership=deepcopy(previous.state['frameOwnership']))
        self.state['qualificationInputs']=dict(policy=deepcopy(policy),ownedIds=deepcopy(owned_ids),marker=deepcopy(marker),voxelBaseline=deepcopy(voxel_baseline),previous=prior,changed=changed);self.save()
        raw=self.frame_owner.archive()
        try:
            observed=self.measure(self.state,raw)
        except BaseException:
            self.state['phase']='failed';self.save();raise
        self.state['phase']='qualified';self.state['qualification']=deepcopy(observed);self.save();return observed
    def measure(self,state,raw):
        supplied=state['qualificationInputs'];need(supplied is not None)
        previous=None
        if supplied['previous'] is not None:
            old=supplied['previous'];before=VulkanWorldFrameOwner.archive_original(old['frameOwnership'],self.frame_owner.root,self.binding,self.run,self.role,0,old['requestId'],self.lock)
            first,last=old['frameOwnership']['frame'],state['originals']['capture']
            need(first['instance']==last['instance'] and first['sequence']<last['sequence']
                 and first['requestId']!=last['requestId'] and first['source']['renderTrace']['frameId']!=last['source']['renderTrace']['frameId']
                 and first['capturedEpochMs']<=last['requestedEpochMs'])
            _,previous=image_observation(before,self.run,old['ticket'],supplied['policy'])
        observed,_subject=compose(self.run,state['ticket'],self.binding,dict(state['originals'],clockJoin=state['clockJoin']),raw,supplied['policy'],
            supplied['ownedIds'],supplied['marker'],voxel_baseline=supplied['voxelBaseline'],previous=previous,changed=supplied['changed'],after_epoch=state['hostBarrier'])
        return observed
    def retire_runtime(self):
        """Retire native buffers first, retaining every original host artifact."""
        self.lock.assert_held();need(self.state is not None)
        if self.frame_owner.store.read() is not None:return self.frame_owner.release()
        need(self.state['phase']=='reading' and 'capture' not in self.state['originals']);return None
    def remove_artifact(self):
        """Only after paired whole-run quiet; the enclosing owner keeps archives."""
        self.retire_runtime()
        if self.frame_owner.store.read() is not None:self.frame_owner.remove_image()
