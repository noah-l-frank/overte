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
    def _emote_rooted_stop(self,owner,cut):
        """Own exact Emote Stop authority; no Graphics retirement authorization."""
        from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
        from ios.adapters.emote_rooted_fence_cut import IOSEmoteRootedFenceCut
        from ios.adapters.emote_rooted_fence import current
        from ios.adapters.installed_process_runtime import admitted_source
        from adapters.script_feature.history import same
        from adapters.operation_transport_guard import scope as transport_scope
        need(type(owner) is IOSEmoteRootedProcessEnd and owner.runtime is self
            and type(cut) is IOSEmoteRootedFenceCut and getattr(cut,'end',None) is owner
            and getattr(cut,'expected_issued',None) is not None and type(getattr(cut,'value',None)) is dict
            and type(getattr(cut,'proof',None)) is dict)
        owner.bound();need(owner.state is not None and owner.state['phase']=='stop-issued'
            and owner.state['fence'] is not None and owner.state['pending'] is None)
        need(owner.store.path==self.state_path(owner.flow.selector).with_name(
            'ios-emote-'+owner.role+'-'+owner.run+'-rooted-process-end.json'))
        def guard():
            owner.bound();cut.guard();value=owner.fence_original()
            current(value['acquisitions'],value['nativeClock'],epoch_ms=owner.flow.epoch_ms,monotonic=owner.monotonic)
        guard()
        with transport_scope(guard):
            need(same(admitted_source(self,owner.flow.selector,owner.binding),owner.state['source']))
        base=self.adapter;outer=base._operation
        need(outer in (None,'feature.emotes.terminal'));base._operation=None
        try:
            with transport_scope(guard):
                guard();return base.invoke(owner.flow.selector,'app.stop',{})
        finally:base._operation=outer

    def _emote_rooted_feature(self,selector,run,*,role,client,settings,target_pair=None):
        """Explicit internal v2 owner; legacy configuration keeps its reader."""
        from ios.adapters.emote_configuration import settings as validate_settings
        from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
        need(role in ('primary','actor') and client is not None)
        selected=validate_settings(settings,role=role,target=selector)
        return IOSEmoteRootedFeature(self,selector,client,run,role,selected['artifactRoot'],selected['imagePolicy'],
            primary_selector=selected.get('primaryTarget'),actor_selector=selected.get('actorTarget'),target_pair=target_pair)

    def _emote_callback_terminal(self,primary,actor=None):
        """Explicit internal Callback8 terminal; no configuration selection."""
        from ios.adapters.emote_callback_terminal import IOSEmoteCallbackTerminalFeature,IOSEmoteCallbackTerminal
        need(type(primary) is IOSEmoteCallbackTerminalFeature and primary.runtime is self)
        return IOSEmoteCallbackTerminal(primary,actor)

    def _emote_rooted_terminal(self,primary,actor=None):
        from ios.adapters.emote_terminal import IOSEmoteTerminal
        need(primary.runtime is self)
        return IOSEmoteTerminal(primary,actor)

    def _emote_feature(self,selector,run,*,role,client,settings):
        from ios.adapters.emote_configuration import settings as validate_settings
        from ios.adapters.emote_feature import IOSEmoteFeature
        need(role in ('primary','actor') and client is not None)
        selected=validate_settings(settings,role=role,target=selector)
        return IOSEmoteFeature(self,selector,client,run,role,selected['artifactRoot'],selected['imagePolicy'],
            primary_selector=selected.get('primaryTarget'),actor_selector=selected.get('actorTarget'))

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
