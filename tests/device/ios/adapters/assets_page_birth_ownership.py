"""Closed pure action1 page-birth inventory, including unresolved prefixes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
import re
from adapters.native_feature_observation import need
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_end_graph import AssetsFinalArchive
from ios.adapters.assets_action_phase import AssetsActionPhases
from ios.adapters.assets_end_metadata import store as metadata_store,entries as metadata_entries,coverage as metadata_coverage
from ios.adapters.assets_page_birth import AssetsPageBirth


@dataclass(frozen=True)
class AssetsPageBirthInventoryContext:
    selected:AssetsFinalArchive
    actions:AssetsActionPhases
    lock:ScriptSourceLock


def inspect_birth(a,*,metadata=None):
    need(type(a) is AssetsPageBirthInventoryContext and type(a.selected) is AssetsFinalArchive
        and type(a.actions) is AssetsActionPhases and a.actions.selected is a.selected
        and a.lock is a.actions.locks['primary'])
    a.lock.assert_held();a.selected.selected_guard();a.actions.guard()
    directory=Path(a.selected.context['roles']['primary']['stateRoot']);run=a.selected.run
    need(a.lock.path==directory/'script-feature-sources.lock')
    before=metadata_entries(directory,metadata);wanted={p for p in before if p.name.startswith(('ios-assets-page-birth-','assets-page-birth-'))}
    patterns=(re.compile('ios-assets-page-birth-'+run+r'-primary\.json'),
        re.compile('assets-page-birth-frame-sources-'+run+r'-primary-[0-9]{4}-[a-f0-9]{64}\.json'))
    need(all(any(pattern.fullmatch(p.name) for pattern in patterns) for p in wanted))
    with read_scope(fresh=True) as reads:
        owner=AssetsPageBirth.from_prefix(a.selected,metadata_store(directory/('ios-assets-page-birth-'+run+'-primary.json'),metadata),a.lock,a.actions)
        paths={owner.store.path};duties=['page-birth-originals']
        for ref in owner.state['frames']:paths.add(owner.originals.path(owner.originals.expand(ref)))
        pending=owner.state['pending']
        if pending is not None:
            duties.append('page-birth-source-write');ref=pending['original']
            if ref is not None and ref['phase']!='planned':paths.add(owner.originals.path(ref))
        complete=bool(a.actions.state['records'])
        if not complete:duties.append('page-action-completion')
        if owner.state['phase']!='opened':duties.append('page-birth-inputs')
        page=owner.page() if owner.state['phase']=='opened' else None
        need(wanted==paths and metadata_coverage(paths,reads,metadata))
        need([p.name for p in metadata_entries(directory,metadata)]==[p.name for p in before])
        owner.guard()
    return dict(owner=owner,report=dict(assetsPageBirthOwnershipVersion=1,runId=run,role='primary',binding=deepcopy(owner.binding),
        paths=paths,actualOriginalReads=set(reads),responsibilities=sorted(set(duties)),action1Complete=complete,
        originalPage=page,currentNativeFactsProduced=False,abortAuthorized=False,wholeEndEligible=False))
