"""Existing admitted input session for a closed ordinary Pending/Cancel flow."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import time
from adapters.native_clock_join import NativeClockAcquisition
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.snapshot_capture_runtime import IOSSnapshotCaptureRuntime
from ios.adapters.snapshot_pending_packets import PACKETS,PendingInputs,PendingChoices


class IOSSnapshotPendingRuntime(IOSSnapshotCaptureRuntime):
    @contextmanager
    def pending_owner(self,selector,run,client,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=False):
        from ios.adapters.snapshot_pending_owner import IOSSnapshotPendingOwner
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        with lock.held():
            sources=self._sources(selector)
            owner=IOSSnapshotPendingOwner(self,selector,run,lock,sources,phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic),
                epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,combined=combined)
            with self.existing_input_session(selector):yield owner

    def component(self,owner,kind,index,*,historical=False):
        from ios.adapters.snapshot_pending_owner import IOSSnapshotPendingOwner
        if not isinstance(owner,IOSSnapshotPendingOwner):return super().component(owner,kind,index,historical=historical)
        cls=owner.packet_class(kind);store=PrivateFeatureState(owner.store.path.with_name('pending-snapshot-primary-'+cls._name+'-'+format(index,'04d')+'.json'))
        args=(store,owner.lock,owner.binding,owner.run,'primary',index)
        if historical:return cls.history(*args)
        if kind=='manifest':return cls(*args,owner.sources['observer'],NativeClockAcquisition(owner.sources['clock_source'],epoch_ms=owner.epoch_ms,monotonic=owner.monotonic),owner.guard)
        return cls(*args,owner.sources['observer'],owner.sources['clock_source'],owner.guard,epoch_ms=owner.epoch_ms,monotonic=owner.monotonic)

    def inputs(self,owner,*,historical=False,choices=False):
        from ios.adapters.snapshot_pending_owner import IOSSnapshotPendingOwner
        if not isinstance(owner,IOSSnapshotPendingOwner):
            from adapters.native_feature_observation import need
            need(not choices);return super().inputs(owner,historical=historical)
        cls=PendingChoices if choices else PendingInputs;args=(PrivateFeatureState(owner.store.path.with_name(cls.store_name('primary'))),owner.lock,owner.binding,owner.run,'primary')
        if historical:return cls.history(*args)
        return cls(*args,owner.sources['native'],owner.guard)
