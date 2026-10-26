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


def retire_roles(flow):
    from ios.adapters.avatar_metadata_retirement import retire_existing
    for selector in flow.selectors.values():
        need(retire_existing(flow.runtime,selector,None)=={'cleaned':True})


def verify_failed_cleanup(flow,call,result):
    """A failed preparation has its own typed end, never a successful Scene."""
    if type(result) is not dict or result.get('status')!='failed':return False
    from feature_journeys.contract import arguments
    from ios.adapters.avatar_failed_preparation import AvatarFailedPreparation
    need(type(flow) is IOSAvatarFeature and flow.role=='primary')
    call=arguments('feature.avatar-people.cleanup',call);need(call['runId']==flow.run)
    with flow.held(paired=True):
        flow.load();need(flow.state is not None and flow.state['phase'] in ('preparing','ready'))
        store=PrivateFeatureState(flow.store.path.with_name('ios-avatar-primary-'+flow.run+'-failed-preparation.json'))
        value=store.read();need(value is not None)
        actual=AvatarFailedPreparation.archive(flow,value).original_result()
        need(same(actual,result) and same(store.read(),value))
    retire_roles(flow);return True


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
    # Only the full typed end above permits metadata CAS. Neither role needs
    # another SDK GET/DELETE or process input after its original SDK absence.
    retire_roles(flow)
    return deepcopy(result)
