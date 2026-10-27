"""Closed Source3 rotation profile with frozen child heads, never Ready.

Only a currently literal Source1/2 owner can prepare this profile. Its nine
child tails are independent originals. Read-only restoration validates their
actual heads and every literal original before returning historical floors.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
import time

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import record as original_read
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES,LIMIT
from adapters.script_feature.history import same,canonical
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_rotation_fence as base
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner,ORDER

VERSION=1
PROFILE='tabletweb-native-child-prefix'


def _signature(value):
    return dict(device=value.st_dev,inode=value.st_ino,mode=value.st_mode,uid=value.st_uid,gid=value.st_gid,
        nlink=value.st_nlink,bytes=value.st_size,mtimeNs=value.st_mtime_ns,ctimeNs=value.st_ctime_ns)


def _raw(path):
    path=Path(path);PrivateFeatureState(path)._parent();before=path.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.geteuid()
        and stat.S_IMODE(before.st_mode)==0o600 and before.st_size<=base.MAX_HEAD_BYTES)
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(descriptor,'rb') as stream:
        need(_signature(os.fstat(stream.fileno()))==_signature(before))
        raw=stream.read(base.MAX_HEAD_BYTES+1)
        need(_signature(os.fstat(stream.fileno()))==_signature(before)==_signature(path.lstat()))
    need(len(raw)==before.st_size);original_read(path);return raw,_signature(before)


def _name(component,expected):
    need(component in ORDER)
    return 'tabletweb-'+component+'-queries-'+expected['runId']+'-'+expected['role']+'.json'


def make(source):
    """Prepare metadata before CAS; never enrich a pre-existing Source3 fence."""
    need(type(source) is TabletWebSourceOwner and not source.historical);source.lock.assert_held();source.bound()
    expected=base.scope(source.binding,source.run,source.role,source.fixture,source.pid)
    need(same(source.store.read(),source.saved) and same(source.saved,source.state)
        and type(source.state.get('tabletWebSourceOwnerVersion')) is int and source.state['tabletWebSourceOwnerVersion'] in (1,2))
    lease=EmoteOriginalLease(source.root,[]);source.history()
    need(not source.blocked)
    need(same(source.store.read(),source.saved) and same(source.saved,source.state))
    raw,signature=_raw(source.store.path);parent=base.make(raw,signature,expected);children=[]
    for component in ORDER:
        child=source.children[component];packets=child.history()
        need(child.historical is False and not child.blocked and child.state['pending'] is child.state['recordIntent'] is child.state['recordInspection'] is None
            and child.store.path==source.root/_name(component,expected)
            and same(child.store.read(),child.saved) and same(child.saved,child.state))
        old,identity=_raw(child.store.path);records=child.state['records']
        children.append(dict(component=component,headerName=_name(component,expected),signature=identity,
            sha256=hashlib.sha256(old).hexdigest(),version=child.state['tabletWebPacketsVersion'],
            count=len(records),lastRecord=None if not records else deepcopy(records[-1]),nextRaw=child.state['nextRaw']))
        need(bool(packets)==bool(records))
    lease.guard()
    value=dict(tabletWebSourceOwnerVersion=3,phase='rotating',tabletWebChildRotationVersion=VERSION,
        profile=PROFILE,scope=expected,parent=parent,children=children,copyIntent=None)
    decode(value,expected);return value


def decode(value,expected):
    expected=base._scope(expected)
    exact(value,{'tabletWebSourceOwnerVersion','phase','tabletWebChildRotationVersion','profile','scope','parent','children','copyIntent'})
    need(type(value['tabletWebSourceOwnerVersion']) is int and value['tabletWebSourceOwnerVersion']==3
        and value['phase']=='rotating' and type(value['tabletWebChildRotationVersion']) is int
        and value['tabletWebChildRotationVersion']==VERSION and value['profile']==PROFILE and same(value['scope'],expected))
    parent=value['parent'];need(type(parent) is dict and 'tabletWebChildRotationVersion' not in parent and parent.get('copyIntent') is None)
    raw=base.decode(parent,expected)
    need(type(value['children']) is list and len(value['children'])==len(ORDER))
    for component,child in zip(ORDER,value['children']):
        exact(child,{'component','headerName','signature','sha256','version','count','lastRecord','nextRaw'})
        need(child['component']==component and child['headerName']==_name(component,expected)
            and type(child['version']) is int and child['version'] in (1,2)
            and type(child['count']) is int and 0<=child['count']<=128
            and type(child['nextRaw']) is int and 1<=child['nextRaw']<=MAX_FRAMES+1
            and type(child['sha256']) is str and len(child['sha256'])==64 and all(c in '0123456789abcdef' for c in child['sha256']))
        base._signature(child['signature'],child['signature']['bytes'])
        need(0<child['signature']['bytes']<=base.MAX_HEAD_BYTES)
        if child['count']==0:need(child['lastRecord'] is None)
        else:
            ref=child['lastRecord'];exact(ref,{'index','sha256','bytes','device','inode'})
            need(type(ref['index']) is int and ref['index']==child['count']
                and type(ref['sha256']) is str and len(ref['sha256'])==64 and all(c in '0123456789abcdef' for c in ref['sha256'])
                and type(ref['bytes']) is int and 2<=ref['bytes']<=LIMIT
                and type(ref['device']) is int and ref['device']>=0 and type(ref['inode']) is int and ref['inode']>0)
    if value['copyIntent'] is not None:base._copy(value['copyIntent'],expected)
    need(len(canonical(value))+1<=base.MAX_HEAD_BYTES);return raw


def copy_body(value,expected):
    decode(value,expected)
    return dict(tabletWebChildClosedHeaderBodyVersion=VERSION,profile=PROFILE,scope=deepcopy(value['scope']),
        parent=deepcopy(value['parent']),children=deepcopy(value['children']))


def with_copy_intent(value,kind,intent,expected):
    decode(value,expected);proxy=deepcopy(value['parent']);proxy['copyIntent']=deepcopy(value['copyIntent'])
    changed=base.with_copy_intent(proxy,kind,intent,expected);result=deepcopy(value)
    result['copyIntent']=changed['copyIntent'];decode(result,expected);return result


def restore(root,binding,run,role,fixture_url,pid,lock,*,monotonic=time.monotonic):
    """Return original historical tails only; canonical head stays rotating."""
    root=Path(root);expected=base.scope(binding,run,role,fixture_url,pid)
    need(isinstance(lock,ScriptSourceLock) and lock.path==root/'script-feature-sources.lock');lock.assert_held()
    head=PrivateFeatureState(root/('tabletweb-source-owner-'+run+'-'+role+'.json'));value=head.read()
    raw=decode(value,expected);reference=value['copyIntent']
    need(reference is not None and reference['phase'] in ('opened','saved'))
    lease=EmoteOriginalLease(root,[])
    current_children={};dom_prefix=None;dom_state=None;dom_reader=None;dom_changed=None
    uikit_state=None;uikit_changed=None;native_states={};native_proofs={}
    def forbidden(*_args,**_kwargs):need(False)
    for child in value['children']:
        old,signature=_raw(root/child['headerName']);digest=hashlib.sha256(old).hexdigest()
        current_children[child['component']]=(signature,digest)
        if signature==child['signature'] and digest==child['sha256']:continue
        # Each changed child needs its own original proof. A DOM subgraph
        # cannot authorize UIKit or the whole Source selector.
        changed=PrivateFeatureState(root/child['headerName']).read()
        if child['component'] not in ('dom','uikit'):
            from ios.adapters.tablet_web_native_child_continuation import decode as native_decode,read_own
            native_raw,native_state=native_decode(changed,expected,child['component'])
            need(changed['previousHeader']['signature']==child['signature'] and hashlib.sha256(native_raw).hexdigest()==child['sha256'])
            native_states[child['component']]=native_state
            continue
        if child['component']=='uikit':
            from ios.adapters.tablet_web_uikit_continuation import (decode as uikit_decode,BOUND_VERSION as UIKIT_BOUND,
                ACTIVE_VERSION as UIKIT_ACTIVE,VERSION as UIKIT_INITIAL)
            uikit_raw,uikit_state=uikit_decode(changed,expected)
            need(changed['tabletWebUIKitContinuationVersion'] in (UIKIT_BOUND,UIKIT_ACTIVE,UIKIT_INITIAL)
                and changed['previousHeader']['signature']==child['signature']
                and hashlib.sha256(uikit_raw).hexdigest()==child['sha256'])
            uikit_changed=changed
            continue
        from ios.adapters.tablet_web_dom_continuation import (TabletDOMClosedPrefix,decode as dom_decode,FENCE_VERSION as DOM_VERSION,
            ACTIVE_VERSION,VERSION as INITIAL_VERSION)
        dom_raw,dom_state=dom_decode(changed,expected)
        need(changed['tabletWebDOMContinuationVersion'] in (DOM_VERSION,ACTIVE_VERSION,INITIAL_VERSION))
        need((changed['tabletWebDOMContinuationVersion']==INITIAL_VERSION or changed['successor'] is not None)
            and changed['previousHeader']['signature']==child['signature']
            and hashlib.sha256(dom_raw).hexdigest()==child['sha256'])
        dom_changed=changed
    dom_proof=None;uikit_proof=None
    for name in native_states:
        native_proofs[name]=read_own(root,binding,run,role,fixture_url,pid,name,lock,monotonic=monotonic)
        need(native_proofs[name]['component']==name and native_proofs[name]['subgraphOnly'] is True
            and native_proofs[name]['peerAuthority'] is False)
    if uikit_state is not None:
        need(dom_state is not None)
        from ios.adapters.tablet_web_dom_original_link import read as dom_original_link
        from ios.adapters.tablet_web_uikit_continuation import TabletUIKitClosedPrefix
        dom_proof=dom_original_link(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
        need(dom_proof['component']=='dom' and dom_proof['subgraphOnly'] is True and dom_proof['peerAuthority'] is False)
        if uikit_changed['tabletWebUIKitContinuationVersion']==UIKIT_BOUND:
            uikit_prefix=TabletUIKitClosedPrefix(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
            need(same(uikit_prefix.old,uikit_state));uikit_proof=uikit_prefix.adopted()
        else:
            need(uikit_changed['tabletWebUIKitContinuationVersion'] in (UIKIT_ACTIVE,UIKIT_INITIAL))
            from ios.adapters.tablet_web_uikit_segment import TabletUIKitSegment
            uikit_reader=TabletUIKitSegment(root,binding,run,role,fixture_url,pid,lock,forbidden,
                monotonic=monotonic,epoch_ms=forbidden,historical=True)
            packets=uikit_reader.history()
            need(not uikit_reader.blocked and packets and same(uikit_reader.closed.old,uikit_state)
                and uikit_reader.state['pending'] is uikit_reader.state['recordIntent'] is uikit_reader.state['recordInspection'] is None)
            uikit_proof=dict(nativeFloor=deepcopy(packets[-1]))
    elif dom_changed is not None:
        if dom_changed['tabletWebDOMContinuationVersion']==DOM_VERSION:
            dom_prefix=TabletDOMClosedPrefix(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
        else:
            need(dom_changed['tabletWebDOMContinuationVersion'] in (ACTIVE_VERSION,INITIAL_VERSION))
            from ios.adapters.tablet_web_dom_segment import TabletDOMSegment
            dom_reader=TabletDOMSegment(root,binding,run,role,fixture_url,pid,lock,forbidden,monotonic=monotonic,
                epoch_ms=forbidden,historical=True)
            dom_reader.history()
            need(not dom_reader.blocked and dom_reader.state['pending'] is dom_reader.state['recordIntent'] is dom_reader.state['recordInspection'] is None)
    def unchanged():
        lock.assert_held();lease.guard();need(same(head.read(),value))
        for child in value['children']:
            old,signature=_raw(root/child['headerName'])
            expected_signature,expected_digest=current_children[child['component']]
            need(signature==expected_signature and hashlib.sha256(old).hexdigest()==expected_digest)
        return True
    copies=OriginalFrameStore(root,binding,run,role,unchanged,forbidden,
        namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=monotonic)
    need(same(copies.read(reference),copy_body(value,expected)));unchanged()
    if dom_prefix is not None:dom_proof=dom_prefix.adopted()
    unchanged()
    # The capsule bytes remain literal. Parsing them is not a newer Source3
    # ready state and never authorizes native/channel capture.
    state=base._legacy(raw,expected)
    owner=TabletWebSourceOwner._closed_snapshot(root,binding,run,role,fixture_url,pid,lock,state,
        monotonic=monotonic,closed_dom_state=dom_state if dom_reader is None else None,closed_dom_reader=dom_reader,
        closed_uikit_state=uikit_state,closed_native_states=native_states or None)
    need(not owner.blocked);frames=owner.history();tails={}
    for child in value['children']:
        component=child['component'];actual=owner.children[component];packets=actual.history()
        if (dom_reader is not None and component!='dom') or uikit_proof is not None or native_proofs:
            need(all(actual.originals.read(actual.originals.expand(ref))['status']=='returned' for ref in actual.state['records']))
        legacy=actual.closed.old if component=='dom' and dom_reader is not None else actual.state
        need(not actual.blocked and actual.state['pending'] is actual.state['recordIntent'] is actual.state['recordInspection'] is None
            and legacy['tabletWebPacketsVersion']==child['version'] and len(legacy['records'])==child['count']
            and legacy['nextRaw']==child['nextRaw']
            and same(None if not legacy['records'] else legacy['records'][-1],child['lastRecord']))
        tails[component]=(deepcopy(native_proofs[component]['nativeFloor']) if component in native_proofs
            else deepcopy(uikit_proof['nativeFloor']) if component=='uikit' and uikit_proof is not None
            else deepcopy(dom_proof['nativeFloor']) if component=='dom' and dom_proof is not None
            else None if not packets else deepcopy(packets[-1]))
    result=dict(historicalOnly=True,phase='rotating',scope=deepcopy(expected),globalIndex=len(state['records']),
        lastRecord=None if not state['records'] else deepcopy(state['records'][-1]),nativeFloor=deepcopy(owner.native_floor),
        phaseFloor=deepcopy(owner.phase_floor),children=tails,frames=deepcopy(frames))
    unchanged();return result
