"""One durable original pre-HUD Vulkan sample between real Web source reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters.world_web_sources import WorldWebSources
from ios.adapters.world_web_image import measure
from ios.adapters.world_web_api_clock import check
from ios.adapters.world_web_sample_clocks import WorldWebSampleClocks
from ios.adapters.emote_native_prefix import follow


class WorldWebSample:
    def __init__(self,store,source,frame_owner,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(source,WorldWebSources) and isinstance(frame_owner,VulkanWorldFrameOwner)
            and same(source.binding,frame_owner.binding) and source.run==frame_owner.run and source.lock is frame_owner.lock and callable(guard))
        self.store,self.source,self.frame_owner,self.guard=store,source,frame_owner,guard
        self.binding,self.run,self.role,self.request,self.lock=source.binding,source.run,frame_owner.role,frame_owner.request_id,source.lock
        self.clocks=WorldWebSampleClocks(PrivateFeatureState(store.path.with_name('ios-world-web-primary-'+self.request[4:]+'-gpu-clocks.json')),
            frame_owner.root,self.binding,self.run,self.request,self.lock,self.guard,native=source.native,monotonic=source.monotonic)
        self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)
    def envelope(self,state):return dict(iosWorldWebSampleVersion=1,binding=self.binding,runId=self.run,role=self.role,requestId=self.request,payload=pack([state]))
    def decode(self,value):
        with self.source.validation_round():return self._decode(value)

    def _decode(self,value):
        exact(value,{'iosWorldWebSampleVersion','binding','runId','role','requestId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','ticket','before','after','frameOwnership','clockOwnership','qualificationInputs','qualification'});identifier(state['ticket'])
        need(state['phase'] in ('reading','captured','qualified','failed'))
        for name in ('before','after'):
            if state[name] is not None:self.source.frame(state[name])
        if state['frameOwnership'] is not None:
            need(state['clockOwnership'] is not None and state['before'] is not None)
            first,last=self.clocks.retained(state['clockOwnership']);need(first is not None and last is not None)
            follow(self.source.frame(state['before'])['clockJoin']['nativeAfter'],first)
            if state['after'] is not None:follow(last,self.source.frame(state['after'])['clockJoin']['nativeBefore'])
        else:need(state['clockOwnership'] is None)
        if state['phase']!='reading':
            need(state['before'] is not None and state['after'] is not None and state['frameOwnership'] is not None)
            VulkanWorldFrameOwner.archive_original(state['frameOwnership'],self.frame_owner.root,self.binding,self.run,self.role,0,self.request,self.lock)
        if state['qualificationInputs'] is not None:
            q=state['qualificationInputs'];exact(q,{'policy','entityId','previous','changed'});need(type(q['changed']) is bool)
        if state['phase']=='qualified':need(state['qualificationInputs'] is not None and same(state['qualification'],self.measure(state)))
        return deepcopy(state)
    def save(self):
        check();self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);check();self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);check()
    def capture(self,ticket):
        need(self.state is None);identifier(ticket);self.state=dict(phase='reading',ticket=ticket,before=None,after=None,frameOwnership=None,clockOwnership=None,qualificationInputs=None,qualification=None);self.save()
        self.state['before']=self.source.capture('before-image');self.save()
        need(self.source.frame(self.state['before'])['ticket']==ticket)
        with self.clocks.owned():
            self.frame_owner.capture(ticket);self.frame_owner.release()
        self.state['frameOwnership']=deepcopy(self.frame_owner.store.read());self.state['clockOwnership']=self.clocks.snapshot();self.save()
        self.state['after']=self.source.capture('after-image');self.state['phase']='captured';self.save()
        return deepcopy(self.state)
    def measure(self,state=None):
        state=self.state if state is None else state;q=state['qualificationInputs'];need(q is not None)
        raw=VulkanWorldFrameOwner.archive_original(state['frameOwnership'],self.frame_owner.root,self.binding,self.run,self.role,0,self.request,self.lock)
        return measure(raw,self.run,state['ticket'],q['policy'],self.source.frame(state['before']),self.source.frame(state['after']),self.frame_owner,
            q['entityId'],ownership=state['frameOwnership'],previous=q['previous'],changed=q['changed'])
    def qualify(self,policy,entity,*,previous=None,changed=False):
        need(self.state is not None and self.state['phase']=='captured' and type(changed) is bool)
        need(previous is None or isinstance(previous,WorldWebSample) and previous.state is not None and previous.state['phase']=='qualified'
            and same(previous.binding,self.binding) and previous.run==self.run and previous.request!=self.request)
        old=None if previous is None else dict(requestId=previous.request,ticket=previous.state['ticket'],frameOwnership=deepcopy(previous.state['frameOwnership']))
        self.state['qualificationInputs']=dict(policy=deepcopy(policy),entityId=entity,previous=old,changed=changed);self.save()
        try:observed=self.measure()
        except BaseException:self.state['phase']='failed';self.save();raise
        self.state.update(phase='qualified',qualification=observed);self.save();return deepcopy(observed)
    def retire_runtime(self):
        self.lock.assert_held()
        if self.frame_owner.store.read() is not None:
            with self.clocks.owned():return self.frame_owner.release()
        need(self.state is not None and self.state['phase']=='reading' and self.state['frameOwnership'] is None);return None
