"""SDK/candidate ownership checks without recursively issuing SDK queries.

This metadata guard complements the existing actual live admission checks; it
supplies no process observation, input permission or native freshness by itself.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from ios.adapters.installed_code import cleanup_record


def guard(adapter,selector,source):
    binding=deepcopy(context(source['binding']));scope={key:value for key,value in binding.items() if key!='processIdentity'}
    session=binding['sessionId'];pid=int(binding['processIdentity'])
    gate=adapter._binding(selector,source['client'],session,source['state'],source['target'])
    accepted=deepcopy(gate.record());need(accepted is not None and accepted['phase']=='bound' and accepted['process']['pid']==pid)
    def check():
        nonlocal accepted
        adapter._candidate_guard();sdk=adapter.read_session(selector)
        need(type(sdk) is dict and sdk.get('sessionId')==session
            and sdk.get('processIdentity') in (None,binding['processIdentity']))
        target=adapter._target(selector)
        need(same(adapter._scope(selector,session,sdk,target),scope))
        actual=adapter._binding_store(selector).read();need(actual is not None)
        validated=cleanup_record(accepted,actual)
        need(validated['phase']=='bound' and validated['process']['pid']==pid)
        accepted=deepcopy(validated);return True
    check();return check
