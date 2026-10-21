"""Pico catalog entry for shared no-build stereo acquisition counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_stereo_world_render import StereoWorldRenderTests
from self_tests.test_stereo_render_trace import StereoRenderTraceTests
from self_tests.test_stereo_camera_uniforms import StereoCameraUniformTests

if __name__=='__main__':unittest.main()
