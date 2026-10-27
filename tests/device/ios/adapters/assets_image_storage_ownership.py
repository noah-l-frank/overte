"""Readonly ownership census for actual Storage/Source1 original journals.

This source is never a whole Resource retirement authority. Unknown original
queries and opened prefixes remain responsibilities; no query or input replays.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import re,time
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from ios.adapters.assets_image_storage_sources import AssetsImageReaderStorageSources,StorageRawSources

OWNER=re.compile(r'ios-assets-image-storage-([a-f0-9]{32})\.json')
FRAME=re.compile(r'assets-image-storage-(native|source)-frame-sources-([a-f0-9]{32})-primary-[0-9]{4}-[a-f0-9]{64}\.json')


def owned_prefix(name):return name.startswith(('ios-assets-image-storage-','assets-image-storage-'))

def storage_path(name):return OWNER.fullmatch(name) is not None or FRAME.fullmatch(name) is not None

def forbidden(*_args,**_kwargs):raise RuntimeError('Historical ImageReader storage inspection cannot query or write')


def inspect_storage(directory,entries):
    directory=Path(directory);owners={};actual={};retained=[];result=[]
    def pins():
        found={}
        for path in directory.iterdir():
            if not owned_prefix(path.name):continue
            need(storage_path(path.name));info=path.lstat()
            found[path]=(info.st_dev,info.st_ino,info.st_mode,info.st_nlink,info.st_uid,info.st_size,info.st_mtime_ns,info.st_ctime_ns)
        return found
    before=pins();need(set(before)=={path for path in entries if owned_prefix(path.name)})
    for path in entries:
        match=OWNER.fullmatch(path.name)
        if match:
            run=match.group(1);value=PrivateFeatureState(path).read();need(type(value) is dict)
            binding=context(value.get('binding'));need(re.fullmatch('[1-9][0-9]{0,15}',binding['processIdentity']) is not None)
            owner=object.__new__(AssetsImageReaderStorageSources)
            owner.store=PrivateFeatureState(path);owner.binding=deepcopy(binding);owner.run=run;owner.role=owner.storage_role='primary'
            owner.pid=int(binding['processIdentity']);owner.native=SimpleNamespace(pid=owner.pid,monotonic=time.monotonic)
            owner.readers=dict(storage=None,reader=None);owner.previous=deepcopy(value);owner._cached=[]
            owner.raws=StorageRawSources(owner,lambda:True,forbidden)
            owner.originals=OriginalFrameStore(directory,binding,run,'primary',lambda:True,forbidden,
                namespace='assets-image-storage-source',schema_prefix='iosAssetsImageStorageSource')
            owner.state=owner.decode(value);covered=owner.raws.owned_paths()
            for reference in owner.state['frames']:covered.add(owner.originals.path(owner.originals.expand(reference)))
            pending=[row['pending'] for row in owner.state['interrupted']]+([] if owner.state['pending'] is None else [owner.state['pending']])
            for row in pending:
                if row['original'] is not None and row['original']['phase']!='planned':covered.add(owner.originals.path(row['original']))
            owners[run]=(owner,covered);retained.append((path,value))
        match=FRAME.fullmatch(path.name)
        if match:actual.setdefault(match.group(2),set()).add(path)
    need(len(owners)<=64 and set(actual)<=set(owners))
    for run,(owner,covered) in sorted(owners.items()):
        need(actual.get(run,set())==covered)
        responsibilities=['image-storage-resource-retirement']
        if owner.state['pending'] is not None or owner.raws.pending is not None or owner.state['interrupted']:
            responsibilities.append('image-storage-source-write')
        result.append(dict(runId=run,role='primary',binding=deepcopy(owner.binding),responsibilities=responsibilities,
            successor=False,clientRetired=False))
    for path,value in retained:need(same(PrivateFeatureState(path).read(),value))
    need(before==pins());return result
