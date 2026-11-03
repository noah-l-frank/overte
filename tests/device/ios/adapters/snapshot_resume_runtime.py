"""Snapshot resume uses the retained candidate/session and one existing lock."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import time
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.lifecycle_background import LifecycleOSContext
from ios.adapters.snapshot_capture_review_owner import SnapshotCaptureReviewOwner
from ios.adapters.snapshot_resume_background import SnapshotResumeBackground,NAME
from ios.adapters.snapshot_resume_page import SnapshotResumePage
from ios.adapters.snapshot_resume_inputs import SnapshotResumeInputsPacket
from ios.adapters.snapshot_review_runtime import IOSSnapshotReviewRuntime


class IOSSnapshotResumeRuntime(IOSSnapshotReviewRuntime):
    @contextmanager
    def resume_owner(self,selector,run,client,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
        root=self.state_path(selector).parent;lock=ScriptSourceLock(root/'script-feature-sources.lock')
        with lock.held():
            store=PrivateFeatureState(root/NAME);saved=store.read()
            if saved is None:binding=self._sources(selector)['binding']
            else:
                need(type(saved) is dict and type(saved.get('iosSnapshotResumeOSOwnerVersion')) is int
                    and saved['iosSnapshotResumeOSOwnerVersion']==1 and saved.get('runId')==run)
                binding=context(saved['binding'])
            # This constructor and its OS probes explicitly allow background
            # continuity; no foreground _sources call is made on this branch.
            os=LifecycleOSContext(self,selector,binding)
            phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            def review():
                lock.assert_held()
                return SnapshotCaptureReviewOwner.archive(PrivateFeatureState(root/'ios-snapshot-rendered-review-owner.json'),
                    lock,binding,run,phase.fixture_url,monotonic=monotonic)
            def foreground():
                lock.assert_held();owner.file_guard();raw=os.foreground_sources();old=raw['check']
                need(same(raw['binding'],binding) and raw['session']==binding['sessionId'])
                def guard():owner.file_guard();need(old() is not False);return True
                raw['check']=guard;return raw
            def page():
                raw=foreground()
                return SnapshotResumePage(self,selector,run,lock,raw,
                    ui=NativeUI(raw['client'],raw['session'],raw['check']),phase=phase,
                    epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,combined=True)
            def packet(page,index,*,historical):
                need(type(page) is SnapshotResumePage and page.lock is lock and same(page.binding,binding)
                    and page.run==run and type(historical) is bool)
                cls=SnapshotResumeInputsPacket
                state=PrivateFeatureState(root/(cls._store_prefix+'-primary-'+cls._name+'-'+format(index,'04d')+'.json'))
                args=(state,lock,binding,run,'primary',index)
                if historical:return cls.history(*args)
                raw=foreground();tail=page.tail()
                if tail is not None:restore(raw['clock_source'],tail)
                return cls(*args,raw['observer'],raw['clock_source'],raw['check'],epoch_ms=epoch_ms,monotonic=monotonic)
            owner=SnapshotResumeBackground(store,os,run,lock,page,review,packet,
                epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
            with self.existing_input_session(selector):yield owner
            owner.file_guard()

    @contextmanager
    def rendered_resume_owner(self,selector,run,client,ticket,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
        from ios.adapters.snapshot_resume_review_images import SnapshotResumeReviewImages
        from ios.adapters.snapshot_resume_rendered_review_owner import SnapshotResumeRenderedReviewOwner
        with self.resume_owner(selector,run,client,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep) as bridge:
            bridge.act(ticket)
            page=bridge.page_factory();capture=bridge.review().capture
            raw=self._sources(selector)
            need(same(raw['binding'],bridge.binding) and raw['session']==bridge.binding['sessionId'])
            native=raw['clock_source']
            def clock():return native.read(native.sequence)['capturedEpochMs']
            def guard():bridge.file_guard();page.bound();return raw['check']()
            images=SnapshotResumeReviewImages(PrivateFeatureState(page.store.path.with_name('ios-snapshot-resume-review-screens.json')),
                page.store.path.parent,bridge.binding,run,'primary',1,raw['client'],clock,guard,
                source_lock=bridge.lock,epoch_ms=epoch_ms,monotonic=monotonic)
            yield SnapshotResumeRenderedReviewOwner(page,capture,images,bridge,monotonic=monotonic)
