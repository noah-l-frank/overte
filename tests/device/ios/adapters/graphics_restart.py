"""Normal explicit Graphics restart and recoverable original scene/preference transfer."""
# Decomposition reviewed at frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# iOS restart inputs, source recovery and retained role images are platform-owned.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.restart_inputs import RestartInputs
from feature_journeys.contract import arguments,identifier
from feature_journeys.witness import Client
from ios.adapters.graphics_scene import IOSGraphicsScene,operation,restored
from adapters.native_scene_loads import committed
from adapters.native_scene_loads import continuity as load_continuity
from ios.adapters.graphics_preferences import IOSGraphicsPreferences,advance
from ios.adapters.graphics_restart_proof import validate as restart_proof
from ios.adapters.graphics_history import restore_native
from ios.adapters.graphics_samples import IOSGraphicsSamples
from adapters.native_vulkan_world_frame import absent
from pathlib import Path
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.graphics_source import validate as graphics_packet

VERSION=2
READS=(1,2)
ARCHIVE_VERSION=1
ARCHIVE_FIELDS=('oldScene','oldPreferences','proposedScene','proposedPreferences','retirement')


def original_reference(value,*,root,run,url,instance,key,write=False):
    """Exact immutable originals outside the bounded mutable restart header."""
    from adapters.native_clock_join import digest
    need(key in set(ARCHIVE_FIELDS)|{'oldSamplesPrimary','oldSamplesActor'})
    if write:
        row=dict(iosGraphicsRestartArchiveVersion=ARCHIVE_VERSION,runId=run,fixtureUrl=url,providerInstance=instance,key=key,value=deepcopy(value))
        reference=dict(iosGraphicsRestartArchiveRefVersion=ARCHIVE_VERSION,key=key,sha256=digest(row))
    else:
        reference=value;exact(reference,{'iosGraphicsRestartArchiveRefVersion','key','sha256'})
        need(type(reference['iosGraphicsRestartArchiveRefVersion']) is int and reference['iosGraphicsRestartArchiveRefVersion']==ARCHIVE_VERSION
             and reference['key']==key and type(reference['sha256']) is str and len(reference['sha256'])==64
             and all(c in '0123456789abcdef' for c in reference['sha256']))
    store=PrivateFeatureState(Path(root)/('graphics-restart-original-'+run+'-'+key+'-'+reference['sha256']+'.json'))
    previous=store.read()
    if write:
        if previous is None:store.write(row,None)
        else:need(same(previous,row))
    original=store.read();need(original is not None and digest(original)==reference['sha256'])
    exact(original,{'iosGraphicsRestartArchiveVersion','runId','fixtureUrl','providerInstance','key','value'})
    need(type(original['iosGraphicsRestartArchiveVersion']) is int and original['iosGraphicsRestartArchiveVersion']==ARCHIVE_VERSION
         and original['runId']==run and original['fixtureUrl']==url and original['providerInstance']==instance and original['key']==key)
    return deepcopy(reference if write else original['value'])


def original_state(value,root):
    """Read compatible original state; no SDK, mutation or new observation."""
    version=value['iosGraphicsRestartVersion'];need(type(version) is int and version in READS)
    rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
    if version==1:return state
    need(value['artifactRoot']==str(root));base=dict(root=root,run=value['runId'],url=value['fixtureUrl'],instance=value['providerInstance'])
    for key in ARCHIVE_FIELDS:
        if state[key] is not None:state[key]=original_reference(state[key],key=key,**base)
    need(type(state['oldSamples']) is list and len(state['oldSamples'])==2)
    state['oldSamples']=[original_reference(item,key='oldSamples'+role,**base) for item,role in zip(state['oldSamples'],('Primary','Actor'))]
    return state


class IOSGraphicsRestart:
    def __init__(self,adapter,selector,client,run,lock,artifact_root,image_policy,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(client,Client) and client.run==run and client.area=='graphics'
            and isinstance(lock,ScriptSourceLock) and callable(monotonic) and callable(sleep))
        identifier(run);identifier(client.graphics_instance)
        self.adapter,self.selector,self.client,self.run,self.lock=adapter,selector,client,run,lock
        self.root,self.policy=Path(artifact_root),deepcopy(image_policy)
        need(self.root.is_absolute() and self.root.is_dir() and self.root.resolve()==self.root
             and type(image_policy) is dict and image_policy.get('source')=='world-render-target')
        self.monotonic,self.sleep,self.started,self.last_clock=monotonic,sleep,None,None
        path=adapter.state_path(selector);need(lock.path==path.with_name('script-feature-sources.lock'));lock.assert_held()
        self.store=PrivateFeatureState(path.with_name('ios-graphics-restart.json'))
        self.scene_store=PrivateFeatureState(path.with_name('ios-graphics-scene.json'))
        self.preferences_store=PrivateFeatureState(path.with_name('ios-graphics-preferences.json'))
        self.sample_stores=[adapter.graphics_samples_store(selector,role,0) for role in ('primary','actor')]
        self.inputs=RestartInputs(PrivateFeatureState(path.with_name('ios-graphics-restart-inputs.json')),
            [self.scene_store,*self.sample_stores],monotonic=monotonic)
        self.previous=self.store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def samples(self,binding,values=None,*,drain=False):
        need(values is None or type(values) is list and len(values)==2)
        archives=[];proofs=[]
        for index,role in enumerate(('primary','actor')):
            store=self.sample_stores[index];value=store.read() if values is None else values[index]
            need(value is not None and same(store.read(),value))
            state=IOSGraphicsSamples.archive_index(value,adapter=self.adapter,selector=self.selector,client=self.client,
                run=self.run,role=role,stage=0,lock=self.lock,binding=binding,artifact_root=self.root,image_policy=self.policy)
            need(state['sequence']>=1 and state['cursors']['native'] is not None)
            if drain:
                live=self.adapter._graphics_samples(self.selector,self.client,self.run,role,0,self.lock,self.root,self.policy)
                absent=live.drain();need(len(absent)==len(state['owners']))
                proofs.append(dict(role=role,proofs=absent))
            archives.append(deepcopy(value))
        return archives,proofs

    def validate_drains(self,state,scene,preferences):
        need(type(state['oldDrain']) is list and [row['role'] for row in state['oldDrain']]==['primary','actor'])
        need(type(state['oldSamples']) is list and len(state['oldSamples'])==2)
        for index,row in enumerate(state['oldDrain']):
            exact(row,{'role','proofs'});need(type(row['proofs']) is list and len(row['proofs'])<=512)
            # These are retained source headers and original native absence
            # receipts, never image/effect validation or a live process check.
            # Actual PNG/chunk archives are checked by samples() before stop;
            # finalization can retire old files after their separate quiet proof.
            scope=object.__new__(IOSGraphicsSamples);scope.binding=scene.binding;scope.pid=int(scene.binding['processIdentity'])
            scope.run,scope.role,scope.stage=self.run,row['role'],0
            scope.instance=self.client.graphics_instance;scope.client=self.client;scope.root,scope.policy=self.root,self.policy
            sample=scope.decode(state['oldSamples'][index]);need(sample['phase']=='ready' and sample['sequence']>=1
                and sample['cursors']['native']['instance']==preferences['native']['instance']
                and len(row['proofs'])==len(sample['owners']))
            seen=set()
            for proof in row['proofs']:
                need(absent(proof) and proof['processId']==int(scene.binding['processIdentity'])
                     and proof['capturedEpochMs']<=preferences['native']['capturedEpochMs'] and proof['requestId'] not in seen)
                candidates=[owner for owner in sample['owners'] if owner['requestId']==proof['requestId']];need(len(candidates)==1)
                need(sample['cursors']['capture'] is not None and proof['instance']==sample['cursors']['capture']['instance'])
                seen.add(proof['requestId'])

    def snapshots(self,scene_value,preferences_value):
        scene=IOSGraphicsScene._archive_scope(adapter=self.adapter,selector=self.selector,client=self.client,run=self.run)
        scene.state=scene.decode(scene_value);scene.binding=scene.state['binding']
        preferences=IOSGraphicsPreferences.archive(preferences_value,scene=scene)
        need(scene.state['phase']=='active' and scene.state['handoff'] is None and not any(scene.state['leases'].values())
            and preferences['phase'] in ('ready','acknowledged') and preferences['handoff'] is None and not preferences['restoration'])
        return scene,preferences

    def decode(self,value):
        exact(value,{'iosGraphicsRestartVersion','runId','fixtureUrl','providerInstance','payload'}|({'artifactRoot'} if value.get('iosGraphicsRestartVersion')==2 else set()))
        need(type(value['iosGraphicsRestartVersion']) is int and value['iosGraphicsRestartVersion'] in READS and value['runId']==self.run
            and value['fixtureUrl']==self.client.url and value['providerInstance']==self.client.graphics_instance)
        state=original_state(value,self.root)
        exact(state,{'arguments','phase','oldScene','oldPreferences','oldSamples','oldDrain','receipt','native','subject','loads','proposedScene','proposedPreferences','retirement'})
        call=arguments('feature.graphics.act',state['arguments'])
        need(call['verb']=='restart-app' and call['runId']==self.run and call['fixtureUrl']==self.client.url+'/runs/'+self.run+'/'
            and state['phase'] in ('prepared','observed','proposed','applied','retiring'))
        scene,preferences=self.snapshots(state['oldScene'],state['oldPreferences'])
        self.validate_drains(state,scene,preferences)
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
            expected_scene=IOSGraphicsScene.restart_record(state['oldScene'],state['receipt'],state['subject'],state['loads'])
            expected_preferences=IOSGraphicsPreferences.restart_record(state['oldPreferences'],state['receipt'])
            for actual,expected in ((state['proposedScene'],expected_scene),(state['proposedPreferences'],expected_preferences)):
                need(same({key:item for key,item in actual.items() if key!='payload'},
                          {key:item for key,item in expected.items() if key!='payload'})
                     and same(unpack(actual['payload']),unpack(expected['payload'])))
            proposed=scene.decode(state['proposedScene'])
            need(same(proposed['handoff']['previous'],state['oldScene']) and same(proposed['handoff']['receipt'],state['receipt'])
                and same(proposed['handoff']['subject'],state['subject']) and same(proposed['handoff']['loads'],state['loads'])
                and proposed['phase']=='preparing' and not proposed['actions'] and not any(proposed['leases'].values()))
            future=IOSGraphicsPreferences.archive(state['proposedPreferences'],scene=scene,
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
        self.bound();wire=deepcopy(self.state)
        scope=dict(root=self.root,run=self.run,url=self.client.url,instance=self.client.graphics_instance,write=True)
        for key in ARCHIVE_FIELDS:
            if wire[key] is not None:wire[key]=original_reference(wire[key],key=key,**scope)
        wire['oldSamples']=[original_reference(item,key='oldSamples'+role,**scope) for item,role in zip(wire['oldSamples'],('Primary','Actor'))]
        value=dict(iosGraphicsRestartVersion=VERSION,runId=self.run,fixtureUrl=self.client.url,
            providerInstance=self.client.graphics_instance,artifactRoot=str(self.root),payload=pack([wire]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def old_owners(self):
        need(self.scene_store.read() is not None and self.preferences_store.read() is not None)
        self.snapshots(self.scene_store.read(),self.preferences_store.read())
        scene=IOSGraphicsScene(self.adapter,self.selector,self.client,self.run,self.lock,monotonic=self.monotonic,sleep=self.sleep)
        scene.prepare();preferences=IOSGraphicsPreferences(scene,monotonic=self.monotonic,sleep=self.sleep);preferences.prepare()
        need(scene.state['handoff'] is None and preferences.state['handoff'] is None
            and preferences.state['phase'] in ('ready','acknowledged') and not preferences.state['restoration']
            and not any(scene.state['leases'].values())
            and PrivateFeatureState(self.store.path.with_name('ios-graphics-background.json')).read() is None)
        samples,drains=self.samples(scene.binding,drain=True)
        return scene,preferences,samples,drains

    def prepare(self,call):
        need(self.state is None);scene,preferences,samples,drains=self.old_owners();self.bound()
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
            oldSamples=samples,oldDrain=drains,receipt=None,native=None,subject=None,loads=None,proposedScene=None,proposedPreferences=None,retirement=None);self.save()

    def deliver(self,operation):
        self.bound();value=self.adapter._graphics_restart_input(self.selector,operation);self.bound();return value

    def observe_restart(self):
        old_scene,old_preferences=self.snapshots(self.state['oldScene'],self.state['oldPreferences'])
        plan=self.inputs.read();need(same(plan['oldBinding'],old_scene.binding)
            and same(dict(pid=old_preferences['native']['processId'],instance=old_preferences['native']['instance'],
                lifecycle=old_preferences['native']['lifecycle']),plan['oldNative']))
        need(same(self.scene_store.read(),self.state['oldScene']) and same(self.preferences_store.read(),self.state['oldPreferences'])
            and all(same(store.read(),value) for store,value in zip(self.sample_stores,self.state['oldSamples'])))
        self.samples(old_scene.binding,self.state['oldSamples'])
        if plan['phase']=='prepared':self.inputs.stop(lambda:self.deliver('app.stop'));self.bound()
        if self.inputs.read()['phase']=='stop-issued':
            self.inputs.launch(lambda:self.adapter._graphics_restart_stopped(self.selector,old_scene.binding),
                lambda:self.deliver('app.launch'));self.bound()
        self.adapter._graphics_recover_launch(self.selector,self.inputs)
        _ui,_observer,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        reader=self.adapter._native_feature_observer(self.selector,read_only=True);packet=self.inputs.observe(binding,reader)
        exit=self.adapter._process_presence(self.selector,read_only=True).require_absent(old_preferences['native']['processId'])
        need(guard() is not False);self.bound()
        receipt=dict(input=self.inputs.read(),oldNative=old_preferences['native'],native=packet,exit=exit);restart_proof(receipt)
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
        graphics=self.adapter._graphics_ui_source(self.selector,read_only=True).capture()
        graphics_packet(graphics,graphics['commandId'],int(binding['processIdentity']),graphics['capturedEpochMs'])
        need(graphics['capturedEpochMs']>=packet['capturedEpochMs'])
        original=graphics['originalReceipt']['observation']
        need(original['tabletShown'] is False and not any(row['id'].startswith('address.') for row in original['controls']))
        subject=self.adapter._graphics_subject_observer(self.selector,read_only=True);subject.last=deepcopy(self.state['subject'])
        value=subject.read(self.run,require_avatar=True,require_camera=True);need(not value['source']['entities'] and len(value['source']['absentIds'])==7)
        self.state['subject']=deepcopy(value);self.save()
        loads=self.adapter._scene_load_observer(self.selector,read_only=True);loads.last=deepcopy(self.state['loads'])
        self.state['loads']=deepcopy(loads.read(self.run));self.save();need(guard() is not False);self.bound()
        scene_value=IOSGraphicsScene.restart_record(self.state['oldScene'],self.state['receipt'],value,self.state['loads'])
        preferences_value=IOSGraphicsPreferences.restart_record(self.state['oldPreferences'],self.state['receipt'])
        scene,_preferences=self.snapshots(self.state['oldScene'],self.state['oldPreferences']);proposed=scene.decode(scene_value)
        IOSGraphicsPreferences.archive(preferences_value,scene=scene,
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
            scene=IOSGraphicsScene(self.adapter,self.selector,self.client,self.run,self.lock,monotonic=self.monotonic,sleep=self.sleep)
            guard=scene.guard
            def bounded_guard():
                self.bound();result=guard();self.bound();return result
            scene.guard=bounded_guard
            need(same(scene.state['handoff']['previous'],self.state['oldScene'])
                and same(scene.state['handoff']['receipt'],self.state['receipt']))
            scene.prepare();preferences=IOSGraphicsPreferences(scene,monotonic=self.monotonic,sleep=self.sleep);preferences.prepare()
            need(same(preferences.state['handoff']['previous'],self.state['oldPreferences'])
                and same(preferences.state['handoff']['receipt'],self.state['receipt'])
                and preferences.state['native']['graphics']==self.state['receipt']['oldNative']['graphics'])
            self.current_native();self.bound()
        return {'performed':True} # Both roles still need fresh post-restart GPU/images.

    def retirement_archives(self,value,state=None):
        state=self.state if state is None else state;exact(value,{'scene','preferences','subject','loads'})
        decoder=IOSGraphicsScene._archive_scope(adapter=self.adapter,selector=self.selector,client=self.client,run=self.run)
        decoder.state=decoder.decode(value['scene']);decoder.binding=decoder.state['binding']
        preferences=IOSGraphicsPreferences.archive(value['preferences'],scene=decoder)
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
            restored(decoder.state['original']['subject'],after)
        if value['loads'] is not None:
            decoder.validate_loads(value['loads'],state['receipt']['native']['processId'])
            load_continuity(decoder.state['loads'],value['loads'],state['receipt']['native']['processId'])
            need(value['subject'] is not None);committed(value['loads'],value['subject']['source']['sceneUrl'])
        return decoder,preferences

    @operation
    def retire(self,final_scene=None,final_preferences=None):
        self.bound();need(self.state is not None and self.state['phase'] in ('applied','retiring')
            and all(store.read() is None for store in (self.scene_store,self.preferences_store,*self.sample_stores)))
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
            actual=subject.read(self.run,require_avatar=True);restored(decoder.state['original']['subject'],actual)
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
