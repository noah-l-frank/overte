#!/usr/bin/env python3
"""Compile original passive history, actual Chat QML and native field input.

VR keyboard and OS/Hidden state are explicit boundaries; no device run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import sys

ROOT=Path(__file__).resolve().parents[4]
environment=dict(os.environ);library_paths=[]
major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
if major not in ('5','6'):raise ValueError('Unsupported Qt major')
if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
    prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
        LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
        QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
    library_paths=['-L'+str(prefix/'usr/lib64')]
flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
    *('Qt'+major+module for module in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
bridge=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp').read_text()
def original_body(signature):
    start=bridge.index(signature);opening=bridge.index('{',start);depth=1;end=opening+1
    while depth:
        if bridge[end]=='{':depth+=1
        elif bridge[end]=='}':depth-=1
        end+=1
    return bridge[start:end]
with tempfile.TemporaryDirectory(prefix='lifecycle-background-') as directory:
    binary=Path(directory)/'test'
    (Path(directory)/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:\n'
        'static QUrl qmlUrl(const QString& value){return QUrl("file:///unused-host-Scripts/").resolved(QUrl(value));}};\n')
    fragment=Path(directory)/'bridge-source.cpp'
    fragment.write_text('''#include "tests/device/native/LifecycleBackgroundHistory.h"
#include "tests/device/native/LifecycleUiObservation.h"
#include "tests/device/native/PrivatePreviewFiles.h"
#include <QQuickItem>
#include <QQuickWindow>
#include <QJsonDocument>
#include <memory>
class NativeApp:public QGuiApplication {public:bool isHMDMode() const;};
#undef qApp
#define qApp (static_cast<NativeApp*>(QCoreApplication::instance()))
class Surface {public:QQuickWindow* getWindow();};
class Tablet:public QObject {public:QQuickItem* getTabletRoot();Surface* getTabletSurface();bool onHomeScreen();};
class TabletScriptingInterface {public:Tablet* getTablet(const QString&);};
class Keyboard {public:QVariantMap featureChatObservation();};
class DependencyManager {public:template<class T>static bool isSet();template<class T>static std::shared_ptr<T> get();};
namespace overte::pico::e2e {namespace {
const QString BRIDGE_DIRECTORY="/explicit-host-boundary",SYSTEM_TABLET="com.highfidelity.interface.tablet.system";
bool bridgeEnabled();
'''+original_body('bool writeJson(')+'''
class ActualSourceBodies:public QObject {public:
'''+original_body('    QVariantMap lifecycleCurrent(')+'\n'+original_body('    void lifecycleBackgroundTick(')+'''
overte::e2e::LifecycleUiObservation _lifecycleObservation{{}};
overte::e2e::LifecycleBackgroundHistory _lifecycleBackground{this,[this](const QString& run){return lifecycleCurrent(run);}};
};}}
''')
    subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),'-c',str(fragment),
        '-o',str(Path(directory)/'bridge-source.o'),*flags],check=True,timeout=90,env=environment)
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+directory,'-I'+str(ROOT),
        '-I'+str(ROOT/'libraries/ui/src'),str(Path(__file__).with_name('lifecycle-background-test.cpp')),
        str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(binary),*library_paths,*flags],
        check=True,timeout=90,env=environment)
    for arguments in ([],['--testScript']):
        subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),*arguments,
            str(ROOT/'scripts/communityScripts/armored-chat/armored_chat.qml'),str(Path(directory)/'original.json')],check=True,timeout=30,
            env={**environment,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'})
    sys.path.insert(0,str(ROOT/'tests/device'))
    from adapters.pico4.lifecycle_background_source import validate,accept
    previous=None
    for row in json.loads((Path(directory)/'original.json').read_text()):
        packet,operation=row['packet'],row['operation']
        request=dict(schemaVersion=1,commandId=packet['commandId'],action='feature-lifecycle-background',operation=operation,runId='a'*32)
        if operation!='observe':request.update(ownerInstance=packet['instance'],intentSequence=packet['lastIntentSequence'])
        validate(packet,request,packet['processId'],packet['capturedEpochMs']);accept(previous,packet);previous=packet
    print('PASS actual Qt'+major+' Chat field/native IME/passive history; no full Pico translation-unit/VR/OS background claim')
