"""Read-only admission of another observer of one existing physical Tablet.

This is SDK/candidate continuity metadata. It creates no session, installed-code
verification query, native-current surface fact, second app Stop or SDK delete.
Actual independent worker/query/phase publication is qualified separately.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from ios.adapters.installed_code import InstalledCodeBinding
from ios.adapters.script_runtime import IOSScriptRuntime

VERSION=2
READS=(1,2)


def installed_forward(before,after):
    """Same actual installation/process; only verified observation advances."""
    need(type(before) is dict and type(after) is dict and set(before)==set(after)
        and all(same(before[key],after[key]) for key in before if key!='observation'))
    from ios.adapters.bundle_observation import validate as bundle_original
    for record in (before,after):
        packet=record['observation'];bundle_original(packet,dict(schemaVersion=1,action='ios-bundle-observe',commandId=packet['commandId']),record['process']['pid'])
        need(packet['status']=='ready')
    a,b=before['observation'],after['observation']
    need(all(same(a[key],b[key]) for key in ('instance','processId','preparedEpochMs','bundle','status','bundleObservationVersion')))
    if a['sequence']==b['sequence']:need(same(a,b))
    else:need(b['sequence']>a['sequence'] and b['capturedEpochMs']>=a['capturedEpochMs'] and b['commandId']!=a['commandId'])
    return deepcopy(after)


def follows(previous,current,binding):
    """Original bootstrap and new CLI admission share one native lifetime."""
    validate(previous,binding);validate(current,binding)
    need(all(same(previous[key],current[key]) for key in ('binding','scope','expectedBundle','processBefore','processAfter')))
    installed_forward(previous['installedAfter'],current['installedBefore'])
    return deepcopy(current)


def validate(value,physical_binding):
    exact(value,{'tabletWebObserverAdmissionVersion','binding','scope','expectedBundle','installedBefore','installedAfter',
        'processBefore','processAfter','hostProcessId','acquisition'})
    need(type(value['tabletWebObserverAdmissionVersion']) is int and value['tabletWebObserverAdmissionVersion'] in READS
        and integer(value['hostProcessId'],1))
    context(physical_binding);observed=context(value['binding']);need(same(observed,physical_binding))
    clock=value['acquisition'];exact(clock,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
    a,b,c,d=[clock[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')]
    need(number(a,1,1e15) and number(b,a,a+1500) and number(c,0,1e15) and number(d,c,c+1.5)
        and b-a<1500 and d-c<1.5 and abs(b-a-(d-c)*1000)<=250)
    need(same(value['processBefore'],value['processAfter']))
    if value['tabletWebObserverAdmissionVersion']==1:need(same(value['installedBefore'],value['installedAfter']))
    class Frozen(PrivateFeatureState):
        def read(self):return deepcopy(value['installedBefore'])
        def write(self,*_args,**_kwargs):need(False)
    forbidden=lambda *_args,**_kwargs:need(False)
    for field in ('installedBefore','installedAfter'):
        class Actual(Frozen):
            def read(self):return deepcopy(value[field])
        gate=InstalledCodeBinding(Actual('/unused-tablet-observer-admission'),value['scope'],value['expectedBundle'],forbidden,forbidden,forbidden)
        record=gate.record();need(record is not None and record['phase']=='bound' and record['process']==value['processBefore']
            and record['process']['foreground'] is True and str(record['process']['pid'])==observed['processIdentity']
            and same(dict(value['scope'],processIdentity=observed['processIdentity']),observed))
    if value['tabletWebObserverAdmissionVersion']>=2:installed_forward(value['installedBefore'],value['installedAfter'])
    return deepcopy(observed)


def admit_existing_tablet_observer(runtime,selector,physical_binding,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
    """Use actual already-prepared physical binding, never a replacement target.

    The enclosing run must retain the genuine prepared Primary binding. This
    function independently reads existing SDK/process/source records; it does
    not qualify the caller's expectation as a fresh native source observation.
    """
    need(isinstance(runtime,IOSScriptRuntime) and callable(epoch_ms) and callable(monotonic));context(physical_binding)
    started,epoch=monotonic(),epoch_ms();need(number(started,0,1e15) and number(epoch,1,1e15))
    client,session,state,target,scope=runtime._existing(selector)
    gate=runtime.adapter._binding(selector,client,session,state,target)
    before=deepcopy(gate.record());need(before is not None and before['phase']=='bound')
    process_before=deepcopy(gate.continuity());process_after=deepcopy(gate.continuity());after=deepcopy(gate.record())
    _client2,session2,state2,_target2,scope2=runtime._existing(selector)
    need(session==session2 and same(state,state2) and same(scope,scope2))
    value=dict(tabletWebObserverAdmissionVersion=VERSION,binding=dict(scope,processIdentity=str(process_after['pid'])),scope=deepcopy(scope),
        expectedBundle=deepcopy(gate.bundle),installedBefore=before,installedAfter=after,processBefore=process_before,processAfter=process_after,
        hostProcessId=os.getpid(),acquisition=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=epoch_ms(),hostBeforeMonotonic=started,hostAfterMonotonic=monotonic()))
    validate(value,physical_binding);return value
