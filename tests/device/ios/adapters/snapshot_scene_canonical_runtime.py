"""Canonical Actor scene publication before and after the unchanged normal cut."""
from copy import deepcopy
from contextlib import contextmanager
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_scene_capture_order import SnapshotSceneCaptureOrder
from ios.adapters.snapshot_scene_pair_runtime import IOSSnapshotScenePairRuntime
from ios.adapters.snapshot_scene_publication import SnapshotSceneCanonicalPublication


class SnapshotScenePublishedCaptureOrder(SnapshotSceneCaptureOrder):
    def __init__(self,page,actors,*,epoch_ms,monotonic,actor_client=None,historical=False):
        super().__init__(page,actors,epoch_ms=epoch_ms,monotonic=monotonic,historical=historical)
        self.publication=SnapshotSceneCanonicalPublication(actors,actor_client,historical=historical)

    def actor(self,index,*,born_here):
        # Historical WAL preparation precedes the new actual native read.
        self.publication.prepare()
        reference,measured=super().actor(index,born_here=born_here)
        self.publication.publish(index)
        return reference,measured

    @classmethod
    def archive(cls,*args,epoch_ms,monotonic):
        need(cls is SnapshotScenePublishedCaptureOrder)
        original=SnapshotSceneCaptureOrder.archive(*args,epoch_ms=epoch_ms,monotonic=monotonic)
        return cls(original.page,original.actors,epoch_ms=epoch_ms,monotonic=monotonic,historical=True)

    @operation
    def proof(self):
        original=super().proof();rows=self.publication.history();references=[self.state['before'],self.state['attempts'][-1]['original']];published=[]
        for reference in references:
            matches=[row for row in rows if row['intent']['body']['actorSequence']==reference['index']]
            need(len(matches)==1);row=matches[0];retained=row['intent']['original']
            need(row['mode']=='published'and retained['ownerSha256']==reference['ownerSha256']and retained['packetOwnerSha256']==reference['packetOwnerSha256']
                and row['intent']['body']['ticket']==original['ticket'])
            published.append(dict(index=reference['index'],originalSha256=digest(retained),receiptSha256=digest(row),entry=deepcopy(row['entry'])))
        return dict(iosSnapshotCanonicalSceneOrderVersion=1,orderedOriginal=original,canonicalActorScenePublications=published,
            canonicalActorScenePublicationEstablished=True,unchangedTemporalOriginalsEstablished=True,
            snapshotUIOutputWitnessRequired=True,actorRenderedPixelsAndReadbackCropRequired=True,
            destinationCompositionRequired=True,pairedEndRequired=True,nativeQualified=False,deviceQualified=False,wholeQualified=False)


class IOSSnapshotSceneCanonicalRuntime(IOSSnapshotScenePairRuntime):
    @contextmanager
    def scene_actor_publications(self,selector,run,actor_client,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        with actor_publications(self,selector,run,actor_client,epoch_ms=epoch_ms,monotonic=monotonic)as operation_owner:
            yield operation_owner

    @contextmanager
    def published_scene_capture_order(self,primary_selector,actor_runtime,actor_selector,run,client,actor_client,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
        # The original factory owns both real held locks, SDK source bindings,
        # ordinary Page constructor and existing input session for this scope.
        need(actor_client is not client and actor_client.url==client.url and actor_client.token!=client.token)
        with self.scene_capture_order(primary_selector,actor_runtime,actor_selector,run,client,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)as original:
            need(type(original)is SnapshotSceneCaptureOrder)
            yield SnapshotScenePublishedCaptureOrder(original.page,original.actors,epoch_ms=epoch_ms,monotonic=monotonic,actor_client=actor_client)


class SnapshotSceneActorSampleOperation:
    """Actor-only source operation; receives no Primary owner, facts or packet."""
    def __init__(self,actors,actor_client):
        self.actors=actors;self.monotonic=actors.monotonic
        self.publication=SnapshotSceneCanonicalPublication(actors,actor_client)

    @operation
    def observe_original(self,index,ticket):
        from adapters.native_feature_observation import integer
        from feature_journeys.contract import identifier
        need(integer(index,1,8));identifier(ticket)
        self.publication.prepare() # All old publisher work precedes native read.
        self.actors.native_floor(range(1,index+1))
        witness=self.actors.owner(index,historical=False)
        original=witness.acquire(ticket);witness.validate_original(original)
        self.publication.publish(index)
        matches=[row for row in self.publication.history()if row['intent']['body']['actorSequence']==index]
        need(len(matches)==1 and matches[0]['mode']=='published')
        return dict(snapshotSceneActorPublishedOriginalVersion=1,original=deepcopy(original),publication=deepcopy(matches[0]),
            canonicalSceneOriginalPublished=True,snapshotUIOutputFactsEstablished=False,actorPixelsEstablished=False,
            processOrSDKEndEstablished=False,nativeQualified=False,wholeQualified=False)


@contextmanager
def actor_publications(runtime,selector,run,actor_client,*,epoch_ms,monotonic):
    """Existing bound SDK and genuine held lock; no session/source creation."""
    from adapters.script_feature.lock import ScriptSourceLock
    from ios.adapters.snapshot_scene_capture_order import SnapshotSceneActorSet
    path=runtime.state_path(selector).with_name('script-feature-sources.lock')
    lock=ScriptSourceLock(path)
    with lock.held():
        source=runtime._sources(selector)
        actors=SnapshotSceneActorSet(path.parent,lock,source['binding'],run,actor_client.url+'/runs/'+run+'/',
            sources=source,client=actor_client,epoch_ms=epoch_ms,monotonic=monotonic)
        yield SnapshotSceneActorSampleOperation(actors,actor_client)
