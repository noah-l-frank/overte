#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile original settings manager, Handle template and Snapshot cleanup body.

Only dependency/bootstrap, GLM declarations and the surrounding GUI owner are
host seams. Setting::Interface member bodies, Manager TU, Handle template and
Snapshot::featureSnapshotSettings body are taken unchanged from this checkout.
"""
import argparse
from pathlib import Path
import shlex
import subprocess
ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir',required=True,type=Path)
args=parser.parse_args();build=args.build_dir.resolve()
if ROOT not in build.parents:parser.error('Build directory must be inside this checkout')
build.mkdir(parents=True,exist_ok=False)
handle=(ROOT/'libraries/shared/src/SettingHandle.h').read_text()
assert handle.count('#include <glm/glm.hpp>')==handle.count('#include <glm/gtc/quaternion.hpp>')==1
handle=handle.replace('#include <glm/glm.hpp>','namespace glm { struct vec3; struct quat; }').replace('#include <glm/gtc/quaternion.hpp>','')
(build/'HostSettingHandle.h').write_text(handle)
source=(ROOT/'libraries/shared/src/SettingInterface.cpp').read_text()
start=source.index('    void Interface::init() {')
(build/'OriginalSettingInterface.inc').write_text('namespace Setting {\n'+source[start:])
source=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
start=source.index('QVariantMap Snapshot::featureSnapshotSettings(')
end=source.index('\nQVariantMap Snapshot::featureSnapshotObservation()',start)
(build/'OriginalSnapshotSettings.inc').write_text(source[start:end])
source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
start=source.index('QVariantMap TestScriptingInterface::phoneSnapshotSettings(')
end=source.index('\nQVariantMap TestScriptingInterface::phoneSnapshotReadback(',start)
(build/'OriginalSnapshotSettingsGateway.inc').write_text(source[start:end])

flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Test','Qt6Quick','Qt6Qml'],text=True))
moc=build/'moc_SettingManager.cpp'
subprocess.run(['/usr/lib64/qt6/libexec/moc','-DOVERTE_E2E_FEATURE_TESTS',str(ROOT/'libraries/shared/src/SettingManager.h'),'-o',str(moc)],check=True,timeout=30)
binary=build/'snapshot-settings-runtime'
subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
    '-I'+str(build),'-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),
    str(ROOT/'android/phone/tests/device/snapshot-settings-runtime.cpp'),str(ROOT/'libraries/shared/src/SettingManager.cpp'),
    str(moc),'-o',str(binary),*flags],check=True,timeout=120)
subprocess.run([str(binary),'--testScript'],check=True,timeout=30)
print('PASS: original settings manager/Handle/Interface/Snapshot cleanup; explicit dependency/GUI seams; devices untested')
