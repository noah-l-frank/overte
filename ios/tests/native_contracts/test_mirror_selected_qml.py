#!/usr/bin/env python3
# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0
"""Qualify normal iOS Settings -> Mirrors with this composed tree's native API.

Production QML, mirror/load methods and JobConfig execute with real Qt/INI.
UIKit metrics, scene/GPU, async settings writer and unrelated APIs are explicit
host boundaries; no SDK/device/world-pixel outcome is inferred.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
if os.environ.get('OVERTE_MIRROR_RENDER_SOURCE_ROOT'):
    raise SystemExit('This iOS qualification requires the composed in-tree renderer source')
os.environ['OVERTE_MIRROR_QML_SELECTORS'] = 'ios,mobile,touch,android_phoneInterface,android_interface,webview'
spec = importlib.util.spec_from_file_location('shared_mirror_controls',
    ROOT / 'tests/device/contracts/graphics/test_mirror_controls.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)


class IOSMirrorControls(shared.MirrorControls):
    def test_real_shared_qml_control_toggles_the_production_native_property(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'prefs.ini'
            result = self.invoke('ios', file, 'qml')
            self.assertEqual(result['selected_qml'], str(ROOT /
                'scripts/system/settings/qml/pages/+ios/GraphicsSettings.qml'))
            self.assertTrue(result['qml_initial'])
            self.assertTrue(result['qml_false'])
            self.assertTrue(result['qml_true'])
            self.assertTrue(result['all_match'])
            self.assertTrue(self.invoke('ios', file, 'load')['value'])


if __name__ == '__main__':
    unittest.main()
