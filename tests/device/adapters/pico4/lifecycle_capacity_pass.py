"""Opt-in immutable capacity audit reuse; never a source/current verdict.

Each hit freshly reads ALL original namespace files through actual OFDs, checks
full physical stamps/bytes and the SAME expanded callback result exactly once.
Only repeated JSON/codec expansion is omitted under its original complete bill.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
import re
import threading
import base64
import zlib
import lzma
from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.pico4.lifecycle_descriptor_close import pin as pin_close,close_original
from adapters.native_feature_observation import need,integer
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.script_journey.history import MAX_RAW

PART=65536
WORK=2*PART
UNRESOLVED=[]


def digest(raw):return hashlib.sha256(raw).hexdigest()


class LifecycleCapacityPass:
    def __init__(self,raw):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
        need(type(raw) is LifecycleSourceRaw4 and raw.capacity_batches is True
            and raw.archive.state['reads']==0 and raw.namespace.lease is None)
        self.raw,self.namespace,self.lock,self.directory=raw,raw.namespace,raw.lock,raw.namespace.directory
        self.host,self.thread=host_identity(),threading.get_ident()
        self._fixed=self._original_fixed=(raw,self.namespace,self.lock,self.directory,self.host,self.thread,
            self.namespace.expanded,self.namespace._expanded)
        self.proof=self._original_proof=None;self.pending=self._original_pending=None
        self.active=self._original_active=None;self.failed=self.closed=False
        self._pending_rows=self._original_pending_rows=();self._pending_state=self._original_pending_state=None
        self.close_proof=self._original_close_proof=pin_close()
        self.close_procedure=self._original_close_procedure=(close_original,close_original.__code__)
        self.full_audits=self.reuses=0
        self.literal_costs=self._original_literal_costs=();self.literal_pending=self._original_literal_pending=()
        from adapters.pico4 import lifecycle_namespace_bill as module
        self.literal_functions=self._original_literal_functions=(module.json.loads,module.unpack,module.lifecycle_world_codec.unpack,
            module.canonical,zlib.decompressobj,base64.b64decode,lzma.LZMADecompressor)
        self.literal_codes=self._original_literal_codes=tuple(getattr(fn,'__code__',None) for fn in self.literal_functions)
        self.literal_hits=self.literal_misses=0
        self.root_costs=self._original_root_costs=();self.root_pending=self._original_root_pending=()
        self.root_hits=self.root_misses=0
        self.root_strict=self._original_root_strict=(module.strict,module.strict.__code__)
        self.root_functions=self._original_root_functions=(module.canonical_size,
            module.logical_bytes,module.decode_parts,module.lifecycle_world_codec.plain)
        self.root_codes=self._original_root_codes=tuple(getattr(fn,'__code__',None) for fn in self.root_functions)
        self.root_constants=self._original_root_constants=(module.PART,module.MAX_RAW,module.MAX_FRAMES,
            module.lifecycle_world_codec.MEMORY_LIMIT,module.lifecycle_world_codec.VERSION,
            module.lifecycle_world_codec.legacy.MAX_RAW,module.lifecycle_world_codec.legacy.MAX_PACKED,
            module.lifecycle_world_codec.legacy.MAX_FRAMES)

    def fail(self):
        self.failed=True;self.raw.failed=True
        if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)

    def identity(self):
        need(not self.failed and not self.closed and self._fixed is self._original_fixed)
        raw,namespace,lock,directory,host,thread,expanded,original_expanded=self._fixed
        need(self.raw is raw and self.namespace is namespace and self.lock is lock and self.directory is directory
            and type(self.host) is str and self.host==host and type(self.thread) is int and self.thread==thread
            and host_identity()==host and threading.get_ident()==thread
            and namespace.path is namespace._path and namespace.lock is namespace._lock is lock
            and namespace.directory is directory and raw.namespace is namespace and raw.lock is lock
            and namespace.expanded is expanded and namespace._expanded is original_expanded
            and namespace.capacity_bill is namespace._capacity_bill
            and namespace._capacity_pass is namespace._original_capacity_pass is self
            and raw._capacity_pass is raw._original_capacity_pass is self)
        self.lock.assert_held();require_directory(self.directory,self.namespace.path)
        from adapters.pico4 import lifecycle_namespace_bill as module
        current=(module.json.loads,module.unpack,module.lifecycle_world_codec.unpack,module.canonical,
            zlib.decompressobj,base64.b64decode,lzma.LZMADecompressor)
        need(self.literal_functions is self._original_literal_functions and self.literal_codes is self._original_literal_codes
            and all(fn is original for fn,original in zip(current,self.literal_functions))
            and all(getattr(fn,'__code__',None) is original for fn,original in zip(current,self.literal_codes)))
        root_current=(module.canonical_size,module.logical_bytes,module.decode_parts,
            module.lifecycle_world_codec.plain)
        constants=(module.PART,module.MAX_RAW,module.MAX_FRAMES,module.lifecycle_world_codec.MEMORY_LIMIT,
            module.lifecycle_world_codec.VERSION,module.lifecycle_world_codec.legacy.MAX_RAW,
            module.lifecycle_world_codec.legacy.MAX_PACKED,module.lifecycle_world_codec.legacy.MAX_FRAMES)
        need(self.root_functions is self._original_root_functions and self.root_codes is self._original_root_codes
            and all(fn is original for fn,original in zip(root_current,self.root_functions))
            and all(getattr(fn,'__code__',None) is code for fn,code in zip(root_current,self.root_codes))
            and self.root_constants is self._original_root_constants and constants==self.root_constants)
        self.metadata_bytes()

    def metadata_bytes(self):
        need(self.proof is self._original_proof and self.pending is self._original_pending
            and self.active is self._original_active)
        cost=WORK
        if self.proof is not None:
            need(type(self.proof) is tuple and len(self.proof)==6 and type(self.proof[0]) is int and self.proof[0]==1
                and type(self.proof[1]) is tuple and len(self.proof[1])<=4096
                and integer(self.proof[2],0,MAX_RAW) and type(self.proof[3]) is str and re.fullmatch('[0-9a-f]{64}',self.proof[3])
                and type(self.proof[4]) is tuple and len(self.proof[4])==4 and integer(self.proof[5],0,MAX_RAW))
            # All nested proof fields are exact immutable tuples/strings/ints
            # validated at actual creation, not a surviving mutable DTO.
            need(tuple(name for name,value in self.proof[4])==('decodedBytes','files','parts','storedBytes')
                and all(integer(value,0,MAX_RAW) for name,value in self.proof[4]))
            cost+=3*len(self.proof[1])*512+4096
        if self.pending is not None:
            count,rows,state=self.pending
            need(type(count) is int and 0<=count<=4096 and type(rows) is list and len(rows)<=count
                and type(state) is list and len(state)<=1)
            # Creation validates every exact immutable row. Mutable builder
            # replacement cannot inherit it: compare lengths and ELEMENT-IS.
            need(self._pending_rows is self._original_pending_rows and len(rows)==len(self._pending_rows)
                and all(current is original for current,original in zip(rows,self._pending_rows))
                and self._pending_state is self._original_pending_state
                and (not state and self._pending_state is None or len(state)==1 and state[0] is self._pending_state))
            cost+=3*count*512+4096
        need(self.literal_costs is self._original_literal_costs and type(self.literal_costs) is tuple
            and self.literal_pending is self._original_literal_pending and type(self.literal_pending) is tuple
            and self.root_costs is self._original_root_costs and type(self.root_costs) is tuple
            and self.root_pending is self._original_root_pending and type(self.root_pending) is tuple
            and self.memo_count()<=512)
        cost+=3*256*self.memo_count()
        need(cost<=MAX_RAW);return cost

    @staticmethod
    def row(value):
        need(type(value) is tuple and len(value)==3)
        name,physical,sha=value
        need(type(name) is str and 0<len(name)<=128 and '/' not in name
            and type(physical) is tuple and len(physical)==8 and all(type(v) is int for v in physical)
            and type(sha) is str and re.fullmatch('[0-9a-f]{64}',sha))
        need(canonical_size([name,list(physical),sha],512)<=512)

    def begin(self,physical):
        self.identity();need(self.pending is None and self.active is None)
        self.pending=self._original_pending=(len(physical),[],[])
        self._pending_rows=self._original_pending_rows=();self._pending_state=self._original_pending_state=None

    def record(self,name,raw,physical):
        self.identity();need(self.pending is not None and type(raw) is bytes and len(raw)<=PART)
        rows=self.pending[1];row=(name,tuple(physical),digest(raw));self.row(row)
        need(len(rows)<self.pending[0] and all(old[0]!=name for old in rows));rows.append(row)
        self._pending_rows=self._original_pending_rows=(*self._pending_rows,row)

    def expanded(self,value,size):
        self.identity();need(self.pending is not None and not self.pending[2])
        need(integer(size,0,MAX_RAW))
        state=(size,json_digest(value));self.pending[2].append(state)
        self._pending_state=self._original_pending_state=state

    def finish(self,result,physical,mutex):
        self.identity();need(self.pending is not None and self.active is None)
        count,rows,state=self.pending
        need(len(rows)==count==len(physical) and len(state)==1
            and tuple(sorted(row[0] for row in rows))==tuple(sorted(physical)))
        for name,stamp,sha in rows:need(tuple(physical[name])==stamp)
        need(type(result) is dict and set(result)=={'parts','storedBytes','decodedBytes','files'}
            and all(integer(v,0,MAX_RAW) for v in result.values()) and integer(mutex,0,MAX_RAW))
        self.proof=self._original_proof=(1,tuple(sorted(rows)),state[0][0],state[0][1],tuple(sorted(result.items())),mutex)
        self.pending=self._original_pending=None;self.full_audits+=1

    def opened(self,owner):
        self.identity();need(type(owner) is OriginalDescriptor and self.active is None)
        self.active=self._original_active=owner

    def close_pair(self,owner):
        need(self.active is self._original_active is owner and type(owner) is OriginalDescriptor
            and self.close_proof is self._original_close_proof
            and self.close_procedure is self._original_close_procedure
            and close_original is self.close_procedure[0] and close_original.__code__ is self.close_procedure[1])
        close_original(owner,self.close_proof)
        self.active=self._original_active=None

    def same_files(self):
        proof=self.proof;names,pins=self.namespace.lease;old=proof[1]
        if names!=tuple(row[0] for row in old):return False
        for (name,current),(saved,stamp,sha) in zip(pins,old):
            need(name==saved)
            if current!=stamp:
                if not (re.fullmatch(r'session-[0-9a-f]{32}\.lock',name) and stamp[5]==0
                        and current[:7]==stamp[:7] and current[7]>=stamp[7]):return False
        return True

    def current(self):
        try:
            self.identity();need(self.pending is None and self.namespace._write is None and self.active is None)
            if self.proof is None:return self.namespace()
            self.namespace.guard_lease()
            if not self.same_files():return self.namespace()
            result=dict(self.proof[4]);old_mutex=self.proof[5];current_mutex=self.namespace.metadata_bytes()
            result['decodedBytes']+=3*(current_mutex-old_mutex)
            # The original full decoded/codec/CAS bill already covers these
            # smaller read/hash/canonical windows. Charge current raw growth,
            # all retained proofs and work BEFORE another byte/hash allocation.
            need(current_mutex>=old_mutex and result['decodedBytes']+self.namespace.capacity_bill()<=MAX_RAW)
            for name,physical,sha in self.proof[1]:
                path=self.namespace.path/name;actual=tuple(signature(path.lstat()))
                if actual!=physical:
                    need(re.fullmatch(r'session-[0-9a-f]{32}\.lock',name) and physical[5]==0
                        and actual[:7]==physical[:7] and actual[7]>=physical[7])
                owner=OriginalDescriptor.__new__(OriginalDescriptor);self.opened(owner)
                OriginalDescriptor.__init__(owner,'/proc/self/fd/'+str(self.directory.fd)+'/'+name,
                    os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
                owner.require(owner.fd);before=tuple(signature(os.fstat(owner.fd)))
                need(before==actual and 0<=before[5]<=PART)
                raw=os.pread(owner.fd,PART+1,0);owner.require(owner.fd)
                need(len(raw)==before[5] and digest(raw)==sha and tuple(signature(os.fstat(owner.fd)))==before
                    and tuple(signature(path.lstat()))==before)
                self.close_pair(owner)
            value=self.namespace.expanded()  # SAME actual callback result, once.
            size=canonical_size(value,self.proof[2])
            self.namespace.guard_expanded(value,size)
            need(size==self.proof[2] and json_digest(value)==self.proof[3])
            self.namespace.guard_lease();need(self.same_files())
            require_directory(self.directory,self.namespace.path)
            self.namespace.last=dict(result)
            self.namespace._admitted_bill=self.namespace._original_budget=tuple(sorted({**result,'mutexBytes':current_mutex}.items()))
            if self.namespace.maximum is None:self.namespace.maximum=dict(result)
            else:self.namespace.maximum={key:max(self.namespace.maximum[key],value) for key,value in result.items()}
            self.reuses+=1;return result
        except BaseException:self.fail();raise

    def literal_lookup(self,value,size):
        self.identity();need(type(value) is str and integer(size,0,MAX_RAW))
        key=(digest(value.encode('utf-8')),size)
        for row in self.literal_costs:
            if row[:2]==key:self.literal_hits+=1;return key,row[2:]
        return key,None

    def literal_begin(self,key):
        self.identity()
        if self.memo_count()>=512:return None
        need(type(key) is tuple and len(key)==2 and type(key[0]) is str and re.fullmatch('[0-9a-f]{64}',key[0])
            and integer(key[1],0,MAX_RAW))
        ticket=(key,object());self.literal_pending=self._original_literal_pending=(*self.literal_pending,ticket)
        return ticket

    def literal_finish(self,ticket,cost,peak):
        self.identity();need(self.literal_pending and self.literal_pending[-1] is ticket
            and integer(cost,0,MAX_RAW) and integer(peak,cost,MAX_RAW))
        self.literal_costs=self._original_literal_costs=(*self.literal_costs,(*ticket[0],cost,peak))
        self.literal_pending=self._original_literal_pending=self.literal_pending[:-1];self.literal_misses+=1

    def root_decoder_guard(self):
        from adapters.pico4 import lifecycle_namespace_bill as module
        need(self.root_strict is self._original_root_strict
            and module.strict is self.root_strict[0] and module.strict.__code__ is self.root_strict[1])

    def memo_count(self):
        return len(self.literal_costs)+len(self.literal_pending)+len(self.root_costs)+len(self.root_pending)

    def root_lookup(self,name):
        self.identity();self.root_decoder_guard();need(self.pending is not None and type(name) is str)
        # Every row was produced by THIS full current read pass, after actual
        # original-OFD/full-eight-stat/complete-byte validation. No DTO verdict
        # or old physical identity is inherited by this numerical memo key.
        selected=[row for row in self._pending_rows if row[0]==name];need(len(selected)==1)
        row=selected[0];key=(name,row[2],row[1][5])
        for entry in self.root_costs:
            if entry[:3]==key:self.root_hits+=1;return key,entry[3:]
        return key,None

    def root_begin(self,key):
        self.identity();self.root_decoder_guard()
        if self.memo_count()>=512:return None
        need(type(key) is tuple and len(key)==3 and type(key[0]) is str and 0<len(key[0])<=128
            and key[0].isascii() and type(key[1]) is str and re.fullmatch('[0-9a-f]{64}',key[1])
            and integer(key[2],1,PART) and canonical_size([*key,MAX_RAW,MAX_RAW],256)<=256)
        ticket=(key,object());self.root_pending=self._original_root_pending=(*self.root_pending,ticket)
        return ticket

    def root_finish(self,ticket,cost,peak):
        self.identity();self.root_decoder_guard();need(self.root_pending and self.root_pending[-1] is ticket
            and integer(cost,0,MAX_RAW) and integer(peak,cost,MAX_RAW))
        self.root_costs=self._original_root_costs=(*self.root_costs,(*ticket[0],cost,peak))
        self.root_pending=self._original_root_pending=self.root_pending[:-1];self.root_misses+=1

    def close_host(self):
        if self.failed or self.active is not None or self.literal_pending or self.root_pending:return False
        self.closed=True;self.proof=self._original_proof=None;self.pending=self._original_pending=None
        self.literal_costs=self._original_literal_costs=();self.root_costs=self._original_root_costs=();return True
