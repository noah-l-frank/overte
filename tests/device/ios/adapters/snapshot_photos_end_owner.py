"""Separate Photos-helper Stop, original OS quiet, SDK404 and exact local CAS.

The Main/Actor/witness remain owned. Literal Result2 is never rewritten.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.installed_code import source as process_source
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_photos_end_context import SnapshotPhotosEndContext
from ios.adapters.snapshot_photos_end_graph import SnapshotPhotosEndGraph
from ios.adapters.snapshot_photos_end_position import SnapshotPhotosRetiredSDKPosition
from ios.adapters.snapshot_share_query_owner import host_clock


def end_record(value):
    """Closed v2 structural gate; this alone grants no endpoint authority."""
    exact(value,{'snapshotPhotosEndOwnerVersion','binding','primaryBinding','runId','fixtureUrl','source','bundleId','payload'})
    need(type(value['snapshotPhotosEndOwnerVersion']) is int and value['snapshotPhotosEndOwnerVersion']==2)
    rows=unpack(value['payload']);need(len(rows)==1 and type(rows[0]) is dict and 'snapshot' in rows[0]);return rows[0]


def initial_process_inventory(root,lock):
    """Missing parent WAL cannot adopt an older process/Stop responsibility."""
    root=Path(root);lock.assert_held();need(lock.path==root/'script-feature-sources.lock')
    store=PrivateFeatureState(root/'photos-sdk-end-owner.json');store._parent();need(store.read() is None)
    for index,path in enumerate(root.iterdir()):
        need(index<8192 and not path.name.startswith('ios-snapshot-photos-'))


class SnapshotPhotosEndOwner:
    def __init__(self,journey,helper,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,historical=False):
        need(type(historical) is bool and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        self._initialize(journey,helper,historical)
    @operation
    def _initialize(self,journey,helper,historical):
        exact(helper,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
        self.graph=SnapshotPhotosEndGraph(journey);photos=self.graph.photos
        need(same(helper['binding'],photos.companion_binding) and helper['sessionStore'].path.parent==photos.companion_root
            and helper['admissionStore'].path==photos.admission.store.path and Path(helper['artifactPath'])==photos.companion.artifact_path)
        self.historical=historical;self.binding=deepcopy(photos.companion_binding);self.primary_binding=deepcopy(photos.binding)
        self.run,self.fixture_url,self.root,self.lock=photos.run,photos.fixture_url,photos.companion_root,photos.companion_lock
        self.store=PrivateFeatureState(self.root/'photos-sdk-end-owner.json');self.previous=self.store.read()
        if self.previous is None:
            need(not historical);initial_process_inventory(self.root,self.lock)
        snapshot=None
        if self.previous is not None:
            snapshot=end_record(self.previous)['snapshot']
        self.ctx=SnapshotPhotosEndContext(helper['client'],helper['sessionStore'],helper['target'],self.binding,helper['artifactPath'],
            helper['admissionStore'],self.lock,self.run,self.fixture_url,epoch_ms=self.epoch_ms,monotonic=self.monotonic,snapshot=snapshot,historical=historical)
        need(same(self.ctx.admission.previous,photos.admission.previous))
        self.state=dict(snapshot=deepcopy(self.ctx.snapshot),graphSha256=None,before=None,stopIssued=False,processReady=False,processSha256=None,
            sdkIssued=False,sdkChecks=[],sdkAbsent=False,localDiscarded=False,result=None)
        if self.previous is None:
            need(not historical);self.ctx.live();self.graph.freeze();self.state['graphSha256']=digest(self.graph.previous);self.save()
        else:self.state=self.load(self.previous)
    @classmethod
    def history(cls,journey,helper):
        owner=cls(journey,dict(helper,client=None),historical=True)
        need(owner.state['result'] is not None);return owner
    def bound(self):
        self.graph.locked();self.graph.verify();self.ctx.local(allow_absent=self.state['sdkAbsent'])
        need(same(self.store.read(),self.previous) and same(self.state['snapshot'],self.ctx.snapshot) and self.state['graphSha256']==digest(self.graph.previous));return True
    def envelope(self):
        return dict(snapshotPhotosEndOwnerVersion=2,binding=self.binding,primaryBinding=self.primary_binding,runId=self.run,
            fixtureUrl=self.fixture_url,source=self.ctx.source,bundleId=self.ctx.target['appId'],payload=pack([self.state]))
    def save(self):
        need(not self.historical);self.bound();value=self.envelope();self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)
    def stamp(self):return host_clock(dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000))
    def process_path(self):return self.root/filename('snapshotphotos','primary',0)
    def process(self):
        need(not self.historical)
        return IOSProcessRetirement(PrivateFeatureState(self.process_path()),self.ctx.process_reader(),self.binding,self.run,'primary',0,self.lock,profile='snapshotphotos')
    def process_history(self):
        value=PrivateFeatureState(self.process_path()).read();need(value is not None)
        state=IOSProcessRetirement.archive(value,path=self.process_path(),binding=self.binding,source=self.ctx.source,bundle=self.ctx.target['appId'],
            run=self.run,role='primary',stage=0,profile='snapshotphotos')
        allowed={self.process_path()}|{self.process_path().with_name(self.process_path().stem+'-'+str(row['ordinal'])+'.json') for row in state['records']}
        if state['pending'] is not None:allowed.add(self.process_path().with_name(self.process_path().stem+'-'+str(state['pending']['ordinal'])+'.json'))
        for path in self.root.iterdir():
            if path.name.startswith('ios-snapshot-photos-'):need(path in allowed)
        return value,state
    def load(self,value):
        exact(value,{'snapshotPhotosEndOwnerVersion','binding','primaryBinding','runId','fixtureUrl','source','bundleId','payload'})
        state=end_record(value);exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(same(value,self.envelope()) and same(state['snapshot'],self.ctx.snapshot) and state['graphSha256']==digest(self.graph.previous)
                and all(type(state[key]) is bool for key in ('stopIssued','processReady','sdkIssued','sdkAbsent','localDiscarded'))
                and type(state['sdkChecks']) is list and len(state['sdkChecks'])<=128)
            self.bound()
            if state['before'] is not None:
                before=state['before'];exact(before,{'process','source','hostBefore','hostAfter'});actual=before['process'];exact(actual,{'bundleId','pid','foreground'})
                need(type(actual['pid']) is int and actual['pid']==int(self.binding['processIdentity']) and actual['bundleId']==self.ctx.target['appId']
                    and type(actual['foreground']) is bool and same(process_source(before['source']),self.ctx.source))
                host_clock(before['hostBefore']);host_clock(before['hostAfter'],before['hostBefore'])
            if state['stopIssued']:need(state['before'] is not None)
            else:need(state['before'] is None and not state['processReady'] and not state['sdkIssued'] and not state['sdkAbsent'])
            if state['processReady']:
                need(state['stopIssued']);process,history=self.process_history();need(any(window['complete'] for window in history['windows']))
                if state['processSha256'] is not None:need(digest(process)==state['processSha256'] and history['windows'][-1]['complete'])
            else:need(state['processSha256'] is None)
            previous=None
            for index,row in enumerate(state['sdkChecks'],1):
                exact(row,{'index','status','sessionId','targetFingerprint','sdkStateSha256','hostBefore','hostAfter'})
                need(type(row['index']) is int and row['index']==index and type(row['status']) is int and row['status'] in (200,404)
                    and row['sessionId']==self.binding['sessionId'] and row['targetFingerprint']==self.binding['targetFingerprint']
                    and row['sdkStateSha256']==digest(self.ctx.snapshot['sdkState']))
                host_clock(row['hostBefore'],previous);host_clock(row['hostAfter'],row['hostBefore']);previous=row['hostAfter']
            if state['sdkChecks']:need(state['processReady'])
            if state['sdkIssued']:need(state['processSha256'] is not None)
            if state['sdkAbsent']:need(state['processSha256'] is not None and state['sdkChecks'] and state['sdkChecks'][-1]['status']==404)
            if state['localDiscarded']:need(state['sdkAbsent'] and self.ctx.session_store.read() is None)
            if state['result'] is not None:need(same(state['result'],self.proof()))
        finally:self.state=prior
        return deepcopy(state)
    def sdk_probe(self,*,retain=True):
        need(not self.historical);self.bound();before=self.stamp();status=200
        try:
            value=self.ctx.client.call('GET','/session/'+self.ctx.session)
            need(type(value) is dict and type(value.get('capabilities')) is dict and value['capabilities'].get('appium:bundleId')==self.ctx.target['appId'])
        except WebDriverRequestError as error:need(error.status==404);status=404
        after=self.stamp()
        if retain:
            need(len(self.state['sdkChecks'])<128)
            self.state['sdkChecks'].append(dict(index=len(self.state['sdkChecks'])+1,status=status,sessionId=self.ctx.session,
                targetFingerprint=self.binding['targetFingerprint'],sdkStateSha256=digest(self.ctx.snapshot['sdkState']),hostBefore=before,hostAfter=after));self.save()
        return status
    def position_record(self):
        self.bound();need(same(self.envelope(),self.previous));state=self.state
        need(state['stopIssued'] and state['processReady'] and state['processSha256'] is not None and state['sdkAbsent']
            and state['localDiscarded'] and self.ctx.session_store.read() is None and state['sdkChecks'] and state['sdkChecks'][-1]['status']==404)
        process,history=self.process_history();need(digest(process)==state['processSha256'] and history['windows'][-1]['complete'])
        return dict(snapshotPhotosRetiredSDKPositionVersion=2,binding=deepcopy(self.binding),primaryBinding=deepcopy(self.primary_binding),
            runId=self.run,fixtureUrl=self.fixture_url,graphSha256=state['graphSha256'],processOwnerSha256=state['processSha256'],
            sdkSnapshotSha256=digest(self.ctx.snapshot),sdkSlotSha256=digest(self.ctx.snapshot['sdkSlot']),sdk404OriginalSha256=digest(state['sdkChecks'][-1]),localSDKPointerAbsent=True,historicalOriginalsOnly=True)
    @operation
    def proof(self):
        from ios.adapters.snapshot_photos_end_round import scope as decode_round
        with decode_round(self.graph):
            position=SnapshotPhotosRetiredSDKPosition(self);original=self.graph.replay(position);record=position.check(self.graph)
        return dict(snapshotPhotosEndedVersion=2,runId=self.run,binding=deepcopy(self.binding),primaryBinding=deepcopy(self.primary_binding),
            originalPID=int(self.binding['processIdentity']),graphSha256=digest(self.graph.previous),originalResult2Sha256=digest(original),
            photosOwnerSha256=original['photos']['archive']['photosOwnerSha256'],companionAdmissionSha256=original['photos']['archive']['companionAdmissionSha256'],
            retiredSDKPosition=record,originalPhotosProcessQuiet=True,originalPhotosSDK404=True,localSDKPointerRetired=True,
            originalGraphReplayedWithoutSDK=True,mainProcessStillOwned=True,independentActorSceneAndRenderedReviewRequired=True,
            sourceMainSDKWitnessRetirementRequired=True,wholeFeatureRequired=True)
    @operation
    def finalize(self):
        need(not self.historical);self.bound()
        if self.state['result'] is not None:need(self.sdk_probe(retain=False)==404);return self.proof()
        if not self.state['stopIssued']:
            before=self.stamp();actual=self.ctx.live();after=self.stamp()
            self.state['before']=dict(process=actual,source=deepcopy(self.ctx.source),hostBefore=before,hostAfter=after)
            self.state['stopIssued']=True;self.save();self.ctx.terminate()
        if not self.state['processReady']:
            process=self.process()
            while not process.advance():self.sleep(1.6)
            self.state['processReady']=True;self.save()
        if not self.state['sdkAbsent']:
            status=self.sdk_probe()
            if status==200:
                need(not self.state['sdkIssued']);process=self.process()
                while not process.advance():self.sleep(1.6)
                process.current();self.state['processSha256']=digest(process.previous);self.state['sdkIssued']=True;self.save()
                try:self.ctx.client.call('DELETE','/session/'+self.ctx.session)
                except WebDriverRequestError as error:
                    if error.status!=404:raise
                status=self.sdk_probe()
            else:
                process,history=self.process_history();need(history['windows'][-1]['complete']);self.state['processSha256']=digest(process)
            need(status==404);self.state['sdkAbsent']=True;self.save()
        current=self.ctx.session_store.read()
        if current is not None:self.ctx.local();self.ctx.session_store.discard(self.ctx.snapshot['sdkState'])
        need(self.ctx.session_store.read() is None);self.state['localDiscarded']=True;self.save()
        result=self.proof();self.state['result']=deepcopy(result);self.save();return result
