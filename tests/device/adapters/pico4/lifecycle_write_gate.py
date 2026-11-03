"""Warm original writer permits; no source, input or cold-resume authority.

Budget checks precede the existing codecs. Only the exact registered writer can
complete an admitted root transition. Source3's optional child sink holds its
actual creation OFD through fsync/readback; the default shared codec is reused.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import os

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import digest,json_digest
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need,integer
from adapters.observer_return import state as file_state
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.script_journey.history import canonical,pack,MAX_RAW,MAX_FRAMES,MAX_PACKED

VERSION=1
PART=65536
NAMES={'world':'lifecycle-world-owner.json','chat':'lifecycle-chat-owner.json',
    'source':'lifecycle-primary-observation.json'}


def compressed_bound(size):
    # Same reviewed zlib bound used by Lifecycle Actor staging admission.
    return size+(size>>12)+(size>>14)+(size>>25)+13


def source_peak(size):
    compressed=compressed_bound(size);encoded=4*((compressed+2)//3)
    parts=max(1,(encoded+24575)//24576)
    # Source bundle part DTO and the unchanged outer Chunk1 pack work window.
    inner=24576+256;outer=4*((compressed_bound(inner+2)+2)//3)
    peak=2*size+compressed+3*encoded+inner+compressed_bound(inner+2)+2*outer+3*PART+4096*(parts+1)
    return parts,parts*PART+PART,peak


@dataclass(eq=False)
class WritePermit:
    gate: object
    writer: object
    value: object
    references: object
    kind: str
    root: object=None
    value_sha: str|None=None
    root_sha: str|None=None
    old: object=None
    old_raw: bytes|None=None
    old_stamp: object=None
    prepared: object=None
    manifest: object=None
    peak: int=0
    stored: int=0
    parts: int=0
    failed: bool=False
    anchors: object=None


class LifecycleWriteGate:
    def __init__(self,raw,writer,role):
        from adapters.pico4.lifecycle_background_raw import LifecycleBackgroundRaw3
        from adapters.pico4.lifecycle_world import PicoLifecycleWorld
        from adapters.pico4.lifecycle_chat import PicoLifecycleChatDraft
        from adapters.pico4.lifecycle_observation import PicoLifecycleObservation
        need(type(raw) is LifecycleBackgroundRaw3 and role in NAMES
            and type(writer) is {'world':PicoLifecycleWorld,'chat':PicoLifecycleChatDraft,'source':PicoLifecycleObservation}[role]
            and writer.lock is raw.lock and writer.run==raw.run and writer.binding==raw.binding
            and writer.store.path==raw.path.parent/NAMES[role] and getattr(writer,'storage_gate',None) is None)
        if role=='source':need(writer.version==3)
        self.raw,self.writer,self.role,self.lock=raw,writer,role,raw.lock
        self.namespace=raw.namespace;self.pending=None;self.poisoned=False;self.child=None
        self.receipts=self._receipts=();self._receipt_seal=(self.receipts,2)
        self.held=[];self.peak=None
        self.history=writer.history if role=='source' else None
        writer.storage_gate=self
        writer._original_storage_gate=self

    def metadata_bytes(self):
        need(self.receipts is self._receipts is self._receipt_seal[0]);return self._receipt_seal[1]

    def identity(self,writer):
        self.lock.assert_held()
        need(not self.poisoned and not self.raw.failed and not self.raw.archive.failed and not self.raw.archive.stopped
            and len(self.receipts)<MAX_FRAMES and writer is self.writer and writer.storage_gate is self
            and writer.lock is self.raw.lock is self.lock and writer.run==self.raw.run
            and writer.binding==self.raw.binding and writer.store.path==self.raw.path.parent/NAMES[self.role])
        self.raw.archive.guard();self.raw.check_hooks()
        if self.role=='source':
            need(writer.history is self.history and self.history.root is writer.store
                and self.history.root_path==writer.store.path and self.history.scope==json_digest(writer.scope))

    def finish_bytes(self,permit):
        need(permit in self.held and permit.gate is self)
        size=canonical_size(permit.value)
        if permit.kind=='child':
            encoded=4*((compressed_bound(size)+2)//3)
            return 2*size+encoded+2*PART
        return 2*size+3*PART

    def hold(self,writer,value,references=None,*,kind):
        # Retain exact acquired objects BEFORE a preflight can raise. No clone,
        # parser, canonical buffer or codec is needed to keep these references.
        permit=WritePermit(self,writer,value,references,kind,prepared={},manifest=[])
        self.held.append(permit)
        try:self.identity(writer)
        except BaseException:self.failed(writer,permit);raise
        permit.anchors=self.anchors()
        return permit

    def anchors(self):
        writer=self.writer
        if self.role=='world':return (writer.acquired_start,writer.fresh_anchor)
        if self.role=='chat':return writer.acquisition
        return (writer.anchor,writer.acquisition.fresh_anchor)

    def admit(self,permit,*,parts,stored,peak):
        need(permit in self.held and self.pending is None)
        self.raw.phase_writes();permit.parts,permit.stored,permit.peak=parts,stored,peak
        self.namespace.begin_write(self,permit,parts=parts,stored=stored,decoded=peak,metadata=4096*(parts+1))
        self.pending=permit;self.peak=max(self.peak or 0,peak)

    def pin_root(self,permit):
        path=self.writer.store.path;self.namespace.write_guard(self,permit,permit.prepared or {})
        descriptor=OriginalDescriptor('/proc/self/fd/'+str(self.namespace.directory.fd)+'/'+path.name,
            os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        permit.old=descriptor;descriptor.require(descriptor.fd)
        info=os.fstat(descriptor.fd);stamp=signature(info)
        raw=os.pread(descriptor.fd,PART+1,0);descriptor.require(descriptor.fd)
        need(stamp==signature(path.lstat()) and 0<len(raw)<=PART and len(raw)==info.st_size
            and raw==canonical(self.writer.disk)+b'\n')
        permit.old_raw,permit.old_stamp=raw,stamp

    def before_state(self,writer,state):
        permit=self.hold(writer,state,kind='state')
        try:
            need(self.role in ('world','chat'))
            size=canonical_size([state]);compressed=(2*size+1024 if self.role=='world' and writer.disk['lifecycleWorldOwnerVersion']==2
                else compressed_bound(size))
            encoded=4*((compressed+2)//3)
            if self.role=='world' and writer.disk['lifecycleWorldOwnerVersion']==2:encoded=min(encoded,MAX_PACKED)
            self.admit(permit,parts=0,stored=PART,peak=2*size+compressed+3*encoded+3*PART+4096)
            self.pin_root(permit);permit.value_sha=hashlib.sha256(canonical([state])).hexdigest()
            return permit
        except BaseException:self.failed(writer,permit);raise

    def encoded(self,writer,permit,root):
        try:
            self.identity(writer);need(self.pending is permit and permit.kind=='state')
            need(canonical_size(root)+1<=PART and root['binding']==self.raw.binding and root['runId']==self.raw.run
                and root['payload']['sha256']==permit.value_sha and root['payload']['bytes']==canonical_size([permit.value]))
            need(hashlib.sha256(canonical([permit.value])).hexdigest()==permit.value_sha)
            from adapters.pico4.lifecycle_world_codec import unpack as world_unpack
            from adapters.script_journey.history import unpack
            decoded=(world_unpack(root['payload'],root['lifecycleWorldOwnerVersion']) if self.role=='world' else unpack(root['payload']))
            need(decoded==[permit.value]);permit.root=deepcopy(root);permit.root_sha=json_digest(root)
            self.namespace.write_guard(self,permit,{})
        except BaseException:self.failed(writer,permit);raise

    def before_root(self,writer,root):
        permit=self.hold(writer,root,kind='root')
        try:
            need(self.role=='source' and canonical_size(root)+1<=PART)
            if self.child is None:
                self.admit(permit,parts=0,stored=PART,peak=3*PART+4096)
            else:
                need(self.pending is self.child and self.child.kind=='child')
                # The child's original whole encoding/materialization credit
                # remains owned across every intermediate actual root CAS.
                self.namespace.subwrite(self,self.child,permit);self.pending=permit
            permit.prepared={} if self.child is None else {name:dict(row) for name,row in self.child.prepared.items()}
            self.pin_root(permit);permit.root=deepcopy(root);permit.root_sha=json_digest(root)
            return permit
        except BaseException:self.failed(writer,permit);raise

    def after(self,writer,permit,root):
        try:
            self.identity(writer);need(self.pending is permit and permit.gate is self and permit.writer is writer
                and permit.root_sha==json_digest(root)==json_digest(writer.disk) and not permit.failed
                and permit.anchors==self.anchors())
            actual,raw,stamp=file_state(writer.store)
            need(actual==root and raw==canonical(root)+b'\n' and len(raw)<=PART)
            permit.old.require(permit.old.fd)
            old=signature(os.fstat(permit.old.fd))
            need(os.pread(permit.old.fd,PART+1,0)==permit.old_raw and old[:4]==permit.old_stamp[:4]
                and old[4]==0 and old[5:7]==permit.old_stamp[5:7] and stamp[:2]!=permit.old_stamp[:2])
            self.namespace.commit_write(self,permit,stamp,permit.prepared or {})
            need(permit.old.close());permit.old=None
            need(len(self.receipts)<MAX_FRAMES)
            row=(self.role,tuple(permit.old_stamp),tuple(stamp),permit.root_sha)
            added=canonical_size(dict(role=self.role,before=permit.old_stamp,after=stamp,sha256=permit.root_sha))
            size=self.metadata_bytes()+added+(1 if self.receipts else 0)
            self.namespace.spend_metadata(self,permit,3*(size-self.metadata_bytes()))
            self.receipts=self._receipts=(*self.receipts,row);self._receipt_seal=(self.receipts,size)
            if self.child is not None:
                child=self.child;self.namespace.resume_child(self,permit,child);self.pending=child
            else:
                self.namespace.finish_write(self,permit);self.pending=None
            self.held.remove(permit)
        except BaseException:self.failed(writer,permit);raise

    def before_child(self,writer,value,references):
        permit=self.hold(writer,value,references,kind='child')
        try:
            need(self.role=='source' and self.child is None)
            size=canonical_size(value);parts,stored,peak=source_peak(size)
            self.admit(permit,parts=parts,stored=stored,peak=peak)
            permit.value_sha=json_digest(value);permit.manifest=deepcopy(writer.disk['chunks'])
            self.child=permit
            return permit
        except BaseException:self.failed(writer,permit);raise

    def append_child(self,writer,permit,part,manifest):
        descriptor=None
        try:
            self.identity(writer);need(self.pending is self.child is permit and permit.kind=='child'
                and manifest==permit.manifest and len(permit.prepared)<permit.parts)
            history=writer.history;index=len(manifest);need(index==len(history.identities)<MAX_FRAMES)
            history.verify();root=history.root.read()
            need(root is not None and root['phase']=='reading' and root['chunks']==manifest)
            self.namespace.write_guard(self,permit,permit.prepared)
            transcript=pack([deepcopy(part)]);total=history.raw_bytes+transcript['bytes']-2+(1 if manifest else 0)
            need(total<=MAX_RAW)
            value=dict(chatSampleChunkVersion=1,scopeSha256=history.scope,index=index,transcript=transcript)
            raw=canonical(value)+b'\n';need(len(raw)<=PART)
            path=history.store(index).path
            need(path==self.namespace.path/(writer.store.path.name+f'.frame-{index:03d}.json'))
            descriptor=OriginalDescriptor('/proc/self/fd/'+str(self.namespace.directory.fd)+'/'+path.name,
                os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC)
            permit.prepared[path.name]=dict(owner=descriptor,physical=None,sha256=None)
            descriptor.require(descriptor.fd);os.fchmod(descriptor.fd,0o600);descriptor.require(descriptor.fd)
            offset=0
            while offset<len(raw):
                descriptor.require(descriptor.fd);count=os.pwrite(descriptor.fd,raw[offset:],offset);descriptor.require(descriptor.fd)
                need(integer(count,1));offset+=count
            os.fsync(descriptor.fd);descriptor.require(descriptor.fd)
            stamp=signature(os.fstat(descriptor.fd));readback=os.pread(descriptor.fd,PART+1,0);descriptor.require(descriptor.fd)
            need(readback==raw and signature(path.lstat())==stamp and stamp[5]==len(raw))
            # This is the SAME creation/write OFD, not a post-hoc opened alias.
            need(descriptor.close());permit.prepared[path.name]=dict(owner=descriptor,physical=stamp,sha256=hashlib.sha256(raw).hexdigest())
            observed=history.signature(index);need(observed==(stamp[0],stamp[1],stamp[5],stamp[3],stamp[2],stamp[4],stamp[6],stamp[7]))
            history.identities.append(observed);history.raw_bytes=total;history.verify()
            permit.manifest=[*manifest,digest(value)];return deepcopy(permit.manifest)
        except BaseException:self.failed(writer,permit);raise

    def after_child(self,writer,permit,reference):
        try:
            self.identity(writer);need(self.pending is self.child is permit and not permit.failed
                and json_digest(permit.value)==permit.value_sha and writer.disk['chunks']==permit.manifest
                and writer.disk['bundles'][-1]==reference and reference['sha256']==permit.value_sha
                and permit.anchors==self.anchors())
            writer.history.verify();self.child=None
            self.namespace.finish_write(self,permit);self.pending=None;self.held.remove(permit)
        except BaseException:self.failed(writer,permit);raise

    def failed(self,writer,permit):
        self.poisoned=True;self.raw.failed=True;self.raw.archive.stopped=True
        if permit is not None:permit.failed=True
        from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
        if not any(owner is self for _path,owner in UNRESOLVED):UNRESOLVED.append((self.namespace.path,self))

    def close_host(self):
        results=[]
        for permit in self.held:
            if permit.old is not None:results.append(permit.old.close())
            for row in (permit.prepared or {}).values():
                if row.get('owner') is not None:results.append(row['owner'].close())
        return not self.held and all(results)
