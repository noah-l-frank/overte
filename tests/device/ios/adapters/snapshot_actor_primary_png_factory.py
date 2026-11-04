"""Existing genuine historical factories under two already-held source locks."""
from adapters.native_feature_observation import integer,need
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_actor_pixel_set import SnapshotActorPixelSet
from ios.adapters.snapshot_actor_pixel_publication import SnapshotActorPixelCanonicalPublication
from ios.adapters.snapshot_actor_primary_png_join import SnapshotActorPrimaryPNGJoin

def retained_original_pixel_join(capture,provenance_index,actors,actor_index):
    need(type(capture)is IOSSnapshotCaptureOwner and type(actors)is SnapshotActorPixelSet
        and integer(provenance_index,1,128)and integer(actor_index,1,8))
    capture.lock.assert_held();actors.lock.assert_held()
    primary=IOSSnapshotCaptureOwner.archive(capture.store,capture.lock,capture.binding,capture.run,capture.phase.fixture_url,combined=capture.combined)
    provenance=primary.history('provenance',provenance_index)
    history=SnapshotActorPixelSet(actors.root,actors.lock,actors.binding,actors.run,actors.fixture_url)
    actor=history.owner(actor_index,historical=True)
    publication=SnapshotActorPixelCanonicalPublication(history,historical=True)
    return SnapshotActorPrimaryPNGJoin(primary,provenance,actor,actor.original(),publication)
