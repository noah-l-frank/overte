"""Neutral installed-candidate and independent OS retirement primitives.

These three extracted readers preserve the original Graphics guards. No helper
can authorize Stop, fabricate native absence or construct a new SDK session.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same

def admitted_source(runtime,selector,binding):
    """Actual admitted installed-code/process source before final stop."""
    from copy import deepcopy
    from ios.adapters.installed_code import source as validate_source
    expected=context(binding);client,session,state,target,scope=runtime._existing(selector)
    need(same(scope,{k:v for k,v in expected.items() if k!='processIdentity'}))
    gate=runtime.adapter._binding(selector,client,session,state,target);gate.verify();actual=gate.continuity()
    record=gate.record();original=validate_source(gate.process_source())
    need(record is not None and record['phase']=='bound' and same(record['scope'],scope)
        and actual['pid']==record['process']['pid']==int(expected['processIdentity']) and same(record['source'],original))
    return deepcopy(original)


def mark_stopped(runtime,selector,binding,source):
    from ios.adapters.installed_code import source as validate_source
    expected=context(binding);client,session,state,target,scope=runtime._existing(selector)
    need(same(scope,{k:v for k,v in expected.items() if k!='processIdentity'}))
    gate=runtime.adapter._binding(selector,client,session,state,target);record=gate.record()
    need(record is not None and record['phase'] in ('retiring','retired') and record['process']['pid']==int(expected['processIdentity'])
        and same(record['scope'],scope) and same(record['source'],validate_source(source)) and same(gate.process_source(),source))
    if record['phase']=='retiring':gate.finish_retirement()
    gate.retired_absence();runtime.adapter.reset_launch_state(selector,state)


def retired_process_observer(runtime,selector,binding,source):
    """Existing SDK only; no foreground UI/native-byte read after app stop."""
    from copy import deepcopy
    from ios.adapters.installed_code import source as validate_source
    from ios.adapters.retired_process import IOSRetiredProcess
    expected=deepcopy(context(binding));validate_source(source)
    client,session,state,target,scope=runtime._existing(selector)
    need(same(scope,{k:v for k,v in expected.items() if k!='processIdentity'}))
    gate=runtime.adapter._binding(selector,client,session,state,target)
    def guard():
        runtime.adapter._candidate_guard(complete=True)
        need(same(runtime.adapter.read_session(selector),state) and runtime.adapter._scope(selector,session,state,target)==scope)
        record=gate.record();need(record is not None and record['phase'] in ('retiring','retired')
             and record['process']['pid']==int(expected['processIdentity']) and same(record['scope'],scope)
             and same(validate_source(gate.process_source()),source) and same(record['source'],source))
    guard()
    return IOSRetiredProcess(lambda query:client.execute(session,'mobile: overteRetiredProcessInfo',query),
                             guard,target['appId'],int(expected['processIdentity']),source)
