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
    def share_owner(self,selector,run,client,archive,system_ui,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=False):
        from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
        need(type(combined) is bool)
        exact(archive,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
        main=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        separate=ScriptSourceLock(archive['sessionStore'].path.with_name('script-feature-sources.lock'));need(main.path!=separate.path)
        with ExitStack() as held:
            for lock in sorted((main,separate),key=lambda item:str(item.path)):held.enter_context(lock.held())
            captured=PrivateFeatureState(main.path.with_name('ios-snapshot-primary-capture-owner.json')).read();need(captured is not None)
            primary=PhotosClientContext(self,selector,captured['binding']);phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            companion=SnapshotShareArchiveContext(archive['client'],archive['sessionStore'],archive['target'],archive['binding'],archive['artifactPath'],
                archive['admissionStore'],separate,run,phase.fixture_url,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
            owner=IOSSnapshotShareOwner(self,selector,run,primary,companion,main,separate,phase,system_ui,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,combined=combined)
            with self.existing_input_session(selector):yield owner

    @contextmanager
    def archive_end_owner(self,selector,run,client,archive,system_ui,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=False):
        """Retire the original Archive SDK without reopening a stopped helper."""
        from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
        from ios.adapters.snapshot_share_archive_end_owner import SnapshotShareArchiveEndOwner
        need(type(combined) is bool)
        exact(archive,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
        main=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        separate=ScriptSourceLock(archive['sessionStore'].path.with_name('script-feature-sources.lock'));need(main.path!=separate.path)
        with ExitStack() as held:
            for lock in sorted((main,separate),key=lambda item:str(item.path)):held.enter_context(lock.held())
            captured=PrivateFeatureState(main.path.with_name('ios-snapshot-primary-capture-owner.json')).read();need(captured is not None)
            primary=PhotosClientContext(self,selector,captured['binding']);phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            share=IOSSnapshotShareOwner.history(PrivateFeatureState(main.path.with_name('snapshot-share-owner.json')),main,separate,captured['binding'],
                archive['binding'],run,phase.fixture_url,system_ui,primary.target['appId'],archive['artifactPath'],archive['admissionStore'],combined=combined)
            yield SnapshotShareArchiveEndOwner(share,primary,archive,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)

    @contextmanager
    def page_return_owner(self,selector,run,client,archive,system_ui,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=False,photos_end=None):
        """Restore Page; optionally hand its completed Combined2 to Photos End."""
        from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
        from ios.adapters.snapshot_journey_files import IOSSnapshotJourneyFilesOwner
        from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner
        from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
        from ios.adapters.snapshot_share_archive_end_owner import SnapshotShareArchiveEndOwner
        need(type(combined) is bool)
        if photos_end is not None:
            exact(photos_end,{'profile','photos','domainPolicy'})
            need(combined is True and type(photos_end['profile']) is str
                and photos_end['profile']=='combined-photos-return-v2')
        exact(archive,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
        main=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        separate=ScriptSourceLock(archive['sessionStore'].path.with_name('script-feature-sources.lock'));need(main.path!=separate.path)
        with ExitStack() as held:
            for lock in sorted((main,separate),key=lambda item:str(item.path)):held.enter_context(lock.held())
            captured=PrivateFeatureState(main.path.with_name('ios-snapshot-primary-capture-owner.json')).read();need(captured is not None)
            primary=PhotosClientContext(self,selector,captured['binding']);phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            page=IOSSnapshotPageOwner.archive(PrivateFeatureState(main.path.with_name('ios-snapshot-page-owner.json')),main,captured['binding'],run,phase.fixture_url,combined=combined)
            files=IOSSnapshotJourneyFilesOwner.archive(PrivateFeatureState(main.path.with_name('ios-snapshot-journey-files-owner.json')),main,captured['binding'],run,phase.fixture_url,combined=combined)
            share=IOSSnapshotShareOwner.history(PrivateFeatureState(main.path.with_name('snapshot-share-owner.json')),main,separate,captured['binding'],
                archive['binding'],run,phase.fixture_url,system_ui,primary.target['appId'],archive['artifactPath'],archive['admissionStore'],combined=combined)
            end=SnapshotShareArchiveEndOwner.history(share,archive)
            owner=SnapshotPageReturnOwner(self,selector,primary,phase,page,files,end,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,combined=combined)
            with self.existing_input_session(selector):yield owner

        if photos_end is not None:
            # The original Page/input/two-lock scope has ended. The End factory
            # owns its exact three existing lock objects in canonical path order.
            need(owner.state['result'] is not None)
            with self.photos_end_owner(selector,run,client,photos_end['photos'],archive,system_ui,
                    photos_end['domainPolicy'],primary_bundle=primary.target['appId'],profile=photos_end['profile'],
                    epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep) as ended:
                ended.finalize()

    @contextmanager
    def photos_end_owner(self,selector,run,client,photos,archive,system_ui,domain_policy,*,primary_bundle,profile=None,
            epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        """Explicit completed Result2 handoff to the existing Photos End owner.

        Main/Actor/fixture/source ownership is not discharged. No SDK is
        created and no completed journey is inferred from the public result.
        """
        need(type(profile) is str and profile=='combined-photos-return-v2'
            and type(primary_bundle) is str and bool(primary_bundle)
            and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        for helper in (photos,archive):
            exact(helper,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
            need(isinstance(helper['sessionStore'],PrivateFeatureState) and isinstance(helper['admissionStore'],PrivateFeatureState))
        from ios.adapters.snapshot_capture_clock import Budget
        from adapters.operation_transport_guard import scope as transport_scope
        from ios.adapters.snapshot_photos_end_originals import SnapshotPhotosEndOriginals
        from ios.adapters.snapshot_photos_end_owner import SnapshotPhotosEndOwner
        from adapters.script_feature.history import same
        budget=Budget(monotonic)
        with transport_scope(budget.check):
            sources=self._sources(selector);budget.check()
            main=dict(root=str(self.state_path(selector).parent),binding=sources['binding'])
            def recorded(helper):
                return dict(root=str(helper['sessionStore'].path.parent),binding=helper['binding'],
                    artifactPath=str(helper['artifactPath']),sessionPath=str(helper['sessionStore'].path),
                    admissionPath=str(helper['admissionStore'].path),target=helper['target'])
            phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            factory=SnapshotPhotosEndOriginals(main,recorded(photos),recorded(archive),run=run,fixture_url=phase.fixture_url,
                primary_bundle=primary_bundle,system_ui=system_ui,domain_policy=domain_policy,reuse_originals=True)
            with ExitStack() as held:
                for lock in sorted(factory.locks.values(),key=lambda item:str(item.path)):held.enter_context(lock.held())
                factory.check_locks();need(sources['check']() is not False);budget.check()
                with factory.read_journey() as journey:
                    # Literal original Result2 must be complete BEFORE any live
                    # helper query or End WAL. The passive area closes here.
                    result=journey.proof()
                    need(result['snapshotCombinedJourneyResultVersion']==2 and result['photosSDKRetirementRequired'] is True
                        and same(journey.photos.binding,sources['binding']))
                budget.check();factory.check_locks()
                owner=SnapshotPhotosEndOwner(journey,photos,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
                budget.check();yield owner;budget.check();factory.check_locks()
