"""Original family data OFDs for fresh checks after the true SourceLock exit.

Read-only prerequisite. Existing BG4 is the executable core fixture; it does
not qualify Pending3, another owner, product effects or a new current verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
import hashlib
import os
import stat

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.pico4.lifecycle_descriptor_close import pin as pin_close,close_original
from adapters.native_feature_observation import need,integer
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.script_journey.history import canonical,unpack,MAX_RAW

PART=65536
UNRESOLVED=[]


def digest(raw):return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class DataPin:
    name:str
    physical:tuple
    sha256:str
    descriptor:object


class LifecyclePendingReturnPins:
    """Same actual writer/gate only; never a filename-based authority grant."""
    def __init__(self,gate):
        self.close_proof=self._original_close_proof=pin_close()
        self.close_procedure=self._original_close_procedure=(close_original,close_original.__code__)
        self.gate=gate;self.entries=[];self.partial=self._original_partial=[];self._partial_seal=self._original_partial_seal=();self._close_receipt=self._original_close_receipt=None;self.failed=False;self.prepared=False;self.closed=False
        self._entries=self._original_entries=None;self._fixed=self._original_fixed=None
        self.reserve_bytes=0;self._reserve_seal=None;self.namespace_pin=None
        try:
            from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
            from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
            from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
            from adapters.pico4.lifecycle_pending import PicoLifecyclePending
            need(type(gate) is LifecycleFamilyGate4 and type(gate.raw) is LifecycleSourceRaw4)
            self.raw,self.writer,self.role=gate.raw,gate.writer,gate.view.role
            self.lock=self.raw.lock;self.lock.assert_held();gate.identity()
            # Pending3 is a subsequent exact role; no fake Pending instance or
            # loose ducktype is accepted to qualify this first executable core.
            need((self.role=='background' and type(self.writer) is PicoLifecycleBackground and self.writer.version in (4,5)
                or self.role=='pending' and type(self.writer) is PicoLifecyclePending and self.writer.version==3
                    and self.writer.layout==3 and self.raw.pending_read_version==1)
                and self.writer.originals is self.raw and self.writer.storage_gate is gate
                and self.writer._original_storage_gate is gate and gate.pending is None
                and self.raw.active_family is None and self.raw.pending_view is None
                and gate.receipts and gate.receipts[-1][0]==self.role)
            self.archive=self.raw.archive;self.directory=self.archive.directory;self.host=self.archive.host
            self.root_name=self.writer.store.path.name;self.root_receipt=gate.receipts[-1]
            self.binding_sha=json_digest(self.writer.binding)
            self._fixed=self._original_fixed=(gate,self.raw,self.writer,self.role,self.archive,self.directory,self.lock,
                self.host,self.root_name,self.root_receipt,self.binding_sha)
            self.raw.verify();need(not self.archive.state['pending'] and not self.archive.unconfirmed_returns)
            disk_size=canonical_size(self.writer.disk);state_size=canonical_size(self.writer.state)
            count=2+len(self.archive.state['parts'])+len(self.archive.pages);need(count<=530)
            payload=self.writer.disk['payload'];need(integer(payload['bytes'],2,MAX_RAW))
            # Admission BEFORE canonical hashes, codec/copy, extra OFDs and
            # read buffers. This core creates no file or part of its own.
            self.reserve_bytes=3*count*512+PART+2*max(disk_size,state_size)+3*payload['bytes']+3*state_size
            self._reserve_seal=self._original_reserve_seal=(self.reserve_bytes,)
            self.raw.bind_return_pins(self)
            current=self.raw.other_bill();ours=self.archive.bill()
            # The exact bank slot already charges the COMPLETE prospective
            # pin/decoder/canonical work reserve before allocating any of it.
            need(current['decodedBytes']+ours['decodedBytes']<=MAX_RAW)
            self.namespace_pin=self.raw.namespace.lease
            need(self.namespace_pin is self.raw.namespace._lease and self.namespace_pin is not None)
            self._owner_seal=(self.writer.disk,disk_size,json_digest(self.writer.disk),
                self.writer.state,state_size,json_digest(self.writer.state))
            need(self.root_receipt[3]==self._owner_seal[2])
            decoded=self.raw.decode(unpack(payload),role=self.role)
            need(json_digest(decoded)==json_digest([self.writer.state]));del decoded
            self._owner_guard()
            root_raw=canonical(self.writer.disk)+b'\n'
            self._open(self.root_name,tuple(self.root_receipt[2]),digest(root_raw))
            self._open(self.archive.path.name,tuple(self.archive.pin),digest(canonical(self.archive.disk)+b'\n'))
            for index,row in enumerate(self.archive.state['parts']):
                self._open(self.archive.part_path(index).name,tuple(row['physical']),row['sha256'])
            for index,(value,pin) in sorted(self.archive.page_pins.items()):
                self._open(self.archive.page_store(index).path.name,tuple(pin),digest(canonical(value)+b'\n'))
            self._entries=self._original_entries=tuple(self.entries)
            self.raw_names=tuple(sorted(pin.name for pin in self._entries if pin.name!=self.root_name))
            actual_metadata=canonical_size([[pin.name,list(pin.physical),pin.sha256] for pin in self._entries])
            need(actual_metadata<=count*512)
            self.reserve_bytes=3*actual_metadata+PART+2*max(disk_size,state_size)
            self._reserve_seal=self._original_reserve_seal=(self.reserve_bytes,)
            self.prepared=True;self.verify_data()
        except BaseException:
            self._fail();raise

    def _fail(self):
        self.failed=True
        raw=getattr(self,'raw',None)
        if raw is not None:raw.failed=True
        if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)

    def metadata_bytes(self):
        try:
            need(type(self.reserve_bytes) is int and 0<=self.reserve_bytes<=MAX_RAW
                and self._reserve_seal is self._original_reserve_seal and self._reserve_seal is not None
                and self.reserve_bytes==self._reserve_seal[0])
            return self.reserve_bytes
        except BaseException:self._fail();raise

    def _parent(self):
        need(self._fixed is self._original_fixed and self._fixed is not None and self.host==host_identity()
            and self.directory is self.archive.directory is self.archive.original_directory)
        require_directory(self.directory,self.archive.path.parent)

    def _owner_guard(self):
        need(self._fixed is self._original_fixed and self._fixed is not None)
        from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
        from adapters.pico4.lifecycle_pending import PicoLifecyclePending
        gate,raw,writer,role,archive,directory,lock,host,name,receipt,binding_sha=self._fixed
        need(self.gate is gate and self.raw is raw and self.writer is writer and self.role==role
            and raw.return_slot is raw._original_return_slot is self
            and self.archive is archive and self.directory is directory and self.lock is lock and self.host==host
            and self.root_name==name and self.root_receipt is receipt
            and gate.writer is writer and gate.raw is raw and gate.view is raw.view(role)
            and (role=='background' and type(writer) is PicoLifecycleBackground and writer.version in (4,5)
                or role=='pending' and type(writer) is PicoLifecyclePending and writer.version==3
                    and writer.layout==3 and raw.pending_read_version==1)
            and writer.storage_gate is writer._original_storage_gate is gate and writer.originals is raw
            and writer.store.path==archive.path.with_name(name) and gate.receipts[-1] is receipt
            and not raw.failed and not archive.failed and not gate.poisoned
            and json_digest(writer.binding)==binding_sha and writer.binding==raw.binding)
        disk,size_disk,sha_disk,state,size_state,sha_state=self._owner_seal
        need(writer.disk is disk and writer.state is state
            and canonical_size(disk,size_disk)==size_disk and canonical_size(state,size_state)==size_state
            and json_digest(disk)==sha_disk and json_digest(state)==sha_state)

    def _open(self,name,physical,sha256):
        self._parent();need(type(name) is str and '/' not in name and len(physical)==8
            and physical[5]<=PART and tuple(signature((self.archive.path.parent/name).lstat()))==physical)
        need(self.partial is self._original_partial and type(self.partial) is list
            and self._partial_seal is self._original_partial_seal and type(self._partial_seal) is tuple
            and len(self.partial)==len(self._partial_seal)
            and all(type(saved) is OriginalDescriptor and current is saved for current,saved in zip(self.partial,self._partial_seal)))
        descriptor=OriginalDescriptor.__new__(OriginalDescriptor);self.partial.append(descriptor)
        self._partial_seal=self._original_partial_seal=(*self._partial_seal,descriptor)
        OriginalDescriptor.__init__(descriptor,'/proc/self/fd/'+str(self.directory.fd)+'/'+name,
            os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        pin=DataPin(name,physical,sha256,descriptor);self.entries.append(pin)
        self._read(pin)

    def _read(self,pin):
        self._parent();need(type(pin) is DataPin and type(pin.descriptor) is OriginalDescriptor)
        owner=pin.descriptor;owner.require(owner.fd);before=tuple(signature(os.fstat(owner.fd)))
        need(before==pin.physical and stat.S_ISREG(before[2]) and stat.S_IMODE(before[2]) in (0o400,0o600)
            and before[3]==os.geteuid() and before[4]==1 and 0<=before[5]<=PART
            and tuple(signature((self.archive.path.parent/pin.name).lstat()))==before)
        raw=os.pread(owner.fd,PART+1,0);owner.require(owner.fd)
        need(len(raw)==before[5] and digest(raw)==pin.sha256
            and tuple(signature(os.fstat(owner.fd)))==before
            and tuple(signature((self.archive.path.parent/pin.name).lstat()))==before)
        self._parent()

    def verify_data(self):
        try:
            need(self.prepared and not self.failed and not self.closed and self._entries is self._original_entries
                and type(self.entries) is list and len(self.entries)==len(self._entries)
                and all(type(saved) is DataPin and current is saved for current,saved in zip(self.entries,self._entries)))
            self._parent();self._owner_guard()
            # Namespace data cannot grow behind the last actual global bill.
            # Zero-byte mutex ctime is capacity metadata, not Product authority.
            names=self.raw.namespace.lease_names();expected,pins=self.namespace_pin
            need(names==expected)
            for name,stamp in pins:
                actual=tuple(signature((self.archive.path.parent/name).lstat()))
                if name.endswith('.lock') and stamp[5]==0:
                    need(actual[:7]==stamp[:7])
                else:need(actual==stamp)
            actual=tuple(sorted(path.name for path in self.archive.path.parent.iterdir()
                if path.name==self.archive.path.name or path.name.startswith(self.archive.path.name+'.')))
            need(actual==self.raw_names)
            for pin in self._entries:self._read(pin)
            self._owner_guard();self._parent()
        except BaseException:self._fail();raise

    def close_host(self):
        try:return self._close_host()
        except BaseException:self._fail();raise

    def _close_host(self):
        if self.closed:
            if self.failed:return False
            need(self._close_receipt is self._original_close_receipt and type(self._close_receipt) is tuple
                and self._close_receipt and not self.partial and not self._partial_seal and self.namespace_pin is None)
            for owner,descriptor,anchor,node in self._close_receipt:
                need(type(owner) is OriginalDescriptor and owner.closed is True and owner.lost is False
                    and type(owner.fd) is type(owner.anchor) is int and owner.fd==owner.anchor==-1
                    and type(owner.node) is type(node) is tuple and len(owner.node)==len(node)==2
                    and all(type(current) is type(saved) is int and current==saved for current,saved in zip(owner.node,node)))
            return True
        need(self._partial_seal is self._original_partial_seal and type(self._partial_seal) is tuple
            and all(type(owner) is OriginalDescriptor for owner in self._partial_seal))
        result=(self.partial is self._original_partial and type(self.partial) is list
            and len(self.partial)==len(self._partial_seal)
            and all(current is saved for current,saved in zip(self.partial,self._partial_seal)))
        if not result:self._fail()
        terminals=[];self._closing_pairs=terminals
        # Exact live alias validation plus the pinned close implementation
        # observes both successful original close syscalls. Later numeric FD
        # reuse is foreign; this holder neither touches nor claims its absence.
        for owner in self._partial_seal:
            try:
                need(type(owner.node) is tuple and len(owner.node)==2 and all(type(value) is int for value in owner.node))
                need(self.close_proof is self._original_close_proof
                    and self.close_procedure is self._original_close_procedure
                    and close_original is self.close_procedure[0] and close_original.__code__ is self.close_procedure[1])
                terminals.append(close_original(owner,self.close_proof))
            except BaseException:result=False
        if result:
            self.closed=True
            if not self.failed:
                try:
                    self.raw.release_return_pins(self)
                    self.partial=self._original_partial=[];self.entries=[]
                    self._partial_seal=self._original_partial_seal=()
                    self._close_receipt=self._original_close_receipt=tuple(terminals)
                    self._closing_pairs=None
                    self._entries=self._original_entries=()
                    self.namespace_pin=self._owner_seal=None;self.raw_names=()
                    self.reserve_bytes=0;self._reserve_seal=self._original_reserve_seal=(0,)
                except BaseException:self._fail();raise
        else:self._fail()
        return result and not self.failed
