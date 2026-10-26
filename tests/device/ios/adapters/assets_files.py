"""Owned Assets INPUT bundle storage and original native consumer inventories.

The files are test input only. Native upload holders are client objects, not
AssetServer/oven work. No upload, mapping, hash, bake or rendering is established.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import secrets
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import check as transport_check
from adapters.script_feature.history import MAX_RAW,canonical,pack,unpack,same
from feature_journeys.asset_fixture import BUNDLES,bundle
from feature_journeys.contract import identifier
from feature_journeys.fixtures import companion,pinned_resource
from ios.adapters.assets_controls import identity,inventory,local,folder
from ios.adapters.assets_budget import operation
from ios.adapters.assets_file_sources import FileSources,sync

VERSION=1
OWNER_VERSION=2
ACTION='feature-ios-assets-files'
FILE=ACTION+'.json'
LIMIT=262144


def encoded(raw):
    return base64.b64encode(raw).decode('ascii')


def original_bytes(value):
    need(type(value) is str and 0<len(value)<=43692)
    raw=base64.b64decode(value,validate=True)
    need(0<len(raw)<=32768 and encoded(raw)==value);return raw


def inode(value,*,directory=False):
    exact(value,{'device','inode'} if directory else {'device','inode','bytes','modifiedSeconds','modifiedNanoseconds','changedSeconds','changedNanoseconds'})
    for part in value.values():need(type(part) is str and re.fullmatch('0|[1-9][0-9]{0,19}',part) and int(part)<2**64)
    need(int(value['inode'])>0)
    if not directory:need(int(value['modifiedNanoseconds'])<10**9 and int(value['changedNanoseconds'])<10**9)


def inputs(run,ticket,url,resource):
    manifest=bundle(run,ticket,url,resource);result={}
    for row in manifest['files']:
        path=row['relativePath'];name=resource if resource=='asset-stand.fbx' else resource.split('/')[0]+'/'+path
        raw=pinned_resource(name) if resource=='asset-stand.fbx' else companion(name)
        need(len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']);result[path]=encoded(raw)
    need(sum(len(original_bytes(value)) for value in result.values())<=65536);return result


def rows(value,resource):
    need(resource in BUNDLES and type(value) is list and [row.get('path') for row in value]==list(BUNDLES[resource][1]))
    for row in value:
        need(type(row.get('exists')) is bool)
        exact(row,{'path','exists'}|({'bytes','sha256','base64','identity'} if row['exists'] else set()))
        if not row['exists']:continue
        raw=original_bytes(row['base64'])
        need(type(row['bytes']) is int and row['bytes']==len(raw) and row['sha256']==hashlib.sha256(raw).hexdigest())
        inode(row['identity']);need(row['identity']['bytes']==str(len(raw)))
    return value


def command(value):
    need(type(value) is dict);operation=value.get('operation')
    exact(value,{'schemaVersion','commandId','action','runId','ticket','ownerToken','resource','operation'}
        |({'files'} if operation=='stage' else {'originals'} if operation in ('retire-primary','release') else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId'])
        and type(value['ownerToken']) is str and re.fullmatch('[a-f0-9]{64}',value['ownerToken'])
        and value['resource'] in BUNDLES and operation in ('stage','observe','retire-primary','release'))
    identifier(value['runId']);identifier(value['ticket'])
    if operation=='stage':
        exact(value['files'],set(BUNDLES[value['resource']][1]))
        need(sum(len(original_bytes(raw)) for raw in value['files'].values())<=65536)
    if operation in ('retire-primary','release'):rows(value['originals'],value['resource'])
    need(len(json.dumps(value,allow_nan=False).encode())<=131072);return value


def clock(value):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs']))


def work(value,pid):
    exact(value,{'iosAssetUploadWorkVersion','available','complete','instance','processId','sequence','clock','jobs'})
    need(type(value['iosAssetUploadWorkVersion']) is int and value['iosAssetUploadWorkVersion']==VERSION
        and type(value['available']) is type(value['complete']) is bool and value['processId']==pid
        and integer(value['processId'],1) and integer(value['sequence'],1) and type(value['jobs']) is list and len(value['jobs'])<=4096)
    identity(value['instance']);clock(value['clock']);seen=set()
    for row in value['jobs']:
        exact(row,{'id','kind','files','created','alive','terminal','ended','expired','entered','returned','pendingBodies'})
        identity(row['id']);need(row['id'] not in seen);seen.add(row['id'])
        need(row['kind'] in ('bundle','upload') and type(row['files']) is list and 0<len(row['files'])<=32
            and type(row['alive']) is type(row['terminal']) is bool and integer(row['entered']) and integer(row['returned'],0,row['entered'])
            and integer(row['pendingBodies']) and row['pendingBodies']==row['entered']-row['returned'])
        for path in row['files']:need(type(path) is str and path.startswith('/') and len(path)<=4096 and '\x00' not in path)
        clock(row['created'])
        for key in ('created','ended','expired'):
            if row[key] is None:continue
            clock(row[key]);need(all(row['created'][part]<=row[key][part]<=value['clock'][part] for part in ('epochMs','monotonicMs')))
        need((row['expired'] is None)==row['alive'])
        if row['kind']=='bundle':need((row['ended'] is not None)==row['terminal'])
        else:need(row['ended'] is None and not row['terminal'])
    return value


def quiet(source,*,selected=None):
    ui=source['ui'];jobs=source['work'];need(ui['available'] and ui['complete'] and jobs['available'] and jobs['complete'])
    pickers=[]
    for row in ui['roots']:
        if not row['alive']:continue
        if row['role']=='page':need(not row['busy'] and not row['bundleRequest'] and not row['pendingBundle'] and not row['destinationOpen'])
        else:pickers.append(row)
    if selected is None:need(not pickers)
    else:
        need(len(pickers)==1);picker=pickers[0]
        need(picker['visible'] and picker['windowId'] is not None and not picker['closing'] and not picker['requestId']
            and not picker['bundleReview'] and selected in picker['chosen'])
    for row in jobs['jobs']:need(not row['alive'] and row['pendingBodies']==0 and (row['kind']!='bundle' or row['terminal']))


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosAssetsFilesVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsFilesVersion']) is int and value['iosAssetsFilesVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and type(value['processId']) is int and value['processId']==pid
        and integer(pid,1) and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance'])
        and integer(value['sequence'],1,10**9) and value['clockDomain']=='native-main-assets-files')
    before,after=value['clockBefore'],value['clockAfter'];clock(before);clock(after)
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'files','ui','work'})
    inventory(source['ui'],pid=pid);work(source['work'],pid)
    need(before['epochMs']<=source['ui']['capturedEpochMs']<=source['work']['clock']['epochMs']<=after['epochMs'])
    files=source['files'];operation=query['operation']
    if operation!='observe':
        exact(files,{'performed'});need(files['performed'] is True)
        if operation in ('retire-primary','release'):quiet(source,selected=None if operation=='release' else _primary(query,source))
    else:
        need(type(files.get('exists')) is bool)
        exact(files,{'exists','files'}|({'directory','complete','retiredPrimary','releasing','manifest','ownerBase64','seal'} if files['exists'] else set()))
        if not files['exists']:need(files['files']==[])
        else:
            expected_leaf='feature-assets-'+query['runId']+'-'+query['ownerToken'][:16]
            need(folder(local(files['directory'])).endswith('/'+expected_leaf))
            need(all(type(files[key]) is bool for key in ('complete','retiredPrimary','releasing')))
            rows(files['files'],query['resource']);manifest=files['manifest']
            exact(manifest,{'assetFileOwnerVersion','runId','ownerToken','ticket','resource','primaryPath','files'})
            owner_bytes=original_bytes(files['ownerBase64']);need(len(owner_bytes)<=8192 and same(decode(owner_bytes.decode('utf-8')),manifest))
            need(type(manifest['assetFileOwnerVersion']) is int and manifest['assetFileOwnerVersion']==VERSION
                and all(manifest[key]==query[key] for key in ('runId','ownerToken','ticket','resource'))
                and manifest['primaryPath']==BUNDLES[query['resource']][0] and type(manifest['files']) is list
                and [row.get('path') for row in manifest['files']]==list(BUNDLES[query['resource']][1]))
            for original,row in zip(manifest['files'],files['files']):
                exact(original,{'path','bytes','sha256'});need(integer(original['bytes'],1,32768) and type(original['sha256']) is str and re.fullmatch('[a-f0-9]{64}',original['sha256']))
                if row['exists']:need(row['bytes']==original['bytes'] and row['sha256']==original['sha256'])
                elif files['complete'] and not files['releasing']:need(files['retiredPrimary'] and row['path']==manifest['primaryPath'])
            if not files['complete']:need(files['seal'] is None)
            else:
                seal=files['seal'];exact(seal,{'assetFileSealVersion','ownerSha256','root','files'})
                need(type(seal['assetFileSealVersion']) is int and seal['assetFileSealVersion']==VERSION
                    and seal['ownerSha256']==hashlib.sha256(owner_bytes).hexdigest() and type(seal['files']) is list
                    and [row.get('path') for row in seal['files']]==list(BUNDLES[query['resource']][1]))
                inode(seal['root'],directory=True)
                for sealed,original,row in zip(seal['files'],manifest['files'],files['files']):
                    exact(sealed,{'path','identity','parent'});inode(sealed['identity']);inode(sealed['parent'],directory=True)
                    need(sealed['identity']['bytes']==str(original['bytes']))
                    if '/' not in sealed['path']:need(same(sealed['parent'],seal['root']))
                    if row['exists']:need(same(row['identity'],sealed['identity']))
    if previous is not None:
        need(all(value[key]==previous[key] for key in ('instance','runId','processId')) and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId'] and all(before[key]>=previous['clockAfter'][key] for key in before)
            and source['ui']['instance']==previous['source']['ui']['instance'] and source['ui']['sequence']>previous['source']['ui']['sequence']
            and source['work']['instance']==previous['source']['work']['instance'] and source['work']['sequence']>previous['source']['work']['sequence'])
        old=previous['source']['work'];new=source['work'];need(all(new['clock'][key]>=old['clock'][key] for key in new['clock']) and len(new['jobs'])>=len(old['jobs']))
        for name in ('ui','work'):need(previous['source'][name]['complete'] or not source[name]['complete'])
        old_roots=previous['source']['ui']['roots'];need(len(source['ui']['roots'])>=len(old_roots))
        for a,b in zip(old_roots,source['ui']['roots']):
            need(all(a[key]==b[key] for key in ('rootId','role','componentSource','ownerRootId','firstObservedEpochMs')) and (a['alive'] or not b['alive']))
        for a,b in zip(old['jobs'],new['jobs']):
            need(all(same(a[key],b[key]) for key in ('id','kind','files','created')) and (a['alive'] or not b['alive'])
                and (not a['terminal'] or b['terminal']) and b['entered']>=a['entered'] and b['returned']>=a['returned'])
            for key in ('ended','expired'):
                if a[key] is not None:need(same(a[key],b[key]))
    return value


def _primary(query,source):
    pickers=[row for row in source['ui']['roots'] if row['alive'] and row['role']=='picker']
    need(len(pickers)==1)
    leaf='feature-assets-'+query['runId']+'-'+query['ownerToken'][:16]
    selected=[url for url in pickers[0]['chosen'] if local(url).endswith('/'+leaf+'/'+BUNDLES[query['resource']][0])]
    need(len(selected)==1);return selected[0]


class IOSAssetsFiles:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=self.last_query=None

    @operation
    def request(self,operation,run,ticket,token,resource,*,files=None,originals=None,retain=None,retain_raw=None):
        query=dict(schemaVersion=VERSION,commandId='ios-'+uuid.uuid4().hex,action=ACTION,operation=operation,
            runId=run,ticket=ticket,ownerToken=token,resource=resource)
        if files is not None:query['files']=deepcopy(files)
        if originals is not None:query['originals']=deepcopy(originals)
        command(query);need((retain is None or callable(retain)) and (retain_raw is None or callable(retain_raw)) and (retain is None or retain_raw is None));need(self.guard() is not False)
        started=last=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
        transport_check();self.send(query) # Never resend this input after uncertainty.
        for attempt in range(61):
            transport_check();need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,last,started+1.5) and now-started<1.5);last=now
            if type(value) is dict and value.get('requestId')==query['commandId']:
                if retain_raw is not None:retain_raw(deepcopy(query),deepcopy(value),raw)
                if retain is not None:retain(deepcopy(query),deepcopy(value))
                epoch=self.clock_ms();need(integer(epoch,requested));validate(value,query,self.pid,epoch,self.last)
                need(value['clockBefore']['epochMs']>=requested and self.guard() is not False)
                now=self.monotonic();need(number(now,last,started+1.5) and now-started<1.5)
                self.last,self.last_query=deepcopy(value),deepcopy(query);return deepcopy(value)
            if attempt<60:self.sleep(.025)
        raise NativeUIError('Original Assets input file source did not produce this request')


class OwnedAssetsFiles:
    """Write-ahead storage ownership; lost mutations are recovered by reads only."""
    def __init__(self,native,store,binding,run,url,*,lock,role='primary'):
        need(isinstance(native,IOSAssetsFiles) and isinstance(store,PrivateFeatureState));context(binding);identifier(run)
        self.native,self.store,self.binding,self.run,self.url,self.lock=native,store,deepcopy(binding),run,url,lock
        need(str(native.pid)==binding['processIdentity']);lock.assert_held();self.previous=store.read();self.state=None
        self.role=role;self.storage_version=OWNER_VERSION;self.sources=FileSources(self,role,self.source_guard,self.save)
        if self.previous is not None:
            self.state=self.decode(self.previous)
            if self.state['originals']:
                last=self.state['originals'][-1];native.last=deepcopy(last['packet']);native.last_query=deepcopy(last['query'])

    def source_guard(self):
        # These are retained local originals, not fresh device facts. Native
        # candidate/process/clock guards remain on every actual native request.
        self.lock.assert_held();PrivateFeatureState(self.store.path)._parent();return True

    def legacy_state(self,value):
        exact(value,{'iosAssetsFileOwnerVersion','runId','fixtureUrl','binding','payload'})
        need(type(value['iosAssetsFileOwnerVersion']) is int and value['iosAssetsFileOwnerVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.url and same(value['binding'],self.binding))
        states=unpack(value['payload']);need(len(states)==1);state=states[0]
        return self.validate_state(state)

    def decode(self,value):
        need(type(value) is dict and type(value.get('iosAssetsFileOwnerVersion')) is int)
        if value['iosAssetsFileOwnerVersion']==VERSION:
            self.storage_version=VERSION;return self.legacy_state(value)
        exact(value,{'iosAssetsFileOwnerVersion','runId','fixtureUrl','binding','role','payload'})
        need(value['iosAssetsFileOwnerVersion']==OWNER_VERSION and value['runId']==self.run and value['fixtureUrl']==self.url and same(value['binding'],self.binding) and value['role']==self.role)
        states=unpack(value['payload']);need(len(states)==1);stored=states[0]
        exact(stored,{'phase','token','ticket','resource','inputManifest','directory','sources'});self.sources.load(stored['sources'])
        planned=inputs(self.run,stored['ticket'],self.url,stored['resource']);expected=[dict(path=path,bytes=len(original_bytes(raw)),sha256=hashlib.sha256(original_bytes(raw)).hexdigest()) for path,raw in planned.items()]
        need(same(stored['inputManifest'],expected));entries=[]
        for index,reference in enumerate(self.sources.refs):
            record=self.sources.read_record(reference)
            if record['kind']=='legacy-owner':
                need(index==0 and self.sources.migration is not None);legacy=self.legacy_state(decode(base64.b64decode(record['rawBase64']).decode('utf-8'),limit=65536))
                need(all(same(legacy[key],stored[key]) for key in ('token','ticket','resource')) and same(legacy['files'],planned));entries.extend(deepcopy(legacy['originals']))
            else:entries.append(dict(query=deepcopy(record['query']),packet=decode(record['raw'])))
        state=dict(phase=stored['phase'],token=stored['token'],ticket=stored['ticket'],resource=stored['resource'],files=planned,directory=stored['directory'],originals=entries)
        need(self.sources.pending is None or state['phase']!='retired');self.storage_version=OWNER_VERSION;return self.validate_state(state)

    def validate_state(self,state):
        need(len(canonical(state))<=MAX_RAW)
        exact(state,{'phase','token','ticket','resource','files','directory','originals'})
        need(state['phase'] in ('reserved','staging','staged','retiring-primary','primary-retired','releasing','retired')
            and type(state['token']) is str and re.fullmatch('[a-f0-9]{64}',state['token']) and type(state['originals']) is list and len(state['originals'])<=128)
        identifier(state['ticket']);need(same(state['files'],inputs(self.run,state['ticket'],self.url,state['resource'])))
        if state['directory'] is not None:need(folder(local(state['directory'])).endswith('/feature-assets-'+self.run+'-'+state['token'][:16]))
        previous=None;first_seal=None
        for entry in state['originals']:
            exact(entry,{'query','packet'});query=entry['query']
            need(all(query[key]==expected for key,expected in (('runId',self.run),('ticket',state['ticket']),('ownerToken',state['token']),('resource',state['resource']))))
            if query['operation'] in ('retire-primary','release'):
                need(previous is not None and previous['source']['files'].get('exists') is True
                    and same(query['originals'],previous['source']['files']['files']))
            validate(entry['packet'],query,self.native.pid,previous=previous);previous=entry['packet']
            source=entry['packet']['source']['files']
            if query['operation']=='stage':need(same(query['files'],state['files']))
            if query['operation']=='observe' and source['exists']:
                if source['complete']:
                    original=(source['manifest'],source['ownerBase64'],source['seal'])
                    if first_seal is None:first_seal=original
                    else:need(same(original,first_seal))
                for row in source['manifest']['files']:
                    raw=original_bytes(state['files'][row['path']]);need(row['bytes']==len(raw) and row['sha256']==hashlib.sha256(raw).hexdigest())
                for row in source['files']:
                    if row['exists']:need(row['base64']==state['files'][row['path']])
        if state['phase'] not in ('reserved','staging'):
            need(previous is not None and state['directory'] is not None)
            # Mutation replies may follow the last admitted observation while
            # a write-ahead phase remains issued. They never become file proof.
            observed=[entry['packet'] for entry in state['originals'] if entry['query']['operation']=='observe']
            need(observed);last=observed[-1]['source'];files=last['files']
            if state['phase']=='retired':need(files=={'exists':False,'files':[]});quiet(last)
            elif state['phase']=='releasing':
                quiet(last)
                need(files=={'exists':False,'files':[]} or files.get('exists') is True and files['directory']==state['directory'] and files['complete'])
            else:
                need(files.get('exists') is True and files['directory']==state['directory'] and files['complete'])
                if state['phase']=='staged':need(not files['retiredPrimary'] and not files['releasing'] and all(row['exists'] for row in files['files']))
                elif state['phase']=='retiring-primary':
                    before=[packet['source'] for packet in observed if packet['source']['files'].get('exists') is True
                        and not packet['source']['files']['retiredPrimary'] and all(row['exists'] for row in packet['source']['files']['files'])]
                    need(before);quiet(before[-1],selected=state['directory']+'/'+BUNDLES[state['resource']][0])
                elif state['phase']=='primary-retired':need(files['retiredPrimary'] and not files['releasing'] and not files['files'][0]['exists'] and all(row['exists'] for row in files['files'][1:]))
        return state

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and self.native.guard() is not False)
        if self.storage_version==VERSION:self.sources.prepare_migration(self.previous);self.storage_version=OWNER_VERSION
        state={key:deepcopy(self.state[key]) for key in ('phase','token','ticket','resource','directory')}
        state['inputManifest']=[dict(path=path,bytes=len(original_bytes(raw)),sha256=hashlib.sha256(original_bytes(raw)).hexdigest()) for path,raw in self.state['files'].items()]
        state['sources']=self.sources.manifest()
        value=dict(iosAssetsFileOwnerVersion=OWNER_VERSION,runId=self.run,fixtureUrl=self.url,binding=self.binding,role=self.role,payload=pack([state]))
        decoded=self.decode(value);need(same(decoded,self.state));self.store.write(value,self.previous);sync(self.store.path.parent);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def retain(self,query,packet):
        # Legacy callback API remains accepted only with an actual original
        # source string that reopens and decodes to precisely this packet.
        raw=self.native.original();need(type(raw) is str and same(decode(raw),packet));return self.retain_raw(query,packet,raw)

    def retain_raw(self,query,packet,raw):
        need(self.state is not None and len(self.state['originals'])<128 and self.sources.pending is None and same(decode(raw),packet))
        self.sources.capture(query,raw);return self.recover_capture()

    def recover_capture(self):
        reference,record=self.sources.completed_capture();packet=decode(record['raw']);previous=self.state['originals'][-1]['packet'] if self.state['originals'] else None
        validate(packet,record['query'],self.native.pid,previous=previous)
        self.sources.accept_capture();self.state['originals'].append(dict(query=deepcopy(record['query']),packet=packet));self.save();return packet

    @operation
    def reserve(self,ticket,resource='gltf-bundle/main.gltf'):
        self.lock.assert_held();need(self.state is None);identifier(ticket)
        self.state=dict(phase='reserved',token=secrets.token_hex(32),ticket=ticket,resource=resource,
            files=inputs(self.run,ticket,self.url,resource),directory=None,originals=[]);self.save()

    @operation
    def request(self,operation,**values):
        need(self.state is not None);state=self.state
        if self.storage_version==VERSION:self.save()
        need(self.sources.pending is None)
        return self.native.request(operation,self.run,state['ticket'],state['token'],state['resource'],retain_raw=self.retain_raw,**values)

    @operation
    def stage(self):
        need(self.state['phase']=='reserved');self.state['phase']='staging';self.save()
        self.request('stage',files=self.state['files']);return self.recover_stage()

    @operation
    def observe(self):return self.request('observe')

    @operation
    def recover_stage(self):
        need(self.state['phase'] in ('staging','staged'));value=self.observe();files=value['source']['files']
        need(files['exists'] and files['complete'] and not files['retiredPrimary'] and not files['releasing'] and all(row['exists'] for row in files['files']))
        self.state['directory']=files['directory'];self.state['phase']='staged';self.save();return local(files['directory'])

    @operation
    def retire_primary(self):
        need(self.state['phase']=='staged');value=self.observe();source=value['source'];files=source['files']
        need(files['exists'] and files['complete'] and not files['retiredPrimary'] and not files['releasing'])
        quiet(source,selected=files['directory']+'/'+BUNDLES[self.state['resource']][0])
        self.state['phase']='retiring-primary';self.save();self.request('retire-primary',originals=files['files']);return self.recover_primary()

    @operation
    def recover_primary(self):
        need(self.state['phase'] in ('retiring-primary','primary-retired'));value=self.observe();files=value['source']['files']
        need(files['exists'] and files['complete'] and files['retiredPrimary'] and not files['releasing']
            and not files['files'][0]['exists'] and all(row['exists'] for row in files['files'][1:]))
        self.state['phase']='primary-retired';self.save();return value

    @operation
    def release(self):
        need(self.state['phase'] in ('staged','primary-retired'));value=self.observe();files=value['source']['files'];need(files['exists'] and not files['releasing']);quiet(value['source'])
        self.state['phase']='releasing';self.save();self.request('release',originals=files['files']);return self.recover_release()

    @operation
    def recover_release(self):
        need(self.state['phase'] in ('releasing','retired'));value=self.observe();need(value['source']['files']=={'exists':False,'files':[]});quiet(value['source'])
        self.state['phase']='retired';self.save();return value
