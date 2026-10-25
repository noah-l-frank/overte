"""SDK-free failed-setup end graph before canonical SDK/Installed metadata CAS.

The independent full decoder and private inventories supply read membership.
No successful Scene, seal or terminal window is manufactured for this path.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.avatar_configuration import selector as target_selector
from ios.adapters.avatar_ended_archive import FilesOnlyClient
from ios.adapters.avatar_failed_preparation import AvatarFailedPreparation
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.emote_archive_lock import ArchiveSourceLock
from ios.adapters.emote_original_lease import EmoteOriginalLease


def verify(adapter,selector,coordinator,failed_original,*,check=lambda:None,membership=None):
    need(callable(check) and callable(getattr(adapter,'state_path',None)) and (membership is None or type(membership) is set));check()
    exact(coordinator,{'iosAvatarFeatureVersion','runId','role','selectors','artifactRoot','imagePolicy','fixtureUrl','payload'})
    run=identifier(coordinator['runId']);role=coordinator['role'];need(role in ('primary','actor'))
    targets=coordinator['selectors'];exact(targets,{'primary','actor'})
    for target in targets.values():target_selector(target)
    need(targets['primary']!=targets['actor'] and selector==targets[role])
    paths={target:Path(adapter.state_path(target)) for target in targets.values()}
    need(len({path.parent for path in paths.values()})==2 and all(path.name=='session.json' and path.is_absolute()
        and path.parent.resolve(strict=True)==path.parent for path in paths.values()))
    def state_path(target):need(target in paths);return paths[target]
    def forbidden(*_args,**_kwargs):need(False)
    runtime=IOSAvatarRuntime(SimpleNamespace(state_path=state_path,_candidate_guard=forbidden,_binding=forbidden))
    locks={subject:ArchiveSourceLock(paths[target].with_name('script-feature-sources.lock')) for subject,target in targets.items()}
    suffix='/runs/'+run+'/'
    need(type(coordinator['fixtureUrl']) is str and coordinator['fixtureUrl'].endswith(suffix))
    client=FilesOnlyClient(coordinator['fixtureUrl'][:-len(suffix)],'historical-avatar-failure-'+'a'*32)
    own_path=paths[selector].with_name('ios-avatar-'+role+'-feature.json')
    failed_path=own_path.with_name('ios-avatar-'+role+'-'+run+'-failed-preparation.json')
    with ExitStack() as held:
        for lock in sorted(locks.values(),key=lambda owner:str(owner.path)):held.enter_context(lock.held())
        need(same(PrivateFeatureState(own_path).read(),coordinator) and same(PrivateFeatureState(failed_path).read(),failed_original))
        flow=IOSAvatarFeature.archive(runtime,coordinator,client,locks)
        owner=AvatarFailedPreparation.archive(flow,failed_original);owner.original_result();peer=owner.peer_original()
        roots={path.parent for path in paths.values()}|{flow.root,peer.feature.root}
        mutable=[item for path in paths.values() for item in (path,path.with_name('installed-code-binding.json'))]
        leases=[EmoteOriginalLease(root,mutable) for root in sorted(roots)]
        with read_scope(fresh=True) as reads:
            check();need(same(PrivateFeatureState(own_path).read(),coordinator) and same(PrivateFeatureState(failed_path).read(),failed_original))
            flow=IOSAvatarFeature.archive(runtime,coordinator,client,locks)
            proof=AvatarFailedPreparation.archive(flow,failed_original).original_result();need(proof['status']=='failed' and proof['performed'])
            for current in (flow,owner.peer_original().feature):
                if current.role=='actor':
                    report=PrivateFeatureState(current.root/('avatar-worker-failed-'+run+'.json')).read()
                    if report is not None:
                        from ios.adapters.avatar_session_carriers import failure_report
                        failure_report(report,current)
            check()
        for lease in leases:lease.guard()
        if membership is not None:membership.update(reads)
        check();return deepcopy(flow.state['bindings'][role])
