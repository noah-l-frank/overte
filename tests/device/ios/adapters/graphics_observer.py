"""Independent role Graphics originals, pixel effects and restart provenance.

No ordinary input, fixture activation or primary-result forwarding is provided.
The whole feature owner must admit the phase/stage under the shared source lock.
"""
# Decomposition reviewed at frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# Original iOS Vulkan ownership, native/host clocks and numeric PIDs remain distinct.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_process_presence import validate as presence_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.native_vulkan_world_frame import absent
from adapters.restart_inputs import validate_native_restart
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import result,identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending
from ios.adapters.graphics_samples import IOSGraphicsSamples,GraphicsMarkerPending
from ios.adapters.graphics_world_measurements import compose
from ios.adapters.graphics_world_effects import compare,GraphicsWorldEffectPending
from ios.adapters.graphics_current_effects import compare as compare_current
from ios.adapters.graphics_history import restore_native,follow_native
from ios.adapters.graphics_restart_proof import validate as restart_receipt
from ios.adapters.login_source import nonce

VERSION=2
READS=(1,2)
FRAME_VERSION=1


class GraphicsEffectReferencePending(GraphicsPhasePending):
    """A current enabled effect needs an actually acquired recent off reference."""


class IOSGraphicsObserver:
    def __init__(self,adapter,selector,source,role,lock,artifact_root,image_policy,*,
                 monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,GraphicsFixtureReader) and role in ('primary','actor') and isinstance(lock,ScriptSourceLock)
             and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role,self.lock=adapter,selector,source,role,lock
        self.run,self.fixture_url=source.run,source.fixture_url
        self.root,self.policy=Path(artifact_root),deepcopy(image_policy)
        need(self.root.is_absolute() and self.root.is_dir() and self.root.resolve()==self.root
             and type(image_policy) is dict and image_policy.get('source')=='world-render-target')
        self.monotonic,self.sleep=monotonic,sleep;lock.assert_held()
        self.store=PrivateFeatureState(adapter.state_path(selector).with_name('ios-graphics-'+role+'-observer.json'))
        need(lock.path==self.store.path.with_name('script-feature-sources.lock'))
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.current_binding=deepcopy(context(binding))
        if source.previous is None:source.status()
        self.previous=self.store.read()
        self.state=dict(phase='ready',binding=self.current_binding,stage=0,sequence=0,capturedEpochMs=0,
            backend=deepcopy(source.previous),baseline=None,last=None,offFrames=dict(haze=None,mirror=None),effects=[],restart=None,pending=None,retirements=[],currentEffects=[],currentEffectsAfter=0,nativeFloor=None)
        if self.previous is None:self.save()
        else:self.state=self.decode(self.previous)

    def frame_store(self,stage,request):
        nonce(request);need(type(stage) is int and stage in (0,1))
        return PrivateFeatureState(self.root/('graphics-observer-'+self.run+'-'+self.role+'-'+str(stage)+'-'+request[4:]+'.json'))

    def retain_frame(self,samples):
        need(isinstance(samples,IOSGraphicsSamples) and samples.role==self.role and same(samples.binding,self.current_binding))
        row=samples.state['owners'][-1];need(row['phase']=='observed')
        original=samples.sample_store(row).read();need(original is not None and digest(original)==row['sampleSha256'])
        owner=PrivateFeatureState(self.store.path.with_name('graphics-world-frame-'+self.role+'-'+str(samples.stage)+'-'+row['requestId'][4:]+'.json')).read()
        value=dict(iosGraphicsObserverFrameVersion=FRAME_VERSION,runId=self.run,role=self.role,stage=samples.stage,
            requestId=row['requestId'],binding=self.current_binding,providerInstance=self.source.instance,
            fixtureUrl=self.source.client.url,imagePolicy=self.policy,payload=pack([dict(sample=original,owner=owner)]))
        store=self.frame_store(samples.stage,row['requestId']);previous=store.read()
        if previous is None:store.write(value,None)
        else:need(same(previous,value))
        need(same(store.read(),value))
        ref=dict(iosGraphicsObserverFrameRefVersion=FRAME_VERSION,stage=samples.stage,requestId=row['requestId'],sha256=digest(value))
        self.frame(ref,self.current_binding);return ref

    def frame(self,reference,binding):
        """Historical originals only; retained clocks never become fresh here."""
        exact(reference,{'iosGraphicsObserverFrameRefVersion','stage','requestId','sha256'})
        need(type(reference['iosGraphicsObserverFrameRefVersion']) is int and reference['iosGraphicsObserverFrameRefVersion']==FRAME_VERSION)
        stage,request=reference['stage'],nonce(reference['requestId']);store=self.frame_store(stage,request);value=store.read()
        need(value is not None and digest(value)==reference['sha256'])
        exact(value,{'iosGraphicsObserverFrameVersion','runId','role','stage','requestId','binding','providerInstance','fixtureUrl','imagePolicy','payload'})
        need(type(value['iosGraphicsObserverFrameVersion']) is int and value['iosGraphicsObserverFrameVersion']==FRAME_VERSION
             and value['runId']==self.run and value['role']==self.role and type(value['stage']) is int and value['stage']==stage
             and value['requestId']==request and same(context(value['binding']),context(binding))
             and value['providerInstance']==self.source.instance and value['fixtureUrl']==self.source.client.url
             and same(value['imagePolicy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);original=rows[0];exact(original,{'sample','owner'})
        sample=original['sample'];exact(sample,{'iosGraphicsSamplesVersion','binding','runId','role','stage','requestId','ticket','afterEpochMs','payload'})
        need(type(sample['iosGraphicsSamplesVersion']) is int and sample['iosGraphicsSamplesVersion'] in (1,2)
             and same(sample['binding'],binding) and sample['runId']==self.run and sample['role']==self.role
             and type(sample['stage']) is int and sample['stage']==stage and sample['requestId']==request)
        frames=unpack(sample['payload']);need(len(frames)==1);frame=frames[0]
        owner=original['owner'];need(type(owner) is dict and same(owner['frame'],frame['capture'])
             and owner['ticket']==sample['ticket'] and any(same(event['receipt'],frame['retirement']) for event in unpack(owner['transcript'])))
        raw=VulkanWorldFrameOwner.archive_original(owner,self.root,binding,self.run,self.role,stage,request,self.lock)
        actual=compose(self.run,sample['ticket'],self.fixture_url,binding,frame,raw,self.policy,
            provider_instance=self.source.instance,after_epoch=sample['afterEpochMs'])
        return deepcopy(frame),raw,deepcopy(actual),owner['name']

    def binding_for(self,state,stage):
        need(integer(stage,0,state['stage']))
        return state['restart']['oldBinding'] if stage==0 and state['stage']==1 else state['binding']

    def transfer(self,proof):
        exact(proof,{'oldBinding','oldFrame','newBinding','newFrame','exit'})
        old,new=context(proof['oldBinding']),context(proof['newBinding'])
        need(proof['oldFrame']['stage']==0 and proof['newFrame']['stage']==1)
        need(all(same(old[key],new[key]) for key in old if key!='processIdentity') and old['processIdentity']!=new['processIdentity'])
        before,_a,first,_name=self.frame(proof['oldFrame'],old);after,_b,last,_name=self.frame(proof['newFrame'],new)
        left,right=before['nativeAfter'],after['nativeBefore']
        validate_native_restart(dict(pid=left['processId'],instance=left['instance'],lifecycle=left['lifecycle']),
            dict(pid=right['processId'],instance=right['instance'],lifecycle=right['lifecycle']))
        need(right['requestedEpochMs']>=left['capturedEpochMs'] and same(left['graphics'],right['graphics'])
             and before['capture']['instance']!=after['capture']['instance'])
        packet=proof['exit'];query=dict(schemaVersion=1,action='feature-process-presence',commandId=nonce(packet['commandId']),queryProcessId=left['processId'])
        presence_packet(packet,query,right['processId'],packet['capturedEpochMs'])
        need(packet['presence']=='absent' and packet['instance']==right['instance'] and packet['capturedEpochMs']>=after['nativeAfter']['capturedEpochMs'])
        return first,last

    def decode(self,value):
        exact(value,{'iosGraphicsObserverVersion','runId','fixtureUrl','providerInstance','role','artifactRoot','imagePolicy','payload'})
        need(type(value['iosGraphicsObserverVersion']) is int and value['iosGraphicsObserverVersion'] in READS
             and value['runId']==self.run and value['fixtureUrl']==self.source.client.url and value['providerInstance']==self.source.instance
             and value['role']==self.role and value['artifactRoot']==str(self.root) and same(value['imagePolicy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        version=value['iosGraphicsObserverVersion']
        fields={'phase','binding','stage','sequence','capturedEpochMs','backend','baseline','last','offFrames','effects','restart','pending','retirements'}
        exact(state,fields|({'currentEffects','currentEffectsAfter','nativeFloor'} if version>=2 else set()))
        if version==1:state=dict(state,currentEffects=[],currentEffectsAfter=state['sequence'],nativeFloor=None)
        need(type(state['currentEffects']) is list and len(state['currentEffects'])<=1024
             and integer(state['currentEffectsAfter'],0,state['sequence']))
        if state['nativeFloor'] is not None:
            packet=state['nativeFloor']
            from adapters.native_feature_observation import validate as native_packet
            native_packet(packet,nonce(packet['requestId']),int(state['binding']['processIdentity']),packet['capturedEpochMs'])
        context(state['binding']);need(state['phase'] in ('ready','reading','retired') and integer(state['stage'],0,1)
             and integer(state['sequence'],0,512) and number(state['capturedEpochMs'],0,1e15)
             and type(state['effects']) is list and len(state['effects'])<=64)
        exact(state['offFrames'],{'haze','mirror'})
        provider=state['backend'];validate_status(provider,instance=self.source.instance,run=self.run,url=self.source.client.url,request=provider['requestId'])
        if state['stage']==0:need(state['restart'] is None)
        else:need(state['restart'] is not None and same(state['binding'],state['restart']['newBinding']));self.transfer(state['restart'])
        if state['baseline'] is None:need(state['last'] is None and state['sequence']==state['capturedEpochMs']==0
             and not state['effects'] and not state['currentEffects'] and state['restart'] is None
             and (version>=2 or all(v is None for v in state['offFrames'].values())))
        else:
            need(state['baseline']['stage']==0)
            _frame,_raw,baseline,_name=self.frame(state['baseline'],self.binding_for(state,0))
            need(not baseline['state']['dialog'] and not baseline['resources'])
        if state['last'] is not None:
            need(state['last']['stage']==state['stage'])
            _frame,_raw,actual,_name=self.frame(state['last'],state['binding'])
            need(state['baseline'] is not None and state['sequence']>0 and actual['capturedEpochMs']==state['capturedEpochMs'])
        for feature,ref in state['offFrames'].items():
            if ref is None:continue
            need(integer(ref['stage'],0,state['stage']))
            _frame,_raw,actual,_name=self.frame(ref,self.binding_for(state,ref['stage']))
            need(not actual['state'][feature] and not actual['state'][feature+'Pass'])
        for effect in state['effects']:
            exact(effect,{'stage','feature','before','after','observed'});need(integer(effect['stage'],0,state['stage']) and effect['feature'] in ('haze','mirror'))
            need(effect['before']['stage']==effect['after']['stage']==effect['stage'])
            binding=self.binding_for(state,effect['stage']);before,a,_old,_name=self.frame(effect['before'],binding);after,b,_new,_name=self.frame(effect['after'],binding)
            observed=compare(self.run,effect['feature'],self.fixture_url,binding,before,a,after,b,self.policy,self.source.instance,
                lambda:round(after['clockJoin']['hostAfterEpochMs']),lambda:True,monotonic=lambda:0.)
            need(same(observed,effect['observed']))
        for effect in state['currentEffects']:
            exact(effect,{'stage','feature','before','after','receipt','observed'})
            need(integer(effect['stage'],0,state['stage']) and effect['feature'] in ('haze','mirror')
                 and effect['after']['stage']==effect['stage'] and integer(effect['before']['stage'],0,effect['stage']))
            left=self.binding_for(state,effect['before']['stage']);right=self.binding_for(state,effect['after']['stage'])
            before,a,_old,_name=self.frame(effect['before'],left);after,b,_new,_name=self.frame(effect['after'],right)
            measured=compare_current(self.run,effect['feature'],self.fixture_url,left,before,a,right,after,b,self.policy,self.source.instance,
                lambda:round(after['clockJoin']['hostAfterEpochMs']),lambda:True,restart=effect['receipt'],monotonic=lambda:0.)
            need(same(measured,effect['observed']))
        if state['last'] is not None and state['sequence']>state['currentEffectsAfter']:
            actual=self.frame(state['last'],state['binding'])[2]
            for feature in ('haze','mirror'):
                if actual['state'][feature]:
                    need(any(row['feature']==feature and same(row['after'],state['last']) for row in state['currentEffects']))
        if state['phase']=='reading':
            self.validate_pending(state['pending']);pending=state['pending'];need(integer(pending['stage'],state['stage'],1))
            if pending['stage']==state['stage']:need(same(pending['binding'],state['binding']))
            else:need(state['stage']==0 and state['baseline'] is not None)
        else:need(state['pending'] is None)
        need(type(state['retirements']) is list and len(state['retirements'])<=64)
        for ordinal,reference in enumerate(state['retirements'],1):self.retirement(reference,ordinal)
        if state['phase']=='retired':need(state['last'] is not None and provider['active'] is False)
        self.accepted_native(state) # All retained source floors must form one original prefix.
        return state

    def accepted_native(self,state=None):
        """Recover the highest admitted original; legacy archives never reset it."""
        state=self.state if state is None else state
        packets=[]
        if state['nativeFloor'] is not None:packets.append(state['nativeFloor'])
        refs=[state['last']]+list(state['offFrames'].values())
        seen=set()
        for ref in refs:
            if ref is None or ref['stage']!=state['stage'] or ref['requestId'] in seen:continue
            seen.add(ref['requestId']);packets.append(self.frame(ref,state['binding'])[0]['clockJoin']['nativeAfter'])
        for ordinal,reference in enumerate(state['retirements'],1):
            data=self.retirement(reference,ordinal)
            if data['samples'] is not None and same(data['pending']['binding'],state['binding']):
                packet=unpack(data['samples']['payload'])[0]['cursors']['native']
                if packet is not None:packets.append(packet)
        originals={}
        for packet in packets:
            key=packet['sequence']
            if key in originals:need(same(originals[key],packet))
            else:originals[key]=packet
        ordered=[originals[key] for key in sorted(originals)]
        for before,after in zip(ordered,ordered[1:]):follow_native(before,after)
        return deepcopy(ordered[-1]) if ordered else None

    def validate_pending(self,pending):
        exact(pending,{'stage','binding','active'});context(pending['binding']);need(integer(pending['stage'],0,1));active=pending['active']
        exact(active,{'ticket','verb','inputs','afterEpochMs','status'})
        self.source.active(dict(schemaVersion=1,runId=self.run,area='graphics',ticket=active['ticket'],stimulus=dict(verb=active['verb'],inputs=active['inputs'])))
        need(integer(active['afterEpochMs'],1));p=active['status']
        validate_status(p,instance=self.source.instance,run=self.run,url=self.source.client.url,request=p['requestId'])
        need(p['active'] and p['ticket']==active['ticket'])

    def retirement_store(self,ordinal):
        need(integer(ordinal,1,64))
        return PrivateFeatureState(self.root/('graphics-observer-retirement-'+self.run+'-'+self.role+'-'+str(ordinal)+'.json'))

    def retirement(self,reference,ordinal):
        exact(reference,{'iosGraphicsObserverRetirementRefVersion','ordinal','sha256'})
        need(type(reference['iosGraphicsObserverRetirementRefVersion']) is int and reference['iosGraphicsObserverRetirementRefVersion']==1
             and type(reference['ordinal']) is int and reference['ordinal']==ordinal)
        value=self.retirement_store(ordinal).read();need(value is not None and digest(value)==reference['sha256'])
        exact(value,{'iosGraphicsObserverRetirementVersion','runId','role','fixtureUrl','providerInstance','payload'})
        need(type(value['iosGraphicsObserverRetirementVersion']) is int and value['iosGraphicsObserverRetirementVersion']==1
             and value['runId']==self.run and value['role']==self.role and value['fixtureUrl']==self.source.client.url and value['providerInstance']==self.source.instance)
        rows=unpack(value['payload']);need(len(rows)==1);data=rows[0];exact(data,{'pending','phase','samples','proofs'})
        self.validate_pending(data['pending']);current=data['phase'];exact(current,{'ticket','verb','inputs','afterEpochMs','status'})
        self.validate_pending(dict(stage=data['pending']['stage'],binding=data['pending']['binding'],active=current))
        need(current['ticket']!=data['pending']['active']['ticket'] and type(data['proofs']) is list and len(data['proofs'])<=512)
        if data['samples'] is not None:
            scope=object.__new__(IOSGraphicsSamples);scope.binding=context(data['pending']['binding']);scope.pid=int(scope.binding['processIdentity'])
            scope.run,scope.role,scope.stage=self.run,self.role,data['pending']['stage'];scope.instance=self.source.instance;scope.client=self.source.client
            scope.root,scope.policy=self.root,self.policy;sample=scope.decode(data['samples']);need(sample['phase']=='ready')
            seen=set()
            for proof in data['proofs']:
                need(absent(proof) and proof['processId']==scope.pid and proof['requestId'] not in seen
                     and any(row['requestId']==proof['requestId'] for row in sample['owners']));seen.add(proof['requestId'])
        else:need(not data['proofs'])
        return data

    def retire_phase(self):
        """Release an interrupted old phase without publishing or replaying it.

        Original samples/commands/files remain durable. This is neither a
        feature cleanup result nor the final whole-run quiet/metadata retirement.
        """
        self.lock.assert_held();need(self.guard() is not False and self.state['phase']=='reading'
             and len(self.state['retirements'])<64 and same(self.current_binding,self.state['pending']['binding']))
        pending=deepcopy(self.state['pending']);phase=self.source.read(self.state['backend'])
        need(phase['ticket']!=pending['active']['ticket'])
        ordinal=len(self.state['retirements'])+1;store=self.retirement_store(ordinal);existing=store.read()
        if existing is not None:
            reference=dict(iosGraphicsObserverRetirementRefVersion=1,ordinal=ordinal,sha256=digest(existing))
            saved=self.retirement(reference,ordinal);need(same(saved['pending'],pending))
        samples=IOSGraphicsSamples(self.adapter,self.selector,self.source.client,self.run,self.role,pending['stage'],self.lock,self.root,self.policy,
            cleanup_only=True,epoch_ms=self.source.epoch_ms,monotonic=self.monotonic)
        if samples.state['phase']=='reading':samples.retire_crossed_phase()
        proofs=samples.drain();need(samples.state['phase']=='ready')
        confirmed=self.source.read(phase['status']);need(confirmed['ticket']==phase['ticket'])
        data=dict(pending=pending,phase=confirmed,samples=samples.previous,proofs=proofs)
        if existing is not None:
            need(same(saved['samples'],samples.previous))
            self.state.update(phase='ready',pending=None,backend=confirmed['status'],retirements=self.state['retirements']+[reference]);self.save()
            return deepcopy(saved)
        value=dict(iosGraphicsObserverRetirementVersion=1,runId=self.run,role=self.role,fixtureUrl=self.source.client.url,
            providerInstance=self.source.instance,payload=pack([data]))
        previous=store.read()
        if previous is None:store.write(value,None)
        else:need(same(previous,value))
        reference=dict(iosGraphicsObserverRetirementRefVersion=1,ordinal=ordinal,sha256=digest(value));self.retirement(reference,ordinal)
        self.state.update(phase='ready',pending=None,backend=confirmed['status'],retirements=self.state['retirements']+[reference]);self.save()
        return deepcopy(data) # Explicit retirement originals, no feature facts.

    def save(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        value=dict(iosGraphicsObserverVersion=VERSION,runId=self.run,fixtureUrl=self.source.client.url,providerInstance=self.source.instance,
            role=self.role,artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def baseline(self):
        need(self.state['baseline'] is not None)
        return projection('graphics',self.frame(self.state['baseline'],self.binding_for(self.state,0))[2]['state'])

    def effect_restart_receipt(self):
        value=PrivateFeatureState(self.store.path.with_name('ios-graphics-restart.json')).read()
        exact(value,{'iosGraphicsRestartVersion','runId','fixtureUrl','providerInstance','payload'})
        need(type(value['iosGraphicsRestartVersion']) is int and value['iosGraphicsRestartVersion']==1
             and value['runId']==self.run and value['fixtureUrl']==self.source.client.url and value['providerInstance']==self.source.instance)
        rows=unpack(value['payload']);need(len(rows)==1 and rows[0]['phase']=='applied')
        receipt=restart_receipt(rows[0]['receipt'])
        need(receipt['input']['ownerFiles']==[str(self.store.path.with_name(name)) for name in
            ('ios-graphics-scene.json','ios-graphics-primary-0-samples.json','ios-graphics-actor-0-samples.json')])
        return receipt

    def effect_preflight(self,stage):
        # Source inspection only, before reserving a resource-creating capture.
        # Missing references never become a positive native draw-only result.
        if stage==self.state['stage'] and same(self.current_binding,self.state['binding']):
            reader=self.adapter._native_feature_observer(self.selector,read_only=True)
            floor=self.accepted_native();restore_native(reader,floor);packet=reader.read(reader.sequence)
            if floor is not None:follow_native(floor,packet)
            self.state['nativeFloor']=deepcopy(packet);self.save();graphics=packet['graphics']
        else:
            need(self.state['last'] is not None)
            graphics=self.frame(self.state['last'],self.state['binding'])[0]['nativeAfter']['graphics']
        for feature,field in (('haze','hazeSetting'),('mirror','mirrorsSetting')):
            if not graphics[field]:continue
            ref=self.state['offFrames'][feature]
            if ref is None:raise GraphicsEffectReferencePending('Current enabled Graphics effect has no original off reference')
            old=self.frame(ref,self.binding_for(self.state,ref['stage']))[0]
            if self.source.clock()-old['clockJoin']['hostAfterEpochMs']>45000:
                raise GraphicsEffectReferencePending('Current Graphics effect off reference requires a new ordinary-input calibration')

    def seed_off(self,features,stage):
        """Retain this role's own actual off originals; no public sample/input.

        The whole owner must perform any necessary ordinary-input calibration
        first. Unknown captures remain in the existing durable sampler and must
        follow the actual crossed-phase retirement path on run cancellation.
        """
        need(type(features) is list and 1<=len(features)<=2 and len(set(features))==len(features)
             and all(f in ('haze','mirror') for f in features) and type(stage) is int
             and stage==self.state['stage'] and same(self.current_binding,self.state['binding']) and self.state['phase']=='ready')
        self.lock.assert_held();need(self.guard() is not False);started=self.monotonic()
        floor=self.accepted_native()
        active=self.source.read(self.state['backend'])
        self.state.update(phase='reading',pending=dict(stage=stage,binding=self.current_binding,active=deepcopy(active)));self.save()
        samples=self.adapter._graphics_samples(self.selector,self.source.client,self.run,self.role,stage,self.lock,self.root,self.policy)
        samples.read(active['ticket'],active['afterEpochMs']);ref=self.retain_frame(samples)
        frame,_raw,measured,_name=self.frame(ref,self.current_binding)
        if floor is not None:follow_native(floor,frame['clockJoin']['nativeBefore'])
        need(all(not measured['state'][f] and not measured['state'][f+'Pass'] for f in features))
        confirmed=self.source.read(samples.state['cursors']['provider']);need(confirmed['ticket']==active['ticket'])
        clock=frame['clockJoin'];epoch=self.source.clock();now=self.monotonic()
        need(number(now,started,started+20) and self.guard() is not False
             and clock['hostAfterEpochMs']<=epoch and epoch-clock['hostBeforeEpochMs']<1500
             and clock['hostAfterMonotonic']<=now and now-clock['hostBeforeMonotonic']<1.5
             and abs(epoch-clock['hostBeforeEpochMs']-(now-clock['hostBeforeMonotonic'])*1000)<=250)
        for f in features:self.state['offFrames'][f]=deepcopy(ref)
        self.state.update(phase='ready',pending=None,backend=confirmed['status'],nativeFloor=deepcopy(frame['clockJoin']['nativeAfter']));self.save()
        return {f:deepcopy(ref) for f in features}

    def read(self,after_sequence,stage):
        need(integer(after_sequence,0,self.state['sequence']) and integer(stage,self.state['stage'],1) and self.state['phase']=='ready')
        need(stage==self.state['stage'] and same(self.current_binding,self.state['binding']) or
             stage==1 and self.state['stage']==0 and self.state['baseline'] is not None and not same(self.current_binding,self.state['binding']))
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();need(self.guard() is not False)
            now=self.monotonic();need(number(now,previous,1e15) and now-started<20);previous=now
        active=self.source.read(self.state['backend']);bound();self.effect_preflight(stage);bound()
        if self.state['baseline'] is None:need(stage==0 and active['verb']=='baseline')
        self.state.update(phase='reading',pending=dict(stage=stage,binding=self.current_binding,active=deepcopy(active)));self.save()
        samples=self.adapter._graphics_samples(self.selector,self.source.client,self.run,self.role,stage,self.lock,self.root,self.policy)
        for attempt in range(81):
            try:actual=samples.read(active['ticket'],active['afterEpochMs'])
            except GraphicsMarkerPending:
                bound();need(attempt<80)
                current=self.source.read(samples.state['cursors']['provider'])
                if current['ticket']!=active['ticket']:raise GraphicsPhasePending('Original Graphics phase changed during marker readiness')
                self.sleep(.25);bound();continue
            ref=self.retain_frame(samples);frame,raw,measured,name=self.frame(ref,self.current_binding);bound()
            need(same({key:measured[key] for key in ('state','lifecycle','resources','image','frameId')},
                      {key:actual[key] for key in ('state','lifecycle','resources','image','frameId')}))
            candidate=deepcopy(self.state)
            if stage==candidate['stage'] and candidate['nativeFloor'] is not None:
                follow_native(candidate['nativeFloor'],frame['clockJoin']['nativeBefore'])
            if stage!=candidate['stage']:
                old=self.frame(self.state['last'],self.state['binding'])[0]
                transfer=dict(oldBinding=self.state['binding'],oldFrame=self.state['last'],newBinding=self.current_binding,newFrame=ref,
                    exit=self.adapter._process_presence(self.selector,read_only=True).require_absent(old['nativeAfter']['processId']))
                self.transfer(transfer);candidate.update(stage=stage,binding=self.current_binding,restart=transfer)
            effects=[];current_effects=[]
            try:
                for feature,verb in (('haze','set-haze'),('mirror','set-mirrors')):
                    enabled=active['verb']==verb and active['inputs'].get('enabled') is True
                    if not measured['state'][feature] and not measured['state'][feature+'Pass'] and not enabled:candidate['offFrames'][feature]=ref
                    elif enabled and measured['state'][feature] and measured['state'][feature+'Pass']:
                        before=candidate['offFrames'][feature];need(before is not None and len(candidate['effects'])+len(effects)<64)
                        if before['stage']==stage:
                            old,a,_old,_name=self.frame(before,self.current_binding)
                            stats=compare(self.run,feature,self.fixture_url,self.current_binding,old,a,frame,raw,self.policy,self.source.instance,
                                self.source.epoch_ms,self.guard,monotonic=self.monotonic)
                            effects.append(dict(stage=stage,feature=feature,before=before,after=ref,observed=stats));bound()
                    if measured['state'][feature]:
                        reference=candidate['offFrames'][feature];need(reference is not None and len(candidate['currentEffects'])+len(current_effects)<1024)
                        left=self.binding_for(candidate,reference['stage']);old,a,_old,_name=self.frame(reference,left)
                        receipt=self.effect_restart_receipt() if not same(left,self.current_binding) else None
                        stats=compare_current(self.run,feature,self.fixture_url,left,old,a,self.current_binding,frame,raw,self.policy,self.source.instance,
                            self.source.epoch_ms,self.guard,restart=receipt,monotonic=self.monotonic)
                        current_effects.append(dict(stage=stage,feature=feature,before=reference,after=ref,receipt=receipt,observed=stats));bound()

            except GraphicsWorldEffectPending:
                bound();need(attempt<80)
                current=self.source.read(samples.state['cursors']['provider'])
                if current['ticket']!=active['ticket']:raise GraphicsPhasePending('Original Graphics phase changed during effect readiness')
                self.sleep(.25);bound();continue
            candidate['effects']+=effects;candidate['currentEffects']+=current_effects;break
        else:raise NativeUIError('Original Graphics pixels did not reach readiness')
        if candidate['baseline'] is None:
            need(not measured['state']['dialog'] and not measured['resources']);candidate['baseline']=ref
        confirmed=self.source.read(samples.state['cursors']['provider']);bound()
        need(measured['capturedEpochMs']>=self.state['capturedEpochMs'])
        candidate.update(phase='ready',pending=None,sequence=self.state['sequence']+1,capturedEpochMs=measured['capturedEpochMs'],backend=confirmed['status'],last=ref,nativeFloor=deepcopy(frame['clockJoin']['nativeAfter']))
        self.state=candidate
        self.save();bound()
        if confirmed['ticket']!=active['ticket']:raise GraphicsPhasePending('Original Graphics frame retained under its own ticket without publication')
        need(confirmed['verb']==active['verb'] and same(confirmed['inputs'],active['inputs']))
        value=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=self.state['sequence'],
            capturedEpochMs=measured['capturedEpochMs'],state=measured['state'],resources=measured['resources'],lifecycle=measured['lifecycle'],
            artifacts=[dict(kind='image',name=name,sequence=self.state['sequence'],capturedEpochMs=measured['capturedEpochMs'],
                ticket=active['ticket'],source='world-render-target')])
        result('feature.graphics.observe',value);epoch=self.source.clock();fresh(value['capturedEpochMs'],epoch);bound()
        clock=frame['clockJoin']
        need(clock['hostAfterEpochMs']<=epoch and epoch-clock['hostBeforeEpochMs']<1500
             and clock['hostAfterMonotonic']<=previous and previous-clock['hostBeforeMonotonic']<1.5
             and abs(epoch-clock['hostBeforeEpochMs']-(previous-clock['hostBeforeMonotonic'])*1000)<=250)
        return deepcopy(value)

    def publish(self,after_sequence,stage):
        need(self.role=='actor');value=self.read(after_sequence,stage)
        frame=self.frame(self.state['last'],self.state['binding'])[0]
        self.source.client.request('/runs/'+self.run+'/samples',dict(ticket=frame['provider']['ticket'],actor='owned-observer',
            actorSequence=value['sequence'],capturedEpochMs=value['capturedEpochMs'],facts=projection('graphics',value['state'])))
        return value['sequence']
