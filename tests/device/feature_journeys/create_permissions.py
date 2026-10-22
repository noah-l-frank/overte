"""Runner-owned original domain Settings control; adapter access is GET only.

Receipts describe Settings API readback, never client rights, peer effects or
physical configuration-file persistence. The original domain controller owns
its process/start and private uncertain-POST lease separately.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
import secrets
import time
from urllib.parse import urlsplit
from urllib.request import build_opener,ProxyHandler,Request
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.contract import identifier,json_document
from fixture.create_permissions import NoRedirect,canonical
from fixture.pico_create_permissions import rows
from fixture.create_permissions import REZ


def receipt(value,domain,previous=None):
    exact(value,{'createPermissionsVersion','domainId','sequence','capturedEpochMs','restored','standard'})
    need(type(value['createPermissionsVersion']) is int and value['createPermissionsVersion']==1
        and value['domainId']==domain and integer(value['sequence'],1) and integer(value['capturedEpochMs'],1)
        and type(value['restored']) is bool)
    rows(value['standard'])
    if previous is not None:
        receipt(previous,domain)
        need(value['sequence']>previous['sequence'] and value['capturedEpochMs']>=previous['capturedEpochMs'])
    return value


class CreatePermissionProvider:
    def __init__(self,config,store,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000)):
        exact(config,{'controlUrl','controlToken','domainId'})
        parsed=urlsplit(config['controlUrl'])
        need(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port is not None
            and parsed.path=='/v1/create-permissions' and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment and isinstance(store,PrivateFeatureState)
            and type(config['controlToken']) is str and 32<=len(config['controlToken'])<=256
            and all(33<=ord(c)<=126 for c in config['controlToken'])
            and type(config['domainId']) is str and re.fullmatch('[0-9a-f-]{36}',config['domainId'])
            and callable(monotonic) and callable(epoch_ms))
        import uuid
        need(str(uuid.UUID(config['domainId']))==config['domainId'] and uuid.UUID(config['domainId']).int)
        self.config,self.store,self.monotonic,self.epoch_ms=deepcopy(config),store,monotonic,epoch_ms
        self.opener=build_opener(ProxyHandler({}),NoRedirect());self.previous=store.read()
        if self.previous is not None:self.validate(self.previous)
    def validate(self,value):
        exact(value,{'createPermissionProviderVersion','instance','domainId','runId','ownerToken','original','last','events','pending','retired'})
        need(type(value['createPermissionProviderVersion']) is int and value['createPermissionProviderVersion']==1
            and value['domainId']==self.config['domainId'] and type(value['ownerToken']) is str
            and re.fullmatch('[0-9a-f]{64}',value['ownerToken']) and type(value['retired']) is bool)
        identifier(value['instance']);identifier(value['runId']);rows(value['original'])
        if value['last'] is not None:receipt(value['last'],value['domainId'])
        need(type(value['events']) is list and len(value['events'])<=256)
        tickets=[]
        for event in value['events']:
            exact(event,{'ticket','operation','allowed','receipt'})
            identifier(event['ticket']);tickets.append(event['ticket'])
            need(event['operation'] in ('set','restore') and type(event['allowed']) is bool)
            receipt(event['receipt'],value['domainId'])
        need(len(tickets)==len(set(tickets)))
        if value['pending'] is not None:
            exact(value['pending'],{'ticket','operation','allowed'});identifier(value['pending']['ticket'])
            need(value['pending']['ticket'] not in tickets and value['pending']['operation'] in ('set','restore')
                and type(value['pending']['allowed']) is bool)
    def state(self):
        value=self.store.read();need(value is not None and value==self.previous);self.validate(value);return value
    def save(self,value):
        self.validate(value);self.store.write(value,self.previous);need(self.store.read()==value);self.previous=deepcopy(value)
    def open(self,request):
        try:return self.opener.open(request,timeout=2)
        except Exception as error:
            if callable(getattr(error,"close",None)):error.close()
            raise
    def request(self,operation,allowed=None):
        state=self.state();need(not state['retired'])
        body=dict(schemaVersion=1,runId=state['runId'],ownerToken=state['ownerToken'],operation=operation)
        if allowed is not None:body['allowed']=allowed
        started=self.monotonic();epoch=self.epoch_ms();need(number(started,0,1e15) and number(epoch,1,1e15))
        request=Request(self.config['controlUrl'],data=canonical(body),method='POST',headers={
            'X-Overte-E2E-Token':self.config['controlToken'],'Content-Type':'application/json','Cache-Control':'no-store'})
        with self.open(request) as response:
            need(response.status==200 and response.geturl()==self.config['controlUrl'])
            raw=response.read(1048577);need(len(raw)<=1048576)
        value=json_document(raw);receipt(value,state['domainId'],state['last'])
        now=self.monotonic();native=self.epoch_ms();need(number(now,started,1e15) and number(native,epoch,1e15))
        effective=max(native,epoch+math.ceil((now-started)*1000))
        need(-250<=effective-value['capturedEpochMs']<=1500 and self.state()==state)
        return value
    def provision(self,run):
        identifier(run);need(self.previous is None)
        # Reserve the owner before contacting the original controller; an
        # uncertain bind can never be silently adopted as a different run.
        value=dict(createPermissionProviderVersion=1,instance=secrets.token_hex(16),domainId=self.config['domainId'],
            runId=run,ownerToken=secrets.token_hex(32),original=[],last=None,events=[],pending=None,retired=False)
        # Original rows are unknown until acquired; reserve only the opaque
        # owner in a separate private CAS, then seal the exact initial receipt.
        reservation=self.store.read();need(reservation is None)
        self.store.write(value,None);self.previous=deepcopy(value)
        try:
            original=self.request_initial(value)
        except Exception:
            # Preserve the reservation on all uncertain transport outcomes.
            raise
        value.update(original=deepcopy(original['standard']),last=original);self.save(value)
    def request_initial(self,value):
        # Admission for the one reserved, explicitly unknown initial snapshot.
        rows_before=value['original'];need(rows_before==[] and value['last'] is None)
        # Reuse exactly the bounded transport body without treating an empty
        # row set as a baseline. state() refuses this reservation everywhere else.
        body=dict(schemaVersion=1,runId=value['runId'],ownerToken=value['ownerToken'],operation='observe')
        started=self.monotonic();epoch=self.epoch_ms()
        request=Request(self.config['controlUrl'],data=canonical(body),method='POST',headers={
            'X-Overte-E2E-Token':self.config['controlToken'],'Content-Type':'application/json','Cache-Control':'no-store'})
        with self.open(request) as response:
            need(response.status==200 and response.geturl()==self.config['controlUrl'])
            raw=response.read(1048577);need(len(raw)<=1048576)
        result=json_document(raw);receipt(result,value['domainId']);now=self.monotonic();native=self.epoch_ms()
        need(number(started,0,1e15) and number(epoch,1,1e15) and number(now,started,1e15) and number(native,epoch,1e15)
            and -250<=max(native,epoch+math.ceil((now-started)*1000))-result['capturedEpochMs']<=1500
            and self.store.read()==self.previous and not result['restored'])
        return result
    def activate(self,run,activation):
        value=self.state();need(value['runId']==run and value['pending'] is None and not value['retired'])
        stimulus=activation['stimulus'];verb=stimulus['verb']
        if verb not in ('set-rez-permission','cleanup'):return
        operation='set' if verb=='set-rez-permission' else 'restore'
        pending=dict(ticket=activation['ticket'],operation=operation,allowed=stimulus['inputs']['allowed'] if operation=='set' else True)
        need(not any(event['ticket']==pending['ticket'] for event in value['events']))
        value['pending']=pending;self.save(value)
        observed=self.request(operation,pending['allowed'] if operation=='set' else None)
        self.complete(observed)
    def target(self,value):
        pending=value['pending'];need(pending is not None);target=deepcopy(value['original'])
        if pending['operation']=='set':
            for row in target:
                for key in REZ:row[key]=pending['allowed']
        return target
    def complete(self,observed):
        value=self.state();need(value['pending'] is not None and observed['standard']==self.target(value)
            and (observed['restored'] if value['pending']['operation']=='restore' else not observed['restored']))
        value['events'].append(value['pending']|dict(receipt=deepcopy(observed)))
        value.update(pending=None,last=deepcopy(observed));self.save(value)
    def snapshot(self,run,request,phase):
        value=self.state();need(value['runId']==identifier(run) and not value['retired'])
        identifier(request)
        observed=self.request('observe')
        if value['pending'] is not None:self.complete(observed)
        else:
            need(observed['standard']==value['last']['standard'] and observed['restored']==value['last']['restored'])
            value['last']=deepcopy(observed);self.save(value)
        value=self.state()
        need(all(sum(event['ticket']==row['ticket'] for row in phase['activations'])==1 for event in value['events']))
        return dict(createPermissionSourceVersion=1,instance=value['instance'],runId=run,requestId=request,
            original=deepcopy(value['original']),events=deepcopy(value['events']),current=deepcopy(observed),
            phaseInstance=phase['instance'],phaseActivations=deepcopy(phase['activations']))
    def retire(self,run):
        value=self.state();need(value['runId']==run and value['pending'] is None and value['last']['restored']
            and value['last']['standard']==value['original'])
        observed=self.request('retire');need(observed['restored'] and observed['standard']==value['original'])
        value.update(last=observed,retired=True);self.save(value)
