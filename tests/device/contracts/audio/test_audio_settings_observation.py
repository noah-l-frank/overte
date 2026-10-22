#!/usr/bin/env python3
"""Compile whole original getter with explicit engine/mixer seams; no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[4]
environment=dict(os.environ);library_paths=[]
major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
moc=None
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
    library_paths=['-L'+str(prefix/'usr/lib64')];moc=prefix/'usr/lib64/qt5/bin/moc'
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
if moc is None:
    moc=shutil.which('moc'+major) or shutil.which('moc')
    if moc is None:
        libexec=subprocess.check_output(['pkg-config','--variable=libexecdir','Qt'+major+'Core'],text=True,env=environment).strip()
        moc=Path(libexec)/'moc'
source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
start=source.index('QVariantMap TestScriptingInterface::featureAudioSettingsObservation(')
end=source.index('QVariantMap TestScriptingInterface::featurePendingCommitOwner(',start)
body=source[start:end]
with tempfile.TemporaryDirectory(prefix='audio-settings-') as directory:
    private=Path(directory);private.chmod(0o700)
    (private/'original-audio-settings-getter.inc').write_text(body)
    fixture=Path(__file__).with_name('audio-settings-observation-test.cpp')
    subprocess.run([str(moc),'-DOVERTE_E2E_FEATURE_TESTS',str(fixture),'-o',str(private/'audio-settings-observation-test.moc')],check=True,timeout=30,env=environment)
    binary=private/'test'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(ROOT),'-I'+str(private),str(fixture),'-o',str(binary),*library_paths,*flags],check=True,timeout=90,env=environment)
    subprocess.run([str(binary)],check=True,timeout=10,env=environment)
    raw=subprocess.check_output([str(binary),'--testScript'],text=True,timeout=10,env=environment)
    sys.path.insert(0,str(ROOT/'tests/device'))
    from adapters.pico4.audio_settings_source import validate,accept
    previous=None
    for line in raw.splitlines():
        value=json.loads(line);validate(value,value,value['processId'],value['capturedEpochMs']);previous=accept(previous,value)
    assert previous is not None
    plain=private/'non-pico.cpp';plain.write_text('#include <QVariantMap>\n#include <cassert>\n'
        'class TestScriptingInterface {public:QVariantMap featureAudioSettingsObservation(const QVariantMap& command);};\n'
        +body+'int main(){TestScriptingInterface source;assert(source.featureAudioSettingsObservation({}).isEmpty());}\n')
    binary=private/'non-pico'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS',str(plain),'-o',str(binary),*library_paths,*flags],check=True,timeout=90,env=environment)
    subprocess.run([str(binary)],check=True,timeout=10,env=environment)
