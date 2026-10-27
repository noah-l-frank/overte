"""Existing separately admitted SDK scopes for the internal Photos Save owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
import time
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.snapshot_page_runtime import IOSSnapshotPageRuntime
from ios.adapters.snapshot_photos_context import PhotosClientContext,PhotosCompanionContext


class IOSSnapshotPhotosRuntime(IOSSnapshotPageRuntime):
    @contextmanager
    def photos_owner(self,selector,run,fixture_client,companion,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=False):
        need(type(combined) is bool)
        from ios.adapters.snapshot_photos_owner import IOSSnapshotPhotosOwner
        exact(companion,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
        need(isinstance(companion['sessionStore'],PrivateFeatureState) and isinstance(companion['admissionStore'],PrivateFeatureState))
        main=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        helper=ScriptSourceLock(companion['sessionStore'].path.with_name('script-feature-sources.lock'))
        need(main.path!=helper.path)
        with ExitStack() as held:
            for lock in sorted((main,helper),key=lambda value:str(value.path)):held.enter_context(lock.held())
            captured=PrivateFeatureState(main.path.with_name('ios-snapshot-primary-capture-owner.json')).read();need(captured is not None)
            primary=PhotosClientContext(self,selector,captured['binding'])
            phase=PhaseFixtureReader(fixture_client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            separate=PhotosCompanionContext(companion['client'],companion['sessionStore'],companion['target'],companion['binding'],
                companion['artifactPath'],companion['admissionStore'],helper,run,phase.fixture_url,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
            owner=IOSSnapshotPhotosOwner(self,selector,run,primary,separate,main,helper,phase,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,combined=combined)
            with self.existing_input_session(selector):yield owner
