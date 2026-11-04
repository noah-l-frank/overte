"""Independent existing Actor runtime -> original PNG -> canonical /samples.

There is no Primary owner argument, UI expected state, extra Source/SDK session,
or device/renderer qualification in this factory.
"""
from contextlib import contextmanager
import time
from copy import deepcopy
from adapters.native_feature_observation import integer,need
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_scene_canonical_runtime import IOSSnapshotSceneCanonicalRuntime
from ios.adapters.snapshot_actor_pixel_set import SnapshotActorPixelSet
from ios.adapters.snapshot_actor_pixel_publication import SnapshotActorPixelCanonicalPublication
class SnapshotActorPixelOperation:
    def __init__(self,actors,actor_client):
        need(type(actors)is SnapshotActorPixelSet)
        self.actors,self.monotonic=actors,actors.monotonic
        self.publication=SnapshotActorPixelCanonicalPublication(actors,actor_client)
    @operation
    def observe_original(self,index,ticket):
        need(integer(index,1,8));identifier(ticket)
        self.publication.prepare() # All historical publisher work precedes native acquisition.
        self.actors.native_floor(range(1,index+1));witness=self.actors.owner(index,historical=False)
        original=witness.acquire(ticket);measured=witness.validate_original(original)
        self.publication.publish(index)
        matches=[row for row in self.publication.history()if row['intent']['body']['actorSequence']==index]
        need(len(matches)==1 and matches[0]['mode']=='published')
        return dict(snapshotActorPixelPublishedOriginalVersion=1,original=deepcopy(original),publication=deepcopy(matches[0]),
            actorRenderPngOriginalRetained=True,canonicalActorPixelOriginalPublished=True,
            actorPixelSha256=measured['nativeOriginal']['packet']['source']['frame']['readback']['pixelSha256'],
            primaryPixelComparisonEstablished=False,completeSceneFidelityEstablished=False,
            independentProcessAuthenticationEstablished=False,processOrSDKEndEstablished=False,
            nativeQualified=False,deviceQualified=False,wholeQualified=False)
class IOSSnapshotActorPixelRuntime(IOSSnapshotSceneCanonicalRuntime):
    @contextmanager
    def actor_pixel_publications(self,selector,run,actor_client,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        path=self.state_path(selector).with_name('script-feature-sources.lock');lock=ScriptSourceLock(path)
        with lock.held():
            source=self._sources(selector)
            actors=SnapshotActorPixelSet(path.parent,lock,source['binding'],run,actor_client.url+'/runs/'+run+'/',sources=source,client=actor_client,epoch_ms=epoch_ms,monotonic=monotonic)
            yield SnapshotActorPixelOperation(actors,actor_client)
