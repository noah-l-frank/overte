#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Compile actual selected Android/Qt/JNI inline backend without unrelated suites."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import signal
import subprocess
import tempfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--qt-root',type=Path,required=True)
p.add_argument('--android-jar',type=Path,required=True)
p.add_argument('--webkit-jar',type=Path,required=True)
p.add_argument('--annotation-jar',type=Path,required=True)
p.add_argument('--jdk',type=Path,default=Path('/usr/lib/jvm/temurin-21-jdk'))
p.add_argument('--evidence-dir',type=Path,required=True)
a=p.parse_args();web=Path(__file__).resolve().parents[1];root=web.parents[2]
a.evidence_dir.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,PKG_CONFIG_PATH=str(a.qt_root/'usr/lib64/pkgconfig'),PKG_CONFIG_SYSROOT_DIR=str(a.qt_root),
         LD_LIBRARY_PATH=str(a.qt_root/'usr/lib64'),QML2_IMPORT_PATH=str(a.qt_root/'usr/lib64/qt5/qml'),
         QT_PLUGIN_PATH=str(a.qt_root/'usr/lib64/qt5/plugins'),QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
java=list(sorted((web/'java/org/overte/web').glob('*.java')))+[web/'tests/java/org/overte/web/WebLifecycleBoundary.java']
inputs=java+list((web/'src').glob('*'))+list((web/'resources').glob('*.js'))+[web/'embedded-web.qrc',web/'tests/native.cpp',
        web/'tests/inline-backend-tests.h',web/'tests/inline-script-tests.h',root/'libraries/shared/src/InlineHtmlDocument.h',
        root/'libraries/shared/src/EmbeddedWebPolicy.h',root/'interface/resources/qml/controls/EmbeddedWebView.qml',
        root/'interface/resources/qml/controls/+android/EmbeddedWebBackend.qml']
record={'inputs':{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs},'commands':[],'environment':{k:env[k] for k in ('PKG_CONFIG_PATH','PKG_CONFIG_SYSROOT_DIR','LD_LIBRARY_PATH','QML2_IMPORT_PATH','QT_PLUGIN_PATH','QT_QPA_PLATFORM','QT_QUICK_BACKEND')}}
def run(argv,**kwargs):
    record['commands'].append(list(map(str,argv)));return subprocess.run(list(map(str,argv)),env=env,check=True,**kwargs)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
try:
    with tempfile.TemporaryDirectory(prefix='overte-inline-native-') as tmp:
        stage=Path(tmp);qtbin=a.qt_root/'usr/lib64/qt5/bin'
        run([a.jdk/'bin/javac','-cp',os.pathsep.join(map(str,(a.android_jar,a.webkit_jar,a.annotation_jar))),'-d',stage,*java])
        abi=run([a.jdk/'bin/javap','-s','-p','-classpath',stage,'org.overte.web.WebResourceLease$Response'],capture_output=True,text=True).stdout
        (a.evidence_dir/'response-abi.txt').write_text(abi)
        assert '(I[BLjava/lang/String;Ljava/lang/String;)V' in abi
        native_api=run([a.jdk/'bin/javap','-s','-p','-classpath',stage,'org.overte.web.EmbeddedWebView'],capture_output=True,text=True).stdout
        (a.evidence_dir/'native-api-abi.txt').write_text(native_api)
        assert 'wheel(long, long, long, java.lang.String, float, float, float, float, float, float, boolean)' in native_api
        assert '(JJJLjava/lang/String;FFFFFFZ)V' in native_api
        moc=stage/'moc.cpp';qrc=stage/'resources.cpp'
        run([qtbin/'moc',web/'src/NativeWebViewItem.h','-o',moc]);run([qtbin/'rcc',web/'embedded-web.qrc','-o',qrc])
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Quick','Qt5WebChannel','Qt5Network'],env=env,text=True))
        binary=stage/'native'
        run(['c++','-std=c++17','-fPIC','-UNDEBUG','-pthread',web/'src/NativeWebViewItem.cpp',web/'tests/native.cpp',moc,qrc,
             '-I'+str(web/'src'),'-I'+str(root/'libraries/shared/src'),'-I'+str(a.jdk/'include'),'-I'+str(a.jdk/'include/linux'),
             '-L'+str(a.jdk/'lib/server'),'-Wl,-rpath,'+str(a.jdk/'lib/server'),'-ljvm','-L'+str(a.qt_root/'usr/lib64'),'-o',binary,*flags])
        command=[str(binary),str(stage/'qwebchannel.js'),str(root/'interface/resources/qml/controls/+android/EmbeddedWebBackend.qml'),str(stage)]
        run(command)
        # A native-only response class must survive shrinking/packaging. Remove
        # actual bytecode, rather than compiling a substitute API, and require failure.
        response=stage/'org/overte/web/WebResourceLease$Response.class';bytecode=response.read_bytes();response.unlink()
        negative=subprocess.run(command,env=env,capture_output=True,text=True)
        response.write_bytes(bytecode)
        (a.evidence_dir/'missing-response-bytecode-negative.log').write_text(negative.stdout+negative.stderr)
        assert negative.returncode==-signal.SIGABRT and 'WebResourceLease$Response' in negative.stderr and 'Assertion' in negative.stderr
        record['missing_response_negative']={'exit':negative.returncode,'expected':'missing real native response bytecode must fail'}
        print('PASS: actual production Java ABI/Qt5/moc/rcc/JNI inline backend; missing native response bytecode rejected')
finally:
    (a.evidence_dir/'compile-inputs-and-commands.json').write_text(json.dumps(record,indent=2)+'\n')
