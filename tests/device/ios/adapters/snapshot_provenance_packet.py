"""Original FrameStore custody for the opt-in ordinary callback provenance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import snapshot_provenance as source
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket


class SnapshotProvenancePacket(SnapshotOwnedPacket):
    _name = 'native-provenance'
    _key = 'iosSnapshotProvenancePacketVersion'
    _namespace = 'snapshot-native-provenance'
    _schema = 'snapshotNativeProvenance'
    _kind = 'provenance'
    _source = source

    def join_capture(self, capture):
        from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
        need(type(self) is SnapshotProvenancePacket and type(capture) is IOSSnapshotCaptureOwner
            and self.lock is capture.lock and same(self.binding, capture.binding)
            and self.run == capture.run and self.role == 'primary'
            and self.store.path.parent == capture.store.path.parent)
        self.lock.assert_held()
        capture.bound()
        proof = capture.result()
        completed = proof['capture']
        native = capture.history('captures', capture.state['settled']['captures']).historical()['packet']
        artifact = capture.history('artifact', capture.state['artifact'])
        fact, raw = artifact.originals()
        need(same(fact['file'], completed['file']))
        retained = self.historical()
        row = source.joined_originals(retained['packet'], native, completed, raw)
        return dict(iosSnapshotOrdinaryProvenanceResultVersion=1, binding=deepcopy(self.binding),
            runId=self.run, role=self.role, capture=deepcopy(completed), provenance=row,
            pins=dict(packetOwnerSha256=digest(self.previous), captureOwnerSha256=digest(capture.previous),
                captureResultSha256=digest(proof), artifactOwnerSha256=digest(artifact.previous)),
            sameOrdinaryCallbackPixelsEstablished=True, capturedFrameAndRecordedViewEstablished=True,
            sceneFidelityRequired=True, independentActorRequired=True, destinationCompositionRequired=True,
            pairedCleanupRequired=True, wholeFeatureRequired=True)
