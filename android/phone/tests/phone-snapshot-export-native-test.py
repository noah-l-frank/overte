#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile the actual Android Snapshot JNI translation unit with host Qt6/JNI.

No synthetic SnapshotStorage/JNI implementations; no JVM, Android runtime or APK
is executed. The Android ABI/toolchain and complete client remain unqualified.
"""
import argparse
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-dir',type=Path)
args=parser.parse_args()
if args.build_dir:
    build=args.build_dir.resolve()
    if ROOT not in build.parents:parser.error('Build directory must be inside this checkout')
    build.mkdir(parents=True,exist_ok=False)
else:
    parent=ROOT/'build';parent.mkdir(exist_ok=True)
    build=Path(tempfile.mkdtemp(prefix='snapshot-export-native-',dir=parent))
header=ROOT/'android/common/snapshot/src/NativeSnapshotAdapter.h'
source=ROOT/'android/common/snapshot/src/NativeSnapshotAdapter.cpp'
java=shutil.which('javac')
if not java:raise SystemExit('Prepared host JDK is required')
jdk=Path(java).resolve().parents[1]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Qml'],text=True))
qt_libexec=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())
moc=build/'moc.cpp'
subprocess.run([str(qt_libexec/'moc'),str(header),'-o',str(moc)],check=True,timeout=30)
harness=build/'main.cpp'
harness.write_text('''#include <QCoreApplication>
#include <jni.h>
#include "NativeSnapshotAdapter.h"
extern "C" jboolean Java_org_overte_snapshot_SnapshotAdapter_nativeFeatureEnabled(JNIEnv*,jclass);
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);
    const bool expected=QString::fromLocal8Bit(argv[1])=="enabled";
    if ((Java_org_overte_snapshot_SnapshotAdapter_nativeFeatureEnabled(nullptr,nullptr)==JNI_TRUE)!=expected)return 1;
    // An uninitialized backend must never be represented as observed success.
    if (!NativeSnapshotAdapter::featureExportObservation().isEmpty())return 2;
    if (!NativeSnapshotAdapter::featureReadbackCommand("{}").isEmpty())return 3;
    return 0;
}
''')
for name,definitions in (
    ('phone',['-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE']),
    ('other-android',['-DOVERTE_E2E_FEATURE_TESTS']),
    ('production',['-DANDROID_APP_PHONE_INTERFACE']),
):
    binary=build/name
    subprocess.run(['c++','-std=c++17','-fPIC',*definitions,
        '-I'+str(header.parent),'-I'+str(ROOT/'interface/src/ui'),
        '-I'+str(jdk/'include'),'-I'+str(jdk/'include/linux'),
        str(source),str(moc),str(harness),'-o',str(binary),*flags],check=True,timeout=90)
    subprocess.run([str(binary),'disabled'],check=True,timeout=10)
    subprocess.run([str(binary),'enabled' if name=='phone' else 'disabled','--testScript'],check=True,timeout=10)
print('Actual Snapshot JNI source: three host compilation profiles and six guarded runtime checks passed.')
