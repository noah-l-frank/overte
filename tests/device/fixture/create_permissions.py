"""Rez control for one process-owned ephemeral domain, with original readback.

This fixture writes the existing domain-server Settings API. Its receipts are
not Interface permission/effect observations. It never reconnects clients,
spawns a replacement domain or touches an external domain endpoint.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
from urllib.request import HTTPRedirectHandler,ProxyHandler,Request,build_opener
import uuid

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.contract import identifier,json_document
from fixture.messages_mixer import start_identity

STANDARD=('anonymous','friends','localhost','logged-in')
OVERRIDES=('permissions','group_permissions','group_forbiddens','ip_permissions','machine_fingerprint_permissions')
REZ=('id_can_rez','id_can_rez_tmp')


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def standard(rows):
    need(type(rows) is list and len(rows)==4)
    seen=set()
    for row in rows:
        need(type(row) is dict and row.get('permissions_id') in STANDARD and row['permissions_id'] not in seen
            and all(type(row.get(key)) is bool for key in REZ))
        seen.add(row['permissions_id'])
    return deepcopy(sorted(rows,key=lambda row:row['permissions_id']))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*_args,**_kwargs):return None


class CreatePermissions:
    def __init__(self,process,owned,port,domain,store):
        need(callable(owned) and integer(port,1,65535) and str(uuid.UUID(domain))==domain
            and isinstance(store,PrivateFeatureState))
        self.process,self.owned,self.domain,self.store=process,owned,domain,store
        self.start=start_identity(process.pid);self.url='http://127.0.0.1:'+str(port)
        self.opener=build_opener(ProxyHandler({}),NoRedirect())
        self.previous=store.read();self.state=None;self.sequence=0
        if self.previous is not None:
            value=self.previous
            exact(value,{'createPermissionsVersion','domainId','processId','processStart','runId','ownerSha256',
                'phase','original','last','outsideSha256','pending'})
            need(type(value['createPermissionsVersion']) is int and value['createPermissionsVersion']==1
                and value['domainId']==domain and value['processId']==process.pid and value['processStart']==self.start
                and value['phase'] in ('ready','changing','restored'))
            identifier(value['runId']);need(re.fullmatch('[0-9a-f]{64}',value['ownerSha256'])
                and re.fullmatch('[0-9a-f]{64}',value['outsideSha256']))
            standard(value['original']);standard(value['last'])
            if value['pending'] is not None:standard(value['pending'])
            need((value['phase']=='changing')==(value['pending'] is not None))
            self.state=deepcopy(value)
        self.guard()

    def guard(self):
        need(self.process.poll() is None and self.owned(self.process.pid) is True
            and start_identity(self.process.pid)==self.start and self.store.read()==self.previous)

    def http(self,path,payload=None):
        self.guard();raw=None if payload is None else canonical(payload)
        request=Request(self.url+path,data=raw,headers={'Content-Type':'application/json','Cache-Control':'no-store'},
                        method='GET' if payload is None else 'POST')
        with self.opener.open(request,timeout=2) as response:
            need(response.status==200 and response.geturl()==self.url+path)
            result=response.read(1048577);need(len(result)<=1048576)
        self.guard();return result

    def original(self):
        need(self.http('/id').decode('ascii').strip()==self.domain)
        value=json_document(self.http('/settings.json'));need(type(value) is dict and type(value.get('values')) is dict)
        security=value['values'].get('security');need(type(security) is dict
            and all(security.get(key)==[] for key in OVERRIDES))
        rows=standard(security.get('standard_permissions'))
        outside=digest({key:item for key,item in security.items() if key!='standard_permissions'})
        need(self.http('/id').decode('ascii').strip()==self.domain)
        return rows,outside

    def save(self,**changes):
        self.guard();value=self.state|changes;self.store.write(value,self.previous)
        need(self.store.read()==value);self.state=self.previous=deepcopy(value)

    def bind(self,run,owner):
        identifier(run);need(type(owner) is str and re.fullmatch('[0-9a-f]{64}',owner))
        owner_hash=hashlib.sha256(owner.encode()).hexdigest()
        if self.state is None:
            rows,outside=self.original()
            self.state=dict(createPermissionsVersion=1,domainId=self.domain,processId=self.process.pid,
                processStart=self.start,runId=run,ownerSha256=owner_hash,phase='ready',original=rows,
                last=rows,outsideSha256=outside,pending=None)
            self.save()
        need(self.state['runId']==run and self.state['ownerSha256']==owner_hash)

    def observe(self):
        need(self.state is not None);rows,outside=self.original();need(outside==self.state['outsideSha256'])
        if self.state['pending'] is not None:
            # Recover a lost POST reply from actual state. No uncertain command
            # is replayed. A changed unknown state keeps its original journal.
            need(rows in (self.state['last'],self.state['pending']))
            self.save(phase='ready',last=rows,pending=None)
        else:need(rows==self.state['last'])
        self.sequence+=1
        return dict(createPermissionsVersion=1,domainId=self.domain,sequence=self.sequence,
            capturedEpochMs=int(time.time()*1000),restored=self.state['phase']=='restored',standard=rows)

    def change(self,rows,*,restoring=False):
        self.observe();need(self.state['phase']!='restored')
        rows=standard(rows)
        if rows!=self.state['last']:
            self.save(phase='changing',pending=rows)
            result=json_document(self.http('/settings.json',{'security':{'standard_permissions':rows}}))
            need(result=={'status':'success'}) # ACK still supplies no effect.
            actual,outside=self.original();need(actual==rows and outside==self.state['outsideSha256'])
            self.save(phase='ready',last=actual,pending=None)
        if restoring:self.save(phase='restored')
        return self.observe()

    def request(self,command):
        fields={'schemaVersion','runId','ownerToken','operation'}
        if type(command) is dict and command.get('operation')=='set':fields.add('allowed')
        exact(command,fields);need(type(command['schemaVersion']) is int and command['schemaVersion']==1
            and command['operation'] in ('observe','set','restore','retire'))
        self.bind(command['runId'],command['ownerToken'])
        if command['operation']=='set':
            need(type(command['allowed']) is bool)
            rows=deepcopy(self.state['original'])
            for row in rows:
                for key in REZ:row[key]=command['allowed']
            return self.change(rows)
        if command['operation']=='restore':
            if self.state['phase']=='restored':return self.observe()
            return self.change(self.state['original'],restoring=True)
        actual=self.observe()
        if command['operation']=='retire':
            need(self.state['phase']=='restored' and actual['standard']==self.state['original'])
            self.store.discard(self.previous);need(self.store.read() is None)
            # Retired controller remains fenced in memory until the fixture
            # process ends. A second run cannot adopt its changed/restored state.
            self.previous=None
        return actual
