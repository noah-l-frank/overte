"""Phone entity-sync foundation over original domain actor and private probe.

The broker accepts one bounded edit; only fresh received native properties
joined to the independent actor receipt prove it. Initial controlled domain
entry uses the existing Appium operation; private sources remain read-only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

from adapters.collaboration_observation import actor_receipt, portable_observation, ENTITY
from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from contracts import validate_operation_arguments, validate_operation_result
from overte_phone_script_lock import PhoneScriptSourceLock

FILE='phone-collaboration-observation.json'
OPERATIONS={'collaboration.edit','collaboration.snapshot'}


def configuration(environment):
    domain=environment.get('OVERTE_E2E_DOMAIN_ID','').strip('{}').lower()
    need(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',domain)
        and domain!='00000000-0000-0000-0000-000000000000')
    token=environment.get('OVERTE_E2E_DOMAIN_CONTROL_TOKEN','');need(re.fullmatch(r'[A-Za-z0-9_-]{40,128}',token))
    urls={}
    for kind in ('state','edit'):
        value=environment.get('OVERTE_E2E_COLLABORATION_'+kind.upper()+'_URL','');parsed=urlsplit(value)
        need(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port
            and parsed.username is None and parsed.password is None and not parsed.query and not parsed.fragment
            and parsed.path=='/v1/collaboration-'+kind)
        urls[kind]=value
    need(urlsplit(urls['state']).netloc==urlsplit(urls['edit']).netloc)
    domain_url=environment.get('OVERTE_E2E_DOMAIN_URL','')
    validate_operation_arguments('navigation.enter-domain',dict(url=domain_url))
    return dict(domainId=domain,domainUrl=domain_url,token=token,**urls)


def decode(raw):
    need(type(raw) in (str,bytes) and 0<len(raw.encode() if type(raw) is str else raw)<=8192)
    def pairs(items):
        result={}
        for key,value in items:need(key not in result);result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _value:need(False))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class CollaborationControl:
    def __init__(self,config):self.config=deepcopy(config)
    def __call__(self,kind,payload=None):
        need(kind in ('state','edit') and (payload is None)==(kind=='state'))
        request=Request(self.config[kind],data=None if payload is None else json.dumps(payload,allow_nan=False).encode(),
            headers={'X-Overte-E2E-Token':self.config['token'],'Content-Type':'application/json'},method='GET' if kind=='state' else 'POST')
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=5) as response:
                need(response.status==200);value=decode(response.read(8193))
                if kind=='state':actor_receipt(value)
                return value
        except HTTPError as error:
            status=error.code;error.close()
            if kind=='state' and status==503:return None
            raise NativeUIError('Original controlled collaboration service rejected the request') from None


def edit_values(values):
    validate_operation_arguments('collaboration.edit',values)
    need(values['entityName']==ENTITY and values['value'] in ('blue','orange'))


def owner(value):
    exact(value,{'phoneCollaborationVersion','binding','domainId','controlIdentity','receipt','sample','pending'})
    need(type(value['phoneCollaborationVersion']) is int and value['phoneCollaborationVersion']==1)
    context(value['binding'])
    need(re.fullmatch(r'[1-9][0-9]{0,9}:[0-9]{1,20}',value['binding']['processIdentity'])
        and type(value['domainId']) is str and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value['domainId'])
        and value['domainId']!='00000000-0000-0000-0000-000000000000'
        and type(value['controlIdentity']) is str and re.fullmatch('[0-9a-f]{64}',value['controlIdentity']))
    actor_receipt(value['receipt']);sample=value['sample'];need(type(sample) is dict)
    portable_observation(sample,value['receipt'],sample['sampleEpochMs'],sample)
    pending=value['pending']
    if pending is not None:
        exact(pending,{'values','before','phase'})
        need(pending['phase'] in ('issued','confirmed'));edit_values(pending['values']);actor_receipt(pending['before'])
        need(pending['before']['actorSessionId']==value['receipt']['actorSessionId'])
        if pending['phase']=='issued':need(value['receipt']==pending['before'])
        else:
            need(value['receipt']['revision']==pending['before']['revision']+1
                and value['receipt']['value']==pending['values']['value']
                and value['receipt']['commandId']!=pending['before']['commandId'])
    return value


def retire_journal(store):
    """Retire only already original-confirmed host history, never actor work.

    Historical validation uses its original epoch. This archive is diagnostic
    and cannot establish a new client/actor measurement or a new owner.
    """
    with PhoneScriptSourceLock(store.path.with_suffix('.lock')).held():
        value=store.read()
        if value is None:return
        owner(value);need(value['pending'] is None or value['pending']['phase']=='confirmed')
        digest=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        archive=PrivateFeatureState(store.path.with_name('phone-collaboration-retired-'+digest+'.json'))
        retained=archive.read()
        if retained is None:archive.write(value,None)
        need(archive.read()==value and store.read()==value)
        store.discard(value);need(store.read() is None)


class PhoneCollaboration:
    def __init__(self,store,binding,domain,guard,read_probe,read_native,clock_ms,control,enter,*,monotonic=time.monotonic,sleep=time.sleep):
        context(binding);need(type(domain) is str and all(callable(fn) for fn in (guard,read_probe,read_native,clock_ms,control,enter,monotonic,sleep)))
        need(type(control.config) is dict and control.config['domainId']==domain)
        self.control_identity=hashlib.sha256(json.dumps(control.config,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.store,self.binding,self.domain=store,deepcopy(binding),domain
        self.guard,self.probe,self.native,self.clock_ms,self.control=guard,read_probe,read_native,clock_ms,control
        self.monotonic,self.sleep=monotonic,sleep
        self.enter=enter
        self.lock=PhoneScriptSourceLock(store.path.with_suffix('.lock'))
        self.state=None

    def load(self):
        self.state=self.store.read()
        if self.state is None:return
        owner(self.state)
        need(self.state['binding']==self.binding and self.state['domainId']==self.domain and self.state['controlIdentity']==self.control_identity)

    def save(self,value):
        self.guard();self.store.write(value,self.state);self.state=deepcopy(value)

    edit_values=staticmethod(edit_values)

    def domain_probe(self,value):
        need(type(value) is dict and value.get('domain',{}).get('connected') is True
            and str(value['domain'].get('id','')).strip('{}').lower()==self.domain
            and integer(value.get('sampleSequence'),1) and number(value.get('sampleEpochMs'),1,1e15))

    def ensure_domain(self):
        self.guard();initial=self.probe()
        if initial.get('domain',{}).get('connected') is True and str(initial['domain'].get('id','')).strip('{}').lower()==self.domain:return
        # The common Create suite follows serverless foundations. Use only the
        # existing controlled Appium operation, then measure actual arrival.
        # A later lost domain cannot be silently repaired under an old owner.
        need(self.state is None);started=previous=self.monotonic();requested=self.clock_ms()
        need(number(started,0,1e15) and number(requested,1,1e15));self.guard();self.enter();self.guard()
        sequence=initial.get('sampleSequence',0);stable=0
        for attempt in range(151):
            value=self.probe();self.guard();epoch=self.clock_ms();self.guard();now=self.monotonic()
            need(number(now,previous,1e15) and now-started<30);previous=now
            if (value.get('domain',{}).get('connected') is True
                    and str(value['domain'].get('id','')).strip('{}').lower()==self.domain
                    and integer(value.get('sampleSequence'),sequence+1)
                    and number(value.get('sampleEpochMs'),requested,epoch)
                    and epoch-value['sampleEpochMs']<=5000):
                stable+=1;sequence=value['sampleSequence']
                if stable>=3:return
            else:stable=0
            need(attempt<150);self.sleep(.2)

    def sample(self):
        self.guard();started=previous=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms()
        need(number(requested,1,1e15))
        for attempt in range(151):
            self.guard();before=self.probe();self.domain_probe(before)
            actor=self.control('state');self.guard()
            if actor is not None:
                actor_receipt(actor)
                value=decode(self.native());epoch=self.clock_ms();after=self.probe();self.domain_probe(after)
                again=self.control('state');self.guard()
                try:
                    need(actor==again)
                    portable=portable_observation(value,actor,epoch,before)
                    need(value['sampleEpochMs']>=requested and after['sampleSequence']>=value['sampleSequence']
                        and after['sampleEpochMs']>=value['sampleEpochMs'])
                    if self.state is not None:
                        old=self.state
                        need(actor['actorSessionId']==old['receipt']['actorSessionId']
                            and value['sampleSequence']>old['sample']['sampleSequence']
                            and value['sampleEpochMs']>=old['sample']['sampleEpochMs']
                            and actor['revision']>=old['receipt']['revision'])
                        if actor['revision']==old['receipt']['revision']:need(actor==old['receipt'])
                        pending=old['pending']
                        if pending is not None:
                            need(actor['revision']==pending['before']['revision']+1 and actor['value']==pending['values']['value']
                                and actor['commandId']!=pending['before']['commandId'])
                    final_epoch=self.clock_ms();need(number(final_epoch,epoch,1e15))
                    portable_observation(value,actor,final_epoch,after);self.guard()
                    now=self.monotonic();need(number(now,previous,1e15) and now-started<30)
                    return portable,deepcopy(actor),deepcopy(value)
                except (ValueError,RuntimeError):pass
            now=self.monotonic();need(number(now,previous,1e15) and now-started<30);previous=now
            need(attempt<150);self.sleep(.2)
        raise NativeUIError('Original collaboration sources did not converge')

    def invoke(self,operation,values):
        need(operation in OPERATIONS);validate_operation_arguments(operation,values)
        with self.lock.held():
            self.load()
            self.ensure_domain()
            if operation=='collaboration.edit':
                self.edit_values(values)
                if self.state is not None and self.state['pending'] is not None:
                    need(self.state['pending']['values']==values)
                else:
                    _portable,receipt,sample=self.sample()
                    value=dict(phoneCollaborationVersion=1,binding=self.binding,domainId=self.domain,controlIdentity=self.control_identity,receipt=receipt,sample=sample,
                        pending=dict(values=deepcopy(values),before=deepcopy(receipt),phase='issued'))
                    self.save(value)  # Durable one-send intent precedes HTTP.
                    self.guard()
                    self.control('edit',dict(schemaVersion=1,**values));self.guard()
                portable,receipt,sample=self.sample()
                value=deepcopy(self.state);value.update(receipt=receipt,sample=sample);value['pending']['phase']='confirmed';self.save(value)
                return {'performed':True}
            portable,receipt,sample=self.sample()
            self.save(dict(phoneCollaborationVersion=1,binding=self.binding,domainId=self.domain,controlIdentity=self.control_identity,receipt=receipt,sample=sample,pending=None))
            return validate_operation_result(operation,portable)
