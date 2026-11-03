"""Pure complete Assets UI screen inventory with independent original authority.

Actual original bytes/inodes and existing typed UI/source/pixel readers execute.
No SDK/client/native query, input, retry, recovery, cleanup or whole end is
performed. Rejected or interrupted images remain owned and cannot become pixels.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from dataclasses import dataclass,field
import os
from pathlib import Path
import re
from types import SimpleNamespace
from adapters.native_feature_observation import need,exact
from adapters.normal_feature_state import context,PrivateFeatureState
from adapters.original_file_reads import scope as read_scope,record as original_read
from adapters.original_screen_images import LIMIT,capture_record
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.evidence import MarkerNotReady
from ios.adapters.assets_end_metadata import store as metadata_store,entries as metadata_entries,coverage as metadata_coverage
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.assets_ui_source import AssetsUiSource
from ios.adapters.assets_ui_samples import AssetsUiSamples
from ios.adapters.assets_ui_images import IOSAssetsUiImages


@dataclass(frozen=True)
class AssetsUiInventoryContext:
    state_root:Path
    artifact_root:Path
    binding:dict
    run:str
    checkpoint:str
    subject:str
    ticket:str
    policy:dict
    lock:ScriptSourceLock
    upload:OwnedAssetsUpload
    marker:OwnedAssetsMarker
    episode:object=None
    _directories:tuple=field(init=False,repr=False,compare=False)

    def __post_init__(self):
        object.__setattr__(self,'_directories',tuple(directory_identity(path) for path in (self.state_root,self.artifact_root)))

    def directory_guard(self):
        need(tuple(directory_identity(path) for path in (self.state_root,self.artifact_root))==self._directories)


def directory_identity(path):
    # The same private-directory boundary is mandatory even before any file
    # exists. Keep identity across the complete read, rather than allowing an
    # equally named replacement directory to inherit independent authority.
    directory=Path(path);boundary=PrivateFeatureState(directory/'.assets-ui-directory-boundary')
    boundary._parent();before=directory.lstat();boundary._parent();after=directory.lstat()
    identity=lambda info:(info.st_dev,info.st_ino,info.st_uid,info.st_mode)
    need(identity(before)==identity(after));return identity(after)


RUN='([a-f0-9]{32})'
TAIL='-[0-9]{4}-[a-f0-9]{64}\\.json'
STATE_PATTERNS=(re.compile('ios-assets-ui-sources-'+RUN+'-(browse|baking-on)\\.json'),
    re.compile('assets-ui-screen-(samples|owner)-'+RUN+'-primary\\.json'),
    re.compile('assets-ui-native-frame-sources-'+RUN+'-primary'+TAIL),
    re.compile('assets-ui-(browse|baking-on)-sources-frame-sources-'+RUN+'-primary'+TAIL))
ARTIFACT_PATTERNS=(re.compile('assets-ui-primary-screen-parts-frame-sources-'+RUN+'-primary'+TAIL),
    re.compile('assets-ui-screen-samples-frame-sources-'+RUN+'-primary'+TAIL),
    re.compile('assets-ui-'+RUN+'-primary-0-[a-f0-9]{32}\\.png'))
PREFIX=('ios-assets-ui-','assets-ui-')


def inventory_path(name):return type(name) is str and any(p.fullmatch(name) for p in (*STATE_PATTERNS,*ARTIFACT_PATTERNS))
def forbidden(*_args,**_kwargs):raise RuntimeError('Historical UI inventory cannot acquire, write, recover or retire')


def authority(a):
    need(type(a) is AssetsUiInventoryContext);context(a.binding);identifier(a.run);identifier(a.ticket)
    exact(a.policy,{'source','marker','subject'});need(a.policy['source']=='native-screen')
    need(a.checkpoint in ('browse','baking-on') and isinstance(a.lock,ScriptSourceLock)
        and isinstance(a.upload,OwnedAssetsUpload) and isinstance(a.marker,OwnedAssetsMarker)
        and a.upload.lock is a.lock and same(a.upload.binding,a.binding) and a.upload.files.run==a.run and a.upload.role=='primary'
        and same(a.marker.scope.binding,a.binding) and a.marker.run==a.run and a.marker.role=='primary'
        and a.marker.scope.fixture_url==a.upload.files.url)
    a.directory_guard();a.lock.assert_held();a.marker.lock.assert_held();state,root=Path(a.state_root),Path(a.artifact_root)
    need(state==a.upload.store.path.parent and a.lock.path==state/'script-feature-sources.lock'
        and state.resolve()==state and root.resolve()==root and state.is_dir() and root.is_dir())
    if a.episode is not None:
        from ios.adapters.assets_episodes import AssetsEpisodeScope
        need(type(a.episode) is AssetsEpisodeScope);a.episode.guard()
        need(a.lock is a.episode.locks['primary'] and state==Path(a.episode.descriptor['directories']['primary']['stateRoot']['path'])
            and root==Path(a.episode.descriptor['directories']['primary']['artifactRoot']['path']))
    return state,root


def members(state,root,run,metadata):
    wanted=set();snapshots={}
    for directory in {state,root}:
        entries=metadata_entries(directory,metadata);need(len(entries)<=4096);snapshots[directory]=[p.name for p in sorted(entries)]
        patterns=STATE_PATTERNS if directory==state and directory!=root else ARTIFACT_PATTERNS if directory==root and directory!=state else (*STATE_PATTERNS,*ARTIFACT_PATTERNS)
        for path in entries:
            if not path.name.startswith(PREFIX):continue
            matches=[p.fullmatch(path.name) for p in patterns];need(any(matches))
            need(run in path.name);wanted.add(path)
    return wanted,snapshots


def screen_files(samples,covered):
    """Retain literal current file rows, including exact opened byte prefixes."""
    owner=object.__new__(IOSAssetsUiImages);owner.namespace,owner.version_key='assets-ui','assetsUiScreenImagesVersion'
    owner.store=samples.feature_store(samples.source.root/('assets-ui-screen-owner-'+samples.run+'-primary.json'))
    owner.root,owner.binding,owner.run,owner.role,owner.stage=samples.root,samples.binding,samples.run,'primary',0
    owner.lock,owner.guard=samples.lock,samples.file_guard;owner._load()
    if owner.state is None:return [],False
    covered.add(owner.store.path);remaining=False;rows=[]
    for row in owner.rows:
        path=owner._path(row)
        if row['phase']=='removed':need(not os.path.lexists(path));rows.append(row);continue
        remaining=True
        if row['file'] is None:need(row['phase']=='planned' and not os.path.lexists(path));rows.append(row);continue
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
        with os.fdopen(fd,'rb') as stream:
            owner._file(row,stream.fileno());before=os.fstat(stream.fileno());raw=stream.read(LIMIT+1)
            owner._file(row,stream.fileno());after=os.fstat(stream.fileno())
        need((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns) and len(raw)<=LIMIT)
        if row['phase']=='saved':capture_record(row['capture'],raw)
        original_read(path);covered.add(path);rows.append(row)
    return rows,remaining


def inspect_ui(a,*,metadata=None):
    state,root=authority(a);wanted,before=members(state,root,a.run,metadata);store_for=lambda path:metadata_store(path,metadata)
    source_path=state/('ios-assets-ui-sources-'+a.run+'-'+a.checkpoint+'.json')
    sample_path=state/('assets-ui-screen-samples-'+a.run+'-primary.json')
    source_value=store_for(source_path).read();need(source_value is not None)
    responsibilities=['ui-screen-originals'];covered={source_path};results=[]
    with read_scope(fresh=True) as reads:
        # Metadata must be read inside this same actual membership scope too.
        source_store=store_for(source_path);source_value=source_store.read()
        source=AssetsUiSource.from_archive(source_value,source_store,a.upload,a.marker,a.lock,subject=a.subject,checkpoint=a.checkpoint)
        if not source.state['records']:responsibilities.append('ui-image-checkpoint')
        covered|=source.raws.owned_paths()
        for ref in source.raws.refs:source.raws.read_record(ref)
        if source.raws.pending is not None:
            responsibilities.append('ui-native-source-write');ref=source.raws.pending['original']
            if ref is not None:
                AssetsModelSources.prefix(SimpleNamespace(originals=source.raws.store),ref)
        for ref in source.state['records']:covered.add(source.originals.path(source.originals.expand(ref)))
        if source.state['pending'] is not None:
            responsibilities.append('ui-source-acquisition');ref=source.state['pending']['original']
            if ref is not None:
                AssetsModelSources.prefix(source,ref)
                if ref['phase']!='planned':covered.add(source.originals.path(ref))
        sample_value=store_for(sample_path).read()
        if sample_value is None:
            need(wanted==covered);responsibilities.append('ui-screen-owner-birth')
        else:
            # Policy is external authority from the immutable sampled owner,
            # not a current screenshot/feature result. Its pixel/source joins
            # below must independently validate every actual returned sample.
            need(type(sample_value.get('policy')) is dict and same(sample_value['policy'],a.policy))
            samples=AssetsUiSamples(source,root,a.policy,SimpleNamespace(call=forbidden),forbidden,historical=True,metadata=metadata)
            covered.add(sample_path);attempts=[]
            for index,ref in enumerate(samples.record_references(),1):
                full=samples.originals.expand(ref);covered.add(samples.originals.path(full));row=samples.record(samples.originals.read(full),index);need(row['ticket']==a.ticket);attempts.append(row)
                if row['archive'] is not None:
                    for part in row['archive']['parts']:
                        for chunk in part['chunks']:
                            if chunk['phase']!='planned':covered.add(samples.raw.parts.store.path(chunk))
                need(row['status']=='returned')
                try:measured=samples.read(ref)['measured'];verdict=dict(index=index,qualified=True,measurement=measured)
                except MarkerNotReady as error:verdict=dict(index=index,qualified=False,rejection=deepcopy(error.observation))
                except AssertionError as error:
                    need(str(error)=='Feature subject is blank or uniform');verdict=dict(index=index,qualified=False,rejection=dict(reason='blank-original-subject'))
                results.append(verdict)
            pending=samples.state['pending']
            if pending is not None:
                responsibilities.append('ui-screen-acquisition');need(pending['ticket']==a.ticket);attempts.append(pending)
                if pending['archive'] is not None:
                    samples.raw.inspect(pending['archive'])
                    for part in pending['archive']['parts']:
                        for chunk in part['chunks']:
                            if chunk['phase']!='planned':covered.add(samples.raw.parts.store.path(chunk))
                if samples.state['original'] is not None:
                    samples.pending_original();ref=samples.state['original']
                    if ref['phase']!='planned':covered.add(samples.originals.path(ref))
            rows,remaining=screen_files(samples,covered)
            need(len(rows)<=len(attempts))
            for index,row in enumerate(rows):
                attempt=attempts[index];need(row['ticket']==attempt['ticket'])
                if attempt['png'] is not None:need(all(same(row[key],attempt['png'][key]) for key in row if key!='phase'))
                elif attempt['raw'] is not None:need('ios-'+row['nonce']==attempt['raw']['requestId'])
                else:need(attempt is pending and index==len(rows)-1)
            if remaining:responsibilities.append('ui-screen-files')
            if not any(row['qualified'] for row in results):responsibilities.append('ui-image-checkpoint')
        need(wanted==covered and metadata_coverage(covered,reads,metadata))
        for directory,names in before.items():need([p.name for p in sorted(metadata_entries(directory,metadata))]==names)
        a.directory_guard()
    return dict(assetsUiOwnershipVersion=1,runId=a.run,role='primary',checkpoint=a.checkpoint,subjectControl=a.subject,
        binding=deepcopy(a.binding),paths=covered,actualOriginalReads=set(reads),responsibilities=sorted(set(responsibilities)),
        images=results,currentNativeFactsProduced=False,wholeEndEligible=False)
