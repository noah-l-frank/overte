"""One normal readonly inventory over six first-anchored Share source files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,need
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_seal_owner import SnapshotShareAdmissionSealOwner,ShareAdmissionSealAction
from ios.adapters import snapshot_share_inventory as source


class ShareSourceInventoryAction(ShareAdmissionSealAction):
    _fields={'snapshot.share.archive.source-inventory':{'snapshot.share.archive.query'}}
    _store_prefix='share-source-inventory-slot'
    _namespace='share-source-inventory-output'
    _schema='shareSourceInventoryOutput'
    _owner_key='snapshotShareSourceInventoryUIActionVersion'
    _frame_key='snapshotShareSourceInventoryUIOutputVersion'
    _output_control='snapshot.share.archive.source-inventory'
    _output_locator='snapshot.share.archive.source-inventory-original'


class SnapshotShareSourceInventoryOwner(SnapshotShareAdmissionSealOwner):
    _store_name='share-source-inventory-owner.json'
    _owner_key='snapshotShareSourceInventoryOwnerVersion'
    _action_type=ShareSourceInventoryAction
    _label='inspect-frozen-source-originals'
    def __init__(self,share):
        need(isinstance(share,IOSSnapshotShareOwner) and not share.historical)
        self.bind_scope(share,share.archive.artifact_path,share.archive.admission.store)
        super().__init__(share.archive,share.archive_lock,epoch_ms=share.queries.epoch_ms,monotonic=share.queries.monotonic)
    def bind_scope(self,share,artifact_path,admission_store):
        need(isinstance(share,IOSSnapshotShareOwner) and share.state['cleanup'] is not None and share.state['cleanup']['result'] is not None)
        share.guard();share.cleanup_proof();self.share=share;self.share_hash=digest(share.previous)
        self.sealed=SnapshotShareAdmissionSealOwner.history(PrivateFeatureState(share.archive_root/'share-admission-seal-owner.json'),share.archive_lock,
            share.archive_binding,share.run,share.fixture_url,artifact_path,admission_store)
        self.sealed.proof();self.seal_hash=digest(self.sealed.previous)
    @classmethod
    def history(cls,store,share,artifact_path,admission_store):
        need(isinstance(store,PrivateFeatureState) and isinstance(share,IOSSnapshotShareOwner) and share.historical)
        result=object.__new__(cls);result.bind_scope(share,artifact_path,admission_store)
        result.ctx=None;result.lock=share.archive_lock;result.historical=True
        result.binding,result.run,result.fixture_url=deepcopy(share.archive_binding),share.run,share.fixture_url
        result.admission=result.sealed.admission;result.epoch_ms=lambda:time.time()*1000;result.monotonic=time.monotonic
        result.setup(store);need(result.previous is not None);return result
    def scope_fields(self):return dict(shareOwnerSha256=self.share_hash,sealOwnerSha256=self.seal_hash)
    def bound(self):
        super().bound();self.share.guard();self.sealed.bound()
        need(digest(self.share.previous)==self.share_hash and digest(self.sealed.previous)==self.seal_hash);return True
    def original(self):
        from ios.adapters.snapshot_photos_end_read_area import inventory_original
        return inventory_original(self,self._original_uncached)
    def _original_uncached(self):
        need(self.state['slotSha256'] is not None);action=self.action(True);need(digest(action.previous)==self.state['slotSha256'])
        raw=action.original();return source.original(decode(raw.decode('utf-8')),self.state['nonce'],self.share,self.sealed),raw
    def _historical_load_proof(self,retained):
        # Same actual inventory pair inside this one completed load; its
        # action/qualification/frame guards below still read current files.
        return self._proof_from_original(*retained) if type(self) is SnapshotShareSourceInventoryOwner else self.proof()
    def proof(self):
        packet,raw=self.original();return self._proof_from_original(packet,raw)
    def _proof_from_original(self,packet,raw):
        source.qualified(packet);action=self.action(True);action.qualified();frame=action.files.read(action.files.expand(action.state['proof']))
        need(packet['clockAfter']['monotonicMs']-packet['clockBefore']['monotonicMs']<=frame['hostAfter']['monotonicMs']-frame['hostBefore']['monotonicMs']+250)
        return dict(snapshotShareSourceInventoryResultVersion=1,runId=self.run,shareOwnerSha256=self.share_hash,sealOwnerSha256=self.seal_hash,
            nativeOriginalSha256=hashlib.sha256(raw).hexdigest(),processId=packet['processId'],sourceInstance=packet['sourceInstance'],catalogInstance=packet['instance'],
            parentIdentity=packet['parentIdentity'],outputs=[{key:value for key,value in pin.items() if key!='data'} for pin in packet['outputs']],
            sourceOriginalsRetained=True,sourceFilesRetirementRequired=True,archiveProcessRetirementRequired=True,wholeFeatureRequired=True)
    def seal(self):need(False)
    def inspect(self):return super().seal()
