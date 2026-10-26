"""Explicit Audio page/recording owner on an existing installed iOS candidate.

Version three can open/restore the page in the same owner. This remains partial, with
no configuration admission, public feature dispatch or capability activation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from types import SimpleNamespace
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.normal_audio import IOSAudioIO
from ios.adapters.script_runtime import IOSScriptRuntime
import time


class IOSAudioRuntime(IOSScriptRuntime):
    @contextmanager
    def recorded_owner(self,selector,run,root,client):
        lock=ScriptSourceLock(self.state_path(selector).with_name('script-feature-sources.lock'))
        failure=None
        with lock.held():
            try:
                source=self._sources(selector);native=source['clock_source'];normal=source['native']
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
