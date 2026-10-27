"""Internal still/PNG capture composition on an existing installed candidate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import time
from adapters.native_clock_join import NativeClockAcquisition
from adapters.native_feature_observation import need
from adapters.native_script_roots import NativeScriptRoots,FILE,LIMIT
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.snapshot_source_packet import PACKETS
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.adapters.snapshot_chunk_owner import SnapshotChunk
from ios.adapters.snapshot_artifact import SnapshotArtifact
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket
from ios.adapters.snapshot_file_work_packet import SnapshotFileWorkPacket
from ios.adapters.snapshot_remove_owner import SnapshotRemoveOwner

TYPES=dict(PACKETS,manifest=SnapshotManifest,chunk=SnapshotChunk,artifact=SnapshotArtifact,
    owned=SnapshotOwnedPacket,filework=SnapshotFileWorkPacket,remove=SnapshotRemoveOwner)


class IOSSnapshotCaptureRuntime(IOSScriptRuntime):
    @contextmanager
    def upload_owner(self,selector,run,client,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=False,frontend_http=False,frontend_caller=False):
        need(type(combined) is type(frontend_http) is type(frontend_caller) is bool and (not frontend_http or combined) and (not frontend_caller or frontend_http))
        from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
        from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        with lock.held():
            sources=self._sources(selector);phase=PhaseFixtureReader(client,run,'snapshots',epoch_ms=epoch_ms,monotonic=monotonic)
            capture=IOSSnapshotCaptureOwner.archive(PrivateFeatureState(lock.path.with_name('ios-snapshot-primary-capture-owner.json')),lock,sources['binding'],run,phase.fixture_url,combined=combined)
            owner=IOSSnapshotUploadOwner(self,selector,run,lock,sources,capture,phase,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,combined=combined,frontend_http=frontend_http,frontend_caller=frontend_caller)
            with self.existing_input_session(selector):yield owner

    @contextmanager
    def capture_owner(self,selector,run,client,*,combined=False):
        from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'));failure=None
        with lock.held():
            try:
                source=self._sources(selector)
                owner=IOSSnapshotCaptureOwner(self,selector,run,lock,source,
                    phase=PhaseFixtureReader(client,run,'snapshots'),epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=combined)
                with self.existing_input_session(selector):yield owner
            except BaseException as original:failure=original
        if failure is not None:raise failure

    @staticmethod
    def component_type(owner,kind):
        if kind=='work' and getattr(owner,'combined',False):
            from ios.adapters.snapshot_combined_packets import CombinedCaptureWorkPacket
            return CombinedCaptureWorkPacket
        return TYPES[kind]

    def component(self,owner,kind,index,*,historical=False):
        cls=self.component_type(owner,kind);name=cls._name if hasattr(cls,'_name') else kind
        store=PrivateFeatureState(owner.store.path.with_name('ios-snapshot-primary-'+name+'-'+format(index,'04d')+'.json'))
        arguments=(store,owner.lock,owner.binding,owner.run,'primary',index)
        if historical and kind!='artifact':return cls.history(*arguments)
        guard=(lambda:True) if historical else owner.guard
        if kind=='artifact':return cls(*arguments,guard)
        if kind in ('manifest','chunk'):
            return cls(*arguments,owner.sources['observer'],NativeClockAcquisition(owner.sources['clock_source'],epoch_ms=owner.epoch_ms,monotonic=owner.monotonic),guard)
        return cls(*arguments,owner.sources['observer'],owner.sources['clock_source'],guard,epoch_ms=owner.epoch_ms,monotonic=owner.monotonic)

    def inputs(self,owner,*,historical=False):
        store=PrivateFeatureState(owner.store.path.with_name('ios-snapshot-primary-inputs.json'))
        arguments=(store,owner.lock,owner.binding,owner.run,'primary')
        if historical:return SnapshotInputOwner.history(*arguments)
        return SnapshotInputOwner(*arguments,owner.sources['native'],owner.guard)

    def roots(self,owner):
        source=owner.sources;native=source['clock_source'];observer=source['observer']
        reader=NativeScriptRoots(observer.send,lambda:observer.original(remote=observer.remote.rsplit('/',1)[0]+'/'+FILE,limit=LIMIT),
            lambda:native.read(native.sequence)['capturedEpochMs'],owner.guard,int(owner.binding['processIdentity']),ios=True,
            monotonic=owner.monotonic,sleep=owner.sleep)
        acquisition=NativeClockAcquisition(native,epoch_ms=owner.epoch_ms,monotonic=owner.monotonic)
        acquisition.begin(owner.epoch_ms());packet=reader.read(0)
        return dict(packet=packet,clockJoin=acquisition.finish(dict(roots=packet),[('roots','capturedEpochMs')]))
