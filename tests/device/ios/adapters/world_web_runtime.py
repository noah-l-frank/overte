"""World Web factories on existing guarded physical sessions; no capability."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.world_web_api_clock import check,guarded
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_sources import WorldWebSources


class IOSWorldWebRuntime(IOSGraphicsRuntime):
    def _sources(self,selector):
        check();sources=super()._sources(selector);check()
        sources['check']=guarded(sources['check']);sources['process']=guarded(sources['process'])
        for name in ('observer','clock_source'):
            original=sources[name];original.observe_process=guarded(original.observe_process);original.before_send=check
        sources['native'].observe_process=guarded(sources['native'].observe_process)
        return sources

    def _world_web_store(self,selector,name):
        need(type(name) is str and name.startswith('ios-world-web-') and name.endswith('.json') and '/' not in name)
        return PrivateFeatureState(self.state_path(selector).with_name(name))

    def _world_web_readers(self,selector,lock):
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
        lock.assert_held();sources=self._sources(selector);observer,clock=sources['observer'],sources['clock_source']
        from ios.adapters.web_closures import IOSWebClosures,FILE as CLOSURES_FILE,LIMIT as CLOSURES_LIMIT
        remote=observer.remote.rsplit('/',1)[0]+'/'+CLOSURES_FILE
        native_closures=IOSWebClosures(observer.send,lambda:observer.original(remote=remote,limit=CLOSURES_LIMIT),
            lambda:clock.read(clock.sequence)['capturedEpochMs'],observer.guard,clock.pid,monotonic=observer.monotonic,sleep=observer.sleep)
        return dict(sources,readers=dict(native=clock,ledger=observer.world_web(clock),document=observer.world_web_dom(clock),
            work=observer.world_web_work(clock),world=observer.emote_world(clock),geometry=observer.world_web_geometry(clock),
            uikit=observer.geometry(),widgets=sources['native'],keys=observer.world_web_keys(clock),pointer=observer.pointer_state(clock),
            entities=observer.create_entities(clock),snapshot=observer.world_web_whole_snapshot(clock),surfaces=observer.world_web_surfaces(clock),closures=native_closures))

    def _world_web_source_owner(self,selector,run,role,phase,lock):
        sources=self._world_web_readers(selector,lock)
        return WorldWebSources(self._world_web_store(selector,'ios-world-web-'+role+'-sources.json'),lock,sources['binding'],run,role,sources['check'],
            phase=phase,readers=sources['readers'])

    def _world_web_marker(self,selector,root,run,role,fixture_url,ticket,lock):
        return IOSWorldWebScope(self,selector,root,run,role,fixture_url,ticket,lock)

    def _world_web_feature(self,selector,run,*,role,client,settings):
        from ios.adapters.world_web_feature import IOSWorldWebFeature
        return IOSWorldWebFeature(self,selector,client,run,role,settings)

    def _world_web_final_stop(self,selector,owner,lock):
        """Canonical Stop only for this exact durably issued World owner."""
        from ios.adapters.world_web_process_end import WorldWebProcessEnd
        from adapters.script_feature.history import same
        need(isinstance(owner,WorldWebProcessEnd) and owner.flow.runtime is self and owner.flow.selector==selector
            and owner.lock is lock and owner.store.path==self.state_path(selector).with_name(
                'ios-world-web-'+owner.role+'-'+owner.run+'-process-final.json'))
        owner.bound();need(owner.state['phase']=='stop-issued' and owner.state['fence'] is not None)
        need(same(self._graphics_final_source(selector,owner.binding),owner.state['source']))
        base=self.adapter;outer=base._operation
        need(outer in (None,'feature.world-web.terminal'))
        base._operation=None
        try:return base.invoke(selector,'app.stop',{})
        finally:base._operation=outer
