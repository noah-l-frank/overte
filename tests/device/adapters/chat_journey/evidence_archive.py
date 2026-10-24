"""Immutable original journal archival before explicitly admitted retirement.

Only a warm complete parent may admit sources. Unknown paths/orphans, replaced
open-file descriptions and uncertain retirement receipts remain retained.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
import stat

from adapters.native_fd_owner import OriginalDescriptor
from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import same,pack,canonical
from adapters.chat_journey.source_chunks import digest

VERSION=4
WINDOW_VERSION=3
CLOSED_VERSION=2
LEGACY_VERSION=1
FILE_OWNERSHIP='closed-immutable-originals'
UNLINK_POLICY='original-source-16-unlinks-250ms'
COPY_POLICY='full-current-copy-and-original-physical-inventory'
LIMIT_FILES=4096
LIMIT_BYTES=64*1024*1024


def stamp(info):
    return [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns]


def private(info,mode=0o600):
    need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==mode
        and info.st_nlink==1 and 0<info.st_size<=65536)


def original_json(raw,expected):
    """Validate the bytes inside the existing owned full-file read window.

    Reopening the same path for JSON validation duplicates the physical read.
    Keep PrivateFeatureState's UTF-8, dictionary and unique-key grammar while
    parsing the exact bytes whose descriptor and complete stamp are checked.
    """
    def pairs(items):
        value={}
        for key,item in items:
            need(key not in value);value[key]=item
        return value
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
    except (ValueError,UnicodeError):
        raise NativeUIError('Normal feature ownership file is invalid') from None
    need(type(value) is dict and same(value,expected))


class ChatArchiveCatalog:
    """Explicit already-consumed originals only; no directory discovery/adoption."""
    def __init__(self,*,hold_files=True):
        need(type(hold_files) is bool)
        self.rows={};self.parents={};self.failed=False;self.hold_files=hold_files;self.uncertain=[]

    def add(self,label,store,expected):
        need(not self.failed and isinstance(store,PrivateFeatureState) and expected is not None
            and type(label) is str and label.startswith(('primary/','peer/')) and label.count('/')==1
            and label.rsplit('/',1)[-1] not in ('','.','..') and '\\' not in label)
        if label in self.rows:
            row=self.rows[label];need(row['store'].path==store.path and same(row['expected'],expected));self.verify(row);return
        need(len(self.rows)<LIMIT_FILES and all(row['store'].path!=store.path for row in self.rows.values()))
        owner=None
        try:
            store._parent()
            if store.path.parent not in self.parents:
                self.parents[store.path.parent]=OriginalDescriptor(store.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.verify_parent(store.path.parent)
            if self.hold_files:
                owner=OriginalDescriptor(store.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
                info=os.fstat(owner.fd);private(info);raw=os.pread(owner.fd,65537,0)
                need(len(raw)==info.st_size and same(store.read(),expected) and stamp(store.path.lstat())==stamp(os.fstat(owner.fd))==stamp(info))
                original_stamp=stamp(info)
            else:
                owner=ClosedOriginalFile(store.path,0o600,lambda:self.verify_parent(store.path.parent))
                def validate(raw):
                    need(owner.path==store.path);original_json(raw,expected);need(owner.path==store.path)
                raw,original_stamp=owner.read(validate)
                need(owner.path==store.path)
            row=dict(label=label,store=store,expected=deepcopy(expected),owner=owner,stamp=original_stamp,raw=raw,sha256=hashlib.sha256(raw).hexdigest())
            self.rows[label]=row;self.verify(row)
            need(sum(len(value['raw']) for value in self.rows.values())<=LIMIT_BYTES)
        except BaseException:
            self.failed=True
            if owner is not None and not owner.close():self.uncertain.append(owner)
            raise

    def verify_parent(self,path):
        owner=self.parents[path];owner.require(owner.fd);info=path.lstat();held=os.fstat(owner.fd)
        need(path.resolve(strict=True)==path and stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode)==0o700
            and info.st_uid==os.geteuid() and (info.st_dev,info.st_ino)==(held.st_dev,held.st_ino)==owner.node)

    def verify(self,row):
        self.verify_parent(row['store'].path.parent)
        owner=row['owner']
        if type(owner) is ClosedOriginalFile:
            need(owner.path==row['store'].path)
            def validate(raw):
                need(owner.path==row['store'].path);original_json(raw,row['expected']);need(owner.path==row['store'].path)
            raw,original_stamp=owner.read(validate)
            need(owner.path==row['store'].path and raw==row['raw'] and original_stamp==row['stamp']);return
        owner.require(owner.fd);info=os.fstat(owner.fd);private(info)
        need(stamp(info)==row['stamp']==stamp(row['store'].path.lstat()) and os.pread(owner.fd,65537,0)==row['raw']
            and same(row['store'].read(),row['expected']))
        owner.require(owner.fd);need(stamp(os.fstat(owner.fd))==row['stamp'])

    def verify_all(self):
        need(not self.failed and self.rows)
        for row in self.rows.values():self.verify(row)

    def close_host(self):
        return all([row['owner'].close() for row in self.rows.values()]+[owner.close() for owner in self.parents.values()]+[owner.close() for owner in self.uncertain])


class ChatEvidenceArchive:
    """Write-once original copies, durable unlink admission and final sources.

    No active/unknown journal is admitted here. The enclosing typed parent must
    validate consumption, original old-PID ESRCH, new sources and actual release
    before making its explicit catalog. A failed warm attempt cannot be retried
    or reconstructed by selecting files from disk.
    """
    def __init__(self,catalog,directory,store,metadata,guard,inventory,*,unlink_fence=None,indexed_verify=False):
        need(type(catalog) is ChatArchiveCatalog and isinstance(store,PrivateFeatureState)
            and directory.parent==store.path.parent and directory.is_absolute()
            and directory.resolve()==directory and not directory.exists() and store.read() is None
            and type(metadata) is dict and callable(guard) and callable(inventory))
        self.catalog,self.directory,self.store,self.metadata=catalog,directory,store,deepcopy(metadata)
        need(unlink_fence is None or not catalog.hold_files and unlink_fence.guard is guard
            and all(callable(getattr(unlink_fence,name,None)) for name in ('prepare','check','complete')))
        need(type(indexed_verify) is bool and (not indexed_verify or unlink_fence is not None))
        self.unlink_fence=unlink_fence;self.indexed_verify=indexed_verify
        self.version=VERSION if indexed_verify else WINDOW_VERSION if unlink_fence is not None else LEGACY_VERSION if catalog.hold_files else CLOSED_VERSION
        need(directory.parent in catalog.parents);self.parent_owner=catalog.parents[directory.parent]
        self.guard,self.inventory=guard,inventory;self.previous=None;self.started=False;self.archived={};self.deleted=[]
        self.root=None;self.manifest=None;self.receipt=None;self.complete=False
        self.admitted={};self.cache_digest='';self.labels=tuple(catalog.rows)
        self.index_rows=self._sealed_index_rows=()
        self.positions={label:index for index,label in enumerate(self.labels)}
        catalog.verify_all();inventory(set(row['store'].path for row in catalog.rows.values()))

    def write(self,phase,**changes):
        need(same(self.store.read(),self.previous))
        value={**(self.previous or dict(chatArchiveRetirementVersion=self.version,metadataSha256=digest(self.metadata),deleted=[])),
            **deepcopy(changes),'phase':phase}
        self.catalog.verify_parent(self.store.path.parent);self.store.write(value,self.previous);os.fsync(self.parent_owner.fd)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def original(self,name,raw):
        path=self.directory/name;need(not path.exists())
        self.root.require(self.root.fd)
        descriptor=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root.fd)
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o400);os.fsync(stream.fileno())
        owner=None
        try:
            if self.version==LEGACY_VERSION:
                owner=OriginalDescriptor(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
                info=os.fstat(owner.fd);private(info,0o400);original_stamp=stamp(info)
            else:
                owner=ClosedOriginalFile(path,0o400,self.verify_root);actual,original_stamp=owner.read();need(actual==raw)
            row=dict(owner=owner,path=path,stamp=original_stamp,raw=raw,sha256=hashlib.sha256(raw).hexdigest())
            self.archived[name]=row
            if self.indexed_verify:
                snapshot=(name,tuple(original_stamp),row['sha256'],len(raw))
                # Immutable bytes plus an independently pinned digest chain;
                # caller mutations cannot update this original admission.
                self.admitted[name]=(snapshot,raw,owner,owner.raw)
                # The exact original tuple and its immutable canonical bytes
                # are pinned together. Reuse serialization, never a physical
                # stamp, current-copy read, or an observed source verdict.
                entry=(self.admitted[name],path,canonical(snapshot))
                self.index_rows=self._sealed_index_rows=self.index_rows+((name,entry),)
                self.cache_digest=digest((self.cache_digest,snapshot))
                self.verify_root()
            else:self.verify_archive()
            return row
        except BaseException:
            if owner is not None and not owner.close():self.catalog.uncertain.append(owner)
            raise

    def verify_root(self):
        need(self.root is not None)
        self.catalog.verify_parent(self.directory.parent);self.root.require(self.root.fd)
        info=self.directory.lstat();held=os.fstat(self.root.fd)
        need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode) in (0o700,0o500)
            and (info.st_dev,info.st_ino)==(held.st_dev,held.st_ino)==self.root.node)

    def verify_archive(self):
        if self.root is None:return
        self.verify_root()
        need({path.name for path in self.directory.iterdir()}==set(self.archived))
        if self.indexed_verify:self.verify_index()
        for row in self.archived.values():self.verify_archived(row)

    def verify_archived(self,row):
        if type(row['owner']) is ClosedOriginalFile:
            raw,original_stamp=row['owner'].read();need(raw==row['raw'] and original_stamp==row['stamp']);return
        row['owner'].require(row['owner'].fd);info=os.fstat(row['owner'].fd);private(info,0o400)
        need(stamp(info)==row['stamp']==stamp(row['path'].lstat()) and os.pread(row['owner'].fd,65537,0)==row['raw'])

    def verify_index(self):
        """Original physical inventory, NOT a new observation of cached bytes.

        Every copy was fully read through its real owned FD window. Between
        complete passes, all original physical stamps are checked via the held
        directory; the current copy/manifest gets another FULL byte window.
        Immutable byte objects and a pinned digest chain guard the cache too.
        """
        need(self.indexed_verify and tuple(self.catalog.rows)==self.labels
            and self.index_rows is self._sealed_index_rows and type(self.index_rows) is tuple
            and len(self.index_rows)==len(self.archived))
        self.verify_root()
        # Enumeration can leave the owned directory OFD at end-of-directory;
        # reset only this still kernel-verified original before every pass.
        os.lseek(self.root.fd,0,os.SEEK_SET)
        need(set(os.listdir(self.root.fd))==set(self.archived)==set(self.admitted))
        chain=''
        for (name,row),(original_name,entry) in zip(self.archived.items(),self.index_rows):
            admitted,path,encoded=entry
            need(name==original_name and self.admitted[name] is admitted)
            snapshot,raw,owner,owner_raw=admitted
            current=(name,tuple(row['stamp']),row['sha256'],len(row['raw']))
            need(current==snapshot and type(raw) is bytes and row['raw'] is raw and row['owner'] is owner
                and type(owner) is ClosedOriginalFile and owner.path is row['path'] is path
                and type(owner_raw) is bytes and owner.raw is owner_raw and owner.stamp==row['stamp'] and not owner.failed and owner.active is None)
            # This is exactly canonical((chain, snapshot)): the chain is
            # empty or lowercase SHA256 hex, and encoded is the pinned original
            # canonical snapshot. Keep the original chain value/verification.
            chain=hashlib.sha256(b'["'+chain.encode('ascii')+b'",'+encoded+b']').hexdigest()
            info=os.stat(name,dir_fd=self.root.fd,follow_symlinks=False);private(info,0o400)
            need(stamp(info)==row['stamp'])
        need(chain==self.cache_digest);self.verify_root()

    def verify_current(self,label):
        self.verify_index();index=self.positions[label]
        need(type(index) is int and 0<=index<len(self.labels) and self.labels[index]==label)
        for name in (f'original-{index:04d}.json',f'manifest-{index//64:03d}.json','manifest.json'):
            self.verify_archived(self.archived[name])
        self.verify_index()

    def retire(self):
        need(not self.started);self.started=True
        self.catalog.verify_all();self.inventory(set(row['store'].path for row in self.catalog.rows.values()));self.guard()
        self.write('archiving');self.catalog.verify_parent(self.directory.parent)
        os.mkdir(self.directory.name,mode=0o700,dir_fd=self.parent_owner.fd);os.fsync(self.parent_owner.fd)
        self.root=OriginalDescriptor(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        items=[]
        for index,row in enumerate(self.catalog.rows.values()):
            self.catalog.verify(row);name=f'original-{index:04d}.json'
            archived=self.original(name,row['raw']);self.catalog.verify(row)
            items.append(dict(label=row['label'],file=name,bytes=len(row['raw']),sha256=row['sha256'],sourceStamp=row['stamp'],archiveStamp=archived['stamp']))
        # Manifest chunks keep the existing per-file size bound. Neither a
        # packed source nor its original bytes are truncated to fit a root.
        manifest=dict(chatEvidenceArchiveVersion=self.version,metadata=self.metadata,parts=[])
        if self.version>=CLOSED_VERSION:manifest['fileOwnership']=FILE_OWNERSHIP
        if self.version>=WINDOW_VERSION:manifest['unlinkPolicy']=UNLINK_POLICY
        if self.version==VERSION:manifest['copyVerification']=COPY_POLICY
        for index in range(0,len(items),64):
            name=f'manifest-{index//64:03d}.json';raw=(json.dumps(items[index:index+64],sort_keys=True,separators=(',',':'))+'\n').encode()
            need(len(raw)<=65536);item=self.original(name,raw);manifest['parts'].append(dict(file=name,sha256=item['sha256']))
        raw=(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n').encode();need(len(raw)<=65536)
        self.manifest=self.original('manifest.json',raw);os.fsync(self.root.fd)
        self.write('archived',archiveSha256=self.manifest['sha256']);self.catalog.verify_all();self.verify_archive();self.guard()
        for row in self.catalog.rows.values():
            self.catalog.verify(row)
            if not self.indexed_verify:self.verify_archive()
            self.inventory({value['store'].path for key,value in self.catalog.rows.items() if key not in self.deleted})
            # The actual source/phase guard follows the final host intent.
            token=self.unlink_fence.prepare() if self.unlink_fence is not None else None
            self.write('unlink-issued',unlink=row['label'],**({'unlinkFence':token} if token is not None else {}))
            if token is None:self.guard();self.catalog.verify(row)
            else:
                self.catalog.verify(row)
                def check():
                    # A special retirement can contain its own final CAS.
                    # Repeat copy/manifest/inventory at that exact callback.
                    if self.indexed_verify:self.verify_current(row['label'])
                    self.unlink_fence.check(token)
                check()
            if 'retire' in row:
                need(callable(row['retire']))
                if token is not None:row['retire'](check)
                else:row['retire']()
                need(row['store'].read() is None)
            else:
                parent=self.catalog.parents[row['store'].path.parent];parent.require(parent.fd)
                os.unlink(row['store'].path.name,dir_fd=parent.fd)
            os.fsync(self.catalog.parents[row['store'].path.parent].fd)
            self.deleted.append(row['label']);need(not row['store'].path.exists())
            if token is not None:self.unlink_fence.complete(token)
            self.write('retiring',deleted=list(range(len(self.deleted))),unlink=None,**({'unlinkFence':None} if token is not None else {}))
        self.inventory(set());self.verify_archive();proof=self.guard()
        receipt=dict(chatEvidenceArchiveFinalVersion=self.version,archiveSha256=self.manifest['sha256'],
            metadataSha256=digest(self.metadata),retiredCount=len(self.catalog.rows),
            retiredSha256=digest(list(self.catalog.rows)),original=pack([proof]))
        raw=(json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n').encode();need(len(raw)<=65536)
        self.receipt=self.original('final.json',raw);os.fsync(self.root.fd)
        self.write('complete',finalSha256=self.receipt['sha256'])
        if self.indexed_verify:self.verify_index()
        else:self.verify_archive()
        # The caller's guard checks its original packet age after the final
        # receipt/CAS; it must not replace the stored proof with a later query.
        result=dict(chatEvidenceArchiveVersion=self.version,archiveSha256=self.manifest['sha256'],finalSha256=self.receipt['sha256'])
        self.guard(proof)
        try:
            self.store.discard(self.previous);os.fsync(self.parent_owner.fd)
            os.chmod(self.directory,0o500);os.fsync(self.root.fd)
            if self.indexed_verify:self.verify_index()
            else:self.verify_archive()
            self.guard(proof)
        except BaseException:
            # No action is replayed and no landed/foreign root is overwritten.
            # If our final marker unlink landed, retain a NEW explicit failure
            # marker by CAS-from-absence, preserving the original completed
            # archive/receipt hashes. This never adopts a target or journal.
            if self.store.read() is None:
                failed={**self.previous,'phase':'final-unavailable'}
                self.store.write(failed,None);os.fsync(self.parent_owner.fd);self.previous=deepcopy(failed)
            raise
        self.complete=True;return result

    def close_host(self):
        okay=self.catalog.close_host()
        for row in self.archived.values():okay=row['owner'].close() and okay
        if self.root is not None:okay=self.root.close() and okay
        return okay


def completed_archive(directory):
    """Verify only sealed archived bytes; never a current target/release claim."""
    from adapters.native_feature_observation import decode,exact,integer
    from adapters.script_journey.history import unpack
    info=directory.lstat();need(directory.resolve(strict=True)==directory and stat.S_ISDIR(info.st_mode)
        and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o500)
    root=OriginalDescriptor(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    names=set();total=0
    def read(name):
        nonlocal total
        need(type(name) is str and name not in ('','.','..') and '/' not in name and '\\' not in name and name not in names)
        names.add(name);owner=OriginalDescriptor(directory/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        try:
            held=os.fstat(owner.fd);private(held,0o400);raw=os.pread(owner.fd,65537,0)
            need(len(raw)==held.st_size and stamp(held)==stamp(os.fstat(owner.fd))==stamp((directory/name).lstat()))
            owner.require(owner.fd);total+=len(raw);need(total<=LIMIT_BYTES+4*1024*1024)
            return raw,stamp(held)
        finally:owner.close()
    try:
        raw,_=read('manifest.json');manifest=decode(raw.decode());manifest_sha=hashlib.sha256(raw).hexdigest()
        version=manifest.get('chatEvidenceArchiveVersion');need(type(version) is int and version in (LEGACY_VERSION,CLOSED_VERSION,WINDOW_VERSION,VERSION))
        exact(manifest,{'chatEvidenceArchiveVersion','metadata','parts'}|({'fileOwnership'} if version>=CLOSED_VERSION else set())|({'unlinkPolicy'} if version>=WINDOW_VERSION else set())|({'copyVerification'} if version==VERSION else set()))
        if version>=CLOSED_VERSION:need(manifest['fileOwnership']==FILE_OWNERSHIP)
        if version>=WINDOW_VERSION:need(manifest['unlinkPolicy']==UNLINK_POLICY)
        if version==VERSION:need(manifest['copyVerification']==COPY_POLICY)
        need(type(manifest['chatEvidenceArchiveVersion']) is int and manifest['chatEvidenceArchiveVersion']==version
            and type(manifest['metadata']) is dict and type(manifest['parts']) is list and 1<=len(manifest['parts'])<=LIMIT_FILES//64)
        labels=[];items=[]
        for index,part in enumerate(manifest['parts']):
            exact(part,{'file','sha256'});need(part['file']==f'manifest-{index:03d}.json')
            raw,_=read(part['file']);need(hashlib.sha256(raw).hexdigest()==part['sha256'])
            # decode accepts both an object and this fixed original list while
            # retaining duplicate-key and non-finite-value rejection.
            rows=decode(raw.decode());need(type(rows) is list and 1<=len(rows)<=64)
            items.extend(rows)
        need(1<=len(items)<=LIMIT_FILES)
        for index,item in enumerate(items):
            exact(item,{'label','file','bytes','sha256','sourceStamp','archiveStamp'})
            need(type(item['label']) is str and item['label'].startswith(('primary/','peer/')) and item['label'].count('/')==1
                and item['label'].rsplit('/',1)[-1] not in ('','.','..') and '\\' not in item['label']
                and item['label'] not in labels and item['file']==f'original-{index:04d}.json' and integer(item['bytes'],1,65536)
                and type(item['sourceStamp']) is list and len(item['sourceStamp'])==8
                and all(type(number) is int and 0<=number<2**64 for number in item['sourceStamp'])
                and stat.S_ISREG(item['sourceStamp'][2]) and stat.S_IMODE(item['sourceStamp'][2])==0o600
                and item['sourceStamp'][3]==os.geteuid() and item['sourceStamp'][4]==1 and item['sourceStamp'][5]==item['bytes']
                and type(item['archiveStamp']) is list and all(type(number) is int for number in item['archiveStamp']))
            labels.append(item['label']);raw,actual=read(item['file'])
            need(len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'] and actual==item['archiveStamp'])
        raw,_=read('final.json');final=decode(raw.decode());exact(final,{'chatEvidenceArchiveFinalVersion','archiveSha256','metadataSha256','retiredCount','retiredSha256','original'})
        need(type(final['chatEvidenceArchiveFinalVersion']) is int and final['chatEvidenceArchiveFinalVersion']==version
            and final['archiveSha256']==manifest_sha and final['metadataSha256']==digest(manifest['metadata']) and type(final['retiredCount']) is int and final['retiredCount']==len(labels) and final['retiredSha256']==digest(labels))
        proof=unpack(final['original']);need(len(proof)==1 and type(proof[0]) is dict)
        root.require(root.fd);need({path.name for path in directory.iterdir()}==names
            and (directory.stat().st_dev,directory.stat().st_ino)==root.node and stat.S_IMODE(directory.stat().st_mode)==0o500)
        result=dict(metadata=manifest['metadata'],original=proof[0],archiveSha256=manifest_sha,finalSha256=hashlib.sha256(raw).hexdigest())
        if version>=CLOSED_VERSION:result.update(chatEvidenceArchiveVersion=version,fileOwnership=FILE_OWNERSHIP)
        if version>=WINDOW_VERSION:result['unlinkPolicy']=UNLINK_POLICY
        if version==VERSION:result['copyVerification']=COPY_POLICY
        return deepcopy(result)
    finally:root.close()
