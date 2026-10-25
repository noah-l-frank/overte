"""SDK-free typed Avatar end replay before canonical SDK/Installed metadata CAS.

All feature/source/process originals remain at their genuine original paths.
Only a successful complete decoder plus unchanged private inventories can
supply read membership. This module writes nothing and retires no metadata.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as original_reads
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from ios.adapters.avatar_configuration import selector as target_selector
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_terminal import AvatarTerminal
from ios.adapters.emote_archive_lock import ArchiveSourceLock
from ios.adapters.emote_original_lease import EmoteOriginalLease


class FilesOnlyClient(Client):
    def request(self,*_args,**_kwargs):need(False)


def verify(adapter,selector,coordinator,terminal_original,*,check=lambda:None,membership=None,held_locks=None):
    """Return the actually ended requested role's binding; never a fresh fact.

    Candidate/target checks and actual SDK/Installed metadata CAS belong to the
    canonical caller. Its own metadata may already be absent. The complete
    Avatar graph must remain at the original paths for this file-only replay.
    """
    need(callable(check) and callable(getattr(adapter,'state_path',None)) and (membership is None or type(membership) is set));check()
    exact(coordinator,{'iosAvatarFeatureVersion','runId','role','selectors','artifactRoot','imagePolicy','fixtureUrl','payload'})
    need(coordinator['role']=='primary');run=identifier(coordinator['runId']);exact(coordinator['selectors'],{'primary','actor'})
    selectors=deepcopy(coordinator['selectors'])
    for target in selectors.values():target_selector(target)
    need(selectors['primary']!=selectors['actor'] and selector in selectors.values())
    paths={target:Path(adapter.state_path(target)) for target in selectors.values()}
    need(len({path.parent for path in paths.values()})==2 and all(path.name=='session.json' and path.is_absolute()
        and path.parent.resolve(strict=True)==path.parent for path in paths.values()))
    def state_path(target):
        need(target in paths);return paths[target]
    # The facade deliberately has no target resolver, process/SDK factory,
    # candidate getter, transport or input methods.
    def forbidden(*_args,**_kwargs):need(False)
    runtime=IOSAvatarRuntime(SimpleNamespace(state_path=state_path,_candidate_guard=forbidden,_binding=forbidden))
    if held_locks is None:
        locks={role:ArchiveSourceLock(paths[target].with_name('script-feature-sources.lock')) for role,target in selectors.items()}
    else:
        # Reuse only the exact caller-held inodes. A fresh independent reader
        # still opens existing files read-only; this path cannot create locks.
        exact(held_locks,{'primary','actor'});locks=dict(held_locks)
        for role,target in selectors.items():
            need(isinstance(locks[role],ScriptSourceLock)
                and locks[role].path==paths[target].with_name('script-feature-sources.lock'))
            locks[role].assert_held()
    suffix='/runs/'+run+'/'
    need(type(coordinator['fixtureUrl']) is str and coordinator['fixtureUrl'].endswith(suffix))
    client=FilesOnlyClient(coordinator['fixtureUrl'][:-len(suffix)],'historical-avatar-end-'+'a'*32)
    feature_path=paths[selectors['primary']].with_name('ios-avatar-primary-feature.json')
    terminal_path=feature_path.with_name('ios-avatar-primary-'+run+'-terminal.json')
    def actor_metadata(owner):
        actor,original=owner.roles(owner.state['sealedRoles'])['actor']
        path=paths[selectors['actor']].with_name('ios-avatar-actor-feature.json')
        need(same(PrivateFeatureState(path).read(),original))
        report=PrivateFeatureState(actor.root/('avatar-worker-failed-'+run+'.json')).read()
        if report is not None:
            from ios.adapters.avatar_session_carriers import failure_report
            failure_report(report,actor)
    with ExitStack() as held:
        for lock in sorted(locks.values(),key=lambda owner:str(owner.path)):held.enter_context(lock.held())
        need(same(PrivateFeatureState(feature_path).read(),coordinator) and same(PrivateFeatureState(terminal_path).read(),terminal_original))
        flow=IOSAvatarFeature.archive(runtime,coordinator,client,locks)
        need(flow.state['phase']=='terminal-ready');owner=AvatarTerminal.archive(flow,terminal_original)
        need(owner.state is not None and owner.state['end'] is not None)
        actor_metadata(owner)
        # Discover the admitted immutable role roots, then repeat the complete
        # decoder inside the independent inventory boundary before returning.
        roots={path.parent for path in paths.values()}|{flow.root}|{role.root for role,_raw in owner.roles(owner.state['sealedRoles']).values()}
        sdk_metadata=[path for base in paths.values() for path in (base,base.with_name('installed-code-binding.json'))]
        leases=[EmoteOriginalLease(root,sdk_metadata) for root in sorted(roots)]
        with original_reads(fresh=True) as reads:
            need(same(PrivateFeatureState(feature_path).read(),coordinator) and same(PrivateFeatureState(terminal_path).read(),terminal_original))
            flow=IOSAvatarFeature.archive(runtime,coordinator,client,locks);owner=AvatarTerminal.archive(flow,terminal_original)
            actor_metadata(owner)
            end=owner.verify_end(membership=reads)
            from feature_journeys import terminal
            terminal.ended(end,owner.state['seal']);check()
        for lease in leases:lease.guard()
        check()
        if membership is not None:membership.update(reads)
        return deepcopy(flow.state['bindings'][next(role for role,target in selectors.items() if target==selector)])
