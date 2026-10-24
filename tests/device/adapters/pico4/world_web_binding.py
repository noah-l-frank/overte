"""Private World Web composition on original normal Pico and source owners.

No new target input system, Web button, scene or public capability is added.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_script_manager import NormalScriptManager
from adapters.pico4.browser_entry import PicoBrowserScriptIO
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.pico4.normal_scripts import configuration
from adapters.pico4.tablet_home import bind_home
from adapters.pico4.world_browser_ray import PicoWorldRayClick
from adapters.pico4.world_browser_text import PicoWorldTextInput
from adapters.token_script_ui import TokenScriptUI
import os


class PicoWorldWebBinding(PicoScriptJourney):
    state_area='world-web'
    def __init__(self,adapter):
        super().__init__(adapter);self.scene_url=configuration(os.environ);need(self.scene_url is not None)

    def _lock(self,target,source_lock=None):return self.original._script_journey()._lock(target,source_lock)

    def prefix(self,target,source,foreign_fixture_url,*,role='primary',require_new_actor=False):
        from adapters.pico4.world_web_prefix import PicoWorldWebPrefix
        return PicoWorldWebPrefix(self,target,source,foreign_fixture_url,role=role,require_new_actor=require_new_actor)

    def source_return(self,target,parent,process,expected,*,stereo=None):
        from adapters.pico4.world_web_source_pass import WorldSourceReturn
        self.check_identity(target,parent)
        with parent.lock.held():
            parent.read();parent.control()
            need(parent.role=='primary' and parent.state['phase']=='source-stopped'
                and expected['prefixScope']==parent.scope and expected['binding']==parent.state['binding']
                and expected['ownerToken']==parent.state['ownerToken'] and expected['runId']==parent.run
                and expected['fixtureUrl']==parent.url and expected['foreignFixtureUrl']==parent.foreign)
            if 'stereoScope' in expected:
                from adapters.pico4.world_web_stereo_join import WorldStereoJoin,original_join
                from adapters.pico4.browser_actor_graph import original
                need(type(stereo) is WorldStereoJoin and stereo.flow is parent and stereo.flow.role=='primary')
                stereo.control();need(expected['stereoScope']==dict(stereo.scope,role='actor'))
                original_join(stereo.store.read(),stereo.scope,parent.history_reader(),lambda name:original(stereo.artifacts/name))
            else:need(stereo is None)
        return WorldSourceReturn(process,parent.root,parent.lock,expected)

    def check_identity(self,target,parent):
        from adapters.pico4.world_web_prefix import PicoWorldWebPrefix
        need(type(parent) is PicoWorldWebPrefix and parent.adapter is self and parent.target==target)

    def check(self,target,parent,*,input=False):
        from adapters.pico4.world_web_prefix import PicoWorldWebPrefix
        need(type(parent) is PicoWorldWebPrefix and parent.adapter is self and parent.target==target)
        self._lock(target,parent.lock).assert_held();parent.control()
        if input:need(parent.role=='primary' and parent.state is not None and parent.state['phase'] in ('preparing','acting','closing'))

    def world_prefix_capture_guard(self,target,lock):
        # Reuse all existing shared capture stores/guards. No capture is
        # acquired by this prefix; a foreign owner still blocks native reserve.
        from adapters.pico4.tablet_web_binding import PicoTabletWebBinding
        return PicoTabletWebBinding(self.original)._tablet_web_capture_guard(target,lock)

    def world_prefix_io(self,target,parent,*,read_only=True):
        self.check(target,parent,input=not read_only)
        io=self.original._browser_originals(target,source_lock=parent.lock,tablet=False,read_only=read_only)
        if not read_only:io.before_send=parent.input_fence().before_send
        return io

    def world_prefix_manager(self,target,parent):
        self.check(target,parent,input=True)
        normal,observe,binding,_guard,_installed=self.normal_feature_runtime(target,read_only=True)
        need(binding==parent.state['binding']);native=self.original._native_feature_observer(target)
        normal.io.navigation.bind_feature_client_url(parent.state['scriptUrl'])
        io=PicoBrowserScriptIO(normal.io,parent.input_fence(),parent.input_begin,parent.input_done)
        home=bind_home(self.original,target,native)
        class WorldScriptUI(TokenScriptUI):
            def open_manager(inner):
                need(inner.tablet_visible());issued=[]
                def intent(stage,before,control):
                    need(not issued);issued.append(True)
                    parent.input_begin(dict(kind='home-ray',operation=stage,control=control,original=before))
                home.ensure(intent,stream_intent=parent.input_fence().stage_intent,stream_publish=parent.input_fence().before_publish)
                if issued:parent.input_done()
                return super().open_manager()
        ui=WorldScriptUI(io,monotonic=parent.source.monotonic,sleep=native.sleep)
        return NormalScriptManager(ui,observe,self._store(target,'pico-world-web-prefix-manager.json'),binding,
            source_kind='feature-world-web',monotonic=parent.source.monotonic,sleep=native.sleep)

    def world_prefix_vm(self,target,parent):
        self.check(target,parent)
        return self.original._world_browser_vm(target,parent.run,parent.url,parent.state['scriptUrl'],role=parent.role,
            source_lock=parent.lock,http=lambda:parent.source.client.request('/runs/'+parent.run+'/browser'))

    def world_prefix_stereo(self,target,parent,artifacts,journal):
        from adapters.pico4.browser_stereo import original_name
        self.check(target,parent)
        return self.original._browser_stereo(target,artifacts/original_name(parent.run,parent.role,journal,surface='world'),
            artifacts,parent.run,self.scene_url,role=parent.role,source_lock=parent.lock,journal_id=journal,
            fixture_url=parent.url,foreign_fixture_url=parent.foreign,owner_token=parent.state['ownerToken'],
            script_url=parent.state['scriptUrl'],http=lambda:parent.source.client.request('/runs/'+parent.run+'/browser'),surface='world')

    def world_prefix_runtime(self,target,parent):
        self.check(target,parent);return self.original._web_runtime_observer(target)

    def ray(self,target,parent):
        self.check(target,parent,input=True)
        io=self.original._browser_originals(target,source_lock=parent.lock,tablet=False,read_only=False)
        identity=self.original.require_pico_session_identity(target)
        def stage(pose,*,intent,before_publish):
            need(self.original.require_pico_session_identity(target)==identity)
            # The exact independent phase is last, outside the Session lock;
            # its locked hooks remain pure host original-anchor/CAS checks.
            parent.input_fence().check()
            return self.original.pico_input_session(target).stage(identity,'input.primary',pose,
                intent=intent,before_publish=before_publish)
        return PicoWorldRayClick(io,stage,parent.input_begin,parent.input_fence().stage_intent,parent.input_fence().before_publish)

    def world_prefix_click(self,target,parent,view,control):
        click=self.ray(target,parent)
        value=click.click(parent.run,parent.url,parent.state['ownerToken'],view,control)
        parent.input_result(value);parent.input_done();return value

    def world_prefix_current_source(self,target,parent):
        self.check_identity(target,parent);need(parent.lock._owner is None)
        return self.original._world_current_input_originals(target,source_lock=parent.lock)

    def world_prefix_current_ray(self,target,parent,source,intent,*,stream_intent,before_publish,admission):
        self.check_identity(target,parent);need(parent.lock._owner is None)
        return self.original._world_current_ray(target,source=source,intent=intent,
            stream_intent=stream_intent,before_publish=before_publish,admission=admission)

    def world_prefix_text(self,target,parent,view,text,*,control='text'):
        click=self.ray(target,parent)
        def commit(original):
            # The ray's ordinary delivery plus independently measured focus
            # have completed. IME gets its own original command and phase CAS.
            parent.input_done();parent.input_begin(original)
        owner=PicoWorldTextInput(click,commit)
        value=owner.replace(parent.run,parent.url,parent.state['ownerToken'],view,text,control=control)
        parent.input_result(value);parent.input_done();return value
