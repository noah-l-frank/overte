"""Normal reopen/Places entry into the existing bookmark/Home/Close/Stereo owners.

This is the eleventh child of one unchanged Navigation recipe, not a second
Journey. Input records never supply the arrival, root death or image verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,need,number
from adapters.native_navigation_directory import joined_directory,continuation as directory_advance
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.graphics_source import validate as graphics_packet,accept_inventory,PROFILES
from adapters.pico4.navigation_transit_join import NavigationTransitJoin
from adapters.pico4.tablet_home import validate as home_packet
from adapters.script_journey.history import pack,unpack,same
from adapters.token_places_ui import TokenPlacesUI,sha
from adapters.token_create_ui import scope,nonce
from feature_journeys.contract import identifier
from feature_journeys.fixtures import context as fixture_context
from openxr_input.controller_protocol import validate_envelope

VERSION=1


class NavigationBookmarkJoin:
    def __init__(self,parent,transit_factory,path):
        need(callable(transit_factory))
        prior=parent.dismiss();need(prior.state is not None and prior.state['phase']=='closed')
        self.parent,self.factory,self.prior=parent,transit_factory,prior
        self.prior_sha=json_digest(prior.disk);self.close_sha=prior.state['closeSha256'];self.prior_close=prior.close_original()
        self.previous=deepcopy(prior.state['controller']['envelope'])
        self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None;self.child=None
        self.ui=TokenPlacesUI(parent.source.normal.io,self.entry_intent,parent.run,
            monotonic=parent.monotonic,sleep=parent.source.normal.sleep)
        self.anchor=self.anchor_sha=None
        if self.disk is not None:self.load()

    def context(self,*,memory_only=False):
        p=self.parent;p.lock.assert_held();p.control()
        need(p.role=='primary' and same(p.state,p.disk) and p.state['phase']=='acting'
            and p.state['active']['verb']=='bookmark-visit' and p.state['active']['stage']=='return')
        self.bound(memory_only=memory_only)
        if self.state is not None:
            need(self.disk is not None and same(unpack(self.disk['payload']),[self.state]))
            if not memory_only:need(same(self.store.read(),self.disk))

    def bound(self,*,memory_only=False):
        need(json_digest(self.prior.disk)==self.prior_sha and same(self.prior.state,self.prior.disk)
            and self.prior.state['phase']=='closed' and self.prior.state['closeSha256']==self.close_sha
            and self.prior.close_owner is self.prior_close and json_digest(self.prior_close.disk)==self.close_sha)
        if not memory_only:
            need(same(self.prior.store.read(),self.prior.disk)
                and same(self.prior_close.store.read(),self.prior_close.disk))

    def archive(self,group):
        exact(group,{'frame','home','graphics'})
        p=self.parent;frame,home,graphics=group['frame'],group['home'],group['graphics']
        facts=p.source.project(frame);p.original_facts(frame)
        need(facts['location']=='B' and facts['bookmark'] and facts['bookmarkName']==fixture_context(p.run)['renamed']
            and not facts['panel'] and not facts['addressDialog'] and facts['error']=='none')
        pid=int(p.binding['processIdentity'].split(':',1)[0]);epoch=graphics['capturedEpochMs']
        home_packet(home,home.get('commandId'),pid,epoch);graphics_packet(graphics,graphics.get('commandId'),pid,epoch)
        need(frame['before']['ui']['open']==frame['after']['ui']['open']
            and all(frame[side]['ui']['ready']==frame[side]['ui']['open'] for side in ('before','after'))
            and home['onHomeScreen'] and home['tabletShown']==graphics['tabletShown']==frame['after']['ui']['open']
            and not graphics['editorFocused'] and not graphics['graphicsInventory']['keyboard3D']['raised']
            and not graphics['graphicsInventory']['roots']
            and 0<=home['capturedEpochMs']-frame['after']['ui']['observedEpochMs']<=1500
            and 0<=epoch-home['capturedEpochMs']<=1500 and epoch-frame['before']['ui']['observedEpochMs']<=1500)

    def page_original(self,group,ticket,before,after):
        p=self.parent;page=p.directory.archive(group)
        frame=after['frame'];p.directory.advance(dict(ui=frame['after']['ui'],native=frame['after']['directory'],provider=frame['provider']),group)
        need(page['querySha256']==sha('') and page['queryLength']==0
            and page['rootInstance'] not in {row['rootId'] for row in before['frame']['after']['directory']['roots']})
        joined_directory(group['native'],group['ui'],group['provider'],run=p.run,ticket=ticket,
            after_epoch=before['frame']['before']['ui']['observedEpochMs'],owned_origin=p.source.origin,
            provider_instance=p.source.provider_instance,provider_inputs=p.source.inputs,source_profile=p.source.profile)
        return page

    def validate(self,value):
        exact(value,{'ticket','phase','before','after','page','controller','pending','history','qml','transitJoinSha256','openStatuses'})
        p=self.parent;identifier(value['ticket'])
        need(value['phase'] in ('opening','entry','transit','closed') and type(value['qml']) is list and len(value['qml'])<=40
            and type(value['history']) is list and len(value['history'])<=32
            and (any(row['ticket']==value['ticket'] and row['verb']=='bookmark-visit' for row in p.state['completed'])
                or p.state['active'] is not None and p.state['active']['ticket']==value['ticket'] and p.state['active']['verb']=='bookmark-visit'))
        self.archive(value['before']);need(not value['before']['graphics']['tabletShown'])
        need((value['after'] is not None)==(value['phase']!='opening')
            and (value['page'] is not None)==(value['phase'] in ('transit','closed'))
            and (value['transitJoinSha256'] is not None)==(value['phase']=='closed'))
        if value['after'] is not None:
            a,b=value['before'],value['after'];self.archive(b);need(b['graphics']['tabletShown'])
            p.source.advance_frames(a['frame'],b['frame'])
            x,y=a['frame']['after']['ui']['scope'],b['frame']['before']['ui']['scope']
            need(x['sequence']==y['sequence'] and x['generation']!=y['generation'])
            for name in ('home','graphics'):
                x,y=a[name],b[name]
                need(x['instance']==y['instance'] and x['generation']==y['generation']
                    and y['sourceSequence']>x['sourceSequence'] and y['commandId']!=x['commandId']
                    and y['capturedEpochMs']>=x['capturedEpochMs'] and y['elapsedMs']>=x['elapsedMs'])
            need(all(a['home'][key]==b['home'][key] for key in ('tabletId','homeId')))
            accept_inventory(a['graphics']['graphicsInventory'],b['graphics']['graphicsInventory'],profiles=PROFILES)
        record=value['controller']
        if record is not None:
            exact(record,{'envelope','sha256','anchor'});envelope=record['envelope'];validate_envelope(envelope,p.session.profile)
            a=record['anchor'];exact(a,{'hostMonotonic','nativeEpochMs','fixtureEpochMs'})
            need(type(envelope['schemaVersion']) is int and envelope['sessionNonce']==self.previous['sessionNonce'] and type(envelope['sequence']) is int
                and envelope['sequence']==self.previous['sequence']+1 and record['sha256']==json_digest(envelope)
                and len(envelope['commands'])==1 and envelope['commands'][0]['operation']=='tablet.open'
                and envelope['commands'][0]['arguments']==dict(holdMilliseconds=1000)
                and all(number(a[key],0 if key=='hostMonotonic' else 1,1e15) for key in a)
                and -250<=a['nativeEpochMs']-a['fixtureEpochMs']<=1500)
        need(type(value['openStatuses']) is list and len(value['openStatuses'])<=96)
        previous=None
        for answer in value['openStatuses']:
            exact(answer,{'status','hostMonotonic'})
            need(record is not None and number(answer['hostMonotonic'],0,1e15)
                and (previous is None or answer['hostMonotonic']>=previous))
            previous=answer['hostMonotonic']
        if value['phase']!='opening':need(record is not None and value['openStatuses'] and self.neutral(value['openStatuses'][-1]['status'],record['envelope']))
        for pending in value['history']+([] if value['pending'] is None else [value['pending']]):
            exact(pending,{'placesInputVersion','action','controlId','controlToken','scope'});scope(pending['scope'])
            need(type(pending['placesInputVersion']) is int and pending['placesInputVersion']==1
                and pending['action']=='activate' and nonce(pending['controlToken'])
                and (pending['controlId']=='places.entry' or pending['controlId'].startswith('tablet.page.'))
                and pending['scope']['instance']==p.binding['sessionId'])
        for command in value['qml']:need(any(same(command,row) for row in p.state['deliveries']))
        if value['page'] is not None:
            self.page_original(value['page'],value['ticket'],value['before'],value['after']);need(value['pending'] is None)
        if value['transitJoinSha256'] is not None:self.transit_original(value)
        if value['page'] is not None and self.child is not None and self.child.transit.state is not None:
            original=self.child.transit.state['original'];page=value['page'];old=self.ui.page(page['ui']);new=self.ui.page(original['ui'])
            need(all(original['ui']['scope'][key]==page['ui']['scope'][key] for key in ('instance','processId','generation','sequence'))
                and all(new[key]==old[key] for key in ('rootInstance','componentSourceSha256','currentAddressSha256','querySha256','queryLength'))
                and same(original['bookmarks']['storage'],value['after']['frame']['after']['bookmarks']['storage']))
            directory_advance(page['native'],original['roots'])
        if value['transitJoinSha256'] is not None:
            child=self.transit_original(value)
            need(child.state is not None and child.state['phase']=='closed' and value['transitJoinSha256']==json_digest(child.disk))

    def load(self):
        body=self.store.read();exact(body,{'navigationBookmarkJoinVersion','runId','binding','parentScopeSha256','priorDismissalSha256','priorCloseSha256','payload'})
        p=self.parent;need(type(body['navigationBookmarkJoinVersion']) is int and body['navigationBookmarkJoinVersion']==VERSION
            and body['runId']==p.run and same(body['binding'],p.binding) and body['parentScopeSha256']==p.scope_sha
            and body['priorDismissalSha256']==self.prior_sha and body['priorCloseSha256']==self.close_sha)
        rows=unpack(body['payload']);need(len(rows)==1);self.validate(rows[0]);self.disk=deepcopy(body);self.state=rows[0]

    def save(self,value):
        p=self.parent;p.lock.assert_held();self.validate(value)
        body=dict(navigationBookmarkJoinVersion=VERSION,runId=p.run,binding=deepcopy(p.binding),parentScopeSha256=p.scope_sha,
            priorDismissalSha256=self.prior_sha,priorCloseSha256=self.close_sha,payload=pack([value]))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.state=deepcopy(value)

    def sample(self):
        p=self.parent;current=p.fence();started=p.now()
        frame=p.source.capture(p.state['receipt'],current['status'],lookup_receipt=p.state['lookupReceipt'])
        # The existing Home entity source is shared with the preceding lookup;
        # querying it does not mutate its completed Close journal.
        group=dict(frame=frame,home=self.prior.lookup.home.source.capture(),graphics=self.prior.graphics.capture())
        self.archive(group);return group,started

    def fresh(self,group,started):
        p=self.parent;p.fence();epoch=p.source.clock_ms();now=p.now()
        need(number(epoch,1,1e15) and max(epoch-group['frame']['before']['ui']['observedEpochMs'],(now-started)*1000)<=1500)

    def entry_intent(self,pending):
        self.context();need(self.state['phase']=='entry')
        current=deepcopy(self.state);old=current['pending']
        if old is not None:
            need(pending['scope']['instance']==old['scope']['instance'] and pending['scope']['processId']==old['scope']['processId']
                and pending['scope']['sequence']==old['scope']['sequence']+1)
            current['history'].append(old)
        current['pending']=deepcopy(pending);self.save(current)

    def pending_input(self):
        need(self.state is not None)
        if self.state['phase']=='entry':return self.state['pending']
        need(self.state['phase']=='transit');return self.transit_original().transit.state['pending']['input']

    def record_qml(self,command):
        self.context()
        if self.state['phase']=='transit':self.transit_original().record_qml(command);return
        need(self.state['phase']=='entry' and self.state['pending'] is not None)
        current=deepcopy(self.state);current['qml'].append(deepcopy(command));self.save(current)

    def before_controller(self,operation):
        self.context()
        if self.state['phase']=='transit':self.transit_original().before_controller(operation);return
        need(self.state['phase']=='opening' and operation=='tablet.open' and self.state['controller'] is None)
        p=self.parent;current=p.fence()
        self.anchor=dict(hostMonotonic=p.now(),nativeEpochMs=p.source.clock_ms(),fixtureEpochMs=current['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor);self.age()

    def age(self):
        self.context(memory_only=True);need(self.anchor is not None and self.anchor_sha==json_digest(self.anchor))
        a=self.anchor;now=self.parent.now()
        need(now>=a['hostMonotonic'] and max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def intent(self,envelope):
        if self.state['phase']=='transit':self.transit_original().intent(envelope);return
        self.age();need(self.state['controller'] is None)
        current=deepcopy(self.state);current['controller']=dict(envelope=deepcopy(envelope),sha256=json_digest(envelope),anchor=deepcopy(self.anchor))
        self.save(current);self.before_publish(envelope)

    def before_publish(self,envelope):
        if self.state['phase']=='transit':self.transit_original().before_publish(envelope);return
        self.age();record=self.state['controller']
        need(record is not None and same(record['anchor'],self.anchor) and record['sha256']==json_digest(envelope) and same(record['envelope'],envelope))

    def transit_original(self,value=None):
        value=self.state if value is None else value
        need(value is not None and value['controller'] is not None)
        if self.child is None:
            child=self.factory(value['controller']['envelope'])
            need(isinstance(child,NavigationTransitJoin) and child.parent is self.parent and child.kind=='bookmark'
                and same(child.prior,value['controller']['envelope']))
            self.child=child
        need(same(self.child.prior,value['controller']['envelope']))
        return self.child

    @staticmethod
    def neutral(status,envelope):
        return (type(status) is dict and status.get('enabled') is True and status.get('state')=='neutral'
            and type(status.get('acceptedSequence')) is int and status['acceptedSequence']==envelope['sequence']
            and status.get('acceptedNonce')=='[redacted]' and status.get('activeCommandId')=='')

    def await_open_neutral(self):
        # The original Session refuses an uncertain transport-grant/host-save
        # boundary. Do not adopt its cursor or send any Qt/controller input.
        # Every actual answer is retained before assessing it; native transition
        # updatedEpochMs is never advanced or treated as a sampling clock.
        p=self.parent;envelope=self.state['controller']['envelope']
        for attempt in range(81):
            p.fence();status=p.session.observe_owned_status(p.binding['processIdentity'],envelope)
            current=deepcopy(self.state);current['openStatuses'].append(dict(status=deepcopy(status),hostMonotonic=p.now()))
            self.save(current);p.fence()
            if self.neutral(status,envelope):return
            need(type(status) is dict and status.get('enabled') is True and status.get('state') in ('accepted','active')
                and type(status.get('acceptedSequence')) is int and status['acceptedSequence']==envelope['sequence']
                and status.get('acceptedNonce')=='[redacted]' and status.get('activeCommandId')==envelope['commands'][0]['id']
                and attempt<80)
            p.source.normal.sleep(.1)
        need(False)

    def act(self,ticket):
        self.context()
        if self.state is None:
            before,started=self.sample();need(not before['graphics']['tabletShown'])
            self.save(dict(ticket=ticket,phase='opening',before=before,after=None,page=None,controller=None,
                pending=None,history=[],qml=[],transitJoinSha256=None,openStatuses=[]));self.fresh(before,started)
            # One uncertain open is observed on cold recovery, never reissued.
            self.prior.normal.io.tablet(True)
        need(self.state['ticket']==ticket)
        if self.state['phase']=='opening':
            need(self.state['controller'] is not None)
            self.await_open_neutral()
            after,started=self.sample();need(after['graphics']['tabletShown'])
            current=deepcopy(self.state);current.update(phase='entry',after=after);self.save(current);self.fresh(after,started)
        if self.state['phase']=='entry':
            if self.state['pending'] is not None:
                value=self.ui.capture();pending=self.state['pending'];old=pending['scope']
                need(value['scope']['instance']==old['instance'] and value['scope']['processId']==old['processId']
                    and value['scope']['sequence']==old['sequence']+1 and pending['controlId']=='places.entry'
                    and self.ui.row(value,'places.page',enabled=False) is not None)
                current=deepcopy(self.state);current['history'].append(current['pending']);current['pending']=None;self.save(current)
            self.parent.fence();self.ui.open()
            p=self.parent;started=p.now();group=dict(ui=self.ui.capture(),native=p.source.readers['directory'].read(p.run),provider=p.source.status())
            self.page_original(group,ticket,self.state['before'],self.state['after']);current=deepcopy(self.state)
            if current['pending'] is not None:current['history'].append(current['pending']);current['pending']=None
            current.update(phase='transit',page=group);self.save(current);p.fence()
            need(max(p.source.clock_ms()-group['ui']['observedEpochMs'],(p.now()-started)*1000)<=1500)
        if self.state['phase']=='transit':
            child=self.transit_original();self.parent.fence();child.act(ticket)
            current=deepcopy(self.state);current.update(phase='closed',transitJoinSha256=json_digest(child.disk));self.save(current)
        self.parent.fence();return dict(performed=True)
