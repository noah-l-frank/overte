"""Read-only full Tablet terminal archive replay, never a new Stop authority.

All terminal/native/OS/witness/worker originals are redecoded. This helper
cannot acquire a session, query a product, send input or remove ownership.
Canonical orphan/input-owner admission is a separate integration requirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.adapters.tablet_web_terminal import TabletWebTerminal
from ios.adapters.tablet_web_process_end import TabletWebProcessEnd,mutable_paths
from ios.adapters.tablet_web_session_end import TabletWebSessionEnd
from ios.adapters.tablet_web_terminal_finish import end_original,worker_store
from ios.adapters.tablet_web_terminal_replay import checked


def replay(runtime,selector,run,lock,*,check,monotonic=time.monotonic):
    need(isinstance(runtime,IOSTabletWebRuntime) and isinstance(lock,ScriptSourceLock)
        and callable(check) and callable(monotonic))
    identifier(run);root=runtime.state_path(selector).parent
    need(lock.path==root/'script-feature-sources.lock');lock.assert_held();check()
    filename='tabletweb-final-archive-'+run+'.json';store=PrivateFeatureState(root/filename)
    value=store.read()
    exact(value,{'tabletWebFinalArchiveVersion','runId','binding','terminal','process','sdkDeletion','worker','end'})
    need(type(value['tabletWebFinalArchiveVersion']) is int and value['tabletWebFinalArchiveVersion']==1 and value['runId']==run)
    feature=PrivateFeatureState(root/('tabletweb-feature-'+run+'-primary.json')).read()
    need(type(feature) is dict and feature.get('runId')==run and feature.get('role')=='primary'
        and same(feature.get('binding'),value['binding']))
    bootstrap=PrivateFeatureState(root/('tabletweb-context-'+run+'-primary.json')).read()
    publication=PrivateFeatureState(root/('phase-publication-tablet-web-'+run+'-actor.json')).read()
    need(type(bootstrap) is dict and same(bootstrap.get('binding'),value['binding'])
        and type(publication) is dict and publication.get('runId')==run and publication.get('area')=='tablet-web')
    # The actual old candidate/target is independently selected by the caller's
    # existing canonical adapter. No current SDK session is created or adopted.
    runtime.adapter._retired_candidate_scope(selector,{key:child for key,child in value['binding'].items() if key!='processIdentity'})
    def forbidden(*_args,**_kwargs):need(False)
    client=object.__new__(Client);client.url=publication['fixtureUrl'];client.request=forbidden
    screen=feature['screen'];need(type(screen) is dict)
    settings=dict(artifactRoot=screen['artifactRoot'],imagePolicy=screen['policy'],physicalBinding=value['binding'],
        setupNative=bootstrap['setupNative'],origins=feature['origins'])
    whole=runtime._tablet_web_feature(selector,run,role='primary',client=client,settings=settings)
    whole.monotonic=monotonic;whole.epoch_ms=forbidden;whole.sleep=forbidden
    roots={root,Path(screen['artifactRoot'])}
    leases=[EmoteOriginalLease(path,[]) for path in roots if not any(path!=other and path.is_relative_to(other) for other in roots)]
    with scope(fresh=True) as members:
        terminal=TabletWebTerminal(whole,lock);need(same(terminal.previous,value['terminal']))
        with checked(terminal,mutable_paths(whole,lock)):
            process=TabletWebProcessEnd(terminal);need(same(process.previous,value['process']))
            session=TabletWebSessionEnd(process);need(same(session.previous,value['sdkDeletion']))
            actual=end_original(whole,process,session)
            expected=dict(tabletWebFinalArchiveVersion=1,runId=run,binding=whole.binding,terminal=terminal.previous,
                process=process.previous,sdkDeletion=session.previous,worker=worker_store(whole).read(),end=actual)
            need(same(value,expected) and same(store.read(),value))
    for lease in leases:lease.guard()
    check();return dict(binding=deepcopy(value['binding']),end=deepcopy(actual),members=frozenset(members),roots=frozenset(roots))
