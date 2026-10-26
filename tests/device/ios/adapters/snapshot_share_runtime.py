"""Existing main/archive scopes for normal Share, without launching sessions."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
import time
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.snapshot_page_runtime import IOSSnapshotPageRuntime
from ios.adapters.snapshot_photos_context import PhotosClientContext
from ios.adapters.snapshot_share_process import SnapshotShareArchiveContext
from ios.adapters.snapshot_share_query_owner import SnapshotShareQueryOwner


class IOSSnapshotShareRuntime(IOSSnapshotPageRuntime):
    def query_owner(self,owner):return SnapshotShareQueryOwner(owner.archive,owner.archive_lock,epoch_ms=owner.epoch_ms,monotonic=owner.monotonic,sleep=owner.sleep)
    @contextmanager
    def share_owner(self,selector,run,client,archive,system_ui,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
        exact(archive,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
        main=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        separate=ScriptSourceLock(archive['sessionStore'].path.with_name('script-feature-sources.lock'));need(main.path!=separate.path)
        with ExitStack() as held:
            for lock in sorted((main,separate),key=lambda item:str(item.path)):held.enter_context(lock.held())
            captured=PrivateFeatureState(main.path.with_name('ios-snapshot-primary-capture-owner.json')).read();need(captured is not None)
            primary=PhotosClientContext(self,selector,captured['binding']);phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            companion=SnapshotShareArchiveContext(archive['client'],archive['sessionStore'],archive['target'],archive['binding'],archive['artifactPath'],
                archive['admissionStore'],separate,run,phase.fixture_url,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
            owner=IOSSnapshotShareOwner(self,selector,run,primary,companion,main,separate,phase,system_ui,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
            with self.existing_input_session(selector):yield owner

    @contextmanager
    def archive_end_owner(self,selector,run,client,archive,system_ui,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        """Retire the original Archive SDK without reopening a stopped helper."""
        from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
        from ios.adapters.snapshot_share_archive_end_owner import SnapshotShareArchiveEndOwner
        exact(archive,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
        main=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        separate=ScriptSourceLock(archive['sessionStore'].path.with_name('script-feature-sources.lock'));need(main.path!=separate.path)
        with ExitStack() as held:
            for lock in sorted((main,separate),key=lambda item:str(item.path)):held.enter_context(lock.held())
            captured=PrivateFeatureState(main.path.with_name('ios-snapshot-primary-capture-owner.json')).read();need(captured is not None)
            primary=PhotosClientContext(self,selector,captured['binding']);phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            share=IOSSnapshotShareOwner.history(PrivateFeatureState(main.path.with_name('snapshot-share-owner.json')),main,separate,captured['binding'],
                archive['binding'],run,phase.fixture_url,system_ui,primary.target['appId'],archive['artifactPath'],archive['admissionStore'])
            yield SnapshotShareArchiveEndOwner(share,primary,archive,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
