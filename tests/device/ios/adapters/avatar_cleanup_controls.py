"""New ordinary cleanup intents, separate from interrupted active recipes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import copy,deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError,Locator
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import arguments,VERSION as CONTRACT_VERSION
from ios.adapters import avatar_operation_clock as operation_clock
from ios.adapters.avatar_cleanup_inputs import AvatarCleanupInputOwner,call as cleanup_call
from ios.adapters.avatar_controls import same_reference
from ios.adapters.avatar_input_reads import IOSAvatarInputReads
from ios.adapters.avatar_recipe_ui import AvatarRecipeUI
from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery
from ios.adapters.avatar_sources import IOSAvatarSources

VERSION=1


class AvatarCleanupPending(NativeUIError):pass


class IOSAvatarCleanupControls:
    def __init__(self,store,sources,inputs,sdk,input_reads):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,IOSAvatarSources) and not sources.historical
            and isinstance(inputs,AvatarCleanupInputOwner) and isinstance(sdk,NativeUI) and isinstance(input_reads,IOSAvatarInputReads)
            and store.path.name=='ios-avatar-'+sources.role+'-cleanup-controls.json')
        need(all(owner.binding==sources.binding and owner.run==sources.run and owner.role==sources.role
            and owner.lock is sources.lock for owner in (inputs,input_reads)) and inputs.fixture_url==sources.phase.fixture_url)
        self.store,self.sources,self.inputs,self.reads=store,sources,inputs,input_reads
        self.lock=sources.lock;self.previous=store.read();self.state=dict(calls=[]);inputs.load()
        self.sdk=copy(sdk)
        def continuous():
            self.deadline();need(sdk.check_continuity() is not False);self.deadline();return True
        self.sdk.check_continuity=continuous
        if self.previous is not None:self.state=self.decode(self.previous)
        need(len(inputs.state['calls'])==sum(row['inputStarted'] for row in self.state['calls']))
        for row,events in zip((row for row in self.state['calls'] if row['inputStarted']),inputs.state['calls']):
            need(same(row['query'],events['arguments']) and (row['phase']!='acknowledged' or events['phase']=='acknowledged'))

    def envelope(self,state):return dict(iosAvatarCleanupControlsVersion=VERSION,runId=self.sources.run,role=self.sources.role,
        binding=self.sources.binding,fixtureUrl=self.sources.phase.fixture_url,payload=pack([state]))

    def original(self,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,len(self.sources.frames)))
        frame=self.sources.frames[reference['index']-1];need(reference['sha256']==digest(frame));return frame

    def reference(self,frame):
        need(self.sources.frames and same(frame,self.sources.frames[-1]));return dict(index=len(self.sources.frames),sha256=digest(frame))

    def decode(self,value):
        exact(value,{'iosAvatarCleanupControlsVersion','runId','role','binding','fixtureUrl','payload'})
        need(type(value['iosAvatarCleanupControlsVersion']) is int and value['iosAvatarCleanupControlsVersion']==VERSION)
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'calls'});need(type(state['calls']) is list and len(state['calls'])<=64)
        for index,row in enumerate(state['calls'],1):
            exact(row,{'query','phase','operationClock','before','after','inputStarted','sdk'})
            query=cleanup_call(row['query']);need(query['runId']==self.sources.run and query['fixtureUrl']==self.sources.phase.fixture_url
                and query['index']==index and row['phase'] in ('acting','issuing','acknowledged') and type(row['inputStarted']) is bool)
            operation_clock.validate(row['operationClock']);self.original(row['before'])
            if row['after'] is not None:self.original(row['after'])
            if index<len(state['calls']) or row['phase']=='acknowledged':need(row['phase']=='acknowledged' and row['after'] is not None)
            need(type(row['sdk']) is list and len(row['sdk'])<=1)
            for event in row['sdk']:
                exact(event,{'before','after'});need(not self.original(event['before'])['ui']['open'])
                if event['after'] is not None:need(self.original(event['after'])['ui']['open'])
            need(sum(event['after'] is None for event in row['sdk'])==(1 if row['phase']=='issuing' else 0))
        return deepcopy(state)

    def bound(self):self.sources.bound();need(same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)
    def deadline(self):
        return operation_clock.check(self.state['calls'][-1]['operationClock'],self.sources.epoch_ms(),self.sources.monotonic())
    def capture(self):
        self.bound();self.deadline();IOSAvatarSourceRecovery(self.sources).recover();frame=self.sources.read();self.deadline()
        activation=frame['phaseAfter']['activations'][-1];need(activation['ticket']==self.state['calls'][-1]['query']['ticket']
            and activation['stimulus']==dict(verb='cleanup',inputs={}));return frame
    def wait(self,predicate):
        for _ in range(101):
            frame=self.capture()
            if predicate(frame):return frame
            self.sdk.sleep(.1)
        raise AvatarCleanupPending('Original cleanup control did not settle; its responsibility remains retained')
    def intent(self,value):
        frame=self.capture();same_reference(value['reference'],frame['ui'],value['controlId'])
        row=self.state['calls'][-1];need(row['phase']=='acting')
        if not row['inputStarted']:
            need(self.inputs.begin(row['query']));row['inputStarted']=True;self.save()
        self.inputs.intent(value)
    def prefix(self):
        row=self.state['calls'][-1];self.deadline()
        if row['phase']=='issuing':raise AvatarCleanupPending('Original cleanup UIKit dispatch is unresolved and is not repeated')
        if not row['inputStarted']:return []
        events=self.inputs.state['calls'][-1]['events'];need(events);event=events[-1];original=event['intent']
        if event['phase']=='issued':
            record=self.reads.read();receipt=self.reads.delivered(record,original);self.deadline();self.inputs.delivered(original,receipt)
        if event['phase']!='observed':
            current=self.sources.readers['ui'].capture();self.deadline();self.inputs.observed(original,current)
        return deepcopy(events)
    def run(self,query,*,index,step,inputs,whole_clock=None):
        arguments('feature.avatar-people.cleanup',query);need(query['runId']==self.sources.run);self.bound()
        if whole_clock is not None:
            operation_clock.validate(whole_clock)
            need(all(same(row['operationClock'],whole_clock) for row in self.state['calls']))
            operation_clock.check(whole_clock,self.sources.epoch_ms(),self.sources.monotonic())
        phase=self.sources.phase.read();need(phase['verb']=='cleanup')
        actual=cleanup_call(dict(avatarCleanupInputCallVersion=1,contractVersion=CONTRACT_VERSION,runId=self.sources.run,
            fixtureUrl=self.sources.phase.fixture_url,ticket=phase['ticket'],index=index,step=step,inputs=deepcopy(inputs)))
        if index<=len(self.state['calls']):
            row=self.state['calls'][index-1];need(same(row['query'],actual))
            if row['phase']=='acknowledged':return {'performed':True}
            need(index==len(self.state['calls']));prefix=self.prefix()
        else:
            need(index==len(self.state['calls'])+1 and (not self.state['calls'] or self.state['calls'][-1]['phase']=='acknowledged'))
            clock=deepcopy(whole_clock) if whole_clock is not None else operation_clock.begin(self.sources.epoch_ms(),self.sources.monotonic())
            operation_clock.check(clock,self.sources.epoch_ms(),self.sources.monotonic())
            IOSAvatarSourceRecovery(self.sources).recover();before=self.sources.read()
            operation_clock.check(clock,self.sources.epoch_ms(),self.sources.monotonic())
            row=dict(query=actual,phase='acting',operationClock=clock,before=self.reference(before),after=None,inputStarted=False,sdk=[])
            self.state['calls'].append(row);self.save();prefix=[]
        before=self.capture()
        if prefix:need(before['ui']['open'])
        if not before['ui']['open']:
            row['sdk'].append(dict(before=self.reference(before),after=None));row['phase']='issuing';self.save()
            self.sdk.click(Locator('accessibility id','OverteTabletOpen'))
            opened=self.wait(lambda frame:frame['ui']['open']);row['sdk'][-1]['after']=self.reference(opened);row['phase']='acting';self.save()
        ui=AvatarRecipeUI(self.sources.readers['ui'],self.intent,prefix,deadline=self.deadline,delivered=self.inputs.delivered,
            observed=self.inputs.observed,monotonic=self.sources.monotonic,sleep=self.sdk.sleep)
        if step=='dismiss-avatar':ui.open();ui.input('avatar.'+inputs['dialog']+'.cancel')
        elif step=='dismiss-people':ui.open('people');ui.input('people.decline' if inputs['phase']=='incoming' else 'people.cancel')
        elif step=='connections':ui.connections()
        elif step=='remove-connection':ui.remove_connection(inputs['username'])
        elif step=='remove-wearable':ui.remove_wearable(inputs['entityId'])
        elif step=='restore-model':ui.avatar_url(inputs['url'])
        elif step=='restore-scale':ui.scale(inputs['value'])
        elif step=='delete-bookmark':ui.choose_bookmark(inputs['name'],delete=True)
        ui.complete();need(row['inputStarted'])
        if self.inputs.state['phase']!='acknowledged':self.inputs.finish()
        row['after']=self.reference(self.capture())
        row['phase']='acknowledged';self.save();return {'performed':True}
