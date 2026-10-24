"""Existing two-eye analytical render boundary on consumed World HTTP bytes.

Native/Qt/HMD/GPU remain explicit fixture seams. The original Pico stereo
factory, capture/storage/receipt owners and actual PNG/metadata files execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.pico4.browser_stereo import original_name
from self_tests.pico_browser_render_fixture import RenderModel


class WorldRenderModel(RenderModel):
    def __init__(self,target,artifacts):
        super().__init__(target,artifacts);self.temporary._finalizer.detach();self.root.chmod(0o700)
        self.ui.shown=target.qt.opened
        ui_write=self.ui.write
        def current_ui(*args,**kwargs):
            self.ui.shown=target.qt.opened;return ui_write(*args,**kwargs)
        self.ui.write=current_ui
        self.subject.edit=lambda packet:packet.update(instance=target.instance)
        mutate=self.features.mutate
        def feature(packet):mutate(packet);packet.update(instance=target.instance)
        self.features.mutate=feature
        target._native_feature_observer=lambda selected:self._native_feature_observer(selected,read_only=True)
        # A normal World source factory does not require a live Script UI.
        # Its diagnostic is the actual independently queried normal service.
    def bind_factory(self,adapter):
        target=self.target
        adapter._script_runtime=lambda selected:(None,target.diagnostic,target.binding)
        adapter._native_feature_observer=lambda selected:self._native_feature_observer(selected,read_only=True)
        adapter._graphics_subject_observer=lambda selected:self.subject_reader()
        adapter.read_probe_snapshot=lambda selected,package,after:self.probe(after)
        adapter._script_journey=lambda:target._script_journey()
        adapter._browser_world_render_capture=lambda selected,role,source_lock:self._world_render_capture(selected,
            read_only=True,role=role,require_frame_view=True,source_lock=source_lock)
        adapter._browser_originals=lambda selected,**kwargs:target._browser_originals(target.selector,**kwargs)
        adapter._web_runtime_observer=lambda selected:target._web_runtime_observer(target.selector,read_only=True)
        def ui(selected):
            value=self.ui.source();value.clock_ms=target.clock.epoch;value.monotonic=target.clock.now;value.sleep=target.clock.sleep;return value
        adapter._graphics_ui_observer=ui
        def stereo(selected,path,artifacts,run,scene,**kwargs):
            self.active=kwargs.pop('active_ticket') if 'active_ticket' in kwargs else target.client.request('/runs/'+run+'/active')['ticket']
            return adapter._browser_stereo(selected,path,artifacts,run,scene,**kwargs)
        target._browser_stereo=stereo
    def retained(self):
        # All actual capture-memory/file receipt transitions run normally. Only
        # synthetic source/PNG directories stay for failure/source provenance.
        return self.root
