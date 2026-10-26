"""Read-only Tablet ownership fence before ordinary canonical SDK cleanup.

Only a complete actual native/OS/SDK/worker archive can report cleaned here.
Filename matches are unresolved responsibility cues, never product facts or
permission to start a live finalizer, Stop, remove files or delete a session.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
from pathlib import Path
import time
from adapters.native_feature_observation import need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import check,scope as transport_scope
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_completed import replay
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime

PREFIXES=('tabletweb-','tablet-web-','phase-publication-tablet-web-','phase-retirement-tablet-web-')


def roots(directory,config):
    result={directory:False}
    if type(config) is dict and 'tablet-web' in config.get('areas',[]):
        from ios.adapters.feature_configuration import validate
        from ios.adapters.tablet_web_configuration import settings
        validate(config);root=Path(settings(config['tabletWeb'])['artifactRoot'])
        result[root]=root!=directory
    return result


def cues(directory,*,entire=False):
    if not directory.exists():return set()
    entries=EmoteOriginalLease(directory,[]).rows;result=set()
    for name,row in entries.items():
        path=directory/name
        if entire and len(row)==9:result.add(path)
        elif Path(name).name.startswith(PREFIXES):
            if len(row)==9:result.add(path)
            else:
                children={directory/key for key,value in entries.items() if len(value)==9 and Path(key).is_relative_to(Path(name))}
                result.update(children or {path})
    return result


def owned(adapter,selector,config):
    return any(cues(root,entire=entire) for root,entire in roots(adapter.state_path(selector).parent,config).items())


def session_entry(function,*,monotonic=time.monotonic):
    @wraps(function)
    def invoke(adapter,selector):
        started=last=monotonic();failed=False
        from ios.adapters.feature_configuration import configuration
        if not owned(adapter,selector,configuration()):return function(adapter,selector)
        need(number(started,0,1e15))
        def budget():
            nonlocal last,failed
            now=monotonic()
            if failed or not number(now,last,started+60) or now>=started+60:
                failed=True;raise NativeUIError('Tablet canonical retirement deadline exhausted or host clock changed')
            last=now
        with transport_scope(budget):budget();answer=function(adapter,selector);budget();return answer
    return invoke


def retire_existing(runtime,selector,config):
    need(type(runtime) is IOSTabletWebRuntime);check();adapter=runtime.adapter;directory=runtime.state_path(selector).parent
    scopes=roots(directory,config);responsibility=set()
    for root,entire in scopes.items():responsibility.update(cues(root,entire=entire))
    if not responsibility:return None
    archives=sorted(directory.glob('tabletweb-final-archive-*.json'));need(1<=len(archives)<=64)
    lock=ScriptSourceLock(directory/'script-feature-sources.lock');members=set();bindings=[]
    with lock.held():
        for path in archives:
            run=identifier(path.name.removeprefix('tabletweb-final-archive-').removesuffix('.json'))
            check();actual=replay(runtime,selector,run,lock,check=check);members.update(actual['members'])
            bindings.append({key:value for key,value in actual['binding'].items() if key!='processIdentity'})
            for root in actual['roots']:scopes[root]=root!=directory
        for root,entire in scopes.items():need(cues(root,entire=entire)<=members)
        check();need(runtime.adapter is adapter and adapter.read_session(selector) is None and adapter._binding_store(selector).read() is None)
        # Historical proof cannot authorize outward cleanup after the selected
        # candidate changes during its potentially long complete graph read.
        for binding in bindings:
            check();need(runtime.adapter is adapter);adapter._retired_candidate_scope(selector,binding)
            check();need(runtime.adapter is adapter)
    check();return {'cleaned':True}
