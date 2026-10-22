"""Emote components on the existing candidate-qualified iOS runtime.

These internal factories enable no complete feature triple. The whole owner
must still join original images, replicated peer effects and quiet retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.native_script_roots import NativeScriptRoots,FILE as ROOTS_FILE,LIMIT as ROOTS_LIMIT
from adapters.native_avatar_receive import NativeAvatarReceive,FILE as RECEIVE_FILE,LIMIT as RECEIVE_LIMIT
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.emote_actions import IOSEmoteActions
from ios.adapters.emote_controls import IOSEmoteIO
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.script_runtime import IOSScriptRuntime


class IOSEmoteRuntime(IOSScriptRuntime):
    def _emote_sources(self,selector,client,run,role,root,lock):
        need(isinstance(lock,ScriptSourceLock));lock.assert_held();s=self._sources(selector)
        need(lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        observer=s['observer'];remote=observer.remote.rsplit('/',1)[0]+'/'
        roots=NativeScriptRoots(observer.send,lambda:observer.original(remote=remote+ROOTS_FILE,limit=ROOTS_LIMIT),
            s['native_clock'],s['check'],int(s['binding']['processIdentity']),ios=True)
        readers=dict(roots=roots,scripts=observer.script_execution_observer(),
            native=observer.bound_native_observer(s['clock_source']),ui=IOSEmoteIO(s['native']),world=observer.emote_world(s['clock_source']))
        return IOSEmoteSources(PrivateFeatureState(self.state_path(selector).with_name('ios-emote-'+role+'-sources.json')),
            root,s['binding'],run,role,lock,s['check'],PhaseFixtureReader(client,run,'emotes'),readers=readers)

    def _emote_actions(self,selector,sources):
        need(isinstance(sources,IOSEmoteSources));sources.bound();s=self._sources(selector)
        need(s['binding']==sources.binding)
        return IOSEmoteActions(PrivateFeatureState(self.state_path(selector).with_name('ios-emote-inputs.json')),sources,
            NativeUI(s['client'],s['session'],s['check']))

    def _avatar_receive(self,selector):
        s=self._sources(selector);observer=s['observer'];remote=observer.remote.rsplit('/',1)[0]+'/'+RECEIVE_FILE
        return NativeAvatarReceive(observer.send,lambda:observer.original(remote=remote,limit=RECEIVE_LIMIT),
            s['native_clock'],s['check'],int(s['binding']['processIdentity']),ios=True)
