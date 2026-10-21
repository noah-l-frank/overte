"""iOS Graphics source factories over the canonical existing candidate session.

Whole-journey ownership is composed here as it is implemented. These factories
do not create a session, install a target or advertise a feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUI
from adapters.token_graphics_ui import TokenGraphicsUI
from ios.adapters.normal_scripts import IOSScriptIO
from ios.adapters.graphics_source import IOSGraphicsSource
from ios.adapters.script_runtime import IOSScriptRuntime


class IOSGraphicsRuntime(IOSScriptRuntime):
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
