"""Original page restoration after the same main's completed Share cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_journey_files import IOSSnapshotJourneyFilesOwner
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters.snapshot_photos_context import PhotosClientContext
from ios.adapters.snapshot_share_archive_end_owner import SnapshotShareArchiveEndOwner


def initial_snapshot(frame,root):
    route=IOSSnapshotPageOwner.route(frame);need(route['kind']=='snapshot' and route['root']==root);return route


class _ReturnPage(IOSSnapshotPageOwner):
    def store_namespace(self):return 'ios-snapshot-return-page'
    def frame_namespace(self):return 'ios-snapshot-combined-return' if self.combined_profile() else self.store_namespace()
    def frame_store(self):
        if not self.combined_profile():return super().frame_store()
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,'primary',self.bound,self.storage_intent,
            namespace=self.frame_namespace(),schema_prefix='iosSnapshotCombinedReturnPage',monotonic=self.monotonic)
    def inventory(self,state):
        super().inventory(state)
        expected={self.frames.path(self.frames.expand(row)) for row in state['records']}
        if state['observation'] is not None and state['observation']['wire'] is not None:expected.add(self.frames.path(state['observation']['wire']))
        for path in self.store.path.parent.iterdir():
            if path.name.startswith('ios-snapshot-combined-return-'):need(self.combined_profile() and path in expected)
    def restore_origin(self):self.outer.bound();return self.outer.page.restore_origin()
    def phase_original(self,value,ticket):
        phase_packet(value,run=self.run,area='snapshots',request=value['requestId'],epoch=value['capturedEpochMs'])
        original=self.outer.phase_original
        need(value['active'] and ticket==original['activations'][-1]['ticket'] and same(value['activations'],original['activations'])
            and value['instance']==original['instance'] and value['createdEpochMs']==original['createdEpochMs'])
    def open(self,*_args):need(False)
    def capture(self,*_args):need(False)
    @classmethod
    def history(cls,outer):
        owner=object.__new__(cls);owner.combined=outer.combined;owner.outer=outer;owner.store=PrivateFeatureState(outer.root/'ios-snapshot-return-page-owner.json')
        owner.lock,owner.binding,owner.run,owner.fixture_url=outer.lock,deepcopy(outer.binding),outer.run,outer.fixture_url
        owner.historical=True;owner.guard=outer.bound;owner.monotonic=time.monotonic;owner.lock.assert_held();owner.previous=owner.store.read()
        need(owner.previous is not None);owner.frames=owner.frame_store();owner.state=unpack(owner.previous['payload'])[0]
        owner.state=owner.decode(owner.previous);return owner


class SnapshotPageReturnOwner:
    def __init__(self,runtime,selector,primary,phase,page,files,end,*,epoch_ms,monotonic,sleep,combined=False):
        need(type(combined) is bool)
        self.primary,self.epoch_ms,self.monotonic,self.sleep=primary,epoch_ms,monotonic,sleep
        need(isinstance(primary,PhotosClientContext));self.initialize(page,files,end,historical=False,combined=combined);need(same(primary.binding,self.binding))
        need(phase.fixture_url==self.fixture_url and phase.run==self.run and phase.area=='snapshots')
        sources=runtime._sources(selector);need(same(sources['binding'],self.binding));check=sources['check']
        def guard():need(check() is not False);return self.bound()
        sources['check']=guard
        engine=object.__new__(_ReturnPage);engine.outer=self
        _ReturnPage.__init__(engine,runtime,selector,self.run,self.lock,sources,ui=NativeUI(sources['client'],sources['session'],guard),phase=phase,
            epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,combined=self.combined)
        self.engine=engine
        if self.state['result'] is not None:need(same(self.state['result'],self.proof()))
    def initialize(self,page,files,end,*,historical,combined=False):
        need(type(combined) is bool)
        need(type(page) is IOSSnapshotPageOwner and page.historical and page.combined_profile()==combined and type(files) is IOSSnapshotJourneyFilesOwner and files.historical and files.combined==combined
            and type(end) is SnapshotShareArchiveEndOwner and end.historical and end.share.combined==combined and type(historical) is bool)
        self.combined=combined
        self.page,self.files,self.end,self.historical=page,files,end,historical;self.lock,self.binding,self.run,self.fixture_url=page.lock,deepcopy(page.binding),page.run,page.fixture_url
        self.root=page.store.path.parent;self.store=PrivateFeatureState(self.root/'snapshot-page-return-owner.json')
        need(historical or same(self.primary.binding,self.binding))
        need(page.store.path==self.root/'ios-snapshot-page-owner.json' and files.store.path.parent==self.root and end.share.root==self.root
            and files.run==self.run==end.run and files.fixture_url==self.fixture_url==end.fixture_url and same(files.binding,self.binding)
            and same(end.share.binding,self.binding) and page.state['opened'] is not None and page.state['restored'] is None)
        self.lock.assert_held();self.files.proof();self.end.proof()
        need(page.route(page.record(page.state['opened']))['root']==files.pending.state['initial']['rootId']
            and files.pins['captureResultSha256']==end.share.state['capture']['resultSha256'])
        follow_native(page.tail(),files.pending.state['nativeTail']);follow_native(end.share.state['nativeTail'],files.capture.state['nativeTail'])
        self.phase_original=deepcopy(end.share.state['phaseOriginal']);need(self.phase_original is not None and end.share.state['selectTicket']==self.phase_original['activations'][-1]['ticket'])
        self.pins=dict(pageOwnerSha256=digest(page.previous),journeyFilesOwnerSha256=digest(files.previous),archiveEndOwnerSha256=digest(end.previous),
            shareOwnerSha256=digest(end.share.previous),phaseOriginalSha256=digest(self.phase_original))
        self.previous=self.store.read();self.state=dict(engineSha256=None,result=None)
        if self.previous is not None:
            exact(self.previous,{'snapshotPageReturnOwnerVersion','runId','binding','fixtureUrl','pins','payload'});rows=unpack(self.previous['payload']);need(len(rows)==1)
            self.state=rows[0];exact(self.state,{'engineSha256','result'});need(type(self.previous['snapshotPageReturnOwnerVersion']) is int and same(self.previous,self.envelope()))
        else:need(not historical);self.save()
        for path in self.root.iterdir():
            if path.name.startswith('snapshot-page-return-'):need(path==self.store.path)
    @classmethod
    def history(cls,page,files,end,*,combined=False):
        owner=object.__new__(cls);owner.initialize(page,files,end,historical=True,combined=combined);owner.engine=_ReturnPage.history(owner)
        if owner.state['result'] is not None:need(same(owner.state['result'],owner.proof()))
        return owner
    def envelope(self):return dict(snapshotPageReturnOwnerVersion=2 if self.combined else 1,runId=self.run,binding=self.binding,fixtureUrl=self.fixture_url,pins=self.pins,payload=pack([self.state]))
    def bound(self):
        self.lock.assert_held();self.page.bound();self.files.guard();self.end.bound()
        need(same(self.store.read(),self.previous) and self.pins==dict(pageOwnerSha256=digest(self.page.previous),journeyFilesOwnerSha256=digest(self.files.previous),
            archiveEndOwnerSha256=digest(self.end.previous),shareOwnerSha256=digest(self.end.share.previous),phaseOriginalSha256=digest(self.phase_original)))
        if not self.historical:self.primary.probe(True)
        return True
    def save(self):
        need(not self.historical);self.bound();value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    def proof(self):
        self.bound();need(self.state['engineSha256'] is not None and digest(self.engine.previous)==self.state['engineSha256'])
        initial_snapshot(self.engine.record(self.engine.state['initial']),self.files.pending.state['initial']['rootId'])
        restored=self.engine.restoration()
        return dict(snapshotPageReturnedVersion=2 if self.combined else 1,runId=self.run,binding=self.binding,pins=deepcopy(self.pins),pageReturnEngineSha256=self.state['engineSha256'],
            restoration=restored,archiveEnded=True,mainProcessStillOwned=True,primarySDKRetirementRequired=True,wholeFeatureRequired=True)
    @operation
    def restore(self):
        need(not self.historical);self.bound()
        if self.state['result'] is not None:return self.proof()
        engine=self.engine
        if engine.state['ticket'] is None:
            engine.state.update(ticket=self.phase_original['activations'][-1]['ticket'],phaseOriginal=deepcopy(self.phase_original));engine.save()
        if engine.state['roots'] is None:
            engine.state['roots']=engine.runtime.roots(engine);engine.runtime_root()
            follow_native(self.files.capture.state['nativeTail'],engine.state['roots']['clockJoin']['nativeBefore']);engine.save()
        if engine.state['initial'] is None:
            first=engine.observe();initial_snapshot(engine.original(first),self.files.pending.state['initial']['rootId'])
            engine.state.update(initial=first['index'],opened=first['index']);engine.save()
        engine.restore();self.state['engineSha256']=digest(engine.previous);result=self.proof();self.state['result']=deepcopy(result);self.save();return result
