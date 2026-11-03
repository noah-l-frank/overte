"""Lossless warm host-mutex metadata; never native events or source authority.

An immutable cohort stores its original seven unchanged stat fields once and
all actually observed ctimes. The order vector preserves interleaved cohorts.
Every new tuple/canonical overlap is admitted by the existing Namespace bill
before copying. This ledger creates no files and cannot resume a cold writer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
import os
import re
import stat
from typing import NamedTuple

from adapters.native_feature_observation import integer,need
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.script_journey.history import MAX_FRAMES,MAX_RAW

VERSION=2
WINDOW_ROWS=6
UINT64=(1<<64)-1
HEADER_BYTES=canonical_size(dict(lifecycleMutexLedgerVersion=VERSION,cohorts=[],order=[]))
# One bounded reconstruction window, charged even when no transition exists.
# All actual Linux stat fields accepted below fit unsigned64-bit integers.
WINDOW_BYTES=WINDOW_ROWS*canonical_size(['session-'+'f'*32+'.lock',[UINT64]*8,[UINT64]*8])


class ReceivedPair(NamedTuple):
    name: object
    before: object
    after: object


class AppendPermit(NamedTuple):
    pair: ReceivedPair
    previous: tuple
    cohort: int
    local: int
    encoded_bytes: int


@dataclass(frozen=True,slots=True)
class MutexObservations2:
    ledger: object

    def __len__(self):return self.ledger.count()
    def __iter__(self):
        # Normal source admission must not accidentally construct a complete
        # expanded observation list. Explicit bounded windows remain available.
        raise TypeError('Mutex metadata requires an explicitly bounded window')
    def __getitem__(self,index):
        if type(index) is int:
            size=len(self);index=index+size if index<0 else index
            if not 0<=index<size:raise IndexError(index)
            return self.ledger.window(index,1)[0]
        need(type(index) is slice and all(value is None or type(value) is int
            for value in (index.start,index.stop,index.step)) and index.step in (None,1))
        start,stop,_step=index.indices(len(self));return self.ledger.window(start,max(0,stop-start))


class LifecycleMutexLedger2:
    def __init__(self,namespace):
        from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
        need(type(namespace) is LifecycleNamespaceBill and namespace.mutex_layout==2)
        self.namespace=self._namespace=namespace
        # cohorts, chronological (cohort,local-transition) references, exact
        # canonical compact bytes. Every nested field is immutable.
        self.state=self._state=((),(),HEADER_BYTES)
        self.view=MutexObservations2(self);self.pending=None;self.poisoned=False;self._admitted_permit=None

    def require(self):
        owner=self.namespace
        need(owner is self._namespace and owner.mutex_layout==owner._mutex_layout==VERSION
            and owner._mutex_ledger is self and owner._original_mutex_ledger is self
            and owner.mutex_observations is owner._mutex_observations is self.view
            and owner.path is owner._path and owner.lock is owner._lock
            and self.state is self._state and type(self.state) is tuple and len(self.state)==3)

    def active(self):
        self.require();need(not self.poisoned and self.pending is None)

    def count(self):self.require();return len(self.state[1])
    def encoded_bytes(self):self.require();return self.state[2]
    def metadata_bytes(self):return self.encoded_bytes()+WINDOW_BYTES

    def window(self,start,count):
        self.require();cohorts,order,_size=self.state
        need(integer(start,0,len(order)) and integer(count,0,min(WINDOW_ROWS,len(order)-start)))
        result=[]
        for position in range(start,start+count):
            group,local=order[position];name,prefix,times=cohorts[group]
            result.append((name,(*prefix,times[local]),(*prefix,times[local+1])))
        return tuple(result)

    def observe(self,name,before,after):
        self.namespace.lock.assert_held();self.active()
        self.pending=ReceivedPair(name,before,after)
        try:
            need(type(name) is str and re.fullmatch(r'session-[0-9a-f]{32}\.lock',name) is not None
                and all(type(value) is tuple and len(value)==8 and all(integer(item,0,UINT64) for item in value)
                    for value in (before,after)) and before[:7]==after[:7] and after[7]>=before[7]
                and stat.S_ISREG(before[2]) and stat.S_IMODE(before[2])==0o600
                and before[3]==os.geteuid() and before[4]==1 and before[5]==0)
            owner=self.namespace
            need(owner.lease is owner._lease and owner.lease is not None and dict(owner.lease[1]).get(name)==before)
            cohorts,order,size=self.state
            index=next((index for index,row in enumerate(cohorts) if row[0]==name),len(cohorts))
            if index<len(cohorts):
                _name,prefix,times=cohorts[index];need(prefix==before[:7] and times[-1]==before[7]);local=len(times)-1
            else:
                need(len(cohorts)<MAX_FRAMES);local=0
            if before==after:self.pending=None;return
            if index==len(cohorts):
                # The tiny prefix has a fixed bounded representation; no new
                # ctime/order vector is allocated before the complete bill.
                prefix_size=canonical_size(dict(name=name,prefix=list(before[:7]),ctimes=[]))
                size+=prefix_size+len(str(before[7]))+1+len(str(after[7]))+(1 if cohorts else 0)
            else:size+=1+len(str(after[7]))
            size+=canonical_size([index,local])+(1 if order else 0)
            permit=AppendPermit(self.pending,self.state,index,local,size);self.pending=permit
            need(integer(size,HEADER_BYTES,MAX_RAW) and owner._admitted_bill is owner._original_budget
                and owner._admitted_bill is not None and owner.capacity_bill is owner._capacity_bill)
            budget=dict(owner._admitted_bill);raw=owner.capacity_bill();new=size+WINDOW_BYTES
            # Retained compact ledger, canonical view and old/new append
            # overlap. Reconstruction window is included before allocation.
            need(budget['decodedBytes']-3*budget['mutexBytes']+3*new+raw<=MAX_RAW)
            self._admitted_permit=permit;self.commit(permit)
        except BaseException:
            self.poisoned=True
            # The exact already-observed pair/permit remains retained even if
            # admission failed before a complete permit could be returned.
            raise

    def commit(self,permit):
        self.require();need(type(permit) is AppendPermit and self.pending is permit
            and not self.poisoned and self.state is permit.previous and self._admitted_permit is permit)
        cohorts,order,_size=self.state;pair=permit.pair
        if permit.cohort==len(cohorts):row=(pair.name,pair.before[:7],(pair.before[7],pair.after[7]))
        else:
            name,prefix,times=cohorts[permit.cohort];row=(name,prefix,(*times,pair.after[7]))
        cohorts=(*cohorts[:permit.cohort],row,*cohorts[permit.cohort+1:])
        order=(*order,(permit.cohort,permit.local))
        self.state=self._state=(cohorts,order,permit.encoded_bytes);self.pending=None;self._admitted_permit=None

    def close(self):
        try:self.require()
        except BaseException:self.poisoned=True;return False
        return not self.poisoned and self.pending is None
