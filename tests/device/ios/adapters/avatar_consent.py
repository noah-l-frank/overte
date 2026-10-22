"""Durable ordinary accept/decline on the independent actual actor SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy,copy
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
from ios.adapters.avatar_recipe_ui import AvatarRecipeUI
from ios.adapters import avatar_operation_clock as operation_clock

VERSION=1


class AvatarConsentPending(NativeUIError):pass


class IOSAvatarConsent:
    def __init__(self,store,sources,inputs,sdk,peer,username,owned_origin,*,input_reads=None):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,IOSAvatarSources) and not sources.historical
            and sources.role=='actor' and isinstance(inputs,AvatarInputOwner) and isinstance(sdk,NativeUI))
        avatar_state.session(peer);need(type(username) is str and username.startswith('e2e-') and avatar_state.identity(username[4:]))
        from ios.adapters.authentication_origin import origin
        need(origin(owned_origin+'/feature-fixture/v1')==owned_origin and inputs.binding==sources.binding and inputs.run==sources.run
            and inputs.role=='actor' and inputs.lock is sources.lock and inputs.fixture_url==sources.phase.fixture_url
            and store.path.name=='ios-avatar-actor-consent.json')
        self.store,self.sources,self.inputs,self.sdk=store,sources,inputs,sdk
        self.sdk=copy(sdk)
        def continuous():
            self.operation_deadline();need(sdk.check_continuity() is not False);self.operation_deadline();return True
        self.sdk.check_continuity=continuous
        self.peer,self.username,self.origin=peer,username,owned_origin
        if input_reads is not None:
            from ios.adapters.avatar_input_reads import IOSAvatarInputReads
            need(isinstance(input_reads,IOSAvatarInputReads) and not input_reads.historical and input_reads.run==sources.run
                and input_reads.role=='actor' and input_reads.binding==sources.binding and input_reads.lock is sources.lock)
        self.input_reads=input_reads
        self.previous=store.read();self.failed=False;self.lock=sources.lock;self.lock.assert_held()
        self.state=dict(calls=[]) if self.previous is None else self.decode(self.previous);inputs.load()
        owned=[call for call in self.state['calls'] if call['inputStarted']]
        need(len(owned)==len(inputs.state['calls']))
        for call,event in zip(owned,inputs.state['calls']):
            need(same(call['query'],event['arguments']) and (call['phase']!='acknowledged' or event['phase']=='acknowledged'))
            for item in event['events']:
                if item['intent']['controlId'] in ('people.accept','people.decline'):
                    self.invitation_reference(call,item['intent']['reference'],item['intent']['controlId'])
                elif item['intent']['controlId']=='people.cancel':self.terminal_reference(call,item['intent']['reference'])

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
            exact(call,{'query','phase','before','after','sdk','inputStarted','invitation'}|({'operationClock'} if 'operationClock' in call else set()))
            if 'operationClock' in call:operation_clock.validate(call['operationClock'])
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
        self.bound()
        if self.state['calls'] and self.state['calls'][-1]['phase']!='acknowledged':self.operation_deadline()
        frame=self.sources.read();native=frame['originals']['native'];account=native['account']
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
        elif value['controlId']=='people.cancel':self.terminal_reference(call,frame['ui'])
        if not call['inputStarted']:need(self.inputs.begin(call['query']));call['inputStarted']=True;self.save()
        self.inputs.intent(value)

    def invitation_reference(self,call,reference,control):
        invitation=call['invitation'];need(invitation is not None)
        need(control==('people.accept' if call['query']['verb']=='peer-accept' else 'people.decline'))
        pages=[row for row in reference['controls'] if row['id']=='people.page'];need(len(pages)==1)
        state=pages[0]['connectionState'];need(state['phase']=='incoming' and state['peer']==self.peer
            and state['requestId']==invitation['requestId'])

    def operation_deadline(self):
        call=self.state['calls'][-1]
        if 'operationClock' not in call:raise AvatarConsentPending('Legacy actor response lacks its original deadline and cannot be resumed')
        return operation_clock.check(call['operationClock'],self.sources.epoch_ms(),self.sources.monotonic())

    def terminal_reference(self,call,reference):
        invitation=call['invitation'];need(invitation is not None)
        pages=[row for row in reference['controls'] if row['id']=='people.page'];need(len(pages)==1)
        state=pages[0]['connectionState'];need(state['phase']==('success' if call['query']['verb']=='peer-accept' else 'declined')
            and state['peer']==self.peer and state['requestId']==invitation['requestId'])

    def recover_event(self):
        self.operation_deadline();call=self.state['calls'][-1]
        if call['phase']!='acting':raise AvatarConsentPending('Original actor UIKit input remains unresolved')
        if not call['inputStarted']:return []
        events=self.inputs.state['calls'][-1]['events'];need(events);event=events[-1];original=event['intent']
        if event['phase']=='issued':
            if self.input_reads is None:raise AvatarConsentPending('Original native actor return is required before continuation')
            row=self.input_reads.read();receipt=self.input_reads.delivered(row,original)
            self.operation_deadline();self.inputs.delivered(original,receipt)
        if event['phase']!='observed':
            current=self.sources.readers['ui'].capture();self.operation_deadline();self.inputs.observed(original,current)
        return deepcopy(events)

    def act(self,query):
        self.bound();query=deepcopy(arguments('feature.avatar-people.act',query))
        need(query['verb'] in ('peer-accept','peer-reject') and query['runId']==self.sources.run and query['fixtureUrl']==self.sources.phase.fixture_url)
        current=None;prefix=[]
        for call in self.state['calls']:
            if call['query']['ticket']==query['ticket']:
                need(same(call['query'],query))
                if call['phase']=='acknowledged':return {'performed':True}
                current=call;break
        if self.state['calls'] and self.state['calls'][-1]['phase']!='acknowledged':
            if current is None:raise AvatarConsentPending('Original actor response remains owned; input is not repeated')
        if current is None:
            call=dict(query=query,phase='acting',before=None,after=None,sdk=[],inputStarted=False,invitation=None,
                operationClock=operation_clock.begin(self.sources.epoch_ms(),self.sources.monotonic()))
            self.state['calls'].append(call);self.save();before=self.capture();call['before']=self.reference(before);self.save()
        else:
            call=current;prefix=self.recover_event();before=self.capture()
            if call['before'] is None:call['before']=self.reference(before);self.save()
            if prefix:need(before['ui']['open'])
        if not before['ui']['open']:
            call['sdk'].append(dict(before=self.reference(before),after=None));call['phase']='issuing';self.save()
            self.sdk.click(Locator('accessibility id','OverteTabletOpen'))
            opened=self.wait(lambda frame:frame['ui']['open']);call['sdk'][-1]['after']=self.reference(opened);call['phase']='acting';self.save()
        ui=AvatarRecipeUI(self.sources.readers['ui'],self.intent,prefix,deadline=self.operation_deadline,
            delivered=self.inputs.delivered,observed=self.inputs.observed,monotonic=self.sources.monotonic,sleep=self.sdk.sleep)
        ui.open('people')
        if call['invitation'] is None:
            incoming=self.capture();pages=[row for row in incoming['ui']['controls'] if row['id']=='people.page']
            need(len(pages)==1 and pages[0]['connectionState']['phase']=='incoming' and pages[0]['connectionState']['peer']==self.peer)
            call['invitation']=dict(requestId=pages[0]['connectionState']['requestId'],source=self.reference(incoming));self.save()
        ui.respond_connection(self.peer,accept=query['verb']=='peer-accept')
        terminal='success' if query['verb']=='peer-accept' else 'declined'
        closed_terminal=any(event['intent']['controlId']=='people.cancel' and any(row['id']=='people.page'
            and row['connectionState']['phase']==terminal for row in event['intent']['reference']['controls']) for event in prefix)
        if not closed_terminal:
            self.wait(lambda frame:any(row['id']=='people.page' and row['connectionState']['phase']==terminal
                and row['connectionState'].get('peer')==self.peer and row['connectionState'].get('requestId')==call['invitation']['requestId']
                for row in frame['ui']['controls']))
        ui.close_connection();ui.connections()
        self.wait(lambda frame:any(row['id']=='people.page' and row['connectionState']['phase']=='idle' for row in frame['ui']['controls']))
        ui.complete();need(call['inputStarted'])
        if self.inputs.state['phase']!='acknowledged':self.inputs.finish()
        call['after']=self.reference(self.capture());call['phase']='acknowledged';self.save()
        return {'performed':True}
