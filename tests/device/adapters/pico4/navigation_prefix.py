"""Normal Origin/Places/bookmark opening prefix of unchanged Navigation v16.

The common Journey remains the sole recipe. This private parent composes its
first seven actions; no feature capability, final cleanup or image verdict is
published. Primary input and independently queried actor frames stay separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.chat_journey.source_chunks import ChatSourceChunks, json_digest
from adapters.android.input_geometry import observed_grip_pose
from adapters.native_feature_observation import exact, integer, need, number
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.navigation_directory import NavigationDirectory
from adapters.navigation_origin import NavigationOrigin
from adapters.navigation_arrival import pose_packet
from adapters.native_location_bookmarks import validate as bookmarks_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import NativeNavigationIO, identifier as ui_identifier
from adapters.pico4.navigation_prefix_source import NavigationPrefixSource
from adapters.script_journey.history import same
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_places_ui import TokenPlacesUI,control_id as places_control
from adapters.token_create_ui import scope as input_scope, nonce
from feature_journeys.contract import arguments, identifier
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.phase_fixture import PhaseFixtureReader, PhasePending, validate as phase_packet
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import validate_envelope

VERSION=2
AREA='world-navigation'
VERBS=tuple(row['verb'] for row in SCENARIOS[AREA]['steps'][:7])


def plan(run,index):
    row=SCENARIOS[AREA]['steps'][index]
    return dict(verb=row['verb'],inputs=expand(row['inputs'],context(run)))


def limit(value):return 5 if value['navigationPrefixVersion']==1 else 7


class NavigationPrefix:
    def __init__(self,path,source,phase,lock,origin,directory,bookmarks,session,*,role='primary',monotonic=time.monotonic):
        need(isinstance(source,NavigationPrefixSource) and isinstance(phase,PhaseFixtureReader) and phase.area==AREA
            and phase.run==source.run and isinstance(lock,ScriptSourceLock) and isinstance(origin,NavigationOrigin)
            and isinstance(directory,NavigationDirectory) and isinstance(bookmarks,NavigationBookmarks)
            and isinstance(session,PicoOpenXrAdapterSession) and callable(monotonic) and origin.home is not None
            and role in ('primary','actor'))
        self.store=PrivateFeatureState(path);self.source,self.phase,self.lock=source,phase,lock
        self.origin,self.directory,self.bookmarks=origin,directory,bookmarks
        self.run,self.binding=source.run,deepcopy(source.binding);self.monotonic=monotonic;self.clock=None
        self.role=role
        self.scope_sha=json_digest(self.scope());self.role_sha=json_digest(role)
        for child in (origin,directory,bookmarks):need(child.run==self.run and same(child.binding,self.binding))
        transport=source.normal.io.original.navigation.io
        need(isinstance(transport,NativeNavigationIO)
            and origin.io.original is source.normal.io.original
            and directory.ui.io.original is source.normal.io.original
            and bookmarks.ui.io.original is source.normal.io.original)
        self.transport=transport;self.before_send=self.admit_qml;transport.bind_before_send(self.before_send)
        self.session=session;self.home_anchor=None;self.home_anchor_sha=None
        self.home_intent_callback=self.home_intent;self.home_publish_callback=self.home_publish
        origin.home.stage=self.home_stage
        self.open_ui=TokenPlacesUI(source.normal.io,self.intent,self.run,monotonic=monotonic,sleep=source.normal.sleep)
        self.disk=self.store.read();self.state=None
        if self.disk is not None:self.load()

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.clock is None or value>=self.clock));self.clock=value;return value

    def scope(self):
        return dict(runId=self.run,binding=self.binding,sourceBinding=self.source.binding,inputs=self.source.inputs,
            providerInstance=self.source.provider_instance,origin=self.source.origin,profile=self.source.profile,
            fixtureUrl=self.phase.fixture_url,path=str(self.store.path),lockPath=str(self.lock.path))

    def control(self):
        need(json_digest(self.scope())==self.scope_sha and json_digest(self.role)==self.role_sha
            and self.phase.run==self.source.run==self.run and self.phase.area==AREA)

    def load(self):
        value=self.store.read()
        if value is None:need(self.disk is None);return
        self.validate(value);self.disk=deepcopy(value);self.state=deepcopy(value)

    def validate(self,value):
        self.control()
        exact(value,{'navigationPrefixVersion','scopeSha256','runId','binding','phase','fixture','completed','active','deliveries','receipt','home','preflight'})
        need(type(value['navigationPrefixVersion']) is int and value['navigationPrefixVersion'] in (1,VERSION)
            and value['runId']==self.run and same(value['binding'],self.binding)
            and value['scopeSha256']==self.scope_sha
            and value['phase'] in ('preparing','ready','acting') and type(value['completed']) is list
            and len(value['completed'])<=limit(value) and type(value['deliveries']) is list and len(value['deliveries'])<=128)
        for index,row in enumerate(value['completed']):
            exact(row,{'ticket','verb'});identifier(row['ticket']);need(row['verb']==VERBS[index])
        tickets=[row['ticket'] for row in value['completed']];need(len(set(tickets))==len(tickets))
        for command in value['deliveries']:
            exact(command,{'schemaVersion','commandId','bridgeId','generation','sequence','observedElapsedMs','controlId','controlToken','action'}
                |({'text'} if command.get('action')=='replace' else set()))
            need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and ui_identifier(command['commandId'])
                and ui_identifier(command['bridgeId']) and ui_identifier(command['generation']) and nonce(command['controlToken'])
                and integer(command['sequence'],1) and integer(command['observedElapsedMs'])
                and command['action'] in ('activate','replace','submit')
                and (command['controlId']=='login.server' or places_control(command['controlId'])))
            if command['action']=='replace':
                need(type(command['text']) is str and len(command['text'])<=4096 and all(32<=ord(c)<=126 for c in command['text']))
        need(len({row['commandId'] for row in value['deliveries']})==len(value['deliveries']))
        fixture=value['fixture'];phase_packet(fixture,run=self.run,area=AREA,request=fixture['requestId'],epoch=fixture['capturedEpochMs'])
        need(fixture['active'] and fixture['activations'])
        for index,row in enumerate(value['completed']):
            original=[entry for entry in fixture['activations'] if entry['ticket']==row['ticket']]
            need(len(original)==1 and same(original[0]['stimulus'],plan(self.run,index)))
        active=value['active']
        if active is None:need(value['phase']!='acting')
        else:
            exact(active,{'ticket','verb','stage','pending','history'})
            need(value['phase']=='acting' and len(value['completed'])<limit(value)
                and active['verb']==VERBS[len(value['completed'])] and active['ticket']==fixture['activations'][-1]['ticket']
                and same(fixture['activations'][-1]['stimulus'],plan(self.run,len(value['completed'])))
                and active['stage'] in (('open','directory','sample') if active['verb']=='open' else
                    ('directory','sample') if active['verb']=='directory-search' else ('bookmark','tab','sample'))
                and type(active['history']) is list and len(active['history'])<=32)
            for pending in active['history']+([] if active['pending'] is None else [active['pending']]):
                exact(pending,{'placesInputVersion','action','controlId','controlToken','scope'});input_scope(pending['scope'])
                need(type(pending['placesInputVersion']) is int and pending['placesInputVersion']==1
                    and pending['action']=='activate' and nonce(pending['controlToken'])
                    and pending['scope']['instance']==self.binding['sessionId']
                    and pending['scope']['processId']==int(self.binding['processIdentity'].split(':',1)[0]))
        home=value['home']
        if home is not None:
            exact(home,{'envelope','sha256','anchor'});envelope=home['envelope'];validate_envelope(envelope,self.session.profile)
            need(json_digest(envelope)==home['sha256'] and type(envelope['sequence']) is int
                and type(envelope['schemaVersion']) is int and len(envelope['commands'])==1
                and envelope['commands'][0]['operation']=='input.primary')
            anchor=home['anchor'];exact(anchor,{'hostMonotonic','nativeEpochMs','fixtureEpochMs','pose'})
            need(number(anchor['hostMonotonic'],0,1e15) and number(anchor['nativeEpochMs'],1,1e15)
                and number(anchor['fixtureEpochMs'],1,1e15) and -250<=anchor['nativeEpochMs']-anchor['fixtureEpochMs']<=1500
                and same(anchor['pose'],envelope['commands'][0]['arguments'])
                and self.origin.state is not None and self.origin.state['homeMode']=='ray')
            before=self.origin.state['operation']['homeBefore']['observation']
            need(same(anchor['pose'],observed_grip_pose(before['sensorToWorld'],before['headPosition'],before['position'])))
        preflight=value['preflight'];exact(preflight,{'pose','bookmarks'})
        need(pose_packet(preflight['pose'],self.run,self.binding,self.source.inputs['sceneUrl'],
            preflight['pose']['subject']['capturedEpochMs'])=='A')
        packet=preflight['bookmarks'];bookmarks_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],
            action='feature-location-bookmarks',runId=self.run),int(self.binding['processIdentity'].split(':',1)[0]),packet['capturedEpochMs'])
        need(not packet['storage']['owned'])

    def save(self,value):
        self.lock.assert_held();self.validate(value);self.store.write(value,self.disk);self.disk=deepcopy(value);self.state=deepcopy(value)

    def fence(self):
        """Actual guards first, exact fresh fixture phase last, then clocks only."""
        self.lock.assert_held();self.control();need(same(self.state,self.disk) and same(self.store.read(),self.disk))
        started=self.now();need(self.source.guard() is not False)
        current=self.phase.read()
        need(self.state is not None and same(current['status']['activations'],self.state['fixture']['activations'])
            and current['status']['instance']==self.state['fixture']['instance'])
        native=self.source.clock_ms();completed=self.now();captured=current['status']['capturedEpochMs']
        need(number(native,1,1e15) and max(native-captured,(completed-started)*1000)<=1500)
        return current

    def home_stage(self,pose):
        self.lock.assert_held();need(self.state['phase']=='preparing' and self.state['home'] is None)
        original=self.origin.state['operation']['homeBefore']['observation']
        need(same(pose,observed_grip_pose(original['sensorToWorld'],original['headPosition'],original['position'])))
        # Preserve the original candidate/process/foreground admission before
        # reading the exact phase. The locked callbacks below are host-only.
        self.transport.bind_input()
        need(self.transport.adapter.require_pico_session_identity(self.transport.target)==self.binding['processIdentity'])
        current=self.fence();self.home_anchor=dict(hostMonotonic=self.now(),nativeEpochMs=self.source.clock_ms(),
            fixtureEpochMs=current['status']['capturedEpochMs'],pose=deepcopy(pose))
        self.home_anchor_sha=json_digest(self.home_anchor)
        self.session.stage(self.binding['processIdentity'],'input.primary',pose,
            intent=self.home_intent_callback,before_publish=self.home_publish_callback)

    def home_age(self):
        self.control();need(same(self.state,self.disk))
        need(self.home_anchor is not None and json_digest(self.home_anchor)==self.home_anchor_sha)
        now=self.now();anchor=self.home_anchor
        need(now>=anchor['hostMonotonic'] and max(anchor['nativeEpochMs']-anchor['fixtureEpochMs'],0)
            +(now-anchor['hostMonotonic'])*1000<=1500)

    def home_intent(self,envelope):
        self.lock.assert_held();self.home_age();need(self.state['phase']=='preparing' and self.state['home'] is None)
        state=deepcopy(self.state);state['home']=dict(envelope=deepcopy(envelope),sha256=json_digest(envelope),anchor=deepcopy(self.home_anchor));self.save(state)
        self.home_publish(envelope)

    def home_publish(self,envelope):
        self.lock.assert_held();self.home_age();original=self.state['home']
        need(original is not None and same(original['anchor'],self.home_anchor)
            and json_digest(envelope)==original['sha256'] and same(original['envelope'],envelope))

    def intent(self,value):
        self.lock.assert_held();need(self.state is not None and self.state['phase']=='acting'
            and self.state['active']['stage'] in ('open','tab'))
        state=deepcopy(self.state);pending=state['active']['pending']
        if pending is not None:
            # Warm ordinary paging may need several distinct controls. The
            # fresh next reference establishes input consumption only; final
            # original Places data establishes the actual resulting page.
            need(value['scope']['instance']==pending['scope']['instance']
                and value['scope']['processId']==pending['scope']['processId']
                and value['scope']['sequence']==pending['scope']['sequence']+1)
            state['active']['history'].append(pending);need(len(state['active']['history'])<=32)
        state['active']['pending']=deepcopy(value);self.save(state)

    def admit_qml(self,command):
        self.lock.assert_held();need(self.state is not None and self.state['phase'] in ('preparing','acting'))
        active=self.state['active'];need(type(command) is dict)
        if self.state['phase']=='preparing':
            need(command['controlId']=='login.server' and command['action'] in ('activate','replace','submit'))
            pending=self.origin.state['operation']['pending'];scope=pending['scope'];token=pending['token']
            need(command['controlId']==pending['control'] and command['action']==pending['action'])
            if command['action']=='replace':need(command['text']==self.origin.desired())
        else:
            stage=active['stage']
            pending=(self.directory.state['active']['pending'] if stage=='directory' else
                self.bookmarks.state['active']['pending'] if stage=='bookmark' else active['pending'])
            need(pending is not None and command['controlId']==pending['controlId'] and command['action']==pending['action'])
            scope=pending['scope'];token=pending['controlToken']
        need(command['controlToken']==token and command['bridgeId']==scope['instance']
            and command['generation']==scope['generation'] and command['sequence']==scope['sequence']+1
            and command['observedElapsedMs']==scope['elapsedMs'])
        state=deepcopy(self.state);state['deliveries'].append(deepcopy(command));need(len(state['deliveries'])<=128);self.save(state)
        # The durable parent command is an input intent, never an effect fact.
        # Nothing with source/SDK/native/HTTP side effects follows this fence.
        self.fence()

    def prepare(self):
        need(self.role=='primary')
        with self.lock.held():
            self.load()
            if self.state is None:
                current=self.phase.read();need(current['verb']=='baseline')
                need(self.origin.state is None and self.directory.state is None and self.bookmarks.state is None)
                pose=self.source.arrival.read();need(pose_packet(pose,self.run,self.binding,self.source.inputs['sceneUrl'],self.source.clock_ms())=='A')
                bookmarks=self.source.readers['bookmarks'].read(self.run);need(not bookmarks['storage']['owned'])
                self.save(dict(navigationPrefixVersion=VERSION,scopeSha256=self.scope_sha,runId=self.run,binding=deepcopy(self.binding),phase='preparing',
                    fixture=deepcopy(current['status']),completed=[],active=None,deliveries=[],receipt=None,home=None,
                    preflight=dict(pose=pose,bookmarks=bookmarks)))
            need(not self.state['completed'])
            if self.state['phase']=='preparing':
                # Origin's own original geometry and one-send journal remain
                # authoritative, including the actual normal Home ray.
                self.origin.select(self.state['fixture']['activations'][-1]['ticket'],self.source.origin)
                state=deepcopy(self.state);state['phase']='ready';self.save(state)
            self.fence()

    def pending_effect(self):
        active=self.state['active'];pending=active['pending']
        if pending is None:return
        value=self.open_ui.capture();scope=pending['scope']
        need(value['scope']['instance']==scope['instance'] and value['scope']['processId']==scope['processId']
            and value['scope']['sequence']==scope['sequence']+1)
        control=pending['controlId'];page=self.open_ui.row(value,'places.page',enabled=False)
        if control=='places.entry':need(page is not None)
        elif control=='places.tab.0':need(page is not None and page['tab']==0)
        else:
            # Unknown/lost Home or paging effects cannot be acknowledged into
            # success or repeated. Their original command remains owned.
            need(False)
        state=deepcopy(self.state);state['active']['history'].append(pending);need(len(state['active']['history'])<=32)
        state['active']['pending']=None;self.save(state)

    def stage(self,name):
        state=deepcopy(self.state);need(state['active']['pending'] is None);state['active']['stage']=name;self.save(state);self.fence()

    def act(self,call):
        call=deepcopy(arguments('feature.'+AREA+'.act',call));need(self.role=='primary' and call['runId']==self.run and call['fixtureUrl']==self.phase.fixture_url)
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']!='preparing')
            if any(row['ticket']==call['ticket'] for row in self.state['completed']):
                need(self.state['completed'][-1]==dict(ticket=call['ticket'],verb=call['verb'])
                    and same(dict(verb=call['verb'],inputs=call['inputs']),plan(self.run,len(self.state['completed'])-1)))
                self.fence();return dict(performed=True)
            active=self.state['active']
            if active is None:
                index=len(self.state['completed']);need(index<limit(self.state)
                    and same(dict(verb=call['verb'],inputs=call['inputs']),plan(self.run,index)))
                current=self.phase.read();need(current['ticket']==call['ticket'] and current['verb']==call['verb'] and same(current['inputs'],call['inputs']))
                state=deepcopy(self.state);state.update(phase='acting',fixture=deepcopy(current['status']),
                    active=dict(ticket=call['ticket'],verb=call['verb'],stage='open' if index==0 else
                        'directory' if call['verb']=='directory-search' else 'bookmark',pending=None,history=[]));self.save(state)
            need(self.state['active']['ticket']==call['ticket'] and self.state['active']['verb']==call['verb']);self.fence()
            if call['verb']=='open':
                if self.state['active']['stage']=='open':
                    self.pending_effect();self.open_ui.open();self.pending_effect();self.stage('directory')
                if self.state['active']['stage']=='directory':
                    self.directory.act(call['ticket'],'refresh');state=deepcopy(self.state)
                    state['receipt']=dict(ticket=call['ticket'],afterEpochMs=self.directory.state['afterEpochMs']);self.save(state);self.stage('sample')
            elif call['verb']=='directory-search':
                self.directory.act(call['ticket'],'hidden' if call['inputs']['query']==context(self.run)['hidden'] else 'owned')
                self.stage('sample')
            else:
                if self.state['active']['stage']=='bookmark':
                    self.bookmarks.act(call['ticket'],call['verb']);self.stage('tab')
                if self.state['active']['stage']=='tab':
                    self.pending_effect();self.open_ui.tab(0);self.pending_effect();self.stage('sample')
            need(self.state['active']['stage']=='sample');state=deepcopy(self.state)
            state['completed'].append(dict(ticket=call['ticket'],verb=call['verb']));state.update(phase='ready',active=None);self.save(state);self.fence()
            return dict(performed=True)

    def observe(self):
        role=self.role
        with self.lock.held():
            self.load()
            if self.state is None or self.state['phase']!='ready':raise PhasePending('Normal Navigation prefix input is incomplete')
            current=self.fence()
            if current['verb']!='baseline':need(self.state['completed'] and self.state['completed'][-1]['ticket']==current['ticket'])
            store=PrivateFeatureState(self.store.path.with_name('navigation-prefix-'+role+'-sources.json'))
            chunks=ChatSourceChunks(store,dict(runId=self.run,binding=self.binding,role=role));old=store.read()
            manifest=[] if old is None else old['chunks'];frames=chunks.load(manifest)
            if old is not None:
                exact(old,{'navigationPrefixSamplesVersion','runId','binding','role','phase','chunks'})
                need(old['navigationPrefixSamplesVersion']==1 and type(old['navigationPrefixSamplesVersion']) is int
                    and old['runId']==self.run and same(old['binding'],self.binding) and old['role']==role)
                if old['phase']!='ready':raise PhasePending('An original Navigation query remains unresolved')
            for index,frame in enumerate(frames):
                self.source.project(frame);self.original_facts(frame)
                if index:self.source.advance_frames(frames[index-1],frame)
            reading=dict(navigationPrefixSamplesVersion=1,runId=self.run,binding=deepcopy(self.binding),role=role,phase='reading',chunks=manifest)
            store.write(reading,old);current=self.fence();started=self.now();frame=self.source.capture(self.state['receipt'],current['status'])
            # Preserve a complete actual bracket before refusing disagreement.
            # A failed projection leaves its original chunk plus reading intent;
            # no actor may turn that unresolved acquisition into an old sample.
            manifest=chunks.append(frame,manifest);actual=self.source.project(frame);self.original_facts(frame)
            if frames:self.source.advance_frames(frames[-1],frame)
            result=dict(sequence=len(manifest),capturedEpochMs=frame['before']['ui']['observedEpochMs'],state=actual,
                fullNavigationRecipe=False,deviceAcceptance=False,journalsRetained=True)
            ready=deepcopy(reading);ready.update(phase='ready',chunks=manifest);store.write(ready,reading)
            chunks.verify();self.fence();epoch=self.source.clock_ms()
            need(number(epoch,1,1e15) and max(epoch-result['capturedEpochMs'],(self.now()-started)*1000)<=1500)
            return result

    def original_facts(self,frame):
        original=self.state['preflight']['bookmarks']['storage']
        for side in ('before','after'):
            storage=frame[side]['bookmarks']['storage']
            need(all(storage[key]==original[key] for key in ('unownedCount','unownedSha256'))
                and frame[side]['environment']['otherSettingsSha256']==self.origin.state['original']['otherSettingsSha256'])
