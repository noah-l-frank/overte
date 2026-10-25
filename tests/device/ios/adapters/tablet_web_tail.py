"""Whole Tablet live quiet originals, retaining actual native cache lifetimes.

Every query has an independent durable owner. This composition joins their
original clocks and prefixes; it cannot convert a detached/ended cached object
into weak death or permit a product Stop. Terminal OS retirement is separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same,pack,unpack
from ios.adapters.graphics_history import follow_native
from ios.adapters.tablet_web_native_reads import TabletNativeReads
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.adapters import tablet_web_state as state,uikit_input as uikit,world_web_keys as keys,pointer_state as pointer
from ios.adapters.tablet_web_runtime import file_responsibilities

VERSION=1
READS=('keys','pointer','dialogs','geometry','widgets','scripts','terminal')


def forbidden(*_args,**_kwargs):need(False)


def host(value,previous=None):
    exact(value,{'epochMs','monotonic'});need(integer(value['epochMs'],1) and number(value['monotonic'],0,1e15))
    if previous is not None:need(value['epochMs']>=previous['epochMs'] and value['monotonic']>=previous['monotonic'])
    return value


def bounds(kind,packet):
    if kind in ('keys','pointer','dialogs'):return packet['clockBefore']['epochMs'],packet['clockAfter']['epochMs']
    if kind in ('geometry','widgets'):return (packet['observation']['sampleEpochMs'],)*2
    return (packet['capturedEpochMs'],)*2


class TabletWebTail:
    def __init__(self,runtime,*,historical=False):
        self.runtime=runtime;source=runtime.observer.source
        self.root,self.binding,self.run,self.role,self.lock=source.root,source.binding,source.run,source.role,source.lock
        self.historical=historical;self.clock_ms,self.monotonic=source.epoch_ms,source.monotonic
        need(type(historical) is bool and self.lock.path==self.root/'script-feature-sources.lock')
        self.store=PrivateFeatureState(self.root/('tabletweb-tail-'+self.run+'-'+self.role+'.json'))
        self.saved=self.store.read()
        if self.saved is None:
            self.live();self.state=dict(records=[],pending=None,original=None);self.save()
        else:
            value=self.saved;exact(value,{'tabletWebTailVersion','binding','runId','role','payload'})
            need(type(value['tabletWebTailVersion']) is int and value['tabletWebTailVersion']==VERSION and same(value['binding'],self.binding)
                and value['runId']==self.run and value['role']==self.role)
            rows=unpack(value['payload']);need(len(rows)==1);self.state=rows[0]
        self.originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.file_guard,self.intent,
            namespace='tabletweb-tail',schema_prefix='tabletWebTail',monotonic=self.monotonic)
        self.decode()

    def live(self):need(not self.historical);self.lock.assert_held();need(self.runtime.check() is not False)
    def file_guard(self):
        if not self.historical:self.lock.assert_held()
        return True
    def save(self):
        self.live();value=dict(tabletWebTailVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,payload=pack([self.state]))
        self.store.write(value,self.saved);self.saved=deepcopy(value)
    def stamp(self):return host(dict(epochMs=self.clock_ms(),monotonic=self.monotonic()))
    def intent(self,kind,reference):
        self.live();need(kind=='original' and self.state['pending'] is not None);self.state['original']=deepcopy(reference);self.save()
    def auxiliary(self,kind):
        return TabletNativeReads(self.root,self.binding,self.run,self.role,kind,self.lock,forbidden,
            epoch_ms=forbidden,monotonic=self.monotonic,historical=True)
    def source(self):
        actual=self.runtime.observer.source
        return TabletWebSourceOwner(self.root,self.binding,self.run,self.role,actual.fixture,actual.pid,self.lock,forbidden,
            epoch_ms=forbidden,monotonic=self.monotonic,historical=True)

    def read(self,reference):
        full=self.originals.expand(reference);index=full['index']
        need(1<=index<=len(self.state['records']) and same(reference,self.state['records'][index-1]))
        row=self.originals.read(full);return self.record(row,index)

    def record(self,row,index):
        exact(row,{'tabletWebTailFrameVersion','index','status','before','after','nativeStart','queries','files','source','clockSha256'})
        need(type(row['tabletWebTailFrameVersion']) is int and row['tabletWebTailFrameVersion']==VERSION and type(row['index']) is int and row['index']==index
            and row['status'] in ('acquiring','returned','failed') and type(row['queries']) is dict and set(row['queries'])<=set(READS)
            and type(row['files']) is list and len(row['files'])<=32)
        host(row['before']);need(row['after'] is None or host(row['after'],row['before']))
        packets={}
        if row['nativeStart'] is not None:packets['native']=self.auxiliary('native').at(row['nativeStart'])
        for kind,reference in row['queries'].items():packets[kind]=self.auxiliary(kind).at(reference)
        seen=set();file_owner=self.auxiliary('files') if row['files'] else None
        for owned in row['files']:
            exact(owned,{'ownership','reference'})
            from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles
            from ios.adapters.tablet_web_app_origin import Frozen
            metadata=OwnedTabletWebAppFiles(None,Frozen(owned['ownership']),self.binding).owned()
            need(metadata['featureRun']==self.run and metadata['runId'] not in seen);seen.add(metadata['runId'])
            packet=file_owner.at(owned['reference']);need(packet['runId']==metadata['runId'] and packet['operation']=='observe')
            packets['files:'+packet['runId']]=packet
        frame=source_row=public=None
        if row['source'] is not None:
            disposition=self.runtime.validate_tail_source(row['source'])
            source_row,frame=disposition['row'],disposition['frame']
        if row['status']=='returned':
            need(set(row['queries'])==set(READS) and row['after'] is not None and frame is not None and 'native' in packets)
            first,last=packets['native'],source_row['nativeAfter'];follow_native(first,source_row['nativeBefore']);follow_native(first,last)
            before,after=row['before'],row['after'];duration=(after['monotonic']-before['monotonic'])*1000
            need(0<=after['epochMs']-before['epochMs']<1500 and 0<=duration<1500
                and abs(after['epochMs']-before['epochMs']-duration)<=250 and abs(last['capturedEpochMs']-first['capturedEpochMs']-duration)<=250)
            for kind,packet in packets.items():
                lo,hi=bounds(kind.split(':')[0],packet);need(first['capturedEpochMs']<=lo<=hi<=last['capturedEpochMs'])
            source_before=source_row['clockJoin']['hostBeforeEpochMs'];source_after=source_row['clockJoin']['hostAfterEpochMs']
            need(before['epochMs']<=source_before<=source_after<=after['epochMs'])
            need(row['clockSha256']==digest(dict(packets=packets,source=row['source'],before=before,after=after)))
        else:need(row['clockSha256'] is None)
        return deepcopy(dict(row=row,packets=packets,frame=frame,source=source_row,public=public))

    def decode(self):
        exact(self.state,{'records','pending','original'});need(type(self.state['records']) is list and len(self.state['records'])<=128)
        self.frames=[];self.blocked=self.state['pending'] is not None;previous=None
        for index,reference in enumerate(self.state['records'],1):
            full=self.originals.expand(reference);need(full['index']==index);value=self.record(self.originals.read(full),index)
            need(value['row']['status'] in ('returned','failed'));host(value['row']['before'],previous);previous=value['row']['after'];self.frames.append(value)
        if self.state['pending'] is not None:
            value=self.record(self.state['pending'],len(self.frames)+1);host(value['row']['before'],previous)
        if self.state['original'] is not None:
            need(self.state['pending'] is not None);ref=self.originals.original(self.state['original'])
            need(ref['index']==len(self.frames)+1)
            if ref['phase']=='saved':need(same(self.originals.read(ref),self.state['pending']))
        return deepcopy(self.frames)

    def recover_original(self):
        """Complete only the same fully written original; never query again.

        A planned, empty or partial file and a lost native result stay owned.
        No failed acquisition is relabeled returned and no timestamp advances.
        """
        self.live();self.decode();reference=self.state['original'];row=self.state['pending']
        need(reference is not None and row is not None and row['status']=='returned'
            and reference['phase'] in ('opened','saved') and reference['index']==len(self.state['records'])+1)
        actual=self.originals.read(reference);need(same(actual,row));self.record(actual,reference['index'])
        compact=self.originals.compact(dict(reference,phase='saved'))
        self.state['records'].append(compact);self.state['pending']=self.state['original']=None;self.save();self.decode()
        return deepcopy(compact)

    def archive_failed(self):
        """Keep an interrupted acquisition as failed before a new one starts.

        Actual raw/query continuity is independently replayed by the auxiliary
        and nine-source owners. This returns no quiet/frame verdict, sends no
        query, preserves the original failure clocks and never resumes a tail.
        """
        self.live();self.decode();row=self.state['pending']
        need(row is not None and row['status']=='failed' and row['after'] is not None and self.state['original'] is None)
        reference=self.originals.write(row['index'],deepcopy(row));self.state['records'].append(reference)
        self.state['pending']=self.state['original']=None;self.save();self.decode();return deepcopy(reference)

    def capture(self,ownerships):
        self.live();self.decode();need(not self.blocked and len(self.state['records'])<128 and type(ownerships) is list and len(ownerships)<=32)
        row=dict(tabletWebTailFrameVersion=VERSION,index=len(self.state['records'])+1,status='acquiring',before=self.stamp(),after=None,
            nativeStart=None,queries={},files=[],source=None,clockSha256=None)
        self.state['pending']=row;self.save()
        try:
            self.runtime.read_auxiliary('native');row['nativeStart']=deepcopy(self.runtime.auxiliary('native').state['records'][-1]);self.save()
            packets={'native':self.auxiliary('native').at(row['nativeStart'])}
            for kind in READS:
                packet=self.runtime.read_auxiliary(kind);row['queries'][kind]=deepcopy(self.runtime.auxiliary(kind).state['records'][-1]);self.save();packets[kind]=packet
            for metadata in ownerships:
                packet=self.runtime.read_auxiliary('files',ownership=metadata);row['files'].append(dict(ownership=deepcopy(metadata),reference=deepcopy(self.runtime.auxiliary('files').state['records'][-1])))
                self.save();packets['files:'+packet['runId']]=packet
            row['source']=self.runtime.tail_source();self.save();row['after']=self.stamp()
            row['clockSha256']=digest(dict(packets=packets,source=row['source'],before=row['before'],after=row['after']));row['status']='returned';self.save()
            self.record(row,row['index']);reference=self.originals.write(row['index'],deepcopy(row))
            self.state['records'].append(reference);self.state['pending']=self.state['original']=None;self.save();self.decode();return deepcopy(reference)
        except Exception:
            if self.state['original'] is None:row['status']='failed';row['clockSha256']=None;row['after']=self.stamp();self.save()
            raise
