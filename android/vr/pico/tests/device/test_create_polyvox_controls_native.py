"""Actual original PolyVox QML/controls with normal Qt pointer/field input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import json
import sys
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))


def original(source, signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


def pointer_source(stage):
    # Whole unchanged source bodies; root/window/pause alone are host boundaries.
    surface=(ROOT/'libraries/ui/src/ui/OffscreenQmlSurface.cpp').read_text()
    header=(ROOT/'libraries/ui/src/ui/OffscreenQmlSurface.h').read_text()
    pointer=(ROOT/'libraries/script-engine/src/PointerEvent.cpp').read_text()
    bridge=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp').read_text()
    first=header.index('    struct TouchState {');last=header.index('std::map<uint32_t, TouchState> _activeTouchPoints;',first)
    state=header[first:last+len('std::map<uint32_t, TouchState> _activeTouchPoints;')]
    context='''
class OffscreenQmlSurface : public QObject {
public:
    OffscreenQmlSurface(QQuickItem* root,QQuickWindow* window):root(root),window(window){}
    QQuickItem* getRootItem(){return root;} QQuickWindow* getWindow(){return window;}
    bool isPaused() const{return false;}
    void hoverBeginEvent(const PointerEvent&,QTouchDevice&);
    void hoverEndEvent(const PointerEvent&,QTouchDevice&);
    bool handlePointerEvent(const PointerEvent&,QTouchDevice&,bool release=false);
    QQuickItem* root;QQuickWindow* window;
    STATE
};
'''.replace('STATE',state)
    bodies=[original(pointer,signature) for signature in (
        'PointerEvent::PointerEvent(EventType type, uint32_t id) :',
        'PointerEvent::PointerEvent(EventType type, uint32_t id, const glm::vec2& pos2D, Button button,')]
    bodies+=[context]
    bodies+=[original(surface,signature) for signature in ('void OffscreenQmlSurface::hoverBeginEvent(',
        'void OffscreenQmlSurface::hoverEndEvent(','bool OffscreenQmlSurface::handlePointerEvent(')]
    bodies+=[original(bridge,signature) for signature in ('bool effectiveVisible(',
        'QTouchDevice& bridgeTouchDevice(','bool sendPointerAt(','bool sendPointerClick(')]
    (stage/'actual-pointer-route.inc').write_text('\n'.join(bodies))


class CreatePolyvoxControlsNativeTests(unittest.TestCase):
    def run_original(self, cpp):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','5');self.assertEqual('5',major)
        prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
            QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt5'+module for module in ('Core','Gui','Qml','Quick','Test'))],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='create-original-polyvox-') as directory:
            stage=Path(directory);pointer_source(stage);binary=stage/'test';imports=stage/'imports/TabletScriptingInterface';imports.mkdir(parents=True)
            (imports/'qmldir').write_text('module TabletScriptingInterface\nsingleton Tablet 1.0 Tablet.qml\nsingleton TabletEnums 1.0 TabletEnums.qml\n')
            (imports/'Tablet.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject { function playSound(value) {} }\n')
            (imports/'TabletEnums.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject { readonly property int buttonClick: 1; readonly property int buttonHover: 2 }\n')
            native=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
            start=native.index('    } else if (controlId.startsWith("create-extra.")) {')
            end=native.index('\n    } else if (',start+10)
            branch=native[start:end].split('{',1)[1]
            admission=original(native,'bool integer(')
            (stage/'actual-create-extra-input.inc').write_text(admission+'\n'
                'QJsonObject originalCreateExtraInput(QQuickItem* item,QQuickWindow* window,const QString& controlId,const QString& action,const QJsonObject& command, const std::function<bool(QQuickItem*)>& pointerClick){\n'
                'QJsonObject result{{"performed",false}},current{{"createExtraControlsVersion",1}};bool delivered=false;struct {QQuickItem* item;} control{item};\n'
                +branch+'\nresult["performed"]=delivered;return result;}\n')
            start=native.index('    } else if (controlId.startsWith("create-voxel.")) {')
            end=native.index('\n    } else if (',start+10)
            branch=native[start:end].split('{',1)[1]
            (stage/'actual-create-voxel-input.inc').write_text(admission+'\n'
                'QJsonObject originalCreateVoxelInput(QQuickItem* item,QQuickWindow* window,const QString& controlId,const QString& action,const QJsonObject& command, const std::function<bool(QQuickItem*)>& pointerClick){\n'
                'QJsonObject result{{"performed",false}},current{{"createVoxelControlsVersion",1}};bool delivered=false;struct {QQuickItem* item;} control{item};\n'
                +branch+'\nresult["performed"]=delivered;return result;}\n')
            (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:\n'
                'inline static QUrl scripts,qml; static QUrl defaultScriptsLocation(){return scripts;}\n'
                'static QUrl qmlUrl(const QString& value){return qml.resolved(QUrl(value));}};\n')
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+directory,'-I'+str(ROOT),
                '-I'+str(ROOT/'libraries/ui/src'),'-I'+str(ROOT/'libraries/script-engine/src'),
                '-isystem',str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),str(HERE/cpp),str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),
                '-o',str(binary),'-L'+str(prefix/'usr/lib64'),*flags],check=True,timeout=90,env=environment)
            environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_FORCE_STDERR_LOGGING='1')
            subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),str(ROOT),str(stage/'imports')],check=True,timeout=30,env=environment)
            output=subprocess.check_output(['unshare','--user','--map-root-user','--net',str(binary),'--testScript',str(ROOT),str(stage/'imports')],
                text=True,timeout=30,env=environment)
            return output

    def test_original_qml_normal_fields_preset_and_canonical_create_callback(self):
        output=self.run_original('create-polyvox-controls.cpp');message=json.loads(output)
        self.assertEqual({'detail','polyvox','cancel'},set(message))
        with tempfile.TemporaryDirectory(prefix='create-original-polyvox-script-') as directory:
            callback=Path(directory)/'actual-qt-callback.json';callback.write_text(output)
            subprocess.run(['node',str(HERE/'create-polyvox-script.js'),str(callback)],check=True,timeout=10)

    def test_original_voxel_tools_fields_backend_settings_remove_stroke_and_restore(self):
        output=self.run_original('create-voxel-controls.cpp');message=json.loads(output)
        from adapters.pico4.create_voxel_ui import settings
        self.assertEqual({'before','configured','restored','stroke','pointerCalls','counterexamples','settingsReceipt'},set(message))
        self.assertEqual({'beforeReply':False,'beforeControls':0,'afterReply':True},message['settingsReceipt'])
        self.assertEqual(['moved-token','disabled','higher-overlay','clipped'],message['counterexamples'])
        settings(message['before']);settings(message['configured']);self.assertEqual(message['before'],message['restored'])
        self.assertEqual('cube',message['configured']['voxelEditMode']);self.assertEqual(.5,message['configured']['voxelSphereSize'])
        self.assertTrue(message['configured']['voxelRemove']);self.assertGreater(message['pointerCalls'],10)
        self.assertEqual(16,sum(v!=0 for v in message['stroke']['volume']));self.assertEqual([],message['stroke']['remainingTimers'])
        self.assertEqual(1,len(message['stroke']['calls']));self.assertEqual(1,len(message['stroke']['strokes']))


if __name__=='__main__':unittest.main()
