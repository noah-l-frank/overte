"""iOS Graphics whole-run input and independent observation coordination.

Source-only composition. Final stop/paired retirement must be present and
verified before this owner can be admitted as a complete feature capability.
"""
# Structure reviewed at frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# Actual iOS input, Vulkan originals, clocks and process ownership remain separate.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
import math
from pathlib import Path
import time

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy
from feature_journeys.contract import arguments,identifier
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.graphics_resources import validate_status
from feature_journeys.witness import projection
from ios.adapters.graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending
from ios.adapters.graphics_scene import IOSGraphicsScene
from ios.adapters.graphics_preferences import IOSGraphicsPreferences
from ios.adapters.graphics_calibration import IOSGraphicsCalibration
from ios.adapters.graphics_lifecycle import IOSGraphicsBackground
from ios.adapters.graphics_restart import IOSGraphicsRestart
from ios.adapters.graphics_observer import IOSGraphicsObserver,GraphicsEffectReferencePending
from ios.adapters.graphics_publisher import IOSGraphicsPublisher
from ios.adapters.graphics_lifetime import IOSGraphicsLifetime,GraphicsLifetimePending

VERSION=1


def bounded(seconds):
    """Nested preparation cannot extend the current public operation deadline."""
    def decorate(method):
        @wraps(method)
        def invoke(self,*args,**kwargs):
            need(self.retirement_store.read() is None)
            started=self.clock();outer=self.deadline
            self.deadline=started+seconds if outer is None else min(outer,started+seconds)
            try:
                for attempt in range(241):
                    try:
                        value=method(self,*args,**kwargs);self.clock();return value
                    except ScriptSourceBusy:
                        # Only proven lock contention is retried. All nested
                        # input/POST paths retain their durable one-send intent.
                        self.clock();need(attempt<240);self.sleep(.025)
                need(False)
            finally:self.deadline=outer
        return invoke
    return decorate


class IOSGraphicsFeature:
    def __init__(self,adapter,selector,source,artifact_root,image_policy,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,GraphicsFixtureReader) and role in ('primary','actor') and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.root,self.policy=Path(artifact_root),deepcopy(image_policy)
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir()
             and type(image_policy) is dict and image_policy.get('source')=='world-render-target')
        PrivateFeatureState(self.root/'graphics-feature-root-check')._parent()
        self.monotonic,self.sleep=monotonic,sleep;self.deadline=self.last_clock=None
        path=adapter.state_path(selector);self.store=PrivateFeatureState(path.with_name('ios-graphics-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('ios-graphics-'+role+'-observer.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('ios-graphics-retirement.json'))
        self.lock=ScriptSourceLock(path.with_name('script-feature-sources.lock'));self.previous=None

    def clock(self):
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.deadline is None or now<self.deadline));self.last_clock=now;return now

    def envelope(self,state):
        return dict(iosGraphicsFeatureVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,
            providerInstance=state['backend']['instance'],artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([state]))

    def validate_control(self,state):
        exact(state,{'phase','stage','binding','backend','ticket','call','calibration','restartReady','backgroundArchive','cleanup','cleanupWindow','restartBarrier','restartRejoined'})
        need(state['phase'] in ('preparing','calibrating','baseline','acting','restart-barrier','restart-observing','active','cleaning','cleaned')
             and integer(state['stage'],0,1) and type(state['cleanup']) is list and len(state['cleanup'])<=81)
        status=state['backend'];validate_status(status,instance=status['instance'],run=self.run,url=self.source.client.url,request=status['requestId'])
        need(self.source.instance in (None,status['instance']))
        if state['binding'] is not None:context(state['binding'])
        if state['phase']!='preparing':need(state['binding'] is not None)
        if state['phase'] in ('acting','restart-barrier','restart-observing','active'):need(state['call'] is not None)
        for key in ('ticket','restartReady'):
            if state[key] is not None:identifier(state[key])
        if state['call'] is not None:
            call=arguments('feature.graphics.act',state['call'])
            need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url and call['ticket']==state['ticket'])
        cal=state['calibration']
        if cal is not None:
            exact(cal,{'ordinal','purpose','resume'});need(integer(cal['ordinal'],1,8)
                and cal['purpose'] in ('baseline','refresh','restart','cleanup') and cal['resume'] in ('baseline','acting','active','cleaning')
                and state['phase']=='calibrating' and state['binding'] is not None)
        else:need(state['phase']!='calibrating')
        barrier=state['restartBarrier']
        if barrier is not None:
            exact(barrier,{'ticket','binding','roles','native'});identifier(barrier['ticket']);context(barrier['binding'])
            need(barrier['ticket']==state['restartReady'] and all(same(barrier['binding'][k],state['binding'][k])
                 for k in state['binding'] if k!='processIdentity'))
            exact(barrier['roles'],{'primary','actor'})
            for item in barrier['roles'].values():
                if item is not None:
                    exact(item,{'phase','before','after','frame'});need(item['phase'] in ('capturing','observed')
                        and type(item['before']) is str and len(item['before'])==64)
                    if item['phase']=='capturing':need(item['after'] is None and item['frame'] is None)
                    else:need(type(item['after']) is str and len(item['after'])==64 and type(item['frame']) is dict)
            if state['stage']==1:need(barrier['native'] is not None and all(r is not None and r['phase']=='observed' for r in barrier['roles'].values()))
        else:need(state['phase']!='restart-barrier')
        exact(state['restartRejoined'],{'primary','actor'})
        for ref in state['restartRejoined'].values():
            if ref is not None:need(type(ref) is str and len(ref)==64 and state['stage']==1)
        if state['phase']=='restart-observing':need(state['stage']==1 and state['restartBarrier'] is not None)
        window=state['cleanupWindow']
        if window is not None:
            exact(window,{'start','elapsedMs','complete'});need(integer(window['start'],0,len(state['cleanup']))
                and integer(window['elapsedMs'],0,20000) and type(window['complete']) is bool)
        for ref in state['cleanup']:
            exact(ref,{'iosGraphicsObserverFrameRefVersion','stage','requestId','sha256'})
            need(type(ref['iosGraphicsObserverFrameRefVersion']) is int and ref['iosGraphicsObserverFrameRefVersion']==1 and ref['stage']==state['stage'])
        if state['phase']=='cleaned':need(window is not None and window['complete'] is True and window['elapsedMs']>=3000)
        return state

    def control(self):
        need(self.retirement_store.read() is None)
        value=self.store.read();self.previous=deepcopy(value)
        if value is None:return None
        exact(value,{'iosGraphicsFeatureVersion','runId','fixtureUrl','providerInstance','artifactRoot','imagePolicy','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosGraphicsFeatureVersion']) is int
            and same(value,self.envelope(rows[0])));return self.validate_control(rows[0])

    def save(self,state):
        self.clock();self.lock.assert_held();self.validate_control(state);need(same(self.store.read(),self.previous))
        value=self.envelope(state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def scene(self):self.clock();return IOSGraphicsScene(self.adapter,self.selector,self.source.client,self.run,self.lock,monotonic=self.clock,sleep=self.sleep)
    def preferences(self,scene):self.clock();return IOSGraphicsPreferences(scene,monotonic=self.clock,sleep=self.sleep)
    def observer(self):self.clock();return IOSGraphicsObserver(self.adapter,self.selector,self.source,self.role,self.lock,self.root,self.policy,monotonic=self.clock,sleep=self.sleep)
    def lifetime(self,stage):self.clock();return IOSGraphicsLifetime(self.adapter,self.selector,self.source,self.role,stage,self.lock,monotonic=self.clock,sleep=self.sleep)
    def restart(self):self.clock();return IOSGraphicsRestart(self.adapter,self.selector,self.source.client,self.run,self.lock,self.root,self.policy,monotonic=self.clock,sleep=self.sleep)
    def calibration(self):self.clock();return IOSGraphicsCalibration(self.preferences(self.scene()),self.source)

    def phase(self,state):
        self.source.status();return self.source.read(state['backend'])

    def reserve_calibration(self,state,purpose,resume):
        need(self.role=='primary' and state['calibration'] is None)
        child=self.calibration();ordinal=1 if child.state is None else len(child.state['rounds'])+1
        need(ordinal<=8);state.update(phase='calibrating',calibration=dict(ordinal=ordinal,purpose=purpose,resume=resume));self.save(state)

    def progress_calibration(self,state):
        need(state['phase']=='calibrating');plan=state['calibration'];child=self.calibration()
        count=0 if child.state is None else len(child.state['rounds'])
        if count<plan['ordinal']:
            need(count==plan['ordinal']-1)
            if self.role=='actor':return False
            child.begin(state['stage'])
        row=child.state['rounds'][-1]
        need(row['ordinal']==plan['ordinal'] and row['stage']==state['stage'] and same(row['binding'],state['binding'])
             and row.get('captureFeatures')==['haze','mirror'])
        if self.role=='primary':child.advance_primary()
        row=child.state['rounds'][-1]
        if row['phase']=='off' and (row['roles'][self.role] is None or row['roles'][self.role]['phase']!='observed'):
            observer=self.observer()
            if observer.state['phase']=='reading':observer.retire_phase()
            child.capture(observer)
        if self.role=='primary' and child.advance_primary():
            if plan['purpose']=='restart':state['restartReady']=state['ticket']
            state.update(phase=plan['resume'],calibration=None,backend=deepcopy(self.source.previous));self.save(state);return True
        return False

    def barrier_store(self,role,kind):
        need(role in ('primary','actor') and kind in ('before','after'))
        return PrivateFeatureState(self.root/('graphics-restart-barrier-'+self.run+'-'+role+'-'+kind+'.json'))

    def barrier_record(self,role,kind,binding,value=None):
        from adapters.native_clock_join import digest
        store=self.barrier_store(role,kind);original=store.read()
        if value is not None:
            row=dict(iosGraphicsRestartBarrierRecordVersion=1,runId=self.run,fixtureUrl=self.source.client.url,
                providerInstance=self.source.instance,role=role,kind=kind,binding=deepcopy(binding),observer=deepcopy(value))
            if original is None:store.write(row,None)
            else:need(same(original,row))
            original=store.read();need(same(original,row))
        exact(original,{'iosGraphicsRestartBarrierRecordVersion','runId','fixtureUrl','providerInstance','role','kind','binding','observer'})
        need(type(original['iosGraphicsRestartBarrierRecordVersion']) is int and original['iosGraphicsRestartBarrierRecordVersion']==1
             and original['runId']==self.run and original['fixtureUrl']==self.source.client.url
             and original['providerInstance']==self.source.instance and original['role']==role and original['kind']==kind
             and same(context(original['binding']),binding))
        scope=IOSGraphicsObserver._archive_scope(original['observer'],path=self.store.path.with_name('ios-graphics-'+role+'-observer.json'),
            run=self.run,fixture_url=self.source.client.url,provider_instance=self.source.instance,role=role,
            lock=self.lock,artifact_root=self.root,image_policy=self.policy)
        need(scope.state['phase']=='ready' and scope.state['stage']==0 and same(scope.state['binding'],binding)
             and scope.state['last'] is not None)
        return original,scope,digest(original)

    def validate_barrier(self,barrier):
        from adapters.native_feature_observation import validate as native_packet
        from ios.adapters.graphics_history import follow_native
        exact(barrier,{'ticket','binding','roles','native'})
        identifier(barrier['ticket']);context(barrier['binding']);exact(barrier['roles'],{'primary','actor'})
        frames=[]
        for role,item in barrier['roles'].items():
            if item is None:continue
            exact(item,{'phase','before','after','frame'});need(item['phase'] in ('capturing','observed'))
            _value,before,sha=self.barrier_record(role,'before',barrier['binding']);need(item['before']==sha)
            if item['phase']=='capturing':need(item['after'] is None and item['frame'] is None);continue
            _value,after,sha=self.barrier_record(role,'after',barrier['binding']);need(item['after']==sha
                and after.state['sequence']==before.state['sequence']+1 and same(after.state['last'],item['frame']))
            frame,_raw,_actual,_name=after.frame(item['frame'],barrier['binding'])
            need(frame['provider']['ticket']==barrier['ticket']);frames.append(frame)
        packet=barrier['native']
        if packet is not None:
            need(len(frames)==2);native_packet(packet,packet['requestId'],int(barrier['binding']['processIdentity']),packet['capturedEpochMs'])
            for frame in frames:
                follow_native(frame['clockJoin']['nativeAfter'],packet)
                need(same(frame['nativeAfter']['graphics'],packet['graphics']))
        return barrier

    def reserve_barrier(self,state):
        need(self.role=='primary' and state['stage']==0 and state['restartBarrier'] is None
             and state['restartReady']==state['ticket'] and state['call']['verb']=='restart-app')
        state.update(phase='restart-barrier',restartBarrier=dict(ticket=state['ticket'],binding=deepcopy(state['binding']),
            roles=dict(primary=None,actor=None),native=None));self.save(state)

    def progress_barrier(self,state):
        from adapters.native_clock_join import digest
        from ios.adapters.graphics_history import follow_native
        need(state['phase']=='restart-barrier' and state['stage']==0)
        barrier=state['restartBarrier'];need(barrier['ticket']==state['ticket'] and same(barrier['binding'],state['binding']))
        active=self.phase(state);need(active['ticket']==barrier['ticket'] and active['verb']=='restart-app')
        observer=self.observer()
        if observer.state['phase']=='reading':observer.retire_phase()
        if self.role=='actor':IOSGraphicsPublisher(observer).resolve()
        item=barrier['roles'][self.role]
        if item is None:
            # The actual before copy is durable before any new capture. A
            # missing role slot may adopt this exact original copy, never a new
            # expected frame or a native resource-creating retry.
            original,old,sha=self.barrier_record(self.role,'before',barrier['binding'],observer.previous)
            item=dict(phase='capturing',before=sha,after=None,frame=None);barrier['roles'][self.role]=item;self.save(state)
        _before,before,sha=self.barrier_record(self.role,'before',barrier['binding']);need(item['before']==sha)
        if item['phase']=='capturing':
            existing=self.barrier_store(self.role,'after').read()
            if existing is not None:
                after,scope,sha=self.barrier_record(self.role,'after',barrier['binding'])
                need(same(observer.previous,after['observer']))
            else:
                if same(observer.previous,_before['observer']):observer.read(0,0)
                else:need(observer.state['phase']=='ready' and observer.state['sequence']==before.state['sequence']+1)
                frame=observer.frame(observer.state['last'],barrier['binding'])[0]
                need(frame['provider']['ticket']==barrier['ticket'])
                after,scope,sha=self.barrier_record(self.role,'after',barrier['binding'],observer.previous)
            need(scope.state['sequence']==before.state['sequence']+1)
            item.update(phase='observed',after=sha,frame=deepcopy(scope.state['last']));self.save(state)
        self.validate_barrier(barrier)
        if self.role=='primary' and all(item is not None and item['phase']=='observed' for item in barrier['roles'].values()):
            if barrier['native'] is None:
                packet=self.preferences(self.scene()).source()
                for role in ('primary','actor'):
                    _value,scope,_sha=self.barrier_record(role,'after',barrier['binding'])
                    frame=scope.frame(barrier['roles'][role]['frame'],barrier['binding'])[0]
                    follow_native(frame['clockJoin']['nativeAfter'],packet);need(same(frame['nativeAfter']['graphics'],packet['graphics']))
                barrier['native']=deepcopy(packet);self.validate_barrier(barrier)
            state.update(phase='acting',backend=deepcopy(self.source.previous));self.save(state);return True
        return False


    def rejoined_record(self,state,role):
        from adapters.native_clock_join import digest
        need(role in ('primary','actor') and state['stage']==1 and state['restartBarrier'] is not None)
        value=PrivateFeatureState(self.root/('graphics-restart-rejoined-'+self.run+'-'+role+'.json')).read()
        exact(value,{'iosGraphicsRestartRejoinedVersion','runId','fixtureUrl','providerInstance','role','binding','observer'})
        need(type(value['iosGraphicsRestartRejoinedVersion']) is int and value['iosGraphicsRestartRejoinedVersion']==1
            and value['runId']==self.run and value['fixtureUrl']==self.source.client.url and value['providerInstance']==self.source.instance
            and value['role']==role and same(value['binding'],state['binding']))
        saved=IOSGraphicsObserver.archive(value['observer'],path=self.store.path.with_name('ios-graphics-'+role+'-observer.json'),
            run=self.run,fixture_url=self.source.client.url,provider_instance=self.source.instance,role=role,lock=self.lock,
            artifact_root=self.root,image_policy=self.policy)
        need(saved['stage']==1 and saved['phase']=='ready' and same(saved['binding'],state['binding'])
             and same(saved['restart']['oldFrame'],state['restartBarrier']['roles'][role]['frame']))
        return value,saved,digest(value)

    def progress_rejoined(self,state):
        """Both roles acquire their own first new-process frame before more input."""
        from adapters.native_clock_join import digest
        need(state['phase']=='restart-observing' and state['stage']==1)
        active=self.phase(state);need(active['ticket']==state['ticket'] and active['verb']=='restart-app')
        observer=self.observer();store=PrivateFeatureState(self.root/('graphics-restart-rejoined-'+self.run+'-'+self.role+'.json'))
        value=store.read()
        if value is None:
            if observer.state['stage']==0:observer.read(0,1)
            need(observer.state['stage']==1 and observer.state['phase']=='ready')
            frame=observer.frame(observer.state['last'],state['binding'])[0];need(frame['provider']['ticket']==state['ticket'])
            value=dict(iosGraphicsRestartRejoinedVersion=1,runId=self.run,fixtureUrl=self.source.client.url,
                providerInstance=self.source.instance,role=self.role,binding=deepcopy(state['binding']),observer=deepcopy(observer.previous))
            store.write(value,None);need(same(store.read(),value))
        value,saved,ref=self.rejoined_record(state,self.role);need(same(value['observer'],observer.previous))
        life=self.lifetime(1)
        if not life.state['activeProofs']:
            try:life.observe_active()
            except GraphicsLifetimePending:return False
        need(state['restartRejoined'][self.role] in (None,ref))
        state['restartRejoined'][self.role]=ref;self.save(state)
        if self.role=='primary' and all(state['restartRejoined'].values()):
            # Re-read both immutable copies and their actual role-owned lifetime
            # histories. Two acknowledgments cannot conceal a foreign record.
            for role,ref in state['restartRejoined'].items():
                _value,_saved,sha=self.rejoined_record(state,role);need(ref==sha)
                path=self.store.path.with_name('ios-graphics-'+role+'-1-lifetime.json')
                lifetime=IOSGraphicsLifetime.archive(PrivateFeatureState(path).read(),path=path,run=self.run,
                    fixture_url=self.source.client.url,provider_instance=self.source.instance,role=role,stage=1,binding=state['binding'])
                need(lifetime['activeProofs'] and lifetime['abortProof'] is None)
            state.update(phase='active',backend=deepcopy(self.source.previous));self.save(state);return True
        return False

    @bounded(20)
    def prepare(self):
        need(self.role=='primary')
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.source.status();state=self.control()
            if state is None:
                need(self.retirement_store.read() is None)
                # Unindexed responsibility is not an empty new run. Evidence
                # artifacts live separately; these are only active owner files.
                parent=self.store.path.parent
                need(not list(parent.glob('ios-graphics-*.json')) and not list(parent.glob('graphics-world-frame-*.json')))
                active=self.source.read();need(active['verb']=='baseline')
                state=dict(phase='preparing',stage=0,binding=None,backend=active['status'],ticket=None,call=None,
                    calibration=None,restartReady=None,backgroundArchive=None,cleanup=[],cleanupWindow=None,restartBarrier=None,restartRejoined=dict(primary=None,actor=None));self.save(state)
            if state['phase']=='preparing':
                scene=self.scene();scene.prepare();prefs=self.preferences(scene);prefs.prepare()
                need(scene.state['phase']=='active' and prefs.state['phase']=='ready')
                state.update(binding=deepcopy(scene.binding),backend=deepcopy(self.source.previous));self.save(state)
                self.reserve_calibration(state,'baseline','baseline')
            if state['phase']=='calibrating':self.progress_calibration(state)
            return deepcopy(state)

    def budget(self,started,limit):
        now=self.monotonic();need(number(now,started,started+limit) and now-started<limit);return now

    @bounded(60)
    def act(self,call):
        need(self.role=='primary');call=deepcopy(arguments('feature.graphics.act',call))
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url);started=self.monotonic()
        for attempt in range(241):
            waiting=False;self.budget(started,60)
            with self.lock.held(),self.adapter.existing_input_session(self.selector):
                self.source.status();state=self.control();need(state is not None)
                active=self.phase(state);need(active['ticket']==call['ticket'] and active['verb']==call['verb'] and same(active['inputs'],call['inputs']))
                if state['phase']=='restart-observing':
                    need(state['ticket']==call['ticket'] and same(state['call'],call))
                    if self.progress_rejoined(state):return {'performed':True}
                    waiting=True
                if state['phase']=='restart-barrier':
                    need(state['ticket']==call['ticket'] and same(state['call'],call))
                    waiting=not self.progress_barrier(state)
                if state['phase']=='calibrating':
                    need(state['ticket']==call['ticket'] and same(state['call'],call))
                    waiting=not self.progress_calibration(state)
                if not waiting:
                    need(state['phase'] in ('baseline','acting','active'))
                    if state['ticket']==call['ticket']:
                        need(same(state['call'],call))
                        if state['phase']=='active':return {'performed':True}
                    else:
                        need(state['phase'] in ('baseline','active'));state.update(phase='acting',ticket=call['ticket'],call=call,backend=active['status']);self.save(state)
                    if call['verb']=='restart-app':
                        if state['restartReady']!=call['ticket']:
                            self.reserve_calibration(state,'restart','acting');waiting=not self.progress_calibration(state)
                        if not waiting:
                            if state['restartBarrier'] is None:self.reserve_barrier(state)
                            if state['phase']=='restart-barrier':waiting=not self.progress_barrier(state)
                        if not waiting:
                            self.validate_barrier(state['restartBarrier']);need(state['restartBarrier']['native'] is not None)
                            store=PrivateFeatureState(self.store.path.with_name('ios-graphics-background.json'))
                            if store.read() is not None:
                                background=IOSGraphicsBackground.recover(self.adapter,self.selector,self.source.client,self.run,self.lock,monotonic=self.clock,sleep=self.sleep)
                                need(background.state['phase']=='observed')
                                if state['backgroundArchive'] is None:state['backgroundArchive']=deepcopy(background.previous);self.save(state)
                                else:need(same(state['backgroundArchive'],background.previous))
                                background.retire()
                            self.restart().act(call);scene=self.scene();state.update(stage=1,binding=deepcopy(scene.binding),phase='restart-observing')
                            self.save(state);waiting=not self.progress_rejoined(state)
                            if not waiting:return {'performed':True}
                    elif call['verb']=='background-resume':
                        store=PrivateFeatureState(self.store.path.with_name('ios-graphics-background.json'))
                        if store.read() is not None:
                            background=IOSGraphicsBackground.recover(self.adapter,self.selector,self.source.client,self.run,self.lock,monotonic=self.clock,sleep=self.sleep)
                        else:background=IOSGraphicsBackground(self.preferences(self.scene()),monotonic=self.clock,sleep=self.sleep)
                        background.act(call)
                    else:self.preferences(self.scene()).act(call)
                    if not waiting:
                        state.update(phase='active',backend=deepcopy(self.source.previous));self.save(state);self.budget(started,60);return {'performed':True}
            need(attempt<240);self.sleep(.25)
        raise GraphicsPhasePending('Independent Graphics calibration has not completed')

    def admit(self,state,active):
        if state is None or state['phase'] in ('preparing','calibrating','acting','restart-barrier','restart-observing','cleaning'):
            raise GraphicsPhasePending('Ordinary Graphics input or calibration is incomplete')
        need(state['binding'] is not None)
        if active['verb']=='baseline':need(state['phase']=='baseline')
        elif active['verb']=='cleanup':
            if state['phase']!='cleaned':raise GraphicsPhasePending('Ordinary Graphics cleanup is incomplete')
            need(active['ticket']==state['ticket'])
        elif state['phase']!='active' or active['ticket']!=state['ticket']:
            raise GraphicsPhasePending('Graphics phase is awaiting its ordinary input')

    def acquire(self,state,after_sequence):
        observer=self.observer();life=self.lifetime(state['stage'])
        if observer.state['phase']=='reading':observer.retire_phase()
        try:observer.effect_preflight(state['stage'])
        except GraphicsEffectReferencePending:
            if self.role=='primary':self.reserve_calibration(state,'refresh',state['phase'])
            raise
        if not life.state['activeProofs']:
            observer.read(0,state['stage'])
            try:life.observe_active()
            except GraphicsLifetimePending:raise GraphicsPhasePending('Original Graphics marker lifetime is not yet admitted') from None
        return observer.read(after_sequence,state['stage'])

    @bounded(20)
    def observe(self,call):
        call=arguments('feature.graphics.observe',call);need(call['runId']==self.run)
        if self.role=='primary':self.prepare()
        started=self.monotonic()
        for attempt in range(81):
            pending=None;self.budget(started,20)
            with self.lock.held():
                self.source.status();state=self.control()
                if state is not None and state['phase']=='calibrating':
                    self.progress_calibration(state)
                    pending=GraphicsPhasePending('Independent Graphics calibration is incomplete')
                else:
                    try:
                        if state is None:raise GraphicsPhasePending('Graphics owner has not prepared its scene')
                        active=self.phase(state);self.admit(state,active);return self.acquire(state,call['afterSequence'])
                    except GraphicsPhasePending as error:pending=error
            if self.role=='actor':raise pending
            need(attempt<80);self.sleep(.25)
        raise pending

    @bounded(20)
    def publish(self):
        need(self.role=='actor');pending=None
        with self.lock.held():
            try:return self._publish_locked()
            except GraphicsPhasePending as error:pending=error
        raise pending

    def _publish_locked(self):
        self.source.status();state=self.control()
        if state is None:raise GraphicsPhasePending('Graphics owner has not prepared its scene')
        if state['phase']=='restart-observing':
            self.progress_rejoined(state);raise GraphicsPhasePending('Both roles must observe the actual new Graphics process')
        if state['phase']=='restart-barrier':
            self.progress_barrier(state);raise GraphicsPhasePending('Both original Graphics roles must join the old-process barrier')
        if state['phase']=='calibrating':
            self.progress_calibration(state);raise GraphicsPhasePending('Independent Graphics calibration is incomplete')
        active=self.phase(state);self.admit(state,active)
        observer=self.observer()
        if observer.state['phase']=='reading':observer.retire_phase()
        publisher=IOSGraphicsPublisher(observer);publisher.resolve()
        life=self.lifetime(state['stage'])
        if not life.state['activeProofs']:
            observer.read(0,state['stage'])
            try:life.observe_active()
            except GraphicsLifetimePending:raise GraphicsPhasePending('Original Graphics marker lifetime is not yet admitted') from None
        return publisher.publish(state['stage'])


    @bounded(60)
    def cleanup(self,call):
        need(self.role=='primary');call=arguments('feature.graphics.cleanup',call);need(call['runId']==self.run)
        started=self.monotonic();window_started=False
        for attempt in range(241):
            self.budget(started,60);waiting=False
            with self.lock.held(),self.adapter.existing_input_session(self.selector):
                self.source.status();state=self.control();need(state is not None and state['binding'] is not None)
                active=self.phase(state);need(active['verb']=='cleanup')
                if state['phase']=='calibrating':
                    plan=state['calibration']
                    if plan['purpose']=='cleanup':waiting=not self.progress_calibration(state)
                    else:
                        # The previous input phase has retired. Its exact child
                        # record stays owned; restore actual preferences below.
                        state.update(phase='cleaning',calibration=None,ticket=active['ticket'],call=None,backend=active['status']);self.save(state)
                elif state['phase'] not in ('cleaning','cleaned'):
                    state.update(phase='cleaning',ticket=active['ticket'],call=None,backend=active['status']);self.save(state)
                    self.reserve_calibration(state,'cleanup','cleaning');waiting=not self.progress_calibration(state)
                if not waiting:
                    need(state['phase'] in ('cleaning','cleaned'))
                    if not window_started:
                        state.update(phase='cleaning',ticket=active['ticket'],call=None,cleanupWindow=None);self.save(state);window_started=True
                    self.preferences(self.scene()).cleanup();observer=self.observer()
                    if observer.state['phase']=='reading':observer.retire_phase()
                    baseline=observer.baseline();window=state['cleanupWindow']
                    if window is None:
                        window=dict(start=len(state['cleanup']),elapsedMs=0,complete=False);state['cleanupWindow']=window;self.save(state)
                    value=observer.read(0,state['stage']);need(projection('graphics',value['state'])==baseline and not value['state']['dialog'] and value['resources']==[])
                    need(len(state['cleanup'])<81);state['cleanup'].append(deepcopy(observer.state['last']))
                    rows=[observer.frame(ref,state['binding'])[0] for ref in state['cleanup'][window['start']:]]
                    first,last=rows[0]['clockJoin'],rows[-1]['clockJoin']
                    elapsed=min(last['hostBeforeEpochMs']-first['hostAfterEpochMs'],last['nativeBefore']['capturedEpochMs']-first['nativeAfter']['capturedEpochMs'],
                        (last['hostBeforeMonotonic']-first['hostAfterMonotonic'])*1000)
                    window['elapsedMs']=max(0,math.floor(elapsed));window['complete']=len(rows)>=3 and elapsed>=3000
                    if window['complete']:state['phase']='cleaned'
                    self.save(state);self.budget(started,60)
                    if window['complete']:return {'performed':True}
            need(attempt<240);self.sleep(.25)
        raise GraphicsPhasePending('Original Graphics cleanup has not reached its quiet window')
