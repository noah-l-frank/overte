"""Private Pico browser composition on existing original sources and normal VR inputs.

No public capability is advertised by these factories. Whole source/actor and
final cleanup qualification belongs to the enclosing feature coordinator.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_script_manager import NormalScriptManager
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.pico4.normal_scripts import configuration
from adapters.pico4.browser_entry import PicoBrowserScriptIO,PicoBrowserEntry
from adapters.pico4.tablet_browser_source import PicoTabletBrowserIO
from adapters.pico4.tablet_home import bind_home
from adapters.token_script_ui import TokenScriptUI
import os

VERSION=1


def retained(adapter,target):
    """Inspect the entire original namespace without configuration or adoption.

    Partial reservations and orphan immutable chunks remain ownership even
    without a readable parent. Generic application stop cannot retire them.
    """
    journey=PicoScriptJourney(adapter);journey.state_area='tablet-web'
    path=journey.existing_state_path(target)
    return path is not None and any(path.parent.iterdir())


class PicoTabletWebBinding(PicoScriptJourney):
    state_area='tablet-web'
    def __init__(self,adapter):
        super().__init__(adapter);self.scene_url=configuration(os.environ);need(self.scene_url is not None)

    def _lock(self,target,source_lock=None):
        # Sources share the original canonical Script lock. Browser files have
        # their own target-specific namespace and cannot adopt Script ownership.
        return self.original._script_journey()._lock(target,source_lock)

    def feature(self,target,source,artifact_root,foreign_fixture_url,*,role='primary'):
        from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
        return PicoTabletWebFeature(self,target,source,artifact_root,foreign_fixture_url,role=role,
            monotonic=source.monotonic)

    def check_flow(self,target,flow,*,input=False):
        from adapters.pico4.tablet_web_feature import PicoTabletWebFeature
        need(isinstance(flow,PicoTabletWebFeature) and flow.adapter is self and flow.selector==target)
        self._lock(target,flow.lock).assert_held()
        if input:need(flow.role=='primary' and flow.live_owner is not None)
        return flow

    def tablet_web_manager_store(self,target):return self._store(target,'pico-tablet-web-manager.json')

    def _normal(self,target,flow):
        self.check_flow(target,flow,input=True)
        ui,observe,binding,_guard,_installed=self.normal_feature_runtime(target,read_only=True)
        need(binding==flow.live_owner['binding']);native=self.original._native_feature_observer(target)
        io=PicoBrowserScriptIO(ui.io,flow.input_fence(),flow.input_begin,flow.input_done)
        return TokenScriptUI(io,monotonic=flow.source.monotonic,sleep=native.sleep),observe,binding

    def _tablet_web_manager(self,target,flow):
        ui,observe,binding=self._normal(target,flow)
        return NormalScriptManager(ui,observe,self.tablet_web_manager_store(target),binding,source_kind='feature-tablet-web',
            monotonic=flow.source.monotonic,sleep=ui.sleep)

    def _tablet_web_entry(self,target,flow,identifier,*,initial):
        self._entry(target,flow).open(identifier,initial=initial)

    def _tablet_web_close(self,target,flow):self._entry(target,flow).close()

    def _entry(self,target,flow):
        normal,_observe,_binding=self._normal(target,flow)
        apps=self.original._browser_app_controls(target,source_lock=flow.lock,read_only=False)
        home=bind_home(self.original,target,self.original._native_feature_observer(target))
        return PicoBrowserEntry(normal,apps,home,flow.input_fence(),flow.input_begin,flow.input_done,
            flow.tablet_owned,flow.tablet_lease)

    def _tablet_web_io(self,target,flow,*,read_only=True):
        self.check_flow(target,flow,input=not read_only)
        original=self.original._browser_originals(target,source_lock=flow.lock,tablet=True,read_only=read_only)
        class OwnedIO(PicoTabletBrowserIO):
            def request(inner,run,url,owner,operation,**fields):
                packet=super().request(run,url,owner,operation,**fields)
                if operation not in ('observe','measure'):flow.input_done()
                return packet
        io=OwnedIO(original.send,original.original,original.clock_ms,original.guard,original.pid,
            source_lock=flow.lock,read_only=read_only,monotonic=original.monotonic,sleep=original.sleep)
        if not read_only:io.before_send=flow.input_fence().before_send
        return io

    def _web_runtime_observer(self,target,*,read_only=True):
        need(read_only is True);self._guard(target)
        source=self.original._web_runtime_observer(target);need(source.require_renderers is True);return source

    def _world_web_clock(self,target):return self.original._native_feature_observer(target).clock_ms()

    def _graphics_lifecycle_status(self,target,binding):
        from adapters.pico4.graphics_binding import PicoGraphicsBinding
        return PicoGraphicsBinding(self.original)._graphics_lifecycle_status(target,binding)

    def _tablet_web_lifecycle(self,target,flow,operation):
        from adapters.pico4.graphics_binding import PicoGraphicsBinding
        self.check_flow(target,flow,input=True)
        facade=PicoGraphicsBinding(self.original);facade.phase_fence=flow.input_fence()
        return facade._graphics_lifecycle_input(target,operation,flow.live_owner['binding'])

    def _tablet_web_stereo(self,target,flow,journal,role):
        from adapters.pico4.browser_stereo import original_name
        self.check_flow(target,flow);need(role==flow.role and flow.live_owner is not None)
        owner=flow.live_owner
        return self.original._browser_stereo(target,flow.artifact_root/original_name(flow.run,role,journal),flow.artifact_root,
            flow.run,self.scene_url,role=role,source_lock=flow.lock,journal_id=journal,fixture_url=flow.fixture_url,
            foreign_fixture_url=flow.foreign_url,owner_token=owner['ownerToken'],script_url=owner['scriptUrl'],
            http=lambda:flow.source.client.request('/runs/'+flow.run+'/browser'))

    def _tablet_web_vm(self,target,flow):
        from adapters.pico4.browser_vm import PicoBrowserVm
        self.check_flow(target,flow);owner=flow.live_owner
        need(owner is not None and owner['scriptUrl'] is not None)
        return PicoBrowserVm(flow.run,flow.fixture_url,owner['scriptUrl'],flow.role,owner['binding'],
            self.original._script_execution_observer(target,read_only=True),
            self.original._script_object_lifetimes(target,source_lock=flow.lock),
            self._store(target,'pico-tablet-web-'+flow.role+'-vm.json'),flow.lock,
            lambda:flow.source.client.request('/runs/'+flow.run+'/browser'))

    def _tablet_web_retired_capture_observer(self,target,proof,lock,*,previous=None):
        from adapters.retired_world_capture import observer
        from adapters.world_render_receipts import INVENTORY_FILE
        from adapters.pico4.graphics_binding import PicoGraphicsBinding
        self._lock(target,lock).assert_held()
        _ui,_source,binding,guard,_installed=self.normal_feature_runtime(target,read_only=True)
        native=self._native_feature_observer(target,read_only=True)
        graphics=PicoGraphicsBinding(self.original)
        stores=[self.original._world_render_store(target)]
        for role in ('primary','actor'):
            stores.extend((self.original._browser_world_render_store(target,role),
                self.original._emote_world_render_store(target,role),graphics.world_render_store(target,role=role)))
        return observer(proof,lock,binding,native,guard,stores,
            lambda:self.original.adb.read_debug_app_file(target,'org.overte.pico','files/overte-e2e/'+INVENTORY_FILE,attempts=1),
            previous=previous)
