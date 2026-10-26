"""Historical Assets ownership before ordinary installed session operations.

The existing owner decoders inspect original private data without constructing
live transports. No SDK, candidate read, native query, input, timestamp or
retirement is produced here. An upload's client retirement never establishes
server/oven/blob retirement; that outstanding responsibility remains blocking.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
from pathlib import Path
import re
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.assets_files import OwnedAssetsFiles
from ios.adapters.assets_picker import OwnedAssetsPicker
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.assets_upload import OwnedAssetsUpload

OWNER=re.compile(r'ios-assets-([a-f0-9]{32})-(primary|actor)-(files|picker|replies|upload)\.json')
FRAME=re.compile(r'assets-upload-frame-sources-([a-f0-9]{32})-(primary|actor)-[0-9]{4}-[a-f0-9]{64}\.json')


def forbidden(*_args,**_kwargs):raise RuntimeError('Historical Assets inspection cannot acquire or write sources')


def directory_entries(directory):
    directory=Path(directory)
    if not directory.exists():return []
    PrivateFeatureState(directory/'assets-read-boundary.json')._parent()
    result=list(directory.iterdir());need(len(result)<=4096);return sorted(result,key=lambda path:path.name)


def inspect_directory(directory):
    """Return private responsibilities, not fresh product-state observations."""
    directory=Path(directory);entries=directory_entries(directory);groups={};frame_paths={}
    for path in entries:
        match=OWNER.fullmatch(path.name)
        if match:
            run,role,kind=match.groups();identifier(run);groups.setdefault((run,role),{})[kind]=(path,PrivateFeatureState(path).read());continue
        match=FRAME.fullmatch(path.name)
        if match:frame_paths.setdefault(match.groups(),set()).add(path);continue
        need(not path.name.startswith(('ios-assets-','assets-upload-')))
    need(len(groups)<=64 and set(frame_paths)<=set(groups));result=[]
    for (run,role),records in sorted(groups.items()):
        need(all(type(value) is dict for _path,value in records.values()))
        values={kind:value for kind,(_path,value) in records.items()};bindings=[context(value.get('binding')) for value in values.values()]
        need(bindings and all(same(bindings[0],binding) for binding in bindings));binding=bindings[0]
        need(re.fullmatch('[1-9][0-9]{0,15}',binding['processIdentity']) is not None);pid=int(binding['processIdentity'])
        urls=[value['fixtureUrl'] for kind,value in values.items() if kind in ('files','replies')]
        need(urls and all(url==urls[0] for url in urls));url=urls[0]
        # These are pure codec contexts, not alternate/live managers. Their
        # constructors are deliberately not called; no transports or clocks
        # can be acquired, and every attempted write is explicitly forbidden.
        files=object.__new__(OwnedAssetsFiles);files.native=SimpleNamespace(pid=pid);files.run,files.url,files.binding=run,url,deepcopy(binding)
        files.state=None
        if 'files' in values:files.state=files.decode(values['files'])
        picker=object.__new__(OwnedAssetsPicker);picker.files,picker.binding=files,deepcopy(binding);picker.state=None
        if 'picker' in values:
            need(files.state is not None);picker.state=picker.decode(values['picker'])
        replies=object.__new__(OwnedAssetsReplyReads);replies.native=SimpleNamespace(pid=pid);replies.run,replies.url,replies.binding=run,url,deepcopy(binding);replies.state=None
        if 'replies' in values:replies.state=replies.decode(values['replies'])
        upload=None;covered=set()
        if 'upload' in values:
            need(files.state is not None and picker.state is not None and replies.state is not None)
            upload=object.__new__(OwnedAssetsUpload);upload.files,upload.picker,upload.replies=files,picker,replies
            upload.binding,upload.role,upload.clock=deepcopy(binding),role,SimpleNamespace(pid=pid)
            upload.state=None;upload._cached=[];upload._validated_refs=[];upload._projects=[]
            upload.originals=OriginalFrameStore(directory,binding,run,role,lambda:True,forbidden,namespace='assets-upload',schema_prefix='iosAssetsUpload')
            upload.state=upload.decode(values['upload']);state=upload.state
            need(picker.state['phase']=='primary-chosen' and state['page']==picker.state['page'] and state['picker']==picker.state['picker'])
            for ref in state['frames']:covered.add(upload.originals.path(upload.originals.expand(ref)))
            if state['pending'] is not None and state['pending']['original'] is not None:covered.add(upload.originals.path(state['pending']['original']))
        need(frame_paths.get((run,role),set())==covered)
        responsibilities=[]
        if files.state is not None and files.state['phase']!='retired':responsibilities.append('input-files')
        if picker.state is not None and picker.state['phase']!='retired' and upload is None:responsibilities.append('picker')
        if replies.state is not None and replies.state['phase']!='closed':responsibilities.append('read-leases')
        if upload is not None:
            if upload.state['phase']!='retired':responsibilities.append('upload-client')
            # No server/oven/blob retirement owner exists in this partial
            # vertical. Local staged-file absence cannot discharge that work.
            responsibilities.append('server-retirement')
        result.append(dict(runId=run,role=role,binding=deepcopy(binding),responsibilities=responsibilities,
            successor=upload is not None,clientRetired=upload is not None and upload.state['phase']=='retired'))
        for kind,(path,value) in records.items():need(same(PrivateFeatureState(path).read(),value))
    need([path.name for path in directory_entries(directory)]==[path.name for path in entries]);return result


def owners_absent(adapter,selector):
    return not any(row['responsibilities'] for row in inspect_directory(adapter.state_path(selector).parent))


def ensure_released(adapter,selector):
    need(owners_absent(adapter,selector));return True


def installed_entry(function):
    @wraps(function)
    def invoke(adapter,selector,operation,values):
        ensure_released(adapter,selector);return function(adapter,selector,operation,values)
    return invoke
