"""Explicit Audio page/recording owner on an existing installed iOS candidate.

Version four joins the original background child and normal page owner. This remains partial, with
no configuration admission, public feature dispatch or capability activation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_session_owners import register_scope
from ios.adapters.normal_audio import IOSAudioIO
from ios.adapters.script_runtime import IOSScriptRuntime
import time


class IOSAudioRuntime(IOSScriptRuntime):
    def resume_recording(self,selector,owner,ticket,client,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(owner,IOSAudioRecordedOwner) and owner.store.path==self.state_path(selector).with_name('ios-audio-recorded-owner.json')
            and owner.version>=4)
        owner.lock.assert_held()
        if owner.state['background'] is not None:
            from adapters.script_feature.history import unpack
            need(unpack(owner.state['background']['proof']['child']['payload'])[0]['ticket']==ticket)
            return owner.adopt_background()
        child=self.background_owner(selector,owner.run,owner.lock,client,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
        child.act(ticket);return owner.adopt_background(child)

    def background_owner(self,selector,run,lock,client,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        """Reconstruct only the original OS scope until foreground is observed."""
        from ios.adapters.audio_background import AudioBackground
        from ios.adapters.audio_background_sources import AudioBackgroundSources
        from ios.adapters.lifecycle_background import LifecycleOSContext
        root=self.state_path(selector).parent
        need(isinstance(lock,ScriptSourceLock) and lock.path==root/'script-feature-sources.lock');lock.assert_held()
        parent_store=PrivateFeatureState(root/'ios-audio-recorded-owner.json');saved=parent_store.read()
        need(type(saved) is dict and saved.get('runId')==run);binding=context(saved['binding'])
        os=LifecycleOSContext(self,selector,binding)
        register_scope(self.adapter,selector,binding,run,saved['artifactRoot'])
        def sources(intent,previous):
            lock.assert_held();os.probe(True);source=self._sources(selector)
            need(source['binding']==binding)
            return AudioBackgroundSources(source,run,client,intent,previous,epoch_ms=epoch_ms,monotonic=monotonic)
        return AudioBackground(PrivateFeatureState(root/'ios-audio-background.json'),parent_store,os,run,lock,sources,
            epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)

    @contextmanager
    def recorded_owner(self,selector,run,root,client):
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        failure=None
        with lock.held():
            try:
                source=self._sources(selector);native=source['clock_source'];normal=source['native']
                register_scope(self.adapter,selector,source['binding'],run,root)
                io=IOSAudioIO(SimpleNamespace(capture=normal.capture,native=normal,ui=NativeUI(source['client'],source['session'],source['check'])))
                owner=IOSAudioRecordedOwner(PrivateFeatureState(self.state_path(selector).with_name('ios-audio-recorded-owner.json')),
                    root,source['binding'],run,lock,source['check'],native=native,io=io,
                    phase=PhaseFixtureReader(client,run,'audio'),epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep)
                send=native.send
                def observed(command):owner.query_intent(command);return send(command)
                native.send=observed;normal.observe_intent=owner.query_intent
                with self.existing_input_session(selector):
                    yield owner
                    need(source['check']() is not False)
            except BaseException as original:failure=original
        if failure is not None:raise failure
