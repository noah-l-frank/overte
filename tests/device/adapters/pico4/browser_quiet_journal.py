"""Immutable original browser quiet frames beneath a bounded parent reference."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest,json_digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_journey.history import canonical,same
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.browser_quiet import frame,validate
from adapters.native_web_runtime import continuity as runtime_advance
from adapters.pico4.browser_source import fixture,continuity as browser_advance
from feature_journeys.contract import identifier

VERSION=1


class PicoBrowserQuietJournal:
    def __init__(self,store,lock,run,url,token,binding,reference):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));lock.assert_held()
        fixture(run,url);identifier(token);context(binding)
        self.store,self.lock=store,lock
        self.scope=dict(picoBrowserQuietJournalVersion=VERSION,runId=run,fixtureUrl=url,ownerToken=token,binding=deepcopy(binding))
        self.run,self.url,self.token,self.pid=run,url,token,int(binding['processIdentity'].split(':',1)[0])
        self.chunks=ChatSourceChunks(store,self.scope);self.disk=store.read();self.remember_value(None);self.failed=False
        self.legacy=reference is not None and 'browserQuietVersion' in reference
        if self.legacy:
            validate(reference,run,url,token,self.pid,retired=False);self.remember_value(reference)
        if self.disk is None:
            need(reference is None or self.legacy);self.chunks.inventory(0)
        else:
            exact(self.disk,set(self.scope)|{'phase','revision','chunks'})
            need(all(same(self.disk[key],value) for key,value in self.scope.items()) and self.disk['phase']=='ready')
            exact(reference,{'browserQuietReferenceVersion','sha256'})
            need(type(reference['browserQuietReferenceVersion']) is int and reference['browserQuietReferenceVersion']==VERSION
                and reference['sha256']==digest(self.disk))
            rows=self.chunks.load(self.disk['chunks'])
            need(1<=len(rows)<=64 and integer(self.disk['revision']) and self.disk['revision']==2*len(rows))
            value=dict(browserQuietVersion=1,frames=rows,complete=False)
            first,last=rows[0],rows[-1]
            a=frame(first,run,url,token,self.pid,retired=False);b=frame(last,run,url,token,self.pid,retired=False)
            value['complete']=len(rows)>=3 and last['host']-first['host']>=3 and all(y-x>=3000 for x,y in zip(a,b))
            validate(value,run,url,token,self.pid,retired=False);self.remember_value(value)
        self.value_digest=self.cache_digest()
    def remember_value(self,value):
        # Only a new, fully admitted original is frozen here. No mutable DTO
        # or caller inspection copy can become a cached validation authority.
        self._value_sha=self._sealed_value_sha=json_digest(value)
        self._value_bytes=self._sealed_value_bytes=None if value is None else canonical(value)

    def immutable_value(self):
        need(self._value_bytes is self._sealed_value_bytes and self._value_sha is self._sealed_value_sha
            and type(self._value_sha) is str and (self._value_bytes is None or type(self._value_bytes) is bytes))

    @property
    def value(self):
        self.immutable_value()
        return None if self._value_bytes is None else json.loads(self._value_bytes)

    def cache_digest(self):
        self.immutable_value();return json_digest(dict(scope=self.scope,valueSha256=self._value_sha))
    def migrate(self):
        """Explicitly copy validated legacy originals; never a device query/input."""
        self.lock.assert_held()
        if not self.legacy:return
        need(self.disk is None);original=self.value;self.remember_value(None);self.value_digest=self.cache_digest();self.legacy=False
        for row in original['frames']:
            self.begin();self.finish(row['browser'],row['runtime'],row['host'])
        need(same(self.value,original))

    def reference(self):
        self.lock.assert_held();self.verify();need(not self.legacy and self.disk is not None and self.disk['phase']=='ready')
        return dict(browserQuietReferenceVersion=VERSION,sha256=digest(self.disk))

    def verify(self):
        self.lock.assert_held();need(not self.failed and same(self.store.read(),self.disk)
            and self.cache_digest()==self.value_digest);self.chunks.verify()

    def write(self,phase,chunks):
        self.verify();value={**self.scope,'phase':phase,'revision':1 if self.disk is None else self.disk['revision']+1,'chunks':deepcopy(chunks)}
        self.store.write(value,self.disk);need(same(self.store.read(),value));self.disk=deepcopy(value)

    def begin(self):
        need(not self.failed and (self.disk is None or self.disk['phase']=='ready')
            and (self.value is None or len(self.value['frames'])<64))
        try:self.write('reading',[] if self.disk is None else self.disk['chunks'])
        except Exception:self.failed=True;raise

    def finish(self,browser,runtime,host):
        need(not self.failed and self.disk is not None and self.disk['phase']=='reading')
        try:
            self.verify();row=dict(browser=deepcopy(browser),runtime=deepcopy(runtime),host=host)
            clocks=frame(row,self.run,self.url,self.token,self.pid,retired=False)
            rows=[] if self.value is None else list(self.value['frames'])
            if rows:
                previous=rows[-1];before=frame(previous,self.run,self.url,self.token,self.pid,retired=False)
                browser_advance(previous['browser'],row['browser']);runtime_advance(previous['runtime'],row['runtime'],self.pid,self.url)
                need(0<host-previous['host']<=.5 and all(0<b-a<=500 for a,b in zip(before,clocks)))
            rows.append(row);first=rows[0];a=frame(first,self.run,self.url,self.token,self.pid,retired=False)
            value=dict(browserQuietVersion=1,frames=rows,complete=len(rows)>=3 and host-first['host']>=3
                and all(b-x>=3000 for x,b in zip(a,clocks)))
            manifest=self.chunks.append(row,self.disk['chunks']);self.write('ready',manifest)
            self.remember_value(value);self.value_digest=self.cache_digest();return self.reference()
        except Exception:self.failed=True;raise
