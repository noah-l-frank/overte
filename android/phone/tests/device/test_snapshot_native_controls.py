"""Real Snapshot QML/Qt controls with explicit script/OS producer seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_snapshot_controls import validate


class SnapshotNativeControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-normal-controls-contract';parent.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='qt6-',dir=parent);cls.addClassCleanup(temporary.cleanup)
        cls.stage=Path(temporary.name);production=cls.stage/'system/snapshot';production.mkdir(parents=True)
        for name in ('NativeSnapshotReview.qml','SnapshotPlatform.qml'):
            shutil.copyfile(ROOT/'scripts/system/snapshot'/name,production/name)
        controls=cls.stage/'controls';controls.mkdir()
        shutil.copyfile(ROOT/'interface/resources/qml/controls/+android/SnapshotPlatformBackend.qml',controls/'SnapshotPlatformBackend.qml')
        (controls/'qmldir').write_text('module controls\nSnapshotPlatformBackend 1.0 SnapshotPlatformBackend.qml\n')
        cpp=ROOT/'android/phone/tests/device/snapshot-controls-runtime.cpp'
        subprocess.run(['/usr/lib64/qt6/libexec/moc',str(cpp),'-o',str(cls.stage/'snapshot-controls-runtime.moc')],check=True,timeout=30)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Quick','Qt6Qml','Qt6Gui','Qt6Core','Qt6Test','Qt6Network'],text=True))
        cls.executable=cls.stage/'check'
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
            '-DOVERTE_SOURCE_ROOT="'+str(ROOT)+'"',
            '-I'+str(ROOT),'-I'+str(cls.stage),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(ROOT/'libraries/ui/src'),
            str(cpp),str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(cls.executable),*flags],check=True,timeout=120)

    def run_case(self,mode):
        raw=subprocess.check_output([str(self.executable),str(self.stage),mode,'--testScript'],text=True,timeout=15,
            env=os.environ|{'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software','XDG_CONFIG_HOME':str(self.stage/'config')})
        original=json.loads(raw);original.update(commandId='a'*32,action='observe')
        validate(original,'a'*32,original['processId'],original['capturedEpochMs'])
    def test_actual_name_mode_format_capture_cancel_and_exact_image_export_inputs(self):self.run_case('normal')
    def test_unknown_token_consumes_intent_and_cannot_be_replayed(self):self.run_case('stale')
    def test_foreign_and_duplicate_original_components_never_qualify_controls(self):self.run_case('foreign')
    def test_actual_foreign_overlay_blocks_input(self):self.run_case('obstruction')


if __name__=='__main__':unittest.main()
