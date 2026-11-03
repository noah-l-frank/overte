"""Bounded warm Actor source consolidation with exact staged-file transfers.

Staging originals precede the next source request. Only a verified immutable
copy and durable retirement intent allow their original files to be removed.
These storage operations never acquire native facts or input authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
import hashlib
import json
import os
import stat

from adapters.chat_journey import source_bundles
from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest,json_digest
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need,exact,integer
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical,pack,unpack,MAX_FRAMES,MAX_RAW

VERSION=2
STAGING_VERSION=2
STAGING_READS=(1,2)
STAGE='lifecycle-actor-in-progress.json'


def sticky(method):
    @wraps(method)
    def invoke(self,*args,**kwargs):
        need(not self.failed)
        try:return method(self,*args,**kwargs)
        except BaseException:
            self.failed=True
            if self.stage is not None:self.stage.failed=True
            raise
    return invoke


def part_cost(history,parts):
    """Exact future wrapper bytes; pack() is the unchanged chunk encoder."""
    raw=stored=0
    for offset,part in enumerate(parts):
        index=len(history.identities)+offset;transcript=pack([deepcopy(part)])
        raw+=transcript['bytes']-2+(1 if index else 0)
        value=dict(chatSampleChunkVersion=1,scopeSha256=history.scope,index=index,transcript=transcript)
        stored+=len(canonical(value))+1
    return raw,stored


def staging_names(path):
    return {entry.name for entry in path.parent.iterdir() if entry.name==STAGE
        or entry.name.startswith((STAGE+'.frame-',STAGE+'.pending-',path.name+'.pending-'))}


def snapshot_file(name,raw,stamp):
    return dict(name=name,raw=raw.decode('utf-8'),sha256=hashlib.sha256(raw).hexdigest(),stamp=list(stamp))


def checked_file(value):
    exact(value,{'name','raw','sha256','stamp'})
    need(type(value['name']) is str and '/' not in value['name'] and type(value['raw']) is str
        and type(value['stamp']) is list and len(value['stamp'])==8
        and all(type(field) is int for field in value['stamp']))
    raw=value['raw'].encode('utf-8')
    need(0<len(raw)<=65536 and len(raw)==value['stamp'][5]
        and hashlib.sha256(raw).hexdigest()==value['sha256'])
    decoded=json.loads(raw);need(type(decoded) is dict and canonical(decoded)+b'\n'==raw)
    return decoded


def nested_bytes(root):
    version=root['actorStagingVersion']
    need(type(version) is int and version in STAGING_READS)
    if version==1:
        need('nestedDecodedBytes' not in root);return 0
    need('nestedDecodedBytes' in root and integer(root['nestedDecodedBytes'],0,MAX_RAW))
    return root['nestedDecodedBytes']


def decode_snapshot(snapshot):
    """Decode copied historical originals; this grants no live ownership."""
    exact(snapshot,{'actorStagingSnapshotVersion','root','files'})
    need(type(snapshot['actorStagingSnapshotVersion']) is int and snapshot['actorStagingSnapshotVersion']==1)
    root=checked_file(snapshot['root']);need(type(snapshot['files']) is list)
    need(snapshot['root']['name']==STAGE and root['phase']=='reading' and root['state']=='collecting'
        and len(root['chunks'])==len(snapshot['files'])<=MAX_FRAMES)
    scope={key:root[key] for key in ('actorStagingVersion','sourceScopeSha256','record')}
    nested=nested_bytes(root)
    parts=[]
    for index,original in enumerate(snapshot['files']):
        need(original['name']==STAGE+f'.frame-{index:03d}.json')
        value=checked_file(original);exact(value,{'chatSampleChunkVersion','scopeSha256','index','transcript'})
        need(value['chatSampleChunkVersion']==1 and type(value['chatSampleChunkVersion']) is int
            and value['scopeSha256']==digest(scope) and type(value['index']) is int and value['index']==index
            and digest(value)==root['chunks'][index])
        data=unpack(value['transcript']);need(len(data)==1);parts.append(data[0])
    need(source_bundles.logical_bytes(root['bundles'])+nested<=MAX_RAW
        and len(root['entries'])==len(root['bundles']))
    entries=[];offset=0
    for index,(entry,reference) in enumerate(zip(root['entries'],root['bundles'])):
        exact(entry,{'key','bundle'});need(type(entry['key']) is str and integer(entry['bundle']) and entry['bundle']==index)
        value,_raw=source_bundles.decode_parts(parts[offset:offset+reference['parts']],reference,index)
        entries.append(dict(key=entry['key'],value=value));offset+=reference['parts']
    need(offset==len(parts));return root,entries


class ActorStagingParts:
    def __init__(self,main):
        self.main,self.lock=main,main.lock;self.store=PrivateFeatureState(main.store.path.with_name(STAGE))
        need(self.store.read() is None and not staging_names(main.store.path))
        self.scope=dict(actorStagingVersion=STAGING_VERSION,sourceScopeSha256=main.scope_sha,record=len(main.disk['records']))
        self.physical=LifecycleProcessFile(self.store);self.history=ChatSourceChunks(self.store,self.scope)
        self.disk=None;self.owners=[];self.files=[];self.failed=False
        self.save(dict(self.scope,phase='reading',state='collecting',chunks=[],bundles=[],entries=[],transfer=None,
            retired=[],unlink=None,nestedDecodedBytes=0))

    def identity(self):
        need(not self.failed);self.main.identity();self.physical.guard()
        need(self.store.read()==self.disk and all(self.disk[key]==value for key,value in self.scope.items()))

    def remaining(self):
        return set(range(len(self.files)))-set(self.disk['retired'])

    def file(self,index):
        owner=self.owners[index];owner.require(owner.fd);path=self.history._path(index)
        info=os.fstat(owner.fd);raw=os.pread(owner.fd,65537,0);owner.require(owner.fd)
        need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
            and info.st_nlink==1 and signature(info)==signature(path.lstat())==self.files[index]['stamp']
            and raw==self.files[index]['raw'].encode('utf-8'))
        return raw,signature(info)

    def verify(self):
        self.identity()
        expected={self.history.names[index] for index in self.remaining()}
        actual={p.name for p in self.store.path.parent.iterdir() if p.name.startswith(STAGE+'.frame-')}
        need(actual==expected)
        need(staging_names(self.main.store.path)=={STAGE,*expected})
        for index in self.remaining():self.file(index)

    def save(self,value):
        self.lock.assert_held();self.main.identity();self.physical.guard()
        self.physical.write(value,self.disk);self.disk=deepcopy(value);self.physical.guard()

    def append(self,key,value):
        self.verify();need(self.disk['state']=='collecting' and type(key) is str)
        reference,parts=source_bundles.prepare(value,len(self.disk['bundles']),self.disk['bundles'])
        raw,stored=part_cost(self.history,parts)
        self.main.capacity(extra_parts=len(parts),extra_logical=reference['bytes'],extra_container=raw,extra_stored=stored)
        for part in parts:
            manifest=self.history.append(part,self.disk['chunks']);index=len(manifest)-1
            path=self.history._path(index)
            owner=OriginalDescriptor(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            self.owners.append(owner)
            owner.require(owner.fd);info=os.fstat(owner.fd);raw=os.pread(owner.fd,65537,0)
            need(self.history.signature(index)==self.history.identities[index]
                and signature(info)==signature(path.lstat())
                and raw==canonical(self.history.store(index).read())+b'\n')
            self.files.append(snapshot_file(path.name,raw,signature(info)))
            updated=deepcopy(self.disk);updated['chunks']=manifest;self.save(updated)
        updated=deepcopy(self.disk);updated['bundles'].append(reference)
        updated['entries'].append(dict(key=key,bundle=len(updated['entries'])));self.save(updated);self.verify();self.main.capacity()

    def snapshot(self):
        self.verify();need(self.disk['state']=='collecting')
        raw,stamp=self.physical.read(self.physical.file,self.store.path)
        result=dict(actorStagingSnapshotVersion=1,root=snapshot_file(STAGE,raw,stamp),files=deepcopy(self.files))
        decoded,entries=decode_snapshot(result);need(decoded==self.disk)
        return result,entries

    def copied(self,index,snapshot):
        self.verify();need(self.disk['state']=='collecting')
        original,_raw=self.main.original(index)
        need(original['staging']==snapshot and decode_snapshot(original['staging'])[0]==self.disk)
        updated=deepcopy(self.disk);updated.update(state='copy-verified',transfer=dict(bundle=index,
            snapshotSha256=json_digest(snapshot),destinationSha256=self.main.disk['bundles'][index]['sha256'],
            destinationParts=[list(stamp) for stamp in self.main.history.identities[
                sum(ref['parts'] for ref in self.main.disk['bundles'][:index]):]]))
        self.save(updated)

    def destination(self):
        self.verify();transfer=self.disk['transfer'];need(transfer is not None)
        # verify() above has just checked the complete same main identity.
        # original() keeps its unchanged full immutable-part verification;
        # repeating its warm ownership traversal adds no observation.
        value,_raw=source_bundles.original(self.main.history,self.main.disk['chunks'],
            self.main.disk['bundles'],transfer['bundle'])
        start=sum(ref['parts'] for ref in self.main.disk['bundles'][:transfer['bundle']])
        end=start+self.main.disk['bundles'][transfer['bundle']]['parts']
        need(json_digest(value['staging'])==transfer['snapshotSha256']
            and self.main.disk['bundles'][transfer['bundle']]['sha256']==transfer['destinationSha256']
            and [list(stamp) for stamp in self.main.history.identities[start:end]]==transfer['destinationParts'])
        return value

    def retire_parts(self):
        self.verify();need(self.disk['state']=='copy-verified' and self.disk['unlink'] is None)
        for index in range(len(self.files)):
            self.destination();self.main.fresh()
            original=self.files[index]
            updated=deepcopy(self.disk);updated['unlink']=dict(index=index,phase='issued',
                sha256=original['sha256'],stamp=original['stamp'])
            self.save(updated)
            self.destination();self.main.fresh();self.file(index)
            require_directory(self.physical.parent,self.store.path.parent)
            os.unlink(self.history.names[index],dir_fd=self.physical.parent.fd);os.fsync(self.physical.parent.fd)
            owner=self.owners[index];owner.require(owner.fd);need(os.fstat(owner.fd).st_nlink==0)
            need(owner.close())
            try:self.history._path(index).lstat()
            except FileNotFoundError:pass
            else:need(False)
            updated=deepcopy(self.disk);updated['retired'].append(index)
            updated.setdefault('retirementReceipts',[]).append(dict(index=index,phase='observed',
                sha256=original['sha256'],stamp=original['stamp'],removed=True,originalFileDescriptionClosed=True))
            updated['unlink']=None;self.save(updated);self.main.fresh()
        updated=deepcopy(self.disk);updated['state']='parts-retired';self.save(updated);self.verify()

    def final_snapshot(self):
        self.verify();need(self.disk['state']=='parts-retired' and not self.remaining())
        raw,stamp=self.physical.read(self.physical.file,self.store.path)
        return snapshot_file(STAGE,raw,stamp)

    def retire_manifest(self,reference):
        self.verify();before=self.final_snapshot();copied,_raw=self.main.original(reference)
        need(copied['stagingTransfer']==before)
        pending=deepcopy(self.main.disk['pending']);pending['manifestRemoval']=dict(phase='issued',
            originalSha256=before['sha256'],originalStamp=before['stamp'],bundle=reference)
        self.main.update(pending=pending)
        self.verify();self.main.fresh();again=self.final_snapshot();need(again==before)
        require_directory(self.physical.parent,self.store.path.parent)
        os.unlink(STAGE,dir_fd=self.physical.parent.fd);os.fsync(self.physical.parent.fd)
        owner=self.physical.file;owner.require(owner.fd);need(os.fstat(owner.fd).st_nlink==0 and owner.close())
        need(self.physical.parent.close());self.physical.file=self.physical._file=None
        self.failed=True # This actual stage can never be used again.
        need(not staging_names(self.main.store.path))
        return dict(originalSha256=before['sha256'],originalStamp=before['stamp'],bundle=reference,
            removed=True,originalFileDescriptionClosed=True,
            originalDirectoryDescriptionClosed=True)


class LifecycleActorStorage:
    def __init__(self,store,scope,lock,guard,fresh):
        need(type(store) is PrivateFeatureState and type(scope['picoLifecycleActorSourceVersion']) is int
            and scope['picoLifecycleActorSourceVersion']==VERSION
            and callable(guard) and callable(fresh))
        self.store,self.scope,self.lock,self.guard,self.fresh=store,deepcopy(scope),lock,guard,fresh
        self.scope_sha=json_digest(scope);self.history=ChatSourceChunks(store,scope)
        self.disk=None;self.stage=None;self.failed=False;self.highwater={}
        lock.assert_held();need(store.read() is None and not staging_names(store.path));self.history.inventory(0)
        self.physical=LifecycleProcessFile(store)
        self.write_root=self.physical.write
        self.save(dict(self.scope,phase='reading',chunks=[],bundles=[],records=[],pending=None,publication=None,decodedSourceBytes=0))

    @sticky
    def identity(self):
        need(not self.failed and self.guard() is not False
            and json_digest(self.scope)==self.scope_sha==self.history.scope)
        self.physical.guard();need(self.store.read()==self.disk);self.history.verify()

    @sticky
    def verify(self):
        if self.stage is not None:
            # Stage verification starts with the same full main identity.
            self.stage.verify()
        else:self.identity();need(not staging_names(self.store.path))

    def save(self,value):
        self.lock.assert_held();self.identity();self.write_root(value,self.disk);self.disk=deepcopy(value);self.physical.guard()

    def update(self,**changes):
        value=deepcopy(self.disk);value.update(deepcopy(changes));self.save(value)

    def capacity(self,*,extra_parts=0,extra_logical=0,extra_container=0,extra_stored=0):
        count=len(self.history.identities);raw=self.history.raw_bytes
        logical=source_bundles.logical_bytes(self.disk['bundles'])+self.disk['decodedSourceBytes']
        # Current roots and one in-flight atomic root publication each retain
        # their unchanged64KiB ceiling. The reserve never omits metadata bytes.
        stored=3*65536+sum(self.history._path(i).stat().st_size for i in range(count))
        if self.stage is not None:
            count+=len(self.stage.remaining());raw+=self.stage.history.raw_bytes
            logical+=source_bundles.logical_bytes(self.stage.disk['bundles'])+nested_bytes(self.stage.disk)
            stored+=sum(len(self.stage.files[i]['raw'].encode('utf-8')) for i in self.stage.remaining())
        need(count+extra_parts<=MAX_FRAMES and raw+extra_container<=MAX_RAW
            and logical+extra_logical<=MAX_RAW and stored+extra_stored<=MAX_RAW)
        paths=[self.store.path,*[self.history._path(i) for i in range(len(self.history.identities))]]
        if self.stage is not None:
            paths.extend([self.stage.store.path,*[self.stage.history._path(i) for i in self.stage.remaining()]])
        sizes=[path.stat().st_size for path in paths]
        actual=dict(parts=count,containerRawBytes=raw,decodedLogicalBytes=logical,storedBytes=sum(sizes),
            files=len(paths),largestFileBytes=max(sizes),reservedStoredBytes=stored)
        for key,value in actual.items():self.highwater[key]=max(self.highwater.get(key,0),value)

    def original(self,index):
        self.identity();return source_bundles.original(self.history,self.disk['chunks'],self.disk['bundles'],index)

    @sticky
    def archive(self,value,*,decoded_extra=0):
        self.identity();reference,parts=source_bundles.prepare(value,len(self.disk['bundles']),self.disk['bundles'])
        raw,stored=part_cost(self.history,parts)
        self.capacity(extra_parts=len(parts),extra_logical=reference['bytes']+decoded_extra,extra_container=raw,extra_stored=stored)
        for part in parts:
            manifest=self.history.append(part,self.disk['chunks']);self.update(chunks=manifest)
        index=len(self.disk['bundles']);self.update(bundles=[*self.disk['bundles'],reference],
            decodedSourceBytes=self.disk['decodedSourceBytes']+decoded_extra);self.capacity();return index

    @sticky
    def begin(self):
        self.verify();need(self.disk['pending'] is None and len(self.disk['records'])<128
            and (self.disk['publication'] is None or self.disk['publication']['phase']=='delivered'))
        self.update(pending=dict(record=len(self.disk['records']),native=None,manifestRemoval=None))
        self.stage=ActorStagingParts(self)

    @sticky
    def retain(self,key,value):
        self.verify();need(self.stage is not None);self.stage.append(key,value)

    @sticky
    def reserve(self,canonical_limit):
        """Reserve the bounded next literal before its original query.

        The zlib compressBound expression covers the unchanged default zlib
        encoder; JSON wrapper overhead has an additional per-part reserve.
        No response can consume another query's unreserved staging capacity.
        """
        need(integer(canonical_limit,1,MAX_RAW))
        compressed=canonical_limit+(canonical_limit>>12)+(canonical_limit>>14)+(canonical_limit>>25)+13
        encoded=4*((compressed+2)//3)
        parts=(encoded+source_bundles.PART_BYTES-1)//source_bundles.PART_BYTES
        self.capacity(extra_parts=parts,extra_logical=canonical_limit,
            extra_container=encoded+parts*1024,extra_stored=encoded+parts*2048)

    @sticky
    def reserve_nested(self,count):
        self.verify();need(self.stage is not None and self.stage.disk['state']=='collecting'
            and self.stage.disk['actorStagingVersion']==STAGING_VERSION and integer(count,0,MAX_RAW))
        self.capacity(extra_logical=count)
        value=deepcopy(self.stage.disk);value['nestedDecodedBytes']=nested_bytes(value)+count
        need(value['nestedDecodedBytes']<=MAX_RAW);self.stage.save(value);self.capacity()

    @sticky
    def native_record(self,record):
        self.verify();snapshot,_entries=self.stage.snapshot()
        value=dict(lifecycleActorSourceGroupVersion=VERSION,staging=snapshot,record=deepcopy(record))
        decoded_extra=(source_bundles.logical_bytes(self.stage.disk['bundles'])-2
            +self.stage.history.raw_bytes-2+nested_bytes(self.stage.disk))
        index=self.archive(value,decoded_extra=decoded_extra);original,raw=self.original(index)
        need(raw==canonical(value) and original==value)
        pending=deepcopy(self.disk['pending']);pending['native']=index;self.update(pending=pending)
        self.stage.copied(index,snapshot);self.stage.retire_parts()
        self.update(records=[*self.disk['records'],dict(native=index,phase=None,reply=None)])
        return index

    def latest(self):
        self.verify();need(self.disk['records'])
        group,_raw=self.original(self.disk['records'][-1]['native']);return deepcopy(group['record'])

    @sticky
    def issue_publication(self,value):
        self.verify();record=len(self.disk['records'])-1;need(self.disk['pending'] is not None
            and self.latest()['publication']==value and (self.disk['publication'] is None
                or self.disk['publication']['phase']=='delivered' and self.disk['publication']['record']<record))
        self.update(publication=dict(phase='issued',record=record,valueSha256=json_digest(value),fixture=None,reply=None))

    @sticky
    def publication_phase(self,phase):
        self.verify();need(self.disk['publication']['phase']=='issued' and self.disk['publication']['fixture'] is None)
        final=self.stage.final_snapshot();reference=self.archive(dict(lifecycleActorPublicationVersion=1,
            phase=deepcopy(phase),stagingTransfer=final))
        records=deepcopy(self.disk['records']);records[-1]['phase']=reference
        publication=deepcopy(self.disk['publication']);publication['fixture']=reference
        self.update(records=records,publication=publication);return reference

    @sticky
    def retire_stage(self):
        self.verify();reference=self.disk['publication']['fixture'];need(reference is not None)
        result=self.stage.retire_manifest(reference);self.stage=None
        pending=deepcopy(self.disk['pending']);pending['manifestRemoval']=dict(phase='observed',receipt=result)
        self.update(pending=pending);self.fresh()

    @sticky
    def retain_reply(self,reply):
        self.verify();need(self.stage is None and self.disk['publication']['phase']=='issued'
            and self.disk['pending']['manifestRemoval']['phase']=='observed'
            and self.disk['publication']['reply'] is None)
        index=self.archive(dict(transportReply=deepcopy(reply),stagingRetirement=deepcopy(self.disk['pending']['manifestRemoval'])))
        records=deepcopy(self.disk['records']);records[-1]['reply']=index
        publication=deepcopy(self.disk['publication']);publication['reply']=index
        self.update(records=records,publication=publication)

    @sticky
    def delivered(self,reply):
        self.verify();need(self.stage is None and self.disk['publication']['phase']=='issued')
        if self.disk['publication']['reply'] is None:self.retain_reply(reply)
        value,_raw=self.original(self.disk['publication']['reply']);need(value['transportReply']==reply)
        publication=deepcopy(self.disk['publication']);publication['phase']='delivered'
        self.update(publication=publication,pending=None);self.fresh()

    def close_host(self):
        result=[]
        if self.stage is not None:
            result.extend(owner.close() for owner in self.stage.owners)
            result.append(self.stage.physical.close_host())
        result.append(self.physical.close_host());return all(result)
