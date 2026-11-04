"""Existing held independent Actor scope, separate rendered-PNG owner type."""
from adapters.native_feature_observation import integer,need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.snapshot_scene_capture_order import SnapshotSceneActorSet
from ios.adapters.snapshot_actor_pixel_witness import SnapshotActorPixelWitnessOwner
class SnapshotActorPixelSet(SnapshotSceneActorSet):
    def store(self,index):
        need(integer(index,1,8));return PrivateFeatureState(self.root/('ios-snapshot-actor-render-witness-'+format(index,'04d')+'.json'))
    def owner(self,index,*,historical):
        self.lock.assert_held();store=self.store(index)
        if historical:return SnapshotActorPixelWitnessOwner(store,self.lock,self.binding,self.run,index,self.fixture_url,historical=True)
        need(self.sources is not None and self.sources['check']()is not False)
        phase=PhaseFixtureReader(self.client,self.run,'snapshots',epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        return SnapshotActorPixelWitnessOwner(store,self.lock,self.binding,self.run,index,self.fixture_url,phase=phase,
            feature=self.sources['observer'],native=self.sources['clock_source'],guard=self.sources['check'],epoch_ms=self.epoch_ms,monotonic=self.monotonic)
