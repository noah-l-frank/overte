"""Two canonical held SDK locks and the genuine normal Snapshot page factory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from pathlib import Path
import time
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUI
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.history import same
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters.snapshot_review_runtime import IOSSnapshotReviewRuntime
from ios.adapters.snapshot_scene_capture_order import SnapshotSceneActorSet,SnapshotSceneCaptureOrder


class IOSSnapshotScenePairRuntime(IOSSnapshotReviewRuntime):
    @contextmanager
    def scene_capture_order(self,primary_selector,actor_runtime,actor_selector,run,client,*,
            epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(actor_runtime,IOSSnapshotReviewRuntime) and all(callable(fn)for fn in(epoch_ms,monotonic,sleep)))
        primary_path=self.state_path(primary_selector).with_name('script-feature-sources.lock')
        actor_path=actor_runtime.state_path(actor_selector).with_name('script-feature-sources.lock')
        need(primary_path!=actor_path and all(path.is_absolute() and path.resolve(strict=False)==path for path in(primary_path,actor_path)))
        # Both roles use these SAME actual instances; no nested second flock.
        # Sorting actual canonical paths makes role inversions deterministic.
        locks={path:ScriptSourceLock(path)for path in(primary_path,actor_path)}
        with ExitStack()as stack:
            for path in sorted(locks,key=str):stack.enter_context(locks[path].held())
            own=self._sources(primary_selector);peer=actor_runtime._sources(actor_selector)
            need(own['binding']['targetFingerprint']!=peer['binding']['targetFingerprint']
                and all(own['binding'][key]==peer['binding'][key]for key in('sourceRevision','artifactSha256'))
                and own['session']==own['binding']['sessionId'])
            phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            page=IOSSnapshotPageOwner(self,primary_selector,run,locks[primary_path],own,
                ui=NativeUI(own['client'],own['session'],own['check']),phase=phase,epoch_ms=epoch_ms,
                monotonic=monotonic,sleep=sleep,combined=True)
            actors=SnapshotSceneActorSet(actor_path.parent,locks[actor_path],peer['binding'],run,phase.fixture_url,
                sources=peer,client=client,epoch_ms=epoch_ms,monotonic=monotonic)
            owner=SnapshotSceneCaptureOrder(page,actors,epoch_ms=epoch_ms,monotonic=monotonic)
            with self.existing_input_session(primary_selector):yield owner
