"""Pure typed complete PageLease inventory for an independently selected prefix.

This report retains shared page duties. It does not authorize abort, acquire
native absence, retire server/Model/SDK resources or admit a whole end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
import time
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import same
from ios.adapters.assets_end_metadata import store as metadata_store,entries as metadata_entries,coverage as metadata_coverage
from ios.adapters.assets_episodes import AssetsEpisodes,AssetsEpisodeScope
from ios.adapters.assets_selected_profile import EpisodeAssetsFiles
from ios.adapters.assets_file_sources import FileSources
from ios.adapters.assets_page_picker import PageLeasePicker
from ios.adapters.assets_page_lease import OwnedAssetsPageLease


@dataclass(frozen=True)
class AssetsPageInventoryContext:
    episodes:AssetsEpisodes
    scopes:tuple
    birth:object=None


def forbidden(*_args,**_kwargs):raise RuntimeError('Historical page inventory cannot acquire, query, write or retire')


def authority(a):
    need(type(a) is AssetsPageInventoryContext and type(a.episodes) is AssetsEpisodes and type(a.scopes) is tuple)
    episodes=a.episodes;episodes.guard();entries=episodes.state['entries']
    need(0<=len(a.scopes)==len(entries)<=5 and all(row['phase']=='ready' for row in entries))
    if not entries:need(a.birth is not None)
    for index,scope in enumerate(a.scopes,1):
        need(type(scope) is AssetsEpisodeScope and scope.owner is episodes and scope.index==index)
        scope.guard()
        for lock in scope.locks.values():lock.assert_held()
    for lock in episodes.locks.values():lock.assert_held()
    return episodes


def skeleton(scope,metadata):
    episodes=scope.owner;run=episodes.run;role='primary';info=episodes.context['roles'][role];binding=info['binding']
    root=Path(scope.descriptor['directories'][role]['stateRoot']['path']);lock=scope.locks[role]
    files=object.__new__(EpisodeAssetsFiles);files.selection,files.selection_read_only,files.episode=episodes.selected,True,scope
    files.native=SimpleNamespace(pid=int(binding['processIdentity']),monotonic=time.monotonic)
    files.run,files.url,files.binding,files.role=run,episodes.context['fixtureUrl'],deepcopy(binding),role
    files.lock=lock;files.state=None;files.store=metadata_store(root/('ios-assets-'+run+'-primary-files.json'),metadata)
    files.previous=files.store.read();need(files.previous is not None and files.previous.get('iosAssetsFileOwnerVersion')==4)
    files.sources=FileSources(files,role,lambda:scope.guard(),forbidden);files.state=files.decode(files.previous)
    need(files.state['ticket']==scope.descriptor['ticket'] and files.state['resource']==scope.descriptor['resource'])
    picker=object.__new__(PageLeasePicker);picker.files,picker.binding,picker.lock,picker.episode=files,deepcopy(binding),lock,scope
    picker.store=metadata_store(root/('ios-assets-'+run+'-primary-picker.json'),metadata);picker.previous=picker.store.read()
    need(picker.previous is not None and picker.previous.get('iosAssetsPickerOwnerVersion')==2)
    picker.state=None;picker.native=SimpleNamespace(capture=forbidden);picker.monotonic=time.monotonic;picker.sleep=forbidden
    return picker


def inspect_page(a,*,metadata=None):
    episodes=authority(a);run=episodes.run;directory=Path(episodes.context['roles']['primary']['stateRoot'])
    store=metadata_store(directory/('ios-assets-page-lease-'+run+'-primary.json'),metadata)
    patterns=(re.compile('ios-assets-page-lease-'+run+r'-primary\.json'),
        re.compile('assets-page-lease-frame-sources-'+run+r'-primary-[0-9]{4}-[a-f0-9]{64}\.json'))
    before=metadata_entries(directory,metadata);wanted={path for path in before if path.name.startswith(('ios-assets-page-lease-','assets-page-lease-'))}
    need(all(any(pattern.fullmatch(path.name) for pattern in patterns) for path in wanted))
    with read_scope(fresh=True) as reads:
        pickers={scope.index:skeleton(scope,metadata) for scope in a.scopes}
        from ios.adapters.assets_historical_picker_snapshots import historical_picker_snapshots
        snapshots=historical_picker_snapshots(episodes,pickers,metadata)
        with snapshots as snapshot_scope:
            value=store.read();need(type(value) is dict)
            if value.get('iosAssetsPageLeaseVersion')==2:
                from ios.adapters.assets_born_page_lease import BornAssetsPageLease
                from ios.adapters.assets_page_birth import AssetsPageBirth
                need(type(a.birth) is AssetsPageBirth and a.birth.historical and a.birth.selected is episodes.selected)
                owner=BornAssetsPageLease.from_archive(episodes,store,episodes.locks['primary'],pickers,context=a.birth,snapshot_scope=snapshot_scope)
            else:
                need(a.birth is None);owner=OwnedAssetsPageLease.from_archive(episodes,store,episodes.locks['primary'],pickers,snapshot_scope=snapshot_scope)
            paths={store.path};responsibilities=['page-originals'];records=[]
            for ref in owner.state['records']:
                paths.add(owner.originals.path(owner.originals.expand(ref)));records.append(owner.read(ref))
            pending=owner.state['pending']
            if pending is not None:
                responsibilities.append('page-source-write');ref=pending['original']
                if ref is not None and ref['phase']!='planned':paths.add(owner.originals.path(ref))
            if owner.state['phase']!='closed':responsibilities.append('shared-page-root')
            for index,picker in pickers.items():
                if picker.files.state['phase']!='retired':responsibilities.append('episode-input-files')
                if picker.state['phase']!=picker.retirement_phase():responsibilities.append('episode-picker-client')
                if str(index) not in owner.state['attachments']:responsibilities.append('episode-page-attachment')
                if str(index) not in owner.state['transfers']:responsibilities.append('episode-page-transfer')
            need(wanted==paths and metadata_coverage(paths,reads,metadata))
            need([p.name for p in metadata_entries(directory,metadata)]==[p.name for p in before]);authority(a)
    return dict(owner=owner,pickers=pickers,report=dict(assetsPageOwnershipVersion=1,runId=run,role='primary',binding=deepcopy(owner.binding),
        paths=paths,actualOriginalReads=set(reads),responsibilities=sorted(set(responsibilities)),phase=owner.state['phase'],
        normalPageClosed=owner.state['phase']=='closed',bornEpisodes=len(a.scopes),currentNativeFactsProduced=False,
        abortAuthorized=False,wholeEndEligible=False))
