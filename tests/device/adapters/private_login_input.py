"""Private credential carrier ownership; no input ACK is authentication success.

Public commands, receipts and durable journals contain no entered text. The
transport writes the original native-created inode through private app storage.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import context as validate_context
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-private-login-input.json'
HEX='[0-9a-f]{32}'
UUID='[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
OPERATIONS={'inspect','reserve','deliver','retire'}
BOOLEANS={'reserved','retired','attempted','filePresent','fileOwned','pending'}
STATE=BOOLEANS|{'openFiles'}


def command(value):
    exact(value,{'schemaVersion','commandId','action','operation','runId','inputId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-private-login-input' and type(value['operation']) is str and value['operation'] in OPERATIONS
         and type(value['commandId']) is str and re.fullmatch('ios-'+HEX,value['commandId'])
         and all(type(value[k]) is str and re.fullmatch(HEX,value[k]) for k in ('runId','inputId')))
    return value


def input_command(value):
    exact(value,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation','text'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['operation']=='replace'
         and all(type(value[k]) is str and re.fullmatch(UUID,value[k]) and uuid.UUID(value[k]).int for k in ('commandId','instance','fieldToken'))
         and integer(value['sequence'],1,2**53-1) and integer(value['observedElapsedMs'],0,2**53-1)
         and type(value['text']) is str and 0<len(value['text'])<=4096 and all(32<=ord(c)<=126 for c in value['text']))
    return value


def filename(input_id):
    need(type(input_id) is str and re.fullmatch(HEX,input_id))
    return 'feature-login-input-'+input_id+'.v1.json'


def validate(value,request,pid):
    command(request)
    exact(value,{'inputVersion','commandId','operation','runId','inputId','instance','processId','capturedEpochMs','elapsedMs','sequence','available','source'})
    need(type(value['inputVersion']) is int and value['inputVersion']==VERSION and value['available'] is True
         and all(value[k]==request[k] for k in ('commandId','operation','runId','inputId'))
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['processId'],1) and value['processId']==pid
         and integer(value['capturedEpochMs'],1) and integer(value['elapsedMs']) and integer(value['sequence'],1))
    state=value['source'];exact(state,STATE|({'inputStatus'} if type(state) is dict and 'inputStatus' in state else set()))
    need(all(type(state[k]) is bool for k in BOOLEANS) and integer(state['openFiles'],0,1) and (not state['fileOwned'] or state['filePresent'] and state['reserved'] and state['openFiles']==1)
         and (not state['attempted'] or state['reserved']) and not state['pending'])
    if 'inputStatus' in state:
        status=state['inputStatus'];exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
        need(state['attempted'] and type(status['schemaVersion']) is int and status['schemaVersion']==1
             and type(status['performed']) is bool and all(type(status[k]) is str and re.fullmatch(UUID,status[k]) for k in ('commandId','instance'))
             and integer(status['sequence'],1) and integer(status['processId'],1) and status['processId']==pid
             and integer(status['sampleEpochMs'],1) and status['sampleEpochMs']<=value['capturedEpochMs'])
    return value


class PrivateLoginInput:
    def __init__(self,transport,store,binding,run,*,component_only=True,monotonic=time.monotonic,sleep=time.sleep):
        validate_context(binding,component_only=component_only)
        need(type(run) is str and re.fullmatch(HEX,run) and all(callable(v) for v in (monotonic,sleep))
             and all(callable(getattr(transport,k,None)) for k in ('guard','send','read','write','original'))
             and integer(getattr(transport,'pid',None),1))
        self.transport,self.store,self.binding,self.run=transport,store,deepcopy(binding),run
        self.monotonic,self.sleep=monotonic,sleep;self.last_clock=None
        self.instance=None;self.sequence=self.elapsed=self.captured=0;self.status=None
        self.previous=store.read()
        if self.previous is not None:
            exact(self.previous,{'inputVersion','binding','runId','inputId','sourceInstance'})
            need(type(self.previous['inputVersion']) is int and self.previous['inputVersion']==VERSION
                 and self.previous['binding']==binding and self.previous['runId']==run
                 and type(self.previous['inputId']) is str and re.fullmatch(HEX,self.previous['inputId'])
                 and (self.previous['sourceInstance'] is None or type(self.previous['sourceInstance']) is str
                      and re.fullmatch(HEX,self.previous['sourceInstance'])))
            self.instance=self.previous['sourceInstance']

    def now(self):
        value=self.monotonic();number(value,0,1e15)
        need(self.last_clock is None or value>=self.last_clock);self.last_clock=value;return value

    def _request(self,operation,deadline):
        need(self.previous is not None and self.now()<deadline);self.transport.guard()
        request=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='feature-private-login-input',operation=operation,
            runId=self.run,inputId=self.previous['inputId'])
        self.transport.send(command(request))
        for attempt in range(51):
            self.transport.guard();raw=self.transport.read()
            try:value=decode(raw) if raw else None
            except (json.JSONDecodeError,UnicodeError):value=None
            self.transport.guard();need(self.now()<deadline)
            if type(value) is dict and value.get('commandId')==request['commandId']:
                validate(value,request,self.transport.pid)
                need(self.instance in (None,value['instance']) and value['sequence']>self.sequence
                     and value['elapsedMs']>=self.elapsed and value['capturedEpochMs']>=self.captured)
                if self.status is not None and 'inputStatus' in value['source']:need(value['source']['inputStatus']==self.status)
                self.instance=value['instance'];self.sequence=value['sequence'];self.elapsed=value['elapsedMs'];self.captured=value['capturedEpochMs']
                if 'inputStatus' in value['source']:self.status=deepcopy(value['source']['inputStatus'])
                if self.previous['sourceInstance'] is None:
                    updated=dict(self.previous,sourceInstance=self.instance);self.store.write(updated,self.previous);self.previous=updated
                return value['source']
            if attempt<50:self.sleep(min(0.1,max(0,deadline-self.now())))
        raise NativeUIError('Private native input did not produce an original receipt')

    def retire(self):
        try:self._retire()
        except Exception:raise NativeUIError('Private credential cleanup remains unresolved') from None

    def _retire(self):
        if self.previous is None:return
        deadline=self.now()+5
        self._request('retire',deadline) # ACK alone is insufficient.
        first=self._request('inspect',deadline)
        need(first['retired'] and not first['filePresent'] and not first['pending'] and first['openFiles']==0)
        # Separate fresh inventory, not a repeated old cleanup acknowledgement.
        second=self._request('inspect',deadline)
        need(second['retired'] and not second['filePresent'] and not second['pending'] and second['openFiles']==0)
        self.store.discard(self.previous);self.previous=None;self.status=None

    def replace(self,value):
        created=False
        try:
            input_command(value);need(self.previous is None);self.transport.guard()
            owned=dict(inputVersion=VERSION,binding=self.binding,runId=self.run,inputId=uuid.uuid4().hex,sourceInstance=None)
            self.store.write(owned,None);self.previous=owned;created=True # Before reserve/AFC mutation; contains no text or secret digest.
            self.instance=None;self.sequence=self.elapsed=self.captured=0;self.status=None
            deadline=self.now()+15
            first=self._request('inspect',deadline)
            need(not first['reserved'] and not first['retired'] and not first['filePresent'])
            self._request('reserve',deadline)
            reserved=self._request('inspect',deadline)
            need(reserved['reserved'] and not reserved['retired'] and reserved['filePresent'] and reserved['fileOwned'] and reserved['openFiles']==1 and not reserved['attempted'])
            body=(json.dumps(dict(schemaVersion=1,runId=self.run,inputId=owned['inputId'],input=value),
                sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
            need(len(body)<=16384);self.transport.guard()
            self.transport.write(filename(owned['inputId']),body)
            self.transport.guard();need(self.now()<deadline)
            need(self.transport.original(filename(owned['inputId']))==body) # Actual app-private bytes, not a push ACK.
            self._request('deliver',deadline)
            observed=self._request('inspect',deadline)
            need(observed['reserved'] and observed['attempted'] and not observed['retired'] and not observed['filePresent'])
            status=observed.get('inputStatus');need(type(status) is dict and status['performed'] is True
                 and all(status[k]==value[k] for k in ('commandId','instance','sequence')))
        except Exception:
            # Preserve uncertain native/file ownership. Caller can explicitly
            # recover it; no public exception carries entered text or raw data.
            raise NativeUIError('Private native credential input failed') from None
        finally:
            # Even failed/partial input must retire its original nonce/file.
            # Failure keeps the durable journal; a replaced process cannot adopt it.
            if created and self.previous is not None:self.retire()
