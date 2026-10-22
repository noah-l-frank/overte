"""Ordinary observer navigation owns its inputs separately from user recipes.

Connections tables must be fetched by the product on each current phase.
Pending invitations are sampled in place: observation never accepts, declines,
cancels or replaces an actual request UUID. Unknown delivery is retained.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator,NativeUIError
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier
from ios.adapters.avatar_controls import AvatarUI,same_reference
from ios.adapters.avatar_input_owner import intent,delivery,observed
from ios.adapters.avatar_sources import IOSAvatarSources

VERSION=2
READS=(1,2)


class AvatarSurfacePending(NativeUIError):pass


class IOSAvatarSurface:
    def __init__(self,store,sources,sdk,*,observer_role,subject_role):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,IOSAvatarSources)
            and not sources.historical and isinstance(sdk,NativeUI)
            and observer_role==sources.role and observer_role in ('primary','actor') and subject_role in ('primary','actor'))
        self.store,self.sources,self.sdk=store,sources,sdk;self.lock=sources.lock
        self.observer_role,self.subject_role=observer_role,subject_role
        need(store.path.name=='ios-avatar-'+observer_role+'-'+subject_role+'-surface.json' and store.path.parent==self.lock.path.parent)
        self.lock.assert_held();self.previous=store.read();self.failed=False
        self.state=dict(calls=[]) if self.previous is None else self.decode(self.previous)

    def envelope(self,state,version=None):
        version=VERSION if version is None else version
        value=deepcopy(state)
        if version>=2:
            for call in value['calls']:call.setdefault('terminal',None)
        return dict(iosAvatarSurfaceVersion=version,binding=self.sources.binding,runId=self.sources.run,
            observerRole=self.observer_role,subjectRole=self.subject_role,payload=pack([value]))

    def reference(self,value):
        need(self.sources.frames and same(value,self.sources.frames[-1]))
        return dict(index=len(self.sources.frames),sha256=digest(value))

    def original(self,ref):
        exact(ref,{'index','sha256'});need(integer(ref['index'],1,len(self.sources.frames)))
        value=self.sources.frames[ref['index']-1];need(digest(value)==ref['sha256']);return value

    def decode(self,value):
        exact(value,{'iosAvatarSurfaceVersion','binding','runId','observerRole','subjectRole','payload'})
        rows=unpack(value['payload']);version=value['iosAvatarSurfaceVersion']
        need(type(version) is int and version in READS and len(rows)==1 and same(value,self.envelope(rows[0],version)))
        state=rows[0];exact(state,{'calls'});need(type(state['calls']) is list and len(state['calls'])<=128)
        for index,call in enumerate(state['calls']):
            exact(call,{'ticket','phase','before','after','sdk','events','invitation'}|({'terminal'} if version>=2 else set()))
            if call.get('terminal') is not None:self.terminal(call)
            identifier(call['ticket']);need(call['phase'] in ('preparing','opening','ready') and type(call['sdk']) is list
                and len(call['sdk'])<=1 and type(call['events']) is list and len(call['events'])<=8)
            for key in ('before','after'):
                if call[key] is not None:
                    frame=self.original(call[key]);need(frame['phaseAfter']['activations'][-1]['ticket']==call['ticket'])
            if call['invitation'] is not None:
                exact(call['invitation'],{'peer','requestId','phase'});identifier(call['invitation']['requestId'].replace('-',''))
                from ios.adapters.avatar_state import session
                session(call['invitation']['peer']);session(call['invitation']['requestId'])
                need(call['invitation']['phase'] in ('incoming','outgoing'))
            for event in call['sdk']:
                exact(event,{'before','after'});need(not self.original(event['before'])['ui']['open'])
                if event['after'] is not None:need(self.original(event['after'])['ui']['open'])
            previous=None
            for event in call['events']:
                exact(event,{'intent','delivery','observed'});intent(event['intent'],self.sources.pid)
                need(event['intent']['controlId'] in ('tablet.home','people.entry','people.nearby','people.connections')
                    or event['intent']['controlId'].startswith('tablet.page.') or version>=2 and event['intent']['controlId']=='people.cancel' and call.get('terminal') is not None)
                if event['intent']['controlId']=='people.cancel':self.terminal_reference(call,event['intent']['reference'])
                if event['delivery'] is not None:delivery(event['delivery'],event['intent'],self.sources.pid)
                else:need(event['observed'] is None)
                if event['observed'] is not None:observed(event['observed'],event['intent'],event['delivery'],self.sources.pid)
                if previous is not None:need(previous['observed'] is not None)
                previous=event
            if index<len(state['calls'])-1 or call['phase']=='ready':
                need(call['phase']=='ready' and call['after'] is not None
                    and all(event['observed'] is not None for event in call['events'])
                    and all(event['after'] is not None for event in call['sdk']))
        return deepcopy(state)

    def terminal(self,call):
        item=call['terminal'];exact(item,{'peer','requestId','phase','admitted'})
        need(self.observer_role==self.subject_role=='actor' and item['phase']=='cancelled')
        from ios.adapters.avatar_state import session
        session(item['peer']);session(item['requestId'])
        admitted=self.original(item['admitted']);before=self.original(call['before'])
        need(admitted['phaseAfter']['activations'][-1]['ticket']!=call['ticket']
            and before['phaseBefore']['activations'][-1]['stimulus']['verb']=='connection-cancel'
            and before['phaseAfter']['activations'][-1]['stimulus']['verb']=='connection-cancel')
        old=AvatarUI.row(admitted['ui'],'people.page');need(old is not None and old['dialog']=='connection'
            and old['connectionState']['phase']=='incoming'
            and all(old['connectionState'][key]==item[key] for key in ('peer','requestId')))
        self.terminal_reference(call,before['ui'])
        return item

    def terminal_reference(self,call,reference):
        item=call['terminal'];page=AvatarUI.row(reference,'people.page')
        need(page is not None and page['dialog']=='connection'
            and all(page['connectionState'].get(key)==item[key] for key in ('peer','requestId','phase')))

    def cancelled(self,before):
        page=AvatarUI.row(before['ui'],'people.page')
        if self.observer_role!=self.subject_role or self.observer_role!='actor' or page is None:return None
        state=page['connectionState']
        if page['dialog']!='connection' or state['phase']!='cancelled':return None
        phase=before['phaseAfter']['activations'][-1]
        if phase['stimulus']['verb']!='connection-cancel':return None
        for call in reversed(self.state['calls']):
            invitation=call['invitation']
            if call['phase']=='ready' and invitation is not None and invitation['phase']=='incoming' and all(invitation[key]==state[key] for key in ('peer','requestId')):
                return dict(peer=state['peer'],requestId=state['requestId'],phase='cancelled',admitted=deepcopy(call['after']))
        return None

    def bound(self):
        self.sources.bound();need(not self.failed and same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def capture(self,ticket):
        self.bound();value=self.sources.read();need(value['phaseBefore']['activations'][-1]['ticket']==ticket
            and value['phaseAfter']['activations'][-1]['ticket']==ticket);return value

    def own_intent(self,value):
        call=self.state['calls'][-1];frame=self.capture(call['ticket']);same_reference(value['reference'],frame['ui'],value['controlId'])
        need(call['phase']=='preparing' and (not call['events'] or call['events'][-1]['observed'] is not None))
        if value['controlId']=='people.cancel':self.terminal(call);self.terminal_reference(call,value['reference'])
        intent(value,self.sources.pid);call['events'].append(dict(intent=deepcopy(value),delivery=None,observed=None));self.save()

    def delivered(self,value,result):
        event=self.state['calls'][-1]['events'][-1];need(same(value,event['intent']) and event['delivery'] is None)
        delivery(result,value,self.sources.pid);event['delivery']=deepcopy(result);self.save()

    def observed(self,value,result):
        event=self.state['calls'][-1]['events'][-1];need(same(value,event['intent']) and event['observed'] is None)
        observed(result,value,event['delivery'],self.sources.pid);event['observed']=deepcopy(result);self.save()

    def prepare(self,ticket):
        identifier(ticket);self.bound()
        for call in self.state['calls']:
            if call['ticket']==ticket:
                if call['phase']!='ready':raise AvatarSurfacePending('Retained observer navigation is unresolved; no ordinary input is resent')
                return self.capture(ticket)
        need(not self.state['calls'] or self.state['calls'][-1]['phase']=='ready')
        before=self.capture(ticket);page=AvatarUI.row(before['ui'],'people.page');terminal=self.cancelled(before)
        if terminal is None and page is not None and page['dialog']=='connection' and page['connectionState']['phase'] not in ('incoming','outgoing'):
            # Primary closes its genuine terminal panel after peer consent.
            # Waiting here has issued no observer input and must not strand a
            # durable navigation recipe or close that panel on its behalf.
            raise AvatarSurfacePending('Waiting for the actual owner to close its terminal connection panel')
        call=dict(ticket=ticket,phase='preparing',before=self.reference(before),after=None,sdk=[],events=[],invitation=None,terminal=terminal)
        self.state['calls'].append(call);self.save()
        if not before['ui']['open']:
            call['sdk'].append(dict(before=self.reference(before),after=None));call['phase']='opening';self.save()
            self.sdk.click(Locator('accessibility id','OverteTabletOpen'))
            after=self.capture(ticket);need(after['ui']['open']);call['sdk'][-1]['after']=self.reference(after);call['phase']='preparing';self.save()
        ui=AvatarUI(self.sources.readers['ui'],self.own_intent,delivered=self.delivered,observed=self.observed,
            monotonic=self.sources.monotonic,sleep=self.sdk.sleep)
        if terminal is not None:
            ui.input('people.cancel');ui.wait(lambda current:bool(ui.row(current,'people.page') and ui.row(current,'people.page')['dialog']=='none'
                and ui.row(current,'people.page')['connectionState']['phase']=='idle'))
        ui.open('people');page=ui.row(ui.capture(),'people.page');need(page is not None)
        if page['dialog']=='connection':
            connection=page['connectionState'];need(connection['phase'] in ('incoming','outgoing'))
            call['invitation']={key:connection[key] for key in ('peer','requestId','phase')};self.save()
        else:
            need(page['dialog']=='none' and page['connectionState']['phase']=='idle');ui.connections()
        after=self.capture(ticket)
        if call['invitation'] is not None:
            page=ui.row(after['ui'],'people.page');need(page is not None and page['dialog']=='connection'
                and all(page['connectionState'][key]==value for key,value in call['invitation'].items()))
        call['after']=self.reference(after);call['phase']='ready';self.save();return after
