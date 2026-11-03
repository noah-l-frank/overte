"""Normal original-world restoration after the SAME G1 Origin3 cleanup.

This warm child owns no recipe, restart, new deadline or desired observation.
Only the independently observed pre-setup lease supplies its normal Go To URL.
Resource, peer and host retirement remain separate outstanding obligations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import exact,fresh,need
from adapters.native_navigation_environment import logged_out,continuation
from adapters.navigation_arrival import NavigationArrival,pose_packet,advance as pose_advance
from adapters.navigation_origin import NavigationOrigin
from adapters.observer_return import state as original_state
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation import PicoNavigation
from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
from adapters.pico4.navigation_originals import read_original
from adapters.pico4.navigation_scene_generation import NavigationSceneGeneration
from adapters.pico4.navigation_scene_raw_reader import NavigationSceneRawReader
from adapters.pico4.navigation_scene_prefix import NavigationSceneIO
from adapters.pico4.tablet_home import bind_home
from adapters.script_journey.history import canonical,pack,same
from feature_journeys.contract import arguments
from navigation_observation import viewpoint_urls
from openxr_input.controller_protocol import validate_envelope

VERSION=1


class NavigationOriginalWorldIO(NavigationSceneIO):
    """Initially bind the original callbacks plus LAST delivery-age fences."""
    def __init__(self,world,*args):
        self.world=world;super().__init__(*args)

    def guard(self):
        self.world.host();result=super().guard();self.world.host();return result

    def wrapped(self,callback):
        original=super().wrapped(callback);world=self.world
        def delivery(*args,**kwargs):
            need(self.world is world);result=original(*args,**kwargs)
            # No work follows this fence before the inherited actual writer
            # or Session publisher. A late callback cannot send then reject.
            world.delivery_age(args[0]);return result
        return delivery


class NavigationSceneOriginalWorld:
    """One issued normal Go To / Home / Close, followed by original quiet.

    Construction requires completed directory restoration and fresh factories
    from that exact G1 adapter. Failed or orphan children cannot be adopted.
    """
    def __init__(self,generation):
        need(type(generation) is NavigationSceneGeneration)
        self.generation=generation;self.scene=generation.owner;self.flow=generation.primary.generation_owner
        need(self.flow is not None and generation.actor.generation_owner is not None)
        self.directory=self.flow.restoration_owner
        need(self.scene.probe_factory is not None and self.directory is not None and self.directory.state is not None
            and self.directory.state['phase']=='complete' and self.directory.runtime is not None
            and self.directory.scene_owner is self.scene and self.scene.state['phase']=='directory-restored')
        self.lock=self.scene.lock;self.lock.assert_held();self.scene.publish_bound()
        self.adapter,self.target=self.directory.adapter,self.directory.target
        self.binding=deepcopy(self.flow.binding);self.run=self.scene.run
        self.lease=self.scene.lease();need(self.lease['navigationSceneOriginalLeaseVersion']==2)
        self.scene_url=self.lease['originalSceneUrl'];self.url=self.lease['originalUrl']
        labels=[label for label,url in viewpoint_urls(self.scene_url).items() if url==self.url]
        need(len(labels)==1);self.label=labels[0]
        self.path=self.scene.path.with_name(self.scene.path.name+'.user-world.json')
        self.ui_path=self.path.with_name(self.path.name+'.normal-ui.json')
        self.store=PrivateFeatureState(self.path);self.disk=self.state=self.physical=None
        self.failed=False;self.runtime=self.original_runtime=None;self.runtime_pins=self.original_runtime_pins=None
        self.channels=[];self.ui_anchor=None;self.status_pending=None
        self.anchor=self.kind=None
        self.directory_originals=tuple(read_original(path) for path in
            (self.directory.store.path,self.directory.origin_path,self.directory.authority.store.path))
        need(all(row['present'] for row in self.directory_originals))
        self.scope=dict(navigationSceneOriginalWorldVersion=VERSION,sceneScopeSha256=self.scene.scope_sha,
            binding=self.binding,runId=self.run,path=str(self.path),uiPath=str(self.ui_path),
            sourceLock=str(self.lock.path),originalSceneUrl=self.scene_url,originalUrl=self.url,
            directoryOriginals=list(self.directory_originals))
        self.scope_sha=json_digest(self.scope)
        need(self.store.read() is None and not any(p.name.startswith(self.path.name+'.') for p in self.scene.root.iterdir()))
        self.chunks=ChatSourceChunks(self.store,self.scope)
        self.qml_callback=self.before_send;self.controller_callback=self.before_controller
        self.intent_callback=self.controller_intent;self.publish_callback=self.before_publish
        self.save(dict(navigationSceneOriginalWorldVersion=VERSION,scope=deepcopy(self.scope),phase='admission',
            ticket=self.directory.state['ticket'],fixture=deepcopy(self.directory.state['fixture']),chunks=[],pending=None,
            authority=None,qml=[],controllers=[],home=None,raw=[],arrival=None,quiet=[]))

    def host(self):
        self.lock.assert_held();need(not self.failed)
        self.scene.publish_bound();self.flow.control();self.flow.validate_links(self.flow.state)
        need(self.generation.owner is self.scene and self.generation.primary.generation_owner is self.flow
            and self.flow.restoration_owner is self.directory and json_digest(self.scope)==self.scope_sha
            and self.directory.state['phase']=='complete' and self.directory.adapter is self.adapter
            and self.directory.target==self.target and self.store.path==self.path
            and self.url==self.scope['originalUrl'] and self.scene_url==self.scope['originalSceneUrl']
            and viewpoint_urls(self.scene_url)[self.label]==self.url and same(self.binding,self.scope['binding']))
        if self.runtime is not None:
            runtime=self.runtime;io=runtime['io'];normal=runtime['normal']
            need(runtime is self.original_runtime and type(runtime) is dict
                and self.runtime_pins is self.original_runtime_pins and type(self.runtime_pins) is tuple
                and set(runtime)=={key for key,_value in self.runtime_pins}
                and all(runtime[key] is value for key,value in self.runtime_pins)
                and normal.io is io and type(io) is NavigationOriginalWorldIO and io.world is self and io.scene_owner is self.scene
                and io.adapter is self.adapter and io.target==self.target and io.identity==self.binding['processIdentity']
                and normal.path==self.ui_path and normal.monotonic is self.scene.monotonic
                and normal.context['processIdentity']==self.binding['processIdentity']
                and all(normal.context[key]==self.binding[key] for key in ('sourceRevision','artifactSha256'))
                and normal.context['sceneSha256']==hashlib.sha256(self.scene_url.encode()).hexdigest()
                and runtime['session'] is self.directory.runtime['session']
                and same(runtime['session'].profile,self.flow.restart.state['profile'])
                and io._read is runtime['uiRead'] and io.controller is runtime['controller']
                and io.scene_qml[0] is self.qml_callback and io._before_send is io.scene_qml[1]
                and all(a is b for a,b in zip(io.scene_controller[0],(self.controller_callback,self.intent_callback,self.publish_callback)))
                and all(a is b for a,b in zip(io.scene_controller[1],(io._before_controller,io._controller_intent,io._controller_publish))))
        for original in self.directory_originals:need(same(read_original(original['path']),original))
        if self.disk is not None:
            body,_raw,pin=original_state(self.store)
            need(same(body,self.disk) and same(body,self.state) and pin==self.physical)

    def save(self,value):
        self.host();need(len(canonical(value))+1<=65536 and same(value['scope'],self.scope))
        self.store.write(value,self.disk);actual,_raw,pin=original_state(self.store)
        need(same(actual,value));self.disk=self.state=deepcopy(value);self.physical=pin

    def change(self,**updates):
        value=deepcopy(self.state);value.update(updates);self.save(value)

    def packet(self,value):
        self.host();need(self.state['pending'] is None)
        phase=self.state['phase'];self.change(phase='reading',pending=pack([value]))
        chunks=self.chunks.append(value,self.state['chunks'])
        self.change(phase=phase,pending=None,chunks=chunks);self.scene.bill();return len(chunks)-1

    def retained(self,reference,request):
        # The enclosing raw owner has ALREADY fsynced and durably committed the
        # literal, even if this later business-history expansion is refused.
        # Full request/binding/clock are already immutable in the ONE raw
        # archive receipt. Keep bounded references here, not duplicate metadata.
        self.change(raw=[*self.state['raw'],dict(reference=deepcopy(reference),
            source=request.get('source',request.get('action','navigation-source')))])

    def live(self):
        if self.runtime is not None:return self.runtime
        self.host();a=self.adapter;t=self.target;identity=a.require_controlled_debug_identity(t);installed=a._installation(t)
        need(identity==self.binding['processIdentity']==a.require_pico_session_identity(t)
            and all(installed[key]==self.binding[key] for key in ('sourceRevision','artifactSha256')))
        io=NavigationOriginalWorldIO(self,a,t,identity,lambda *_args:need(False),self.scene)
        normal=PicoNavigation(io,self.ui_path,installed,identity,self.scene_url,
            monotonic=self.scene.monotonic,sleep=self.directory.runtime['native'].sleep)
        need(normal.state is None);old_read=io._read
        def read(kind):
            self.guard();token=self.status_pending if kind=='status' else None
            if kind=='status':self.status_pending=None
            if token is None:token=self.scene.raw.reserve('navigation-original-world',dict(source='navigation-ui',kind=kind,binding=self.binding),262144,side_bytes=0)
            self.guard();raw=old_read(kind);reference=self.scene.raw.retain(token,raw)
            self.retained(reference,dict(source='navigation-ui',kind=kind))
            self.guard()
            if kind=='observation':
                value=json.loads(raw)
                self.ui_anchor=dict(bridgeId=value['bridgeId'],generation=value['generation'],sequence=value['lastCommandSequence'],
                    elapsedMs=value['elapsedMs'],epoch=value['updatedEpochMs'],hostMonotonic=self.scene.now())
            return raw
        io._read=read
        old_controller=io.controller
        def controller(operation):
            result=old_controller(operation)
            self.neutral('opening' if operation=='tablet.open' else 'closing');return result
        io.controller=controller
        io.bind_before_send(self.qml_callback);io.bind_controller_admission(self.controller_callback,
            intent=self.intent_callback,before_publish=self.publish_callback)
        native=a._native_feature_observer(t);source=self.flow.source();environment=a._navigation_environment(t)
        self.raw_authority=self.host
        home=bind_home(a,t,native)
        self.runtime=self.original_runtime=dict(normal=normal,io=io,native=native,environment=environment,home=home,
            graphics=a._graphics_ui_observer(t),bookmarks=a._location_bookmarks(t),panels=a._navigation_panels(t),
            modals=a._navigation_modals(t),presence=a._process_presence(t),session=a.pico_input_session(t),
            installed=deepcopy(installed),source=source,uiRead=read,controller=controller)
        def probe(after):self.guard();value=a.read_probe_snapshot(t,'org.overte.pico',after);self.guard();return value
        self.runtime['arrival']=NavigationArrival(probe,a._graphics_subject_observer(t),native.clock_ms,self.guard,
            self.run,self.binding,self.scene_url,monotonic=self.scene.monotonic)
        self.probe_originals=self.scene.bind_probe(self.runtime['arrival'],a,t,self.guard,'primary')
        readers=[('native',native,'read'),('environment',environment,'read'),('home',home.source,'capture'),
            ('graphics',self.runtime['graphics'],'capture'),('bookmarks',self.runtime['bookmarks'],'read'),
            ('panels',self.runtime['panels'],'read'),('modals',self.runtime['modals'],'read'),
            ('presence',self.runtime['presence'],'read'),('subject',self.runtime['arrival'].subject,'read')]
        self.channels=[NavigationSceneRawReader(self.scene,reader,self.binding,'navigation-original-'+name,
            self.raw_authority,self.retained,method=method) for name,reader,method in readers]
        self.runtime_pins=self.original_runtime_pins=tuple(self.runtime.items())
        return self.runtime

    def guard(self):
        self.host();runtime=self.live();a=self.adapter;t=self.target
        need(runtime['source'].guard() is not False and runtime['native'].guard() is not False
            and a.require_controlled_debug_identity(t)==self.binding['processIdentity']==a.require_pico_session_identity(t)
            and a._installation(t)==runtime['installed'] and runtime['io']._read is runtime['uiRead']
            and runtime['io'].controller is runtime['controller'])
        phase=self.flow.parent.phase.read()
        need(phase['verb']=='cleanup' and phase['inputs']=={} and phase['ticket']==self.state['ticket']
            and same(phase['status']['activations'],self.state['fixture']['activations']))
        fresh(phase['status']['capturedEpochMs'],runtime['native'].clock_ms())
        if self.state['authority'] is not None:
            baseline=self.chunks.load(self.state['chunks'])[self.state['authority']]['session']
            with runtime['session']._lock():session=deepcopy(runtime['session']._load())
            need(session is not None and session['processIdentity']==baseline['processIdentity']
                and session['sessionNonce']==baseline['sessionNonce']
                and session['nextSequence']==baseline['nextSequence']+len(self.state['controllers']))
        self.scene.bound();return phase

    def unchanged(self,environment):
        self.scene.unchanged_settings(environment);logged_out(environment)
        need(not environment['ui']['loginPageAlive'])

    def authority(self):
        runtime=self.live();phase=self.guard();native=runtime['native'].read(0)
        plan=self.flow.restart.inputs.read();new=plan['newNative']
        need(plan['phase']=='observed' and same(plan['newBinding'],self.binding))
        need(native['processId']==int(self.binding['processIdentity'].split(':',1)[0])
            and native['instance']==new['instance'] and native['lifecycle']==new['lifecycle'])
        old_pid=int(self.flow.restart.binding['processIdentity'].split(':',1)[0])
        absent=runtime['presence'].require_absent(old_pid)
        environment=runtime['environment'].read(self.run);self.unchanged(environment)
        need(not environment['ui']['open'] and not environment['ui']['ready'])
        with runtime['session']._lock():session=deepcopy(runtime['session']._load())
        last=self.directory.state['controllers'][-1]['envelope']
        need(session['sessionNonce']==last['sessionNonce'] and session['nextSequence']==last['sequence']+1
            and session['processIdentity']==self.binding['processIdentity'])
        status=runtime['session'].observe_owned_status(self.binding['processIdentity'],last)
        need(NavigationBookmarkJoin.neutral(status,last))
        reference=self.packet(dict(kind='original-world-authority',binding=self.binding,phase=phase,native=native,oldAbsent=absent,
            environment=environment,session=session,status=status,hostMonotonic=self.scene.now()))
        self.change(authority=reference,phase='goto')

    def input_anchor(self,kind):
        phase=self.guard();self.kind=kind
        self.anchor=dict(hostMonotonic=self.scene.now(),nativeEpochMs=self.runtime['native'].clock_ms(),
            fixtureEpochMs=phase['status']['capturedEpochMs'])

    def age(self):
        self.host();need(self.anchor is not None);now=self.scene.now();a=self.anchor
        need(max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def delivery_age(self,argument):
        self.scene.bound()
        if type(argument) is dict and 'controlId' in argument:
            need(self.ui_anchor is not None);anchor=self.ui_anchor
            need(argument['bridgeId']==anchor['bridgeId'] and argument['generation']==anchor['generation']
                and argument['sequence']==anchor['sequence']+1 and argument['observedElapsedMs']==anchor['elapsedMs']
                and self.scene.now()-anchor['hostMonotonic']<=.5
                and 0<=self.runtime['native'].clock_ms()-anchor['epoch']<=500)
        else:self.age()

    def before_send(self,command):
        self.guard();need(self.state['phase']=='goto' and len(self.state['qml'])<40
            and (command['controlId'] in ('navigation.goto','navigation.address','tablet.home')
                 or command['controlId'].startswith('tablet.page.')))
        if command['action']=='replace':need(command['controlId']=='navigation.address' and command['text']==self.url)
        self.change(qml=[*self.state['qml'],deepcopy(command)])
        need(self.status_pending is None)
        self.status_pending=self.scene.raw.reserve('navigation-original-world',dict(source='navigation-ui',kind='status',
            binding=self.binding,command=deepcopy(command)),262144,side_bytes=0)
        self.delivery_age(command)

    def before_controller(self,operation):
        need((self.state['phase'],operation) in (('goto','tablet.open'),('closing','tablet.close')))
        kind='opening' if operation=='tablet.open' else 'closing'
        need(not any(row['kind']==kind for row in self.state['controllers']));self.input_anchor(kind)

    def controller_intent(self,envelope):
        self.age();validate_envelope(envelope,self.runtime['session'].profile)
        baseline=self.chunks.load(self.state['chunks'])[self.state['authority']]['session']
        operation={'opening':'tablet.open','home':'input.primary','closing':'tablet.close'}[self.kind]
        need(envelope['sessionNonce']==baseline['sessionNonce']
            and envelope['sequence']==baseline['nextSequence']+len(self.state['controllers'])
            and len(envelope['commands'])==1 and envelope['commands'][0]['operation']==operation
            and not any(row['kind']==self.kind for row in self.state['controllers']))
        self.change(controllers=[*self.state['controllers'],dict(kind=self.kind,envelope=deepcopy(envelope),
            anchor=deepcopy(self.anchor),statuses=[])])

    def before_publish(self,envelope):
        self.scene.publish_bound();self.age();need(same(self.state['controllers'][-1]['envelope'],envelope)
            and same(self.state['controllers'][-1]['anchor'],self.anchor));self.scene.publish_bound();self.age()

    def neutral(self,kind,*,quiet=False):
        for attempt in range(81):
            self.guard();index=next(i for i,row in enumerate(self.state['controllers']) if row['kind']==kind)
            envelope=self.state['controllers'][index]['envelope']
            status=self.runtime['session'].observe_owned_status(self.binding['processIdentity'],envelope)
            value=deepcopy(self.state);value['controllers'][index]['statuses'].append(dict(status=deepcopy(status),hostMonotonic=self.scene.now()))
            self.save(value)
            if NavigationBookmarkJoin.neutral(status,envelope):return
            need(not quiet and attempt<80 and status.get('state') in ('accepted','active'));self.runtime['native'].sleep(.1)
        need(False)

    def home_intent(self,stage,before,control):
        self.guard();need(self.state['phase']=='home' and self.state['home'] is None and stage=='tablet-home-ray' and control=='tablet.home-ray')
        self.change(home=deepcopy(before));self.input_anchor('home')

    def sample(self):
        self.guard();runtime=self.runtime;self.neutral('closing',quiet=True)
        environment=runtime['environment'].read(self.run);self.unchanged(environment)
        pose=runtime['arrival'].read();home=runtime['home'].source.capture();graphics=runtime['graphics'].capture()
        need(pose_packet(pose,self.run,self.binding,self.scene_url,runtime['native'].clock_ms())==self.label
            and not environment['ui']['open'] and not environment['ui']['ready'] and not home['tabletShown']
            and home['onHomeScreen'] and not graphics['tabletShown'] and not graphics['editorFocused']
            and not graphics['graphicsInventory']['keyboard3D']['raised'] and not graphics['graphicsInventory']['roots'])
        for reference in self.directory_originals:need(same(read_original(reference['path']),reference))
        self.guard();return dict(kind='original-world-quiet',environment=environment,pose=pose,home=home,graphics=graphics,
            hostMonotonic=self.scene.now())

    def restore(self,call):
        call=arguments('feature.world-navigation.cleanup',call);need(call['runId']==self.run and self.lock._owner is None)
        try:
            with self.lock.held():
                self.host();need(self.state['phase']=='admission')
                self.authority();runtime=self.runtime
                runtime['normal'].invoke('places.goto',dict(url=self.url));self.neutral('opening')
                pose=runtime['arrival'].read()
                need(pose_packet(pose,self.run,self.binding,self.scene_url,runtime['native'].clock_ms())==self.label)
                arrival=self.packet(dict(kind='original-world-arrival',pose=pose,hostMonotonic=self.scene.now()))
                self.change(phase='home',arrival=arrival)
                runtime['home'].ensure(self.home_intent,stream_intent=self.intent_callback,stream_publish=self.publish_callback)
                if self.state['home'] is not None:self.neutral('home')
                self.change(phase='closing');runtime['normal'].close();self.neutral('closing');self.change(phase='quiet')
                while len(self.state['quiet'])<8:
                    frame=self.sample();previous=None if not self.state['quiet'] else self.chunks.load(self.state['chunks'])[self.state['quiet'][-1]]
                    if previous is not None:
                        continuation(previous['environment'],frame['environment']);NavigationOrigin.quiet_continuation(previous['environment'],frame['environment'])
                        pose_advance(previous['pose'],frame['pose'])
                    reference=self.packet(frame);self.change(quiet=[*self.state['quiet'],reference])
                    first=self.chunks.load(self.state['chunks'])[self.state['quiet'][0]]
                    if len(self.state['quiet'])>=3 and frame['hostMonotonic']-first['hostMonotonic']>=3 and frame['environment']['capturedEpochMs']-first['environment']['capturedEpochMs']>=3000:break
                    runtime['native'].sleep(.5)
                else:need(False)
                self.change(phase='complete');self.guard();self.scene.bill()
            self.finalize();return dict(navigationSceneOriginalWorldVersion=VERSION,originalWorldRestored=True,
                original=read_original(self.path),fullNavigationRecipe=False,roleRetirementPending=True,hostRetirementPending=True)
        except BaseException:
            self.failed=True;raise

    def finalize(self):
        """Requalify after the REAL outer exit; never renew the last sample."""
        need(self.lock._owner is None and self.state['phase']=='complete')
        self.scene.publish_bound();runtime=self.runtime;a=self.adapter;t=self.target
        need(runtime['native'].guard() is not False and a.require_controlled_debug_identity(t)==self.binding['processIdentity']
            and a.require_pico_session_identity(t)==self.binding['processIdentity'] and a._installation(t)==runtime['installed'])
        with runtime['session']._lock():session=deepcopy(runtime['session']._load())
        last=self.state['controllers'][-1]['envelope']
        need(session is not None and session['sessionNonce']==last['sessionNonce'] and session['nextSequence']==last['sequence']+1)
        phase=self.flow.parent.phase.read()
        need(phase['verb']=='cleanup' and phase['inputs']=={} and phase['ticket']==self.state['ticket']
            and same(phase['status']['activations'],self.state['fixture']['activations']))
        self.scene.publish_bound();body,_raw,pin=original_state(self.store)
        need(same(body,self.disk) and pin==self.physical)
        frame=self.chunks.load(self.state['chunks'])[self.state['quiet'][-1]]
        now=self.scene.now();epoch=runtime['native'].clock_ms()
        effective=max(epoch,frame['environment']['capturedEpochMs']+(now-frame['hostMonotonic'])*1000)
        fresh(frame['environment']['capturedEpochMs'],int(effective));fresh(phase['status']['capturedEpochMs'],int(effective))
