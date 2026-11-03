"""Actual once-only local Assets Stop and independent shared OS stage0.

This authority never claims unknown bytes, a global pool or GPU reclamation.
Only the exact held frozen graph, original source and fresh native work cut
permit Stop; issued uncertainty can only observe the existing OS endpoint.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.operation_transport_guard import scope as transport_scope
from ios.adapters.assets_budget import operation,check
from ios.adapters.installed_process_runtime import admitted_source,mark_stopped,retired_process_observer
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.retired_process import absent

_STOP=ContextVar('ios_assets_exact_once_owned_stop',default=None)


def admitted_stop(adapter,selector,operation,values):
    owner=_STOP.get()
    if owner is None:return False
    need(type(owner) is AssetsProcessEnd and owner.runtime.adapter is adapter and owner.target==selector
        and operation=='app.stop' and values=={} and owner.state['phase']=='stop-issued')
    owner.stop_guard();return True


class AssetsProcessEnd:
    def __init__(self,transaction,role,*,peer=None):
        from ios.adapters.assets_paired_end import AssetsPairedLocalEnd
        need(type(transaction) is AssetsPairedLocalEnd and role in ('primary','actor'))
        self.tx,self.role,self.peer=transaction,role,peer;self.runtime=transaction.runtime
        self.info=transaction.context['roles'][role];self.binding=deepcopy(self.info['binding']);self.source=deepcopy(self.info['source'])
        self.target,self.root,self.run,self.lock=self.info['target'],transaction.role_root(role),transaction.run,transaction.locks[role]
        self.archive=transaction.archive;self.monotonic,self.epoch_ms=self.runtime.monotonic,self.runtime.epoch_ms
        self.store=PrivateFeatureState(self.lock.path.with_name('ios-assets-'+self.run+'-'+role+'-process-end.json'))
        self.frames=OriginalFrameStore(self.root,self.binding,self.run,role,self.bound,self.intent,
            namespace='assets-process-end',schema_prefix='iosAssetsProcessEnd',monotonic=self.monotonic)
        self.stop_cut=None;self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
        need((role=='actor') is (peer is None))
        if peer is not None:need(type(peer) is AssetsProcessEnd and peer.tx is transaction and peer.role=='actor')
    def envelope(self,state):return dict(iosAssetsProcessEndVersion=1,contextSha256=digest(self.tx.context),runId=self.run,
        role=self.role,binding=self.binding,payload=pack([state]))
    def decode(self,value):
        exact(value,{'iosAssetsProcessEndVersion','contextSha256','runId','role','binding','payload'})
        rows=unpack(value['payload']);need(type(value['iosAssetsProcessEndVersion']) is int and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','fence','pending','osSha256','peerSha256'})
        need(state['phase'] in ('prepared','stop-issued','stopped','complete'))
        if state['fence'] is not None:self.frames.expand(state['fence'])
        if state['pending'] is not None:self.frames.original(state['pending']);need(state['phase']=='prepared' and state['fence'] is None)
        if state['phase']!='prepared':need(state['fence'] is not None and state['pending'] is None)
        if self.role=='actor':need(state['peerSha256'] is None)
        else:need(self.peer is not None and state['peerSha256']==digest(self.peer.previous))
        if state['phase']=='complete':need(state['osSha256']==digest(self.os_store().read()))
        else:need(state['osSha256'] is None)
        return deepcopy(state)
    def bound(self):
        check();self.tx.guard();self.lock.assert_held();need(same(self.store.read(),self.previous));return True
    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def intent(self,event,value):
        need(event=='original' and self.state['phase']=='prepared' and self.state['fence'] is None and value['index']==1)
        self.frames.original(value)
        if self.stop_cut is not None:self.stop_cut.original_intent(value)
        self.state['pending']=deepcopy(value);self.save()
    def os_store(self):return PrivateFeatureState(self.store.path.with_name(filename('assets',self.role,0)))
    def os_state(self):
        value=self.os_store().read();need(value is not None)
        return IOSProcessRetirement.archive(value,path=self.os_store().path,binding=self.binding,source=self.source,
            bundle=self.info['bundleId'],run=self.run,role=self.role,stage=0,profile='assets')
    def fence(self):
        need(self.state is not None and self.state['fence'] is not None)
        value=self.frames.read(self.frames.expand(self.state['fence']))
        exact(value,{'assetsProcessFenceVersion','contextSha256','archiveSha256','role','binding','source','clockJoin','originals'})
        need(type(value['assetsProcessFenceVersion']) is int and value['assetsProcessFenceVersion']==1
            and value['contextSha256']==digest(self.tx.context) and value['archiveSha256']==self.archive.frozen_identity()
            and value['role']==self.role and same(value['binding'],self.binding) and same(value['source'],self.source))
        validate_join(value['clockJoin'],value['originals']);return value
    def fresh(self,value):
        join=value['clockJoin'];epoch,mono=self.epoch_ms(),self.monotonic()
        need(number(epoch,join['hostAfterEpochMs'],join['hostBeforeEpochMs']+1500) and epoch-join['hostBeforeEpochMs']<1500
            and number(mono,join['hostAfterMonotonic'],join['hostBeforeMonotonic']+1.5) and mono-join['hostBeforeMonotonic']<1.5
            and abs(epoch-join['hostBeforeEpochMs']-(mono-join['hostBeforeMonotonic'])*1000)<=250)
    @operation
    def prepare(self):
        self.bound();need(self.state is None);self.tx.current_graph()
        if self.peer is not None:self.peer.completed()
        need(same(admitted_source(self.runtime,self.target,self.binding),self.source))
        self.state=dict(phase='prepared',fence=None,pending=None,osSha256=None,peerSha256=None if self.peer is None else digest(self.peer.previous));self.save()
    @operation
    def stop(self):
        try:
            self.bound();need(self.state['phase']=='prepared');self.tx.current_graph()
            need(same(admitted_source(self.runtime,self.target,self.binding),self.source))
            native=None if self.state['fence'] is not None or self.state['pending'] is not None else self.runtime._assets_end_native(self)
            from ios.adapters.assets_end_stop_cut import AssetsStopCut
            need(self.stop_cut is None);self.stop_cut=AssetsStopCut(self)
            if self.state['pending'] is not None:
                pending=self.state['pending'];need(pending['phase'] in ('opened','saved'))
                value=self.frames.read(pending)
                # A recovered original may be used only while its exact original
                # freshness still holds; it is never retimed or acquired twice.
                self.state.update(fence=self.frames.compact(dict(pending,phase='saved')),pending=None);self.save()
            if self.state['fence'] is None:
                acquisition=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
                acquisition.begin(self.epoch_ms());originals=dict(nativeBarrier=deepcopy(acquisition.started['nativeBefore']))
                join=acquisition.finish(originals,[('nativeBarrier','capturedEpochMs')])
                value=dict(assetsProcessFenceVersion=1,contextSha256=digest(self.tx.context),archiveSha256=self.archive.frozen_identity(),
                    role=self.role,binding=deepcopy(self.binding),source=deepcopy(self.source),clockJoin=join,originals=originals)
                reference=self.frames.write(1,value);self.state.update(fence=reference,pending=None);self.save()
            self.fence();self.stop_cut.acquired(self.fence());self.fresh(self.fence());self.stop_cut.issue()
            self.state['phase']='stop-issued';self.save()
            token=_STOP.set(self)
            try:
                with transport_scope(self.stop_guard):
                    self.stop_guard();base=self.runtime.adapter;outer=base._operation;need(outer in (None,'feature.assets.terminal'))
                    base._operation=None
                    try:return base.invoke(self.target,'app.stop',{})
                    finally:base._operation=outer
            finally:_STOP.reset(token)
        finally:self.stop_cut=None
    def stop_guard(self):
        self.bound();need(self.state['phase']=='stop-issued' and self.stop_cut is not None)
        self.stop_cut.guard();self.fresh(self.fence());return True
    @operation
    def advance(self):
        self.bound();need(self.state['phase'] in ('stop-issued','stopped','complete'))
        if self.state['phase']=='complete':self.completed();return True
        self.fence();reader=retired_process_observer(self.runtime,self.target,self.binding,self.source)
        reader.epoch_ms,reader.monotonic=self.epoch_ms,self.monotonic
        owner=IOSProcessRetirement(self.os_store(),reader,self.binding,self.run,self.role,0,self.lock,profile='assets')
        complete=owner.advance();actual=owner.current()
        need(actual['acquisition']['hostBeforeEpochMs']>=self.fence()['clockJoin']['hostAfterEpochMs'])
        if absent(actual['original']):mark_stopped(self.runtime,self.target,self.binding,self.source);self.state['phase']='stopped'
        if complete:self.state.update(phase='complete',osSha256=digest(owner.previous))
        self.save();return bool(complete)
    def completed(self):
        self.bound();need(self.state is not None and self.state['phase']=='complete');self.fence();state=self.os_state()
        need(state['pending'] is None and state['windows'] and state['windows'][-1]['complete'])
        if self.peer is not None:self.peer.completed()
        return deepcopy(self.previous)
    def owned_paths(self):
        result={self.store.path,self.os_store().path}
        if self.state is not None:
            for ref in (self.state['fence'],self.state['pending']):
                if ref is None:continue
                wire=ref if 'phase' in ref else self.frames.expand(ref)
                if wire['phase']!='planned':result.add(self.frames.path(wire))
        raw=self.os_store().read()
        if raw is not None:
            rows=unpack(raw['payload']);need(len(rows)==1)
            for ref in rows[0]['records']:result.add(self.os_store().path.with_name(self.os_store().path.stem+'-'+str(ref['ordinal'])+'.json'))
            if rows[0]['pending'] is not None:result.add(self.os_store().path.with_name(self.os_store().path.stem+'-'+str(rows[0]['pending']['ordinal'])+'.json'))
        return result
