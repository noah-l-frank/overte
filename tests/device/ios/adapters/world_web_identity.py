"""Actual Script-returned Web UUID joined to code, original Tree birth and DOM."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from ios.adapters.emote_original_lease import EmoteOriginalLease
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_sources import WorldWebSources
from ios.adapters.world_web_work import owned_worker
from ios.adapters import create_entities
from ios.adapters import world_web_surface_lease
from ios.adapters.world_web_resource_disposition import resource_admission


class WorldWebLease:
    def __init__(self,scope,source,before,after):
        need(isinstance(scope,IOSWorldWebScope) and isinstance(source,WorldWebSources) and scope.run==source.run
            and same(scope.binding,source.binding) and scope.lock is source.lock)
        self.scope,self.source,self.before,self.after=scope,source,deepcopy(before),deepcopy(after)
        self.binding,self.run=deepcopy(source.binding),source.run;self._round=None;self._identity=self.derive()

    def derive(self):
        with self.source.validation_round():return self._derive()

    def _derive(self):
        scope=self.scope;need(same(scope.store.read(),scope.previous) and same(scope.binding,self.binding) and scope.run==self.run)
        from ios.adapters.world_web_scope_archive import archived
        from ios.adapters.world_web_marker_measurements import admitted as marker_admitted
        original=archived(scope,self.source)
        state=original.state;need(state['admission'] is not None and state['admissionFrame'] is not None and state['webAdmission'] is not None)
        a,b=self.source.frame(self.before),self.source.frame(self.after)
        need(a['index']<b['index'] and a['clockJoin']['nativeAfter']['capturedEpochMs']<=state['loadBarrier'])
        loaded=[frame for frame in original.frames if frame['label']=='marker-loaded'];need(len(loaded)==1);admitted=loaded[0]
        expected=marker_admitted(original.frames[state['baseline']-1]['world'],admitted['world'],state['fileOwnership'],state['directory'],after_epoch=state['loadBarrier'])
        if state['cleanupMode']=='full':need(same(expected,state['admission']))
        result=create_entities.returned(b['originals']['entities'],a['originals']['entities'],expected['manager'],expected['code'],after_epoch=state['loadBarrier'])
        need(result['birth'] is not None and result['returned']['entityId']==result['birth']['id']==expected['marker']['id']
            and result['treeInstance']==b['originals']['geometry']['source']['tree']['treeInstance'])
        worker=owned_worker(b['originals']['work'],state['fileOwnership'],state['directory'],result['returned']['entityId'])
        need(worker['manager']==expected['manager'] and worker['code']==expected['code'])
        document=b['originals']['document'];need(document is not None and document['source']['nativeView']['sourceIdentity']=='web-entity:'+result['returned']['entityId']
            and document['source']['nativeView']['sourceUrl']==expected['marker']['sourceUrl'])
        self._validated_scope_state=deepcopy(state)
        value=dict(iosWorldWebLeaseVersion=2 if self.source.version>=4 else 1,binding=deepcopy(self.binding),runId=self.run,admission=deepcopy(expected),returned=result,
            files=deepcopy(state['fileOwnership']),directory=state['directory'],before=deepcopy(self.before),after=deepcopy(self.after))
        if self.source.version>=4:value['surfaceLease']=world_web_surface_lease.admitted(a['originals']['surfaces'],b['originals']['surfaces'],
            result['returned']['entityId'],expected['marker']['sourceUrl'],after_epoch=state['loadBarrier'])
        if self.source.version>=4:value['resourceAdmission']=resource_admission(b['originals']['closures'],result['returned']['entityId'],expected['marker']['sourceUrl'])
        return value

    @contextmanager
    def validation_round(self):
        if self._round is not None:yield;return
        # The generic filesystem lease guards the unchanged inventory around
        # the full actual Scope/Source decoder. It supplies no native fact.
        continuity=EmoteOriginalLease(self.scope.root,[])
        actual=self.derive();need(same(actual,self._identity));continuity.guard();self._round=deepcopy(actual)
        try:yield
        finally:
            try:continuity.guard();self.header()
            finally:self._round=None

    def header(self):
        need(same(self.scope.store.read(),self.scope.previous) and same(self.scope.binding,self.binding)
            and same(self.source.binding,self.binding) and self.scope.run==self.source.run==self.run)
        need(same(self.before,self._identity['before']) and same(self.after,self._identity['after'])
            and (self._round is None or same(self._round,self._identity)))

    def packet(self):
        if self._round is not None:self.header();return deepcopy(self._round)
        actual=self.derive();need(same(actual,self._identity));return deepcopy(actual)

    def scope_state(self):
        self.packet();return deepcopy(self._validated_scope_state)

    def current(self,frame,*,live):
        need(type(live) is bool);owned=self.packet();raw=frame['originals'];manager=owned['admission']['manager'];code=owned['admission']['code']
        worker=owned_worker(raw['work'],owned['files'],owned['directory'],owned['returned']['returned']['entityId'])
        need(worker['manager']==manager and worker['code']==code)
        if owned['iosWorldWebLeaseVersion']==2:world_web_surface_lease.current(owned['surfaceLease'],raw['surfaces'],live=live)
        if live:
            script=raw['world']['source']['scriptOriginal']['source'];members=script.get('membership')
            need(script.get('membershipSourceVersion')==1 and members['complete'] and any(same(row,manager) for row in members['managers']))
            engines=[row for row in script['engines'] if row['required']['instance']==manager['instance']]
            need(len(engines)==1 and same(engines[0]['code'],code))
            markers=[row for row in raw['world']['source']['markers'] if row['id']==owned['admission']['marker']['id']]
            need(len(markers)==1 and same(markers[0],owned['admission']['marker']))
        return owned
