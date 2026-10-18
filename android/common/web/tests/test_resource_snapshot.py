#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Focused actual Qt Core and portable JVM resource lease tests."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--qt-major', choices=('5', '6'), default='6')
args = parser.parse_args()
web = Path(__file__).resolve().parents[1]
root = web.parents[2]
with tempfile.TemporaryDirectory(prefix='overte-resource-snapshot-') as temporary:
    stage = Path(temporary)
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt' + args.qt_major + 'Core'], text=True))
    subprocess.run(['c++', '-std=c++17', '-fPIC', '-UNDEBUG', '-pthread', str(web / 'tests/resource-snapshot.cpp'),
                    '-I' + str(web / 'src'), '-I' + str(root / 'libraries/shared/src'), '-o', str(stage / 'snapshot'), *flags], check=True)
    subprocess.run([str(stage / 'snapshot')], check=True)
    subprocess.run(['javac', '-d', str(stage), str(web / 'java/org/overte/web/WebResourceLease.java'),
                    str(web / 'tests/java/org/overte/web/WebResourceLeaseTest.java')], check=True)
    subprocess.run(['java', '-cp', str(stage), 'org.overte.web.WebResourceLeaseTest'], check=True)
