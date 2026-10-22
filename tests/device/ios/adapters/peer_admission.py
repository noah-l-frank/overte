"""Read-only admission of an already prepared independent physical SDK peer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from ios.adapters.installed_code import InstalledCodeBinding
from ios.adapters.script_runtime import IOSScriptRuntime

VERSION=1


def validate(value,primary_binding):
    exact(value,{'iosPeerAdmissionVersion','binding','scope','expectedBundle','installedBefore','installedAfter','processBefore','processAfter','acquisition'})
    need(type(value['iosPeerAdmissionVersion']) is int and value['iosPeerAdmissionVersion']==VERSION);context(primary_binding);peer=context(value['binding'])
    need(peer['targetFingerprint']!=primary_binding['targetFingerprint'] and peer['sessionId']!=primary_binding['sessionId']
        and all(peer[key]==primary_binding[key] for key in ('sourceRevision','artifactSha256')))
    clock=value['acquisition'];exact(clock,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
    a,b,c,d=[clock[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')]
    need(number(a,1,1e15) and number(b,a,a+1500) and number(c,0,1e15) and number(d,c,c+1.5)
        and b-a<1500 and d-c<1.5 and abs(b-a-(d-c)*1000)<=250)
    need(same(value['installedBefore'],value['installedAfter']) and same(value['processBefore'],value['processAfter']))
    class Frozen(PrivateFeatureState):
        def read(self):return deepcopy(value['installedBefore'])
        def write(self,*_args,**_kwargs):need(False)
    forbidden=lambda *_args,**_kwargs:need(False)
    gate=InstalledCodeBinding(Frozen('/unused-read-only-peer-admission'),value['scope'],value['expectedBundle'],forbidden,forbidden,forbidden)
    record=gate.record();need(record is not None and record['phase']=='bound' and record['process']==value['processBefore']
        and record['process']['foreground'] is True and str(record['process']['pid'])==peer['processIdentity']
        and same(dict(value['scope'],processIdentity=peer['processIdentity']),peer))
    return deepcopy(peer)


def admit_existing_peer(runtime,selector,primary_binding,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
    need(isinstance(runtime,IOSScriptRuntime) and callable(epoch_ms) and callable(monotonic));context(primary_binding)
    started,epoch=monotonic(),epoch_ms();need(number(started,0,1e15) and number(epoch,1,1e15))
    client,session,state,target,scope=runtime._existing(selector)
    gate=runtime.adapter._binding(selector,client,session,state,target)
    before=deepcopy(gate.record());need(before is not None and before['phase']=='bound')
    process_before=deepcopy(gate.continuity());process_after=deepcopy(gate.continuity());after=deepcopy(gate.record())
    _client2,session2,state2,_target2,scope2=runtime._existing(selector)
    need(session==session2 and same(state,state2) and same(scope,scope2))
    value=dict(iosPeerAdmissionVersion=VERSION,binding=dict(scope,processIdentity=str(process_after['pid'])),scope=deepcopy(scope),
        expectedBundle=deepcopy(gate.bundle),installedBefore=before,installedAfter=after,processBefore=process_before,processAfter=process_after,
        acquisition=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=epoch_ms(),hostBeforeMonotonic=started,hostAfterMonotonic=monotonic()))
    validate(value,primary_binding);return value
