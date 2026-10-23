#!/usr/bin/env python3
"""Actual upload provenance header/file/lifetime; explicit reply signal seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import json
import sys
ROOT=Path(__file__).resolve().parents[4]
environment=dict(os.environ);library=[];major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'))
    library=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',*('Qt'+major+name for name in ('Core','Gui','Network'))],text=True,env=environment))
compatibility=['-include','QChar','-include','QBitArray'] if major=='6' else []
with tempfile.TemporaryDirectory(prefix='pico-snapshot-upload-native-') as directory:
    stage=Path(directory);runtime=stage/'runtime';runtime.mkdir(mode=0o700)
    environment.update(QT_QPA_PLATFORM='offscreen',XDG_RUNTIME_DIR=str(runtime))
    source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text();start=source.index('QVariantMap TestScriptingInterface::featurePicoSnapshotUpload(')
    opening=source.index('{',start);depth=1;end=opening+1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    (stage/'original-snapshot-upload-getter.inc').write_text(source[start:end]+'\n')
    header=(ROOT/'libraries/networking/src/AccountManager.h').read_text();opening=header.index('class JSONCallbackParameters {');end=header.index('Q_DECLARE_METATYPE(AccountManagerAuth::Type);',opening)+len('Q_DECLARE_METATYPE(AccountManagerAuth::Type);')
    (stage/'original-callback-params.inc').write_text(header[opening:end])
    account=(ROOT/'libraries/networking/src/AccountManager.cpp').read_text();opening=account.index('JSONCallbackParameters::JSONCallbackParameters(');end=account.index('\nQJsonObject AccountManager::dataObjectFromResponse',opening)
    (stage/'original-callback-constructor.inc').write_text(account[opening:end])
    opening=account.index('#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)',account.index('    if (networkReply) {'))
    end=account.index('#endif',opening)+len('#endif');(stage/'original-account-upload-hook.inc').write_text(account[opening:end]+'\n')
    (stage/'AddressManager.h').write_text('// Explicit host backend seam; declarations precede the original TU.\n')
    (stage/'scripting').mkdir();(stage/'scripting/WindowScriptingInterface.h').write_text('// Explicit host window signal seam.\n')
    variable='host_bins' if major=='5' else 'libexecdir'
    moc=Path(subprocess.check_output(['pkg-config','--variable='+variable,'Qt'+major+'Core'],text=True,env=environment).strip())/'moc'
    if not moc.is_file() and environment.get('PKG_CONFIG_SYSROOT_DIR'):moc=Path(environment['PKG_CONFIG_SYSROOT_DIR'])/str(moc).lstrip('/')
    for name,defines in (('pico',['OVERTE_E2E_FEATURE_TESTS','ANDROID_APP_PICO_INTERFACE']),('phone',['OVERTE_E2E_FEATURE_TESTS','ANDROID_APP_PHONE_INTERFACE']),('other',['OVERTE_E2E_FEATURE_TESTS']),('production',['ANDROID_APP_PICO_INTERFACE'])):
        executable=Path(directory)/name
        subprocess.run([str(moc),*('-D'+value for value in defines),str(ROOT/'interface/src/ui/SnapshotUploader.h'),'-o',str(stage/'original-snapshot-uploader.moc')],check=True,timeout=20,env=environment)
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-pthread',*compatibility,'-DOVERTE_PICO_SETUP','-I'+str(stage),*('-D'+value for value in defines),'-I'+str(ROOT),'-I'+str(ROOT/'libraries/networking/src'),str(Path(__file__).with_name('snapshot-upload-originals-test.cpp')),'-o',str(executable),*library,*flags],check=True,timeout=45,env=environment)
        for options in ([],['--testScript']):
            result=subprocess.run([str(executable),*options],capture_output=True,text=True,timeout=5,env=environment)
            if result.returncode:sys.stderr.write(result.stderr);result.check_returncode()
            if name=='pico' and options:
                sys.path.insert(0,str(ROOT/'tests/device'))
                from adapters.pico4.snapshot_upload_source import validate,file_original
                from adapters.normal_ui import NativeUIError
                value=json.loads(result.stdout);request=dict(schemaVersion=1,commandId='a'*32,action='feature-pico-snapshot-upload',runId='b'*32)
                # These are actual host paths/FDs, not invented Android paths.
                # Their original metadata validates; the full Pico parser must
                # reject them as target evidence rather than relabel host files.
                jobs=value['source']['jobs'];assert len(jobs)==1
                file_original(jobs[0]['file']);assert not any(jobs[0][key] for key in ('uploaderAlive','fileAlive','multipartAlive'))
                try:validate(value,request,value['processId'],value['capturedEpochMs'])
                except NativeUIError:pass
                else:raise AssertionError('Host path was incorrectly admitted as Pico source')
            else:assert result.stdout==''
print('PASS: actual gated Pico upload original FD/read/hash/lifetime and reply-signal observation (Qt'+major+'); network/Android are explicit seams')
