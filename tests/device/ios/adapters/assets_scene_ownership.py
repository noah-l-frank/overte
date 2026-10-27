"""Readonly Scene/Peer WAL validation; an on-disk path grants no access.

Peer inspection requires the caller's already authorized primary directory.
Sources alone never retire the independently held peer parser/cache objects.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import re
import time
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from ios.adapters.assets_scene_sources import AssetsSceneSources,SceneRawSources,NAMES
from ios.adapters.assets_peer_owner import OwnedAssetsPeer

SCENE=re.compile(r'ios-assets-scene-([a-f0-9]{32})-(primary|actor|actor-primary)\.json')
PEER=re.compile(r'ios-assets-peer-([a-f0-9]{32})\.json')
FRAME=re.compile(r'assets-scene-(primary|actor|read-primary)-(native|source)-frame-sources-([a-f0-9]{32})-(primary|actor)-[0-9]{4}-[a-f0-9]{64}\.json')


def scene_path(name):return SCENE.fullmatch(name) is not None or PEER.fullmatch(name) is not None or FRAME.fullmatch(name) is not None


def forbidden(*_args,**_kwargs):raise RuntimeError('Historical Assets Scene inspection cannot acquire or write sources')


def source(path,value,run,role):
    binding=context(value.get('binding'));need(re.fullmatch('[1-9][0-9]{0,15}',binding['processIdentity']) is not None)
    owner=object.__new__(AssetsSceneSources);owner.store=PrivateFeatureState(path);owner.binding=deepcopy(binding);owner.run,owner.role=run,role
    owner.pid=int(binding['processIdentity']);owner.native=SimpleNamespace(pid=owner.pid,monotonic=time.monotonic)
    owner.storage_role='actor' if role=='actor' else 'primary';owner._cached=[];owner.previous=deepcopy(value)
    owner.raws=SceneRawSources(owner,lambda:True,forbidden)
    owner.originals=OriginalFrameStore(path.parent,binding,run,owner.storage_role,lambda:True,forbidden,
        namespace='assets-scene-'+NAMES[role]+'-source',schema_prefix='iosAssetsSceneSource')
    owner.state=owner.decode(value);covered=owner.raws.owned_paths()
    for reference in owner.state['frames']:covered.add(owner.originals.path(owner.originals.expand(reference)))
    pending=[row['pending'] for row in owner.state['interrupted']]+([] if owner.state['pending'] is None else [owner.state['pending']])
    for row in pending:
        if row['original'] is not None and row['original']['phase']!='planned':covered.add(owner.originals.path(row['original']))
    return owner,covered


def inspect_scenes(directory,entries,*,primary_directory=None):
    directory=Path(directory);sources={};actual={};peers={};retained=[];result=[]
    for path in entries:
        match=SCENE.fullmatch(path.name)
        if match:
            run,role=match.groups();value=PrivateFeatureState(path).read();need(type(value) is dict)
            owner,covered=source(path,value,run,role);sources[(run,role)]=(owner,covered);retained.append((path,value));continue
        match=FRAME.fullmatch(path.name)
        if match:
            name,_kind,run,storage=match.groups();role=next(key for key,value in NAMES.items() if value==name)
            need(storage==('actor' if role=='actor' else 'primary'));actual.setdefault((run,role),set()).add(path);continue
        match=PEER.fullmatch(path.name)
        if match:
            value=PrivateFeatureState(path).read();need(type(value) is dict);peers[match.group(1)]=(path,value);retained.append((path,value))
    need(len(sources)<=192 and len(peers)<=64 and set(actual)<=set(sources))
    for (run,role),(owner,covered) in sorted(sources.items()):
        need(actual.get((run,role),set())==covered)
        pending=owner.state['pending'] is not None or owner.raws.pending is not None
        responsibilities=['scene-source-write'] if pending else []
        if role=='actor':responsibilities.append('scene-peer-resources')
        result.append(dict(runId=run,role=role,binding=deepcopy(owner.binding),responsibilities=responsibilities,successor=False,clientRetired=False))
    if peers:
        # Never open the directory named by an untrusted WAL. Authorization is
        # supplied independently by the installed runtime's target mapping.
        need(primary_directory is not None);primary_directory=Path(primary_directory)
        need(primary_directory!=directory)
        from ios.adapters.assets_session_owners import inspect_directory,directory_entries
        contexts={};inspect_directory(primary_directory,_contexts=contexts)
        primary_entries=directory_entries(primary_directory)
        for run,(path,value) in sorted(peers.items()):
            need(value.get('primaryDirectory')==str(primary_directory) and (run,'primary') in contexts
                and (run,'actor') in sources and (run,'actor-primary') not in sources)
            primary_path=primary_directory/('ios-assets-scene-'+run+'-actor-primary.json')
            need(primary_path in primary_entries);primary_value=PrivateFeatureState(primary_path).read()
            primary,_covered=source(primary_path,primary_value,run,'actor-primary');peer=sources[(run,'actor')][0]
            parsed=contexts[(run,'primary')]['parsed'];need(parsed is not None
                and same(primary.binding,parsed.model.usage.source.binding)
                and primary.binding['targetFingerprint']!=peer.binding['targetFingerprint'] and primary.pid!=peer.pid)
            owner=object.__new__(OwnedAssetsPeer);owner.parsed,owner.primary,owner.peer=parsed,primary,peer
            owner.store=PrivateFeatureState(path);owner.run=run;owner.state=owner.decode(value)
            responsibilities=['peer-resource-retirement']
            if owner.state['result'] is None:responsibilities.append('peer-observation')
            result.append(dict(runId=run,role='actor',binding=deepcopy(peer.binding),responsibilities=responsibilities,successor=False,clientRetired=False))
            need(same(PrivateFeatureState(primary_path).read(),primary_value))
    for path,value in retained:need(same(PrivateFeatureState(path).read(),value))
    return result
