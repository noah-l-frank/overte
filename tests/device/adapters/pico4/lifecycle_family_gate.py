"""Exact warm Background4 root writer, sharing SourceRaw4 admission.

No generic callback, changed filename or payload equality admits a write. The
first root retains its creation OFD; later roots require the existing writer's
actual CAS, old original OFD unlink and exact readback. Unknown writes remain
owned and prohibit another target acquisition.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from dataclasses import dataclass
import os

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need,integer
from adapters.observer_return import state as file_state
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.pico4.lifecycle_write_gate import compressed_bound
from adapters.script_journey.history import canonical,pack,unpack,MAX_FRAMES,MAX_PACKED,MAX_RAW

PART=65536
# Profile is bounded by the exact neutral helper before its first file read.
CODEC_RESERVE=3*32768+2*PART


@dataclass(eq=False)
class FamilyPermit4:
    gate:object
    writer:object
    value:object
    value_size:int=0
    value_sha:str|None=None
    projection:object=None
    projection_sha:str|None=None
    root:object=None
    root_sha:str|None=None
    old:object=None
    old_raw:bytes|None=None
    old_stamp:object=None
    created:object=None
    prepared:object=None
    committed:bool=False
    failed:bool=False


class LifecycleFamilyGate4:
    def __init__(self,raw,writer,*,role='background'):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
        from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
        from adapters.pico4.lifecycle_pending import PicoLifecyclePending
        need(type(raw) is LifecycleSourceRaw4 and type(role) is str and role in ('background','pending'))
        if role=='background':need(type(writer) is PicoLifecycleBackground and writer.version in (4,5))
        else:need(type(writer) is PicoLifecyclePending and writer.version==3 and writer.layout==3
            and raw.pending_read_version==1 and writer.originals is raw)
        need(writer.originals is raw and writer.run==raw.run and writer.binding==raw.binding and writer.lock is raw.lock
            and writer.store.path==raw.path.parent/('lifecycle-'+role+'-owner.json')
            and getattr(writer,'storage_gate',None) is None)
        self.role=self._role=role
        self.root_key='lifecycleBackgroundOwnerVersion' if role=='background' else 'lifecyclePendingOwnerVersion'
        self.root_version=writer.version if role=='background' else 3
        self.raw,self.writer,self.namespace,self.lock=raw,writer,raw.namespace,raw.lock
        self.view=raw.view(role);self.pending=None;self.held=[];self.poisoned=False
        self.receipts=self._receipts=();self._receipt_seal=(self.receipts,2)
        self._family=self._original_family=(role,self.root_key,self.root_version,raw,writer,self.view)
        writer.storage_gate=writer._original_storage_gate=self
        self.codec=self._original_codec=None
        self._codec_seal=self._original_codec_seal=(None,0)
        if role=='pending':
            # Admission precedes extension/helper OFDs, hashes and metadata
            # materialization. No target acquisition occurs in this window.
            try:
                need(type(raw.family_attempt) is tuple and raw.family_attempt is raw._original_family_attempt
                    and raw.family_attempt[0] is self and raw.family_attempt[1]==CODEC_RESERVE)
                current=raw.other_bill();ours=raw.archive.bill()
                # The bank already holds/charges CODEC_RESERVE for this exact
                # attempt. Do not construct before that original reservation.
                need(current['decodedBytes']+ours['decodedBytes']<=MAX_RAW)
                from adapters.loaded_chunk_codec import OriginalChunkCodec
                codec=OriginalChunkCodec.__new__(OriginalChunkCodec)
                self.codec=self._original_codec=codec
                self._codec_seal=self._original_codec_seal=(codec,CODEC_RESERVE)
                OriginalChunkCodec.__init__(codec)
                need(codec.metadata_bytes()<=CODEC_RESERVE)
            except BaseException:
                self.poisoned=True;raw.failed=True
                from adapters.pico4.lifecycle_background_raw_state import close_or_retain,UNRESOLVED
                close_or_retain(raw.path.parent,self.codec)
                if not any(owner is self for _directory,owner in UNRESOLVED):UNRESOLVED.append((raw.path.parent,self))
                raise

    def codec_guard(self):
        need(self._codec_seal is self._original_codec_seal and self.codec is self._original_codec is self._codec_seal[0])
        if self.role=='pending':
            from adapters.loaded_chunk_codec import OriginalChunkCodec
            need(type(self.codec) is OriginalChunkCodec and self._codec_seal[1]==CODEC_RESERVE)
            self.codec.guard()
        else:need(self.codec is None and self._codec_seal[1]==0)

    def identity(self):
        self.lock.assert_held()
        need(not self.poisoned and not self.raw.failed and not self.raw.archive.failed
            and not self.raw.archive.stopped and self.writer.storage_gate is self
            and self.writer._original_storage_gate is self and self.writer.originals is self.raw
            and self._family is self._original_family and self.role==self._role==self._family[0]
            and self.root_key==self._family[1] and self.root_version==self._family[2]
            and self.raw is self._family[3] and self.writer is self._family[4] and self.view is self._family[5]
            and self.writer.version==self.root_version and self.writer.lock is self.lock is self.raw.lock
            and self.writer.run==self.raw.run and self.writer.binding==self.raw.binding
            and self.writer.store.path==self.raw.path.parent/('lifecycle-'+self.role+'-owner.json'))
        self.raw.archive.guard();self.raw.check_hooks();self.codec_guard()

    def metadata_bytes(self):
        need(self.receipts is self._receipts is self._receipt_seal[0])
        # Exact held graphs are counted, not a caller-mutable cached cost.
        need(self._codec_seal is self._original_codec_seal and self.codec is self._original_codec is self._codec_seal[0])
        # The conservative reservation also covers incomplete/failed profiles;
        # business failure must not hide already held codec/file resources.
        return self._receipt_seal[1]+sum(canonical_size(permit.value) for permit in self.held)+self._codec_seal[1]

    def finish_bytes(self,permit):
        need(permit in self.held and permit.gate is self)
        return 4*canonical_size(permit.value)+3*PART

    def read_bill(self):
        permit=self.pending;need(permit is not None and self.namespace._write is not None
            and self.namespace._write[:2]==(self,permit))
        return self.namespace(_write_token=self.namespace._write[5])

    def guard_namespace(self):
        need(self.pending is not None)
        self.namespace.write_guard(self,self.pending,self.pending.prepared or {})

    def before(self,value):
        permit=FamilyPermit4(self,self.writer,value,prepared={});self.held.append(permit)
        try:
            self.identity();need(self.pending is None and self.raw.active_family is None
                and self.view.pending is None and self.raw.pending_view is None and len(self.receipts)<MAX_FRAMES)
            self.raw.phase_writes();size=canonical_size([value]);permit.value_size=size
            reference_work=0;encoded_bound=size
            if self.role=='pending':
                self.namespace.bind_family_root(self)
                _size,encoded_bound,reference_work=self.raw.pending_projection_bound([value])
                need(_size==size)
            # All DTO/projection/pack/Base64/decode and root CAS work windows
            # are charged BEFORE the projection or codec allocates them.
            compressed=(self.codec.compress_bound(encoded_bound) if self.role=='pending'
                else compressed_bound(encoded_bound))
            encoded=4*((compressed+2)//3)
            peak=8*encoded_bound+compressed+3*max(encoded,MAX_PACKED)+6*PART+3*reference_work
            self.namespace.begin_write(self,permit,parts=0,stored=PART,decoded=peak,metadata=8192)
            self.pending=permit;self.raw.active_family=self
            permit.value_sha=json_digest(value)
            if self.writer.disk is not None:
                path=self.writer.store.path
                permit.old=OriginalDescriptor('/proc/self/fd/'+str(self.namespace.directory.fd)+'/'+path.name,
                    os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                permit.old.require(permit.old.fd);stamp=signature(os.fstat(permit.old.fd))
                raw=os.pread(permit.old.fd,PART+1,0);permit.old.require(permit.old.fd)
                need(stamp==signature(path.lstat()) and raw==canonical(self.writer.disk)+b'\n' and 0<len(raw)<=PART)
                permit.old_raw,permit.old_stamp=raw,stamp
            self.guard_namespace();return permit
        except BaseException:self.failed(permit);raise

    def save(self,value):
        permit=self.before(value)
        try:
            permit.projection=self.view.project([value])
            projection=permit.projection
            permit.projection_sha=json_digest(projection.encoded)
            refs=self.view.reference_dtos(projection.references)
            if self.role=='pending':self.codec_guard()
            encoded=pack(projection.encoded)
            if self.role=='pending':self.codec_guard()
            root={self.root_key:self.root_version,'runId':self.raw.run,'binding':deepcopy(self.raw.binding),
                'originalChunks':refs,'payload':encoded}
            need(canonical_size(root)+1<=PART and unpack(encoded)==projection.encoded
                and json_digest(projection.encoded)==permit.projection_sha and json_digest(value)==permit.value_sha)
            permit.root=root;permit.root_sha=json_digest(root)
            self.identity();self.guard_namespace()
            if permit.old is None:self.create_root(permit)
            else:self.writer.store.write(root,self.writer.disk)
            actual,raw,stamp=file_state(self.writer.store)
            need(actual==root and raw==canonical(root)+b'\n' and len(raw)<=PART)
            if permit.old is not None:
                permit.old.require(permit.old.fd);old=signature(os.fstat(permit.old.fd))
                need(os.pread(permit.old.fd,PART+1,0)==permit.old_raw and old[:4]==permit.old_stamp[:4]
                    and old[4]==0 and old[5:7]==permit.old_stamp[5:7] and stamp[:2]!=permit.old_stamp[:2])
            self.namespace.commit_write(self,permit,stamp,permit.prepared)
            if permit.old is not None:need(permit.old.close());permit.old=None
            if self.role=='background' and self.root_version==5:
                need(type(projection.encoded) is list and len(projection.encoded)==1 and type(projection.encoded[0]) is dict)
                current_state=projection.encoded[0]
            else:current_state=value
            self.writer.disk,self.writer.state=deepcopy(root),deepcopy(current_state)
            receipt=(self.role,None if permit.old_stamp is None else tuple(permit.old_stamp),tuple(stamp),permit.root_sha)
            added=canonical_size(dict(role=receipt[0],before=None if receipt[1] is None else list(receipt[1]),
                after=list(receipt[2]),sha256=receipt[3]))+(1 if self.receipts else 0)
            self.namespace.spend_metadata(self,permit,3*added)
            self.receipts=self._receipts=(*self.receipts,receipt)
            self._receipt_seal=(self.receipts,self._receipt_seal[1]+added)
            self.namespace.finish_write(self,permit)
            need(json_digest(value)==permit.value_sha and json_digest(root)==permit.root_sha
                and json_digest(projection.encoded)==permit.projection_sha)
            # Actual CAS and the complete new namespace bill BOTH succeeded.
            # Only now may this one typed owner's confirmed manifest advance.
            permit.committed=True
            self.view.confirm(self,permit)
            self.pending=None;self.raw.active_family=None;self.held.remove(permit)
            self.raw.published=True;self.raw.verify()
        except BaseException:self.failed(permit);raise

    def create_root(self,permit):
        path=self.writer.store.path;require_directory(self.namespace.directory,path.parent)
        descriptor=OriginalDescriptor.__new__(OriginalDescriptor);permit.created=descriptor
        OriginalDescriptor.__init__(descriptor,'/proc/self/fd/'+str(self.namespace.directory.fd)+'/'+path.name,
            os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC)
        descriptor.require(descriptor.fd);os.fchmod(descriptor.fd,0o600);descriptor.require(descriptor.fd)
        raw=canonical(permit.root)+b'\n';offset=0
        while offset<len(raw):
            descriptor.require(descriptor.fd);written=os.pwrite(descriptor.fd,raw[offset:],offset)
            need(integer(written,1,len(raw)-offset));offset+=written
        descriptor.require(descriptor.fd);os.fsync(descriptor.fd);descriptor.require(descriptor.fd)
        actual=os.pread(descriptor.fd,PART+1,0);stamp=signature(os.fstat(descriptor.fd))
        descriptor.require(descriptor.fd)
        need(actual==raw and stamp==signature(path.lstat()) and stamp[2]&0o777==0o600)
        os.fsync(self.namespace.directory.fd);require_directory(self.namespace.directory,path.parent)
        need(descriptor.close())
        permit.prepared[path.name]=dict(owner=descriptor,physical=tuple(stamp))

    def failed(self,permit):
        permit.failed=True;self.poisoned=True;self.raw.failed=True
        from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
        if not any(owner is self for _directory,owner in UNRESOLVED):UNRESOLVED.append((self.raw.path.parent,self))

    def close_host(self):
        result=True
        if self.codec is not None:
            try:result=self.codec.close_host() is True and result
            except BaseException:result=False
        for permit in self.held:
            for owner in (permit.old,permit.created):
                if owner is not None:
                    try:result=owner.close() is True and result
                    except BaseException:result=False
        return result and not self.held and not self.poisoned
