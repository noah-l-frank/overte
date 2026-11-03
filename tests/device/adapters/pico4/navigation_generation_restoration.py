"""One typed cleanup phase: old original directory via normal G1 Login input.

This continues the same fifteen-action owner. It never changes the completed
G0/G1 journals, scene, camera or rating preferences, and does not publish a
whole-feature capability or retire the remaining source/Host obligations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os

from adapters.android.input_geometry import observed_grip_pose
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,fresh,need,number
from adapters.native_navigation_environment import continuation,logged_out,validate as environment_packet
from adapters.native_location_bookmarks import validate as bookmarks_packet
from adapters.native_navigation_panels import validate as panels_packet
from adapters.native_navigation_modals import validate as modals_packet
from adapters.navigation_arrival import pose_packet,advance as pose_advance
from adapters.navigation_origin import NavigationOrigin
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import normal_scripts
from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
from adapters.pico4.navigation_originals import read_original,verify_archive
from adapters.pico4.navigation_origin_restart import NavigationOriginRestart
from adapters.pico4.normal_login import PicoLoginIO
from adapters.pico4.normal_navigation_origin import PicoNavigationOriginIO
from adapters.pico4.tablet_home import bind_home
from adapters.pico4.tablet_home import validate as home_packet
from adapters.pico4.graphics_source import validate as graphics_packet,accept_inventory,PROFILES
from adapters.script_journey.history import same,pack,unpack
from adapters.token_login_ui import TokenLoginUI
from openxr_input.controller_protocol import validate_envelope
from feature_journeys.contract import arguments

VERSION=1
PHASES=('admission','opening','entry','origin','closing','quiet','complete')


class NavigationGenerationRestoration:
    def __init__(self,flow,adapter,target):
        from adapters.pico4.navigation_generation_flow import NavigationGenerationFlow
        need(isinstance(flow,NavigationGenerationFlow) and flow.parent.role=='primary')
        self.flow,self.adapter,self.target=flow,adapter,target;self.lock=flow.lock;self.run=flow.run;self.binding=deepcopy(flow.binding)
        self.lock.assert_held()
        self.store=PrivateFeatureState(self.lock.path.with_name('navigation-prefix-generation-1-restoration.json'))
        self.origin_path=self.store.path.with_name('navigation-prefix-generation-1-restoration-origin.json')
        self.ui_path=self.store.path.with_name('navigation-prefix-generation-1-restoration-ui.json')
        self.scope_sha=json_digest(self.scope());self.disk=self.store.read();self.state=None;self.physical=None
        self.runtime=None;self.origin=None;self.anchor=None;self.anchor_sha=None;self.kind=None
        self.authority=NavigationOriginRestart(self)
        self.qml_callback=self.before_send;self.controller_callback=self.before_controller
        self.intent_callback=self.controller_intent;self.publish_callback=self.before_publish
        if self.disk is not None:
            exact(self.disk,{'navigationGenerationRestorationVersion','scope','payload'})
            need(type(self.disk['navigationGenerationRestorationVersion']) is int and self.disk['navigationGenerationRestorationVersion']==VERSION
                and same(self.disk['scope'],self.scope()))
            rows=unpack(self.disk['payload']);need(len(rows)==1);self.state=rows[0];self.validate(self.state)
            self.physical=read_original(self.store.path)

    def scope(self):
        return dict(runId=self.run,binding=self.binding,parentScope=self.flow.scope(),parentSha256=json_digest(self.flow.disk),
            path=str(self.store.path),originPath=str(self.origin_path),uiPath=str(self.ui_path),sourceLock=str(self.lock.path))

    def now(self):
        value=self.flow.parent.now();need(number(value,0,1e15));return value

    def host(self):
        self.lock.assert_held();self.flow.control();self.flow.validate_links(self.flow.state)
        need(self.scope_sha==json_digest(self.scope()) and self.flow.state['phase']=='ready'
            and [row['verb'] for row in self.flow.state['completed']]==['open','bookmark-delete','close'])
        if self.state is not None:
            need(same(self.store.read(),self.disk) and same(unpack(self.disk['payload']),[self.state]))
            if self.physical is not None:need(same(read_original(self.store.path),self.physical))
        if self.origin is not None:self.origin.require_physical()

    def live(self):
        if self.runtime is not None:return self.runtime
        self.host();a=self.adapter;t=self.target;installed=a._installation(t);identity=a.require_controlled_debug_identity(t)
        need(identity==self.binding['processIdentity']==a.require_pico_session_identity(t)
            and all(installed[k]==self.binding[k] for k in ('sourceRevision','artifactSha256'))
            and hashlib.sha256((t+'\0'+str(a.pico_configuration)).encode()).hexdigest()==self.binding['targetFingerprint'])
        scene=normal_scripts.configuration(os.environ);need(scene==self.flow.parent.source.inputs['sceneUrl'])
        normal,_observe,binding=normal_scripts.runtime(a,t,scene,installed,identity,self.ui_path,lambda *_args:need(False))
        need(same(binding,self.binding));native=a._native_feature_observer(t)
        normal.io.navigation.io.bind_before_send(self.qml_callback)
        normal.io.navigation.io.bind_controller_admission(self.controller_callback,intent=self.intent_callback,before_publish=self.publish_callback)
        home=bind_home(a,t,native);home.stage=self.home_stage
        runtime=dict(normal=normal,native=native,environment=a._navigation_environment(t),presence=a._process_presence(t),
            home=home,graphics=a._graphics_ui_observer(t),session=a.pico_input_session(t),installed=deepcopy(installed))
        runtime.update(bookmarks=a._location_bookmarks(t),panels=a._navigation_panels(t),modals=a._navigation_modals(t))
        # This callback owns one fresh reader instance. A reused reader could
        # otherwise retain a previous owner's archive writer after recovery.
        environment=runtime['environment'];need(not hasattr(environment,'_pico_navigation_restoration_owner'))
        environment._pico_navigation_restoration_owner=self
        original=environment.original;native_guard=environment.guard
        def environment_original():
            raw=original();need(type(raw) is str and len(raw.encode())<=262144)
            # Preserve the original transport bytes BEFORE native parsing.
            value=deepcopy(self.state);value['nativeOriginals'].append(dict(phase=value['phase'],raw=raw,hostMonotonic=self.now()))
            self.save(value,host_only=True);return raw
        def environment_guard():
            need(environment.original is environment_original and environment._pico_navigation_restoration_owner is self)
            return native_guard()
        environment.original=environment_original;environment.guard=environment_guard
        self.runtime=runtime;return self.runtime

    def guard(self):
        self.host();runtime=self.live();a=self.adapter;t=self.target
        need(runtime['native'].guard() is not False and a.require_controlled_debug_identity(t)==self.binding['processIdentity']
            and a.require_pico_session_identity(t)==self.binding['processIdentity'] and a._installation(t)==runtime['installed'])
        phase=self.flow.parent.phase.read();need(phase['verb']=='cleanup' and phase['inputs']=={}
            and phase['ticket']==self.state['ticket'] and same(phase['status']['activations'],self.state['fixture']['activations']))
        fresh(phase['status']['capturedEpochMs'],runtime['native'].clock_ms())
        if self.state['reference'] is not None:
            with runtime['session']._lock():session=runtime['session']._load()
            before=self.authority.read(self.state['reference'])['session']
            need(session is not None and session['processIdentity']==before['processIdentity']
                and session['sessionNonce']==before['sessionNonce'] and session['nextSequence']==before['nextSequence']+len(self.state['controllers']))
        return phase

    def validate(self,value):
        exact(value,{'phase','ticket','fixture','reference','entry','qml','controllers','originSha256','quiet','nativeOriginals','acquisitions'})
        need(value['phase'] in PHASES and type(value['qml']) is list and len(value['qml'])<=8
            and type(value['controllers']) is list and len(value['controllers'])<=3
            and type(value['quiet']) is list and len(value['quiet'])<=8
            and type(value['nativeOriginals']) is list and len(value['nativeOriginals'])<=1024
            and type(value['acquisitions']) is list and len(value['acquisitions'])<=8)
        for row in value['nativeOriginals']:
            exact(row,{'phase','raw','hostMonotonic'});need(row['phase'] in PHASES and type(row['raw']) is str
                and len(row['raw'].encode())<=262144 and number(row['hostMonotonic'],0,1e15))
        for row in value['acquisitions']:
            exact(row,{'phase','packets'});need(row['phase'] in ('reading','complete') and type(row['packets']) is dict
                and set(row['packets'])<={'environment','home','graphicsBefore','pose','bookmarks','panels','modals','graphics'})
        need((value['reference'] is None)==(value['phase']=='admission'))
        count=len(value['controllers']);need(count in ((0,) if value['phase']=='admission' else (0,1) if value['phase']=='opening'
            else (1,) if value['phase']=='entry' else (1,2) if value['phase']=='origin' else (2,3) if value['phase']=='closing' else (3,)))
        profile=self.flow.restart.state['profile'];base=self.flow.restart.state['newSession']['nextSequence']+len(self.flow.state['controllers'])
        for index,row in enumerate(value['controllers']):
            exact(row,{'kind','envelope','anchor','statuses'});need(row['kind']==('opening','home','closing')[index])
            validate_envelope(row['envelope'],profile);envelope=row['envelope']
            need(envelope['sessionNonce']==self.flow.restart.state['newSession']['sessionNonce'] and envelope['sequence']==base+index
                and len(envelope['commands'])==1 and envelope['commands'][0]['operation']==('tablet.open','input.primary','tablet.close')[index])
            exact(row['anchor'],{'hostMonotonic','nativeEpochMs','fixtureEpochMs'})
            need(all(number(row['anchor'][k],0 if k=='hostMonotonic' else 1,1e15) for k in row['anchor'])
                and type(row['statuses']) is list and len(row['statuses'])<=81)
            for status in row['statuses']:
                exact(status,{'status','hostMonotonic'});need(number(status['hostMonotonic'],0,1e15))
        ids=set()
        for row in value['qml']:
            exact(row,{'command','pending'});command,pending=row['command'],row['pending']
            need(command['commandId'] not in ids and command['bridgeId']==self.binding['sessionId']);ids.add(command['commandId'])
            need(command['controlId']==pending['control'] and command['controlToken']==pending['token']
                and command['action']==pending['action'] and command['sequence']==pending['scope']['sequence']+1
                and command['generation']==pending['scope']['generation'])
        need((value['originSha256'] is not None)==(value['phase'] in ('closing','quiet','complete')))
        previous=None
        for row in value['quiet']:
            self.archive_quiet(row,previous);previous=row
        if value['phase']=='complete':
            need(len(value['quiet'])>=3)
            first,last=value['quiet'][0],value['quiet'][-1]
            need(last['environment']['capturedEpochMs']-first['environment']['capturedEpochMs']>=3000
                and last['hostMonotonic']-first['hostMonotonic']>=3)

    def archive_quiet(self,row,previous=None):
        exact(row,{'environment','home','graphicsBefore','graphics','pose','bookmarks','panels','modals','hostMonotonic','sourceAnchor','statusIndex'})
        epoch=row['graphics']['capturedEpochMs'];pid=int(self.binding['processIdentity'].split(':',1)[0])
        environment=row['environment'];environment_packet(environment,dict(schemaVersion=1,commandId=environment['commandId'],
            action='feature-navigation-environment',runId=self.run),pid,epoch);logged_out(environment)
        old=self.authority.read(self.state['reference'])['oldOriginal']
        need(environment['navigationEnvironmentVersion']==2 and environment['selectedSettingPresent']
            and environment['settings']['selectedType']==old['settings']['selectedType']=='string'
            and environment['settings']['rawSettingsSha256']==old['settings']['rawSettingsSha256']
            and environment['otherSettingsSha256']==old['otherSettingsSha256']
            and environment['selectedServer']==environment['effectiveServer']==old['selectedServer']
            and not environment['ui']['loginPageAlive'] and not environment['ui']['open'] and not environment['ui']['ready'])
        home_packet(row['home'],row['home']['commandId'],pid,epoch);graphics_packet(row['graphics'],row['graphics']['commandId'],pid,epoch)
        graphics_packet(row['graphicsBefore'],row['graphicsBefore']['commandId'],pid,epoch)
        accept_inventory(row['graphicsBefore']['graphicsInventory'],row['graphics']['graphicsInventory'],profiles=PROFILES)
        need(not row['home']['tabletShown'] and row['home']['onHomeScreen'] and not row['graphics']['tabletShown']
            and not row['graphics']['editorFocused'] and not row['graphics']['graphicsInventory']['keyboard3D']['raised']
            and not row['graphics']['graphicsInventory']['roots'])
        for key,action,validator in (('bookmarks','feature-location-bookmarks',bookmarks_packet),('panels','feature-navigation-panels',panels_packet),
                ('modals','feature-navigation-modals',modals_packet)):
            packet=row[key];validator(packet,dict(schemaVersion=1,commandId=packet['commandId'],action=action,runId=self.run),pid,epoch)
        original=self.flow.parent.state['preflight'];storage=row['bookmarks']['storage']
        need(not storage['owned'] and all(storage[k]==original['bookmarks']['storage'][k] for k in ('unownedCount','unownedSha256'))
            and not any(root['alive'] or root['inCurrentTree'] for root in row['panels']['roots'])
            and not any(record['rootAlive'] or record['listenerAlive'] for record in row['modals']['records']))
        scene=self.flow.parent.source.inputs['sceneUrl']
        label=pose_packet(original['pose'],self.run,self.flow.parent.binding,scene,original['pose']['subject']['capturedEpochMs'])
        need(pose_packet(row['pose'],self.run,self.binding,scene,epoch)==label)
        exact(row['sourceAnchor'],{'hostMonotonic','nativeEpochMs'})
        need(number(row['hostMonotonic'],0,1e15) and number(row['sourceAnchor']['hostMonotonic'],0,row['hostMonotonic'])
            and number(row['sourceAnchor']['nativeEpochMs'],1,epoch))
        closing=self.state['controllers'][-1];need(type(row['statusIndex']) is int and 0<=row['statusIndex']<len(closing['statuses'])
            and closing['kind']=='closing' and NavigationBookmarkJoin.neutral(closing['statuses'][row['statusIndex']]['status'],closing['envelope']))
        if previous is not None:
            continuation(previous['environment'],environment);NavigationOrigin.quiet_continuation(previous['environment'],environment)
            pose_advance(previous['pose'],row['pose']);need(row['statusIndex']>previous['statusIndex'])
            for key in ('home','graphics'):
                before,after=previous[key],row[key]
                need(before['instance']==after['instance'] and before['generation']==after['generation']
                    and before['commandId']!=after['commandId'] and after['sourceSequence']>before['sourceSequence']
                    and 0<=after['capturedEpochMs']-before['capturedEpochMs']<=1500 and after['elapsedMs']>=before['elapsedMs'])
            accept_inventory(previous['graphics']['graphicsInventory'],row['graphics']['graphicsInventory'],profiles=PROFILES)

    def save(self,value,*,host_only=False):
        self.host() if host_only else self.guard();self.validate(value)
        body=dict(navigationGenerationRestorationVersion=VERSION,scope=self.scope(),payload=pack([value]))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.state=deepcopy(value);self.physical=read_original(self.store.path)

    def stage(self,phase):
        value=deepcopy(self.state);value['phase']=phase;self.save(value)

    def login_intent(self,stage,before,control):
        self.guard();need(self.state['phase']=='entry' and control=='login.entry' and stage=='login-activate' and self.state['entry'] is None)
        rows=[row for row in before['controls'] if row['id']==control];need(len(rows)==1)
        value=deepcopy(self.state);value['entry']=dict(stage=0,control=control,action='activate',token=rows[0]['token'],
            scope=dict(instance=before['bridgeId'],generation=before['generation'],sequence=before['lastCommandSequence'],
                elapsedMs=before['elapsedMs'],processId=before['processId']))
        self.save(value)

    def before_send(self,command):
        self.guard()
        if self.state['phase']=='entry':pending=self.state['entry'];need(not self.state['qml'])
        else:
            need(self.state['phase']=='origin' and self.origin is not None)
            pending=self.origin.state['operation']['pending'];need(pending is not None and pending['control']=='login.server')
        need(command['controlId']==pending['control'] and command['controlToken']==pending['token']
            and command['action']==pending['action'] and command['bridgeId']==pending['scope']['instance']
            and command['generation']==pending['scope']['generation'] and command['sequence']==pending['scope']['sequence']+1)
        if command['action']=='replace':need(command['text']==self.authority.target(self.state['reference']))
        value=deepcopy(self.state);value['qml'].append(dict(command=deepcopy(command),pending=deepcopy(pending)));self.save(value)
        self.guard()  # Actual phase and physical parent after CAS, before writer.

    def anchor_input(self,kind):
        phase=self.guard();self.kind=kind
        self.anchor=dict(hostMonotonic=self.now(),nativeEpochMs=self.runtime['native'].clock_ms(),fixtureEpochMs=phase['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor)

    def age(self):
        self.host();need(self.anchor is not None and self.anchor_sha==json_digest(self.anchor));a=self.anchor;now=self.now()
        need(now>=a['hostMonotonic'] and max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def before_controller(self,operation):
        need((self.state['phase'],operation) in (('opening','tablet.open'),('closing','tablet.close')))
        need(not any(row['kind']==self.state['phase'] for row in self.state['controllers']));self.anchor_input(self.state['phase'])

    def controller_intent(self,envelope):
        self.age();need(not any(row['kind']==self.kind for row in self.state['controllers']))
        value=deepcopy(self.state);value['controllers'].append(dict(kind=self.kind,envelope=deepcopy(envelope),anchor=deepcopy(self.anchor),statuses=[]))
        self.save(value,host_only=True);self.before_publish(envelope)

    def before_publish(self,envelope):
        self.age();row=self.state['controllers'][-1]
        need(row['kind']==self.kind and same(row['envelope'],envelope) and same(row['anchor'],self.anchor))

    def home_stage(self,pose):
        self.guard();need(self.state['phase']=='origin' and self.origin is not None)
        operation=self.origin.state['operation'];need(operation['stage']==3 and operation['pending']['control']=='tablet.home-ray')
        observation=operation['homeBefore']['observation']
        need(same(pose,observed_grip_pose(observation['sensorToWorld'],observation['headPosition'],observation['position']))
            and not any(row['kind']=='home' for row in self.state['controllers']))
        self.anchor_input('home');self.runtime['session'].stage(self.binding['processIdentity'],'input.primary',pose,
            intent=self.intent_callback,before_publish=self.publish_callback)

    def neutral(self,kind,*,quiet=False):
        for attempt in range(81):
            self.guard();index=next(i for i,row in enumerate(self.state['controllers']) if row['kind']==kind)
            envelope=self.state['controllers'][index]['envelope']
            status=self.runtime['session'].observe_owned_status(self.binding['processIdentity'],envelope)
            value=deepcopy(self.state);value['controllers'][index]['statuses'].append(dict(status=deepcopy(status),hostMonotonic=self.now()));self.save(value)
            if NavigationBookmarkJoin.neutral(status,envelope):return
            need(not quiet and attempt<80 and status.get('state') in ('accepted','active'));self.runtime['native'].sleep(.1)
        need(False)

    def origin_owner(self):
        if self.origin is None:
            runtime=self.live();self.origin=NavigationOrigin(PicoNavigationOriginIO(runtime['normal'].io),runtime['environment'],
                self.origin_path,self.run,self.binding,self.guard,home=runtime['home'],monotonic=runtime['native'].monotonic,
                sleep=runtime['native'].sleep,restoration_authority=self.authority)
        return self.origin

    def packet(self,key,value):
        need(self.state['acquisitions'] and self.state['acquisitions'][-1]['phase']=='reading'
            and key not in self.state['acquisitions'][-1]['packets'])
        current=deepcopy(self.state);current['acquisitions'][-1]['packets'][key]=deepcopy(value);self.save(current)
        return value

    def final_sample(self):
        runtime=self.runtime;anchor=dict(hostMonotonic=self.now(),nativeEpochMs=runtime['native'].clock_ms())
        self.neutral('closing',quiet=True)
        environment=self.packet('environment',runtime['environment'].read(self.run));logged_out(environment)
        old=self.authority.read(self.state['reference'])['oldOriginal'];origin=self.origin_owner()
        need(environment['navigationEnvironmentVersion']==2 and environment['selectedSettingPresent']
            and environment['settings']['selectedType']==old['settings']['selectedType']=='string'
            and environment['settings']['rawSettingsSha256']==old['settings']['rawSettingsSha256']
            and environment['otherSettingsSha256']==old['otherSettingsSha256']
            and environment['selectedServer']==environment['effectiveServer']==old['selectedServer']
            and not environment['ui']['loginPageAlive'] and not environment['ui']['open'] and not environment['ui']['ready'])
        continuation(origin.state['last'],environment)
        home=self.packet('home',runtime['home'].source.capture());graphics=self.packet('graphicsBefore',runtime['graphics'].capture())
        need(not home['tabletShown'] and home['onHomeScreen'] and not graphics['tabletShown'] and not graphics['editorFocused']
            and not graphics['graphicsInventory']['keyboard3D']['raised'] and not graphics['graphicsInventory']['roots'])
        for key in ('instance','tabletId','homeId'):need(home[key]==origin.state['operation']['homeAfter']['observation'][key])
        after=origin.state['operation']['homeAfter']['original']['ui']
        need(environment['ui']['sequence']==after['sequence'] and environment['ui']['generation']!=after['generation'])
        pose=self.packet('pose',self.flow.source().arrival.read());bookmarks=self.packet('bookmarks',runtime['bookmarks'].read(self.run))
        panels=self.packet('panels',runtime['panels'].read(self.run));modals=self.packet('modals',runtime['modals'].read(self.run))
        # Native source queries follow the first graphics sample. Keep the
        # original final graphics timestamp after all independent sources.
        before_graphics=graphics;graphics=self.packet('graphics',runtime['graphics'].capture())
        return dict(environment=environment,home=home,graphicsBefore=before_graphics,graphics=graphics,pose=pose,bookmarks=bookmarks,panels=panels,modals=modals,
            sourceAnchor=anchor,hostMonotonic=self.now(),statusIndex=len(self.state['controllers'][-1]['statuses'])-1)

    def quiet(self):
        rows=self.state['quiet']
        if len(rows)>=3 and rows[-1]['environment']['capturedEpochMs']-rows[0]['environment']['capturedEpochMs']>=3000 and rows[-1]['hostMonotonic']-rows[0]['hostMonotonic']>=3:return
        need(not self.state['acquisitions'] or self.state['acquisitions'][-1]['phase']=='complete')
        while len(self.state['quiet'])<8:
            value=deepcopy(self.state);value['acquisitions'].append(dict(phase='reading',packets={}));self.save(value)
            frame=self.final_sample();rows=self.state['quiet']
            if rows:
                previous=rows[-1];continuation(previous['environment'],frame['environment'])
                NavigationOrigin.quiet_continuation(previous['environment'],frame['environment'])
                need(frame['hostMonotonic']>=previous['hostMonotonic'])
            value=deepcopy(self.state);value['quiet'].append(frame);value['acquisitions'][-1]['phase']='complete';self.save(value)
            first=self.state['quiet'][0]
            if len(self.state['quiet'])>=3 and frame['environment']['capturedEpochMs']-first['environment']['capturedEpochMs']>=3000 and frame['hostMonotonic']-first['hostMonotonic']>=3:return
            self.runtime['native'].sleep(.5)
        need(False)

    def evidence(self):
        paths=[self.store.path,self.origin_path,self.ui_path,self.authority.store.path]
        prefix=self.origin_path.stem+'-environment-';queries=set(self.origin.state['queries']);seen=set()
        operation=self.origin.state['operation']
        homes={operation[key]['observation']['commandId'] for key in ('homeBefore','homeAfter')}
        need(len(homes)==2 and homes<=queries);queries-=homes
        for path in self.lock.path.parent.iterdir():
            if not path.name.startswith(prefix):continue
            raw=PrivateFeatureState(path).read();environment_packet(raw,dict(schemaVersion=1,commandId=raw['commandId'],
                action='feature-navigation-environment',runId=self.run),int(self.binding['processIdentity'].split(':',1)[0]),raw['capturedEpochMs'])
            need(path==self.origin.packet_store(self.origin.packet_digest(raw)).path and raw['commandId'] in queries and raw['commandId'] not in seen)
            seen.add(raw['commandId']);paths.append(path)
        need(seen==queries)
        return [read_original(path) for path in paths]

    def restore(self,call):
        call=arguments('feature.world-navigation.cleanup',call);need(call['runId']==self.run and self.lock._owner is None)
        with self.lock.held():
            self.host()
            if self.state is None:
                # No child/orphan may be adopted by a fresh parent.
                need(not any(path.name.startswith(('navigation-prefix-generation-1-restoration','navigation-prefix-generation-1-origin-restart'))
                    for path in self.lock.path.parent.iterdir()))
                self.authority.old_origin()  # QString/original admission before ANY input.
                phase=self.flow.parent.phase.read();need(phase['verb']=='cleanup' and phase['inputs']=={}
                    and phase['status']['activations'][:-1]==self.flow.state['fixture']['activations'])
                value=dict(phase='admission',ticket=phase['ticket'],fixture=phase['status'],reference=None,entry=None,qml=[],controllers=[],originSha256=None,quiet=[],nativeOriginals=[],acquisitions=[])
                self.validate(value);body=dict(navigationGenerationRestorationVersion=VERSION,scope=self.scope(),payload=pack([value]))
                self.store.write(body,None);self.disk=body;self.state=value;self.physical=read_original(self.store.path)
            self.guard()
            if self.state['phase']=='admission':
                reference=self.authority.create();value=deepcopy(self.state);value.update(reference=reference,phase='opening');self.save(value)
            if self.state['phase']=='opening':
                if not self.state['controllers']:self.runtime['normal'].open_tablet()
                else:need(self.runtime['normal'].tablet_visible())
                self.neutral('opening');self.stage('entry')
            if self.state['phase']=='entry':
                controls=TokenLoginUI(PicoLoginIO(self.runtime['normal'].io),self.login_intent,self.run,self.flow.parent.source.origin,
                    monotonic=self.runtime['native'].monotonic,sleep=self.runtime['native'].sleep)
                if self.state['entry'] is None:
                    need(controls.row(controls.capture(),'login.page') is None)
                    controls._input('login.entry','activate')
                # The actual ordinary Entry may replace the Qt page generation.
                # Its fresh observer must still prove this exact recorded input.
                controls=TokenLoginUI(PicoLoginIO(self.runtime['normal'].io),self.login_intent,self.run,self.flow.parent.source.origin,
                    monotonic=self.runtime['native'].monotonic,sleep=self.runtime['native'].sleep)
                entered=controls.wait(lambda value:controls.row(value,'login.page') is not None)
                need(entered['bridgeId']==self.state['entry']['scope']['instance']
                    and entered['lastCommandSequence']==self.state['entry']['scope']['sequence']+1)
                self.stage('origin')
            if self.state['phase']=='origin':
                owner=self.origin_owner()
                if owner.state is None:owner.seed_restoration(self.state['ticket'],self.flow.parent.source.origin,self.state['reference'])
                owner.select(self.state['ticket'],self.flow.parent.source.origin,restoring=True);self.neutral('home')
                value=deepcopy(self.state);value.update(phase='closing',originSha256=json_digest(owner.disk_state));self.save(value)
            if self.state['phase']=='closing':
                need(json_digest(self.origin_owner().disk_state)==self.state['originSha256'])
                if not any(row['kind']=='closing' for row in self.state['controllers']):self.runtime['normal'].close_tablet()
                self.neutral('closing');need(not self.runtime['normal'].tablet_visible());self.stage('quiet')
            if self.state['phase']=='quiet':self.quiet();self.stage('complete')
            need(self.state['phase']=='complete');self.guard();evidence=self.evidence()
            captured=self.state['quiet'][-1]['environment']['capturedEpochMs'];anchor=self.state['quiet'][-1]['sourceAnchor']
            started=anchor['hostMonotonic'];requested=anchor['nativeEpochMs']
            session=self.runtime['session'];old_files=self.authority.originals()
        need(self.lock._owner is None and same(read_original(self.store.path),self.physical)
            and same([read_original(row['path']) for row in evidence],evidence)
            and same([read_original(row['path']) for row in old_files],old_files))
        verify_archive(self.flow.restart.state['files'],self.lock.path.parent,self.run,self.flow.restart.state['normalUiPath'])
        need(self.runtime['native'].guard() is not False)
        with session._lock():current=session._load()
        need(current['sessionNonce']==self.flow.restart.state['newSession']['sessionNonce']
            and current['nextSequence']==self.flow.restart.state['newSession']['nextSequence']+len(self.flow.state['controllers'])+len(self.state['controllers']))
        phase=self.flow.parent.phase.read();need(phase['ticket']==self.state['ticket'] and same(phase['status']['activations'],self.state['fixture']['activations']))
        epoch=self.runtime['native'].clock_ms();fresh(captured,epoch)
        need(self.now()>=started and max(epoch-captured,requested-captured+(self.now()-started)*1000)<=1500)
        return dict(performed=True)
