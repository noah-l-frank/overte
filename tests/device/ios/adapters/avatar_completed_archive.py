"""SDK-free replay of completed Avatar role originals before session teardown.

Original SDK directories are path associations only. No target resolver,
credential authority, HTTP transport or product query runs during this replay.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import unpack,same
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from ios.adapters.avatar_configuration import selector
from ios.adapters.avatar_final_archive import IOSAvatarFinalArchive
from ios.adapters.avatar_finalization import AvatarFinalization
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.emote_archive_lock import ArchiveSourceLock


def verify(directory,path,value,*,check=lambda:None,membership=None):
    need(callable(check) and (membership is None or type(membership) is set));check()
    with read_scope(fresh=True) as reads:
        need(same(PrivateFeatureState(path).read(),value))
        binding=_verify(Path(directory),Path(path),value,check)
    if membership is not None:membership.update(reads)
    check();return binding


def _verify(directory,path,value,check):
    exact(value,{'iosAvatarFinalArchiveVersion','runId','role','binding','artifactRoot','paths','payload'})
    run,role=identifier(value['runId']),value['role'];binding=context(value['binding'])
    need(role in ('primary','actor') and path==directory/('ios-avatar-'+role+'-'+run+'-finalization.json')
        and type(value['paths']) is list and 1<=len(value['paths'])<=128)
    paths=[PrivateFeatureState(item) for item in value['paths']];need(paths[-1].path==directory/('ios-avatar-'+role+'-feature.json'))
    # Both roles retained source metadata for both independently admitted SDKs.
    # Path identities are fixed by those original owners, never guessed from a
    # selector or supplied by a caller during historical replay.
    directories=[store.path.parent for store in paths if store.path.name=='ios-avatar-'+role+'-sources.json']
    need(len(directories)==2 and len(set(directories))==2 and directory in directories)
    preliminary={subject:ArchiveSourceLock(parent/'script-feature-sources.lock') for subject,parent in zip(('primary','actor'),directories)}
    with ExitStack() as held:
        for lock in sorted(preliminary.values(),key=lambda lock:str(lock.path)):held.enter_context(lock.held())
        probe=IOSAvatarFinalArchive(PrivateFeatureState(path),value['artifactRoot'],binding,run,role,preliminary,paths,lambda:False,lambda _:need(False))
        need(probe.state is not None and probe.state['phase']=='complete')
        raw=probe.copy(probe.state['records'][-1]);need(type(raw) is dict)
        exact(raw,{'iosAvatarFeatureVersion','runId','role','selectors','artifactRoot','imagePolicy','fixtureUrl','payload'})
        exact(raw['selectors'],{'primary','actor'})
        for target in raw['selectors'].values():selector(target)
        need(raw['role']==role and raw['runId']==run and raw['artifactRoot']==value['artifactRoot'] and raw['selectors']['primary']!=raw['selectors']['actor'])
        # Locate actual per-subject source packet bindings before creating a
        # read-only runtime facade. The facade resolves only these exact paths.
        by_selector={};locks={}
        copies=probe.copies();state=unpack(raw['payload']);need(len(state)==1);bindings=state[0]['bindings']
        for subject in ('primary','actor'):
            matches=[]
            for parent in directories:
                current=copies[str(parent/('ios-avatar-'+role+'-sources.json'))]
                need(type(current) is dict)
                if same(current.get('binding'),bindings[subject]):matches.append(parent)
            need(len(matches)==1);by_selector[raw['selectors'][subject]]=matches[0];locks[subject]=next(lock for lock in preliminary.values() if lock.path.parent==matches[0])
        need(by_selector[raw['selectors'][role]]==directory and same(binding,bindings[role]))
        def state_path(target):
            need(target in by_selector);return by_selector[target]/'session.json'
        runtime=IOSAvatarRuntime(SimpleNamespace(state_path=state_path,_candidate_guard=forbidden,_binding=forbidden));suffix='/runs/'+run+'/'
        need(type(raw['fixtureUrl']) is str and raw['fixtureUrl'].endswith(suffix))
        # Client construction is inert; historical methods use only .url.
        client=Client(raw['fixtureUrl'][:-len(suffix)],'historical-read-only-'+'a'*32)
        flow=IOSAvatarFeature.archive(runtime,raw,client,locks);final=AvatarFinalization(flow)
        archive=IOSAvatarFinalArchive(PrivateFeatureState(path),flow.root,binding,run,role,locks,paths,lambda:False,final.decode)
        need(archive.state['phase']=='complete');check();archive.qualify();check()
        need(all(store.read() is None for store in paths) and same(archive.store.read(),value))
        if role=='actor':
            report=PrivateFeatureState(flow.root/('avatar-worker-failed-'+run+'.json')).read()
            if report is not None:
                from ios.adapters.avatar_session_carriers import failure_report
                failure_report(report,flow)
        archive.qualified.guard();check()
    return binding
