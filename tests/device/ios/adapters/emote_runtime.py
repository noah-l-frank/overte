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
from ios.adapters import emote_operation


class IOSEmoteRuntime(IOSScriptRuntime):
    def operation_guard(self,guard):return emote_operation.scope(self,guard)

    def _sources(self,selector):
        emote_operation.check(self);source=super()._sources(selector);emote_operation.check(self)
        if not emote_operation.active(self):return source
        source['client']=emote_operation.Client(self,source['client'])
        source['check']=emote_operation.guarded(self,source['check'])
        source['process']=emote_operation.guarded(self,source['process'])
        clock_owner=getattr(source['clock_source'].guard,'__self__',None)
        seen=set()
        for boundary in (source['native'],source['observer'],clock_owner):
            if boundary is None or id(boundary) in seen:continue
            seen.add(id(boundary));boundary.client=source['client']
            boundary.observe_process=emote_operation.guarded(self,boundary.observe_process)
            if boundary is not source['native']:boundary.before_send=lambda:emote_operation.check(self)
        original=source['native']._request
        def request(operation,native=None,*,before_send=None):
            def final():
                emote_operation.check(self)
                if before_send is not None and before_send() is False:return False
                emote_operation.check(self)
            return original(operation,native,before_send=final)
        source['native']._request=request;return source

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
            NativeUI(s['client'],s['session'],sources.bound))

    def _avatar_receive(self,selector):
        s=self._sources(selector);observer=s['observer'];remote=observer.remote.rsplit('/',1)[0]+'/'+RECEIVE_FILE
        return NativeAvatarReceive(observer.send,lambda:observer.original(remote=remote,limit=RECEIVE_LIMIT),
            s['native_clock'],s['check'],int(s['binding']['processIdentity']),ios=True)
