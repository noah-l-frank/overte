"""Pure final InstalledAdapter verification of the exact Tablet end archive.

No live SDK/bundle verification follows an already deleted SDK. This hook
instead replays the actual sealed native/OS/delete/worker chain and keeps the
caller's original outer transport budget through the complete final read.
It neither initiates cleanup nor supplies orphan/root retirement authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.operation_transport_guard import check
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys import terminal as protocol
from ios.adapters.tablet_web_completed import replay
from ios.adapters.tablet_web_feature import IOSTabletWebFeature


def verify(feature,call,result):
    need(type(feature) is IOSTabletWebFeature and feature.role=='primary')
    call=protocol.arguments('tablet-web',call);protocol.result('tablet-web',result)
    need(call['stage']==result['stage']=='finish' and call['runId']==feature.run
        and same(result['end']['seal'],call['seal']))
    check();lock=ScriptSourceLock(feature.root/'script-feature-sources.lock')
    with lock.held():
        actual=replay(feature.runtime,feature.selector,feature.run,lock,check=check,monotonic=feature.monotonic)
        need(same(actual['binding'],feature.binding) and same(result,dict(stage='finish',end=actual['end'])))
        check();return deepcopy(result)
