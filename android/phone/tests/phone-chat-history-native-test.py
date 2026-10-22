#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile actual Setting::Manager and Chat history lease; no device transport."""
import argparse
from pathlib import Path
import shlex
import subprocess
ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build-dir',required=True,type=Path)
args=parser.parse_args();build=args.build_dir.resolve()
if ROOT not in build.parents:parser.error('Build directory must be inside this checkout')
build.mkdir(parents=True,exist_ok=False)
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Test'],text=True))
header=ROOT/'libraries/shared/src/SettingManager.h';moc=build/'moc_SettingManager.cpp'
subprocess.run(['/usr/lib64/qt6/libexec/moc','-DOVERTE_E2E_FEATURE_TESTS',str(header),'-o',str(moc)],check=True,timeout=30)
binary=build/'chat-history-runtime'
subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),
    str(ROOT/'android/phone/tests/device/chat-history-runtime.cpp'),str(ROOT/'libraries/shared/src/SettingManager.cpp'),str(moc),'-o',str(binary),*flags],check=True,timeout=120)
view=build/'chat-view-syntax.cpp';view.write_text('#include "tests/device/native/ChatViewObservation.h"\nint main() { overte::e2e::ChatViewObservation source; }\n')
view_flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Quick','Qt6Qml','Qt6Gui','Qt6Core','Qt6Network'],text=True))
subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE','-I'+str(ROOT),
    '-I'+str(ROOT/'libraries/shared/src'),'-I'+str(ROOT/'libraries/ui/src'),'-fsyntax-only',str(view),*view_flags],check=True,timeout=120)
subprocess.run([str(binary),'--testScript'],check=True,timeout=30)
print('PASS: actual Setting::Manager translation unit and Qt6 history helper; GUI closure/Erase producer synthetic; devices untested')
