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


class IOSGraphicsRuntime(IOSScriptRuntime):
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

    def _graphics_surface(self,selector,run,intent,owns,lease,allow_url):
        source=self._sources(selector)
        original=IOSScriptIO(NativeUI(source['client'],source['session'],source['check']),source['native'])
        reader=IOSGraphicsSource(original,source['native_clock'],source['check'],int(source['binding']['processIdentity']))
        graphics=TokenGraphicsUI(reader,lambda *_:need(False))
        return IOSGraphicsSurface(original,source['observer'].graphics_subject(),graphics,run,intent,owns,lease,allow_url)
