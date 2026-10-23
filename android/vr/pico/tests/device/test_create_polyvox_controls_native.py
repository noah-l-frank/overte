"""Actual original PolyVox QML/controls with normal Qt pointer/field input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import hashlib
import threading
import time
import json
import sys
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from contextlib import nullcontext
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


def native_trace_process(command,environment,trace):
    """Actual independent host receipts of bounded, immediately written frames."""
    receipts=[];failure=[];done=threading.Event()
    def consume():
        source=None;pending=b'';total=0
        try:
            with trace.with_suffix('.host-receipts.jsonl').open('x') as observed:
                while True:
                    if source is None and trace.exists():source=trace.open('rb')
                    chunk=source.read(65536) if source else b''
                    if chunk:
                        total+=len(chunk)
                        if total>16*1024*1024:raise ValueError('Original native trace exceeds its byte inventory')
                        pending+=chunk
                        while b'\n' in pending:
                            line,pending=pending.split(b'\n',1)
                            host_ns=time.monotonic_ns();host_epoch=time.time_ns()//1_000_000
                            original=json.loads(line)
                            if len(receipts)>=512:raise ValueError('Original native trace exceeds its frame inventory')
                            receipt=dict(sequence=original['sequence'],capturedHostMonotonicNs=host_ns,
                                capturedHostEpochMs=host_epoch,sourceSha256=hashlib.sha256(line+b'\n').hexdigest())
                            receipts.append(receipt);observed.write(json.dumps(receipt,sort_keys=True)+'\n');observed.flush()
                    elif done.is_set():
                        if pending:raise ValueError('Incomplete original native frame')
                        break
                    else:done.wait(.01)
        except BaseException as error:failure.append(error)
        finally:
            if source:source.close()
    reader=threading.Thread(target=consume,name='create-original-native-host-receipts',daemon=True);reader.start()
    try:output=subprocess.check_output(command,text=True,timeout=30,env=environment)
    finally:
        done.set();reader.join(timeout=2)
    if reader.is_alive():raise RuntimeError('Original native receipt reader did not stop')
    if failure:raise failure[0]
    lines=trace.read_bytes().splitlines(keepends=True)
    return dict(raw=output,hostReceipts=receipts,traceLines=lines)


class CreatePolyvoxControlsNativeTests(unittest.TestCase):
    def run_original(self, cpp, modes=None):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','5');self.assertEqual('5',major)
        prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
            QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt5'+module for module in (('Core','Gui','Qml','Quick','Test','Concurrent') if modes else ('Core','Gui','Qml','Quick','Test')))],text=True,env=environment))
        evidence=environment.get('OVERTE_CREATE_VOXEL_NATIVE_EVIDENCE_DIR') if modes else None
        destination=None
        if evidence:
            destination=Path(evidence);destination.mkdir(parents=True,exist_ok=False,mode=0o700)
        context=(nullcontext(tempfile.mkdtemp(prefix='create-original-polyvox-',dir=destination))
            if destination else tempfile.TemporaryDirectory(prefix='create-original-polyvox-'))
        with context as directory:
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
            start=native.index('    } else if (controlId.startsWith("create.")) {')
            end=native.index('\n    } else if (',start+10)
            branch=native[start:end].split('{',1)[1]
            (stage/'actual-create-base-input.inc').write_text(admission+'\n'
                'QJsonObject originalCreateInput(QQuickItem* item,QQuickWindow* window,const QString& controlId,const QString& action,const QJsonObject& command, const std::function<bool(QQuickItem*)>& pointerClick,const std::function<bool(QQuickItem*,QPointF)>& pointerAt={}){\n'
                'QJsonObject result{{"performed",false}},current{{"createControlsVersion",1}};bool delivered=false;struct {QQuickItem* item;} control{item};\n'
                +branch+'\nresult["performed"]=delivered;return result;}\n')
            (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:\n'
                'inline static QUrl scripts,qml; static QUrl defaultScriptsLocation(){return scripts;}\n'
                'static QUrl qmlUrl(const QString& value){return qml.resolved(QUrl(value));}};\n')
            if cpp=='create-recovery-controls.cpp':
                edit=(ROOT/'scripts/system/create/edit.js').read_text()
                code=edit[edit.index('    function copyProperties(a, b) {'):edit.index('    var fcreateNewEntity;')]
                code+='\n'+original(edit,'function createNewEntity(')
                code+='\n'+original(edit,'function fromQml(')
                code+='\n'+original(edit,'function sortSelectedEntities(')+'\n'+original(edit,'function recursiveDelete(')
                code+='\n'+original(edit,'createApp.deleteSelectedEntities = function()')+';\n'
                (stage/'original-recovery.js').write_text(code)
            additional=[];native_flags=[]
            if modes:
                import importlib.util
                spec=importlib.util.spec_from_file_location('create_voxel_native_prepare',HERE/'create-voxel-native-prepare.py')
                prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
                additional=prepare.prepare(stage,environment,prefix)
                native_flags=['-DANDROID_APP_PICO_INTERFACE','-DGLM_FORCE_RADIANS','-DGLM_ENABLE_EXPERIMENTAL','-DGLM_FORCE_CTOR_INIT','-fmax-errors=4','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-pthread',
                    '-I'+str(HERE),
                    *('-I'+str(ROOT/path) for path in ('libraries/shared/src','libraries/gpu/src','libraries/graphics/src'))]
            subprocess.run(['c++','-std=c++20' if modes else '-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+directory,'-I'+str(ROOT),
                '-I'+str(ROOT/'libraries/ui/src'),'-I'+str(ROOT/'libraries/script-engine/src'),
                '-isystem',str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),*native_flags,str(HERE/cpp),*additional,str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),
                '-o',str(binary),'-L'+str(prefix/'usr/lib64'),*flags],check=True,timeout=90,env=environment)
            environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_FORCE_STDERR_LOGGING='1')
            subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),str(ROOT),str(stage/'imports')],check=True,timeout=30,env=environment)
            if modes:
                results={}
                for mode in modes:
                    environment['OVERTE_CREATE_VOXEL_NATIVE_MODE']=mode
                    trace=(destination if destination else stage)/(mode+'-source.jsonl')
                    environment['OVERTE_CREATE_VOXEL_NATIVE_TRACE']=str(trace)
                    results[mode]=native_trace_process(['unshare','--user','--map-root-user','--net',str(binary),
                        '--testScript',str(stage/'original-voxel-delete.js'),str(ROOT),str(stage/'imports')],environment,trace)
                    if destination:(destination/(mode+'.json')).write_text(results[mode]['raw'])
                if destination:
                    (destination/'original-provenance.json').write_bytes((stage/'create-voxel-native-original-provenance.json').read_bytes())
                return results
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
