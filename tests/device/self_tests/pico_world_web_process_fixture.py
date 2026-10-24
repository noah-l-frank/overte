"""World analytical producers over the existing owned original-read RPC seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from adapters.native_feature_observation import need
from adapters.native_script_observation import NativeScriptObservation
from adapters.native_script_object_lifetimes import NativeScriptObjectLifetimes
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.browser_vm import PicoBrowserVm
from adapters.pico4.world_browser_ray import PicoWorldBrowserIO
from self_tests.pico_browser_process_fixture import ProductSources,IndependentBrowserSources


class WorldProductSources(ProductSources):
    def __init__(self,f,model=None):super().__init__(f,model or SimpleNamespace(root=f.root,native_root=f.root))
    def configuration(self):
        f=self.f
        return dict(port=self.server.server_address[1],token=self.token,path=str(f.root),modelRoot=str(self.model.root),
            artifacts=str(getattr(f,'artifacts',f.root)),nativeRoot=str(self.model.native_root),binding=deepcopy(f.target.binding),run=f.run,
            fixture=f.fixture_url,foreign=f.foreign,scene=f.target.scene_url,selector=f.target.selector)
    def dispatch(self,action,value):
        try:return self.original_dispatch(action,value)
        except BaseException as error:
            import traceback
            store=PrivateFeatureState(self.f.root/'first-world-source-server-error.json')
            if store.read() is None:store.write(dict(action=action,original=value,traceback=''.join(traceback.format_exception(error))),None)
            raise
    def original_dispatch(self,action,value):
        target=self.f.target;self.calls.append(action)
        if action=='diagnostic':return target.diagnostic(value)
        if action=='feature':
            reader=target._native_feature_observer(target.selector);reader.send(value);return reader.original()
        if action=='browser':
            need(value['operation'] in ('observe','measure-ray'));target.send(value);return target.raw
        if action=='runtime':
            reader=target._web_runtime_observer(target.selector,read_only=True);reader.send(value);return target.runtime_raw
        if action in ('scripts','objects'):
            b=target.vm_boundary
            if action=='scripts':b.script.send(value);return b.script.original()
            b.objects.send(value);return json.dumps(b.objects.packet)
        # The common source endpoint has no ordinary input action. The World
        # override above likewise permits only independent original reads.
        self.calls.pop();result=super().dispatch(action,value)
        if action=='capture' and getattr(self.model,'capture_error',False):raise RuntimeError('lost original applied GPU capture result')
        return result


class IndependentWorldSources(IndependentBrowserSources):
    def __init__(self,config):
        super().__init__(config);self.pico_configuration=('owned-world',self.path);self.selector=config['selector']
        need(self.binding['targetFingerprint']==hashlib.sha256((self.selector+'\0'+str(self.pico_configuration)).encode()).hexdigest())
        self.adb=SimpleNamespace(foreground_package=lambda target:self.foreground(target))
    def guard(self):
        # The original World candidate guard is also valid after the actual
        # source-lock exit. Source acquisition still uses that same lock.
        value=self.rpc.call('candidate');need(value['binding']==self.binding and value['foreground'] is True);return True
    def foreground(self,target):self.require(target);self.guard();return 'org.overte.pico'
    def require(self,target):need(target==self.selector)
    def _installation(self,target):
        self.require(target);self.guard();return dict(schemaVersion=1,installedCandidateVerified=True,
            **{key:self.binding[key] for key in ('sourceRevision','artifactSha256')})
    def require_pico_session_identity(self,target):self.require(target);self.guard();return self.binding['processIdentity']
    require_controlled_debug_identity=require_pico_session_identity
    def _script_runtime(self,target):self.require(target);return None,lambda after:tuple(self.rpc.call('diagnostic',after)),deepcopy(self.binding)
    def _script_journey(self):return SimpleNamespace(_lock=lambda target,provided=None:self.lock)
    def _browser_originals(self,target,*,source_lock,tablet,read_only):
        self.require(target);need(source_lock is self.lock and tablet is False and read_only is True)
        return PicoWorldBrowserIO(*self.channel('browser'),self.clock.epoch,self.guard,self.pid,source_lock=self.lock,read_only=True,
            monotonic=self.clock.now,sleep=self.clock.sleep)
    def _world_browser_vm(self,target,run,url,script_url,*,role,source_lock,http):
        self.require(target);need(role=='actor' and source_lock is self.lock)
        scripts=NativeScriptObservation(*self.channel('scripts'),self.clock.epoch,self.guard,self.pid,monotonic=self.clock.now,sleep=self.clock.sleep)
        objects=NativeScriptObjectLifetimes(*self.channel('objects'),self.clock.epoch,self.guard,self.pid,monotonic=self.clock.now,sleep=self.clock.sleep)
        from adapters.pico4.world_web_binding import PicoWorldWebBinding
        root=PicoWorldWebBinding(self).state_path(target).parent
        return PicoBrowserVm(run,url,script_url,role,self.binding,scripts,objects,PrivateFeatureState(root/'pico-world-web-actor-vm.json'),
            self.lock,http,surface='world')

    def _browser_stereo(self,target,path,artifacts,run,scene,*,role,source_lock,journal_id,fixture_url,foreign_fixture_url,owner_token,script_url,http,surface):
        from adapters.native_graphics_subject import NativeGraphicsSubject
        from adapters.navigation_arrival import NavigationArrival
        from adapters.pico4.browser_stereo import PicoBrowserStereo
        from adapters.pico4.graphics_source import PicoGraphicsSource
        self.require(target);need(role=='actor' and surface=='world' and source_lock is self.lock);self.guard()
        subject=NativeGraphicsSubject(*self.channel('subject'),self.clock.epoch,self.guard,self.pid,require_framework=True,
            monotonic=self.clock.now,sleep=self.clock.sleep)
        arrival=NavigationArrival(lambda after:self.rpc.call('probe',after),subject,self.clock.epoch,self.guard,run,self.binding,scene,monotonic=self.clock.now)
        ui_channel=self.channel('ui')
        def write(_target,_package,_path,raw):ui_channel[0](json.loads(raw))
        adapter=SimpleNamespace(adb=SimpleNamespace(write_debug_app_file=write,read_debug_app_file=lambda *_args,**_kwargs:ui_channel[1]()))
        native=SimpleNamespace(clock_ms=self.clock.epoch,guard=self.guard,pid=self.pid,monotonic=self.clock.now,sleep=self.clock.sleep)
        ui=PicoGraphicsSource(adapter,'synthetic',native)
        return PicoBrowserStereo(arrival,self.world_capture,path,artifacts,run,self.binding,self.lock,self.guard,
            fixture_url=fixture_url,foreign_fixture_url=foreign_fixture_url,owner_token=owner_token,script_url=script_url,
            browser_factory=lambda:self._browser_originals(target,source_lock=self.lock,tablet=False,read_only=True),
            runtime_factory=lambda:self._web_runtime_observer(target),scripts=self._script_runtime(target)[1],http=http,
            role=role,journal_id=journal_id,ui_factory=lambda:ui,native_factory=lambda:self._native_feature_observer(target),monotonic=self.clock.now,surface='world')
