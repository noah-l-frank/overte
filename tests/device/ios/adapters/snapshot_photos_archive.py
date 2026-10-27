"""Closed original Photos2 reader; it has no live SDK, source or writer path.

Saved/cleanup packets remain their literal originals. This reader reports
historical admission and handoffs, never current permission/process presence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import re
import time
from types import SimpleNamespace
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_companion_owner import IOSSnapshotCompanionOwner
from ios.adapters.snapshot_companion_runtime import IOSSnapshotCompanionRuntime
from ios.adapters.snapshot_photos_owner import IOSSnapshotPhotosOwner
from ios.adapters.snapshot_photos_packets import PACKETS
from ios.adapters import snapshot_exports as exports,snapshot_companion_source as companion_source


class SnapshotPhotosArchive(IOSSnapshotPhotosOwner):
    @classmethod
    def history(cls,store,lock,companion_lock,binding,companion_binding,run,fixture_url,artifact_path,admission_store,primary_bundle):
        owner=object.__new__(cls);owner.monotonic=time.monotonic
        return owner._read_history(store,lock,companion_lock,binding,companion_binding,run,fixture_url,artifact_path,admission_store,primary_bundle)
    @operation
    def _read_history(self,store,lock,companion_lock,binding,companion_binding,run,fixture_url,artifact_path,admission_store,primary_bundle):
        need(isinstance(store,PrivateFeatureState) and isinstance(admission_store,PrivateFeatureState)
            and store.path.name=='photos-save-owner.json' and lock.path==store.path.with_name('script-feature-sources.lock')
            and companion_lock.path==admission_store.path.with_name('script-feature-sources.lock')
            and type(primary_bundle) is str and re.fullmatch(r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+',primary_bundle))
        lock.assert_held();companion_lock.assert_held();owner=self
        owner.combined=True;owner.historical=True;owner.lock,owner.companion_lock=lock,companion_lock
        owner.binding,owner.companion_binding=deepcopy(context(binding)),deepcopy(context(companion_binding))
        owner.run,owner.fixture_url=identifier(run),fixture_url;owner.root,owner.companion_root=store.path.parent,admission_store.path.parent
        need(owner.root!=owner.companion_root)
        owner.store=store;owner.previous=store.read();need(owner.previous is not None)
        need(type(owner.previous.get('iosSnapshotPhotosOwnerVersion')) is int and owner.previous['iosSnapshotPhotosOwnerVersion']==2)
        owner.admission=IOSSnapshotCompanionOwner.archive(admission_store,companion_lock,companion_binding,run,fixture_url,artifact_path)
        owner.admission.result();owner.admission_sha=digest(owner.admission.previous)
        owner.primary=SimpleNamespace(target=dict(appId=primary_bundle))
        owner.companion=SimpleNamespace(artifact_path=Path(artifact_path),binding=deepcopy(owner.companion_binding),
            artifact=deepcopy(owner.admission.artifact),target=dict(appId=owner.admission.artifact['bundle']['bundleId']))
        owner.artifact_pin=IOSSnapshotCompanionRuntime.pin_artifact(owner.companion)
        owner.capture_store=PrivateFeatureState(owner.root/'ios-snapshot-primary-capture-owner.json')
        owner.capture_pin=owner.capture_store.read();need(owner.capture_pin is not None)
        owner.monotonic=time.monotonic;owner.epoch_ms=owner.sleep=None;owner.runtime=owner.selector=owner.phase=None
        owner.state=dict(ticket=None,phaseOriginal=None,capture=None,device=None,slots=[],input=None,export=None,actions=[],handoffs=[],
            nativeTail=None,companionTail=None,destination=[],chunks=[],saved=None,photoQuiet=[],fileQuiet=[],retireOriginal=None,cleaned=None)
        owner.guard();owner.state=owner.decode(owner.previous)
        need(owner.state['saved'] is not None and owner.state['cleaned'] is not None)
        owner.guard();return owner
    def guard(self):
        self.lock.assert_held();self.companion_lock.assert_held();self.admission.bound()
        need(same(self.store.read(),self.previous) and same(self.capture_store.read(),self.capture_pin)
            and digest(self.admission.previous)==self.admission_sha
            and IOSSnapshotCompanionRuntime.pin_artifact(self.companion)==self.artifact_pin)
        return True
    @staticmethod
    def _unavailable(*_args,**_kwargs):need(False)
    save_state=save=cleanup=observed=handoff=acted=active=permission=companion_clock=inspect_destination=_unavailable
    def packet(self,slot,historical=False):
        need(historical is True);return super().packet(slot,historical=True)
    def inputs(self,historical=False):
        need(historical is True);return super().inputs(historical=True)
    def action(self,row,historical=False):
        need(historical is True);return super().action(row,historical=True)
    @operation
    def proof(self):
        self.guard();value=super().proof();self.guard();return value
    @operation
    def cleanup_proof(self):
        self.guard();value=super().cleanup_proof();self.guard();return value
    @operation
    def result(self):
        self.guard();capture,captured,artifact,_raw=self.capture();state=self.state
        need(state['saved'] is not None and state['cleaned'] is not None and state['capture'] is not None
            and type(state['device']) is str and re.fullmatch('[0-9a-f]{64}',state['device'])
            and state['input'] is not None and state['export'] is not None and all(row['after'] is not None and row['sha256'] is not None for row in state['actions'])
            and all(row['issued'] and row['after'] is not None for row in state['handoffs']))
        inputs=self.inputs(True);inputs.validate_original(1)
        before=self.packet_original(state['input']['baseline']);after=self.packet_original(state['export']['label'])
        exports.drained(before);exports.drained(after);exports.drained(self.packet_original('cleanup-exports'))
        old={row['id'] for row in before['source']['operations']};new=[row for row in after['source']['operations'] if row['id'] not in old]
        need(len(new)==1 and new[0]['id']==state['export']['id'] and new[0]['action']=='save'
            and new[0]['owned'] and new[0]['fileName']==state['capture']['file']['name'])
        born=[event for event in after['source']['events'] if event['operation']==new[0]['id'] and event['kind']=='created'];need(len(born)==1)
        need(born[0]['clock']['epochMs']>=max(before['clockAfter']['epochMs'],inputs.state['events'][0]['reference']['scope']['sampleEpochMs']))
        identifier(state['ticket']);phase=state['phaseOriginal']
        phase_packet(phase,run=self.run,area='snapshots',request=phase['requestId'],epoch=phase['capturedEpochMs'],previous=capture.state['phaseOriginal'])
        need(phase['active'] and phase['activations'][-1]['ticket']==state['ticket']
            and phase['activations'][-1]['stimulus']==dict(verb='save',inputs={}))
        previous_clock=self.admission.original(self.admission.state['queries'][-1]);last_clock=None
        for row in state['actions']:
            control=row['plan']['control']
            if control not in ('snapshot.companion.clock','snapshot.companion.photos'):continue
            value=self.original_action(row['index']);kind=control.rsplit('.',1)[1]
            companion_source.original(value,action=kind,nonce=dict(row['plan']['fields'])['snapshot.companion.nonce'],
                pid=int(self.companion_binding['processIdentity']),bundle=self.companion.artifact['bundle']['bundleId'],previous=previous_clock)
            need(value['status']=='ready')
            if kind=='photos':need(value['readWriteAuthorizationBefore']==value['readWriteAuthorizationAfter']==3)
            else:last_clock=value
            previous_clock=value
        need(last_clock is not None and same(last_clock,state['companionTail']))
        rows=[row for row in capture.state['slots'] if row['kind']=='filework' and row['label']=='copy-filework'];need(len(rows)==1)
        child=capture.history('filework',rows[0]['index']);child.qualified();tail=child.historical()['acquisition']['nativeAfter'];previous={}
        for slot in state['slots']:
            need(slot['sha256'] is not None);child=self.packet(slot,True);frame=child.historical();module=PACKETS[slot['kind']]._source
            module.validate(frame['packet'],frame['query'],int(self.binding['processIdentity']),previous=previous.get(slot['kind']))
            previous[slot['kind']]=frame['packet'];follow_native(tail,frame['acquisition']['nativeBefore']);tail=frame['acquisition']['nativeAfter']
        need(same(tail,state['nativeTail']))
        saved=self.proof();cleaned=self.cleanup_proof();need(same(saved,state['saved']) and same(cleaned,state['cleaned']))
        self.guard()
        return dict(snapshotPhotosArchiveResultVersion=1,runId=self.run,binding=deepcopy(self.binding),companionBinding=deepcopy(self.companion_binding),
            fixtureUrl=self.fixture_url,photosOwnerSha256=digest(self.previous),captureResultSha256=digest(captured),artifactJournalSha256=digest(artifact.previous),
            companionAdmissionSha256=self.admission_sha,savedSha256=digest(saved),cleanupSha256=digest(cleaned),recordedDeviceSha256=state['device'],
            originalPhotos2SavedAndCleanupJoined=True,historicalOnly=True,liveSDKPresenceRequired=True,wholeFeatureRequired=True)
