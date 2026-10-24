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
    def __init__(self,f):super().__init__(f,SimpleNamespace(root=f.root,native_root=f.root))
    def configuration(self):
        f=self.f
        return dict(port=self.server.server_address[1],token=self.token,path=str(f.root),modelRoot=str(f.root),
            artifacts=str(f.root),nativeRoot=str(f.root),binding=deepcopy(f.target.binding),run=f.run,
            fixture=f.fixture_url,foreign=f.foreign,scene=f.target.scene_url,selector=f.target.selector)
    def dispatch(self,action,value):
        target=self.f.target;self.calls.append(action)
        if action=='diagnostic':return target.diagnostic(value)
        if action=='feature':target.native.send(value);return target.native.original()
        if action=='browser':
            need(value['operation']=='observe');target.send(value);return target.raw
        if action=='runtime':
            reader=target._web_runtime_observer(target.selector,read_only=True);reader.send(value);return target.runtime_raw
        if action in ('scripts','objects'):
            b=target.vm_boundary
            if action=='scripts':b.script.send(value);return b.script.original()
            b.objects.send(value);return json.dumps(b.objects.packet)
        # The common source endpoint has no ordinary input action. The World
        # override above likewise permits only independent original reads.
        self.calls.pop();return super().dispatch(action,value)


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
