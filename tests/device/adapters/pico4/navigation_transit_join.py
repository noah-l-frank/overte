"""Existing normal transit/Home/controller Close under one prefix authority.

This is a child of NavigationPrefix, never another Journey or source publisher.
Original transit, stereo and Close journals remain the effect/release evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.android.input_geometry import observed_grip_pose
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,need,number
from adapters.navigation_transit import NavigationTransit
from adapters.navigation_arrival import stereo_frame
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation_close import NavigationTabletClose
from adapters.pico4.graphics_source import PicoGraphicsSource
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.script_journey.history import same
from adapters.token_script_ui import TokenScriptUI
from openxr_input.controller_protocol import validate_envelope
from feature_journeys.contract import identifier

VERSION=1


class NavigationTransitJoin:
    def __init__(self,parent,transit,normal,graphics,path):
        need(isinstance(transit,NavigationTransit) and isinstance(normal,TokenScriptUI)
            and isinstance(normal.io,PicoScriptIO) and isinstance(graphics,PicoGraphicsSource)
            and transit.defer_stereo and transit.home is not None and transit.directory is parent.directory
            and transit.ui.io.original is normal.io is parent.source.normal.io.original
            and same(transit.binding,parent.binding) and transit.run==parent.run)
        self.parent,self.transit,self.normal,self.graphics=parent,transit,normal,graphics
        self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None;self.close_owner=None
        self.anchor=self.anchor_sha=None
        self.home_callback=self.stage_home;transit.home.stage=self.home_callback
        self.admission_callback=self.before_controller;self.intent_callback=self.intent;self.publish_callback=self.before_publish
        if self.disk is not None:self.load()

    def context(self,*,memory_only=False):
        p=self.parent;p.lock.assert_held();p.control()
        need(p.role=='primary' and same(p.state,p.disk) and p.state['phase']=='acting'
            and p.state['active']['verb']=='directory-select' and p.state['active']['stage']=='transit')
        if not memory_only:need(same(p.store.read(),p.disk))

    def validate(self,value):
        exact(value,{'navigationTransitJoinVersion','runId','binding','parentScopeSha256','parentPath','ticket','phase',
            'qml','controllers','transitSha256','closeSha256','stereoSha256'})
        p=self.parent
        need(type(value['navigationTransitJoinVersion']) is int and value['navigationTransitJoinVersion']==VERSION
            and value['runId']==p.run and same(value['binding'],p.binding) and value['parentScopeSha256']==p.scope_sha
            and value['parentPath']==str(p.store.path) and value['phase'] in ('transit-issued','transited','close-issued','image-issued','closed')
            and type(value['qml']) is list and len(value['qml'])<=70)
        identifier(value['ticket'])
        need(any(row['ticket']==value['ticket'] and row['verb']=='directory-select' for row in p.state['completed'])
            or p.state['active'] is not None and p.state['active']['ticket']==value['ticket'] and p.state['active']['verb']=='directory-select')
        need((value['transitSha256'] is not None)==(value['phase']!='transit-issued')
            and (value['closeSha256'] is not None)==(value['phase'] in ('image-issued','closed'))
            and (value['stereoSha256'] is not None)==(value['phase']=='closed'))
        for command in value['qml']:need(any(same(command,row) for row in p.state['deliveries']))
        exact(value['controllers'],{'home','close'})
        for kind,record in value['controllers'].items():
            if record is None:continue
            exact(record,{'envelope','sha256','anchor'});envelope=record['envelope'];validate_envelope(envelope,p.session.profile)
            need(type(envelope['schemaVersion']) is int and type(envelope['sequence']) is int
                and len(envelope['commands'])==1 and record['sha256']==json_digest(envelope))
            anchor=record['anchor'];exact(anchor,{'kind','operation','arguments','hostMonotonic','nativeEpochMs','fixtureEpochMs'})
            need(anchor['kind']==kind and anchor['operation']==('input.primary' if kind=='home' else 'tablet.close')
                and number(anchor['hostMonotonic'],0,1e15) and number(anchor['nativeEpochMs'],1,1e15)
                and number(anchor['fixtureEpochMs'],1,1e15) and -250<=anchor['nativeEpochMs']-anchor['fixtureEpochMs']<=1500
                and envelope['commands'][0]['operation']==anchor['operation']
                and same(envelope['commands'][0]['arguments'],anchor['arguments']))
            if kind=='home':
                need(self.transit.state is not None and self.transit.state['homeBefore'] is not None)
                observed=self.transit.state['homeBefore']['observation']
                need(same(anchor['arguments'],observed_grip_pose(observed['sensorToWorld'],observed['headPosition'],observed['position'])))
            else:need(anchor['arguments']==dict(holdMilliseconds=1000))
        a,b=value['controllers']['home'],value['controllers']['close']
        if a is not None:
            original=p.state['home']['envelope']
            need(a['envelope']['sessionNonce']==original['sessionNonce'] and a['envelope']['sequence']==original['sequence']+1)
        if value['phase']!='transit-issued':need(a is not None)
        if value['phase'] in ('image-issued','closed'):need(b is not None)
        if a is not None and b is not None:
            need(a['envelope']['sessionNonce']==b['envelope']['sessionNonce']
                and b['envelope']['sequence']==a['envelope']['sequence']+1)
        if value['transitSha256'] is not None:
            need(self.transit.disk is not None and value['transitSha256']==self.transit_proof()
                and self.transit.state['ticket']==value['ticket'] and self.transit.state['quiet'])
        if value['stereoSha256'] is not None:
            stereo=self.transit.stereo_factory(value['ticket'])
            need(stereo.state is not None and stereo.state['phase']=='complete' and value['stereoSha256']==json_digest(stereo.disk))
            facts=stereo_frame(stereo.state['frame'],stereo.image_bytes(),p.run,p.binding,self.transit.scene_url)
            frame=stereo.state['frame'];closed=self.close_original().state
            need(facts['location']=='B' and frame['navigationStereoSourceVersion']==2
                and frame['before']['subject']['capturedEpochMs']>=closed['last']['graphics']['capturedEpochMs']
                and frame['before']['subject']['sequence']>closed['last']['transit']['pose']['subject']['sequence']
                and not set(self.transit.stereo_queries(stereo)).intersection(set(self.transit.state['queries'])|set(closed['queries'])))
        if value['phase']=='closed':need(value['transitSha256'] is not None and value['closeSha256'] is not None and value['stereoSha256'] is not None)
        if value['closeSha256'] is not None:
            owner=self.close_original()
            need(owner.disk is not None and value['closeSha256']==json_digest(owner.disk) and owner.state['phase']=='closed')

    def load(self):
        value=self.store.read();need(value is not None);self.validate(value)
        self.disk=deepcopy(value);self.state=deepcopy(value)

    def save(self,value):
        self.parent.lock.assert_held();self.validate(value);self.store.write(value,self.disk)
        self.disk=deepcopy(value);self.state=deepcopy(value)

    def record_qml(self,command):
        self.context();need(self.state is not None and self.state['phase']=='transit-issued')
        pending=self.transit.state['pending'];need(pending is not None and 'input' in pending)
        current=deepcopy(self.state);current['qml'].append(deepcopy(command));self.save(current)

    def anchor_for(self,kind,operation,arguments):
        p=self.parent;current=p.fence()
        self.anchor=dict(kind=kind,operation=operation,arguments=deepcopy(arguments),hostMonotonic=p.now(),
            nativeEpochMs=p.source.clock_ms(),fixtureEpochMs=current['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor);self.age()

    def age(self):
        self.context(memory_only=True)
        need(self.anchor is not None and self.anchor_sha==json_digest(self.anchor))
        now=self.parent.now();a=self.anchor
        need(now>=a['hostMonotonic'] and max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def stage_home(self,pose):
        self.context();need(self.state['phase']=='transit-issued' and self.state['controllers']['home'] is None)
        observed=self.transit.state['homeBefore']['observation']
        need(same(pose,observed_grip_pose(observed['sensorToWorld'],observed['headPosition'],observed['position'])))
        p=self.parent;p.transport.bind_input()
        need(p.transport.adapter.require_pico_session_identity(p.transport.target)==p.binding['processIdentity'])
        self.anchor_for('home','input.primary',pose)
        p.session.stage(p.binding['processIdentity'],'input.primary',pose,intent=self.intent_callback,before_publish=self.publish_callback)

    def before_controller(self,operation):
        self.context();need(operation=='tablet.close' and self.state['phase']=='close-issued'
            and self.state['controllers']['close'] is None and self.close_original().state['phase']=='closing')
        # NativeNavigationIO has completed its candidate/process/session/FG
        # guards. The exact phase follows the last durable child Close intent.
        self.anchor_for('close',operation,dict(holdMilliseconds=1000))

    def intent(self,envelope):
        self.age();kind=self.anchor['kind'];need(self.state['controllers'][kind] is None)
        current=deepcopy(self.state);current['controllers'][kind]=dict(envelope=deepcopy(envelope),sha256=json_digest(envelope),anchor=deepcopy(self.anchor))
        self.save(current);self.before_publish(envelope)

    def before_publish(self,envelope):
        # Original Session lock: retained DTO, host CAS/clock only. No phase,
        # source, SDK, normal UI, Session reentry or physical source read.
        self.age();record=self.state['controllers'][self.anchor['kind']]
        need(record is not None and same(record['anchor'],self.anchor) and record['sha256']==json_digest(envelope)
            and same(record['envelope'],envelope))

    def close_original(self):
        if self.close_owner is None:
            p=self.parent
            self.close_owner=NavigationTabletClose(self.transit,self.normal,self.graphics,
                self.store.path.with_name('navigation-prefix-tablet-close.json'),p.source.guard,
                monotonic=p.monotonic,sleep=self.source_sleep())
        return self.close_owner

    def source_sleep(self):return self.parent.source.normal.sleep

    def transit_proof(self):
        # Close's fresh independent samples legitimately advance last/queries.
        # The original completed input/quiet/stereo proof remains immutable.
        return json_digest({key:self.transit.state[key] for key in
            ('ticket','kind','stage','original','homeMode','homeBefore','homeAfter','stereoDeferred','stereoSha256','quiet')})

    def act(self,ticket):
        self.context()
        if self.state is None:
            self.save(dict(navigationTransitJoinVersion=VERSION,runId=self.parent.run,binding=deepcopy(self.parent.binding),
                parentScopeSha256=self.parent.scope_sha,parentPath=str(self.parent.store.path),ticket=ticket,
                phase='transit-issued',qml=[],controllers=dict(home=None,close=None),transitSha256=None,closeSha256=None,stereoSha256=None))
        need(self.state['ticket']==ticket)
        if self.state['phase']=='transit-issued':
            self.parent.fence();self.transit.act(ticket,'directory')
            current=deepcopy(self.state);current.update(phase='transited',transitSha256=self.transit_proof());self.save(current);self.parent.fence()
        if self.state['phase']=='transited':
            current=deepcopy(self.state);current['phase']='close-issued';self.save(current);self.parent.fence()
        if self.state['phase']=='close-issued':
            owner=self.close_original();owner.close(ticket)
            current=deepcopy(self.state);current.update(phase='image-issued',closeSha256=json_digest(owner.disk));self.save(current);self.parent.fence()
        if self.state['phase']=='image-issued':
            self.parent.fence();stereo=self.transit.stereo_factory(ticket);stereo.acquire(ticket)
            current=deepcopy(self.state);current.update(phase='closed',stereoSha256=json_digest(stereo.disk));self.save(current);self.parent.fence()
        need(self.state['phase']=='closed');self.parent.fence()
        return dict(performed=True)
