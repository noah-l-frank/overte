"""Original Pending/PNG pair and its closed file-cleanup composition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import time
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.snapshot_pending_runtime import IOSSnapshotPendingRuntime
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_journey_files import IOSSnapshotJourneyFilesOwner


class IOSSnapshotJourneyFilesRuntime(IOSSnapshotPendingRuntime):
    @contextmanager
    def journey_files_owner(self,selector,run,client,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=False):
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        with lock.held():
            sources=self._sources(selector);capture=IOSSnapshotCaptureOwner(self,selector,run,lock,sources,
                phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic),epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,combined=combined)
            owner=IOSSnapshotJourneyFilesOwner(capture,combined=combined)
            with self.existing_input_session(selector):yield owner
