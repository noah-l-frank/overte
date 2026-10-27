"""Closed UIKit128, bound129 and explicit initial/active segments, no Ready.

Every contact/object/dispatch field is replayed by the literal UIKit reader.
Storage closure does not prove contact release, quiescence or weak retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
from pathlib import Path
import time
import zlib

from adapters.native_feature_observation import decode as json_decode,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES
from adapters.script_feature.history import canonical,same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_child_rotation as children,tablet_web_rotation_fence as base
from ios.adapters import tablet_web_dom_original_link as dom_link
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_packets import TabletWebPackets,CAPTURES,COMPONENTS

VERSION=4
READS=(1,2,3,4)
ACTIVE_VERSION=3
BOUND_VERSION=2
BODY_VERSION=1
FENCE_VERSION=1
PROFILE='tabletweb-uikit-closed-prefix'


def _old(raw,expected):
    value=json_decode(raw.decode('utf-8'),limit=base.MAX_HEAD_BYTES)
    exact(value,{'tabletWebPacketsVersion','binding','runId','role','fixtureUrl','processId','component',
        'nextRaw','records','pending','recordIntent','recordInspection'})
    need(type(value['tabletWebPacketsVersion']) is int and value['tabletWebPacketsVersion'] in (1,2)
        and all(same(value[key],expected[key]) for key in expected) and value['component']=='uikit'
        and type(value['records']) is list and len(value['records'])==CAPTURES
        and integer(value['nextRaw'],1,MAX_FRAMES+1)
        and value['pending'] is value['recordIntent'] is value['recordInspection'] is None)
    return value


def decode(value,expected):
    expected=base._scope(expected)
    version=value.get('tabletWebUIKitContinuationVersion') if type(value) is dict else None
    need(type(version) is int and version in READS)
    exact(value,{'tabletWebPacketsVersion','tabletWebUIKitContinuationVersion','profile','phase','scope',
        'parent','previousHeader','copyIntent','manifests','manifestIntent'}|({'successor'} if version>=2 else set())|({'active'} if version>=3 else set()))
    need(type(value['tabletWebPacketsVersion']) is int and value['tabletWebPacketsVersion']==3
        and type(value['tabletWebUIKitContinuationVersion']) is int and value['tabletWebUIKitContinuationVersion'] in READS
        and value['profile']==PROFILE and value['phase']=='rotating' and same(value['scope'],expected))
    parent=value['parent'];exact(parent,{'signature','sha256'});base._signature(parent['signature'],parent['signature']['bytes'])
    need(type(parent['sha256']) is str and len(parent['sha256'])==64 and all(c in '0123456789abcdef' for c in parent['sha256']))
    prior=value['previousHeader'];exact(prior,{'signature','sha256','data','bytes'})
    need(integer(prior['bytes'],1,base.MAX_HEAD_BYTES) and type(prior['data']) is str and len(prior['data'])<=base.MAX_HEAD_BYTES)
    try:
        packed=base64.b64decode(prior['data'],validate=True);need(base64.b64encode(packed).decode('ascii')==prior['data'])
        stream=zlib.decompressobj();raw=stream.decompress(packed,prior['bytes']+1)
    except (ValueError,zlib.error):need(False)
    need(len(raw)==prior['bytes'] and stream.eof and not stream.unused_data and not stream.unconsumed_tail
        and hashlib.sha256(raw).hexdigest()==prior['sha256'])
    base._signature(prior['signature'],len(raw));old=_old(raw,expected)
    need(type(value['manifests']) is list and len(value['manifests'])<=1)
    for ref in value['manifests']:OriginalFrameStore.manifest_reference(ref);need(ref['block']==1)
    intent=value['manifestIntent']
    if intent is not None:
        exact(intent,{'tabletWebSourcePacketManifestVersion','reference','phase'})
        need(type(intent['tabletWebSourcePacketManifestVersion']) is int and intent['tabletWebSourcePacketManifestVersion']==1
            and intent['phase'] in ('planned','saved'))
        ref=intent['reference'];OriginalFrameStore.manifest_reference(ref)
        need(ref['block']==1 and ref['count']==(value['manifests'][0]['count'] if value['manifests'] else 0)+1)
    if value['copyIntent'] is not None:base._copy(value['copyIntent'],expected)
    if version>=2:
        ref=value['successor']
        if ref is None:need(version==VERSION)
        else:
            exact(ref,{'index','sha256','bytes','device','inode'})
            need(type(ref['index']) is int and ref['index']==CAPTURES+1 and integer(ref['bytes'],2,1048576)
                and integer(ref['device'],0,2**64-1) and integer(ref['inode'],1,2**64-1)
                and type(ref['sha256']) is str and len(ref['sha256'])==64 and all(c in '0123456789abcdef' for c in ref['sha256']))
    if version>=3:
        from ios.adapters.tablet_web_uikit_segment import segment_header
        need(value['manifestIntent'] is None and len(value['manifests'])==1 and value['manifests'][0]['count']==CAPTURES
            and value['copyIntent'] is not None and value['copyIntent']['phase'] in ('opened','saved'))
        segment_header(value['active'],expected,value['successor'])
        need(value['active']['tabletWebUIKitActiveSegmentVersion']==(1 if version==ACTIVE_VERSION else 2))
        if version==VERSION and not value['active']['records'] and value['active']['pending'] is None:
            need(value['active']['nextRaw']==old['nextRaw']
                and value['active']['recordIntent'] is value['active']['recordInspection'] is None)
    need(len(canonical(value))+1<=base.MAX_HEAD_BYTES);return raw,old


def _snapshot(root,expected,state,monotonic):
    reader=object.__new__(TabletWebPackets);reader.root=Path(root);reader.binding=deepcopy(context(expected['binding']))
    reader.run,reader.role,reader.fixture,reader.pid=expected['runId'],expected['role'],expected['fixtureUrl'],expected['processId']
    reader.component,reader.module='uikit',COMPONENTS['uikit']
    def forbidden(*_args,**_kwargs):need(False)
    reader.guard=reader.storage_guard=reader.epoch_ms=forbidden;reader.monotonic=monotonic;reader.historical=True;reader.clock=None
    reader.store=PrivateFeatureState(reader.root/children._name('uikit',expected));reader.state=deepcopy(state);reader.saved=deepcopy(state)
    reader._original_storage();reader.history();return reader


def prepare(source):
    source.bound();expected=base.scope(source.binding,source.run,source.role,source.fixture,source.pid)
    lease=EmoteOriginalLease(source.root,[]);parent_raw,parent_signature=children._raw(source.store.path)
    proof=children.restore(source.root,source.binding,source.run,source.role,source.fixture,source.pid,source.lock,monotonic=source.monotonic)
    child=source.children['uikit'];packets=child.history();need(not child.historical and not child.blocked and packets
        and same(packets[-1],proof['children']['uikit']) and same(child.store.read(),child.saved) and same(child.saved,child.state))
    raw,signature=children._raw(child.store.path);old=_old(raw,expected)
    need(all(child.originals.read(child.originals.expand(ref))['status']=='returned' for ref in old['records']))
    parent=source.store.read();children.decode(parent,expected);descriptor=next(row for row in parent['children'] if row['component']=='uikit')
    need(signature==descriptor['signature'] and hashlib.sha256(raw).hexdigest()==descriptor['sha256'])
    value=dict(tabletWebPacketsVersion=3,tabletWebUIKitContinuationVersion=FENCE_VERSION,profile=PROFILE,phase='rotating',scope=expected,
        parent=dict(signature=parent_signature,sha256=hashlib.sha256(parent_raw).hexdigest()),
        previousHeader=dict(signature=signature,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
            data=base64.b64encode(zlib.compress(raw,9)).decode('ascii')),copyIntent=None,manifests=[],manifestIntent=None)
    decode(value,expected);lease.guard();return value


def install(source,value):
    need(same(prepare(source),value));child=source.children['uikit'];raw,signature=children._raw(child.store.path)
    need(signature==value['previousHeader']['signature'] and hashlib.sha256(raw).hexdigest()==value['previousHeader']['sha256'])
    child.store.write(value,child.saved)


def read_barrier(value,binding,run,role,fixture_url,pid,component):
    need(component=='uikit');decode(value,base.scope(binding,run,role,fixture_url,pid))
    raise base.TabletHeaderRotating('UIKit original prefix remains fenced; acquisition is unavailable')


class TabletUIKitClosedPrefix:
    def __init__(self,root,binding,run,role,fixture_url,pid,lock,*,monotonic=time.monotonic):
        self.root=Path(root);self.expected=base.scope(binding,run,role,fixture_url,pid);self.lock,self.monotonic=lock,monotonic
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.root/'script-feature-sources.lock');lock.assert_held()
        lease=EmoteOriginalLease(root,[])
        self.store=PrivateFeatureState(self.root/children._name('uikit',self.expected));self.state=self.store.read()
        self.raw,self.old=decode(self.state,self.expected)
        self.dom_path=self.root/children._name('dom',self.expected);raw,signature=children._raw(self.dom_path)
        dom_link.read(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
        self.dom_identity=signature;self.dom_sha=hashlib.sha256(raw).hexdigest();lease.guard()
        self.copies=OriginalFrameStore(root,binding,run,role,self.guard,self.intent,
            namespace='tabletweb-uikit-closed',schema_prefix='tabletWebClosedHeader',monotonic=monotonic)
        self.records=OriginalFrameStore(root,binding,run,role,self.guard,self.intent,
            namespace='tabletweb-uikit-packets',schema_prefix='tabletWebSourcePacket',monotonic=monotonic)
        self.guard()

    def guard(self):
        self.lock.assert_held();need(same(self.store.read(),self.state));raw,old=decode(self.state,self.expected)
        need(raw==self.raw and same(old,self.old));expected=self.expected
        path=self.root/('tabletweb-source-owner-'+expected['runId']+'-'+expected['role']+'.json');raw,signature=children._raw(path)
        need(signature==self.state['parent']['signature'] and hashlib.sha256(raw).hexdigest()==self.state['parent']['sha256'])
        parent=PrivateFeatureState(path).read();children.decode(parent,expected);reference=parent['copyIntent']
        need(reference is not None and reference['phase'] in ('opened','saved'))
        def locked():self.lock.assert_held();return True
        def forbidden(*_args,**_kwargs):need(False)
        copies=OriginalFrameStore(self.root,expected['binding'],expected['runId'],expected['role'],locked,forbidden,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=self.monotonic)
        need(same(copies.read(reference),children.copy_body(parent,expected)))
        for child in parent['children']:
            if child['component']=='uikit':
                need(child['signature']==self.state['previousHeader']['signature'] and child['sha256']==self.state['previousHeader']['sha256']
                    and child['lastRecord']==self.old['records'][-1] and child['nextRaw']==self.old['nextRaw'])
            else:
                actual,identity=children._raw(self.root/child['headerName'])
                prior,sha=(self.dom_identity,self.dom_sha) if child['component']=='dom' else (child['signature'],child['sha256'])
                need(identity==prior and hashlib.sha256(actual).hexdigest()==sha)
        return True

    def body(self):
        return dict(tabletWebUIKitClosedBodyVersion=BODY_VERSION,profile=PROFILE,scope=deepcopy(self.expected),
            parent=deepcopy(self.state['parent']),previousHeader=deepcopy(self.state['previousHeader']))

    def save(self,value):
        self.guard();decode(value,self.expected);self.store.write(value,self.state);self.state=deepcopy(value)

    def intent(self,kind,value):
        changed=deepcopy(self.state)
        if kind=='original':
            base._copy(value,self.expected);previous=changed['copyIntent']
            if previous is None:need(value['phase']=='planned')
            else:need((previous['phase'],value['phase']) in (('planned','opened'),('opened','saved'))
                and all(same(value[key],previous[key]) for key in value if key not in ('phase','file'))
                and (previous['file'] is None or same(previous['file'],value['file'])))
            changed['copyIntent']=deepcopy(value)
        else:
            need(kind=='manifest');previous=changed['manifestIntent']
            if previous is None:need(value['phase']=='planned')
            else:need(previous['phase']=='planned' and value['phase']=='saved' and same(previous['reference'],value['reference']))
            changed['manifestIntent']=deepcopy(value)
        self.save(changed)

    def copy(self):
        need(self.state['copyIntent'] is None);return self.copies.write(1,self.body())

    def index(self):
        need(self.state['copyIntent'] is not None and self.state['copyIntent']['phase']=='saved'
            and same(self.copies.read(self.state['copyIntent']),self.body()) and self.state['manifestIntent'] is None)
        count=self.state['manifests'][0]['count'] if self.state['manifests'] else 0
        for reference in self.old['records'][count:]:
            refs=self.records.append(self.state['manifests'],reference);changed=deepcopy(self.state)
            changed.update(manifests=refs,manifestIntent=None);self.save(changed)

    def history(self):
        self.guard();lease=EmoteOriginalLease(self.root,[])
        need(self.state['copyIntent'] is not None and self.state['copyIntent']['phase'] in ('opened','saved')
            and same(self.copies.read(self.state['copyIntent']),self.body()) and self.state['manifestIntent'] is None
            and len(self.state['manifests'])==1 and self.state['manifests'][0]['count']==CAPTURES
            and same(self.records.manifest(self.state['manifests'][0]),self.old['records']))
        need(all(row['status']=='returned' for row in self.records.restore(self.state['manifests'],CAPTURES)))
        reader=_snapshot(self.root,self.expected,self.old,self.monotonic);packets=reader.history();need(not reader.blocked and packets)
        result=dict(component='uikit',historicalOnly=True,phase='rotating',globalIndex=CAPTURES,nextIndex=CAPTURES+1,
            nextRaw=self.old['nextRaw'],nativeFloor=deepcopy(packets[-1]))
        self.guard();lease.guard();return result

    def successor(self,reference):
        """Read an already owned UIKit129; no new query or release is issued."""
        prefix=self.history();lease=EmoteOriginalLease(self.root,[])
        reader=_snapshot(self.root,self.expected,self.old,self.monotonic)
        ref=self.records.expand(reference);need(ref['index']==prefix['nextIndex'])
        row=self.records.read(ref);need(row['status']=='returned' and row['query'] is not None)
        prior=[self.records.read(self.records.expand(item)) for item in self.old['records']]
        need(row['query']['commandId'] not in {item['query']['commandId'] for item in prior if item['query'] is not None})
        clock=reader.clock;need(clock is not None and row['before']['epochMs']>=clock['epochMs'] and row['before']['monotonic']>=clock['monotonic'])
        reader.blocked=False;tail,values=reader.record(row,ref['index'],prefix['nativeFloor']);need(not reader.blocked and values)
        from ios.adapters.tablet_web_segments import CHUNK_BYTES
        raw=prefix['nextRaw']
        for part in row['raws']:
            parent=part['segments'];need(parent['first']==raw);raw+=max(1,(parent['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES)
        need(raw<=MAX_FRAMES+1);self.guard();lease.guard()
        return dict(component='uikit',historicalOnly=True,phase='rotating',globalIndex=ref['index'],nextIndex=ref['index']+1,
            nextRaw=raw,nativeFloor=deepcopy(tail))

    def bind_successor(self,reference):
        need(self.state['tabletWebUIKitContinuationVersion']==FENCE_VERSION);self.successor(reference)
        changed=deepcopy(self.state);changed.update(tabletWebUIKitContinuationVersion=BOUND_VERSION,successor=deepcopy(reference));self.save(changed)

    def adopted(self):
        need(self.state['tabletWebUIKitContinuationVersion']==BOUND_VERSION);return self.successor(self.state['successor'])
