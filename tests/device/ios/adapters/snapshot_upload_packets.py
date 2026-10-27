"""Closed Upload journals; old Capture/Photos/Share namespaces stay literal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.original_packet_segments import OriginalPacketSegments
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_source_packet import SnapshotWorkPacket,SnapshotCapturesPacket,SnapshotExportsPacket,SnapshotInputsPacket
from ios.adapters.snapshot_file_work_packet import SnapshotFileWorkPacket
from ios.adapters import snapshot_uploads,snapshot_combined_preflight_http


class UploadSegments(OriginalPacketSegments):PROFILE='snapshot-upload-sources'


class SnapshotUploadInputs(SnapshotInputOwner):
    _owner_key='snapshotUploadInputOwnerVersion'
    _proof_namespace='upload-input-proof'
    _proof_schema='uploadInputProof'
    @staticmethod
    def store_name(role):return 'snapshot-upload-'+role+'-inputs.json'
    def decode(self,value):
        state=super().decode(value);events=state['events'];need(len(events)<=2)
        if events:need(events[0]['controlId'].startswith('snapshot.upload.'))
        if len(events)==2:need(events[1]['controlId']=='snapshot.upload-cancel')
        return state
    def reserve(self,control,original,*,operation='activate',text=None):
        need(type(control) is str and (control=='snapshot.upload-cancel' or control.startswith('snapshot.upload.')) and operation=='activate' and text is None)
        return super().reserve(control,original,operation=operation,text=text)


class UploadWorkPacket(SnapshotWorkPacket):
    _store_prefix='snapshot-upload';_key='snapshotUploadWorkPacketVersion';_namespace='upload-native-work';_schema='uploadNativeWork';_segments=UploadSegments


class UploadCapturesPacket(SnapshotCapturesPacket):
    _store_prefix='snapshot-upload';_key='snapshotUploadCapturesPacketVersion';_namespace='upload-native-captures';_schema='uploadNativeCaptures';_segments=UploadSegments


class UploadExportsPacket(SnapshotExportsPacket):
    _store_prefix='snapshot-upload';_key='snapshotUploadExportsPacketVersion';_namespace='upload-native-exports';_schema='uploadNativeExports';_segments=UploadSegments


class UploadInputsPacket(SnapshotInputsPacket):
    _store_prefix='snapshot-upload';_key='snapshotUploadInputsPacketVersion';_namespace='upload-native-inputs';_schema='uploadNativeInputs';_segments=UploadSegments


class UploadsPacket(SnapshotFileWorkPacket):
    _store_prefix='snapshot-upload';_name='native-uploads';_key='snapshotUploadsPacketVersion';_namespace='upload-native-uploads';_schema='uploadNativeUploads'
    _kind='uploads';_source=snapshot_uploads;_segments=UploadSegments;_segment_subject='uploads'


PACKETS={'uploads':UploadsPacket,'inputs':UploadInputsPacket,'work':UploadWorkPacket,'captures':UploadCapturesPacket,'exports':UploadExportsPacket}


class CombinedHttpSegments(OriginalPacketSegments):PROFILE='snapshot-combined-http'


class CombinedUploadHttpPacket(SnapshotFileWorkPacket):
    _store_prefix='snapshot-upload';_name='native-combined-http';_key='snapshotUploadCombinedHttpPacketVersion'
    _namespace='upload-combined-http';_schema='uploadCombinedHttp';_kind='combined-preflight-http'
    _source=snapshot_combined_preflight_http;_segments=CombinedHttpSegments;_segment_subject='upload'


def packet_types(frontend_http=False):
    need(type(frontend_http) is bool)
    return dict(PACKETS,http=CombinedUploadHttpPacket) if frontend_http else PACKETS
