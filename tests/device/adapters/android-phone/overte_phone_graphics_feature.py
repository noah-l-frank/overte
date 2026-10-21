"""Phone Graphics run coordination over existing ordinary inputs and originals.

The explicitly enabled feature composes whole-run retirement and registration.
No requested setting or input ACK is returned as measured state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,result
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import projection
from overte_phone_graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending,GraphicsRunRetired
from overte_phone_graphics_scene import PhoneGraphicsScene
from overte_phone_graphics_preferences import PhoneGraphicsPreferences
from overte_phone_graphics_lifecycle import PhoneGraphicsBackground
from overte_phone_graphics_restart import PhoneGraphicsRestart
from overte_phone_graphics_observer import PhoneGraphicsObserver
from overte_phone_graphics_lifetime import PhoneGraphicsLifetime
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=1


class PhoneGraphicsFeature:
    def __init__(self,adapter,selector,source,artifact_root,image_policy,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,GraphicsFixtureReader) and role in ('primary','actor') and type(image_policy) is dict
            and image_policy.get('source')=='world-render-target' and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.artifact_root,self.image_policy=Path(artifact_root),deepcopy(image_policy)
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector);self.store=PrivateFeatureState(path.with_name('phone-graphics-feature.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('phone-graphics-retirement.json'))
        self.role_store=PrivateFeatureState(path.with_name('phone-graphics-'+role+'-observer.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'));self.originals={}

    def read_record(self,store,kind):
        value=store.read();self.originals[store.path]=deepcopy(value)
        if value is None:return None
        exact(value,{'graphicsFeatureVersion','kind','runId','fixtureUrl','artifactRoot','imagePolicy','payload'})
        need(type(value['graphicsFeatureVersion']) is int and value['graphicsFeatureVersion']==VERSION
            and value['kind']==kind and value['runId']==self.run and value['fixtureUrl']==self.fixture_url
            and value['artifactRoot']==str(self.artifact_root) and same(value['imagePolicy'],self.image_policy))
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def write_record(self,store,kind,state):
        self.lock.assert_held();need(store.path in self.originals and same(store.read(),self.originals[store.path]))
        value=dict(graphicsFeatureVersion=VERSION,kind=kind,runId=self.run,fixtureUrl=self.fixture_url,
            artifactRoot=str(self.artifact_root),imagePolicy=deepcopy(self.image_policy),payload=pack([state]))
        store.write(value,self.originals[store.path]);need(same(store.read(),value));self.originals[store.path]=deepcopy(value)

    def control(self):
        state=self.read_record(self.store,'owner')
        if state is None:return None
        return self.validate_control(state)

    def validate_control(self,state):
        exact(state,{'phase','stage','binding','backend','ticket','call','backgroundArchive','cleanup','cleanupWindow','world'})
        need(state['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned','world-restoring','world-restored','retiring')
            and integer(state['stage'],0,1) and type(state['cleanup']) is list and len(state['cleanup'])<=64)
        if state['binding'] is not None:context(state['binding'])
        window=state['cleanupWindow']
        if window is not None:
            exact(window,{'start','elapsedMs','complete'})
            need(integer(window['start'],0,len(state['cleanup'])) and integer(window['elapsedMs'],0,45000) and type(window['complete']) is bool)
        if state['call'] is not None:
            call=arguments('feature.graphics.act',state['call']);need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url and call['ticket']==state['ticket'])
        status=state['backend']
        from feature_journeys.graphics_resources import validate_status
        validate_status(status,instance=status['instance'],run=self.run,url=self.source.client.url,request=status['requestId'])
        if self.source.instance is not None:need(self.source.instance==status['instance'])
        return state

    def save(self,state):self.write_record(self.store,'owner',state)

    def scene(self):return PhoneGraphicsScene(self.adapter,self.selector,self.source.client,self.run,self.lock,monotonic=self.monotonic,sleep=self.sleep)
    def preferences(self,scene):return PhoneGraphicsPreferences(scene,monotonic=self.monotonic,sleep=self.sleep)
    def background(self,preferences):return PhoneGraphicsBackground(preferences,monotonic=self.monotonic,sleep=self.sleep)
    def restart(self):return PhoneGraphicsRestart(self.adapter,self.selector,self.source.client,self.run,self.lock,monotonic=self.monotonic,sleep=self.sleep)
    def observer(self):return PhoneGraphicsObserver(self.adapter,self.selector,self.source,self.role,self.lock,self.artifact_root,self.image_policy,monotonic=self.monotonic,sleep=self.sleep)
    def lifetime(self,stage):return PhoneGraphicsLifetime(self.adapter,self.selector,self.source,self.role,stage,self.lock,monotonic=self.monotonic,sleep=self.sleep)

    def phase(self,state):
        # Acquire this role's own current provider history before comparing a
        # coordinator floor that may have advanced through the other Client.
        self.source.status()
        return self.source.read(state['backend'])

    def prepare(self):
        need(self.role=='primary')
        with self.lock.held():
            state=self.control()
            if state is None:
                need(self.retirement_store.read() is None)
                names=['phone-graphics-scene.json','phone-graphics-preferences.json','phone-graphics-background.json',
                    'phone-graphics-restart.json','phone-graphics-restart-inputs.json']
                names += ['phone-graphics-'+role+'-observer.json' for role in ('primary','actor')]
                names += ['phone-graphics-'+role+'-'+str(stage)+'-'+kind+'.json' for role in ('primary','actor')
                    for stage in (0,1) for kind in ('samples','lifetime')]
                need(all(PrivateFeatureState(self.store.path.with_name(name)).read() is None for name in names)
                    and all(self.adapter.world_render_store(self.selector,role=role).read() is None for role in ('primary','actor')))
                active=self.source.read();need(active['verb']=='baseline')
                state=dict(phase='preparing',stage=0,binding=None,backend=active['status'],ticket=None,call=None,
                    backgroundArchive=None,cleanup=[],cleanupWindow=None,world=None);self.save(state)
            if state['phase']=='preparing':
                if self.source.instance is None:self.source.status()
                self.source.status(state['backend']);scene=self.scene();scene.prepare();preferences=self.preferences(scene);preferences.prepare()
                need(scene.state['phase']=='active' and preferences.state['phase']=='ready')
                state.update(phase='baseline',binding=deepcopy(scene.binding),backend=deepcopy(self.source.client.graphics_previous));self.save(state)
            return deepcopy(state)

    def act(self,call):
        need(self.role=='primary');call=deepcopy(arguments('feature.graphics.act',call))
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url);self.prepare()
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            state=self.control();need(state['phase'] in ('baseline','acting','active'))
            active=self.phase(state);need(active['ticket']==call['ticket']
                and active['verb']==call['verb'] and same(active['inputs'],call['inputs']))
            if state['ticket']==call['ticket']:
                need(same(state['call'],call))
                if state['phase']=='active':return {'performed':True}
            else:
                need(state['phase'] in ('baseline','active'));state.update(phase='acting',ticket=call['ticket'],call=call,backend=active['status']);self.save(state)
            if call['verb']=='restart-app':
                # Background metadata must retire on the old process before
                # Stop. Preserve its exact completed archive before removal.
                background_store=PrivateFeatureState(self.store.path.with_name('phone-graphics-background.json'))
                if background_store.read() is not None:
                    scene=self.scene();preferences=self.preferences(scene);background=self.background(preferences)
                    need(background.state['phase']=='observed')
                    if state['backgroundArchive'] is None:state['backgroundArchive']=deepcopy(background.previous);self.save(state)
                    else:need(same(state['backgroundArchive'],background.previous))
                    background.retire();need(background_store.read() is None)
                self.restart().act(call)
                scene=self.scene();preferences=self.preferences(scene)
                need(scene.state['handoff'] is not None and preferences.state['handoff'] is not None)
                state.update(stage=1,binding=deepcopy(scene.binding))
            else:
                scene=self.scene();preferences=self.preferences(scene);need(same(scene.binding,state['binding']))
                if call['verb']=='background-resume':self.background(preferences).act(call)
                else:preferences.act(call)
            state.update(phase='active',backend=deepcopy(self.source.client.graphics_previous));self.save(state)
            return {'performed':True}

    def admit_observation(self,state,active):
        if state is None or state['phase'] in ('preparing','acting','cleaning','world-restoring','world-restored','retiring'):
            raise GraphicsPhasePending('Ordinary Graphics input or whole-run cleanup is incomplete')
        need(state['binding'] is not None)
        if active['verb']=='baseline':need(state['phase']=='baseline')
        elif active['verb']=='cleanup':
            if state['phase']!='cleaned':raise GraphicsPhasePending('Graphics baseline cleanup is awaiting ordinary input')
            need(active['ticket']==state['ticket'])
        elif state['phase']!='active' or active['ticket']!=state['ticket']:
            raise GraphicsPhasePending('Graphics phase is awaiting its ordinary input')

    def acquire(self,state,after_sequence):
        observer=self.observer();life=self.lifetime(state['stage'])
        if not life.state['activeProofs']:
            # An actual original PNG first establishes the current rendered
            # marker. Lifetime then reads its own native/Java authority, and the
            # returned public observation needs another newly acquired frame.
            observer.read(after_sequence,state['stage']);life.observe_active()
        return observer.read(after_sequence,state['stage'])

    def observe(self,call):
        call=arguments('feature.graphics.observe',call);need(call['runId']==self.run)
        if self.role=='primary':self.prepare()
        pending=None
        with self.lock.held():
            state=self.control()
            if state is None:pending=GraphicsPhasePending('Graphics owner has not prepared its controlled scene')
            else:
                try:
                    active=self.phase(state);self.admit_observation(state,active)
                    return self.acquire(state,call['afterSequence'])
                except GraphicsPhasePending as error:pending=error
        raise pending

    def publish(self):
        need(self.role=='actor');pending=None
        with self.lock.held():
            state=self.control()
            if state is None:pending=GraphicsPhasePending('Graphics owner has not prepared its controlled scene')
            else:
                try:
                    active=self.phase(state);self.admit_observation(state,active)
                    observer=self.observer();life=self.lifetime(state['stage'])
                    if not life.state['activeProofs']:observer.read(0,state['stage']);life.observe_active()
                    return observer.publish(0,state['stage'])
                except GraphicsRunRetired as error:
                    try:pending=self.retire_actor(state,error.status)
                    except GraphicsPhasePending as waiting:pending=waiting
                except GraphicsPhasePending as error:pending=error
        raise pending

    def cleanup(self,call):
        need(self.role=='primary');call=arguments('feature.graphics.cleanup',call);need(call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            state=self.control();need(state is not None and state['binding'] is not None
                and state['phase'] in ('baseline','acting','active','cleaning','cleaned'))
            active=self.phase(state);need(active['verb']=='cleanup')
            started=previous=self.monotonic();need(number(started,0,1e15))
            def bound():
                nonlocal previous
                now=self.monotonic();need(number(now,previous,1e15) and now-started<45);previous=now;self.lock.assert_held()
            if state['phase']!='cleaned':
                state.update(phase='cleaning',ticket=active['ticket'],call=None,backend=active['status']);self.save(state)
                scene=self.scene();preferences=self.preferences(scene);preferences.cleanup();bound()
                observer=self.observer();baseline=observer.baseline();first=since=None
                state['cleanupWindow']=dict(start=len(state['cleanup']),elapsedMs=0,complete=False);self.save(state)
                for attempt in range(32):
                    value=observer.read(0,state['stage']);bound()
                    need(projection('graphics',value['state'])==baseline and value['state']['dialog'] is False and value['resources']==[])
                    if first is None:first,since=value['capturedEpochMs'],self.monotonic()
                    need(len(state['cleanup'])<64);state['cleanup'].append(observer.frame_record(observer.state['last']['frame']))
                    state['cleanupWindow']['elapsedMs']=int((self.monotonic()-since)*1000);self.save(state)
                    if attempt>=2 and self.monotonic()-since>=3 and value['capturedEpochMs']-first>=3000:
                        state['cleanupWindow']['complete']=True;self.save(state);break
                    need(attempt<31);self.sleep(.25);bound()
                state['phase']='cleaned';self.save(state)
            else:need(state['ticket']==active['ticket'])
            bound();return {'performed':True}

    def child_stores(self):
        names={kind:'phone-graphics-'+kind+'.json' for kind in ('scene','preferences','background','restart','restart-inputs')}
        for role in ('primary','actor'):
            names['observer-'+role]='phone-graphics-'+role+'-observer.json'
            for stage in (0,1):
                for kind in ('samples','lifetime'):
                    names[kind+'-'+role+'-'+str(stage)]='phone-graphics-'+role+'-'+str(stage)+'-'+kind+'.json'
        return {key:PrivateFeatureState(self.store.path.with_name(name)) for key,name in names.items()}

    def diagnostic(self,plan,key,value=None):
        """Private immutable original archive, not an active product resource."""
        import hashlib
        from overte_phone_script_history import canonical
        need(key in set(self.child_stores())|{'owner'} and type(plan['archives']) is dict)
        path=self.artifact_root/('graphics-'+self.run+'-'+key+'.json');store=PrivateFeatureState(path)
        old=store.read()
        if value is not None:
            need(type(value) is dict and key not in plan['archives'] and (old is None or same(old,value)))
            digest=hashlib.sha256(canonical(value)).hexdigest()
            if key not in plan['archiveIntents']:
                plan['archiveIntents'][key]=digest;self.write_record(self.retirement_store,'retirement',plan)
            else:need(plan['archiveIntents'][key]==digest)
            if old is None:store.write(deepcopy(value),None)
            old=store.read();need(same(old,value))
            plan['archives'][key]=digest;self.write_record(self.retirement_store,'retirement',plan)
        need(old is not None and key in plan['archives']
            and hashlib.sha256(canonical(old)).hexdigest()==plan['archives'][key])
        return deepcopy(old)

    def recover_diagnostics(self,plan):
        import hashlib,re
        from overte_phone_script_history import canonical
        need(type(plan['archiveIntents']) is dict and type(plan['archives']) is dict)
        stores=self.child_stores();stores['owner']=self.store
        need(set(plan['archives'])<=set(plan['archiveIntents'])<=set(stores))
        for key,digest in plan['archiveIntents'].items():
            need(type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest))
            if key in plan['archives']:
                need(plan['archives'][key]==digest);self.diagnostic(plan,key);continue
            path=self.artifact_root/('graphics-'+self.run+'-'+key+'.json');archive=PrivateFeatureState(path)
            value=archive.read()
            if value is None:
                # Recovery precedes component source reads. Only its exact
                # still-owned pre-write header can recreate this intended file.
                value=stores[key].read();need(value is not None and hashlib.sha256(canonical(value)).hexdigest()==digest)
                archive.write(value,None);need(same(archive.read(),value))
            need(hashlib.sha256(canonical(value)).hexdigest()==digest)
            plan['archives'][key]=digest;self.write_record(self.retirement_store,'retirement',plan)

    def observer_archive(self,plan,role):
        return PhoneGraphicsObserver.archive(self.diagnostic(plan,'observer-'+role),run=self.run,fixture_url=self.source.client.url,
            provider_instance=self.source.instance,role=role,artifact_root=self.artifact_root,image_policy=self.image_policy)

    def lifetime_archive(self,plan,role,stage,binding):
        return PhoneGraphicsLifetime.archive(self.diagnostic(plan,'lifetime-'+role+'-'+str(stage)),run=self.run,
            fixture_url=self.source.client.url,provider_instance=self.source.instance,role=role,stage=stage,binding=binding)

    def original_world(self,plan):
        value=self.diagnostic(plan,'scene')
        decoder=PhoneGraphicsScene._archive_scope(adapter=self.adapter,selector=self.selector,client=self.source.client,run=self.run)
        state=decoder.decode(value);need(state['phase']=='restored' and not any(state['leases'].values()) and state['proof'] is not None)
        return deepcopy(state['original']['subject'])

    def retire_actor(self,state,status):
        """After ordinary world restoration, this worker measures its own quiet window."""
        need(self.role=='actor')
        if state['phase'] not in ('world-restored','retiring'):
            raise GraphicsPhasePending('Graphics user scene has not reached final restoration')
        plan=self.read_record(self.retirement_store,'retirement');need(plan is not None and plan['stage']==state['stage'])
        observer=self.observer();saved=observer.state
        need(saved['phase'] in ('ready','retired') and saved['stage']==state['stage'] and saved['last'] is not None
            and saved['last']['frame']['ticket']==state['ticket'] and same(saved['binding'],state['binding']))
        actual,_=observer.frame(saved['last']['frame'],saved['binding'],saved['stage'])
        need(projection('graphics',actual['state'])==observer.baseline() and actual['state']['dialog'] is False and actual['resources']==[])
        if saved['phase']!='retired':
            life=self.lifetime(state['stage']);life.wait_released(self.original_world(plan))
            saved.update(phase='retired',backend=deepcopy(life.state['provider']));observer.save()
        need(saved['backend']['active'] is False and status['active'] is False)
        return GraphicsRunRetired(status)

    def world_restoration(self,state,plan):
        """Restore product state before deciding whether the run can retire green."""
        stores=self.child_stores()
        need(all(self.adapter.world_render_store(self.selector,role=role).read() is None for role in ('primary','actor')))
        state['phase']='world-restoring';self.save(state)
        # Exact final component archives are durable before their metadata can
        # disappear. A retry uses those originals and the component's own fresh
        # proof/removal path, never an invented successful empty fallback.
        if stores['preferences'].read() is not None:
            scene=self.scene();preferences=self.preferences(scene);preferences.cleanup()
            if 'preferences' not in plan['archives']:self.diagnostic(plan,'preferences',preferences.previous)
            if stores['background'].read() is not None:
                background=self.background(preferences);need(background.state['phase']=='observed')
                if 'background' not in plan['archives']:self.diagnostic(plan,'background',background.previous)
                background.retire()
            preferences.retire();need(stores['preferences'].read() is None)
        else:need('preferences' in plan['archives'])
        if stores['scene'].read() is not None:
            scene=self.scene();scene.restore()
            if 'scene' not in plan['archives']:self.diagnostic(plan,'scene',scene.previous)
            scene.retire();need(stores['scene'].read() is None)
        else:need('scene' in plan['archives'])
        if stores['restart'].read() is not None:
            restart=self.restart();restart.retire(self.diagnostic(plan,'scene'),self.diagnostic(plan,'preferences'))
        need(all(stores[key].read() is None for key in ('scene','preferences','background','restart','restart-inputs')))
        plan['phase']='world-restored';self.write_record(self.retirement_store,'retirement',plan)
        state.update(phase='world-restored',world=dict(scene=plan['archives']['scene'],preferences=plan['archives']['preferences']))
        self.save(state)

    def complete_archives(self,state,plan):
        """Validate both roles and every original image/source before metadata removal."""
        from overte_phone_graphics_samples import PhoneGraphicsSamples
        stores=self.child_stores();baseline=None
        for role in ('primary','actor'):
            key='observer-'+role
            if key not in plan['archives']:self.diagnostic(plan,key,stores[key].read())
            observer=self.observer_archive(plan,role)
            need(observer['phase']==('retired' if role=='actor' else 'ready') and observer['stage']==state['stage']
                and observer['last'] is not None and observer['last']['frame']['ticket']==state['ticket']
                and same(observer['binding'],state['binding']))
            scope=object.__new__(PhoneGraphicsObserver)
            scope.run,scope.fixture_url,scope.role=self.run,self.fixture_url,role
            scope.artifact_root,scope.image_policy=self.artifact_root,self.image_policy
            frame=observer['last']['frame'];actual,_=scope.frame(frame,observer['binding'],observer['stage'])
            binding0=observer['restart']['oldBinding'] if observer['stage'] else observer['binding']
            initial,_=scope.frame(observer['baseline'],binding0,0);original=projection('graphics',initial['state'])
            if baseline is None:baseline=original
            need(original==baseline and projection('graphics',actual['state'])==baseline
                and not actual['state']['dialog'] and actual['resources']==[])
            if state['stage']==1:
                newer_key='lifetime-'+role+'-1'
                if newer_key not in plan['archives']:self.diagnostic(plan,newer_key,stores[newer_key].read())
            for stage in range(state['stage']+1):
                binding=binding0 if stage==0 else observer['binding']
                for kind in ('samples','lifetime'):
                    key=kind+'-'+role+'-'+str(stage)
                    if key not in plan['archives']:self.diagnostic(plan,key,stores[key].read())
                samples=PhoneGraphicsSamples.archive(self.diagnostic(plan,'samples-'+role+'-'+str(stage)),client=self.source.client,
                    run=self.run,provider_instance=self.source.instance,role=role,stage=stage,binding=binding,
                    artifact_root=self.artifact_root,image_policy=self.image_policy)
                expected=observer['restart']['oldFrame'] if stage<state['stage'] else frame
                need(same(samples['frame'],expected))
                life=self.lifetime_archive(plan,role,stage,binding)
                need(life['activeProofs'] and life['activeProofs'][-1]['subject']['instance']==expected['nativeAfter']['instance'])
                if stage==state['stage']:need(life['phase']=='released')
                else:
                    # This role's separate qualified ESRCH receipt retires the
                    # old process; old Web facts retain their original PID.
                    need(life['phase']=='ready' and observer['restart'] is not None
                        and observer['restart']['exit']['queryProcessId']==life['activeProofs'][-1]['subject']['processId'])
                    newer=self.lifetime_archive(plan,role,1,observer['binding'])
                    old_web=life['activeProofs'][-1]['web'];new_web=newer['activeProofs'][0]['web']
                    need(old_web['instance']!=new_web['instance']
                        and old_web['source']['java']['instance']!=new_web['source']['java']['instance'])
        need(baseline is not None)
        # The adapter's own cleanup evidence must span both actual clocks,
        # independently of the later common cleanup and whole-world windows.
        window=state['cleanupWindow'];exact(window,{'start','elapsedMs','complete'})
        need(integer(window['start'],0,len(state['cleanup'])) and integer(window['elapsedMs'],3000,45000) and window['complete'] is True)
        scope.role='primary'
        samples=[scope.load_frame(reference) for reference in state['cleanup'][window['start']:]]
        for frame in samples:
            current,_=scope.frame(frame,state['binding'],state['stage'])
            need(frame['ticket']==state['ticket'] and projection('graphics',current['state'])==baseline
                and current['state']['dialog'] is False and current['resources']==[])
        need(len(samples)>=3 and samples[-1]['nativeAfter']['capturedEpochMs']-samples[0]['nativeBefore']['capturedEpochMs']>=3000)
        return baseline

    def final_runtime(self,state,plan):
        # Accepted original source floors belong to the parent plan, never a
        # recreated child. Every attempt starts a new complete quiet window.
        scope=object.__new__(PhoneGraphicsLifetime)
        scope.run,scope.fixture_url,scope.source=self.run,self.fixture_url,self.source
        scope.pid=int(state['binding']['processIdentity'].split(':')[0])
        archived=self.lifetime_archive(plan,'primary',state['stage'],state['binding'])
        original=self.original_world(plan);runtime=plan['runtime']
        if runtime is None:
            runtime=dict(sequence=archived['sequence'],cursors={key:deepcopy(archived[key]) for key in ('provider','subject','loads','web')},frame=None,windows=[])
            plan['runtime']=runtime;self.write_record(self.retirement_store,'retirement',plan)
        exact(runtime,{'sequence','cursors','frame','windows'});exact(runtime['cursors'],{'provider','subject','loads','web'})
        need(integer(runtime['sequence'],archived['sequence'],255) and type(runtime['windows']) is list and len(runtime['windows'])<8)
        previous=archived['windows'][-1]['samples'][-1]
        for window in runtime['windows']:
            exact(window,{'samples','elapsedMs','complete'})
            need(type(window['samples']) is list and len(window['samples'])<=64 and integer(window['elapsedMs'],0,20000)
                and type(window['complete']) is bool)
            for row in window['samples']:
                scope.group(row,'released',original);need(row['sequence']==previous['sequence']+1)
                for kind,key in (('provider','providerAfter'),('subject','subject'),('loads','loads'),('web','web')):
                    scope.follows(kind,previous[key],row['providerBefore'] if kind=='provider' else row[key])
                previous=row
            if window['complete']:
                need(len(window['samples'])>=3 and window['elapsedMs']>=3000 and
                    window['samples'][-1]['providerBefore']['capturedEpochMs']-window['samples'][0]['providerBefore']['capturedEpochMs']>=3000)
        need(previous['sequence']==runtime['sequence'])
        if runtime['frame'] is None:
            need(runtime['sequence']==archived['sequence'] and not any(window['samples'] for window in runtime['windows']))
        else:need(same(runtime['frame'],previous))
        for kind,packet in runtime['cursors'].items():
            scope.validate_packet(kind,packet,packet['capturedEpochMs'])
            key='providerAfter' if kind=='provider' else kind
            if not same(previous[key],packet):scope.follows(kind,previous[key],packet)
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,state['binding']) and guard() is not False)
        started=last=self.monotonic();need(number(started,0,1e15));since=None
        runtime['windows'].append(dict(samples=[],elapsedMs=0,complete=False));self.write_record(self.retirement_store,'retirement',plan)
        def bound():
            nonlocal last
            self.lock.assert_held();need(guard() is not False)
            now=self.monotonic();need(number(now,last,started+20) and now-started<20);last=now;return now
        def accept(kind,packet):
            bound();scope.validate_packet(kind,packet,packet['capturedEpochMs'])
            scope.follows(kind,runtime['cursors'][kind],packet);runtime['cursors'][kind]=deepcopy(packet)
            self.write_record(self.retirement_store,'retirement',plan);bound();return packet
        for attempt in range(64):
            epoch=self.source.clock();group_started=bound()
            before=accept('provider',self.source.status(runtime['cursors']['provider']))
            subject=self.adapter._graphics_subject_observer(self.selector,read_only=True);subject.last=deepcopy(runtime['cursors']['subject'])
            actual=accept('subject',subject.read(self.run,require_avatar=True))
            loads=self.adapter._scene_load_observer(self.selector,read_only=True);loads.last=deepcopy(runtime['cursors']['loads'])
            pending=accept('loads',loads.read(self.run))
            web=self.adapter._web_runtime_observer(self.selector,read_only=True);web.last=deepcopy(runtime['cursors']['web'])
            browsers=accept('web',web.read(self.run,self.fixture_url))
            after=accept('provider',self.source.status(runtime['cursors']['provider']))
            frame=dict(sequence=runtime['sequence']+1,providerBefore=before,subject=actual,loads=pending,web=browsers,providerAfter=after)
            scope.group(frame,'released',original)
            from adapters.native_feature_observation import fresh
            fresh(before['capturedEpochMs'],self.source.clock())
            need(max(self.source.clock()-before['capturedEpochMs'],epoch-before['capturedEpochMs']+(bound()-group_started)*1000)<=1500)
            now=bound()
            if since is None:since=now
            window=runtime['windows'][-1];window['samples'].append(deepcopy(frame));window['elapsedMs']=int((now-since)*1000)
            runtime.update(sequence=frame['sequence'],frame=deepcopy(frame));self.write_record(self.retirement_store,'retirement',plan)
            if len(window['samples'])>=3 and now-since>=3 and frame['providerBefore']['capturedEpochMs']-window['samples'][0]['providerBefore']['capturedEpochMs']>=3000:
                window['complete']=True;self.write_record(self.retirement_store,'retirement',plan);bound();return frame
            need(attempt<63);self.sleep(.25);bound()
        raise NativeUIError('Original Graphics final runtime did not reach a complete quiet window')

    def final_native(self,state,plan):
        """New original native/UI evidence, preserving source-owned histories."""
        from overte_phone_graphics_samples import restore_native,restore_ui
        from overte_phone_script_files import validate as tablet_packet
        from adapters.script_ui_inventory import validate as inventory_packet
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,state['binding']) and guard() is not False)
        scene=PhoneGraphicsScene._archive_scope(adapter=self.adapter,selector=self.selector,client=self.source.client,run=self.run)
        scene.state=scene.decode(self.diagnostic(plan,'scene'));scene.binding=scene.state['binding']
        preferences=PhoneGraphicsPreferences.archive(self.diagnostic(plan,'preferences'),scene=scene)
        originals=[preferences['native']]
        tablets=[]
        for role in ('primary','actor'):
            observer=self.observer_archive(plan,role);originals.append(observer['last']['frame']['nativeAfter'])
            tablets.append(observer['last']['frame']['tablet'])
        if plan['verification'] is not None:
            originals.append(plan['verification']['native']);tablets.append(plan['verification']['tablet'])
        native=self.adapter._native_feature_observer(self.selector,read_only=True)
        # Restore only the newest original accepted source floor. The actual
        # source reader still verifies its full native-owned event histories.
        prior=max(originals,key=lambda packet:packet['sequence']);restore_native(native,prior)
        runtime=self.final_runtime(state,plan)
        acquired_at=self.monotonic();initial_epoch=self.source.clock()
        packet=native.read(native.sequence);need(packet['graphics']==preferences['original']['graphics'])
        tablet=self.adapter._script_file_io(self.selector,read_only=True)
        restore_ui(tablet,max(tablets,key=lambda packet:packet['sourceSequence']),tablet_packet)
        page=tablet.capture();inventory=inventory_packet(page['scriptInventory'])
        need(inventory['complete'] and not inventory['tabletShown'] and not any(row['rootVisible'] for row in inventory['managers'])
            and not any(row['visible'] or row['requestId'] for row in inventory['pickers']))
        status=self.source.status(state['backend']);need(status['active'] is False and guard() is not False)
        from adapters.native_feature_observation import fresh
        epoch=self.source.clock();oldest=min(packet['capturedEpochMs'],page['capturedEpochMs'],runtime['providerBefore']['capturedEpochMs']);fresh(oldest,epoch)
        need(guard() is not False)
        need(max(epoch-oldest,initial_epoch-oldest+(self.monotonic()-acquired_at)*1000)<=1500)
        return dict(native=packet,tablet=page,status=status,runtime=runtime)

    def finalize(self):
        """Bounded, recoverable retirement after original ordinary restoration."""
        import hashlib
        from overte_phone_script_history import canonical
        need(self.role=='primary');started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            now=self.monotonic();need(number(now,previous,1e15) and now-started<60);previous=now
        # Short lock intervals allow the independent actor to observe its own
        # final restored world after provider retirement, without new captures.
        for attempt in range(121):
            bound();waiting=False
            with self.lock.held(),self.adapter.existing_input_session(self.selector):
                plan=self.read_record(self.retirement_store,'retirement');state=self.control()
                if state is None:
                    need(plan is not None and plan['phase']=='retiring' and plan['owner'] is not None)
                    state=self.validate_control(deepcopy(plan['owner']))
                need(state['binding'] is not None)
                if self.source.instance is None:self.source.status()
                status=self.source.status(state['backend']);need(status['active'] is False)
                if plan is None:
                    need(state['phase'] in ('baseline','acting','active','cleaning','cleaned'))
                    plan=dict(phase='world',stage=state['stage'],binding=deepcopy(state['binding']),archives={},archiveIntents={},verification=None,items=None,owner=None,runtime=None)
                    self.write_record(self.retirement_store,'retirement',plan)
                exact(plan,{'phase','stage','binding','archives','archiveIntents','verification','items','owner','runtime'})
                need(plan['phase'] in ('world','world-restored','retiring') and type(plan['stage']) is int
                    and plan['stage']==state['stage'] and same(plan['binding'],state['binding']))
                self.recover_diagnostics(plan);bound()
                if plan['phase']=='world':self.world_restoration(state,plan);bound()
                if plan['phase']=='world-restored':
                    actor_path=self.child_stores()['observer-actor'];actor_value=actor_path.read();need(actor_value is not None)
                    actor=PhoneGraphicsObserver.archive(actor_value,run=self.run,fixture_url=self.source.client.url,
                        provider_instance=self.source.instance,role='actor',artifact_root=self.artifact_root,image_policy=self.image_policy)
                    if actor['phase']!='retired':waiting=True
                    else:
                        life=self.lifetime(state['stage']);life.wait_released(self.original_world(plan));bound()
                        self.complete_archives(state,plan);bound()
                        items=[]
                        for key,store in self.child_stores().items():
                            value=store.read()
                            if value is None:continue
                            need(key in plan['archives'] and same(value,self.diagnostic(plan,key)))
                            items.append(dict(component=key,sha256=hashlib.sha256(canonical(value)).hexdigest()))
                        plan.update(phase='retiring',items=items);self.write_record(self.retirement_store,'retirement',plan)

                if not waiting:
                    need(plan['phase']=='retiring' and type(plan['items']) is list)
                    if plan['owner'] is None:
                        state['phase']='retiring';self.save(state)
                        plan['owner']=deepcopy(state);self.write_record(self.retirement_store,'retirement',plan)
                    else:need(same(state,plan['owner']))
                    if 'owner' not in plan['archives']:self.diagnostic(plan,'owner',self.originals[self.store.path])
                    # The immutable originals remain private evidence after
                    # metadata retirement. Repeated attempts need fresh native
                    # absence and exact digest/actual filesystem absence only.
                    self.complete_archives(state,plan);bound()
                    plan['verification']=self.final_native(state,plan);self.write_record(self.retirement_store,'retirement',plan);bound()
                    stores=self.child_stores();seen=set()
                    for item in plan['items']:
                        exact(item,{'component','sha256'});key=item['component'];need(key in stores and key not in seen)
                        seen.add(key);original=self.diagnostic(plan,key)
                        need(hashlib.sha256(canonical(original)).hexdigest()==item['sha256'])
                        value=stores[key].read();need(value is None or same(value,original))
                        if value is not None:stores[key].discard(value)
                        need(stores[key].read() is None);bound()
                    need(all(store.read() is None for store in stores.values()))
                    if self.store.read() is not None:
                        need(same(state,plan['owner']));self.store.discard(self.originals[self.store.path])
                    need(self.store.read() is None)
                    self.retirement_store.discard(self.originals[self.retirement_store.path]);need(self.retirement_store.read() is None)
                    bound();return {'performed':True}
            need(attempt<120);self.sleep(.25)
        raise NativeUIError('Independent Graphics actor did not finish original world retirement')
