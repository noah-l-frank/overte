"""Paired original-world restoration and one-send final Graphics process stop.

The shared observable cleanup precedes this separate fixture-retired teardown.
Retained native counters remain original pre-exit data. OS death is separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import re
import math
import hashlib
import os
import stat

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters.installed_code import source as process_source
from ios.adapters.graphics_run_retirement import IOSGraphicsRunRetirement,validate as retired_authority
from ios.adapters.graphics_samples import IOSGraphicsSamples
from ios.adapters.graphics_restored_frame import IOSGraphicsRestoredFrame
from ios.adapters.graphics_lifetime import IOSGraphicsLifetime
from ios.adapters.graphics_publisher import IOSGraphicsPublisher
from ios.adapters.graphics_history import follow_native
from ios.adapters.retired_process import absent as process_absent
from adapters.native_vulkan_world_frame import absent as image_absent,storage

VERSION=1
ROLE_VERSION=1
REF_VERSION=1
MANIFEST_VERSION=1
RECEIPT_VERSION=1


class IOSGraphicsFinalization:
    def __init__(self,feature):
        from ios.adapters.graphics_feature import IOSGraphicsFeature
        need(isinstance(feature,IOSGraphicsFeature))
        self.flow=feature;self.lock,self.store,self.root=feature.lock,feature.retirement_store,feature.root
        self.run,self.role=feature.run,feature.role;self.previous=None;self.state=None

    def original(self,key,value=None,reference=None):
        need(type(key) is str and re.fullmatch('[a-z0-9][a-z0-9.-]{0,127}',key))
        if reference is None:
            need(type(value) is dict);reference=dict(iosGraphicsFinalOriginalRefVersion=REF_VERSION,key=key,sha256=digest(value))
        exact(reference,{'iosGraphicsFinalOriginalRefVersion','key','sha256'})
        need(type(reference['iosGraphicsFinalOriginalRefVersion']) is int and reference['iosGraphicsFinalOriginalRefVersion']==REF_VERSION
             and reference['key']==key and type(reference['sha256']) is str and re.fullmatch('[a-f0-9]{64}',reference['sha256']))
        store=PrivateFeatureState(self.root/('graphics-final-original-'+self.run+'-'+key+'-'+reference['sha256']+'.json'))
        previous=store.read()
        if value is not None:
            need(digest(value)==reference['sha256'])
            if previous is None:store.write(value,None)
            else:need(same(previous,value))
        result=store.read();need(result is not None and digest(result)==reference['sha256'])
        return deepcopy(reference),deepcopy(result)

    def retain(self,key,value):return self.original(key,value)[0]
    def load(self,reference):return self.original(reference['key'],reference=reference)[1]

    def envelope(self,state):
        return dict(iosGraphicsFinalizationVersion=VERSION,runId=self.run,fixtureUrl=self.flow.fixture_url,
            providerInstance=self.flow.source.instance,artifactRoot=str(self.root),imagePolicy=self.flow.policy,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosGraphicsFinalizationVersion','runId','fixtureUrl','providerInstance','artifactRoot','imagePolicy','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosGraphicsFinalizationVersion']) is int
            and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','stage','binding','source','control','authority','scene','preferences','roles','stopNative','liveFence','process','items','imageFiles'})
        need(state['phase'] in ('restoring','restored','stop-issued','stopped','retiring') and integer(state['stage'],0,1))
        context(state['binding']);process_source(state['source']);self.load(state['control']);self.load(state['authority'])
        exact(state['roles'],{'primary','actor'});exact(state['process'],{'primary','actor'})
        for item in state['process'].values():
            if item is not None:
                exact(item,{'sha256','complete'});need(type(item['sha256']) is str and re.fullmatch('[a-f0-9]{64}',item['sha256'])
                    and type(item['complete']) is bool)
        for item in state['roles'].values():
            if item is not None:
                exact(item,{'drain','lifetime','frame'})
                for reference in item.values():
                    if reference is not None:self.load(reference)
        if state['phase']!='restoring':need(state['scene'] is not None and state['preferences'] is not None)
        for key in ('scene','preferences','stopNative','liveFence'):
            if state[key] is not None:self.load(state[key])
        if state['phase'] in ('stop-issued','stopped','retiring'):
            need(state['stopNative'] is not None and state['liveFence'] is not None and state['items']
                and all(item is not None and all(item.values()) for item in state['roles'].values()))
        if state['phase']=='retiring':need(all(p is not None and p['complete'] for p in state['process'].values()))
        for key in ('items','imageFiles'):
            need(type(state[key]) is list and len(state[key])<=64);self.manifest(state[key])
        return state

    def manifest(self,pages):
        result={}
        for ordinal,ref in enumerate(pages,1):
            page=self.load(ref);exact(page,{'iosGraphicsFinalManifestVersion','runId','ordinal','entries'})
            need(type(page['iosGraphicsFinalManifestVersion']) is int and page['iosGraphicsFinalManifestVersion']==MANIFEST_VERSION
                 and page['runId']==self.run and type(page['ordinal']) is int and page['ordinal']==ordinal
                 and type(page['entries']) is list and 1<=len(page['entries'])<=64)
            for item in page['entries']:
                exact(item,{'name','original'});name=item['name']
                need(type(name) is str and re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,123}\.json',name) and name not in result
                     and item['original']['key']==name and name!=self.store.path.name)
                result[name]=self.load(item['original'])
        need(len(result)<=4096);return result

    def freeze(self,copies):
        need(type(copies) is dict and 1<=len(copies)<=4096);entries=[];pages=[]
        for name,value in sorted(copies.items()):
            entries.append(dict(name=name,original=self.retain(name,value)))
            if len(entries)==64:
                n=len(pages)+1;pages.append(self.retain('manifest-'+str(n),dict(iosGraphicsFinalManifestVersion=MANIFEST_VERSION,
                    runId=self.run,ordinal=n,entries=entries)));entries=[]
        if entries:
            n=len(pages)+1;pages.append(self.retain('manifest-'+str(n),dict(iosGraphicsFinalManifestVersion=MANIFEST_VERSION,
                runId=self.run,ordinal=n,entries=entries)))
        need(same(self.manifest(pages),copies));return pages

    def collect(self,*,include_process):
        """Enumerate exact owner-declared paths; a glob can only reject extras."""
        copies={};parent=self.store.path.parent
        def take(name,required=False):
            self.flow.clock();value=PrivateFeatureState(parent/name).read()
            need(value is not None or not required)
            if value is not None:copies[name]=value
            return value
        for name in ('ios-graphics-feature.json','ios-graphics-scene.json','ios-graphics-preferences.json'):
            take(name,True)
        for name in ('ios-graphics-calibration.json','ios-graphics-background.json','ios-graphics-restart.json','ios-graphics-restart-inputs.json'):
            take(name)
        for role in ('primary','actor'):
            take('ios-graphics-'+role+'-observer.json')
            if role=='actor':take('ios-graphics-actor-publication.json')
            for stage in range(self.state['stage']+1):
                prefix='ios-graphics-'+role+'-'+str(stage)
                index=take(prefix+'-samples.json',True)
                for row in unpack(index['payload'])[0]['owners']:
                    take(prefix+'-'+row['requestId'][4:]+'-sample.json',True)
                    take('graphics-world-frame-'+role+'-'+str(stage)+'-'+row['requestId'][4:]+'.json',row['phase']!='abandoned')
                life=take(prefix+'-lifetime.json',stage==self.state['stage'])
                if life is not None:
                    for ref in unpack(life['payload'])[0]['records']:take(prefix+'-lifetime-'+str(ref['ordinal'])+'.json',True)
                image=take(prefix+'-restored-frame.json',stage==self.state['stage'])
                if image is not None:
                    request=unpack(image['payload'])[0]['state']['requestId']
                    take('graphics-world-frame-'+role+'-'+str(stage)+'-'+request[4:]+'.json',True)
                if include_process:
                    value=take(prefix+'-process-retirement.json',stage==self.state['stage'])
                    if value is not None:
                        for ref in unpack(value['payload'])[0]['records']:take(prefix+'-process-retirement-'+str(ref['ordinal'])+'.json',True)
        actual=set()
        for pattern in ('ios-graphics-*.json','graphics-world-frame-*.json','graphics-screen-images-*.json','graphics-frame-lease-*.json'):
            actual.update(p.name for p in parent.glob(pattern))
        if not include_process:
            need(not any('-process-retirement' in name for name in actual))
        need(actual==set(copies)|{self.store.path.name});return copies

    def validate_static(self,copies):
        """All retained sources/PNGs; this cannot manufacture a current sample."""
        from ios.adapters.graphics_scene import IOSGraphicsScene
        from ios.adapters.graphics_preferences import IOSGraphicsPreferences
        from ios.adapters.graphics_observer import IOSGraphicsObserver
        from ios.adapters.graphics_calibration import IOSGraphicsCalibration
        from ios.adapters.graphics_lifecycle import IOSGraphicsBackground
        from ios.adapters.graphics_restart import IOSGraphicsRestart
        scene,preferences=self.scene_archive();state=self.state;scopes={}
        need(same(copies['ios-graphics-scene.json'],self.load(state['scene']))
             and same(copies['ios-graphics-preferences.json'],self.load(state['preferences'])))
        for role in ('primary','actor'):
            self.validate_role(role,copies=copies)
            name='ios-graphics-'+role+'-observer.json'
            if name in copies:
                scopes[role]=IOSGraphicsObserver._archive_scope(copies[name],path=self.store.path.with_name(name),run=self.run,
                    fixture_url=self.flow.source.client.url,provider_instance=self.flow.source.instance,role=role,lock=self.lock,
                    artifact_root=self.root,image_policy=self.flow.policy)
            for stage in range(state['stage']+1):
                binding=(scene.state['handoff']['receipt']['input']['oldBinding'] if stage<state['stage'] else state['binding'])
                prefix='ios-graphics-'+role+'-'+str(stage);index=copies[prefix+'-samples.json'];raw=unpack(index['payload'])[0]
                originals={row['requestId']:dict(sample=copies[prefix+'-'+row['requestId'][4:]+'-sample.json'],
                    owner=copies.get('graphics-world-frame-'+role+'-'+str(stage)+'-'+row['requestId'][4:]+'.json')) for row in raw['owners']}
                IOSGraphicsSamples.archive_owned(index,path=self.store.path.with_name(prefix+'-samples.json'),run=self.run,role=role,
                    stage=stage,lock=self.lock,binding=binding,fixture_url=self.flow.source.client.url,provider_instance=self.flow.source.instance,
                    artifact_root=self.root,image_policy=self.flow.policy,originals=originals)
                name=prefix+'-lifetime.json'
                if name in copies:
                    rows=unpack(copies[name]['payload'])[0]['records']
                    IOSGraphicsLifetime.archive(copies[name],path=self.store.path.with_name(name),run=self.run,
                        fixture_url=self.flow.source.client.url,provider_instance=self.flow.source.instance,role=role,stage=stage,binding=binding,
                        records={r['ordinal']:copies[prefix+'-lifetime-'+str(r['ordinal'])+'.json'] for r in rows})
        name='ios-graphics-actor-publication.json'
        if name in copies:
            public=IOSGraphicsPublisher.archive(copies[name],copies['ios-graphics-actor-observer.json'],
                path=self.store.path.with_name('ios-graphics-actor-observer.json'),run=self.run,fixture_url=self.flow.source.client.url,
                provider_instance=self.flow.source.instance,role='actor',lock=self.lock,artifact_root=self.root,image_policy=self.flow.policy)
            need(public['pending'] is None)
        name='ios-graphics-calibration.json'
        if name in copies:
            calibration=IOSGraphicsCalibration.archive(copies[name],scene=scene,source=self.flow.source)
            for row in calibration['rounds']:
                for role,item in row['roles'].items():
                    if item is None:continue
                    scope=IOSGraphicsObserver._archive_scope(item['before'],path=self.store.path.with_name('ios-graphics-'+role+'-observer.json'),
                        run=self.run,fixture_url=self.flow.source.client.url,provider_instance=self.flow.source.instance,role=role,
                        lock=self.lock,artifact_root=self.root,image_policy=self.flow.policy)
                    if item['refs'] is not None:
                        for reference in item['refs'].values():
                            frame,_raw,actual,_name=scope.frame(reference,row['binding'])
                            need(frame['provider']['ticket']==row['active']['ticket'] and not actual['state']['haze'] and not actual['state']['mirror']
                                 and frame['nativeBefore']['requestedEpochMs']>=row['offNative']['capturedEpochMs'])
                            if row['restoredNative'] is not None:need(frame['nativeAfter']['capturedEpochMs']<=row['restoredNative']['requestedEpochMs'])
        name='ios-graphics-restart.json';old_scene=None
        if name in copies:
            restart=IOSGraphicsRestart.archive(copies[name],adapter=self.flow.adapter,selector=self.flow.selector,client=self.flow.source.client,
                run=self.run,lock=self.lock,artifact_root=self.root,image_policy=self.flow.policy)
            need(restart['phase']=='applied' and same(restart['receipt'],scene.state['handoff']['receipt'])
                 and same(restart['receipt']['input'],copies['ios-graphics-restart-inputs.json']))
            old_scene=IOSGraphicsScene._archive_scope(adapter=self.flow.adapter,selector=self.flow.selector,client=self.flow.source.client,run=self.run)
            old_scene.state=old_scene.decode(restart['oldScene']);old_scene.binding=old_scene.state['binding'];old_scene.pid=int(old_scene.binding['processIdentity'])
            for role,index in zip(('primary','actor'),restart['oldSamples']):need(same(index,copies['ios-graphics-'+role+'-0-samples.json']))
        control_value=copies['ios-graphics-feature.json'];control=unpack(control_value['payload'])[0]
        self.flow.validate_control(control);need(same(control_value,self.flow.envelope(control))
            and same(control['binding'],state['binding']) and control['stage']==state['stage'])
        if control['backgroundArchive'] is not None:
            need(old_scene is not None);IOSGraphicsBackground.archive(control['backgroundArchive'],scene=old_scene)
        name='ios-graphics-background.json'
        if name in copies:IOSGraphicsBackground.archive(copies[name],scene=scene)
        if control['restartBarrier'] is not None:self.flow.validate_barrier(control['restartBarrier'])
        for role,ref in control['restartRejoined'].items():
            if ref is not None:need(self.flow.rejoined_record(control,role)[2]==ref)
        if control['phase']=='cleaned':
            scope=scopes['primary'];window=control['cleanupWindow']
            rows=[scope.frame(ref,state['binding'])[0] for ref in control['cleanup'][window['start']:]];need(len(rows)>=3)
            first,last=rows[0]['clockJoin'],rows[-1]['clockJoin']
            elapsed=min(last['hostBeforeEpochMs']-first['hostAfterEpochMs'],last['nativeBefore']['capturedEpochMs']-first['nativeAfter']['capturedEpochMs'],
                (last['hostBeforeMonotonic']-first['hostAfterMonotonic'])*1000)
            need(elapsed>=3000 and window['complete'] and window['elapsedMs']==max(0,math.floor(elapsed)))
        return True

    def read(self):
        self.lock.assert_held();self.previous=self.store.read()
        if self.previous is None:return None
        self.state=self.decode(self.previous);return self.state

    def save(self):
        self.lock.assert_held();self.flow.clock();need(same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def authority(self):
        return IOSGraphicsRunRetirement(self.flow.source,monotonic=self.flow.clock).read()

    def start(self):
        need(self.role=='primary' and self.state is None)
        authority=self.authority();control=self.flow.control();need(control is not None and control['binding'] is not None)
        source=self.flow.adapter._graphics_final_source(self.flow.selector,control['binding'])
        self.state=dict(phase='restoring',stage=control['stage'],binding=deepcopy(control['binding']),source=deepcopy(source),
            control=self.retain('initial-control',self.flow.previous),authority=self.retain('initial-authority',authority),scene=None,preferences=None,
            roles=dict(primary=None,actor=None),stopNative=None,liveFence=None,process=dict(primary=None,actor=None),items=[],imageFiles=[])
        self.save()

    def restore(self):
        need(self.role=='primary' and self.state['phase']=='restoring')
        scene=self.flow.scene();preferences=self.flow.preferences(scene);preferences.cleanup();scene.restore()
        need(scene.state['phase']=='restored' and preferences.state['phase']=='cleaned' and not any(scene.state['leases'].values())
             and same(scene.binding,self.state['binding']))
        self.state.update(scene=self.retain('restored-scene',scene.previous),preferences=self.retain('restored-preferences',preferences.previous),phase='restored')
        self.save()

    def scene_archive(self):
        from ios.adapters.graphics_scene import IOSGraphicsScene
        from ios.adapters.graphics_preferences import IOSGraphicsPreferences
        scene=IOSGraphicsScene._archive_scope(adapter=self.flow.adapter,selector=self.flow.selector,client=self.flow.source.client,run=self.run)
        scene.state=scene.decode(self.load(self.state['scene']));scene.binding=scene.state['binding'];scene.pid=int(scene.binding['processIdentity'])
        preferences=IOSGraphicsPreferences.archive(self.load(self.state['preferences']),scene=scene)
        need(scene.state['phase']=='restored' and preferences['phase']=='cleaned' and same(scene.binding,self.state['binding'])
             and not any(scene.state['leases'].values()))
        return scene,preferences

    def prepare_role(self):
        state=self.state;need(state['phase']=='restored');item=state['roles'][self.role]
        if item is None:
            item=dict(drain=None,lifetime=None,frame=None);state['roles'][self.role]=item;self.save()
        if item['drain'] is None:
            samples=IOSGraphicsSamples(self.flow.adapter,self.flow.selector,self.flow.source.client,self.run,self.role,state['stage'],
                self.lock,self.root,self.flow.policy,cleanup_only=True,epoch_ms=self.flow.source.epoch_ms,monotonic=self.flow.clock)
            if samples.previous is None:samples.save()
            if samples.state['phase']=='reading':samples.retire_inactive_run()
            proofs=samples.drain();need(samples.state['phase']=='ready')
            if self.role=='actor':IOSGraphicsPublisher(self.flow.observer()).retire_run()
            original=dict(iosGraphicsFinalRoleVersion=ROLE_VERSION,runId=self.run,role=self.role,stage=state['stage'],
                binding=state['binding'],sampleIndex=self.retain(self.role+'-released-index',samples.previous),proofs=proofs)
            item['drain']=self.retain(self.role+'-released',original);self.save()
        scene,preferences=self.scene_archive();original=deepcopy(scene.state['original']['subject'])
        restart=None if scene.state['handoff'] is None else deepcopy(scene.state['handoff']['receipt'])
        if item['lifetime'] is None:
            life=self.flow.lifetime(state['stage'])
            if not life.state['activeProofs'] and life.state['abortProof'] is None:life.observe_aborted()
            life.recover()
            restored=[r for r in life.state['records'] if life.load(r)['mode'] in ('held','released')]
            if not restored:life.observe_restored(original,restart=restart)
            else:need(same(life.state['original'],dict(subject=original,restart=restart)))
            item['lifetime']=self.retain(self.role+'-restored-lifetime',life.previous);self.save()
        life_value=self.load(item['lifetime']);life_state=unpack(life_value['payload'])[0]
        need(life_state['original'] is not None and life_state['windows'] and life_state['windows'][-1]['samples'])
        floors={k:deepcopy(life_state['cursors'][k]) for k in ('native','subject','loads')}
        need(same(floors['native']['graphics'],preferences['original']['graphics']))
        frame=IOSGraphicsRestoredFrame(self.flow.adapter,self.flow.selector,self.run,self.role,state['stage'],self.lock,self.root,
            state['binding'],life_state['original'],floors,preferences['original']['graphics'],
            epoch_ms=self.flow.source.epoch_ms,monotonic=self.flow.clock)
        if item['frame'] is None:
            control=unpack(self.load(state['control'])['payload'])[0];need(control['backend']['activations'])
            frame.capture(control['backend']['activations'][-1]['ticket'])
            item['frame']=self.retain(self.role+'-restored-frame',frame.previous);self.save()
        self.validate_role(self.role)

    def validate_role(self,role,*,copies=None):
        state=self.state;item=state['roles'][role];need(item is not None and all(item.values()))
        original=self.load(item['drain']);exact(original,{'iosGraphicsFinalRoleVersion','runId','role','stage','binding','sampleIndex','proofs'})
        need(type(original['iosGraphicsFinalRoleVersion']) is int and original['iosGraphicsFinalRoleVersion']==ROLE_VERSION
            and original['runId']==self.run and original['role']==role and type(original['stage']) is int and original['stage']==state['stage']
            and same(context(original['binding']),state['binding']) and type(original['proofs']) is list)
        index=self.load(original['sampleIndex']);data=unpack(index['payload'])[0]
        need(data['phase']=='ready' and same(data['binding'],state['binding']))
        expected={};parent=self.store.path.parent
        for row in data['owners']:
            name='graphics-world-frame-'+role+'-'+str(state['stage'])+'-'+row['requestId'][4:]+'.json'
            value=PrivateFeatureState(parent/name).read() if copies is None else copies.get(name)
            if value is None:
                name='ios-graphics-'+role+'-'+str(state['stage'])+'-'+row['requestId'][4:]+'-sample.json'
                sample=PrivateFeatureState(parent/name).read() if copies is None else copies[name]
                packet=unpack(sample['payload'])[0]
                need(row['phase']=='abandoned' and digest(sample)==row['sampleSha256'] and packet['capture'] is None and packet['retirement'] is None)
            else:expected[row['requestId']]=value
        need(len(expected)==len(original['proofs']))
        for proof in original['proofs']:
            storage(proof,dict(schemaVersion=1,action='feature-vulkan-world-frame',operation=proof['operation'],
                commandId=proof['commandId'],requestId=proof['requestId']),int(state['binding']['processIdentity']),proof['capturedEpochMs'])
            need(image_absent(proof) and proof['processId']==int(state['binding']['processIdentity']) and proof['requestId'] in expected)
            owner=expected.pop(proof['requestId'])
            need(any(same(event['receipt'],proof) for event in unpack(owner['transcript'])))
            floor=data['cursors']['retirement'];need(floor is not None and proof['instance']==floor['instance'] and proof['sequence']>floor['sequence']
                and proof['requestedEpochMs']>=data['cursors']['native']['capturedEpochMs'])
        need(not expected)
        path=self.store.path.with_name('ios-graphics-'+role+'-'+str(state['stage'])+'-lifetime.json')
        life_value=self.load(item['lifetime']);raw=unpack(life_value['payload'])[0]
        records=None if copies is None else {r['ordinal']:copies[path.stem+'-'+str(r['ordinal'])+'.json'] for r in raw['records']}
        life=IOSGraphicsLifetime.archive(life_value,path=path,run=self.run,fixture_url=self.flow.source.client.url,
            provider_instance=self.flow.source.instance,role=role,stage=state['stage'],binding=state['binding'],records=records)
        need(life['phase']=='releasing' and life['original'] is not None and life['windows'] and life['windows'][-1]['samples'])
        last=life['records'][life['windows'][-1]['samples'][-1]-1]
        record=(PrivateFeatureState(path.with_name(path.stem+'-'+str(last['ordinal'])+'.json')).read() if copies is None else records[last['ordinal']])
        need(unpack(record['payload'])[0]['mode'] in ('held','released'))
        value=self.load(item['frame']);parts=unpack(value['payload'])[0]
        need(same(parts['original'],life['original']) and same(parts['floors'],{k:life['cursors'][k] for k in ('native','subject','loads')}))
        frame_record=PrivateFeatureState(self.root/('graphics-restored-'+self.run+'-'+role+'-'+str(state['stage'])+'.json')).read()
        image_path=self.store.path.with_name('ios-graphics-'+role+'-'+str(state['stage'])+'-restored-frame.json')
        frame,raw=IOSGraphicsRestoredFrame.archive(value,frame_record,path=image_path,lock=self.lock,root=self.root,run=self.run,role=role,
            stage=state['stage'],binding=state['binding'],original=parts['original'],floors=parts['floors'],graphics=parts['graphics'])
        need(raw and frame['clockJoin']['nativeBefore']['capturedEpochMs']>=life['cursors']['native']['capturedEpochMs'])
        return frame

    @classmethod
    def historical(cls,value,path,lock):
        """Pure decoder scope with an explicitly unusable HTTP client."""
        from types import SimpleNamespace
        from ios.adapters.graphics_fixture import GraphicsFixtureReader
        from ios.adapters.graphics_feature import IOSGraphicsFeature
        from feature_journeys.witness import Client
        from feature_journeys.graphics_resources import fixture_url
        exact(value,{'iosGraphicsFinalizationVersion','runId','fixtureUrl','providerInstance','artifactRoot','imagePolicy','payload'})
        run=identifier(value['runId']);instance=identifier(value['providerInstance']);root=Path(value['artifactRoot'])
        suffix='/runs/'+run+'/';need(value['fixtureUrl'].endswith(suffix))
        url=fixture_url(value['fixtureUrl'][:-len(suffix)])
        class Historical(Client):
            def request(self,*_args,**_kwargs):need(False)
        client=Historical(url,'0'*32);client.run,client.area,client.graphics_instance,client.closed=run,'graphics',instance,True
        scope=object.__new__(cls);scope.run,scope.root,scope.store=run,root,PrivateFeatureState(path)
        from adapters.script_feature.lock import ScriptSourceLock
        need(isinstance(lock,ScriptSourceLock) and lock.path==scope.store.path.with_name('script-feature-sources.lock'))
        scope.lock=lock;scope.lock.assert_held()
        need(scope.store.path.name=='ios-graphics-retirement.json' and root.is_absolute() and root.resolve()==root and root.is_dir())
        PrivateFeatureState(root/'graphics-final-root-check')._parent()
        adapter=SimpleNamespace(state_path=lambda _selector:scope.store.path.with_name('session.json'))
        adapter.graphics_restart_owners=lambda _selector:[PrivateFeatureState(lock.path.with_name(name)) for name in
            ('ios-graphics-scene.json','ios-graphics-primary-0-samples.json','ios-graphics-actor-0-samples.json')]
        source=GraphicsFixtureReader(client,run,epoch_ms=lambda:0)
        scope.flow=IOSGraphicsFeature(adapter,'historical',source,root,value['imagePolicy'],monotonic=lambda:0,sleep=lambda *_:need(False))
        scope.flow.lock=lock;scope.state=scope.decode(value);return scope

    @classmethod
    def authorize_stop(cls,value,path,lock):
        """Pure validation at the normal input boundary; no SDK/HTTP factory."""
        scope=cls.historical(value,path,lock);need(scope.state['phase']=='stop-issued')
        scene,preferences=scope.scene_archive();packet=scope.load(scope.state['stopNative'])
        for role in ('primary','actor'):
            frame=scope.validate_role(role);follow_native(frame['clockJoin']['nativeAfter'],packet)
            need(same(frame['clockJoin']['nativeAfter']['lifecycle'],packet['lifecycle'])
                and same(packet['graphics'],preferences['original']['graphics']))
            life=unpack(scope.load(scope.state['roles'][role]['lifetime'])['payload'])[0]
            need(same(life['original']['subject'],scene.state['original']['subject']))
        authority=scope.load(scope.state['authority'])
        retired_authority(authority,run=scope.run,url=scope.flow.source.client.url,instance=scope.flow.source.instance)
        scope.validate_fence()
        return deepcopy(scope.state['binding']),deepcopy(scope.state['source'])

    def fence(self,scene,preferences):
        from adapters.native_clock_join import NativeClockAcquisition
        from adapters.token_graphics_ui import TokenGraphicsUI
        from adapters.script_ui_inventory import validate as inventory
        from adapters.native_scene_loads import committed
        from ios.adapters.graphics_scene import restored
        from ios.adapters.graphics_history import restore_native
        native=self.flow.adapter._native_feature_observer(self.flow.selector,read_only=True);restore_native(native,preferences.state['native'])
        window=NativeClockAcquisition(native,epoch_ms=self.flow.source.clock,monotonic=self.flow.clock);window.begin(self.flow.source.clock())
        subject=self.flow.adapter._graphics_subject_observer(self.flow.selector,read_only=True);subject.last=deepcopy(scene.state['subject'])
        loads=self.flow.adapter._scene_load_observer(self.flow.selector,read_only=True);loads.last=deepcopy(scene.state['loads'])
        packets=dict(subject=subject.read(self.run,require_avatar=True,require_camera=True),loads=loads.read(self.run),
            graphics=self.flow.adapter._graphics_ui_source(self.flow.selector,read_only=True).capture(),
            tablet=self.flow.adapter._script_file_io(self.flow.selector,read_only=True).capture())
        restored(scene.state['original']['subject'],packets['subject']);committed(packets['loads'],packets['subject']['source']['sceneUrl'])
        need(TokenGraphicsUI.row(packets['graphics'],'graphics.page') is None and not inventory(packets['tablet']['scriptInventory'])['tabletShown'])
        clock=window.finish(packets,[(key,'capturedEpochMs') for key in packets])
        value=dict(iosGraphicsFinalFenceVersion=1,runId=self.run,binding=self.state['binding'],payload=pack([dict(packets=packets,clockJoin=clock)]))
        self.state['liveFence']=self.retain('final-live-fence',value);self.state['stopNative']=self.retain('final-live-native',clock['nativeAfter'])
        self.validate_fence();return clock['nativeAfter']

    def validate_fence(self):
        from adapters.native_clock_join import validate_join
        from adapters.native_graphics_subject import validate as subject_packet
        from adapters.native_scene_loads import validate as load_packet,continuity,committed
        from adapters.token_graphics_ui import TokenGraphicsUI
        from adapters.script_feature.ui_source import validate as tablet_packet
        from adapters.script_ui_inventory import validate as inventory
        from ios.adapters.graphics_source import validate as graphics_packet
        from ios.adapters.graphics_scene import restored
        value=self.load(self.state['liveFence']);exact(value,{'iosGraphicsFinalFenceVersion','runId','binding','payload'})
        need(type(value['iosGraphicsFinalFenceVersion']) is int and value['iosGraphicsFinalFenceVersion']==1 and value['runId']==self.run
            and same(value['binding'],self.state['binding']))
        rows=unpack(value['payload']);need(len(rows)==1);exact(rows[0],{'packets','clockJoin'});packets=rows[0]['packets']
        exact(packets,{'subject','loads','graphics','tablet'});clock=validate_join(rows[0]['clockJoin'],packets)
        scene,preferences=self.scene_archive();pid=int(self.state['binding']['processIdentity']);epoch=clock['nativeAfter']['capturedEpochMs']
        subject=packets['subject'];subject_packet(subject,dict(schemaVersion=1,action='feature-graphics-subject-observe',
            commandId=subject['requestId'],runId=self.run),pid,epoch,require_avatar=True,require_camera=True)
        need(subject['instance']==scene.state['subject']['instance']==clock['nativeBefore']['instance']
            and subject['sequence']>scene.state['subject']['sequence']);restored(scene.state['original']['subject'],subject)
        loads=packets['loads'];load_packet(loads,dict(schemaVersion=1,action='feature-scene-load-observe',commandId=loads['commandId'],runId=self.run),pid,epoch)
        continuity(scene.state['loads'],loads,pid);committed(loads,subject['source']['sceneUrl'])
        ui,tablet=packets['graphics'],packets['tablet'];graphics_packet(ui,ui['commandId'],pid,epoch);tablet_packet(tablet,tablet['commandId'],pid,epoch)
        tabs=inventory(tablet['scriptInventory']);need(tabs['complete'] and not tabs['tabletShown'] and TokenGraphicsUI.row(ui,'graphics.page') is None
            and not any(row['rootVisible'] for row in tabs['managers']) and not any(row['visible'] or row['requestId'] for row in tabs['pickers']))
        follow_native(preferences['native'],clock['nativeBefore']);follow_native(clock['nativeBefore'],clock['nativeAfter'])
        need(same(clock['nativeBefore']['graphics'],preferences['original']['graphics'])
            and same(clock['nativeAfter']['graphics'],preferences['original']['graphics'])
            and same(clock['nativeBefore']['lifecycle'],clock['nativeAfter']['lifecycle'])
            and same(self.load(self.state['stopNative']),clock['nativeAfter']))
        return clock

    def stop(self):
        need(self.role=='primary' and self.state['phase']=='restored')
        need(all(item is not None and all(item.values()) for item in self.state['roles'].values()))
        frames=[self.validate_role(role) for role in ('primary','actor')]
        scene=self.flow.scene();scene.restore();preferences=self.flow.preferences(scene);preferences.cleanup()
        self.state.update(scene=self.retain('restored-scene',scene.previous),preferences=self.retain('restored-preferences',preferences.previous))
        copies=self.collect(include_process=False);self.validate_static(copies)
        self.state['items']=self.freeze(copies);self.state['imageFiles']=self.freeze(self.file_originals(copies));self.save()
        packet=self.fence(scene,preferences)
        for frame in frames:
            previous=frame['clockJoin']['nativeAfter'];follow_native(previous,packet);need(same(previous['lifecycle'],packet['lifecycle']))
        need(same(self.flow.adapter._graphics_final_source(self.flow.selector,self.state['binding']),self.state['source']))
        self.authority();self.state['phase']='stop-issued';self.save()
        # Exactly once. Lost delivery/result leaves stop-issued responsibility.
        self.flow.adapter._graphics_final_stop(self.flow.selector,source_lock=self.lock)

    def process(self):
        state=self.state;need(state['phase'] in ('stop-issued','stopped'))
        owner=self.flow.adapter._graphics_process_retirement(self.flow.selector,state['binding'],state['source'],self.run,self.role,state['stage'],self.lock)
        complete=owner.advance();actual=owner.current()
        if self.role=='primary' and process_absent(actual['original']):
            self.flow.adapter._graphics_final_stopped(self.flow.selector,state['binding'],state['source'])
            if state['phase']=='stop-issued':state['phase']='stopped'
        # The parent records exact originals, never requested absence or a new
        # timestamp around a previous completed quiet window.
        state['process'][self.role]=dict(sha256=digest(owner.previous),complete=complete);self.save()
        return complete

    def file_originals(self,copies):
        """Controller file integrity only; partial files never become images."""
        from adapters.native_vulkan_world_frame import PNG_LIMIT
        result={}
        for name,value in copies.items():
            if not name.startswith('graphics-world-frame-'):continue
            need(value['root']==str(self.root) and re.fullmatch(r'vulkan-world-[a-z0-9-]+\.png',value['name']))
            path=self.root/value['name'];identity=value['file'];size=sha=None
            if identity is None:
                try:path.lstat()
                except FileNotFoundError:pass
                else:need(False)
            else:
                descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
                with os.fdopen(descriptor,'rb') as stream:
                    before=os.fstat(stream.fileno());current=path.lstat()
                    need(stat.S_ISREG(before.st_mode) and before.st_nlink==current.st_nlink==1 and before.st_uid==os.geteuid()
                         and stat.S_IMODE(before.st_mode)==0o600 and 0<=before.st_size<=PNG_LIMIT
                         and (before.st_dev,before.st_ino)==(current.st_dev,current.st_ino)==(identity['device'],identity['inode']))
                    checksum=hashlib.sha256();size=0
                    while chunk:=stream.read(65536):checksum.update(chunk);size+=len(chunk);need(size<=PNG_LIMIT)
                    after=os.fstat(stream.fileno());current=path.lstat()
                    need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
                        and (current.st_dev,current.st_ino)==(after.st_dev,after.st_ino) and size==after.st_size)
                    sha=checksum.hexdigest()
            result[name]=dict(iosGraphicsFinalFileVersion=1,runId=self.run,ownerName=name,artifactName=value['name'],
                file=deepcopy(identity),bytes=size,sha256=sha)
        need(result);return result

    def process_archives(self,copies):
        from ios.adapters.process_retirement import IOSProcessRetirement
        states={}
        for role in ('primary','actor'):
            name='ios-graphics-'+role+'-'+str(self.state['stage'])+'-process-retirement.json';value=copies[name]
            raw=unpack(value['payload'])[0]
            state=IOSProcessRetirement.archive(value,path=self.store.path.with_name(name),binding=self.state['binding'],source=self.state['source'],
                bundle=value['bundleId'],run=self.run,role=role,stage=self.state['stage'],
                records={r['ordinal']:copies[name[:-5]+'-'+str(r['ordinal'])+'.json'] for r in raw['records']})
            need(state['pending'] is None and state['windows'] and state['windows'][-1]['complete'])
            need(self.state['process'][role]==dict(sha256=digest(value),complete=True));states[role]=state
        return states

    def fresh_process_pair(self):
        for role in ('primary','actor'):
            owner=self.flow.adapter._graphics_process_retirement(self.flow.selector,self.state['binding'],self.state['source'],
                self.run,role,self.state['stage'],self.lock)
            expected=self.state['process'][role]
            need(expected is not None and expected['complete'] and digest(owner.previous)==expected['sha256']
                and owner.state['windows'][-1]['complete'])
            try:owner.current()
            except Exception:return False
        return True

    def receipt_store(self):return PrivateFeatureState(self.root/('graphics-finalized-'+self.run+'.json'))

    def finish(self):
        need(self.role=='primary' and self.state['phase'] in ('stopped','retiring'))
        # This factory admits only the original retired SDK/candidate scope.
        # It performs no native or new OS acquisition and cannot recreate any
        # already removed process-retirement metadata during CAS recovery.
        self.flow.adapter._retired_process_observer(self.flow.selector,self.state['binding'],self.state['source']).guard()
        if self.state['phase']!='retiring':
            if not all(p is not None and p['complete'] for p in self.state['process'].values()):return False
            static=self.manifest(self.state['items']);copies=self.collect(include_process=True)
            need(all(same(copies.get(name),value) for name,value in static.items()))
            self.process_archives(copies)
            need(same(self.file_originals(copies),self.manifest(self.state['imageFiles'])))
            self.authority() # Original host authority only, never a native query after exit.
            if not self.fresh_process_pair():return False
            self.state.update(phase='retiring',items=self.freeze(copies));self.save()
        copies=self.manifest(self.state['items'])
        # Before any removal, all native/OS originals and file bytes were
        # qualified. Recovery keeps the exact same frozen cutoff and originals;
        # it never retimes them or resends Stop.
        self.process_archives(copies);need(same(self.file_originals(copies),self.manifest(self.state['imageFiles'])))
        names=sorted(copies,key=lambda name:(name=='ios-graphics-feature.json',name))
        all_present=True
        for name in names:
            self.flow.clock();store=PrivateFeatureState(self.store.path.with_name(name));value=store.read()
            need(value is None or same(value,copies[name]));all_present=all_present and value is not None
        if all_present and not self.fresh_process_pair():
            # No removal has started. Serialization/file validation cannot age
            # an old pair into current evidence; ask both roles for new reads.
            static={name:value for name,value in copies.items() if '-process-retirement' not in name}
            self.state.update(phase='stopped',items=self.freeze(static));self.save();return False
        for name in names:
            self.flow.clock();store=PrivateFeatureState(self.store.path.with_name(name));value=store.read()
            if value is not None:need(same(value,copies[name]));store.discard(value)
        need(not any(self.store.path.parent.glob('graphics-world-frame-*.json')))
        need({p.name for p in self.store.path.parent.glob('ios-graphics-*.json')}=={self.store.path.name})
        reference=self.retain('completed-plan',self.previous)
        receipt=dict(iosGraphicsFinalReceiptVersion=RECEIPT_VERSION,runId=self.run,fixtureUrl=self.flow.fixture_url,
            providerInstance=self.flow.source.instance,artifactRoot=str(self.root),imagePolicy=self.flow.policy,plan=reference)
        store=self.receipt_store();old=store.read()
        if old is None:store.write(receipt,None)
        else:need(same(old,receipt))
        self.validate_receipt(store.read(),require_absent=False)
        self.store.discard(self.previous);need(self.store.read() is None);return True

    def validate_receipt(self,value,*,require_absent=True):
        exact(value,{'iosGraphicsFinalReceiptVersion','runId','fixtureUrl','providerInstance','artifactRoot','imagePolicy','plan'})
        need(type(value['iosGraphicsFinalReceiptVersion']) is int and value['iosGraphicsFinalReceiptVersion']==RECEIPT_VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.flow.fixture_url and value['artifactRoot']==str(self.root)
            and same(value['imagePolicy'],self.flow.policy) and self.flow.source.instance in (None,value['providerInstance']))
        original=self.load(value['plan']);scope=self.historical(original,self.store.path,self.lock)
        need(scope.state['phase']=='retiring');copies=scope.manifest(scope.state['items']);scope.validate_static(copies)
        scope.validate_fence();scope.process_archives(copies)
        need(same(scope.file_originals(copies),scope.manifest(scope.state['imageFiles'])))
        if require_absent:
            need(self.store.read() is None and all(PrivateFeatureState(self.store.path.with_name(name)).read() is None for name in copies))
            need(not list(self.store.path.parent.glob('ios-graphics-*.json')) and not list(self.store.path.parent.glob('graphics-world-frame-*.json')))
        return deepcopy(scope.state)

    def step(self):
        """One role-owned teardown step; not a complete feature capability."""
        started=self.flow.clock();outer=self.flow.deadline;self.flow.deadline=started+60 if outer is None else min(outer,started+60)
        try:
            result=self.advance();self.flow.clock();return result
        finally:self.flow.deadline=outer

    def advance(self):
        with self.lock.held():
            receipt=self.receipt_store().read()
            if receipt is not None and self.store.read() is None:self.validate_receipt(receipt);return True
        with self.lock.held(),self.flow.adapter.existing_input_session(self.flow.selector):
            self.flow.source.status();self.read()
            if self.state is None:
                if self.role=='actor':return False
                self.start()
            if self.state['phase']=='restoring':
                if self.role=='actor':return False
                self.restore()
            if self.state['phase']=='restored':
                self.prepare_role()
                if self.role=='primary' and all(i is not None and all(i.values()) for i in self.state['roles'].values()):self.stop()
                else:return False
            if self.state['phase'] in ('stop-issued','stopped'):
                self.process()
                return self.finish() if self.role=='primary' and self.state['phase']!='stop-issued' else False
            need(self.state['phase']=='retiring')
            return self.finish() if self.role=='primary' else False
