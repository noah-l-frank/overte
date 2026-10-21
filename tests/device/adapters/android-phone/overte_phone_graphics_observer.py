"""Separate role histories of original Graphics frames, effects and process exit.

No ordinary input, fixture activation or primary-observer forwarding is provided.
The complete feature owner must authorize the current phase/process stage while
holding the shared source lock before calling this internal measurement owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import math
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_process_presence import validate as presence_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.restart_inputs import validate_native_restart
from feature_journeys.contract import identifier,result
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection
from feature_journeys.graphics_resources import validate_status
from overte_phone_graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending
from overte_phone_graphics_images import PhoneGraphicsImages
from overte_phone_graphics_effects import original,compare
from overte_phone_graphics_samples import PhoneGraphicsSamples
from overte_phone_graphics_readiness import PhoneGraphicsReadiness
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=1


class PhoneGraphicsObserver:
    def __init__(self,adapter,selector,source,role,lock,artifact_root,image_policy,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,GraphicsFixtureReader) and role in ('primary','actor') and isinstance(lock,PhoneScriptSourceLock)
            and type(image_policy) is dict and image_policy.get('source')=='world-render-target'
            and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role,self.lock=adapter,selector,source,role,lock
        self.run,self.fixture_url=source.run,source.fixture_url
        self.artifact_root,self.image_policy=Path(artifact_root),deepcopy(image_policy)
        self.monotonic,self.sleep=monotonic,sleep
        lock.assert_held();path=adapter.state_path(selector);need(lock.path==path.with_name('phone-script-sources.lock'))
        self.store=PrivateFeatureState(path.with_name('phone-graphics-'+role+'-observer.json'))
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.current_binding=deepcopy(context(binding));self.previous=self.store.read()
        if source.previous is None:source.status()
        self.state=dict(phase='ready',binding=self.current_binding,stage=0,sequence=0,capturedEpochMs=0,
            backend=deepcopy(source.previous),baseline=None,last=None,offFrames=dict(haze=None,mirror=None),effects=[],restart=None,pending=None)
        if self.previous is not None:self.state=self.decode(self.previous)
        PrivateFeatureState(self.artifact_root/'graphics-observer-boundary.json')._parent()
        if self.previous is None:self.save()

    def binding_for(self,state,stage):
        need(integer(stage,0,state['stage']))
        return state['restart']['oldBinding'] if stage==0 and state['stage']==1 else state['binding']

    def frame(self,frame,binding,stage):
        need(type(frame) is dict and frame['image']['stage']==stage)
        raw=PhoneGraphicsImages.archive(self.artifact_root,frame['image'])
        actual=original(self.run,frame,raw,binding,self.role,self.fixture_url,self.image_policy)
        return actual,raw

    def transfer(self,proof):
        exact(proof,{'oldBinding','oldFrame','newBinding','newFrame','exit'})
        old,new=context(proof['oldBinding']),context(proof['newBinding'])
        before,_=self.frame(proof['oldFrame'],old,0);after,_=self.frame(proof['newFrame'],new,1)
        need(all(same(old[key],new[key]) for key in old if key!='processIdentity')
            and old['processIdentity']!=new['processIdentity'])
        left,right=proof['oldFrame']['nativeAfter'],proof['newFrame']['nativeBefore']
        validate_native_restart(dict(pid=left['processId'],instance=left['instance'],lifecycle=left['lifecycle']),
            dict(pid=right['processId'],instance=right['instance'],lifecycle=right['lifecycle']))
        need(right['requestedEpochMs']>=left['capturedEpochMs'] and right['graphics']==left['graphics']
            and proof['newFrame']['capture']['instance']!=proof['oldFrame']['capture']['instance'])
        exit=proof['exit'];packet=proof['newFrame']['nativeAfter']
        request=dict(schemaVersion=1,commandId=exit['commandId'],action='feature-process-presence',queryProcessId=left['processId'])
        presence_packet(exit,request,packet['processId'],exit['capturedEpochMs'])
        need(exit['presence']=='absent' and exit['instance']==packet['instance'] and exit['capturedEpochMs']>=packet['capturedEpochMs'])
        return before,after

    def decode(self,value):
        exact(value,{'graphicsObserverVersion','runId','fixtureUrl','providerInstance','role','artifactRoot','imagePolicy','payload'})
        need(type(value['graphicsObserverVersion']) is int and value['graphicsObserverVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.source.client.url and value['providerInstance']==self.source.instance
            and value['role']==self.role and value['artifactRoot']==str(self.artifact_root) and same(value['imagePolicy'],self.image_policy))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','binding','stage','sequence','capturedEpochMs','backend','baseline','last','offFrames','effects','restart','pending'})
        context(state['binding']);need(state['phase'] in ('ready','reading','retired') and integer(state['stage'],0,1)
            and integer(state['sequence'],0,256) and integer(state['capturedEpochMs']) and type(state['effects']) is list and len(state['effects'])<=64)
        exact(state['offFrames'],{'haze','mirror'})
        provider=state['backend'];validate_status(provider,instance=self.source.instance,run=self.run,url=self.source.client.url,request=provider['requestId'])
        if state['stage']==0:need(state['restart'] is None)
        else:
            need(state['restart'] is not None and same(state['binding'],state['restart']['newBinding']))
            self.transfer(state['restart'])
        baseline=state['baseline']
        if baseline is not None:
            actual,_=self.frame(baseline,self.binding_for(state,0),0)
            need(not actual['state']['dialog'] and actual['resources']==[])
        last=state['last']
        if last is not None:
            exact(last,{'stage','frame'});need(type(last['stage']) is int and last['stage']==state['stage'])
            actual,_=self.frame(last['frame'],state['binding'],state['stage'])
            need(actual['capturedEpochMs']==state['capturedEpochMs'] and baseline is not None and state['sequence']>0)
        else:need(state['sequence']==0 and state['capturedEpochMs']==0 and baseline is None and not state['effects'] and state['restart'] is None)
        for feature,frame in state['offFrames'].items():
            if frame is None:continue
            actual,_=self.frame(frame,state['binding'],state['stage'])
            need(not actual['state'][feature] and not actual['state'][feature+'Pass'])
        for effect in state['effects']:
            exact(effect,{'stage','feature','before','after','observed'})
            need(integer(effect['stage'],0,state['stage']) and effect['feature'] in ('haze','mirror'))
            binding=self.binding_for(state,effect['stage']);before,_raw=self.frame(effect['before'],binding,effect['stage'])
            after,_raw_after=self.frame(effect['after'],binding,effect['stage'])
            observed=compare(self.run,effect['feature'],self.fixture_url,binding,self.role,effect['before'],_raw,effect['after'],_raw_after,
                self.image_policy,lambda:effect['after']['nativeAfter']['capturedEpochMs'],lambda:True)
            need(same(observed,effect['observed']) and not before['state'][effect['feature']] and after['state'][effect['feature']])
        pending=state['pending']
        if state['phase']=='reading':
            exact(pending,{'stage','binding','active'});context(pending['binding']);need(integer(pending['stage'],state['stage'],1))
            active=pending['active'];exact(active,{'ticket','verb','inputs','afterEpochMs','status'});identifier(active['ticket'])
            self.source.active(dict(schemaVersion=1,runId=self.run,area='graphics',ticket=active['ticket'],stimulus=dict(verb=active['verb'],inputs=active['inputs'])))
            need(integer(active['afterEpochMs'],1));validate_status(active['status'],instance=self.source.instance,run=self.run,
                url=self.source.client.url,request=active['status']['requestId'])
            need(active['status']['active'] and active['status']['ticket']==active['ticket'])
            if pending['stage']==state['stage']:need(same(pending['binding'],state['binding']))
            else:need(state['stage']==0 and pending['stage']==1 and baseline is not None)
        else:need(pending is None)
        if state['phase']=='retired':need(last is not None and provider['active'] is False)
        return state

    def save(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=dict(graphicsObserverVersion=VERSION,runId=self.run,fixtureUrl=self.source.client.url,providerInstance=self.source.instance,
            role=self.role,artifactRoot=str(self.artifact_root),imagePolicy=deepcopy(self.image_policy),payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def baseline(self):
        need(self.state['baseline'] is not None)
        actual,_=self.frame(self.state['baseline'],self.binding_for(self.state,0),0)
        return projection('graphics',actual['state'])

    def read(self,after_sequence,stage):
        need(integer(after_sequence,0,self.state['sequence']) and integer(stage,self.state['stage'],1) and self.state['phase']=='ready')
        need(stage==self.state['stage'] and same(self.current_binding,self.state['binding'])
            or stage==1 and self.state['stage']==0 and self.state['baseline'] is not None and not same(self.current_binding,self.state['binding']))
        if stage!=self.state['stage']:
            need(all(same(self.current_binding[key],self.state['binding'][key])
                for key in self.current_binding if key!='processIdentity'))
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();need(self.guard() is not False)
            now=self.monotonic();need(number(now,previous,1e15) and now-started<30);previous=now
        active=self.source.read(self.state['backend']);bound()
        if self.state['baseline'] is None:need(stage==0 and active['verb']=='baseline')
        self.state.update(phase='reading',pending=dict(stage=stage,binding=self.current_binding,active=deepcopy(active)))
        self.save();bound()
        samples=PhoneGraphicsSamples(self.adapter,self.selector,self.source.client,self.run,self.source.instance,self.role,stage,
            self.lock,self.artifact_root,self.image_policy,epoch_ms=self.source.epoch_ms,monotonic=self.monotonic)
        acquisition_epoch=self.source.clock();acquisition_local=self.monotonic();bound()
        try:
            actual=PhoneGraphicsReadiness(samples,monotonic=self.monotonic,sleep=self.sleep).read(active['ticket'],active['afterEpochMs'])
        except Exception:
            if self.role!='actor':raise
            samples.retire_changed_ticket();confirmed=self.source.read(samples.state['cursors']['provider'])
            need(confirmed['ticket']!=active['ticket']);self.state.update(phase='ready',pending=None,backend=confirmed['status'])
            self.save();raise GraphicsPhasePending('Changed Graphics acquisition was retired without publishing old facts') from None
        frame=deepcopy(samples.state['frame']);bound()
        need(frame['ticket']==active['ticket'] and same(samples.state['binding'],self.current_binding))
        if stage!=self.state['stage']:
            proof=dict(oldBinding=deepcopy(self.state['binding']),oldFrame=deepcopy(self.state['last']['frame']),
                newBinding=deepcopy(self.current_binding),newFrame=deepcopy(frame),
                exit=self.adapter._process_presence(self.selector,read_only=True).require_absent(self.state['last']['frame']['nativeAfter']['processId']))
            self.transfer(proof);bound();self.state.update(stage=stage,binding=self.current_binding,restart=proof,offFrames=dict(haze=None,mirror=None))
        if self.state['baseline'] is None:
            need(not actual['state']['dialog'] and actual['resources']==[]);self.state['baseline']=deepcopy(frame)
        effects=[]
        for feature,verb in (('haze','set-haze'),('mirror','set-mirrors')):
            if not actual['state'][feature] and not actual['state'][feature+'Pass']:
                self.state['offFrames'][feature]=deepcopy(frame)
            elif active['verb']==verb and actual['state'][feature]:
                before=self.state['offFrames'][feature];need(before is not None and len(self.state['effects'])+len(effects)<64)
                _old,raw_before=self.frame(before,self.current_binding,stage)
                _current,raw_after=self.frame(frame,self.current_binding,stage)
                observed=compare(self.run,feature,self.fixture_url,self.current_binding,self.role,before,raw_before,frame,raw_after,
                    self.image_policy,self.source.epoch_ms,self.guard,monotonic=self.monotonic)
                effects.append(dict(stage=stage,feature=feature,before=deepcopy(before),after=deepcopy(frame),observed=observed));bound()
        pending_phase=None
        try:confirmed=self.source.read(samples.state['cursors']['provider'])
        except GraphicsPhasePending as error:
            pending_phase=error;confirmed=dict(status=deepcopy(self.source.previous),ticket=None,verb=None,inputs=None)
        bound()
        need(actual['capturedEpochMs']>=self.state['capturedEpochMs'])
        self.state.update(phase='ready',pending=None,sequence=self.state['sequence']+1,capturedEpochMs=actual['capturedEpochMs'],
            backend=deepcopy(confirmed['status']),last=dict(stage=stage,frame=deepcopy(frame)),effects=self.state['effects']+effects)
        self.save();bound()
        if pending_phase is not None:
            need(self.role=='actor');raise pending_phase
        if confirmed['ticket']!=active['ticket']:
            need(self.role=='actor');raise GraphicsPhasePending('Retired Graphics frame retained under its original ticket without publication')
        need(confirmed['verb']==active['verb'] and same(confirmed['inputs'],active['inputs']))
        image=frame['image'];value=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=self.state['sequence'],
            capturedEpochMs=actual['capturedEpochMs'],state=actual['state'],resources=actual['resources'],lifecycle=actual['lifecycle'],
            artifacts=[dict(kind='image',name=image['name'],sequence=self.state['sequence'],capturedEpochMs=frame['capture']['source']['capturedEpochMs'],
                ticket=frame['ticket'],source='world-render-target')])
        result('feature.graphics.observe',value)
        epoch_started=self.monotonic();epoch=self.source.clock();bound();fresh(value['capturedEpochMs'],epoch)
        need(max(epoch-value['capturedEpochMs']+math.ceil((previous-epoch_started)*1000),
            acquisition_epoch-value['capturedEpochMs']+math.ceil((previous-acquisition_local)*1000))<=1500)
        return deepcopy(value)

    def publish(self,after_sequence,stage):
        need(self.role=='actor')
        value=self.read(after_sequence,stage);ticket=self.state['last']['frame']['ticket']
        payload=dict(ticket=ticket,actor='owned-observer',actorSequence=value['sequence'],capturedEpochMs=value['capturedEpochMs'],facts=projection('graphics',value['state']))
        try:self.source.client.request('/runs/'+self.run+'/samples',payload)
        except ValueError:
            if self.source.read(self.state['backend'])['ticket']!=ticket:return None
            raise
        return value['sequence']

    @classmethod
    def archive(cls,value,*,run,fixture_url,provider_instance,role,artifact_root,image_policy):
        """Historical validation with original PNGs, never an adapter or fresh facts."""
        from types import SimpleNamespace
        from feature_journeys.graphics_resources import fixture_url as validate_url
        identifier(run);identifier(provider_instance);validate_url(fixture_url);need(role in ('primary','actor'))
        owner=object.__new__(cls);owner.run=run;owner.fixture_url=fixture_url+'/runs/'+run+'/'
        owner.role,owner.artifact_root,owner.image_policy=role,Path(artifact_root),deepcopy(image_policy)
        owner.source=SimpleNamespace(instance=provider_instance,client=SimpleNamespace(url=fixture_url),active=lambda value:GraphicsFixtureReader.active(owner.source,value))
        owner.source.run=run;owner.source.fixture_url=owner.fixture_url
        return deepcopy(owner.decode(value))
