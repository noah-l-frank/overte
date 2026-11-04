"""One-send actor-only native pixel packet; original PFS/OFS ownership."""
from adapters.native_feature_observation import need
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket
from ios.adapters import snapshot_actor_pixels
class SnapshotActorPixelPacket(SnapshotOwnedPacket):
    _name='native-actor-pixels';_key='iosSnapshotActorPixelPacketVersion'
    _namespace='snapshot-native-actor-pixels';_schema='snapshotNativeActorPixels'
    _kind='actor-pixels';_source=snapshot_actor_pixels
    def setup(self,store,lock,binding,run,role,index):
        need(role=='actor');super().setup(store,lock,binding,run,role,index)
