"""iOS Graphics source factories over the canonical existing candidate session.

Whole-journey ownership is composed here as it is implemented. These factories
do not create a session, install a target or advertise a feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUI
from adapters.normal_feature_state import PrivateFeatureState
from adapters.completed_frame_lease import CompletedFrameLease
from adapters.token_graphics_ui import TokenGraphicsUI
from ios.adapters.normal_scripts import IOSScriptIO
from ios.adapters.graphics_source import IOSGraphicsSource
from ios.adapters.graphics_surface import IOSGraphicsSurface
from ios.adapters.script_runtime import IOSScriptRuntime
from adapters.script_feature.history import unpack,same
from adapters.normal_feature_state import context


class IOSGraphicsRuntime(IOSScriptRuntime):
    def _graphics_restart(self,selector,client,run,lock,artifact_root,image_policy):
        from ios.adapters.graphics_restart import IOSGraphicsRestart
        return IOSGraphicsRestart(self,selector,client,run,lock,artifact_root,image_policy)

    def graphics_restart_inputs_store(self,selector):
        return PrivateFeatureState(self.state_path(selector).with_name('ios-graphics-restart-inputs.json'))

    def _graphics_restart_inputs(self,selector):
        from adapters.restart_inputs import RestartInputs
        return RestartInputs(self.graphics_restart_inputs_store(selector),self.graphics_restart_owners(selector))

    def _graphics_restart_input(self,selector,operation):
        from ios.adapters.graphics_restart import VERSION
        from feature_journeys.contract import arguments
        need(operation in ('app.stop','app.launch'))
        value=PrivateFeatureState(self.state_path(selector).with_name('ios-graphics-restart.json')).read()
        need(type(value) is dict and type(value.get('iosGraphicsRestartVersion')) is int and value['iosGraphicsRestartVersion']==VERSION)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];call=arguments('feature.graphics.act',state['arguments'])
        need(call['verb']=='restart-app' and call['runId']==value['runId'] and call['fixtureUrl']==value['fixtureUrl']+'/runs/'+value['runId']+'/'
             and state['phase']=='prepared')
        plan=self._graphics_restart_inputs(selector).read()
        need(plan['phase']==('stop-issued' if operation=='app.stop' else 'launch-issued')
             and same(plan['oldBinding'],unpack(state['oldScene']['payload'])[0]['binding']))
        base=self.adapter;outer=base._operation;need(outer in (None,'feature.graphics.act'))
        base._operation=None
        try:return base.invoke(selector,operation,{})
        finally:base._operation=outer

    def _graphics_recover_launch(self,selector,inputs):
        from adapters.restart_inputs import RestartInputs
        need(isinstance(inputs,RestartInputs) and not inputs.component_only
             and inputs.owner_files==self._graphics_restart_inputs(selector).owner_files)
        owned=self.adapter._binding_store(selector).read()
        if owned is not None and owned['phase']=='preparing':
            need(inputs.read()['phase']=='launch-issued')
            self.adapter._recover_script_restart_launch(selector,inputs=inputs)

    def _graphics_restart_stopped(self,selector,old_binding):
        inputs=self._graphics_restart_inputs(selector);need(same(inputs.read()['oldBinding'],old_binding))
        base=self.adapter;base._candidate_guard(complete=True)
        client,state,target=base._script_restart_session(selector,inputs=inputs)
        gate=base._binding(selector,client,state['sessionId'],state,target);record=gate.record()
        if record is not None and record['phase']=='retiring':gate.finish_retirement()
        gate.retired_absence();base.reset_launch_state(selector,state)
        return dict(running=False,identity=None)

    def _graphics_background(self,selector,client,run,lock):
        from ios.adapters.graphics_lifecycle import IOSGraphicsBackground
        return IOSGraphicsBackground.recover(self,selector,client,run,lock)

    def _graphics_lifecycle_status(self,selector,binding):
        context(binding);source=self._existing(selector);client,session,state,target,scope=source
        gate=self.adapter._binding(selector,client,session,state,target)
        before=gate.continuity(allow_background=True)
        need(same(dict(scope,processIdentity=str(before['pid'])),binding))
        app_state=self.adapter.query_app_state(client,session,target)
        after=gate.continuity(allow_background=True)
        need(type(app_state) is int and app_state in (2,3,4) and same(before,after)
             and after['foreground']==(app_state==4) and self.adapter._scope(selector,session,state,target)==scope)
        return dict(binding=dict(scope,processIdentity=str(after['pid'])),foreground=after['foreground'],running=True,appState=app_state)

    def invoke(self,selector,operation,values):
        # Full feature owners persist the exact one-send lifecycle phase first.
        # This cannot install/create a session or bypass candidate source checks.
        need(operation in ('lifecycle.background','app.launch') and values=={})
        value=PrivateFeatureState(self.state_path(selector).with_name('ios-graphics-background.json')).read()
        from ios.adapters.graphics_lifecycle import VERSION
        from feature_journeys.contract import arguments
        need(type(value) is dict and type(value.get('iosGraphicsBackgroundVersion')) is int
             and value['iosGraphicsBackgroundVersion']==VERSION)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        call=arguments('feature.graphics.act',state['arguments'])
        need(call['verb']=='background-resume' and call['runId']==value['runId'] and call['fixtureUrl']==value['fixtureUrl']
             and state['phase']==('background-issued' if operation=='lifecycle.background' else 'foreground-issued'))
        packet=self._graphics_lifecycle_status(selector,state['binding'])
        need(packet['foreground']==(operation=='lifecycle.background'))
        base=self.adapter;outer=base._operation;need(outer in (None,'feature.graphics.act'))
        base._operation=None
        try:return base.invoke(selector,operation,{})
        finally:base._operation=outer

    def _graphics_samples(self,selector,client,run,role,stage,lock,artifact_root,image_policy,*,cleanup_only=False):
        from ios.adapters.graphics_samples import IOSGraphicsSamples
        return IOSGraphicsSamples(self,selector,client,run,role,stage,lock,artifact_root,image_policy,cleanup_only=cleanup_only)

    def _native_feature_observer(self,selector,*,read_only=False):
        need(type(read_only) is bool)
        source=self._sources(selector)
        return source['observer'].bound_native_observer(source['clock_source'])

    def graphics_samples_store(self,selector,role,stage):
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1))
        return PrivateFeatureState(self.state_path(selector).with_name('ios-graphics-'+role+'-'+str(stage)+'-samples.json'))

    def graphics_restart_owners(self,selector):
        return [PrivateFeatureState(self.state_path(selector).with_name('ios-graphics-scene.json'))]+[
            self.graphics_samples_store(selector,role,0) for role in ('primary','actor')]

    def _vulkan_world_frame_owner(self,selector,run,role,stage,request_id,root,*,source_lock=None):
        from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
        from adapters.native_completed_frame import nonce
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1) and nonce(request_id))
        source=self._sources(selector)
        store=PrivateFeatureState(self.state_path(selector).with_name('graphics-world-frame-'+role+'-'+str(stage)+'-'+request_id[4:]+'.json'))
        return VulkanWorldFrameOwner(store,root,source['binding'],run,role,stage,request_id,
            lambda intent,receipt:self._vulkan_world_frame_reader(selector,intent,receipt),source['check'],source_lock=source_lock)

    def _graphics_geometry(self,selector):
        return self._sources(selector)['observer'].geometry()

    def _graphics_images(self,selector,run,role,stage,root,*,source_lock=None):
        from ios.adapters.graphics_images import IOSGraphicsImages
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1))
        source=self._sources(selector)
        store=PrivateFeatureState(self.state_path(selector).with_name('graphics-screen-images-'+role+'-'+str(stage)+'.json'))
        return IOSGraphicsImages(store,root,source['binding'],run,role,stage,source['client'],source['native_clock'],
            source['check'],source_lock=source_lock)

    def _completed_frame_lease(self,selector,run,role,stage,*,source_lock=None):
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1))
        source=self._sources(selector)
        store=PrivateFeatureState(self.state_path(selector).with_name('graphics-frame-lease-'+role+'-'+str(stage)+'.json'))
        return CompletedFrameLease(store,source['binding'],run,role,
            lambda intent:self._completed_frame_reader(selector,intent),source['check'],source_lock=source_lock)

    def _completed_frame_reader(self,selector,intent):
        need(callable(intent))
        return self._sources(selector)['observer'].completed_frame(intent)

    def _vulkan_world_frame_reader(self,selector,intent,receipt=None):
        need(callable(intent))
        return self._sources(selector)['observer'].vulkan_world_frame(intent,receipt)

    def _scene_load_observer(self,selector,*,read_only=True):
        need(read_only is True)
        return self._sources(selector)['observer'].scene_loads()

    def _graphics_subject_observer(self,selector,*,read_only=True):
        need(read_only is True)
        return self._sources(selector)['observer'].graphics_subject()

    def _graphics_ui_source(self,selector,*,read_only=True):
        need(type(read_only) is bool);source=self._sources(selector)
        original=IOSScriptIO(NativeUI(source['client'],source['session'],source['check']),source['native'])
        return IOSGraphicsSource(original,source['native_clock'],source['check'],int(source['binding']['processIdentity']),read_only=read_only)

    def _graphics_controls(self,selector,intent):
        need(callable(intent))
        return TokenGraphicsUI(self._graphics_ui_source(selector,read_only=False),intent)

    def _graphics_surface(self,selector,run,intent,owns,lease,allow_url,*,lock=None):
        if lock is not None:
            from adapters.script_feature.lock import ScriptSourceLock
            need(isinstance(lock,ScriptSourceLock) and lock.path==self.state_path(selector).with_name('script-feature-sources.lock'))
            lock.assert_held()
        source=self._sources(selector)
        original=IOSScriptIO(NativeUI(source['client'],source['session'],source['check']),source['native'])
        reader=IOSGraphicsSource(original,source['native_clock'],source['check'],int(source['binding']['processIdentity']))
        graphics=TokenGraphicsUI(reader,lambda *_:need(False))
        return IOSGraphicsSurface(original,source['observer'].graphics_subject(),graphics,run,intent,owns,lease,allow_url)
