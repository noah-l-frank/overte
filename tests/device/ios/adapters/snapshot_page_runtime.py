"""Normal SNAP navigation on the existing bound iOS input session."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
import time
from adapters.normal_ui import NativeUI
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.snapshot_capture_runtime import IOSSnapshotCaptureRuntime


class IOSSnapshotPageRuntime(IOSSnapshotCaptureRuntime):
    def roots(self,owner):
        from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
        if not isinstance(owner,IOSSnapshotPageOwner):return super().roots(owner)
        from adapters.native_script_roots import NativeScriptRoots,FILE,LIMIT
        from adapters.native_clock_join import NativeClockAcquisition
        source=owner.sources;native=source['clock_source'];observer=source['observer']
        def send(query):owner.query_intent(query);return observer.send(query)
        reader=NativeScriptRoots(send,lambda:observer.original(remote=observer.remote.rsplit('/',1)[0]+'/'+FILE,limit=LIMIT),
            lambda:native.read(native.sequence)['capturedEpochMs'],owner.guard,int(owner.binding['processIdentity']),ios=True,
            monotonic=owner.monotonic,sleep=owner.sleep)
        acquisition=NativeClockAcquisition(native,epoch_ms=owner.epoch_ms,monotonic=owner.monotonic)
        acquisition.begin(owner.epoch_ms());packet=reader.read(0)
        return dict(packet=packet,clockJoin=acquisition.finish(dict(roots=packet),[('roots','capturedEpochMs')]))

    @contextmanager
    def page_owner(self,selector,run,client,*,combined=False):
        from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'));failure=None
        with lock.held():
            try:
                source=self._sources(selector)
                owner=IOSSnapshotPageOwner(self,selector,run,lock,source,
                    ui=NativeUI(source['client'],source['session'],source['check']),
                    phase=PhaseFixtureReader(client,run,'snapshots'),epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,combined=combined)
                with self.existing_input_session(selector):yield owner
            except BaseException as original:failure=original
        if failure is not None:raise failure

    def capture_child(self,owner):
        """Use the same held OS lock, retaining both owners' clock floors."""
        from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
        from adapters.native_clock_source_history import restore
        from ios.adapters.graphics_history import follow_native
        from adapters.script_feature.history import same
        from adapters.native_feature_observation import need
        source=self._sources(owner.selector)
        child=IOSSnapshotCaptureOwner(self,owner.selector,owner.run,owner.lock,source,phase=owner.phase,
            epoch_ms=owner.epoch_ms,monotonic=owner.monotonic,sleep=owner.sleep,combined=owner.combined_profile())
        page=owner.tail();capture=child.state['nativeTail']
        if capture is None:
            if page is not None:restore(source['clock_source'],page)
        elif page is not None:
            if page['sequence']>capture['sequence']:
                follow_native(capture,page)
                # The constructor already restored capture; use a pristine
                # independently constructed reader rather than reset it.
                fresh=self._sources(owner.selector);need(same(fresh['binding'],source['binding']))
                restore(fresh['clock_source'],page);child.sources=fresh
            elif page['sequence']<capture['sequence']:follow_native(page,capture)
            else:need(same(page,capture))
        return child
