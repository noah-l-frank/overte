"""Exact original Snapshot work/capture/export/input packets, without effects.

These closed owners reuse the existing native/host brackets, once-only query
responsibility and segmented immutable raw bytes. No source is synthesized and
no completed capture, destination, current permission or cleanup is inferred.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_packet_segments import OriginalPacketSegments
from ios.adapters.snapshot_file_work_packet import SnapshotFileWorkPacket
from ios.adapters import snapshot_work,snapshot_captures,snapshot_exports,snapshot_inputs


class SnapshotSourceSegments(OriginalPacketSegments):PROFILE='snapshot-native-sources'


class SnapshotWorkPacket(SnapshotFileWorkPacket):
    _name='native-work'
    _key='iosSnapshotWorkPacketVersion'
    _namespace='snapshot-native-work'
    _schema='snapshotNativeWork'
    _kind='script-work'
    _source=snapshot_work
    _segments=SnapshotSourceSegments
    _segment_subject='work'


class SnapshotCapturesPacket(SnapshotFileWorkPacket):
    _name='native-captures'
    _key='iosSnapshotCapturesPacketVersion'
    _namespace='snapshot-native-captures'
    _schema='snapshotNativeCaptures'
    _kind='captures'
    _source=snapshot_captures
    _segments=SnapshotSourceSegments
    _segment_subject='captures'


class SnapshotExportsPacket(SnapshotFileWorkPacket):
    _name='native-exports'
    _key='iosSnapshotExportsPacketVersion'
    _namespace='snapshot-native-exports'
    _schema='snapshotNativeExports'
    _kind='exports'
    _source=snapshot_exports
    _segments=SnapshotSourceSegments
    _segment_subject='exports'


class SnapshotInputsPacket(SnapshotFileWorkPacket):
    _name='native-inputs'
    _key='iosSnapshotInputsPacketVersion'
    _namespace='snapshot-native-inputs'
    _schema='snapshotNativeInputs'
    _kind='inputs'
    _source=snapshot_inputs
    _segments=SnapshotSourceSegments
    _segment_subject='inputs'


PACKETS={'work':SnapshotWorkPacket,'captures':SnapshotCapturesPacket,'exports':SnapshotExportsPacket,'inputs':SnapshotInputsPacket}
