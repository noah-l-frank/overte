"""Phone Lifecycle/Input public operations over independent original sources.

Fixture verbs authorize ordinary inputs only. Original native event/context
histories, kernel/session guards and original render bytes supply every fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import math
import time
import uuid
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.native_phone_web_runtime import active_marker,released as web_released
from feature_journeys.contract import arguments,result
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.evidence import image_observation
from feature_journeys.witness import projection
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_script_ui import PhoneScriptUI
from overte_phone_lifecycle_editor import advance as editor_advance
from overte_phone_lifecycle_world import advance as world_advance
from overte_phone_lifecycle_measurements import validate_sources,measurement,continuity_sources
from overte_phone_lifecycle_actions import LifecycleActions
from overte_phone_lifecycle_evidence import LifecycleEvidence
from overte_phone_navigation_feature import NavigationImages
from overte_phone_navigation_marker import input_command,input_receipt,ready as marker_ready,retired as marker_retired,near,rotation_equal,VIEW

AREA='lifecycle-input'
VERSION=1
IMAGE_VERBS={'world-input','background-resume','restore'}


class PhoneLifecycleInputFeature:
    def __init__(self,adapter,selector,source,root,policy,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,PhaseFixtureReader) and source.area==AREA and role in ('primary','actor') and all(callable(f) for f in (monotonic,sleep)))
        if role=='actor':need(not isinstance(source.client,AdapterFixtureClient))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url;self.root,self.policy=Path(root),deepcopy(policy)
        PrivateFeatureState(self.root/'lifecycle-evidence-boundary.json')._parent()
        path=adapter.state_path(selector);self.store=PrivateFeatureState(path.with_name('phone-lifecycle-input-feature.json'))
        self.role_store=self.role_path(role);self.retirement_store=PrivateFeatureState(path.with_name('phone-lifecycle-input-retirement.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'));self.completed_store=PrivateFeatureState(self.root/('lifecycle-retired-'+self.run+'.json'))
        self.completed_index=PrivateFeatureState(path.with_name('phone-lifecycle-input-completed.json'))
        self.monotonic,self.sleep=monotonic,sleep;self.previous={};self.owner=None;self.started=None;self.last_clock=None
    def role_path(self,role):return PrivateFeatureState(self.adapter.state_path(self.selector).with_name('phone-lifecycle-input-'+role+'.json'))
    @contextmanager
    def serialized(self):
        pending=None
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            try:
                self.started=self.monotonic();self.last_clock=self.started;self.bound();yield;self.bound()
            except PhasePending as error:pending=error
            finally:self.started=None
        if pending is not None:raise pending
    def bound(self):
        self.lock.assert_held();now=self.monotonic();need(number(now,0,1e15) and self.started is not None
            and self.last_clock<=now and now-self.started<45);self.last_clock=now
    def read(self,store,kind):
        value=store.read();self.previous[store.path]=deepcopy(value)
        if value is None:return None
        exact(value,{'lifecycleInputFeatureVersion','kind','runId','fixtureUrl','artifactRoot','imagePolicy','payload'})
        need(type(value['lifecycleInputFeatureVersion']) is int and value['lifecycleInputFeatureVersion']==VERSION and value['kind']==kind
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['artifactRoot']==str(self.root) and same(value['imagePolicy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]
    def save(self,store,kind,value):
        self.lock.assert_held();need(store.path in self.previous and same(store.read(),self.previous[store.path]))
        metadata=dict(lifecycleInputFeatureVersion=VERSION,kind=kind,runId=self.run,fixtureUrl=self.fixture_url,artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([value]))
        store.write(metadata,self.previous[store.path]);need(same(store.read(),metadata));self.previous[store.path]=deepcopy(metadata)
    def save_owner(self,owner):self.save(self.store,'owner',owner)
    def save_role(self,state,role):self.save(self.role_path(role),role,state)
    def load(self):
        self.owner=self.read(self.store,'owner')
        if self.owner is not None:
            owner=self.owner;exact(owner,{'binding','phase','baseline','phaseSource','call','tickets','steps','intents','tabletLease','marker','markerHistory'})
            context(owner['binding']);need(owner['phase'] in ('baseline','acting','active','cleaning','cleaned') and type(owner['tabletLease']) is bool)
            need(type(owner['steps']) is list and len(owner['steps'])<=256 and len(set(owner['steps']))==len(owner['steps'])
                and type(owner['intents']) is list and len(owner['intents'])<=256 and type(owner['tickets']) is list and len(owner['tickets'])<=256
                and len(set(owner['tickets']))==len(owner['tickets']) and type(owner['markerHistory']) is list and len(owner['markerHistory'])<=4)
            if owner['call'] is not None:arguments('feature.'+AREA+'.act',owner['call'])
        return self.owner
    def runtime(self,owner):
        self.bound()
        _ui,_observe,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(context(binding),owner['binding']) and guard() is not False);self.bound();return binding,guard
    def role_state(self,role=None):
        role=role or self.role;state=self.read(self.role_path(role),role)
        if state is None:
            state=dict(binding=deepcopy(self.owner['binding']),sequence=0,manifests=[],pending=None,originalIntent=None,manifestIntent=None,imageIntent=None,abandoned=[],quiet=None,closed=None)
            self.save_role(state,role)
        exact(state,{'binding','sequence','manifests','pending','originalIntent','manifestIntent','imageIntent','abandoned','quiet','closed'})
        need(same(state['binding'],self.owner['binding']) and integer(state['sequence'],0,256) and type(state['abandoned']) is list and len(state['abandoned'])<=256)
        return state
    def collect(self,last=None,*,after_epoch=0):
        binding,guard=self.runtime(self.owner);pid=int(binding['processIdentity'].split(':')[0])
        editor=self.adapter._lifecycle_editor(self.selector,read_only=True);world=self.adapter._lifecycle_world(self.selector,read_only=True)
        pending=self.adapter._pending_owner(self.selector,read_only=True);native=self.adapter._native_feature_observer(self.selector,read_only=True)
        if last is not None:
            validate_sources(self.run,last,pid,max(v['capturedEpochMs'] for v in last.values()))
            editor.last=deepcopy(last['editor']);world.restore([last['world']]);pending.last=deepcopy(last['pending'])
        before=editor.request(self.run);w=world.request(self.run)
        started=self.monotonic()
        for attempt in range(31):
            if w['motion']['capturedEpochMs']>=after_epoch:break
            need(attempt<30 and self.monotonic()-started<1.5);self.sleep(.05);w=world.request(self.run)
        p=pending.read(self.run);n=native.read(last['native']['sequence'] if last else 0)
        ui=PhoneScriptUI(self.adapter.normal_feature_runtime(self.selector,read_only=True)[0],'io.github.noah_be.overte.phone')
        sdk=dict(tabletVisible=ui.tablet_visible(),homeVisible=ui.native.available(ui.resource('app.scripts'),require_enabled=False),capturedEpochMs=int(native.clock_ms()))
        scene_reader=self.adapter._scene_load_observer(self.selector,read_only=True)
        if last is not None:scene_reader.last=deepcopy(last['scene'])
        scene=scene_reader.read(self.run);floor=last['probe']['source']['sampleSequence'] if last else 0;started=self.monotonic()
        for attempt in range(101):
            probe=self.adapter._navigation_probe(self.selector,floor);need(probe['sampleSequence']>=floor)
            if probe['sampleSequence']>floor and probe['sampleEpochMs']>=after_epoch and (last is None or probe['render']['frameCount']>last['probe']['source']['render']['frameCount']):break
            need(attempt<100 and self.monotonic()-started<5);self.sleep(.05)
        after=editor.request(self.run)
        need(all(same(before['source'][k],after['source'][k]) for k in ('current','contexts','osKeyboardVisible')))
        frame=dict(editor=after,world=w,pending=p,native=n,sdk=sdk,scene=scene,probe=dict(capturedEpochMs=probe['sampleEpochMs'],source=probe));epoch=int(native.clock_ms());validate_sources(self.run,frame,pid,epoch)
        if last is not None:
            continuity_sources(last,frame,pid)
        guard();return frame,epoch
    def neutral(self,frame,origin):
        e,w,p=frame['editor']['source'],frame['world'],frame['pending'];m=w['motion']
        need(e['current']['status']=='none' and not any(row['active'] for row in e['contexts']) and not e['osKeyboardVisible'] and not frame['sdk']['tabletVisible'] and not frame['sdk']['homeVisible']
            and not w['source']['pending'] and not w['source']['timerActive'] and not p['resources']['pendingRuns']
            and (not p['commit'] or not p['commit']['observation']['pending']) and m['upPressed']==0 and all(abs(v)<=1e-6 for v in m['effectiveDrive'])
            and m['grounded'] and math.dist(m['feetPosition'],origin)<=.025)
        return True
    def prepare(self):
        need(self.role=='primary')
        with self.serialized():
            owner=self.load()
            if owner is not None:self.runtime(owner);return owner
            need(self.retirement_store.read() is None and self.role_path('primary').read() is None and self.role_path('actor').read() is None and self.completed_store.read() is None)
            phase=self.source.read();need(phase['verb']=='baseline');binding=self.adapter.normal_feature_runtime(self.selector,read_only=True)[2]
            self.owner=dict(binding=deepcopy(context(binding)),phase='baseline',baseline=None,phaseSource=phase['status'],call=None,tickets=[],steps=[],intents=[],tabletLease=False,marker=None,markerHistory=[])
            frame,epoch=self.collect();self.neutral(frame,frame['world']['motion']['feetPosition'])
            need(not any(row['runId']==self.run for row in frame['world']['source']['gestures']) and not frame['pending']['commit'])
            self.owner['baseline']=frame;self.save_owner(self.owner);return deepcopy(self.owner)
    def release_marker(self):
        owned=self.owner['marker']
        if owned is None:return
        reader=self.adapter._navigation_marker(self.selector,read_only=True)
        if owned['original'] is not None:reader.restore([owned['original']])
        actual=reader.read(self.run);need(same(actual['source']['originalInput'],owned['request']))
        if actual['source']['phase']!='drained':
            request=input_command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-navigation-marker-input',operation='release',runId=self.run,fixtureInstance=actual['source']['fixtureInstance']))
            owned['release']=request;self.save_owner(self.owner);input_receipt(self.adapter._navigation_marker_input(self.selector,request),request)
        started=self.monotonic()
        for attempt in range(101):
            actual=reader.read(self.run)
            self.bound();need(self.monotonic()-started<10)
            try:marker_retired(actual);break
            except Exception:need(attempt<100);self.sleep(.1)
        web_reader=self.adapter._web_runtime_observer(self.selector,read_only=True)
        started=self.monotonic()
        for attempt in range(101):
            web=web_reader.read(self.run,self.fixture_url)
            self.bound();need(self.monotonic()-started<10)
            try:web_released(web);break
            except Exception:need(attempt<100);self.sleep(.1)
        self.owner['markerHistory'].append(dict(owner=deepcopy(owned),retired=actual,web=web));need(len(self.owner['markerHistory'])<=4)
        self.owner['marker']=None;self.save_owner(self.owner)
    def prepare_marker(self,ticket):
        self.release_marker()
        request=input_command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-navigation-marker-input',operation='prepare',runId=self.run,
            fixtureUrl=self.fixture_url,ticket=ticket,imageExtent=self.policy['imageExtent'],markerRoi=self.policy['markerRoi']))
        self.owner['marker']=dict(request=request,original=None,release=None);self.save_owner(self.owner)
        receipt=input_receipt(self.adapter._navigation_marker_input(self.selector,request),request)
        reader=self.adapter._navigation_marker(self.selector,read_only=True)
        started=self.monotonic()
        for attempt in range(81):
            marker=reader.read(self.run);avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read()
            self.bound();need(self.monotonic()-started<10)
            try:marker_ready(marker,avatar);break
            except Exception:need(attempt<80);self.sleep(.1)
        need(same(marker['source']['originalInput'],request) and marker['source']['fixtureInstance']==receipt['fixtureInstance'])
        self.owner['marker']['original']=marker;self.save_owner(self.owner)
    def act(self,call):
        call=deepcopy(arguments('feature.'+AREA+'.act',call));need(self.role=='primary' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url);self.prepare()
        with self.serialized():
            owner=self.load();self.runtime(owner);phase=self.source.read(owner['phaseSource'])
            need(phase['ticket']==call['ticket'] and phase['verb']==call['verb'] and same(phase['inputs'],call['inputs']))
            if call['ticket'] in owner['tickets']:
                need(owner['phase']=='active' and same(owner['call'],call));return {'performed':True}
            need(owner['phase'] in ('baseline','active'));owner.update(phase='acting',phaseSource=phase['status'],call=call);owner['tickets'].append(call['ticket']);self.save_owner(owner)
            # Marker teardown precedes the next normal input; holding a view is
            # forbidden here because it would suppress actual avatar drives.
            self.release_marker();LifecycleActions(self,owner).deliver(call)
            if call['verb'] in IMAGE_VERBS:self.prepare_marker(call['ticket'])
            owner['phase']='active';self.save_owner(owner);return {'performed':True}
    def capture(self,state,phase,last):
        if self.role!='primary' or phase['verb'] not in IMAGE_VERBS:return None,None,None,None
        owned=self.owner['marker'];need(owned is not None and owned['request']['ticket']==phase['ticket'] and 'holdView' not in owned['request'])
        reader=self.adapter._navigation_marker(self.selector,read_only=True);reader.restore([owned['original']]);marker=reader.read(self.run)
        need(same(marker['source']['originalInput'],owned['request']));marker_ready(marker,self.adapter._avatar_render_observer(self.selector,read_only=True).read())
        web=self.adapter._web_runtime_observer(self.selector,read_only=True).read(self.run,self.fixture_url)
        active_marker(web,self.fixture_url+'tickets/'+phase['ticket']+'/graphics-marker.v1.html')
        capture=self.adapter._world_render_capture(self.selector,read_only=True,role=self.role,require_trace=True,require_frame_view=True)
        packet,raw=capture.read(0);recorded=packet['source']['renderTrace']['recordedView'];wanted=marker['source']['originalView']
        need(all(near(recorded[key],wanted[key],.0001) for key in VIEW if key!='rotation') and rotation_equal(recorded['rotation'],wanted['rotation'],.0001))
        if last is not None and last['capture'] is not None:
            previous=last['capture'];need(packet['instance']==previous['instance'] and packet['sequence']>previous['sequence'] and packet['source']['acquisitionSequence']>previous['source']['acquisitionSequence']
                and packet['source']['renderTrace']['frameId']!=previous['source']['renderTrace']['frameId'])
        def intent(value):state['imageIntent']=deepcopy(value);self.save_role(state,self.role)
        images=NavigationImages(self.root,self.owner['binding'],self.run,self.role,state['sequence']+1,lambda:self.runtime(self.owner),intent,monotonic=self.monotonic)
        image=images.write(phase['ticket'],packet,raw);image_observation(raw,self.run,phase['ticket'],self.policy['imagePolicy']);release=capture.release()
        return image,packet,dict(marker=marker,web=web),release
    def archive_sample(self,state,phase,*,closed=False):
        evidence=LifecycleEvidence(self,state,self.role);evidence.recover();frames=evidence.frames();last=frames[-1] if frames else None
        if not frames:
            need(phase['verb']=='baseline');baseline,_=self.collect();self.neutral(baseline,baseline['world']['motion']['feetPosition'])
        else:baseline=frames[0]['sources']
        state['pending']=dict(frame=None);self.save_role(state,self.role)
        image,capture,marker,release=self.capture(state,phase,last)
        sources,epoch=self.collect(last['sources'] if last else None,after_epoch=math.ceil(phase['afterEpochMs']))
        facts,resources=measurement(self.run,sources,baseline,self.owner['intents'],baseline['world']['motion']['feetPosition'],pid=sources['editor']['processId'],epoch=epoch,after_epoch=math.ceil(phase['afterEpochMs']))
        if self.owner['marker'] is not None:resources.append('entity:lifecycle-marker')
        if phase['verb']=='cleanup':
            self.neutral(sources,baseline['world']['motion']['feetPosition']);need(not resources)
            window=state['quiet'];now=sources['editor']['capturedEpochMs'];position=sources['world']['motion']['feetPosition']
            if window is None:window=dict(ticket=phase['ticket'],firstEpochMs=now,firstMonotonic=self.monotonic(),position=position,samples=0,complete=False)
            need(window['ticket']==phase['ticket'] and math.dist(position,window['position'])<=.025);window['samples']+=1
            window['complete']=window['samples']>=3 and now-window['firstEpochMs']>=3000 and self.monotonic()-window['firstMonotonic']>=3;state['quiet']=window
            if closed:need(window['complete']);state['closed']=deepcopy(phase['status'])
            if self.role=='primary':
                actor=self.read(self.role_path('actor'),'actor')
                if not window['complete'] or actor is None or actor['quiet'] is None or not actor['quiet']['complete']:resources.append('input:lifecycle-retirement')
        frame=dict(ticket=phase['ticket'],phase=deepcopy(phase['status']),sources=sources,image=image,capture=capture,marker=marker,release=release)
        evidence.append(frame)
        if closed:raise PhaseRetired(phase['status'])
        # A phase bracket is source metadata only; crossing it cannot label an
        # old source acquisition as a new stimulus's observed result.
        after=self.source.read(phase['status']);need(after['ticket']==phase['ticket'])
        artifacts=[] if image is None else [dict(kind='image',source='world-render-target',name=image['name'],sequence=state['sequence'],capturedEpochMs=capture['capturedEpochMs'],ticket=phase['ticket'])]
        return result('feature.'+AREA+'.observe',dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=state['sequence'],capturedEpochMs=sources['editor']['capturedEpochMs'],state=facts,artifacts=artifacts,resources=resources,lifecycle=sources['native']['lifecycle']))
    def observe(self,call):
        call=arguments('feature.'+AREA+'.observe',call);need(call['runId']==self.run)
        if self.role=='primary':self.prepare()
        with self.serialized():
            owner=self.load()
            if owner is None or owner['phase'] in ('acting','cleaning'):raise PhasePending('Original lifecycle input is not complete')
            self.runtime(owner);state=self.role_state();need(call['afterSequence']<=state['sequence'])
            try:phase=self.source.read(owner['phaseSource'])
            except PhaseRetired as error:
                need(self.role=='actor' and owner['phase']=='cleaned' and state['quiet'] is not None and state['quiet']['complete'])
                status=error.status;last=status['activations'][-1];need(last['stimulus']==dict(verb='cleanup',inputs={}))
                phase=dict(ticket=last['ticket'],verb='cleanup',inputs={},afterEpochMs=status['retiredEpochMs'],status=status)
                return self.archive_sample(state,phase,closed=True)
            if phase['verb']=='cleanup':
                if owner['phase']!='cleaned':raise PhasePending('Owned lifecycle cleanup is not complete')
            elif phase['verb']!='baseline' and (owner['call'] is None or owner['call']['ticket']!=phase['ticket']):raise PhasePending('Original input awaits its owned stimulus')
            return self.archive_sample(state,phase)
    def publish(self):
        need(self.role=='actor');value=self.observe(dict(contractVersion=CONTRACT_VERSION,runId=self.run,afterSequence=0))
        with self.serialized():
            self.load();state=self.role_state();frame=LifecycleEvidence(self,state,self.role).frames()[-1];need(state['sequence']==value['sequence'])
        try:self.source.client.request('/runs/'+self.run+'/samples',dict(ticket=frame['ticket'],actor='owned-observer',actorSequence=value['sequence'],capturedEpochMs=value['capturedEpochMs'],facts=projection(AREA,value['state'])))
        except ValueError:
            if self.source.read()['ticket']!=frame['ticket']:raise PhasePending('Independent lifecycle publication crossed its phase') from None
            raise
        return value
    def cleanup(self,call):
        arguments('feature.'+AREA+'.cleanup',call);need(self.role=='primary' and call['runId']==self.run)
        with self.serialized():
            owner=self.load();need(owner is not None);self.runtime(owner);phase=self.source.read(owner['phaseSource']);need(phase['verb']=='cleanup')
            if owner['phase']=='cleaned':need(owner['phaseSource']['activations'][-1]['ticket']==phase['ticket']);return {'performed':True}
            owner.update(phase='cleaning',phaseSource=phase['status'],call=None);self.save_owner(owner)
            for role in ('primary','actor'):
                state=self.read(self.role_path(role),role)
                if state is not None:LifecycleEvidence(self,state,role).recover()
                if self.adapter.world_render_store(self.selector,role=role).read() is not None:self.adapter._world_render_capture(self.selector,read_only=True,role=role).release()
            self.release_marker();actions=LifecycleActions(self,owner);actions.release_world()
            pending=actions.pending(control=True);actual=pending.read(self.run)
            if actual['commit'] and actual['commit']['observation']['pending']:pending.release_owned(self.run,actual['commit']['observation']['eventId'])
            actions.close();actions.sdk()[0].release_actions()
            sources,_epoch=self.collect();origin=owner['baseline']['world']['motion']['feetPosition']
            if math.dist(sources['world']['motion']['feetPosition'],origin)>.025:actions.restore()
            sources,_epoch=self.collect();self.neutral(sources,origin);owner['phase']='cleaned';self.save_owner(owner);return {'performed':True}
    def fresh_retired(self,owner,status,previous):
        self.runtime(owner);closed=self.source.status(status);need(not closed['active'])
        sources,epoch=self.collect(previous);self.neutral(sources,owner['baseline']['world']['motion']['feetPosition'])
        need(not any(row['active'] for row in sources['editor']['source']['contexts']) and not sources['pending']['resources']['pendingRuns'])
        if owner['markerHistory']:
            old=owner['markerHistory'][-1]
            reader=self.adapter._navigation_marker(self.selector,read_only=True);reader.restore([old['retired']]);actual=reader.read(self.run)
            # The singleton retains the latest exact original fixture. Earlier
            # fixtures must remain disjoint and independently drained in Web's
            # complete native/Java inventory, rather than being re-adopted.
            need(actual['source']['fixtureInstance']==old['retired']['source']['fixtureInstance']);marker_retired(actual)
        if owner['markerHistory']:
            web_released(self.adapter._web_runtime_observer(self.selector,read_only=True).read(self.run,self.fixture_url))
        need(all(self.adapter.world_render_store(self.selector,role=role).read() is None for role in ('primary','actor')))
        return dict(status=closed,sources=sources,capturedEpochMs=epoch)
    def finalize(self):
        need(self.role=='primary')
        for attempt in range(101):
            with self.serialized():
                owner=self.load();plan=self.read(self.retirement_store,'retirement');completed=self.read(self.completed_store,'completed')
                retained=plan or completed
                if owner is None:
                    need(retained is not None);self.owner=owner=retained['owner']
                need(owner['phase']=='cleaned' and owner['marker'] is None and not owner['tabletLease'])
                status=self.source.status(owner['phaseSource']);need(not status['active'] and status['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
                if retained is None:
                    roles={role:self.read(self.role_path(role),role) for role in ('primary','actor')}
                    if any(value is None or value['quiet'] is None or not value['quiet']['complete'] for value in roles.values()) or roles['actor']['closed'] is None:
                        need(attempt<100);ready=False
                    else:
                        need(not roles['actor']['closed']['active']);ready=True
                        for role,state in roles.items():LifecycleEvidence(self,state,role).verify()
                        retained=dict(owner=deepcopy(owner),roles=roles,status=status,proof=None);self.save(self.retirement_store,'retirement',retained)
                else:
                    ready=True;need(same(owner,retained['owner']))
                    for role,state in retained['roles'].items():
                        need(state['quiet'] is not None and state['quiet']['complete'] and (role!='actor' or state['closed'] is not None and not state['closed']['active']))
                        LifecycleEvidence(self,state,role).verify()
                if ready:
                    # Every resume, even an already-pruned completed receipt,
                    # owes a NEW actual three-second original absence window.
                    started=self.monotonic();first=None;last=None;proof=[]
                    reference=LifecycleEvidence(self,retained['roles']['primary'],'primary').frames()[-1]['sources']
                    for index in range(41):
                        actual=self.fresh_retired(owner,status,last['sources'] if last is not None else reference);position=actual['sources']['world']['motion']['feetPosition']
                        source=actual['sources'];editor_advance(reference['editor'],source['editor']);world_advance(reference['world'],source['world'])
                        need(len(source['editor']['source']['contexts'])==len(reference['editor']['source']['contexts'])
                            and source['world']['source']['gestures']==reference['world']['source']['gestures']
                            and source['pending']['resources']==reference['pending']['resources'])
                        a,b=reference['pending']['commit'],source['pending']['commit'];need(bool(a)==bool(b))
                        if a:need(all(a[key]==b[key] for key in ('fieldToken','captureCommandId')) and a['observation']['events']==b['observation']['events'])
                        if first is None:first=actual
                        need(math.dist(position,first['sources']['world']['motion']['feetPosition'])<=.025)
                        if last is not None:editor_advance(last['sources']['editor'],actual['sources']['editor']);world_advance(last['sources']['world'],actual['sources']['world'])
                        proof=[first,actual];last=actual
                        if index>=2 and self.monotonic()-started>=3 and actual['capturedEpochMs']-first['capturedEpochMs']>=3000:break
                        need(index<40 and self.monotonic()-started<5);self.sleep(.1)
                    if completed is None:
                        retained['proof']=proof;self.save(self.completed_store,'completed',retained)
                    # A completed immutable receipt remains discoverable for
                    # strict idempotent cleanup after active journals retire.
                    index=self.completed_index.read();metadata=self.completed_store.read()
                    if index is not None and index.get('runId')!=self.run:
                        need(index.get('kind')=='completed' and index.get('lifecycleInputFeatureVersion')==VERSION)
                    if not same(index,metadata):self.completed_index.write(metadata,index)
                    for role in ('primary','actor'):
                        store=self.role_path(role);old=store.read()
                        if old is not None:need(same(self.read(store,role),retained['roles'][role]));store.discard(old)
                    if self.store.read() is not None:need(same(self.load(),owner));self.store.discard(self.previous[self.store.path])
                    old=self.retirement_store.read()
                    if old is not None:self.retirement_store.discard(old)
                    return True
            self.sleep(.1)
        need(False)
