#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile actual native Chat peer/cache/file helpers, with synthetic producers."""
import argparse
from pathlib import Path
import shlex
import subprocess
ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build-dir',required=True,type=Path)
args=parser.parse_args();build=args.build_dir.resolve()
if ROOT not in build.parents:parser.error('Build directory must be inside this checkout')
build.mkdir(parents=True,exist_ok=False)
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
binary=build/'chat-peer-runtime'
subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),str(ROOT/'android/phone/tests/device/chat-peer-runtime.cpp'),'-o',str(binary),*flags],check=True,timeout=120)
subprocess.run([str(binary),'--testScript'],check=True,timeout=30)
print('PASS: Qt6 host helper only; Agent/MessagesClient product translation units and devices remain untested')
