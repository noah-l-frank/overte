"""Tablet same-SDK terminal scheduling, preserving independent Actor ownership.

Polling waits happen outside the shared source lock. Only Primary can Stop or
delete the SDK; Actor independently observes the same old process and records
its own actual worker retirement after the original SDK absence is established.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys import terminal as protocol
from ios.adapters.tablet_web_terminal import TabletWebTerminal
from ios.adapters.tablet_web_process_end import TabletWebProcessEnd,mutable_paths
from ios.adapters.tablet_web_session_end import TabletWebSessionEnd
from ios.adapters.tablet_web_terminal_replay import checked


def worker_store(feature):return PrivateFeatureState(feature.root/('tabletweb-worker-retired-'+feature.run+'.json'))


def worker_original(feature,process,session):
    need(feature.role=='actor');process.verify();session.historical()
    role=process.state['roles']['actor'];need(role is not None and role['issuers'] and role['issuers'][-1]['hostProcessId']==os.getpid())
    return dict(tabletWebWorkerRetirementVersion=1,runId=feature.run,binding=deepcopy(feature.binding),hostProcessId=os.getpid(),
        terminalSha256=digest(process.terminal.previous),processOriginalSha256=digest(process.previous),
        osOriginalSha256=process.role_os('actor')['originalSha256'],sdkDeletionOriginalSha256=digest(session.previous))


def actor_step(feature):
    """None: active; False: sealed/waiting; True: own worker may now exit."""
    need(feature.role=='actor');lock=ScriptSourceLock(feature.root/'script-feature-sources.lock')
    with feature.locked(lock):
        terminal=TabletWebTerminal(feature,lock)
        if terminal.state is None or terminal.state['seal'] is None:return None
        cue=PrivateFeatureState(feature.root/('tabletweb-process-end-'+feature.run+'.json')).read()
        if cue is None:return False  # Ownership wait only, never an OS/native fact.
        exact(cue,{'tabletWebProcessEndVersion','binding','runId','payload'})
        need(type(cue['tabletWebProcessEndVersion']) is int and cue['tabletWebProcessEndVersion']==1
            and cue['runId']==feature.run and same(cue['binding'],feature.binding))
        from adapters.script_feature.history import unpack
        rows=unpack(cue['payload']);need(len(rows)==1 and type(rows[0]) is dict and rows[0].get('phase') in ('prepared','stop-issued','complete'))
        if rows[0]['phase']=='prepared':return False
        with checked(terminal,mutable_paths(feature,lock)):
            process=TabletWebProcessEnd(terminal)
            if process.state['phase']!='complete':
                own=process.state['roles']['actor']
                if own is None or own['pending'] is not None or own['original'] is None or not process.os_archive('actor',own['original'])['windows'][-1]['complete']:process.advance('actor')
                return False
            store=PrivateFeatureState(feature.root/('tabletweb-session-end-'+feature.run+'.json'));value=store.read()
            if value is None:return False
            session=TabletWebSessionEnd(process)
            if session.state['phase']!='complete':return False
            original=worker_original(feature,process,session);store=worker_store(feature);previous=store.read()
            if previous is None:store.write(original,None)
            else:need(same(previous,original))
            need(same(store.read(),original));return True


def end_original(feature,process,session):
    """Replay the actual two-role seal/OS/delete/worker chain without I/O sends."""
    process.verify();session.historical();terminal=process.terminal;seal=terminal.replay();worker=worker_store(feature).read()
    exact(worker,{'tabletWebWorkerRetirementVersion','runId','binding','hostProcessId','terminalSha256','processOriginalSha256','osOriginalSha256','sdkDeletionOriginalSha256'})
    need(type(worker['tabletWebWorkerRetirementVersion']) is int and worker['tabletWebWorkerRetirementVersion']==1
        and worker['runId']==feature.run and same(worker['binding'],feature.binding)
        and worker['hostProcessId']==process.state['roles']['actor']['issuers'][-1]['hostProcessId']
        and worker['terminalSha256']==digest(terminal.previous) and worker['processOriginalSha256']==digest(process.previous)
        and worker['osOriginalSha256']==process.role_os('actor')['originalSha256'] and worker['sdkDeletionOriginalSha256']==digest(session.previous))
    roles={}
    for role in protocol.ROLES:
        held=seal['description']['roles'][role];os_original=process.role_os(role)
        archive=dict(tabletWebRoleFinalVersion=1,role=role,heldOriginal=terminal.state['references'][role],live=terminal.state['live'],
            process=process.previous,osAbsence=os_original,sdkDeletion=session.previous,worker=worker)
        roles[role]=dict(binding=held['binding'],heldOriginalSha256=held['originalSha256'],stopOriginalSha256=digest(process.previous),
            osAbsence=os_original,sdkDeletionOriginalSha256=digest(session.previous),archiveSha256=digest(archive))
    value=dict(featureTerminalEndVersion=1,seal=seal,roles=roles);protocol.ended(value,seal);return value


def finish(feature,seal):
    need(feature.role=='primary');lock=ScriptSourceLock(feature.root/'script-feature-sources.lock')
    while True:
        feature.clock()
        with feature.locked(lock):
            terminal=TabletWebTerminal(feature,lock);need(terminal.state is not None and same(terminal.state['seal'],seal))
            prior=PrivateFeatureState(feature.root/('tabletweb-process-end-'+feature.run+'.json')).read()
            if prior is None:TabletWebProcessEnd(terminal).inventories()
            with checked(terminal,mutable_paths(feature,lock)):
                need(same(terminal.replay(),seal));process=TabletWebProcessEnd(terminal)
                if process.state is None:process.prepare()
                if process.state['phase']=='prepared':process.stop()
                if process.state['phase']!='complete':process.advance('primary')
                if process.state['phase']=='complete':
                    session=TabletWebSessionEnd(process);completed=session.advance()
                    if completed is not None and worker_store(feature).read() is not None:
                        value=end_original(feature,process,session)
                        store=PrivateFeatureState(feature.root/('tabletweb-final-archive-'+feature.run+'.json'));old=store.read()
                        original=dict(tabletWebFinalArchiveVersion=1,runId=feature.run,binding=feature.binding,terminal=terminal.previous,
                            process=process.previous,sdkDeletion=session.previous,worker=worker_store(feature).read(),end=value)
                        if old is None:store.write(original,None)
                        else:need(same(old,original))
                        need(same(store.read(),original));return value
        feature.sleep(.25);feature.clock()
