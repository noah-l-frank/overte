"""Pico no-build original Graphics source and lifetime counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_native_graphics_subject import GraphicsSubjectTests
from self_tests.test_native_scene_loads import SceneLoadTests
from self_tests.test_native_tablet_http import TabletHttpTests
from self_tests.test_native_web_runtime import WebRuntimeTests
from self_tests.test_native_web_renderers import WebRendererTests
from self_tests.test_pico_graphics_source import PicoGraphicsSourceTests

if __name__=='__main__':unittest.main()
