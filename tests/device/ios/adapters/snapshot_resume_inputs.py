"""Existing raw native Snapshot-input owner in a separate resumed namespace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_packet_segments import OriginalPacketSegments
from ios.adapters.snapshot_source_packet import SnapshotInputsPacket


class SnapshotResumeSegments(OriginalPacketSegments):PROFILE='snapshot-resume-sources'


class SnapshotResumeInputsPacket(SnapshotInputsPacket):
    _store_prefix='resume-snapshot'
    _key='iosSnapshotResumeInputsPacketVersion'
    _namespace='snapshot-resume-native-inputs'
    _schema='snapshotResumeNativeInputs'
    _segments=SnapshotResumeSegments
