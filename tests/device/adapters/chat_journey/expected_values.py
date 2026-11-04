"""Replace redundant canonical expected copies within their original memory credit.

No current file/source verdict is cached. Every use compares the original
expected object and complete current type/shape/key/scalar identities. Actual
original bytes, stamps, descriptors and directory windows remain independent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from adapters.json_original_value import capture,dimensions,scratch_bound,matches_original_refs
from adapters.native_feature_observation import need


class CatalogExpectedValues:
    """One warm already admitted catalog; no second canonical-entry array."""
    def __init__(self,catalog):
        self.catalog=catalog
        self.original_bytes=sum(len(entry[3]) for entry in self.entries)
        self.canonical_bytes=self.original_bytes;self.metadata=0;self.sealed=0;self.failed=False
        self.maximum=max((len(entry[3]) for entry in self.entries),default=0)
        self.original_workspace=2*self.maximum
        self.tuple_scratch=24*len(self.entries)+8192
        self.construction_highwater=self.original_bytes

    @property
    def entries(self):return self.catalog._json_originals

    def freeze(self):
        tried=bytearray(len(self.entries))
        while True:
            index=-1;largest=-1
            for current in range(len(self.entries)):
                stored=self.entries[current][3]
                if not tried[current] and type(stored) is bytes and len(stored)>largest:
                    index=current;largest=len(stored)
            stored=None
            if index<0:break
            tried[index]=1
            available=(self.original_bytes+self.original_workspace-self.canonical_bytes-self.metadata
                -self.tuple_scratch-len(tried))
            if available<scratch_bound(16):continue
            old=self.entries[index][3];value=self.entries[index][1]['expected'];old_size=len(old)
            plan=dimensions(value,max_depth=16)
            if plan is None or plan[3]+256>old_size or plan[4]>available:continue
            prospective=self.canonical_bytes+self.metadata+self.tuple_scratch+len(tried)+plan[4]
            need(prospective<=self.original_bytes+self.original_workspace)
            result=capture(value,capacity=available,max_depth=16)
            if result is None:continue
            seal,resident,_peak=result
            need(matches_original_refs(value,seal))
            capsule=(value,seal,hashlib.sha256(old).hexdigest(),resident+256)
            label,row,raw,_old=self.entries[index]
            entry=(label,row,raw,capsule)
            replacement=self.entries[:index]+(entry,)+self.entries[index+1:]
            self.catalog._json_originals=self.catalog._sealed_json_originals=replacement
            # Drop every local old-canonical holder BEFORE releasing its credit.
            old=_old=result=entry=replacement=None
            self.canonical_bytes-=old_size;self.metadata+=resident+256;self.sealed+=1
            self.construction_highwater=max(self.construction_highwater,prospective)
        return self.summary()

    def verify(self,index,value):
        need(not self.failed)
        try:
            stored=self.entries[index][3]
            if type(stored) is bytes:
                from adapters.chat_journey.source_chunks import json_digest
                need(json_digest(value)==hashlib.sha256(stored).hexdigest())
                return hashlib.sha256(stored).hexdigest()
            need(type(stored) is tuple and len(stored)==4 and value is stored[0]
                and matches_original_refs(value,stored[1]))
            return stored[2]
        except BaseException:self.failed=True;raise

    def summary(self):
        return dict(rows=len(self.entries),sealed=self.sealed,originalCanonicalBytes=self.original_bytes,
            remainingCanonicalBytes=self.canonical_bytes,residentSealMetadata=self.metadata,
            releasedCanonicalCredit=self.original_bytes-self.canonical_bytes-self.metadata,
            originalTemporaryWorkspace=self.original_workspace,constructionHighwater=self.construction_highwater)
