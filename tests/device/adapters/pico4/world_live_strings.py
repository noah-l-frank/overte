# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""One census-only immutable-string extent counter, never source authority.

Exact string objects are held until this short counter returns to prevent id
recycling. Mutable containers and every reference/node retain their full old
charge. Equal-new strings are separate; after1024 identities or depth16, the
original full canonical/node bill is used, no eviction/resealing/grammar cap.
"""
from adapters.native_feature_observation import need
from adapters.pico4.lifecycle_namespace_bill import canonical_size
LIMIT=16777216
CAPACITY=1024
DEPTH=16

def nodes(item):
    kind=type(item)
    if kind is dict:return 1+sum(1+nodes(v) for v in item.values())
    if kind is list:return 1+sum(nodes(v) for v in item)
    return 1

class WorldLiveStrings1:
    def __init__(self):
        self.originals={};self.active=set();self.hits=0;self.fallbacks=0
    def size(self,item,depth=0):
        kind=type(item)
        if kind is bytes:return len(item)+256
        if kind is tuple:return 64+8*len(item)+sum(self.size(v,depth+1) for v in item)
        if kind is str:
            key=id(item);old=self.originals.get(key)
            if old is item:
                self.hits+=1;return 256  # reference/header metadata stays charged
            if len(self.originals)<CAPACITY:self.originals[key]=item
            else:self.fallbacks+=1
            return 4*canonical_size(item,LIMIT)+256
        if kind is dict or kind is list:
            if depth>=DEPTH:
                self.fallbacks+=1
                return 4*canonical_size(item,LIMIT)+256*nodes(item)
            need(id(item) not in self.active)
            if kind is dict:need(all(type(k) is str for k in item))
            self.active.add(id(item))
            try:
                punctuation=2+max(0,len(item)-1)+(len(item) if kind is dict else 0)
                value=4*punctuation+256
                if kind is dict:
                    for k,v in item.items():value+=self.size(k,depth+1)+self.size(v,depth+1)
                else:
                    for v in item:value+=self.size(v,depth+1)
                return value
            finally:self.active.remove(id(item))
        return 4*canonical_size(item,LIMIT)+256

VERSION=1
