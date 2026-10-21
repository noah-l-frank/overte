"""Internal Pico Graphics owner namespaces; no complete feature operation yet."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.owned_world_render import OwnedWorldRenderCapture
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1


class PicoGraphicsBinding(PicoScriptJourney):
    state_area='graphics'

    def __init__(self,adapter,*,fixture_profile=None):
        from feature_journeys.graphics_fixture import LEGACY_PROFILE
        from feature_journeys.graphics_resources import profile_name
        self.fixture_profile=profile_name(LEGACY_PROFILE if fixture_profile is None else fixture_profile)
        super().__init__(adapter)

    @property
    def graphics_scene_policy(self):
        from adapters.pico4.graphics_scene import PicoGraphicsScenePolicy,PicoGraphicsSurfaceScenePolicy
        from feature_journeys.graphics_fixture import PICO_PROFILE
        return (PicoGraphicsSurfaceScenePolicy if self.fixture_profile==PICO_PROFILE else PicoGraphicsScenePolicy)()

    def _graphics_subject_observer(self,target,*,read_only=False):
        need(type(read_only) is bool);self._guard(target)
        return self.original._graphics_subject_observer(target)

    def _scene_load_observer(self,target,*,read_only=False):
        need(type(read_only) is bool);self._guard(target)
        return self.original._scene_load_observer(target)

    def _graphics_ui_observer(self,target,*,read_only=False):
        need(type(read_only) is bool);self._guard(target)
        return self.original._graphics_ui_observer(target)

    def _script_file_io(self,target,*,read_only=False):
        need(type(read_only) is bool)
        return super()._script_file_io(target)

    def _graphics_surface(self,target,run,intent,owns,lease,allow_url,*,lock):
        self._lock(target,lock).assert_held();self._guard(target)
        return self.original._graphics_surface(target,run,intent,owns,lease,allow_url)

    def world_render_store(self,target,*,role):
        need(type(role) is str and role in ('primary','actor'))
        return self._store(target,'graphics-'+role+'-world-render-owner.json')

    def _world_render_capture(self,target,*,read_only=True,role,require_frame_view=True,source_lock):
        need(read_only is True and require_frame_view is True)
        return self.original._world_render_capture(target,read_only=True,role=role,require_frame_view=True,source_lock=source_lock)


class SerializedWorldCapture(OwnedWorldRenderCapture):
    """Use the same explicit source-lock instance across role/native channels."""
    def __init__(self,*args,source_lock,**options):
        need(isinstance(source_lock,ScriptSourceLock));self.source_lock=source_lock
        super().__init__(*args,**options)

    def read(self,after_sequence):
        with self.source_lock.held():return super().read(after_sequence)

    def release(self):
        with self.source_lock.held():return super().release()
