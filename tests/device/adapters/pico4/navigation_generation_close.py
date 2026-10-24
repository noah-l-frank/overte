"""Normal G1 Places Home ray and existing tablet Close, with original journals.

The page source is the actually opened and deleted page. This owner adds no
transit, UI setter, restart, or requested effect. Issued gestures stay owned on
cold recovery and are never published a second time.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.android.input_geometry import observed_grip_pose
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import need,exact,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
from adapters.pico4.navigation_close import NavigationTabletClose
from adapters.pico4.navigation_generation_page import NavigationGenerationPage
from adapters.pico4.tablet_home import validate as home_packet,validate_input as home_input
from adapters.script_journey.history import same,pack,unpack
from adapters.token_script_ui import TokenScriptUI
from openxr_input.controller_protocol import validate_envelope

VERSION=1


class NavigationGenerationClose:
    def __init__(self,parent,home,graphics):
        self.parent,self.home,self.graphics=parent,home,graphics
        self.store=PrivateFeatureState(parent.lock.path.with_name('navigation-prefix-generation-1-close-join.json'))
        self.disk=self.store.read();self.state=None;self.owner=None;self.anchor=self.anchor_sha=None
        self.home.stage=self.stage_home
        self.home_intent_callback=self.home_controller_intent;self.home_publish_callback=self.home_before_publish
        if self.disk is not None:self.load()

    def validate(self,value):
        exact(value,{'ticket','phase','before','after','session','homeBefore','homeController','homeStatuses',
            'controller','statuses','closeSha256'})
        p=self.parent;need(value['phase'] in ('home','closing','closed'))
        original=value['session'];exact(original,{'schemaVersion','processIdentity','sessionNonce','nextSequence'})
        need(type(original['schemaVersion']) is int and original['schemaVersion']==1
            and original['processIdentity']==p.binding['processIdentity'] and type(original['nextSequence']) is int
            and original['nextSequence']>=p.restart.state['newSession']['nextSequence']
            and original['sessionNonce']==p.restart.state['newSession']['sessionNonce'])
        for group in (value['before'],value['after']):
            if group is None:continue
            exact(group,{'frame','home'});p.source().project(group['frame']);p.parent.original_facts(group['frame'])
            row=group['home'];home_packet(row,row['commandId'],int(p.binding['processIdentity'].split(':',1)[0]),row['capturedEpochMs'])
            need(row['tabletShown'] and row['capturedEpochMs']>=group['frame']['after']['ui']['observedEpochMs']
                and row['capturedEpochMs']-group['frame']['before']['ui']['observedEpochMs']<=1500)
        facts=p.source().project(value['before']['frame']);need(facts['panel'] and not facts['bookmark'])
        if value['after'] is not None:
            p.source().advance_frames(value['before']['frame'],value['after']['frame'])
            NavigationGenerationPage(p,self.home,value['before'],value['after'])
        need((value['after'] is not None)==(value['phase']!='home')
            and (value['closeSha256'] is not None)==(value['phase']=='closed'))
        sequence=original['nextSequence']
        for key,statuses,operation in (('homeController','homeStatuses','input.primary'),('controller','statuses','tablet.close')):
            record=value[key]
            if record is not None:
                exact(record,{'envelope','anchor'});envelope=record['envelope'];validate_envelope(envelope,p.runtime['session'].profile)
                a=record['anchor'];exact(a,{'hostMonotonic','nativeEpochMs','fixtureEpochMs'})
                need(all(number(a[k],0 if k=='hostMonotonic' else 1,1e15) for k in a)
                    and -250<=a['nativeEpochMs']-a['fixtureEpochMs']<=1500
                    and envelope['sessionNonce']==original['sessionNonce'] and type(envelope['sequence']) is int
                    and envelope['sequence']==sequence and len(envelope['commands'])==1
                    and envelope['commands'][0]['operation']==operation)
                if operation=='input.primary':
                    observed=value['homeBefore'];need(observed is not None)
                    home_input(observed,int(p.binding['processIdentity'].split(':',1)[0]),observed['capturedEpochMs'],'tablet.home-ray')
                    need(same(envelope['commands'][0]['arguments'],observed_grip_pose(observed['sensorToWorld'],observed['headPosition'],observed['position'])))
                else:need(envelope['commands'][0]['arguments']==dict(holdMilliseconds=1000))
                sequence+=1
            answers=value[statuses];need(type(answers) is list and len(answers)<=128)
            previous=None
            for answer in answers:
                exact(answer,{'status','hostMonotonic'});need(record is not None and number(answer['hostMonotonic'],0,1e15)
                    and (previous is None or answer['hostMonotonic']>=previous));previous=answer['hostMonotonic']
            if key=='homeController' and record is not None and value['phase']!='home':
                need(answers and NavigationBookmarkJoin.neutral(answers[-1]['status'],record['envelope']))
        if value['phase']=='closed':
            need(value['controller'] is not None and value['statuses']
                and NavigationBookmarkJoin.neutral(value['statuses'][-1]['status'],value['controller']['envelope']))

    def load(self):
        body=self.store.read();exact(body,{'navigationGenerationCloseVersion','scope','payload'})
        need(type(body['navigationGenerationCloseVersion']) is int and body['navigationGenerationCloseVersion']==VERSION
            and same(body['scope'],self.parent.scope()))
        rows=unpack(body['payload']);need(len(rows)==1);self.validate(rows[0]);self.disk=deepcopy(body);self.state=rows[0]

    def save(self,value,*,host_only=False):
        if host_only:self.parent.memory_control()
        else:self.parent.control()
        self.validate(value)
        body=dict(navigationGenerationCloseVersion=VERSION,scope=self.parent.scope(),payload=pack([value]))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.state=deepcopy(value)

    def age(self):
        p=self.parent;p.memory_control();need(self.anchor is not None and json_digest(self.anchor)==self.anchor_sha)
        a=self.anchor;now=p.parent.now()
        need(now>=a['hostMonotonic'] and max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def anchor_input(self):
        p=self.parent;p.source().normal.io.original.navigation.io.bind_input();phase=p.fence()
        self.anchor=dict(hostMonotonic=p.parent.now(),nativeEpochMs=p.runtime['native'].clock_ms(),fixtureEpochMs=phase['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor)

    def home_intent(self,stage,before,control):
        need(stage=='tablet-home-ray' and control=='tablet.home-ray' and self.state['phase']=='home'
            and self.state['homeBefore'] is None and self.state['homeController'] is None)
        home_input(before,int(self.parent.binding['processIdentity'].split(':',1)[0]),before['capturedEpochMs'],control)
        value=deepcopy(self.state);value['homeBefore']=deepcopy(before);self.save(value)

    def stage_home(self,pose):
        p=self.parent;before=self.state['homeBefore'];need(before is not None and self.state['homeController'] is None
            and same(pose,observed_grip_pose(before['sensorToWorld'],before['headPosition'],before['position'])))
        self.anchor_input();p.runtime['session'].stage(p.binding['processIdentity'],'input.primary',pose,
            intent=self.home_intent_callback,before_publish=self.home_publish_callback)

    def home_controller_intent(self,envelope):
        self.age();need(self.state['homeController'] is None)
        value=deepcopy(self.state);value['homeController']=dict(envelope=deepcopy(envelope),anchor=deepcopy(self.anchor));self.save(value,host_only=True)
        self.parent.record_controller(envelope,'close-home');self.home_before_publish(envelope)

    def home_before_publish(self,envelope):
        self.parent.controller_recorded(envelope,'close-home');self.age();need(self.state['homeController'] is not None and same(envelope,self.state['homeController']['envelope'])
            and same(self.anchor,self.state['homeController']['anchor']))

    def before_controller(self,operation):
        self.parent.control();need(operation=='tablet.close' and self.state['phase']=='closing' and self.state['controller'] is None)
        self.anchor_input()

    def intent(self,envelope):
        self.age();need(self.state['controller'] is None)
        value=deepcopy(self.state);value['controller']=dict(envelope=deepcopy(envelope),anchor=deepcopy(self.anchor));self.save(value,host_only=True)
        self.parent.record_controller(envelope,'close');self.before_publish(envelope)

    def before_publish(self,envelope):
        self.parent.controller_recorded(envelope,'close');self.age();need(self.state['controller'] is not None and same(envelope,self.state['controller']['envelope'])
            and same(self.anchor,self.state['controller']['anchor']))

    def admit_qml(self,_command):need(False)

    def status(self,key,statuses):
        p=self.parent;p.fence();envelope=self.state[key]['envelope']
        answer=p.runtime['session'].observe_owned_status(p.binding['processIdentity'],envelope)
        value=deepcopy(self.state);value[statuses].append(dict(status=deepcopy(answer),hostMonotonic=p.parent.now()));self.save(value);p.fence()
        return answer

    def neutral(self,key,statuses):
        for attempt in range(81):
            answer=self.status(key,statuses);envelope=self.state[key]['envelope']
            if NavigationBookmarkJoin.neutral(answer,envelope):return
            need(type(answer) is dict and answer.get('enabled') is True and answer.get('state') in ('accepted','active')
                and type(answer.get('acceptedSequence')) is int and answer['acceptedSequence']==envelope['sequence']
                and answer.get('acceptedNonce')=='[redacted]' and answer.get('activeCommandId')==envelope['commands'][0]['id'] and attempt<80)
            self.parent.runtime['native'].sleep(.1)
        need(False)

    def capture(self):
        p=self.parent;phase=p.fence()
        return dict(frame=p.source().capture(p.state['receipt'],phase['status'],lookup_receipt=p.parent.state['lookupReceipt']),home=self.home.source.capture())

    def quiet_status(self):
        if self.state['controller'] is not None:
            answer=self.status('controller','statuses')
            # An active/unknown sample is durably archived before refusing the
            # existing quiet window. It is never silently polled away.
            need(NavigationBookmarkJoin.neutral(answer,self.state['controller']['envelope']))

    def close_owner(self):
        if self.owner is None:
            page=NavigationGenerationPage(self.parent,self.home,self.state['before'],self.state['after'],before_sample=self.quiet_status)
            self.owner=NavigationTabletClose(page,TokenScriptUI(self.parent.source().normal.io.original),self.graphics,
                self.store.path.with_name('navigation-prefix-generation-1-tablet-close.json'),self.parent.fence,
                monotonic=self.parent.parent.monotonic,sleep=self.parent.runtime['native'].sleep)
        return self.owner

    def close(self,ticket):
        p=self.parent;p.control()
        if self.state is None:
            before=self.capture()
            with p.runtime['session']._lock():session=deepcopy(p.runtime['session']._load())
            self.save(dict(ticket=ticket,phase='home',before=before,after=None,session=session,homeBefore=None,
                homeController=None,homeStatuses=[],controller=None,statuses=[],closeSha256=None))
        need(self.state['ticket']==ticket)
        if self.state['phase']=='home':
            if self.state['homeController'] is None:observed=self.home.ensure(self.home_intent)
            else:
                observed=self.home.source.capture();need(observed['onHomeScreen'] and observed['tabletShown'])
            if self.state['homeController'] is not None:self.neutral('homeController','homeStatuses')
            after=self.capture();need(all(after['home'][k]==observed[k] for k in ('instance','tabletId','homeId')))
            value=deepcopy(self.state);value.update(phase='closing',after=after);self.save(value)
        owner=self.close_owner();owner.close(ticket)
        self.neutral('controller','statuses')
        value=deepcopy(self.state);value.update(phase='closed',closeSha256=json_digest(owner.disk));self.save(value)
        return dict(performed=True)
