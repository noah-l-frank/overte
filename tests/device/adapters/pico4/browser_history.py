"""Complete original browser transactions, using the shared immutable chunks.

This is retained historical evidence, never a transport or a fresh observation.
Interrupted reads/publications retain their original ownership and cannot replay.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json

from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import MAX_FRAMES,canonical,same
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1


class PicoBrowserHistory:
    def __init__(self,store,lock,scope,validate):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(validate))
        lock.assert_held();self.store,self.lock,self.validate=store,lock,validate
        self.scope=dict(picoBrowserHistoryVersion=VERSION,**deepcopy(scope))
        self.disk=store.read();self.chunks=ChatSourceChunks(store,self.scope)
        self._rows=();self._row_hashes=();self._sealed_rows=self._rows;self._sealed_hashes=self._row_hashes
        self.last=None;self.publication=None;self.failed=False
        self.nonces={key:set() for key in ('feature','browser','runtime','diagnostic','phase')}
        if self.disk is None:self.chunks.inventory(0)
        else:
            exact(self.disk,set(self.scope)|{'phase','revision','chunks','intent'})
            need(all(same(self.disk[key],value) for key,value in self.scope.items())
                and self.disk['phase']=='ready' and self.disk['intent'] is None)
            rows=self.chunks.load(self.disk['chunks'])
            need(integer(self.disk['revision']) and self.disk['revision']==2*len(rows))
            for row in rows:self.admit(row)
        self.cached=self.cache_digest()

    def cache_digest(self):
        return digest(dict(scope=self.scope,rows=self._row_hashes,last=self.last,publication=self.publication,
            nonces={key:sorted(value) for key,value in self.nonces.items()}))

    @property
    def rows(self):
        """Copies for archival inspection; the admitted raw prefix stays immutable."""
        return [json.loads(raw) for raw in self._rows]

    def verify(self):
        self.lock.assert_held();need(not self.failed and self._rows is self._sealed_rows and self._row_hashes is self._sealed_hashes
            and same(self.store.read(),self.disk) and self.cache_digest()==self.cached)
        self.chunks.verify()

    def matches(self,state):
        self.verify()
        if self.last is None:need(state['sequence']==0 and state['last'] is None and state['publication'] is None)
        else:
            need(same(state['last'],self.last['sample']) and state['sequence']==self.last['sample']['sequence']
                and same(state['native'],self.last['native']) and same(state['runtime'],self.last['runtime'])
                and same(state['browser'],self.last['browser']) and same(state['phase'],self.last['phaseBefore'])
                and same(state['publication'],self.publication))

    def write(self,phase,chunks,intent):
        self.verify();value={**self.scope,'phase':phase,'revision':1 if self.disk is None else self.disk['revision']+1,
            'chunks':deepcopy(chunks),'intent':deepcopy(intent)}
        self.store.write(value,self.disk);need(same(self.store.read(),value));self.disk=deepcopy(value)

    def begin(self,event,sequence):
        self.verify();need(event in ('sample','publication-intent','publication-accepted') and integer(sequence,1)
            and (self.disk is None or self.disk['phase']=='ready') and len(self._rows)<MAX_FRAMES)
        expected=1 if self.last is None else self.last['sample']['sequence']+(event=='sample')
        need(sequence==expected)
        if event=='sample':need(self.publication is None or self.publication['phase']=='accepted')
        else:
            need(self.scope['role']=='actor' and self.last is not None)
            need(self.publication is None if event=='publication-intent' else
                self.publication is not None and self.publication['phase']=='issued')
        try:self.write('reading',[] if self.disk is None else self.disk['chunks'],dict(event=event,sequence=sequence))
        except Exception:self.failed=True;raise

    def admit(self,row):
        exact(row,{'event','sequence','original'})
        event,sequence,original=row['event'],row['sequence'],row['original']
        need(event in ('sample','publication-intent','publication-accepted') and integer(sequence,1))
        if event=='sample':
            need(sequence==(1 if self.last is None else self.last['sample']['sequence']+1)
                and (self.publication is None or self.publication['phase']=='accepted'))
            self.validate(original,self.last)
            need(original['sample']['sequence']==sequence)
            queries={'feature':[original[key]['requestId'] for key in ('nativeBefore','nativeAfter')],
                'browser':[original['native']['commandId']],'runtime':[original['runtime']['commandId']],
                'phase':[original[key]['requestId'] for key in ('phaseBefore','phaseAfter')],
                'diagnostic':[original['diagnostic']['requestId']] if 'requestId' in original['diagnostic'] else []}
            for key,values in queries.items():
                need(len(set(values))==len(values) and not self.nonces[key].intersection(values))
                self.nonces[key].update(values)
            self.last=deepcopy(original);self.publication=None
        else:
            from feature_journeys.witness import projection
            need(self.scope['role']=='actor' and self.last is not None and sequence==self.last['sample']['sequence'])
            exact(original,{'payload','ack'})
            payload=original['payload'];exact(payload,{'ticket','actor','actorSequence','capturedEpochMs','facts'})
            need(payload==dict(ticket=self.last['phaseBefore']['activations'][-1]['ticket'],actor='owned-observer',
                actorSequence=sequence,capturedEpochMs=self.last['sample']['capturedEpochMs'],
                facts=projection('tablet-web',self.last['sample']['state'])))
            if event=='publication-intent':need(self.publication is None and original['ack'] is None)
            else:need(self.publication is not None and self.publication['phase']=='issued'
                and same(self.publication['payload'],payload) and same(original['ack'],{}))
            self.publication=dict(phase='issued' if event=='publication-intent' else 'accepted',payload=deepcopy(payload))
        # bytes and tuples cannot be changed in place. Warm verification checks
        # their admitted identities, hashes and the complete physical inventory;
        # cold construction still parses and validates every original source.
        self._rows=self._rows+(canonical(row),);self._row_hashes=self._row_hashes+(digest(row),)
        self._sealed_rows,self._sealed_hashes=self._rows,self._row_hashes

    def finish(self,original):
        try:
            self.verify();need(self.disk is not None and self.disk['phase']=='reading')
            row={**self.disk['intent'],'original':deepcopy(original)}
            self.admit(row);self.cached=self.cache_digest()
            chunks=self.chunks.append(row,self.disk['chunks']);self.write('ready',chunks,None)
            self.verify()
        except Exception:self.failed=True;raise
