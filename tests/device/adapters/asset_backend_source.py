"""Strict originals from the independently owned AssetServer native source.

Backend clocks remain in their own process domain. This module performs no
transport and cannot turn missing data, callback completion or UI state into
server retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import posixpath
import re
from copy import deepcopy
from adapters.native_feature_observation import decode, exact, integer, need
from adapters import asset_backend_work as work
from adapters.script_feature.history import same

VERSION=1
HASH=re.compile('[0-9a-f]{64}')
STAT={'device','inode','uid','mode','links','modifiedSeconds','modifiedNanoseconds','changedSeconds','changedNanoseconds'}


def digest(value):
    need(type(value) is str and HASH.fullmatch(value) is not None);return value


def text(value,maximum=4096):
    need(type(value) is str and len(value)<=maximum and not any(ord(c)<32 or ord(c)==127 for c in value));return value


def path(value):
    text(value);need(value.startswith('/') and posixpath.normpath(value)==value and not value.startswith('//'));return value


def stat(value,*,directory=False):
    exact(value,STAT | (set() if directory else {'bytes'}))
    for key,item in value.items():
        need(type(item) is str and re.fullmatch('0|[1-9][0-9]{0,19}',item) is not None)
        need(int(item)<=2**64-1)
    need(int(value['inode'])>0 and int(value['links'])>0 and int(value['mode'])<=0o7777
        and int(value['modifiedNanoseconds'])<10**9 and int(value['changedNanoseconds'])<10**9)
    if not directory:need(value['links']=='1' and int(value['bytes'])<=2**53-1)
    return value


def directory(value):
    exact(value,{'configuredPath','canonicalPath','identity'});path(value['configuredPath']);path(value['canonicalPath']);stat(value['identity'],directory=True);return value


def file(value,*,name=None,limit=65536,required=False):
    need(type(value) is dict and type(value.get('exists')) is bool)
    exact(value,{'name','exists'} | ({'identity','body'} if value['exists'] else set()))
    text(value['name'],128);need(value['name'] not in ('','.','..') and '/' not in value['name'] and (name is None or value['name']==name))
    if not value['exists']:need(not required);return None
    stat(value['identity']);body=value['body'];exact(body,{'retained','base64','sha256'});need(type(body['retained']) is bool)
    if not body['retained']:need(body['base64'] is body['sha256'] is None);return None
    need(type(body['base64']) is str and len(body['base64'])<=4*((limit+2)//3))
    try:raw=base64.b64decode(body['base64'],validate=True)
    except (ValueError,TypeError):need(False)
    need(base64.b64encode(raw).decode()==body['base64'] and len(raw)==int(value['identity']['bytes']) and len(raw)<=limit
        and hashlib.sha256(raw).hexdigest()==digest(body['sha256']));return raw


def object_bytes(raw,limit):
    need(type(raw) is bytes and len(raw)<=limit)
    try:result=decode(raw.decode('utf-8'),limit=limit)
    except (UnicodeError,ValueError):need(False)
    need(type(result) is dict);return result


def root_identity(value):
    exact(value,{'device','inode'})
    for item in value.values():need(type(item) is str and re.fullmatch('0|[1-9][0-9]{0,19}',item) is not None and int(item)<=2**64-1)
    need(int(value['inode'])>0);return value


def admission(value,*,pid=None,owner=None):
    exact(value,{'assetBackendAdmissionVersion','instance','processId','role','ownerSha256','serverId','domainId','sourceRootIdentity','dataRoot','dataRootIdentity','clockDomain','clock'})
    need(type(value['assetBackendAdmissionVersion']) is int and value['assetBackendAdmissionVersion']==VERSION
        and integer(value['processId'],1) and (pid is None or value['processId']==pid) and value['role']=='asset-server'
        and value['clockDomain']=='asset-server-native' and (owner is None or value['ownerSha256']==owner))
    for key in ('instance','serverId','domainId'):work.identity(value[key])
    digest(value['ownerSha256']);root_identity(value['sourceRootIdentity']);root_identity(value['dataRootIdentity']);path(value['dataRoot']);work.clock(value['clock']);return value


def query(value,original):
    admission(original);exact(value,{'schemaVersion','commandId','action','runId','ticket','processId','instance'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']=='feature-assets-backend-observe'
        and type(value['commandId']) is str and re.fullmatch('assets-[0-9a-f]{32}',value['commandId']) is not None
        and integer(value['processId'],1) and all(value[key]==original[key] for key in ('processId','instance')))
    for key in ('runId','ticket'):need(type(value[key]) is str and re.fullmatch('[0-9a-f]{32}',value[key]) is not None)
    return value


def mappings(value):
    need(type(value) is dict and len(value)<=512)
    for key,item in value.items():path(key);need(key!='/');digest(item)
    return value


def snapshot(value,*,pid=None):
    exact(value,{'assetBackendSnapshotVersion','available','complete','serverId','domainId','resourcesRoot','filesRoot','memoryMappings','mapFile',
        'persistedMappings','blobs','unknownEntries','meta','workBefore','workAfter','nodes','hiddenPrefix','modelBakeVersion','modelOutputName','bakeableModelExtensions'})
    need(type(value['assetBackendSnapshotVersion']) is int and value['assetBackendSnapshotVersion']==VERSION
        and type(value['available']) is type(value['complete']) is bool)
    work.identity(value['serverId']);work.identity(value['domainId']);directory(value['resourcesRoot']);directory(value['filesRoot'])
    need(value['filesRoot']['canonicalPath'].startswith(value['resourcesRoot']['canonicalPath']+'/'))
    need(type(value['memoryMappings']) is list and len(value['memoryMappings'])<=512);memory={}
    for row in value['memoryMappings']:
        exact(row,{'path','hash'});path(row['path']);digest(row['hash']);need(row['path'] not in memory);memory[row['path']]=row['hash']
    mappings(memory);raw=file(value['mapFile'],name='map.json')
    if value['persistedMappings'] is not None:
        mappings(value['persistedMappings']);need(raw is not None and same(object_bytes(raw,65536),value['persistedMappings']))
    if value['complete']:
        need(value['available'] and (same(value['persistedMappings'],memory) if value['mapFile']['exists'] else not memory))
    need(type(value['blobs']) is list and len(value['blobs'])<=512);blobs={};retained=0
    for row in value['blobs']:
        digest(row.get('name'));need(row['name'] not in blobs);body=file(row,limit=32768,required=True);blobs[row['name']]=(row,body)
        if body is not None:need(hashlib.sha256(body).hexdigest()==row['name']);retained+=len(body)
    need(retained<=262144 and type(value['unknownEntries']) is list and len(value['unknownEntries'])<=512)
    for name in value['unknownEntries']:text(name,255);need('/' not in name)
    need(not value['complete'] or not value['unknownEntries'])
    need(value['hiddenPrefix']=='/.baked/' and integer(value['modelBakeVersion']) and value['modelOutputName']=='asset.fbx'
        and type(value['bakeableModelExtensions']) is list and value['bakeableModelExtensions']==['fbx'])
    need(type(value['meta']) is list and len(value['meta'])<=512);meta=set()
    expected={key for key in memory if re.fullmatch('/\\.baked/[0-9a-f]{64}/meta\\.json',key)}
    for row in value['meta']:
        exact(row,{'mappingPath','originalHash','blobHash','decoded'});digest(row['originalHash']);digest(row['blobHash'])
        need(row['mappingPath']=='/.baked/'+row['originalHash']+'/meta.json' and row['mappingPath'] not in meta and memory.get(row['mappingPath'])==row['blobHash']);meta.add(row['mappingPath'])
        decoded=row['decoded']
        if decoded is not None:
            exact(decoded,{'bakeVersion','failedLastBake','lastBakeErrors','redirectTarget'})
            need(integer(decoded['bakeVersion']) and type(decoded['failedLastBake']) is bool);text(decoded['lastBakeErrors'],32768);text(decoded['redirectTarget'])
            need(row['blobHash'] in blobs and blobs[row['blobHash']][1] is not None)
            original=object_bytes(blobs[row['blobHash']][1],32768)
            need(all(same(original.get(rawkey,'' if key=='redirectTarget' else None),decoded[key]) for key,rawkey in
                (('bakeVersion','bake_version'),('failedLastBake','failed_last_bake'),('lastBakeErrors','last_bake_errors'),('redirectTarget','redirect_target'))))
    need(meta==expected)
    before,after=value['workBefore'],value['workAfter'];work.validate(before,pid=pid);work.validate(after,pid=pid);work.accept(before,after)
    need(not value['complete'] or all(row['available'] and row['complete'] for row in (before,after)))
    need(type(value['nodes']) is list and len(value['nodes'])<=256);nodes=set()
    for row in value['nodes']:
        exact(row,{'nodeId','type','canWriteAssets'});work.identity(row['nodeId']);need(row['nodeId'] not in nodes and integer(row['type'],0,255) and type(row['canWriteAssets']) is bool);nodes.add(row['nodeId'])
    return value


def observation(value,request,original,admission_sha):
    admission(original);query(request,original);digest(admission_sha)
    exact(value,{'assetBackendObservationVersion','requestId','instance','sequence','runId','ticket','processId','ownerSha256','serverId','domainId',
        'admissionSha256','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['assetBackendObservationVersion']) is int and value['assetBackendObservationVersion']==VERSION and integer(value['sequence'],1)
        and value['requestId']==request['commandId'] and value['admissionSha256']==admission_sha
        and all(same(value[key],original[key]) for key in ('processId','instance','ownerSha256','serverId','domainId','clockDomain'))
        and all(value[key]==request[key] for key in ('runId','ticket')))
    work.after(value['clockBefore'],original['clock']);work.after(value['clockAfter'],value['clockBefore'])
    # Missing hooks are diagnostic-only and never validated as empty state.
    snapshot(value['source'],pid=value['processId']);source=value['source'];need(all(source[key]==value[key] for key in ('serverId','domainId')))
    need(source['resourcesRoot']['canonicalPath']==original['dataRoot'] and all(source['resourcesRoot']['identity'][key]==original['dataRootIdentity'][key] for key in ('device','inode')))
    work.after(source['workBefore']['clock'],value['clockBefore']);work.after(value['clockAfter'],source['workAfter']['clock']);return value


def saved(value,packet,raw):
    exact(value,{'assetBackendSavedVersion','instance','requestId','processId','admissionSha256','original'})
    need(type(value['assetBackendSavedVersion']) is int and value['assetBackendSavedVersion']==VERSION
        and all(same(value[key],packet[key]) for key in ('instance','requestId','processId','admissionSha256')))
    original=value['original'];exact(original,{'file','identity','sha256'});stat(original['identity']);digest(original['sha256'])
    need(original['file']=='asset-backend-original-'+packet['requestId']+'.json' and type(raw) is bytes
        and len(raw)==int(original['identity']['bytes']) and hashlib.sha256(raw).hexdigest()==original['sha256']
        and same(object_bytes(raw,2097152),packet));return value


def accept(previous,value):
    if previous is not None:
        need(all(same(previous[key],value[key]) for key in ('instance','processId','ownerSha256','serverId','domainId','admissionSha256','clockDomain','runId','ticket'))
            and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'])
        work.after(value['clockBefore'],previous['clockAfter']);work.accept(previous['source']['workAfter'],value['source']['workBefore'])
        for key in ('resourcesRoot','filesRoot'):
            old,new=previous['source'][key],value['source'][key]
            need(all(old[field]==new[field] for field in ('configuredPath','canonicalPath')) and all(old['identity'][field]==new['identity'][field] for field in ('device','inode','uid','mode')))
    return deepcopy(value)
