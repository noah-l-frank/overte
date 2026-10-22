#!/usr/bin/env python3
"""Original Android export JNI/lease and normal QML controls on host Qt/JNI.

No Android runtime, JVM backend, renderer or network operates here. The original
normal pointer path reaches the actual JNI-unavailable error, never Save success.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[4]
def body(source,marker):
    start=source.index(marker);opening=source.index('{',start);depth=1;end=opening+1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'

environment=dict(os.environ);library=[];major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
        QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
    library=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
    *('Qt'+major+name for name in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
variable='host_bins' if major=='5' else 'libexecdir'
moc=Path(subprocess.check_output(['pkg-config','--variable='+variable,'Qt'+major+'Core'],text=True,env=environment).strip())/'moc'
if not moc.is_file() and environment.get('PKG_CONFIG_SYSROOT_DIR'):moc=Path(environment['PKG_CONFIG_SYSROOT_DIR'])/str(moc).lstrip('/')
# The unchanged original JNI TU uses Qt5's ushort UTF16 overload. Qt6 still
# provides it; retain its deprecation warning without rejecting the baseline.
# Complete QBitArray before GCC16's Qt6 header SFINAE sees its forward declaration.
compatibility=['-include','QChar','-include','QBitArray','-Wno-error=deprecated-declarations'] if major=='6' else []
java=shutil.which('javac')
if not java:raise RuntimeError('Prepared host JDK is required')
jdk=Path(java).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='pico-snapshot-export-native-') as directory:
    stage=Path(directory);runtime=stage/'runtime';runtime.mkdir(mode=0o700);data=stage/'data';data.mkdir(mode=0o700)
    environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime),XDG_DATA_HOME=str(data))
    source=Path(__file__).with_name('snapshot-export-lease-test.cpp');header=ROOT/'android/common/snapshot/src/NativeSnapshotAdapter.h'
    (stage/'original-snapshot-export-getter.inc').write_text(body((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),
        'QVariantMap TestScriptingInterface::featurePicoSnapshotExports('))
    (stage/'original-snapshot-existing-tablet.inc').write_text(body((ROOT/'libraries/ui/src/ui/TabletScriptingInterface.cpp').read_text(),
        'TabletProxy* TabletScriptingInterface::featureExistingTablet('))
    subprocess.run([str(moc),str(source),'-o',str(stage/'snapshot-export-lease-test.moc')],check=True,timeout=30,env=environment)
    subprocess.run([str(moc),str(header),'-o',str(stage/'native-moc.cpp')],check=True,timeout=30,env=environment)
    for profile,defines in (('pico',['OVERTE_E2E_FEATURE_TESTS','ANDROID_APP_PICO_INTERFACE']),
            ('phone',['OVERTE_E2E_FEATURE_TESTS','ANDROID_APP_PHONE_INTERFACE']),('other',['OVERTE_E2E_FEATURE_TESTS']),('production',['ANDROID_APP_PICO_INTERFACE'])):
        executable=stage/profile
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-pthread','-DOVERTE_PICO_SETUP',*compatibility,
            *('-D'+value for value in defines),'-I'+str(ROOT),'-I'+str(ROOT/'interface/src/ui'),'-I'+str(header.parent),'-I'+str(stage),
            '-I'+str(jdk/'include'),'-I'+str(jdk/'include/linux'),str(ROOT/'android/common/snapshot/src/NativeSnapshotAdapter.cpp'),
            str(stage/'native-moc.cpp'),str(source),'-o',str(executable),*library,*flags],check=True,timeout=60,env=environment)
        for options in ([],['--testScript']):
            expected='enabled' if options and profile in ('pico','phone') else 'disabled'
            subprocess.run(['unshare','--user','--map-root-user','--net',str(executable),expected,str(ROOT),*options],
                check=True,timeout=20,env=environment)
print('PASS: original whole Snapshot JNI, native monotone leases, normal QML Save/Share/Upload controls; four gated profiles (Qt'+major+')')
