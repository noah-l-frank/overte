"""Normal explicit Graphics restart and recoverable original scene/preference transfer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import time

from adapters.native_feature_observation import exact,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.restart_inputs import RestartInputs
from feature_journeys.contract import arguments,identifier
from feature_journeys.witness import Client
from adapters.graphics_journey.scene import GraphicsScene,operation
from adapters.native_scene_loads import committed
from adapters.native_scene_loads import continuity as load_continuity
from adapters.graphics_journey.preferences import GraphicsPreferences,advance
from adapters.graphics_journey.restart_proof import validate as restart_proof,PICO_BINDING_POLICY
from adapters.graphics_journey.source_history import restore_native
from adapters.script_journey.history import pack,unpack,same,canonical
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1


class GraphicsRestart:
    def __init__(self,adapter,selector,client,run,lock,*,artifact_root,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(client,Client) and client.run==run and client.area=='graphics'
            and isinstance(lock,ScriptSourceLock) and callable(monotonic) and callable(sleep))
        identifier(run);identifier(client.graphics_instance)
        self.adapter,self.selector,self.client,self.run,self.lock=adapter,selector,client,run,lock
        self.monotonic,self.sleep,self.started,self.last_clock=monotonic,sleep,None,None
        self.artifact_root=Path(artifact_root)
        PrivateFeatureState(self.artifact_root/'graphics-restart-boundary.json')._parent()
        path=adapter.state_path(selector);need(lock.path==path.with_name('script-sources.lock'));lock.assert_held()
        self.store=PrivateFeatureState(path.with_name('graphics-restart.json'))
        self.scene_store=PrivateFeatureState(path.with_name('graphics-scene.json'))
        self.preferences_store=PrivateFeatureState(path.with_name('graphics-preferences.json'))
        self.world_stores=[adapter.world_render_store(selector,role=role) for role in ('primary','actor')]
        self.inputs=RestartInputs(PrivateFeatureState(path.with_name('graphics-restart-inputs.json')),
            [self.scene_store,*self.world_stores],monotonic=monotonic)
        self.previous=self.store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def archive_record(self,value,kind):
        need(kind in ('scene','preferences') and value['runId']==self.run)
        digest=hashlib.sha256(canonical(value)).hexdigest()
        name='graphics-restart-'+kind+'-'+digest+'.json'
        store=PrivateFeatureState(self.artifact_root/name);old=store.read()
        if old is None:store.write(value,None);old=store.read()
        need(same(old,value))
        return dict(graphicsRestartArchiveVersion=1,kind=kind,name=name,sha256=digest)

    def load_record(self,reference):
        exact(reference,{'graphicsRestartArchiveVersion','kind','name','sha256'})
        need(type(reference['graphicsRestartArchiveVersion']) is int and reference['graphicsRestartArchiveVersion']==1
            and reference['kind'] in ('scene','preferences') and type(reference['sha256']) is str
            and re.fullmatch('[0-9a-f]{64}',reference['sha256']))
        name='graphics-restart-'+reference['kind']+'-'+reference['sha256']+'.json';need(reference['name']==name)
        value=PrivateFeatureState(self.artifact_root/name).read()
        need(type(value) is dict and value.get('runId')==self.run
            and hashlib.sha256(canonical(value)).hexdigest()==reference['sha256'])
        need(('graphicsSceneVersion' in value) if reference['kind']=='scene' else ('graphicsPreferencesVersion' in value))
        return value

    def references(self,value,*,loading):
        if type(value) is dict:
            if 'graphicsRestartArchiveVersion' in value:
                need(loading);return self.load_record(value)
            if 'graphicsSceneVersion' in value or 'graphicsPreferencesVersion' in value:
                need(not loading)
                return self.archive_record(value,'scene' if 'graphicsSceneVersion' in value else 'preferences')
            return {key:self.references(child,loading=loading) for key,child in value.items()}
        if type(value) is list:return [self.references(child,loading=loading) for child in value]
        return value

    def snapshots(self,scene_value,preferences_value):
        scene=GraphicsScene._archive_scope(adapter=self.adapter,selector=self.selector,client=self.client,run=self.run)
        scene.state=scene.decode(scene_value);scene.binding=scene.state['binding']
        preferences=GraphicsPreferences.archive(preferences_value,scene=scene)
        need(scene.state['phase']=='active' and scene.state['handoff'] is None and not any(scene.state['leases'].values())
            and preferences['phase'] in ('ready','acknowledged') and preferences['handoff'] is None and not preferences['restoration'])
        return scene,preferences

    def decode(self,value):
        exact(value,{'graphicsRestartVersion','runId','fixtureUrl','providerInstance','artifactRoot','payload'})
        need(type(value['graphicsRestartVersion']) is int and value['graphicsRestartVersion']==VERSION and value['runId']==self.run
            and value['fixtureUrl']==self.client.url and value['providerInstance']==self.client.graphics_instance
            and value['artifactRoot']==str(self.artifact_root))
        rows=unpack(value['payload']);need(len(rows)==1);state=self.references(rows[0],loading=True)
        exact(state,{'arguments','phase','oldScene','oldPreferences','receipt','native','subject','loads','proposedScene','proposedPreferences','retirement'})
        call=arguments('feature.graphics.act',state['arguments'])
        need(call['verb']=='restart-app' and call['runId']==self.run and call['fixtureUrl']==self.client.url+'/runs/'+self.run+'/'
            and state['phase'] in ('prepared','observed','proposed','applied','retiring'))
        scene,preferences=self.snapshots(state['oldScene'],state['oldPreferences'])
        if state['receipt'] is not None:
            receipt=restart_proof(state['receipt']);need(same(receipt['input']['oldBinding'],scene.binding)
                and same(receipt['oldNative'],preferences['native'])
                and receipt['input']['ownerFiles']==self.inputs.owner_files)
            packet=state['native'];native_packet(packet,packet['requestId'],receipt['native']['processId'],packet['capturedEpochMs'])
            if not same(receipt['native'],packet):advance(receipt['native'],packet)
            if state['subject'] is not None:
                scene.validate_subject(state['subject'],packet['processId'])
                need(state['subject']['instance']==packet['instance'] and not state['subject']['source']['entities']
                    and len(state['subject']['source']['absentIds'])==7)
            if state['loads'] is not None:
                scene.validate_loads(state['loads'],packet['processId'])
                need(state['loads']['instance']!=scene.state['loads']['instance'])
        else:need(state['phase']=='prepared' and all(state[key] is None for key in ('native','subject','loads','proposedScene','proposedPreferences')))
        if state['phase'] in ('proposed','applied','retiring'):
            proposed=scene.decode(state['proposedScene'])
            need(same(proposed['handoff']['previous'],state['oldScene']) and same(proposed['handoff']['receipt'],state['receipt'])
                and same(proposed['handoff']['subject'],state['subject']) and same(proposed['handoff']['loads'],state['loads'])
                and proposed['phase']=='preparing' and not proposed['actions'] and not any(proposed['leases'].values()))
            future=GraphicsPreferences.archive(state['proposedPreferences'],scene=scene,
                expected_binding=state['receipt']['input']['newBinding'],scene_handoff=proposed['handoff'])
            need(same(future['handoff']['previous'],state['oldPreferences']) and future['phase']=='ready' and future['current'] is None)
        else:need(state['proposedScene'] is None and state['proposedPreferences'] is None)
        if state['retirement'] is not None:
            need(state['phase']=='retiring');self.retirement_archives(state['retirement'],state)
        else:need(state['phase']!='retiring')
        return state

    def bound(self):
        # Stop/launch temporarily makes native foreground guards unavailable.
        # Each ordinary input still uses existing SDK/candidate admission and
        # the separate stopped/native/kernel observations below.
        self.lock.assert_held();now=self.monotonic()
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.started is None or 0<=now-self.started<45) and same(self.store.read(),self.previous))
        self.last_clock=now

    def save(self):
        self.bound();value=dict(graphicsRestartVersion=VERSION,runId=self.run,fixtureUrl=self.client.url,
            providerInstance=self.client.graphics_instance,artifactRoot=str(self.artifact_root),
            payload=pack([self.references(self.state,loading=False)]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def old_owners(self):
        need(self.scene_store.read() is not None and self.preferences_store.read() is not None)
        self.snapshots(self.scene_store.read(),self.preferences_store.read())
        scene=GraphicsScene(self.adapter,self.selector,self.client,self.run,self.lock,monotonic=self.monotonic,sleep=self.sleep)
        scene.prepare();preferences=GraphicsPreferences(scene,monotonic=self.monotonic,sleep=self.sleep);preferences.prepare()
        need(scene.state['handoff'] is None and preferences.state['handoff'] is None
            and preferences.state['phase'] in ('ready','acknowledged') and not preferences.state['restoration']
            and not any(scene.state['leases'].values()) and all(store.read() is None for store in self.world_stores)
            and PrivateFeatureState(self.store.path.with_name('graphics-background.json')).read() is None)
        return scene,preferences

    def prepare(self,call):
        need(self.state is None);scene,preferences=self.old_owners();self.bound()
        source=self.adapter._native_feature_observer(self.selector,read_only=True);restore_native(source,preferences.state['native'])
        if self.inputs.store.read() is None:
            packet=self.inputs.capture(scene.binding,source)
        else:
            plan=self.inputs.read();need(plan['phase']=='prepared' and same(plan['oldBinding'],scene.binding))
            packet=source.read(source.sequence)
        advance(preferences.state['native'],packet)
        need(same(dict(pid=packet['processId'],instance=packet['instance'],lifecycle=packet['lifecycle']),self.inputs.read()['oldNative']))
        preferences.state['native']=deepcopy(packet);preferences.save();self.bound()
        self.state=dict(arguments=deepcopy(call),phase='prepared',oldScene=deepcopy(scene.previous),oldPreferences=deepcopy(preferences.previous),
            receipt=None,native=None,subject=None,loads=None,proposedScene=None,proposedPreferences=None,retirement=None);self.save()

    def deliver(self,operation):
        self.bound();value=self.adapter.invoke(self.selector,operation,{});self.bound();return value

    def observe_restart(self):
        old_scene,old_preferences=self.snapshots(self.state['oldScene'],self.state['oldPreferences'])
        plan=self.inputs.read();need(same(plan['oldBinding'],old_scene.binding)
            and same(dict(pid=old_preferences['native']['processId'],instance=old_preferences['native']['instance'],
                lifecycle=old_preferences['native']['lifecycle']),plan['oldNative']))
        need(same(self.scene_store.read(),self.state['oldScene']) and same(self.preferences_store.read(),self.state['oldPreferences'])
            and all(store.read() is None for store in self.world_stores))
        if plan['phase']=='prepared':self.inputs.stop(lambda:self.deliver('app.stop'));self.bound()
        if self.inputs.read()['phase']=='stop-issued':
            self.inputs.launch(lambda:self.adapter._graphics_restart_stopped(self.selector,old_scene.binding),
                lambda:self.deliver('app.launch'));self.bound()
        binding,reader,guard=self.adapter._graphics_restart_source(self.selector,self.inputs,self)
        packet=self.inputs.observe(binding,reader)
        exit=self.adapter._process_presence(self.selector,read_only=True).require_absent(old_preferences['native']['processId'])
        need(guard() is not False);self.bound()
        receipt=dict(graphicsRestartProofVersion=2,bindingPolicy=PICO_BINDING_POLICY,
            input=self.inputs.read(),oldNative=old_preferences['native'],native=packet,exit=exit);restart_proof(receipt)
        self.state.update(phase='observed',receipt=receipt,native=deepcopy(packet));self.save()

    def current_native(self):
        _ui,_observer,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(context(binding),self.state['receipt']['input']['newBinding']))
        source=self.adapter._native_feature_observer(self.selector,read_only=True);restore_native(source,self.state['native'])
        packet=source.read(source.sequence);advance(self.state['native'],packet);need(guard() is not False);self.bound()
        self.state['native']=deepcopy(packet);self.save();return packet

    def propose(self):
        packet=self.current_native();need(packet['graphics']==self.state['receipt']['oldNative']['graphics'])
        ui,_observer,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,self.state['receipt']['input']['newBinding']))
        self.adapter._graphics_restart_quiet_ui(self.selector,self.run)
        subject=self.adapter._graphics_subject_observer(self.selector,read_only=True);subject.last=deepcopy(self.state['subject'])
        value=subject.read(self.run,require_avatar=True);need(not value['source']['entities'] and len(value['source']['absentIds'])==7)
        self.state['subject']=deepcopy(value);self.save()
        loads=self.adapter._scene_load_observer(self.selector,read_only=True);loads.last=deepcopy(self.state['loads'])
        self.state['loads']=deepcopy(loads.read(self.run));self.save();need(guard() is not False);self.bound()
        scene_value=GraphicsScene.restart_record(self.state['oldScene'],self.state['receipt'],value,self.state['loads'])
        preferences_value=GraphicsPreferences.restart_record(self.state['oldPreferences'],self.state['receipt'])
        scene,_preferences=self.snapshots(self.state['oldScene'],self.state['oldPreferences']);proposed=scene.decode(scene_value)
        GraphicsPreferences.archive(preferences_value,scene=scene,
            expected_binding=self.state['receipt']['input']['newBinding'],scene_handoff=proposed['handoff'])
        # Persist the exact complete proposals before either mutable owner file.
        self.state.update(phase='proposed',proposedScene=scene_value,proposedPreferences=preferences_value);self.save()

    def apply(self):
        self.current_native();self.decode(self.previous);self.bound()
        for store,old,new in ((self.scene_store,self.state['oldScene'],self.state['proposedScene']),
                              (self.preferences_store,self.state['oldPreferences'],self.state['proposedPreferences'])):
            actual=store.read();need(same(actual,old) or same(actual,new))
            if same(actual,old):store.write(new,old)
            need(same(store.read(),new));self.bound()
        self.state['phase']='applied';self.save()

    @operation
    def act(self,call):
        call=deepcopy(arguments('feature.graphics.act',call))
        need(call['verb']=='restart-app' and call['runId']==self.run and call['fixtureUrl']==self.client.url+'/runs/'+self.run+'/')
        self.bound()
        with self.adapter.existing_input_session(self.selector):
            if self.state is None:self.prepare(call)
            else:need(same(self.state['arguments'],call))
            if self.state['phase']=='prepared':self.observe_restart()
            if self.state['phase']=='observed':self.propose()
            if self.state['phase']=='proposed':self.apply()
            need(self.state['phase']=='applied')
            scene=GraphicsScene(self.adapter,self.selector,self.client,self.run,self.lock,monotonic=self.monotonic,sleep=self.sleep)
            guard=scene.guard
            def bounded_guard():
                self.bound();result=guard();self.bound();return result
            scene.guard=bounded_guard
            need(same(scene.state['handoff']['previous'],self.state['oldScene'])
                and same(scene.state['handoff']['receipt'],self.state['receipt']))
            scene.prepare();preferences=GraphicsPreferences(scene,monotonic=self.monotonic,sleep=self.sleep);preferences.prepare()
            need(same(preferences.state['handoff']['previous'],self.state['oldPreferences'])
                and same(preferences.state['handoff']['receipt'],self.state['receipt'])
                and preferences.state['native']['graphics']==self.state['receipt']['oldNative']['graphics'])
            self.current_native();self.bound()
        return {'performed':True} # Both roles still need fresh post-restart GPU/images.

    def retirement_archives(self,value,state=None):
        state=self.state if state is None else state;exact(value,{'scene','preferences','subject','loads'})
        decoder=GraphicsScene._archive_scope(adapter=self.adapter,selector=self.selector,client=self.client,run=self.run)
        decoder.state=decoder.decode(value['scene']);decoder.binding=decoder.state['binding']
        preferences=GraphicsPreferences.archive(value['preferences'],scene=decoder)
        need(decoder.state['phase']=='restored' and not any(decoder.state['leases'].values()) and preferences['phase']=='cleaned'
            and same(decoder.state['handoff']['receipt'],state['receipt'])
            and same(preferences['handoff']['receipt'],state['receipt'])
            and same(decoder.state['handoff']['previous'],state['oldScene'])
            and same(preferences['handoff']['previous'],state['oldPreferences']))
        if value['subject'] is not None:
            decoder.validate_subject(value['subject'],state['receipt']['native']['processId'])
            before,after=decoder.state['subject'],value['subject']
            need(after['instance']==before['instance'] and after['sequence']>before['sequence']
                and after['capturedEpochMs']>=before['capturedEpochMs'])
            decoder.restored(decoder.state['original']['subject'],after,decoder.state['handoff'])
        if value['loads'] is not None:
            decoder.validate_loads(value['loads'],state['receipt']['native']['processId'])
            load_continuity(decoder.state['loads'],value['loads'],state['receipt']['native']['processId'])
            need(value['subject'] is not None);committed(value['loads'],value['subject']['source']['sceneUrl'])
        return decoder,preferences

    @operation
    def retire(self,final_scene=None,final_preferences=None):
        self.bound();need(self.state is not None and self.state['phase'] in ('applied','retiring')
            and all(store.read() is None for store in (self.scene_store,self.preferences_store,*self.world_stores)))
        with self.adapter.existing_input_session(self.selector):
            if self.state['retirement'] is None:
                value=dict(scene=deepcopy(final_scene),preferences=deepcopy(final_preferences),subject=None,loads=None);self.retirement_archives(value)
                self.state.update(phase='retiring',retirement=value);self.save()
            else:
                need((final_scene is None and final_preferences is None)
                    or same(self.state['retirement']['scene'],final_scene) and same(self.state['retirement']['preferences'],final_preferences))
            decoder,preferences=self.retirement_archives(self.state['retirement'])
            packet=self.current_native();need(packet['graphics']==preferences['original']['graphics'])
            subject=self.adapter._graphics_subject_observer(self.selector,read_only=True)
            subject.last=deepcopy(self.state['retirement']['subject'] or decoder.state['subject'])
            actual=subject.read(self.run,require_avatar=True,require_framework=decoder.policy.require_framework)
            decoder.restored(decoder.state['original']['subject'],actual,decoder.state['handoff'])
            self.state['retirement']['subject']=deepcopy(actual);self.save()
            loads=self.adapter._scene_load_observer(self.selector,read_only=True)
            loads.last=deepcopy(self.state['retirement']['loads'] or decoder.state['loads'])
            load=loads.read(self.run);committed(load,actual['source']['sceneUrl'])
            self.state['retirement']['loads']=deepcopy(load);self.save()
            final=self.current_native();need(final['graphics']==preferences['original']['graphics'] and final['lifecycle']==packet['lifecycle'])
            if self.inputs.store.read() is not None:
                source=self.adapter._native_feature_observer(self.selector,read_only=True);restore_native(source,final)
                self.inputs.retire(self.state['receipt']['input']['newBinding'],source)
            need(self.inputs.store.read() is None);self.bound();self.store.discard(self.previous)
            need(self.store.read() is None)
