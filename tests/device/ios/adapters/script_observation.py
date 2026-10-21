"""Durable host/native clock admission around five new iOS Script originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import NativeClockAcquisition, validate_join
from adapters.native_feature_observation import exact, integer, need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.observation import ScriptObservation

VERSION=1
FIELDS=(('execution','capturedEpochMs'),('ui','capturedEpochMs'),('service','sampleEpochMs'),
        ('lifecycle','capturedEpochMs'),('files','capturedEpochMs'))


class IOSScriptObservation:
    def __init__(self,inner,native,history_store,store,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(inner,ScriptObservation) and isinstance(store,PrivateFeatureState)
             and isinstance(history_store,PrivateFeatureState) and native.ios is True)
        self.inner,self.native,self.history_store,self.store=inner,native,history_store,store
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.previous=store.read();self.last=None
        if self.previous is not None:
            exact(self.previous,{'iosScriptClockVersion','binding','runId','role','phase','payload'})
            need(type(self.previous['iosScriptClockVersion']) is int and self.previous['iosScriptClockVersion']==VERSION
                 and same(self.previous['binding'],inner.binding) and self.previous['runId']==inner.run
                 and self.previous['role']==inner.role and self.previous['phase']=='ready')
            rows=unpack(self.previous['payload']);need(len(rows)==1);self.last=rows[0]
            exact(self.last,{'sequence','join'})
            need(integer(self.last['sequence'],1) and self.last['sequence']==inner.state['sequence'])
            history=history_store.read();need(type(history) is dict and history['phase']=='ready')
            frames=unpack(history['transcript']);need(bool(frames))
            frame=frames[-1]
            originals={name:frame[name] for name in ('execution','ui','service','lifecycle')}
            originals['files']=inner.state['fileObservation']
            validate_join(self.last['join'],originals)

    def _save(self,value):
        self.inner.lock.assert_held();need(same(self.store.read(),self.previous))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def read(self,ticket,after_epoch,*,after_sequence=None,native_action_epoch=None):
        with self.inner.lock.held():
            need(integer(after_epoch,1) and (self.previous is None or self.previous['phase']=='ready'))
            pending=dict(iosScriptClockVersion=VERSION,binding=deepcopy(self.inner.binding),runId=self.inner.run,
                role=self.inner.role,phase='reading',payload=pack([] if self.last is None else [self.last]))
            # The nonce fence is itself an acquisition; persist uncertainty first.
            self._save(pending)
            window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            native_after=window.begin(after_epoch)
            if self.last is not None:
                before=window.started['nativeBefore'];old=self.last['join']['nativeAfter']
                need(before['instance']==old['instance'] and before['processId']==old['processId']
                     and before['sequence']>old['sequence'] and before['capturedEpochMs']>=old['capturedEpochMs']
                     and all(before['lifecycle'][key]>=count for key,count in old['lifecycle'].items())
                     and window.started['hostBeforeEpochMs']>=self.last['join']['hostAfterEpochMs'])
            # Persistent native callbacks belong after the original input
            # barrier, not after every later read. The clock join independently
            # requires all newly acquired envelopes after this fresh fence.
            causal_after=native_after if native_action_epoch is None else native_action_epoch
            need(integer(causal_after,1) and causal_after<=native_after)
            actual=self.inner.read(ticket,causal_after,after_sequence=after_sequence)
            originals={name:actual['sources'][name] for name in ('execution','ui','service','lifecycle')}
            originals['files']=self.inner.state['fileObservation']
            join=window.finish(originals,FIELDS)
            self.last=dict(sequence=actual['sequence'],join=join)
            self._save(dict(pending,phase='ready',payload=pack([self.last])))
            # Public acquisition time is separate from every untouched native
            # source and from the private native measurement clock.
            return deepcopy(dict(actual,clockJoin=join,hostCapturedEpochMs=int(join['hostBeforeEpochMs'])))
