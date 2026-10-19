#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Exercise the production Phone graphics controller and Qt 5 touch page."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
subprocess.run(["node", str(ROOT / "android/phone/tests/phone-graphics-controller-test.js")], check=True)
runner = shutil.which("qmltestrunner")
if not runner:
    raise SystemExit("Qt 5 qmltestrunner is required for Phone graphics touch validation")
with tempfile.TemporaryDirectory(prefix="phone-graphics-qml-") as temporary:
    stage = Path(temporary)
    controls = stage / "controlsUit"
    controls.mkdir()
    for filename in ("TouchUiMetrics.qml", "TouchUiProfile.qml", "TouchUiProfileBase.qml"):
        shutil.copyfile(ROOT / "interface/resources/qml/controlsUit" / filename, controls / filename)
    (controls / "qmldir").write_text("module controlsUit\nTouchUiMetrics 1.0 TouchUiMetrics.qml\n"
        "TouchUiProfile 1.0 TouchUiProfile.qml\nTouchUiProfileBase 1.0 TouchUiProfileBase.qml\n")
    source = (ROOT / "android/phone/tests/qml/graphics/tst_phonegraphics.qml").read_text()
    page = (ROOT / "scripts/system/settings/qml/pages/+android_phoneInterface/GraphicsSettings.qml").as_uri()
    source = source.replace('property var page\n', 'property var page\n    property string pageSource: "' + page + '"\n')
    source = source.replace('property var page\n', 'property var page\n'
        '    property string phoneProfileSource: "' + (ROOT / "interface/resources/qml/controlsUit/+android_phoneInterface/TouchUiProfile.qml").as_uri() + '"\n'
        '    property string settingsConfigurationSource: "' + (ROOT / "scripts/system/settings/qml/SettingsTouchConfiguration.qml").as_uri() + '"\n')
    (stage / "tst_phonegraphics.qml").write_text(source)
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
    result = subprocess.run([runner, "-input", str(stage), "-import", str(stage)],
        env=environment, capture_output=True, text=True, timeout=30)
    print(result.stdout, end="")
    print(result.stderr, end="")
    result.check_returncode()
    if re.search(r"TypeError:|ReferenceError:|Binding loop|Cannot assign", result.stdout + result.stderr):
        raise RuntimeError("Production Phone graphics QML emitted an execution error")
