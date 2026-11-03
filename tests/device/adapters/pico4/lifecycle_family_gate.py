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
from adapters.script_journey.history import canonical,pack,unpack,MAX_FRAMES,MAX_PACKED

PART=65536


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
    def __init__(self,raw,writer):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
        from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
        need(type(raw) is LifecycleSourceRaw4 and type(writer) is PicoLifecycleBackground
            and writer.version==4 and writer.originals is raw and writer.run==raw.run
            and writer.binding==raw.binding and writer.lock is raw.lock
            and writer.store.path==raw.path.parent/'lifecycle-background-owner.json'
            and getattr(writer,'storage_gate',None) is None)
        self.raw,self.writer,self.namespace,self.lock=raw,writer,raw.namespace,raw.lock
        self.view=raw.view('background');self.pending=None;self.held=[];self.poisoned=False
        self.receipts=self._receipts=();self._receipt_seal=(self.receipts,2)
        writer.storage_gate=writer._original_storage_gate=self

    def identity(self):
        self.lock.assert_held()
        need(not self.poisoned and not self.raw.failed and not self.raw.archive.failed
            and not self.raw.archive.stopped and self.writer.storage_gate is self
            and self.writer._original_storage_gate is self and self.writer.originals is self.raw
            and self.writer.version==4 and self.writer.lock is self.lock is self.raw.lock
            and self.writer.run==self.raw.run and self.writer.binding==self.raw.binding
            and self.writer.store.path==self.raw.path.parent/'lifecycle-background-owner.json')
        self.raw.archive.guard();self.raw.check_hooks()

    def metadata_bytes(self):
        need(self.receipts is self._receipts is self._receipt_seal[0])
        # Exact held graphs are counted, not a caller-mutable cached cost.
        return self._receipt_seal[1]+sum(canonical_size(permit.value) for permit in self.held)

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
            # All DTO/projection/pack/Base64/decode and root CAS work windows
            # are charged BEFORE the projection or codec allocates them.
            compressed=compressed_bound(size);encoded=4*((compressed+2)//3)
            peak=8*size+compressed+3*max(encoded,MAX_PACKED)+6*PART
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
            encoded=pack(projection.encoded)
            root=dict(lifecycleBackgroundOwnerVersion=4,runId=self.raw.run,binding=deepcopy(self.raw.binding),
                originalChunks=refs,payload=encoded)
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
            self.writer.disk,self.writer.state=deepcopy(root),deepcopy(value)
            receipt=('background',None if permit.old_stamp is None else tuple(permit.old_stamp),tuple(stamp),permit.root_sha)
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
        for permit in self.held:
            for owner in (permit.old,permit.created):
                if owner is not None:
                    try:result=owner.close() is True and result
                    except BaseException:result=False
        return result and not self.held and not self.poisoned
