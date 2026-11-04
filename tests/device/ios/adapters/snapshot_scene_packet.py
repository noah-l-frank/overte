"""Real PFS/OFS/native bracket owner of one passive consumed-scene original."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket
from ios.adapters import snapshot_scene


class SnapshotScenePacket(SnapshotOwnedPacket):
    _name='native-scene'
    _key='iosSnapshotScenePacketVersion'
    _namespace='snapshot-native-scene'
    _schema='snapshotNativeScene'
    _kind='scene-inputs'
    _source=snapshot_scene
