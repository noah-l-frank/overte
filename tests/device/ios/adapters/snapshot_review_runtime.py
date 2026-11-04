"""Existing bound SNAP page, completed capture and original WDA PNG factory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import time
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_page_runtime import IOSSnapshotPageRuntime
from ios.adapters.snapshot_capture_review_owner import SnapshotCaptureReviewOwner
from ios.adapters.snapshot_review_images import SnapshotReviewImages


class IOSSnapshotReviewRuntime(IOSSnapshotPageRuntime):
    @contextmanager
    def rendered_review_owner(self,selector,run,client,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
        # Reuse the page's actual held serialization instance and existing SDK
        # session. This creates no second lock domain or app/source lifetime.
        with self.page_owner(selector,run,client,combined=True) as page:
            page.epoch_ms,page.monotonic,page.sleep=epoch_ms,monotonic,sleep
            page.phase.epoch_ms,page.phase.monotonic=epoch_ms,monotonic
            source=self._sources(selector);need(same(source['binding'],page.binding)
                and source['session']==source['binding']['sessionId'])
            capture=IOSSnapshotCaptureOwner.archive(PrivateFeatureState(page.store.path.with_name('ios-snapshot-primary-capture-owner.json')),
                page.lock,page.binding,run,page.fixture_url,combined=True)
            native=source['clock_source']
            def clock():return native.read(native.sequence)['capturedEpochMs']
            def guard():page.bound();return source['check']()
            images=SnapshotReviewImages(PrivateFeatureState(page.store.path.with_name('ios-snapshot-review-screens.json')),
                page.store.path.parent,page.binding,run,'primary',0,source['client'],clock,guard,
                source_lock=page.lock,epoch_ms=epoch_ms,monotonic=monotonic)
            yield SnapshotCaptureReviewOwner(page,capture,images,monotonic=monotonic)

    @contextmanager
    def scene_actor_owner(self,selector,run,client,index,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        """Optional independent Actor source; no normal Snapshot input or launch.

        The caller supplies a separate already admitted runtime/selector. The
        typed join subsequently rejects a shared target, directory or lock.
        """
        from adapters.script_feature.lock import ScriptSourceLock
        from feature_journeys.phase_fixture import PhaseFixtureReader
        from ios.adapters.snapshot_scene_witness import SnapshotSceneWitnessOwner
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        with lock.held():
            source=self._sources(selector)
            phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            owner=SnapshotSceneWitnessOwner(PrivateFeatureState(lock.path.with_name('ios-snapshot-actor-scene-witness-'+format(index,'04d')+'.json')),
                lock,source['binding'],run,index,phase.fixture_url,phase=phase,feature=source['observer'],native=source['clock_source'],
                guard=source['check'],epoch_ms=epoch_ms,monotonic=monotonic)
            yield owner

    @staticmethod
    def joined_scene_review(review,provenance,actor,actor_original):
        from ios.adapters.snapshot_scene_review_join import SnapshotSceneReviewJoin
        return SnapshotSceneReviewJoin(review,provenance,actor,actor_original).proof()
