"""One fixed actual Browse setting, native originals and durable one-shot CAS."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import math
import re
import secrets

from adapters.native_feature_observation import decode,exact,fresh,integer,need
from adapters.normal_feature_state import context
from adapters.pico4.create_callbacks import NativeCreateCallbacks
from adapters.token_create_ui import nonce

FILE='feature-create-browse-setting.json'
ACTION='feature-create-browse-setting'
OPERATIONS=('reserve','observe','claim','claim-read','restore','release')


def raw(value):
    exact(value,{'present','typeId','typeName','base64','sha256','stringValue'})
    need(type(value['present']) is bool and integer(value['typeId'],0,65535)
        and (value['typeName'] is None or type(value['typeName']) is str and 0<len(value['typeName'])<=256)
        and type(value['base64']) is str and len(value['base64'])<=10924)
    data=base64.b64decode(value['base64'],validate=True)
    need(0<len(data)<=8192 and base64.b64encode(data).decode()==value['base64']
        and hashlib.sha256(data).hexdigest()==value['sha256']
        and (value['stringValue'] is None or value['present'] and value['typeId']==10 and value['typeName']=='QString'
            and type(value['stringValue']) is str and len(value['stringValue'])<=8192))
    need(value['present'] or value['typeId']==0 and value['typeName'] is None and value['stringValue'] is None)
    return value


def browse_read(value,epoch):
    exact(value,{'before','after'})
    for row in value.values():
        exact(row,{'capturedEpochMs','raw'});need(integer(row['capturedEpochMs'],1,epoch));raw(row['raw'])
    need(value['after']['capturedEpochMs']>=value['before']['capturedEpochMs'])
    return value


def physical(value,epoch):
    exact(value,{'physicalVersion','format','pathSha256','capturedEpochMs','file','fileSha256','row'})
    need(type(value['physicalVersion']) is int and value['physicalVersion']==1 and value['format'] in ('ini','json')
        and integer(value['capturedEpochMs'],1,epoch)
        and all(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}',value[k]) for k in ('pathSha256','fileSha256')))
    file=value['file'];need(type(file) is dict and type(file.get('exists')) is bool)
    exact(file,{'exists'}|({'device','inode','bytes','mode','modified','changed'} if file['exists'] else set()))
    if file['exists']:
        need(all(type(file[k]) is str and re.fullmatch('[0-9]{1,24}',file[k]) for k in ('device','inode'))
            and integer(file['bytes'],0,1048576) and type(file['mode']) is int and file['mode']==0o600
            and all(type(file[k]) is str and re.fullmatch(r'[0-9]{1,20}\.[0-9]{9}',file[k]) for k in ('modified','changed')))
    row=value['row'];exact(row,{'present','base64','sha256'})
    need(type(row['present']) is bool and type(row['base64']) is str and len(row['base64'])<=43692)
    data=base64.b64decode(row['base64'],validate=True)
    need(len(data)<=32768 and base64.b64encode(data).decode()==row['base64'] and (row['present'] or not data)
        and hashlib.sha256((b'present:' if row['present'] else b'absent:')+data).hexdigest()==row['sha256'])
    need(file['exists'] or not row['present'] and value['fileSha256']==hashlib.sha256(b'').hexdigest())
    return value


def physical_original(value):
    need(value['createBrowseSettingVersion']==3)
    a,b=value['originalPhysical'],value['writer']['physical']
    return all(a[k]==b[k] for k in ('format','pathSha256','row'))


def physical_owned(value):
    need(value['createBrowseSettingVersion']==3)
    row=value['writer']['physical']['row'];owned=value['owned']
    if not owned['present']:return not row['present']
    if owned['typeId']!=10 or not row['present'] or owned['stringValue'] is None:return False
    data=base64.b64decode(row['base64'],validate=True);text=owned['stringValue']
    if value['writer']['physical']['format']=='json':
        try:original=decode('['+data.decode('utf-8')+']')
        except (ValueError,UnicodeError):return False
        return len(original)==1 and type(original[0]) is str and original[0]==('@'+text if text.startswith('@') else text)
    return (not text or bool(re.fullmatch('[A-Za-z0-9/._:-]+',text))) and data==text.encode('ascii')


def restored(value):
    return value['current']==value['original'] and value['writer']['raw']==value['original'] and physical_original(value)


def source(value,epoch):
    version=value.get('createBrowseSettingVersion');need(type(version) is int and version in (2,3))
    exact(value,{'createBrowseSettingVersion','leaseId','runId','createdEpochMs','original','current','claims','reads','owned','writer','restoreAttempted','restored','released'}|({'originalPhysical'} if version==3 else set()))
    need(type(value['createBrowseSettingVersion']) is int and value['createBrowseSettingVersion'] in (2,3)
        and nonce(value['leaseId']) and nonce(value['runId']) and integer(value['createdEpochMs'],1,epoch)
        and all(type(value[k]) is bool for k in ('restoreAttempted','restored','released'))
        and (not value['restored'] or value['restoreAttempted']) and type(value['claims']) is list and len(value['claims'])<=4)
    raw(value['original']);raw(value['current']);raw(value['owned']);seen=set()
    writer=value['writer'];exact(writer,{'id','capturedEpochMs','raw'}|({'physical'} if version==3 else set()))
    need(nonce(writer['id']) and integer(writer['capturedEpochMs'],value['createdEpochMs'],epoch));raw(writer['raw'])
    if version==3:
        physical(value['originalPhysical'],epoch);physical(writer['physical'],writer['capturedEpochMs'])
        need(value['createdEpochMs']<=value['originalPhysical']['capturedEpochMs']<=writer['physical']['capturedEpochMs']
            and all(value['originalPhysical'][k]==writer['physical'][k] for k in ('format','pathSha256')))
    need(type(value['reads']) is list and len(value['reads'])<=4)
    for row in value['reads']:
        exact(row,{'dialogId','sourceInstance','ticket','role','read','claimedEpochMs'})
        need(all(nonce(row[k]) for k in ('dialogId','sourceInstance','ticket')) and row['dialogId'] not in seen and row['role'] in ('import','export'))
        browse_read(row['read'],epoch)
        need(value['createdEpochMs']<=row['read']['before']['capturedEpochMs']
            and integer(row['claimedEpochMs'],row['read']['after']['capturedEpochMs'],epoch))
        seen.add(row['dialogId'])
    reads={r['dialogId']:r for r in value['reads']};seen=set()
    for claim in value['claims']:
        exact(claim,{'dialogId','sourceInstance','ticket','role','responseSha256','setting','registeredEpochMs','returnedEpochMs','claimedEpochMs'})
        need(all(nonce(claim[k]) for k in ('dialogId','sourceInstance','ticket')) and claim['dialogId'] not in seen
            and claim['role'] in ('import','export') and type(claim['responseSha256']) is str
            and re.fullmatch('[0-9a-f]{64}',claim['responseSha256'])
            and integer(claim['registeredEpochMs'],value['createdEpochMs'],epoch)
            and integer(claim['returnedEpochMs'],claim['registeredEpochMs'],epoch)
            and integer(claim['claimedEpochMs'],claim['returnedEpochMs'],epoch))
        need(claim['dialogId'] in reads and all(claim[k]==reads[claim['dialogId']][k] for k in ('sourceInstance','ticket','role'))
            and claim['returnedEpochMs']>=reads[claim['dialogId']]['claimedEpochMs'])
        raw(claim['setting']);need(claim['setting']['present'] and claim['setting']['typeId']==10 and claim['setting']['stringValue'] is not None)
        seen.add(claim['dialogId'])
    need(value['owned'] in [value['original']]+[r['read']['after']['raw'] for r in value['reads']]+[r['setting'] for r in value['claims']])
    if value['released']:
        need(value['current']==value['original'] and value['writer']['raw']==value['original'] and (not value['claims'] or value['restored']))
        if version==3:need(physical_original(value))
    return value


def validate(value,request,pid,epoch):
    exact(value,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','runId','operation','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(request) and value['requestId']==request
        and nonce(value['instance']) and nonce(value['runId']) and value['operation'] in OPERATIONS and integer(value['sequence'],1)
        and integer(pid,1) and value['processId']==pid and type(value['processId']) is int
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch);source(value['source'],value['capturedEpochMs']);need(value['source']['runId']==value['runId'])
    return value


def continuity(before,after):
    if before is None:return
    need(before['instance']==after['instance'] and before['runId']==after['runId'] and after['sequence']>before['sequence']
        and after['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source'],after['source']
    need(a['writer']['id']==b['writer']['id'] and b['writer']['capturedEpochMs']>=a['writer']['capturedEpochMs'])
    need(all(a[k]==b[k] for k in ('createBrowseSettingVersion','leaseId','runId','createdEpochMs','original'))
        and b['claims'][:len(a['claims'])]==a['claims'] and b['reads'][:len(a['reads'])]==a['reads']
        and (b['claims']!=a['claims'] or b['reads']!=a['reads'] or b['owned']==a['owned'])
        and all(not a[k] or b[k] for k in ('restoreAttempted','restored','released')))
    if a['createBrowseSettingVersion']==3:
        need(a['originalPhysical']==b['originalPhysical'] and b['writer']['physical']['capturedEpochMs']>=a['writer']['physical']['capturedEpochMs'])


class NativeCreateBrowseSetting(NativeCreateCallbacks):
    validate=staticmethod(validate)
    continuity=staticmethod(continuity)
    def request(self,operation,run,owner,extra,before):
        need(operation in OPERATIONS);self.operation,self.run,self.owner,self.extra,self.before=operation,run,owner,deepcopy(extra),before
        result=self.read();need(result['operation']==operation and result['runId']==run);return result
    def command(self,request):
        value=dict(schemaVersion=1,commandId=request,action=ACTION,operation=self.operation,runId=self.run,ownerToken=self.owner,**self.extra)
        self.before(deepcopy(value)) # Persist original nonce/intent BEFORE send.
        return value


class OwnedCreateBrowseSetting:
    def __init__(self,native,store,binding):
        self.native,self.store,self.binding=native,store,deepcopy(context(binding));self.previous=store.read()
        if self.previous is not None:
            self.check(self.previous)
            if self.previous['packet'] is not None:
                self.native.last=decode(self.previous['packet']['raw'])
    def check(self,value):
        exact(value,{'schemaVersion','binding','runId','ownerToken','commands','packet'})
        need(value['schemaVersion']==1 and type(value['schemaVersion']) is int and context(value['binding'])==self.binding
            and nonce(value['runId']) and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}',value['ownerToken'])
            and type(value['commands']) is list and len(value['commands'])<=12)
        ids=set()
        for command in value['commands']:
            operation=command.get('operation');exact(command,{'schemaVersion','commandId','action','operation','runId','ownerToken'}
                | ({'ticket','fileOwnerToken','dialogBinding'} if operation in ('claim','claim-read') else set()))
            need(command['schemaVersion']==1 and command['action']==ACTION and operation in OPERATIONS
                and nonce(command['commandId']) and command['commandId'] not in ids
                and command['runId']==value['runId'] and command['ownerToken']==value['ownerToken'])
            ids.add(command['commandId'])
        if value['packet'] is not None:
            record=value['packet'];exact(record,{'raw','sha256'})
            need(type(record['raw']) is str and hashlib.sha256(record['raw'].encode()).hexdigest()==record['sha256'])
            packet=decode(record['raw']);validate(packet,packet['requestId'],self.native.pid,packet['capturedEpochMs'])
            need(packet['runId']==value['runId'])
    def state(self):
        value=self.store.read();need(value is not None and value==self.previous);self.check(value);return value
    def write(self,value):
        self.check(value);self.store.write(value,self.previous);self.previous=deepcopy(value)
    def command(self,operation,extra=None):
        value=self.state()
        if operation!='observe':
            matching=[c for c in value['commands'] if c['operation']==operation
                and (operation not in ('claim','claim-read') or c['dialogBinding']['dialogId']==extra['dialogBinding']['dialogId'])]
            need(not matching) # Uncertain mutations are observe-only, never resend.
        def before(command):
            if operation!='observe':
                state=self.state();need(len(state['commands'])<12);state['commands'].append(command);self.write(state)
        packet=self.native.request(operation,value['runId'],value['ownerToken'],extra or {},before)
        state=self.state();state['packet']=dict(raw=self.native.last_raw,sha256=self.native.last_sha256);self.write(state);return packet['source']
    def reserve(self,run):
        if self.previous is None:
            self.write(dict(schemaVersion=1,binding=self.binding,runId=run,ownerToken=secrets.token_hex(32),commands=[],packet=None))
            actual=self.command('reserve');need(actual['createBrowseSettingVersion']==3);return actual
        need(self.state()['runId']==run);actual=self.command('observe');need(actual['createBrowseSettingVersion']==3);return actual
    def observe(self):return self.command('observe')
    def claim_read(self,files,binding):
        native=self.observe();need(native['createBrowseSettingVersion']==3)
        found=[r for r in native['reads'] if r['dialogId']==binding['dialogId']]
        if found:
            need(len(found)==1 and found[0]['ticket']==files['ticket'] and found[0]['role']==binding['role']);return native
        return self.command('claim-read',dict(ticket=files['ticket'],fileOwnerToken=files['ownerToken'],dialogBinding=binding))
    def claim(self,files,binding):
        native=self.observe();need(native['createBrowseSettingVersion']==3)
        found=[r for r in native['claims'] if r['dialogId']==binding['dialogId']]
        if found:
            need(len(found)==1 and found[0]['ticket']==files['ticket'] and found[0]['role']==binding['role']);return native
        return self.command('claim',dict(ticket=files['ticket'],fileOwnerToken=files['ownerToken'],dialogBinding=binding))
    def restore(self):
        actual=self.observe()
        if actual['current']==actual['original'] and not actual['claims']:
            need(restored(actual));return actual
        if not actual['restoreAttempted']:
            started=previous=self.native.monotonic()
            need(type(started) in (int,float) and math.isfinite(started) and started>=0)
            for attempt in range(32):
                current=self.native.monotonic();need(type(current) in (int,float) and math.isfinite(current) and previous<=current<=started+3)
                previous=current;need(actual['current']==actual['owned'])
                if actual['writer']['raw']==actual['owned'] and physical_owned(actual):break
                remaining=3-(current-started);need(remaining>0 and attempt<31)
                self.native.sleep(min(.1,remaining));actual=self.observe();need(not actual['restoreAttempted'])
            self.command('restore')
        actual=self.observe();need(restored(actual) and actual['restored']);return actual
    def release(self):
        actual=self.restore()
        if not actual['released']:self.command('release')
        actual=self.observe();need(actual['released'] and restored(actual))
        return actual
    def retire(self):
        actual=self.observe();need(actual['released'] and restored(actual))
        self.store.discard(self.state());self.previous=None
