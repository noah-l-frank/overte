"""Once-only private credential retirement for an interrupted Avatar input.

Only closed safe lease metadata is retained. Credential bytes, their hashes
and the private AFC readback are never copied into this owner or its results.
Unknown retire delivery is followed by distinct inspect commands, never replay.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import time
import uuid

from adapters.native_feature_observation import decode,exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.operation_transport_guard import scope as transport_scope
from adapters.private_login_input import command,filename,validate as lease_packet
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.avatar_abort import IOSAvatarAbort
from ios.adapters.private_login_transport import IOSPrivateLoginTransport
from ios.adapters import avatar_operation_clock as operation_clock

VERSION=1
MAX_QUERIES=16


class AvatarAbortCredentials:
    @classmethod
    def archive(cls,value,*,store,private_store,binding,run,child_run,role,lock):
        need(isinstance(store,PrivateFeatureState) and isinstance(private_store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and role in ('primary','actor'));lock.assert_held();result=object.__new__(cls)
        result.store,result.private_store,result.binding,result.lock=store,private_store,deepcopy(context(binding)),lock
        result.run,result.child,result.role=identifier(run),identifier(child_run),role
        need(run!=child_run and store.path.name=='ios-avatar-'+role+'-'+run+'-abort-credentials.json'
            and private_store.path==store.path.with_name('ios-avatar-'+role+'-private-login-input.json')
            and lock.path==store.path.with_name('script-feature-sources.lock') and same(store.read(),value))
        result.transport=SimpleNamespace(pid=int(binding['processIdentity']));result.previous=deepcopy(value)
        result.state=result.decode(value);need(result.state['phase']=='retired' and private_store.read() is None)
        return deepcopy(result.state)

    def __init__(self,store,private_store,transport,binding,run,child_run,role,lock,guard,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(private_store,PrivateFeatureState)
            and type(transport) is IOSPrivateLoginTransport and isinstance(lock,ScriptSourceLock)
            and role in ('primary','actor') and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.private_store,self.transport,self.binding=store,private_store,transport,deepcopy(context(binding))
        self.run,self.child,self.role,self.lock=identifier(run),identifier(child_run),role,lock
        need(run!=child_run and store.path.name=='ios-avatar-'+role+'-'+run+'-abort-credentials.json'
            and private_store.path==store.path.with_name('ios-avatar-'+role+'-private-login-input.json')
            and lock.path==store.path.with_name('script-feature-sources.lock') and str(transport.pid)==binding['processIdentity'])
        self.guard,self.epoch_ms,self.monotonic=guard,epoch_ms,monotonic;lock.assert_held();self.previous=store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        return dict(iosAvatarAbortCredentialsVersion=VERSION,runId=self.run,childRunId=self.child,role=self.role,binding=self.binding,payload=pack([state]))

    def owned(self,value):
        exact(value,{'inputVersion','binding','runId','inputId','sourceInstance','transferPending'})
        need(type(value['inputVersion']) is int and value['inputVersion']==2 and same(value['binding'],self.binding)
            and value['runId']==self.child and type(value['transferPending']) is bool)
        identifier(value['inputId'])
        if value['sourceInstance'] is not None:identifier(value['sourceInstance'])
        return value

    def decode(self,value):
        exact(value,{'iosAvatarAbortCredentialsVersion','runId','childRunId','role','binding','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosAvatarAbortCredentialsVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','operationClock','ownership','drains','queries','pending','retireIssued'})
        need(state['phase'] in ('owned','retired') and type(state['retireIssued']) is bool
            and type(state['drains']) is list and len(state['drains'])<=MAX_QUERIES
            and type(state['queries']) is list and len(state['queries'])<=MAX_QUERIES)
        operation_clock.validate(state['operationClock']);owned=self.owned(state['ownership'])
        for index,row in enumerate(state['drains'],1):
            exact(row,{'index','status','acquisition'});need(type(row['index']) is int and row['index']==index and row['status'] in ('issued','returned','abandoned')
                and (row['status']!='issued' or index==len(state['drains'])))
            if row['status']=='returned':self.drain_clock(row['acquisition'])
            else:need(row['acquisition'] is None)
        previous=None;nonces=set()
        for index,row in enumerate(state['queries'],1):
            exact(row,{'index','query','status','packet','acquisition','issued'});need(type(row['index']) is int and row['index']==index
                and row['status'] in ('issued','observed','abandoned'))
            exact(row['issued'],{'epochMs','monotonic'});need(number(row['issued']['epochMs'],1,1e15) and number(row['issued']['monotonic'],0,1e15))
            query=command(row['query']);need(query['runId']==self.child and query['inputId']==owned['inputId']
                and query['operation'] in ('retire','inspect') and query['commandId'] not in nonces);nonces.add(query['commandId'])
            if query['operation']=='retire':need(state['retireIssued'] and index==1)
            packet=row['packet']
            if packet is None:need(row['status']!='observed' and row['acquisition'] is None)
            else:
                lease_packet(packet,query,self.transport.pid)
                need(owned['sourceInstance'] in (None,packet['instance']))
                if previous:need(packet['instance']==previous['instance'] and packet['sequence']>previous['sequence']
                    and packet['elapsedMs']>=previous['elapsedMs'] and packet['capturedEpochMs']>=previous['capturedEpochMs'])
                previous=packet;need(row['status']=='observed');IOSAvatarAbort.acquisition(row['acquisition'])
                need(row['acquisition']['hostBeforeEpochMs']>=row['issued']['epochMs'] and row['acquisition']['hostBeforeMonotonic']>=row['issued']['monotonic'])
            if row['status']=='issued':need(index==len(state['queries']) and state['pending']==index)
        need(state['pending'] is None or type(state['pending']) is int and state['pending']==len(state['queries'])
            and state['queries'][-1]['status']=='issued')
        need(state['retireIssued']==bool(state['queries']))
        if state['queries']:need(state['queries'][0]['query']['operation']=='retire')
        if owned['transferPending'] and state['queries']:
            returned=[row for row in state['drains'] if row['status']=='returned'];need(len(returned)==1 and state['drains'][-1] is returned[0])
            fence=returned[0]['acquisition'];issued=state['queries'][0]['issued']
            need(fence['hostAfterEpochMs']<=issued['epochMs'] and fence['hostAfterMonotonic']<=issued['monotonic'])
        if state['phase']=='retired':
            self.closed(state)
        return deepcopy(state)

    @staticmethod
    def drain_clock(value):
        exact(value,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        a,b,c,d=(value[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'))
        need(number(a,1,1e15) and number(b,a,a+5000) and b-a<5000 and number(c,0,1e15)
            and number(d,c,c+5) and d-c<5 and abs(b-a-(d-c)*1000)<=250)

    @staticmethod
    def closed(state):
        need(state['pending'] is None and state['retireIssued']);observed=[row for row in state['queries'] if row['status']=='observed' and row['query']['operation']=='inspect']
        need(len(observed)>=2)
        for row in observed[-2:]:
            source=row['packet']['source'];need(source['retired'] and not source['filePresent'] and not source['pending'] and source['openFiles']==0)

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous));self.transport.guard()
        if self.state is not None:
            current=self.private_store.read()
            if current is None:
                if self.state['phase']!='retired':self.closed(self.state)
            else:need(self.state['phase']!='retired' and same(current,self.state['ownership']))

    def input_guard(self):
        self.bound();operation_clock.check(self.state['operationClock'],self.epoch_ms(),self.monotonic());return True

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def query(self,operation):
        self.bound();need(operation in ('retire','inspect') and self.state['pending'] is None and len(self.state['queries'])<MAX_QUERIES)
        if operation=='retire':self.input_guard()
        query=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='feature-private-login-input',operation=operation,runId=self.child,inputId=self.state['ownership']['inputId'])
        row=dict(index=len(self.state['queries'])+1,query=query,status='issued',packet=None,acquisition=None,
            issued=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic()))
        if operation=='retire':need(not self.state['retireIssued']);self.state['retireIssued']=True
        self.state['queries'].append(row);self.state['pending']=row['index'];self.save()
        before,started=self.epoch_ms(),self.monotonic()
        final_guard=self.input_guard if operation=='retire' else self.bound
        with transport_scope(final_guard):final_guard();self.transport.send(query)
        # AFC retrieval may observe a prior fixed-file response. No foreign or
        # malformed payload, entered text or partial bytes become a host file.
        for _ in range(51):
            self.bound()
            with transport_scope(self.bound):raw=self.transport.read()
            try:packet=decode(raw,limit=65536) if raw else None
            except (ValueError,UnicodeError):packet=None
            if type(packet) is dict and packet.get('commandId')==query['commandId']:
                lease_packet(packet,query,self.transport.pid)
                row.update(status='observed',packet=deepcopy(packet),acquisition=dict(hostBeforeEpochMs=before,hostAfterEpochMs=self.epoch_ms(),
                    hostBeforeMonotonic=started,hostAfterMonotonic=self.monotonic()));self.state['pending']=None;self.save()
                ended=self.monotonic();epoch=self.epoch_ms();need(started<=ended<started+1.5 and before<=epoch<before+1500
                    and abs(epoch-before-(ended-started)*1000)<=250);return packet
            need(self.monotonic()-started<1.5)
            self.transport.observer.sleep(.02)
        need(False)

    def cleanup(self):
        self.bound()
        if self.state is None:
            original=self.private_store.read();need(original is not None);self.owned(original)
            self.state=dict(phase='owned',operationClock=operation_clock.begin(self.epoch_ms(),self.monotonic()),ownership=deepcopy(original),
                drains=[],queries=[],pending=None,retireIssued=False);self.save()
        current=self.private_store.read()
        if self.state['phase']=='retired':need(current is None);return dict(performed=True)
        if current is None:
            self.closed(self.state);self.state['phase']='retired';self.save();return dict(performed=True)
        need(current is not None and same(current,self.state['ownership']))
        if self.state['ownership']['transferPending'] and not any(row['status']=='returned' for row in self.state['drains']):
            rows=self.state['drains']
            if rows and rows[-1]['status']=='issued':rows[-1]['status']='abandoned';self.save()
            need(len(rows)<MAX_QUERIES);rows.append(dict(index=len(rows)+1,status='issued',acquisition=None));self.save()
            # The actual serialized private RPC fence is intentionally not
            # retained: its value contains credentials and supplies no fact.
            before,started=self.epoch_ms(),self.monotonic()
            with transport_scope(self.bound):self.bound();self.transport.drain(filename(current['inputId']))
            rows[-1].update(status='returned',acquisition=dict(hostBeforeEpochMs=before,hostAfterEpochMs=self.epoch_ms(),
                hostBeforeMonotonic=started,hostAfterMonotonic=self.monotonic()));self.save()
        if self.state['pending'] is not None:
            self.state['queries'][-1]['status']='abandoned';self.state['pending']=None;self.save()
        if not self.state['retireIssued']:self.query('retire')
        for _ in range(2):
            packet=self.query('inspect');source=packet['source']
            need(source['retired'] and not source['filePresent'] and not source['pending'] and source['openFiles']==0)
        self.bound();self.private_store.discard(current);need(self.private_store.read() is None)
        self.state['phase']='retired';self.save();return dict(performed=True)
