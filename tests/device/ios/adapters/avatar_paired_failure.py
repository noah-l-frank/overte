"""Closed actual peer failure admission; never relabel a ready feature phase."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same,pack

VERSION=1


def peer(feature):
    from ios.adapters.avatar_feature import IOSAvatarFeature
    other='actor' if feature.role=='primary' else 'primary';feature.locks[other].assert_held()
    path=feature.runtime.state_path(feature.selectors[other]).with_name('ios-avatar-'+other+'-feature.json')
    value=PrivateFeatureState(path).read();need(value is not None)
    flow=IOSAvatarFeature.archive(feature.runtime,value,feature.client,feature.locks)
    need(flow.role==other and flow.run==feature.run and same(flow.selectors,feature.selectors)
        and same(flow.state['bindings'],feature.state['bindings']))
    return flow,value


def prepare(feature):
    """None means no failed peer; a preparing peer may still need admission."""
    from ios.adapters.avatar_failed_preparation import FailedPreparationPending
    from ios.adapters.avatar_abort import IOSAvatarAbort
    feature.lock.assert_held();need(feature.state['phase']=='ready');flow,value=peer(feature)
    if flow.state['phase']!='preparing':return None
    path=flow.store.path.with_name('ios-avatar-'+flow.role+'-'+feature.run+'-abort.json');original=PrivateFeatureState(path).read()
    if original is None:raise FailedPreparationPending('Independent preparing peer has not admitted failure cleanup')
    admission=IOSAvatarAbort.history(flow,original);need(admission.paired_failure is None and admission.state['phase']=='failed')
    result=dict(avatarPairedPreparationFailureVersion=VERSION,peerRole=flow.role,peerFeatureSha256=digest(value),
        peerAdmissionSha256=digest(original),source=deepcopy(original['source']),bundleId=original['bundleId'],
        operationClock=deepcopy(admission.state['operationClock']))
    validate(feature,result);return result


def validate(feature,value):
    from ios.adapters.avatar_abort import IOSAvatarAbort,PHASES
    exact(value,{'avatarPairedPreparationFailureVersion','peerRole','peerFeatureSha256','peerAdmissionSha256','source','bundleId','operationClock'})
    need(type(value['avatarPairedPreparationFailureVersion']) is int and value['avatarPairedPreparationFailureVersion']==VERSION
        and feature.state['phase']=='ready')
    flow,current=peer(feature);need(flow.role==value['peerRole'] and flow.state['phase']=='preparing' and digest(current)==value['peerFeatureSha256'])
    # This is a compact projection of the actual initial host admission, not
    # a new product original. Its closed initial-state grammar reconstructs
    # every field and must match the independently retained original digest.
    admission=dict(iosAvatarAbortVersion=1,runId=flow.run,role=flow.role,binding=flow.state['bindings'][flow.role],
        source=deepcopy(value['source']),bundleId=value['bundleId'],failure=dict(kind='preparation-incomplete',original=current,
        originalSha256=digest(current)),payload=pack([dict(phase='failed',operationClock=value['operationClock'],
        stopReturned=False,process=None,sdkQueries=[],sdkPending=None)]))
    need(digest(admission)==value['peerAdmissionSha256'])
    before=IOSAvatarAbort.history(flow,admission);need(before.paired_failure is None and before.state['phase']=='failed')
    current=PrivateFeatureState(before.store.path).read();need(current is not None)
    after=IOSAvatarAbort.history(flow,current);need(after.paired_failure is None and PHASES.index(after.state['phase'])>=PHASES.index(before.state['phase']))
    for key in ('binding','source','bundleId','failure'):need(same(current[key],admission[key]))
    need(same(after.state['operationClock'],before.state['operationClock'])
        and same(after.state['sdkQueries'][:len(before.state['sdkQueries'])],before.state['sdkQueries']))
    return deepcopy(value)
