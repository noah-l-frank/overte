"""Ordinary known-error cleanup without replaying an uncertain OK input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import scope
from adapters.script_feature.history import same
from ios.adapters.navigation_feature import IOSNavigationFeature,NavigationFeaturePending
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_process_scope import NavigationProcessScope,owner_path
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions


def cleanup(flow,admission,call):
    need(type(flow) is IOSNavigationFeature and flow.role=='primary'
        and isinstance(admission,(NavigationAdmissionOwner,NavigationProcessScope)) and admission.lock is flow.lock)
    flow.lock.assert_held();need(flow.state is not None and flow.state['phase']=='ready'
        and same(flow.state['binding'],admission.binding) and flow.run==admission.run)
    checker=object.__new__(NavigationSurfaceActions);checker.run=flow.run;checker.admission=admission
    checker.call(call);need(call['verb']=='cleanup' and 'iosNavigationCleanupCallVersion' in call)
    path=owner_path(admission,'ios-navigation-missing-actions.json');original=PrivateFeatureState(path).read()
    if original is None:return None
    missing=flow.runtime._navigation_missing_actions(flow.selector,admission);need(same(missing.previous,original))
    if missing.state['proof'] is None:
        frames=missing.state['frames']
        if frames and frames[-1]['kind']=='missing' and frames[-1]['clockJoin'] is not None:missing.recover_missing()
        else:raise NavigationFeaturePending('Original named-lookup failure remains unresolved; no OK is sent')
    if missing.state['cleared'] is None:
        dismissed=missing.state['dismiss']
        if dismissed is None:missing.dismiss_cleanup(call)
        else:
            need(dismissed['phase'] in ('issued','delivered'))
            if 'iosNavigationCleanupCallVersion' in dismissed['call']:need(same(dismissed['call'],call))
        if missing.observe_cleared() is None:
            raise NavigationFeaturePending('Actual error dialog/listener still requires original drainage')
    address=flow.runtime._navigation_address_dismiss(flow.selector,admission)
    with scope(lambda:missing.transport_guard(authority=call)):
        if address.state is not None and address.state['after'] is not None:address.recover()
        else:address.close()
    return missing
