"""Pure post-end verification for the exact completed Worlds owner.

This is a read of the actual original graph, OS windows and SDK absence. It has
no branch that can prepare ownership, Stop, query a live source or delete SDKs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys import terminal as protocol
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.adapters.navigation_terminal import NavigationTerminal
from ios.adapters.navigation_process_end import NavigationProcessEnd
from ios.adapters.navigation_session_end import NavigationSessionEnd


def verify(whole,call,result):
    need(type(whole) is NavigationWholeFeature and whole.flow.role=='primary')
    call=protocol.arguments('world-navigation',call)
    need(call['stage']=='finish' and call['runId']==whole.flow.run)
    protocol.result('world-navigation',result)
    need(result['stage']=='finish' and same(result['end']['seal'],call['seal']))
    f=whole.flow
    with f.held():
        store=PrivateFeatureState(f.store.path.with_name('ios-navigation-final-archive.json'));archive=store.read()
        need(archive is not None
            and PrivateFeatureState(f.store.path.with_name('ios-navigation-process-end.json')).read() is not None
            and PrivateFeatureState(f.store.path.with_name('ios-navigation-session-end.json')).read() is not None)
        owner=NavigationTerminal(f)
        need(owner.state is not None and same(owner.state['seal'],call['seal']))
        process=NavigationProcessEnd(owner)
        from ios.adapters.navigation_terminal_replay import checked
        with checked(owner,process.mutable()) as proof:
            process.checked_terminal=proof
            return _verify(process,archive,store,call,result)


def _verify(process,archive,store,call,result):
    owner=process.terminal;f=owner.flow;process.verify();sdk=NavigationSessionEnd(process);sdk.historical()
    expected=dict(iosNavigationFinalArchiveVersion=1,runId=f.run,artifactRoot=str(f.root),binding=process.binding,
        terminalOriginalSha256=digest(owner.previous),processOriginalSha256=digest(process.previous),
        sdkOriginalSha256=digest(sdk.previous),sourceInventorySha256=digest(process.state['inventories']))
    need(same(archive,expected) and same(store.read(),archive))
    ended=dict(featureTerminalEndVersion=1,seal=deepcopy(call['seal']),roles={
        role:dict(binding=deepcopy(prior['binding']),heldOriginalSha256=prior['originalSha256'],
            stopOriginalSha256=digest(process.previous),osAbsence=process.role_os(role),
            sdkDeletionOriginalSha256=digest(sdk.previous),archiveSha256=digest(archive))
        for role,prior in owner.state['description']['roles'].items()})
    protocol.ended(ended,call['seal']);need(same(result,dict(stage='finish',end=ended)))
    process.verify();sdk.historical();need(same(store.read(),archive));f.clock()
    return deepcopy(result)
