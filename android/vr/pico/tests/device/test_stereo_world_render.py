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
from self_tests.test_stereo_graphics_pixels import StereoGraphicsPixelTests
from self_tests.test_stereo_graphics_evidence import StereoGraphicsEvidenceTests
from self_tests.test_stereo_graphics_surfaces import StereoGraphicsSurfaceTests
from self_tests.test_stereo_graphics_surface_evidence import StereoGraphicsSurfaceEvidenceTests
from self_tests.test_pico_graphics_surface_samples import PicoGraphicsSurfaceSampleTests
from self_tests.test_graphics_surface_cues import GraphicsSurfaceCueTests
from self_tests.test_graphics_surface_resources import GraphicsSurfaceResourceTests
from self_tests.test_graphics_originals import GraphicsOriginalTests
from self_tests.test_pico_graphics_samples import PicoGraphicsSampleTests

if __name__=='__main__':unittest.main()
