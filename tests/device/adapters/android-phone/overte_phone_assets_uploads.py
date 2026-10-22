"""Passive originals of normal bundle uploads; receipts alone prove no mapping."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_graphics_subject import entity_id
from adapters.normal_ui import NativeUIError
from overte_phone_assets_files import PhoneAssetsFiles
from overte_phone_assets_source import mapping_path
from overte_phone_create_source import nonce,digest,text

FILE='phone-assets-uploads.json'


def command(value):
    release=type(value) is dict and value.get('operation')=='release'
    exact(value,{'schemaVersion','commandId','action','operation','runId'}|({'instance','bundleIds'} if release else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-assets-uploads'
        and nonce(value['commandId']) and nonce(value['runId']) and value['operation'] in ('observe','release'))
    if release:
        need(nonce(value['instance']) and type(value['bundleIds']) is list and len(value['bundleIds'])<=64
            and value['bundleIds']==sorted(set(value['bundleIds'])) and all(entity_id(item) for item in value['bundleIds']))
    return value


def source(value,run,captured):
    exact(value,{'assetsUploadsVersion','instance','runId','valid','retired','activeBundles','liveRequests','retainedBundles','bundles'})
    need(type(value['assetsUploadsVersion']) is int and value['assetsUploadsVersion']==1 and nonce(value['instance']) and value['runId']==run
        and value['valid'] is True and type(value['retired']) is bool and type(value['bundles']) is list and len(value['bundles'])<=64)
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
        exact(bundle['connection'],{'domainId','sessionId','assetServerId'});need(all(entity_id(item) for item in bundle['connection'].values()))
        if bundle['active']:need(bundle['finishedEpochMs'] is None and bundle['errorSha256'] is None)
        else:need(integer(bundle['finishedEpochMs'],bundle['createdEpochMs'],captured) and digest(bundle['errorSha256']))
        for request in bundle['requests']:
            exact(request,{'instance','kind','issuedEpochMs','completedEpochMs','destroyedEpochMs','original'})
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
            if request['destroyedEpochMs'] is None:live+=1
            else:need(integer(request['destroyedEpochMs'],request['completedEpochMs'],captured))
    need(ids==sorted(ids))
    for key,actual in (('activeBundles',active),('liveRequests',live),('retainedBundles',len(ids))):need(type(value[key]) is int and value[key]==actual)
    need(not value['retired'] or not value['bundles']);return value


class PhoneAssetsUploads(PhoneAssetsFiles):
    def request(self,operation,run,instance=None,bundle_ids=None):
        try:
            call=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-assets-uploads',operation=operation,runId=run)
            if operation=='release':call.update(instance=instance,bundleIds=bundle_ids)
            else:need(instance is None and bundle_ids is None)
            command(call);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms();need(integer(requested,1));self.send(call)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=1048576)
                try:packet=decode(raw) if raw else None
                except json.JSONDecodeError:packet=None
                need(self.guard() is not False);now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(packet) is dict and packet.get('requestId')==call['commandId']:
                    exact(packet,{'schemaVersion','requestId','runId','operation','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
                    need(type(packet['schemaVersion']) is int and packet['schemaVersion']==1 and packet['runId']==run and packet['operation']==operation
                        and nonce(packet['instance']) and integer(packet['sequence'],1) and packet['processId']==self.pid and integer(packet['processId'],1)
                        and integer(packet['requestedEpochMs'],requested) and integer(packet['capturedEpochMs'],packet['requestedEpochMs'])
                        and packet['capturedEpochMs']-packet['requestedEpochMs']<1500)
                    fresh(packet['capturedEpochMs'],self.clock_ms());source(packet['source'],run,packet['capturedEpochMs'])
                    if self.last is not None:
                        need(packet['instance']==self.last['instance'] and packet['runId']==self.last['runId'] and packet['sequence']>self.last['sequence']
                            and packet['capturedEpochMs']>=self.last['capturedEpochMs'] and packet['source']['instance']==self.last['source']['instance']
                            and (not self.last['source']['retired'] or packet['source']['retired']))
                    need(self.guard() is not False);fresh(packet['capturedEpochMs'],self.clock_ms());now=self.monotonic();need(number(now,previous,1e15) and now-started<5)
                    self.last=deepcopy(packet);return deepcopy(packet)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Phone Assets upload receipts are unavailable or invalid') from None
        raise NativeUIError('Original Phone Assets upload receipts did not produce this request')
