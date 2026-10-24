"""In-progress normal G1 controller/Home/Places opening and original adoption.

This child receives no desired result. It joins actual new normal controls to
current directory READY/read/message/root provenance before using the existing
bookmark handoff. No original G0/UI/Session journal is rebound or overwritten.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import json_digest
from adapters.android.input_geometry import observed_grip_pose
from adapters.native_feature_observation import need,exact,number
from adapters.native_navigation_directory import joined_directory
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.pico4.graphics_source import validate as graphics_packet
from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
from adapters.pico4.tablet_home import validate as home_packet,validate_input as home_input
from adapters.script_journey.history import same,pack,unpack
from adapters.token_places_ui import TokenPlacesUI,sha
from openxr_input.controller_protocol import validate_envelope

VERSION=1


class NavigationGenerationOpen:
    def __init__(self,parent,directory,home,graphics,adopt):
        need(callable(adopt));self.parent,self.directory,self.home,self.graphics,self.adopt=parent,directory,home,graphics,adopt
        self.store=PrivateFeatureState(parent.lock.path.with_name('navigation-prefix-generation-1-open.json'))
        self.disk=self.store.read();self.state=None;self.anchor=None;self.anchor_sha=None
        self.ui=TokenPlacesUI(parent.source().normal.io,self.entry_intent,parent.run,
            monotonic=parent.parent.monotonic,sleep=parent.runtime['native'].sleep)
        self.home.stage=self.stage_home
        self.home_intent_callback=self.home_controller_intent;self.home_publish_callback=self.home_before_publish
        if self.disk is not None:self.load()

    def validate(self,value):
        exact(value,{'ticket','phase','before','after','controller','statuses','pending','history','page','adoptedSha256',
            'homeBefore','homeAfter','homeController','homeStatuses','adoptedOriginal','graphics'})
        need(value['phase'] in ('opening','home','entry','ready') and type(value['statuses']) is list and len(value['statuses'])<=96
            and type(value['history']) is list and len(value['history'])<=32)
        for frame in [value['before']]+([] if value['after'] is None else [value['after']]):
            self.parent.source().project(frame);self.parent.parent.original_facts(frame)
        need(not value['before']['before']['ui']['open'] and not value['before']['after']['ui']['open'])
        if value['after'] is not None:
            need(value['after']['after']['ui']['open']);self.parent.source().advance_frames(value['before'],value['after'])
        record=value['controller']
        if record is not None:
            exact(record,{'envelope','anchor'});envelope=record['envelope'];validate_envelope(envelope,self.parent.runtime['session'].profile)
            old=self.parent.restart.state['newSession']
            need(type(envelope['schemaVersion']) is int and envelope['sessionNonce']==old['sessionNonce']
                and type(envelope['sequence']) is int and envelope['sequence']==old['nextSequence']
                and len(envelope['commands'])==1 and envelope['commands'][0]['operation']=='tablet.open'
                and envelope['commands'][0]['arguments']==dict(holdMilliseconds=1000))
        for pending in value['history']+([] if value['pending'] is None else [value['pending']]):
            exact(pending,{'placesInputVersion','action','controlId','controlToken','scope'})
            need(type(pending['placesInputVersion']) is int and pending['placesInputVersion']==1 and pending['action']=='activate'
                and (pending['controlId']=='places.entry' or pending['controlId'].startswith('tablet.page.'))
                and pending['scope']['instance']==self.parent.binding['sessionId']
                and pending['scope']['processId']==int(self.parent.binding['processIdentity'].split(':',1)[0]))
        previous=None
        for answer in value['statuses']:
            exact(answer,{'status','hostMonotonic'});need(number(answer['hostMonotonic'],0,1e15)
                and (previous is None or answer['hostMonotonic']>=previous));previous=answer['hostMonotonic']
        if value['phase']!='opening':need(record is not None and value['statuses']
            and NavigationBookmarkJoin.neutral(value['statuses'][-1]['status'],record['envelope']) and value['after'] is not None)
        if value['phase']=='ready':
            need(value['page'] is not None and value['adoptedSha256'] is not None and value['pending'] is None
                and value['adoptedOriginal'] is not None and json_digest(value['adoptedOriginal'])==value['adoptedSha256'])
            original=NavigationBookmarks.archive(value['adoptedOriginal'])
            need(same(original['binding'],self.parent.binding) and original['original']['rootInstance']==self.directory.archive(value['page'])['rootInstance']
                and original['active'] is None and not original['completed'])
        else:need(value['adoptedOriginal'] is None and value['adoptedSha256'] is None)
        pid=int(self.parent.binding['processIdentity'].split(':',1)[0])
        for name in ('homeBefore','homeAfter'):
            row=value[name]
            if row is not None:
                home_packet(row,row['commandId'],pid,row['capturedEpochMs']);need(row['tabletShown'])
        if value['homeAfter'] is not None:need(value['homeAfter']['onHomeScreen'])
        if value['phase'] in ('entry','ready'):need(value['homeAfter'] is not None)
        if value['homeController'] is not None:
            record=value['homeController'];exact(record,{'envelope','anchor'});envelope=record['envelope']
            validate_envelope(envelope,self.parent.runtime['session'].profile);before=value['homeBefore'];need(before is not None)
            need(envelope['sessionNonce']==value['controller']['envelope']['sessionNonce']
                and envelope['sequence']==value['controller']['envelope']['sequence']+1 and len(envelope['commands'])==1
                and envelope['commands'][0]['operation']=='input.primary'
                and same(envelope['commands'][0]['arguments'],observed_grip_pose(before['sensorToWorld'],before['headPosition'],before['position'])))
        need(type(value['homeStatuses']) is list and len(value['homeStatuses'])<=96)
        for answer in value['homeStatuses']:
            exact(answer,{'status','hostMonotonic'});need(number(answer['hostMonotonic'],0,1e15))
        if value['homeController'] is not None and value['phase'] in ('entry','ready'):
            need(value['homeStatuses'] and NavigationBookmarkJoin.neutral(value['homeStatuses'][-1]['status'],value['homeController']['envelope']))
        if value['page'] is not None:self.page(value['page'],value)
        need(type(value['graphics']) is list and len(value['graphics'])<=2)
        for packet in value['graphics']:
            graphics_packet(packet,packet['commandId'],pid,packet['capturedEpochMs'])
            need(packet['tabletShown'] and not packet['editorFocused'] and not packet['graphicsInventory']['keyboard3D']['raised']
                and not packet['graphicsInventory']['roots'])
        if value['phase']=='ready':need(len(value['graphics'])==1)

    def load(self):
        body=self.store.read();exact(body,{'navigationGenerationOpenVersion','scope','payload'})
        need(type(body['navigationGenerationOpenVersion']) is int and body['navigationGenerationOpenVersion']==VERSION
            and same(body['scope'],self.parent.scope()))
        rows=unpack(body['payload']);need(len(rows)==1);self.validate(rows[0]);self.disk=deepcopy(body);self.state=rows[0]

    def save(self,value,*,host_only=False):
        if host_only:self.parent.memory_control()
        else:self.parent.control()
        self.validate(value)
        body=dict(navigationGenerationOpenVersion=VERSION,scope=self.parent.scope(),payload=pack([value]))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.state=deepcopy(value)

    def page(self,group,value):
        page=self.directory.archive(group);p=self.parent
        need(page['rootInstance'] not in {row['rootId'] for row in value['before']['after']['directory']['roots']}
            and page['rootInstance']!=p.parent.bookmarks.store.read()['original']['rootInstance']
            and page['querySha256']==sha('') and page['queryLength']==0)
        entry=[row for row in value['history'] if row['controlId']=='places.entry'];need(len(entry)==1)
        # Actual new READY traffic must follow the exact ordinary Entry's
        # original frame barrier, not the predecessor's first open receipt.
        joined_directory(group['native'],group['ui'],group['provider'],run=p.run,ticket=value['ticket'],
            after_epoch=value['after']['before']['ui']['observedEpochMs'],owned_origin=p.parent.source.origin,
            provider_instance=p.parent.source.provider_instance,provider_inputs=p.parent.source.inputs,source_profile=p.parent.source.profile)
        return page

    def before_controller(self,operation):
        p=self.parent;p.control();need(operation=='tablet.open' and self.state is not None
            and self.state['phase']=='opening' and self.state['controller'] is None)
        phase=p.fence();self.anchor=dict(hostMonotonic=p.parent.now(),nativeEpochMs=p.runtime['native'].clock_ms(),fixtureEpochMs=phase['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor)

    def age(self):
        p=self.parent;p.memory_control();need(self.anchor is not None and json_digest(self.anchor)==self.anchor_sha)
        a=self.anchor;now=p.parent.now()
        need(now>=a['hostMonotonic'] and max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def intent(self,envelope):
        self.age();need(self.state['controller'] is None)
        value=deepcopy(self.state);value['controller']=dict(envelope=deepcopy(envelope),anchor=deepcopy(self.anchor));self.save(value,host_only=True)
        self.parent.record_controller(envelope,'open');self.before_publish(envelope)

    def before_publish(self,envelope):
        self.parent.controller_recorded(envelope,'open');self.age();need(self.state['controller'] is not None and same(envelope,self.state['controller']['envelope'])
            and same(self.anchor,self.state['controller']['anchor']))

    def home_intent(self,stage,before,control):
        need(stage=='tablet-home-ray' and control=='tablet.home-ray' and self.state['phase']=='home'
            and self.state['homeBefore'] is None and self.state['homeController'] is None)
        home_input(before,int(self.parent.binding['processIdentity'].split(':',1)[0]),before['capturedEpochMs'],control)
        value=deepcopy(self.state);value['homeBefore']=deepcopy(before);self.save(value)

    def stage_home(self,pose):
        p=self.parent;p.control();before=self.state['homeBefore'];need(before is not None and self.state['homeController'] is None
            and same(pose,observed_grip_pose(before['sensorToWorld'],before['headPosition'],before['position'])))
        source=p.source();source.normal.io.original.navigation.io.bind_input();phase=p.fence()
        self.anchor=dict(hostMonotonic=p.parent.now(),nativeEpochMs=p.runtime['native'].clock_ms(),fixtureEpochMs=phase['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor)
        p.runtime['session'].stage(p.binding['processIdentity'],'input.primary',pose,
            intent=self.home_intent_callback,before_publish=self.home_publish_callback)

    def home_controller_intent(self,envelope):
        self.age();need(self.state['homeController'] is None)
        value=deepcopy(self.state);value['homeController']=dict(envelope=deepcopy(envelope),anchor=deepcopy(self.anchor));self.save(value,host_only=True)
        self.parent.record_controller(envelope,'open-home');self.home_before_publish(envelope)

    def home_before_publish(self,envelope):
        self.parent.controller_recorded(envelope,'open-home');self.age();need(self.state['homeController'] is not None and same(envelope,self.state['homeController']['envelope'])
            and same(self.anchor,self.state['homeController']['anchor']))

    def entry_intent(self,pending):
        self.parent.control();need(self.state['phase']=='entry' and self.state['pending'] is None)
        # Each actual normal page/Entry input is issued at most once. Current
        # sequence alone is consumption metadata, never a loaded-page result.
        need(not any(row['controlId']==pending['controlId'] for row in self.state['history']))
        value=deepcopy(self.state);value['pending']=deepcopy(pending);self.save(value)

    def admit_qml(self,command):
        self.parent.control();pending=self.state['pending'];need(self.state['phase']=='entry' and pending is not None)
        scope=pending['scope'];need(command['controlId']==pending['controlId'] and command['controlToken']==pending['controlToken']
            and command['action']=='activate' and command['bridgeId']==scope['instance']
            and command['generation']==scope['generation'] and command['sequence']==scope['sequence']+1)

    def current_page(self):
        p=self.parent;return dict(ui=self.ui.capture(),native=self.directory.native.read(p.run),provider=self.directory.status())

    def wait_stream(self,controller,statuses):
        p=self.parent;started=p.parent.now()
        for _ in range(81):
            p.fence();answer=p.runtime['session'].observe_owned_status(p.binding['processIdentity'],self.state[controller]['envelope'])
            value=deepcopy(self.state);value[statuses].append(dict(status=deepcopy(answer),hostMonotonic=p.parent.now()));self.save(value)
            if NavigationBookmarkJoin.neutral(answer,self.state[controller]['envelope']):return
            p.fence();envelope=self.state[controller]['envelope']
            need(type(answer) is dict and answer.get('enabled') is True and answer.get('state') in ('accepted','active')
                and type(answer.get('acceptedSequence')) is int and answer['acceptedSequence']==envelope['sequence']
                and answer.get('acceptedNonce')=='[redacted]' and answer.get('activeCommandId')==envelope['commands'][0]['id']
                and p.parent.now()-started<=8);p.runtime['native'].sleep(.1)
        need(False)

    def advance_pending(self):
        pending=self.state['pending']
        if pending is None:return
        group=self.current_page();scope=group['ui']['scope'];old=pending['scope']
        need(all(scope[key]==old[key] for key in ('instance','processId')) and scope['sequence']==old['sequence']+1)
        if pending['controlId']=='places.entry':need(self.ui.row(group['ui'],'places.page',enabled=False) is not None)
        value=deepcopy(self.state);value['history'].append(deepcopy(pending));value['pending']=None;self.save(value)

    def act(self,ticket):
        p=self.parent;p.control()
        if self.state is None:
            phase=p.fence();before=p.source().capture(p.state['receipt'],phase['status'],lookup_receipt=p.parent.state['lookupReceipt'])
            self.save(dict(ticket=ticket,phase='opening',before=before,after=None,controller=None,statuses=[],pending=None,history=[],page=None,adoptedSha256=None,
                homeBefore=None,homeAfter=None,homeController=None,homeStatuses=[],adoptedOriginal=None,graphics=[]))
        need(self.state['ticket']==ticket)
        if self.state['phase']=='opening':
            if self.state['controller'] is None:p.source().normal.io.original.tablet(True)
            # Archive every original answer, including active/unknown, rather
            # than polling those away inside a neutral-only helper. No restage.
            self.wait_stream('controller','statuses')
            phase=p.fence();after=p.source().capture(p.state['receipt'],phase['status'],lookup_receipt=p.parent.state['lookupReceipt'])
            value=deepcopy(self.state);value.update(phase='home',after=after);self.save(value)
        if self.state['phase']=='home':
            if self.state['homeController'] is None:observed=self.home.ensure(self.home_intent)
            else:
                # A previously issued ray is never restaged. A hidden or
                # missing effect remains owned and unavailable.
                observed=self.home.source.capture();need(observed['onHomeScreen'] and observed['tabletShown'])
            if self.state['homeController'] is not None:self.wait_stream('homeController','homeStatuses')
            value=deepcopy(self.state);value.update(phase='entry',homeAfter=deepcopy(observed));self.save(value)
        if self.state['phase']=='entry':
            self.advance_pending();current=self.ui.capture()
            if self.ui.row(current,'places.page',enabled=False) is None:
                # New process baseline must already be its real ordinary Home;
                # a retained foreign surface is not repaired by test setters.
                observed=self.home.source.capture();need(observed['onHomeScreen'] and observed['tabletShown'])
                controls=[row['id'] for row in current['controls'] if row['id'].startswith('tablet.page.')]
                visited={row['controlId'] for row in self.state['history']}
                if self.ui.row(current,'places.entry') is None:
                    remaining=sorted(set(controls)-visited,key=lambda value:int(value.rsplit('.',1)[1]));need(remaining)
                    for control in remaining:
                        self.ui.input(control);self.advance_pending();current=self.ui.capture()
                        if self.ui.row(current,'places.entry') is not None:break
                need(self.ui.row(current,'places.entry') is not None)
                self.ui.input('places.entry');self.advance_pending()
            self.ui.idle();group=self.current_page();value=deepcopy(self.state);value['page']=group;self.page(group,value)
            # Existing original handoff, after actual normal entry and READY.
            adopted=self.adopt();actual=self.graphics.capture();p.fence()
            need(actual['capturedEpochMs']>=group['native']['capturedEpochMs'] and actual['capturedEpochMs']-group['ui']['observedEpochMs']<=1500)
            value.update(phase='ready',adoptedSha256=json_digest(adopted.store.read()),adoptedOriginal=deepcopy(adopted.state),graphics=[actual])
            self.save(value)
        return dict(performed=True)
