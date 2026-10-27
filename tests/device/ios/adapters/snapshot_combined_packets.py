"""Closed combined-manager work originals in their own retained namespaces."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.original_packet_segments import OriginalPacketSegments
from ios.adapters.snapshot_source_packet import SnapshotWorkPacket
from ios.adapters import snapshot_combined_work


class CombinedWorkSegments(OriginalPacketSegments):PROFILE='snapshot-combined-work'


class CombinedCaptureWorkPacket(SnapshotWorkPacket):
    _name='native-combined-work'
    _key='iosSnapshotCombinedWorkPacketVersion'
    _namespace='snapshot-native-combined-work'
    _schema='snapshotNativeCombinedWork'
    _kind='combined-script-work'
    _source=snapshot_combined_work
    _segments=CombinedWorkSegments
    _segment_subject='capture'
