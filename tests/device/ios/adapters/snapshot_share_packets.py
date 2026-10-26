"""Closed Share-only input/original profiles; Capture/Photos remain exact."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.original_packet_segments import OriginalPacketSegments
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_source_packet import SnapshotExportsPacket,SnapshotInputsPacket


class ShareNativeSegments(OriginalPacketSegments):PROFILE='share-native-sources'


class SnapshotShareInputs(SnapshotInputOwner):
    _owner_key='snapshotShareInputOwnerVersion'
    _proof_namespace='share-input-proof'
    _proof_schema='shareInputProof'
    @staticmethod
    def store_name(role):return 'snapshot-share-'+role+'-inputs.json'
    def decode(self,value):
        state=super().decode(value);need(all(row['controlId'].startswith('snapshot.share.') for row in state['events']));return state
    def reserve(self,control,original,*,operation='activate',text=None):
        need(type(control) is str and control.startswith('snapshot.share.') and operation=='activate' and text is None)
        return super().reserve(control,original,operation=operation,text=text)


class SnapshotShareExportsPacket(SnapshotExportsPacket):
    _store_prefix='snapshot-share'
    _key='snapshotShareExportsPacketVersion'
    _namespace='share-native-exports'
    _schema='shareNativeExports'
    _segments=ShareNativeSegments


class SnapshotShareInputsPacket(SnapshotInputsPacket):
    _store_prefix='snapshot-share'
    _key='snapshotShareInputsPacketVersion'
    _namespace='share-native-inputs'
    _schema='shareNativeInputs'
    _segments=ShareNativeSegments


PACKETS={'exports':SnapshotShareExportsPacket,'inputs':SnapshotShareInputsPacket}
