"""Passive originals of normal bundle uploads; receipts alone prove no mapping."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_graphics_subject import entity_id
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_source import mapping_path,nonce,text,effective_epoch
from adapters.world_render_evidence import digest
import hashlib
import time

FILE='feature-pico-assets-uploads.json'
ACTION='feature-pico-assets-uploads-observe'


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and nonce(value['commandId']) and nonce(value['runId']))
    return value


def connection(value,run,captured):
    exact(value,{'domainId','sessionId','assetServerId','domainSession','canWrite'})
    need(all(entity_id(value[key]) for key in ('domainId','sessionId','assetServerId')) and type(value['canWrite']) is bool)
    session=value['domainSession'];exact(session,{'domainSessionVersion','instance','revision','connected','domainSha256','connectionBirth','connectedEpochMs'})
    need(type(session['domainSessionVersion']) is int and session['domainSessionVersion']==1 and nonce(session['instance'])
        and integer(session['revision'],1) and session['connected'] is True and nonce(session['connectionBirth'])
        and integer(session['connectedEpochMs'],1,captured)
        and session['domainSha256']==hashlib.sha256((run+':').encode()+uuid.UUID(value['domainId']).bytes).hexdigest())
    return value


def source(value,run,captured):
    exact(value,{'picoAssetsUploadsVersion','instance','runId','valid','retired','activeBundles','liveRequests','retainedBundles','bundles','totalCalls','calls','connection','originalActiveBundles'})
    need(type(value['picoAssetsUploadsVersion']) is int and value['picoAssetsUploadsVersion']==1 and nonce(value['instance']) and value['runId']==run
        and value['valid'] is True and type(value['retired']) is bool and type(value['bundles']) is list and len(value['bundles'])<=64)
    connection(value['connection'],run,captured)
    need(type(value['calls']) is list and len(value['calls'])<=512 and integer(value['totalCalls'],0,512)
        and value['totalCalls']==len(value['calls']) and integer(value['originalActiveBundles'],0,512))
    previous=0
    for call in value['calls']:
        exact(call,{'kind','epochMs','argumentsSha256'});need(call['kind'] in ('bundle','single','cancel')
            and integer(call['epochMs'],previous,captured) and digest(call['argumentsSha256']));previous=call['epochMs']
    ids=[];instances=set();live=active=0
    for bundle in value['bundles']:
        exact(bundle,{'id','runId','directorySha256','destination','primary','files','connection','createdEpochMs','active','finishedEpochMs','errorSha256','requests'})
        need(entity_id(bundle['id']) and bundle['id'] not in ids and bundle['runId']==run and digest(bundle['directorySha256'])
            and bundle['destination']=='/e2e-'+run+'/' and text(bundle['primary'],128) and type(bundle['active']) is bool
            and integer(bundle['createdEpochMs'],1,captured) and type(bundle['files']) is list and 1<=len(bundle['files'])<=7
            and type(bundle['requests']) is list and len(bundle['requests'])<=14)
        ids.append(bundle['id']);active+=bundle['active'];names=set();filenames=set()
        for row in bundle['files']:
            exact(row,{'relativePath','filenameSha256'});need(text(row['relativePath'],256) and row['relativePath'] not in names
                and not row['relativePath'].startswith('/') and all(part not in ('','.','..') for part in row['relativePath'].split('/'))
                and digest(row['filenameSha256']) and row['filenameSha256'] not in filenames)
            names.add(row['relativePath']);filenames.add(row['filenameSha256'])
        need(bundle['primary'] in names)
        exact(bundle['connection'],{'domainId','sessionId','assetServerId','domainSession'})
        need(all(bundle['connection'][key]==value['connection'][key] for key in bundle['connection']))
        if bundle['active']:need(bundle['finishedEpochMs'] is None and bundle['errorSha256'] is None)
        else:need(integer(bundle['finishedEpochMs'],bundle['createdEpochMs'],captured) and digest(bundle['errorSha256']))
        for request in bundle['requests']:
            exact(request,{'instance','kind','issuedEpochMs','completedEpochMs','destroyedEpochMs','original','lifetime'})
            need(nonce(request['instance']) and request['instance'] not in instances and request['kind'] in ('upload','mapping')
                and integer(request['issuedEpochMs'],bundle['createdEpochMs'],captured));instances.add(request['instance'])
            if request['completedEpochMs'] is None:need(request['original'] is None and request['destroyedEpochMs'] is None)
            else:
                need(integer(request['completedEpochMs'],request['issuedEpochMs'],captured));original=request['original']
                if request['kind']=='upload':
                    exact(original,{'filenameSha256','originalSha256','originalBytes','errorCode','returnedHash'})
                    need(digest(original['filenameSha256']) and original['filenameSha256'] in filenames and digest(original['originalSha256'])
                        and integer(original['originalBytes'],0,32768) and integer(original['errorCode'],0,64) and text(original['returnedHash'],64))
                    if original['errorCode']==0:need(original['originalBytes']>0 and original['returnedHash']==original['originalSha256'])
                else:
                    exact(original,{'path','hash','errorCode'});mapping_path(original['path'])
                    need(original['path'] in {bundle['destination']+name for name in names} and digest(original['hash']) and integer(original['errorCode'],0,64))
            life=request['lifetime'];flags={'requestAlive','finishedConnected','destroyedConnected','finishedCaptureAlive','destroyedCaptureAlive','callbacksInstalled','resourcesRetired'}
            exact(life,flags);need(all(type(life[key]) is bool for key in flags) and life['callbacksInstalled'] is True)
            retired=not any(life[key] for key in flags-{'callbacksInstalled','resourcesRetired'})
            need(life['resourcesRetired']==retired);live+=not retired
            if request['destroyedEpochMs'] is not None:need(integer(request['destroyedEpochMs'],request['completedEpochMs'],captured))
            if retired:need(request['destroyedEpochMs'] is not None and request['completedEpochMs'] is not None)
    need(ids==sorted(ids))
    for key,actual in (('activeBundles',active),('liveRequests',live),('retainedBundles',len(ids))):need(type(value[key]) is int and value[key]==actual)
    need(value['originalActiveBundles']>=active and (not value['retired'] or not value['bundles']));return value



def validate(value,request,pid,epoch):
    command(request);exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
        and value['runId']==request['runId'] and nonce(value['instance']) and integer(value['sequence'],1,512)
        and integer(value['processId'],1) and value['processId']==pid and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch);source(value['source'],request['runId'],value['capturedEpochMs']);return value


def continuity(before,after):
    if before is None:return
    a,b=before['source'],after['source']
    need(before['runId']==after['runId'] and before['instance']==after['instance'] and after['sequence']>before['sequence']
        and before['requestId']!=after['requestId'] and after['capturedEpochMs']>=before['capturedEpochMs']
        and a['instance']==b['instance'] and a['connection']==b['connection'] and b['totalCalls']>=a['totalCalls']
        and b['calls'][:a['totalCalls']]==a['calls'] and (not a['retired'] or b['retired']))


from adapters.native_avatar_render import _OriginalQuery


class PicoAssetsUploads(_OriginalQuery):
    """Reuse the closed source transport; seal own raw copies before publication."""
    def __init__(self,*args,intent=None,**kwargs):
        super().__init__(*args,**kwargs);need(not self.ios and (intent is None or callable(intent)))
        self.intent=intent;self.pending=None;self.history=[];self.last_raw=self.last_sha256=None;self._seen_raw=None
        original=self.original
        def capture():self._seen_raw=original();return self._seen_raw
        self.original=capture
    def read(self,run):
        old=self.last
        try:
            need(self.pending is None and len(self.history)<128)
            started=self.monotonic();need(number(started,0,1e15));epoch=self.clock_ms();need(integer(epoch,1))
            request=command(self._request(ACTION,runId=run))
            if self.intent is not None:need(self.intent(deepcopy(request)) is not False)
            self.pending=deepcopy(request);value=self._read(request,validate);continuity(old,value)
            raw=self._seen_raw;need(type(raw) is str and decode(raw)==value)
            sha256=hashlib.sha256(raw.encode()).hexdigest();retained=deepcopy(value);result=deepcopy(value)
            history=self.history+[dict(command=deepcopy(request),raw=raw,sha256=sha256)]
            need(self.guard() is not False);native=self.clock_ms();finished=self.monotonic();need(number(finished,started,1e15) and finished-started<5)
            validate(value,request,self.pid,effective_epoch(lambda:native,epoch,started,finished))
            self.last=retained;self.last_raw=raw;self.last_sha256=sha256;self.history=history;self.pending=None;return result
        except Exception:
            self.last=old;raise NativeUIError('Original Pico upload calls/resources remain unresolved') from None
    def restore(self,history,pending=None):
        need(self.last is None and not self.history and self.pending is None and type(history) is list and len(history)<=128)
        old=None;seen=set()
        for frame in history:
            exact(frame,{'command','raw','sha256'});request=command(frame['command'])
            need(type(frame['raw']) is str and digest(frame['sha256']) and hashlib.sha256(frame['raw'].encode()).hexdigest()==frame['sha256'])
            value=decode(frame['raw']);validate(value,request,self.pid,value.get('capturedEpochMs'));continuity(old,value)
            need(request['commandId'] not in seen);seen.add(request['commandId']);old=value
        if pending is not None:
            command(pending);need(pending['commandId'] not in seen and (old is None or pending['runId']==old['runId']))
        self.history=deepcopy(history);self.pending=deepcopy(pending)
        if old is not None:self.last=deepcopy(old);self.last_raw=history[-1]['raw'];self.last_sha256=history[-1]['sha256']
