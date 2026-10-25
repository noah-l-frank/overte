"""SDK-free canonical verification of a completed Avatar terminal finish."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,unpack
from feature_journeys import terminal
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_ended_archive import verify as ended_originals


def verify(flow,call,result):
    need(type(flow) is IOSAvatarFeature and flow.role=='primary')
    call=terminal.arguments('avatar-people',call);terminal.result('avatar-people',result)
    need(call['runId']==flow.run and call['stage']==result['stage']=='finish' and same(call['seal'],result['end']['seal']))
    with flow.held(paired=True):
        flow.load();need(flow.state is not None and flow.state['phase']=='terminal-ready')
        path=flow.store.path.with_name('ios-avatar-primary-'+flow.run+'-terminal.json');value=PrivateFeatureState(path).read()
        need(value is not None)
        rows=unpack(value['payload'])
        need(len(rows)==1 and same(rows[0]['end'],result['end']) and same(rows[0]['seal'],call['seal']))
        binding=ended_originals(flow.runtime.adapter,flow.selector,deepcopy(flow.previous),value,held_locks=flow.locks)
        need(same(binding,flow.state['bindings']['primary']) and same(PrivateFeatureState(path).read(),value))
    return deepcopy(result)
