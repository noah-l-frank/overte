"""Immutable admitted Chat JSON originals; never an observation or file owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json

from adapters.chat_journey.observation_cursor import plain
from adapters.native_feature_observation import integer,need
from adapters.script_journey.history import canonical,MAX_FRAMES,MAX_RAW

VERSION=1


class ChatOriginalMemory:
    """Only the admitting live reader may append already validated originals.

    This object has no restore/acquire/query operation. Inspection returns new
    JSON values; all admitted bytes and their pinned tuples stay immutable.
    """
    def __init__(self,scope):
        need(type(scope) is dict);plain(scope);self.scope=canonical(scope);self._scope=self.scope
        self.scope_sha=hashlib.sha256(self.scope).hexdigest()
        self.raws=self._raws=();self.hashes=self._hashes=();self.raw_bytes=2

    def _identities(self):
        need(type(self.scope) is bytes and self.scope is self._scope
            and type(self.scope_sha) is str and hashlib.sha256(self.scope).hexdigest()==self.scope_sha
            and type(self.raws) is tuple and self.raws is self._raws
            and type(self.hashes) is tuple and self.hashes is self._hashes
            and len(self.raws)==len(self.hashes)<=MAX_FRAMES and type(self.raw_bytes) is int)

    def control(self,scope):
        self._identities();need(type(scope) is dict);plain(scope);need(canonical(scope)==self.scope)
        total=2
        for index,(raw,sha) in enumerate(zip(self.raws,self.hashes)):
            need(type(raw) is bytes and type(sha) is str and hashlib.sha256(raw).hexdigest()==sha)
            total+=len(raw)+(1 if index else 0)
        need(total==self.raw_bytes<=MAX_RAW)
        return dict(version=VERSION,scopeSha256=self.scope_sha,rows=list(self.hashes),rawBytes=total)

    def count(self):
        self._identities();return len(self.raws)

    def row(self,index):
        self._identities();need(integer(index,0,len(self.raws)-1))
        raw,sha=self.raws[index],self.hashes[index]
        need(type(raw) is bytes and type(sha) is str and hashlib.sha256(raw).hexdigest()==sha)
        return json.loads(raw)

    def inspect(self):
        return [self.row(index) for index in range(self.count())]

    def append(self,value,scope):
        self.control(scope);plain(value);raw=canonical(value)
        total=self.raw_bytes+len(raw)+(1 if self.raws else 0)
        need(len(self.raws)<MAX_FRAMES and total<=MAX_RAW)
        self.raws=self.raws+(raw,);self.hashes=self.hashes+(hashlib.sha256(raw).hexdigest(),)
        self._raws,self._hashes=self.raws,self.hashes;self.raw_bytes=total
        self.control(scope)
