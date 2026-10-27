"""Read actual image ownership with independently supplied roots and parents.

No SDK/current clock/native command, write, artifact deletion or resource
retirement can be performed by this reader. Unknown or missing child data
remains blocking rather than becoming empty ownership.
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
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_file_reads import scope as read_scope,record as record_read
from adapters.original_frame_store import OriginalFrameStore
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import same,unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.assets_image_sample import AssetsImageSample,ImageRawSources
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput


@dataclass(frozen=True)
class ImageInventoryContext:
    """Caller authority, supplied separately from every retained envelope."""
    artifact_root: Path
    binding: dict
    run: str
    initial_ticket: str
    lock: ScriptSourceLock


def inventory_path(name):
    # Lifecycle originals are a separate closed namespace. This component
    # does not validate/retire them; the full Session reader must run their
    # independent ownership validator. Unknown lookalike names stay blocking.
    from ios.adapters.assets_image_reader_lifecycle_ownership import lifecycle_path
    from ios.adapters.assets_image_processing_ownership import processing_path
    if lifecycle_path(name) or processing_path(name):return False
    return name.startswith(('ios-assets-image-','assets-image-','ios-assets-marker-','assets-marker-'))


def forbidden(*_args,**_kwargs):raise RuntimeError('Historical Assets image inspection cannot acquire or mutate sources')


def sample_path(run,request):
    identifier(run);need(type(request) is str and re.fullmatch('ios-[a-f0-9]{32}',request))
    return 'ios-assets-image-'+run+'-primary-'+request[4:]+'.json'


def independent_context(directory,artifact_root,binding,run,lock,parsed,marker):
    directory,artifact_root=Path(directory),Path(artifact_root);context(binding);identifier(run)
    need(isinstance(lock,ScriptSourceLock) and isinstance(parsed,OwnedAssetsParsedInput) and isinstance(marker,OwnedAssetsMarker)
        and parsed.lock is marker.lock is lock and lock.path==directory/'script-feature-sources.lock'
        and parsed.store.path.parent==marker.store.path.parent==directory and marker.scope.root==artifact_root
        and same(parsed.sources.binding,binding) and same(marker.scope.binding,binding)
        and parsed.sources.run==marker.run==run and parsed.sources.role==marker.role=='primary')
    lock.assert_held();PrivateFeatureState(directory/'assets-image-read-boundary.json')._parent()
    PrivateFeatureState(artifact_root/'assets-image-read-boundary.json')._parent()
    return directory,artifact_root


def archived_sample(directory,artifact_root,binding,run,request,lock,parsed,marker):
    directory,artifact_root=independent_context(directory,artifact_root,binding,run,lock,parsed,marker)
    store=PrivateFeatureState(directory/sample_path(run,request));value=store.read();need(value is not None)
    child=VulkanWorldFrameOwner(PrivateFeatureState(directory/('graphics-world-frame-primary-0-'+request[4:]+'.json')),
        artifact_root,binding,run,'primary',0,request,forbidden,lambda:True,source_lock=lock)
    owner=object.__new__(AssetsImageSample)
    owner.store,owner.lock,owner.binding,owner.run,owner.role=store,lock,deepcopy(binding),run,'primary'
    owner.request,owner.pid,owner.active,owner.monotonic=request,int(binding['processIdentity']),False,time.monotonic
    owner.native=SimpleNamespace(monotonic=time.monotonic);owner.guard=forbidden;owner.parsed,owner.marker,owner.frame_owner=parsed,marker,child
    owner.previous=deepcopy(value);owner.raws=ImageRawSources(owner,'primary',owner.local_guard,forbidden)
    owner.frames=OriginalFrameStore(directory,binding,run,'primary',owner.local_guard,forbidden,
        namespace='assets-image-source',schema_prefix='iosAssetsImageSource')
    owner.originals=owner.frames;owner.state=owner.decode(value)
    return owner


def inspect_sample(directory,artifact_root,binding,run,request,lock,parsed,marker):
    """Typed current sample/WAL plus exact nested original and GPU coverage.

    This returns private responsibilities. It never supplies a current image,
    a whole-directory admission or Model/texture/renderer/OS retirement.
    """
    with read_scope(fresh=True) as actual_reads:
        owner=archived_sample(directory,artifact_root,binding,run,request,lock,parsed,marker);state=owner.state
        covered={owner.store.path}|owner.raws.owned_paths();responsibilities=[]
        if state['phase']=='reading':responsibilities.append('image-acquisition')
        if owner.raws.pending is not None:
            responsibilities.append('image-raw-source-write');reference=owner.raws.pending['original']
            if reference is not None:
                raw_context=SimpleNamespace(originals=owner.raws.store)
                observed=AssetsModelSources.prefix(raw_context,reference)
                if owner.raws.pending['snapshot'] is not None:need(same(observed,owner.raws.pending['snapshot']))
        if state['original'] is not None:
            if state['original']['phase']!='planned':covered.add(owner.frames.path(state['original']))
            if state['original']['phase']!='saved':responsibilities.append('image-logical-source-write')
        child=owner.frame_owner;current=child.store.read()
        if current is None:
            if state['gpuStarted']:responsibilities.append('image-gpu-unknown')
            need(state['frameOwnership'] is None)
        else:
            need(state['gpuStarted']);covered.add(child.store.path);child._load()
            prior=state['frameOwnership']
            if prior is not None:
                for key in ('binding','runId','role','stage','requestId','root','name','ticket','file','frame'):
                    need(same(prior[key],current[key]))
                old,new=unpack(prior['transcript']),unpack(current['transcript'])
                need(len(old)<=len(new) and same(old,new[:len(old)]))
            if child.state['phase']=='released':
                child.verify_owned_artifact()
            else:responsibilities.append('image-gpu')
            if child.state['file'] is not None:
                path=child.root/child.name;covered.add(path)
                # The shared reader checks current inode/permissions even for
                # an interrupted empty/partial PNG. It does not claim pixels.
                import os
                descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
                try:child._file(descriptor)
                finally:os.close(descriptor)
                record_read(path)
        need(covered<=actual_reads and same(owner.store.read(),owner.previous))
        if current is not None:need(same(child.store.read(),current))
        # Retained host originals and the separate marker/Model owners still
        # belong to the enclosing journey even when the native child is quiet.
        responsibilities.append('image-originals')
        return dict(owner=owner,paths=covered,responsibilities=responsibilities)


def inspect_directory(directory,artifact_root,binding,run,lock,parsed,marker):
    """Close this run's image namespaces; generic PNG peers remain separate.

    Other features may legitimately own generic Vulkan children in the same
    directory. Their whole-directory inventory must separately cover those
    nodes. This function never guesses their owner from a generic filename.
    """
    directory,artifact_root=independent_context(directory,artifact_root,binding,run,lock,parsed,marker)
    before=sorted(directory.iterdir(),key=lambda path:path.name);need(len(before)<=4096)
    owner_pattern=re.compile('ios-assets-image-'+run+r'-primary-([a-f0-9]{32})\.json')
    source_pattern=re.compile('assets-image-(native|source)-frame-sources-'+run+r'-primary-[0-9]{4}-[a-f0-9]{64}\.json')
    owners=[];wanted=set()
    for path in before:
        if path.name.startswith('ios-assets-image-'):
            match=owner_pattern.fullmatch(path.name);need(match is not None);owners.append((path,'ios-'+match[1]));wanted.add(path)
        elif path.name.startswith('assets-image-'):
            need(source_pattern.fullmatch(path.name) is not None);wanted.add(path)
    need(len(owners)<=32);covered=set();reports=[]
    for path,request in owners:
        report=inspect_sample(directory,artifact_root,binding,run,request,lock,parsed,marker)
        need(path in report['paths'] and not (covered&report['paths']));covered|=report['paths'];reports.append(report)
    need(wanted<=covered and [path.name for path in sorted(directory.iterdir(),key=lambda path:path.name)]==[path.name for path in before])
    return dict(owners=reports,paths=covered,responsibilities=[item for report in reports for item in report['responsibilities']])


def inspect_session(directory,authorization,parsed,fixture_url):
    """Compose the closed image inventory with the original released marker.

    An active/uncertain marker's current child metadata remains unavailable to
    this historical reader. Neither a root/ticket in its WAL nor absent image
    entries authorize skipping that separate original owner.
    """
    need(isinstance(authorization,ImageInventoryContext));a=authorization
    directory,root=Path(directory),Path(a.artifact_root);binding=context(a.binding)
    identifier(a.run);identifier(a.initial_ticket)
    need(isinstance(parsed,OwnedAssetsParsedInput) and isinstance(a.lock,ScriptSourceLock)
        and parsed.lock is a.lock and a.lock.path==directory/'script-feature-sources.lock'
        and same(parsed.sources.binding,binding) and parsed.sources.run==a.run and parsed.sources.role=='primary')
    a.lock.assert_held()
    with read_scope(fresh=True) as actual_reads:
        marker_store=PrivateFeatureState(directory/('ios-assets-marker-'+a.run+'-primary.json'))
        value=marker_store.read();need(value is not None)
        marker=OwnedAssetsMarker.from_archive(value,marker_store,artifact_root=root,binding=binding,run=a.run,
            role='primary',fixture_url=fixture_url,ticket=a.initial_ticket,lock=a.lock)
        need(marker.state['phase']=='released' and marker.state['pending'] is None)
        # Actual ordinary cleanup discards these two child ledgers. A retained
        # one is not silently classified as an already retired child.
        for kind in ('files','script'):need(marker.scope.marker_store(kind).read() is None)
        marker_paths=set()
        for parent in {directory,root}:
            entries=list(parent.iterdir());need(len(entries)<=4096)
            marker_paths|={path for path in entries if path.name.startswith(('ios-assets-marker-','assets-marker-'))}
        need(marker_store.path in marker_paths and marker.scope.store.path in marker_paths and marker_paths<=actual_reads)
        report=inspect_directory(directory,root,binding,a.run,a.lock,parsed,marker)
        need(same(marker.store.read(),value))
        return dict(runId=a.run,role='primary',binding=deepcopy(binding),
            responsibilities=['marker-originals']+report['responsibilities'],successor=False,clientRetired=False,
            paths=marker_paths|report['paths'])
