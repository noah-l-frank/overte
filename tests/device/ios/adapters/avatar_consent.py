"""Durable ordinary accept/decline on the independent actual actor SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import exact,integer,need
from adapters.native_account_observation import validate as account_original
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator,NativeUIError
from adapters.script_feature.history import canonical,pack,unpack,same
from feature_journeys.contract import arguments
from ios.adapters import avatar_state,avatar_renderers
from ios.adapters.avatar_controls import AvatarUI,same_reference
from ios.adapters.avatar_input_owner import AvatarInputOwner
from ios.adapters.avatar_sources import IOSAvatarSources

VERSION=1


class AvatarConsentPending(NativeUIError):pass


class IOSAvatarConsent:
    def __init__(self,store,sources,inputs,sdk,peer,username,owned_origin):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,IOSAvatarSources) and not sources.historical
            and sources.role=='actor' and isinstance(inputs,AvatarInputOwner) and isinstance(sdk,NativeUI))
        avatar_state.session(peer);need(type(username) is str and username.startswith('e2e-') and avatar_state.identity(username[4:]))
        from ios.adapters.authentication_origin import origin
        need(origin(owned_origin+'/feature-fixture/v1')==owned_origin and inputs.binding==sources.binding and inputs.run==sources.run
            and inputs.role=='actor' and inputs.lock is sources.lock and inputs.fixture_url==sources.phase.fixture_url
            and store.path.name=='ios-avatar-actor-consent.json')
        self.store,self.sources,self.inputs,self.sdk=store,sources,inputs,sdk
        self.peer,self.username,self.origin=peer,username,owned_origin
        self.previous=store.read();self.failed=False;self.lock=sources.lock;self.lock.assert_held()
        self.state=dict(calls=[]) if self.previous is None else self.decode(self.previous);inputs.load()
        owned=[call for call in self.state['calls'] if call['inputStarted']]
        need(len(owned)==len(inputs.state['calls']))
        for call,event in zip(owned,inputs.state['calls']):
            need(same(call['query'],event['arguments']) and (call['phase']!='acknowledged' or event['phase']=='acknowledged'))
            for item in event['events']:
                if item['intent']['controlId'] in ('people.accept','people.decline'):
                    self.invitation_reference(call,item['intent']['reference'],item['intent']['controlId'])

    def envelope(self,state):return dict(iosAvatarConsentVersion=VERSION,binding=self.sources.binding,runId=self.sources.run,
        peer=self.peer,username=self.username,origin=self.origin,payload=pack([state]))

    def reference(self,frame):
        need(self.sources.frames and same(frame,self.sources.frames[-1]))
        return dict(revision=len(self.sources.frames),sha256=hashlib.sha256(canonical(frame)).hexdigest())

    def original(self,reference):
        exact(reference,{'revision','sha256'});need(integer(reference['revision'],1,len(self.sources.frames)))
        frame=self.sources.frames[reference['revision']-1]
        need(frame.get('avatarSourceGroupVersion')==2 and hashlib.sha256(canonical(frame)).hexdigest()==reference['sha256']);return frame

    def decode(self,value):
        exact(value,{'iosAvatarConsentVersion','binding','runId','peer','username','origin','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'calls'});need(type(state['calls']) is list and len(state['calls'])<=16);tickets=set();invitations=set()
        for index,call in enumerate(state['calls']):
            exact(call,{'query','phase','before','after','sdk','inputStarted','invitation'})
            query=arguments('feature.avatar-people.act',call['query'])
            need(query['verb'] in ('peer-accept','peer-reject') and query['runId']==self.sources.run
                and query['fixtureUrl']==self.sources.phase.fixture_url and query['ticket'] not in tickets
                and call['phase'] in ('acting','issuing','acknowledged') and type(call['inputStarted']) is bool
                and type(call['sdk']) is list and len(call['sdk'])<=1);tickets.add(query['ticket'])
            if call['before'] is not None:self.original(call['before'])
            else:need(call['after'] is None and not call['sdk'] and not call['inputStarted'] and call['invitation'] is None)
            if call['after'] is not None:self.original(call['after'])
            if index<len(state['calls'])-1 or call['phase']=='acknowledged':need(call['phase']=='acknowledged' and call['after'] is not None)
            if call['invitation'] is not None:
                item=call['invitation'];exact(item,{'requestId','source'});avatar_state.session(item['requestId'])
                need(item['requestId'] not in invitations);invitations.add(item['requestId'])
                frame=self.original(item['source']);pages=[row for row in frame['ui']['controls'] if row['id']=='people.page']
                need(len(pages)==1 and pages[0]['connectionState']['phase']=='incoming'
                    and pages[0]['connectionState']['peer']==self.peer and pages[0]['connectionState']['requestId']==item['requestId'])
            for event in call['sdk']:
                exact(event,{'before','after'});need(not self.original(event['before'])['ui']['open'])
                if event['after'] is not None:need(self.original(event['after'])['ui']['open'])
            need(sum(event['after'] is None for event in call['sdk'])==(1 if call['phase']=='issuing' else 0))
        return deepcopy(state)

    def bound(self):self.sources.bound();need(not self.failed and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def capture(self):
        self.bound();frame=self.sources.read();native=frame['originals']['native'];account=native['account']
        account_original(account,native['capturedEpochMs'])
        need(account['loggedIn'] and account['principalSha256']==hashlib.sha256(self.username.encode()).hexdigest()
            and account['observation']['endpointSha256']==hashlib.sha256(self.origin.encode()).hexdigest())
        avatar_renderers.avatar(frame['originals']['renderers'],self.peer,remote=True)
        if self.state['calls']:
            call=self.state['calls'][-1];current=frame['phaseAfter']['activations'][-1]
            need(current['ticket']==call['query']['ticket'] and current['stimulus']['verb']==call['query']['verb']
                and same(current['stimulus']['inputs'],call['query']['inputs']))
            baseline=self.state['calls'][0]['before']
            if baseline is not None:
                before=self.original(baseline)['originals'];after=frame['originals']
                avatar_renderers.preserve_unowned(before['renderers'],after['renderers'],set())
                need(before['state']['source']['bookmarks']==after['state']['source']['bookmarks'])
                for key in ('sessionId','requestedUrl','resourceUrl','geometryLoaded','rigReady','targetScale','modelScale'):
                    need(before['state']['source'][key]==after['state']['source'][key])
        return frame

    def wait(self,predicate):
        started=previous=self.sources.monotonic()
        for attempt in range(121):
            frame=self.capture()
            if predicate(frame):return frame
            now=self.sources.monotonic();need(previous<=now<started+12);previous=now
            if attempt<120:self.sdk.sleep(.1)
        raise AvatarConsentPending('Original actor consent has not settled; no event is replayed')

    def intent(self,value):
        frame=self.capture();same_reference(value['reference'],frame['ui'],value['controlId']);call=self.state['calls'][-1]
        need(call['phase']=='acting')
        if value['controlId'] in ('people.accept','people.decline'):
            self.invitation_reference(call,frame['ui'],value['controlId'])
        if not call['inputStarted']:need(self.inputs.begin(call['query']));call['inputStarted']=True;self.save()
        self.inputs.intent(value)

    def invitation_reference(self,call,reference,control):
        invitation=call['invitation'];need(invitation is not None)
        need(control==('people.accept' if call['query']['verb']=='peer-accept' else 'people.decline'))
        pages=[row for row in reference['controls'] if row['id']=='people.page'];need(len(pages)==1)
        state=pages[0]['connectionState'];need(state['phase']=='incoming' and state['peer']==self.peer
            and state['requestId']==invitation['requestId'])

    def act(self,query):
        self.bound();query=deepcopy(arguments('feature.avatar-people.act',query))
        need(query['verb'] in ('peer-accept','peer-reject') and query['runId']==self.sources.run and query['fixtureUrl']==self.sources.phase.fixture_url)
        for call in self.state['calls']:
            if call['query']['ticket']==query['ticket']:
                need(same(call['query'],query) and call['phase']=='acknowledged');return {'performed':True}
        if self.state['calls'] and self.state['calls'][-1]['phase']!='acknowledged':
            raise AvatarConsentPending('Original actor response remains owned; input is not repeated')
        call=dict(query=query,phase='acting',before=None,after=None,sdk=[],inputStarted=False,invitation=None)
        self.state['calls'].append(call);self.save();before=self.capture();call['before']=self.reference(before);self.save()
        if not before['ui']['open']:
            call['sdk'].append(dict(before=self.reference(before),after=None));call['phase']='issuing';self.save()
            self.sdk.click(Locator('accessibility id','OverteTabletOpen'))
            opened=self.wait(lambda frame:frame['ui']['open']);call['sdk'][-1]['after']=self.reference(opened);call['phase']='acting';self.save()
        ui=AvatarUI(self.sources.readers['ui'],self.intent,delivered=self.inputs.delivered,observed=self.inputs.observed,
            monotonic=self.sources.monotonic,sleep=self.sdk.sleep)
        ui.open('people');incoming=self.capture();pages=[row for row in incoming['ui']['controls'] if row['id']=='people.page']
        need(len(pages)==1 and pages[0]['connectionState']['phase']=='incoming' and pages[0]['connectionState']['peer']==self.peer)
        call['invitation']=dict(requestId=pages[0]['connectionState']['requestId'],source=self.reference(incoming));self.save()
        ui.respond_connection(self.peer,accept=query['verb']=='peer-accept')
        terminal='success' if query['verb']=='peer-accept' else 'declined'
        self.wait(lambda frame:any(row['id']=='people.page' and row['connectionState']['phase']==terminal for row in frame['ui']['controls']))
        ui.close_connection();ui.connections()
        self.wait(lambda frame:any(row['id']=='people.page' and row['connectionState']['phase']=='idle' for row in frame['ui']['controls']))
        need(call['inputStarted']);self.inputs.finish();call['after']=self.reference(self.capture());call['phase']='acknowledged';self.save()
        return {'performed':True}
