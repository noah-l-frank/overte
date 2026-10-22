#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile original Phone navigation Qt controls in an isolated host build.

Requires preinstalled Qt6 development modules. This is neither an Android build
nor device acceptance. No downloads, installations or device transport run.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir',type=Path)
args=parser.parse_args()
if args.build_dir is None:
    parent=ROOT/'build';parent.mkdir(parents=True,exist_ok=True)
    build=Path(tempfile.mkdtemp(prefix='phone-navigation-native-',dir=parent))/'check'
else:build=args.build_dir.resolve()
if ROOT not in build.parents:parser.error('Build directory must be inside this checkout')
build.mkdir(parents=True,exist_ok=False)
modules=['Qt6Quick','Qt6Qml','Qt6Gui','Qt6Core','Qt6Test','Qt6Network']
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',*modules],text=True))
command=['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
    '-DOVERTE_SOURCE_ROOT="'+str(ROOT)+'"','-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(ROOT/'libraries/ui/src')]
source=ROOT/'android/phone/tests/device/navigation-controls-runtime.cpp'
binary=build/'navigation-controls-runtime'
subprocess.run([*command,str(source),str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(binary),*flags],check=True,timeout=120)
# Compile the passive model/settings/keyboard source too, with real headers.
syntax=build/'navigation-view-syntax.cpp'
syntax.write_text('#include "tests/device/native/NavigationViewObservation.h"\nint main() { overte::e2e::NavigationViewObservation source; }\n')
subprocess.run([*command,'-fsyntax-only',str(syntax),*flags],check=True,timeout=120)
env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
subprocess.run([str(binary),'--testScript'],check=True,env=env,timeout=30)
print('PASS: original Places QML, ordinary Qt events, obstruction refusal, reply/modal identity; Qt6 host only')
