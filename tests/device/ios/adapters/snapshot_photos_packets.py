"""Closed Photos Save journals reusing the original Snapshot source owners.

The capture owner keeps its original names, formats and exact census. These
separate journals cannot be adopted by that owner or overwrite its old frames.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_packet_segments import OriginalPacketSegments
from adapters.native_feature_observation import need
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_source_packet import SnapshotExportsPacket,SnapshotInputsPacket


class PhotosSaveSegments(OriginalPacketSegments):PROFILE='photos-save-sources'


class PhotosSaveInputs(SnapshotInputOwner):
    _owner_key='photosSaveInputOwnerVersion'
    _proof_namespace='photos-save-input-proof'
    _proof_schema='photosSaveInputProof'
    @staticmethod
    def store_name(role):return 'photos-save-'+role+'-inputs.json'
    def decode(self,value):
        state=super().decode(value);need(all(row['controlId'].startswith('snapshot.save.') for row in state['events']));return state
    def reserve(self,control,original,*,operation='activate',text=None):
        need(type(control) is str and control.startswith('snapshot.save.') and operation=='activate' and text is None)
        return super().reserve(control,original,operation=operation,text=text)


class PhotosSaveExportsPacket(SnapshotExportsPacket):
    _store_prefix='photos-save'
    _key='photosSaveExportsPacketVersion'
    _namespace='photos-save-exports'
    _schema='photosSaveExports'
    _segments=PhotosSaveSegments


class PhotosSaveInputsPacket(SnapshotInputsPacket):
    _store_prefix='photos-save'
    _key='photosSaveInputsPacketVersion'
    _namespace='photos-save-inputs'
    _schema='photosSaveInputs'
    _segments=PhotosSaveSegments


PACKETS={'exports':PhotosSaveExportsPacket,'inputs':PhotosSaveInputsPacket}
