#!/usr/bin/env python3
"""Original bounded recipe + actual normal Pico UI TU/QML; explicit VM/VR seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.snapshot_cancel import original,validate,PicoSnapshotCancel,PicoSnapshotCancelIO
from adapters.script_journey.lock import ScriptSourceLock
from adapters.normal_ui import NativeUIError
from copy import deepcopy


def body(source,marker):
    start=source.index(marker);opening=source.index('{',start);depth=1;end=opening+1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]+'\n'


def reader_boundaries(output,directory):
    """Real immutable native packet; SDK/file channel is an explicit host seam."""
    packet=output['packet'];request=output['command'];epoch=packet['capturedEpochMs']
    raw=json.dumps(dict(commandId=request['commandId'],packet=packet))
    class Transport(PicoSnapshotCancelIO):
        def __init__(self):
            self._before_send=lambda command:None;self.writes=[];self.checks=0;self.late=lambda:None;self.lost=False
        def guard(self):
            self.checks+=1
            if self.checks==2:self.late()
        def _read(self,kind):
            assert kind=='status';return raw
        def bind_input(self):pass
        def send(self,command):
            self.guard();self._before_send(deepcopy(command));self.writes.append(deepcopy(command))
            if self.lost:raise NativeUIError('Original response lost')
    lock=ScriptSourceLock(directory/'script-sources.lock')
    def source(io,clock):return PicoSnapshotCancel(io,lambda:clock[0],packet['processId'],lock,monotonic=lambda:clock[1],sleep=lambda _:None)
    io=Transport();clock=[epoch,1.0];reader=source(io,clock)
    assert reader.reconcile(request)==packet and io.writes==[]
    assert reader.reconcile(request)==packet and io.writes==[]
    cold=source(io,clock);cold.restore(packet,request,anchor=reader.original()['anchor']);assert cold.reconcile(request)==packet and io.writes==[]
    clock[1]+=2
    try:reader.reconcile(request)
    except NativeUIError:pass
    else:raise AssertionError('Old reply retimed under frozen native clock')
    try:cold.reconcile(request)
    except NativeUIError:pass
    else:raise AssertionError('Cold original host receipt replaced')
    for native,host in ((2000,0),(0,2)):
        io=Transport();clock=[epoch,1.0]
        def late():clock[0]+=native;clock[1]+=host
        io.late=late
        try:source(io,clock).reconcile(request)
        except NativeUIError:pass
        else:raise AssertionError('Late final guard accepted')
        assert io.writes==[]
    io=Transport();clock=[epoch,1.0];io.lost=True;reader=source(io,clock)
    try:reader.request(request)
    except NativeUIError:pass
    else:raise AssertionError('Lost transport response accepted')
    assert io.writes==[request]
    try:reader.request(request)
    except NativeUIError:pass
    else:raise AssertionError('Uncertain command published twice')
    assert io.writes==[request]
    io.lost=False;io.checks=0
    assert reader.reconcile(request)==packet and io.writes==[request]
    io=Transport();clock=[epoch,1.0]
    def reject(command):raise NativeUIError('Parent intent not current')
    io._before_send=reject
    try:source(io,clock).request(request)
    except NativeUIError:pass
    else:raise AssertionError('Rejected parent intent wrote')
    assert io.writes==[]


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
if not moc.is_file() and environment.get('PKG_CONFIG_SYSROOT_DIR'):
    moc=Path(environment['PKG_CONFIG_SYSROOT_DIR'])/str(moc).lstrip('/')
module=importlib.util.spec_from_file_location('snapshot_vm_host_seam',Path(__file__).with_name('test_snapshot_script_native.py'))
vm=importlib.util.module_from_spec(module);module.loader.exec_module(vm)
manager=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text()
snapshot=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
original_vm=vm.PREFIX+'thread_local QVariantMap ScriptManager::_featureNativeCallContext;\n'+''.join(body(manager,marker) for marker in (
    'QVariantMap ScriptManager::featureNativeCallContext(',
    'ScriptManager::FeatureNativeCallScope::FeatureNativeCallScope(const QVariantMap&',
    'ScriptManager::FeatureNativeCallScope::FeatureNativeCallScope(ScriptManager*',
    'ScriptManager::FeatureNativeCallScope::~FeatureNativeCallScope(',
    'QVariantMap ScriptManager::featureCaptureWorkObservation('))+''.join(body(snapshot,marker) for marker in (
    'void Snapshot::featureCaptureEvent(','QVariantMap Snapshot::featureSnapshotScriptOriginals('))
normal=r'''
#include <QChar>
#include <QBitArray>
#include "android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp"
using Original=overte::pico::e2e::NavigationUi;
void* originalNavigation() {return new Original;}
void deleteOriginalNavigation(void* value) {delete static_cast<Original*>(value);}
QJsonObject observeOriginalNavigation(void* value,QQuickItem* root,QQuickWindow* window,bool shown) {
    return static_cast<Original*>(value)->observe(root,window,shown);
}
QJsonObject applyOriginalNavigation(void* value,QQuickItem* root,QQuickWindow* window,bool shown,const QJsonObject& input,
        const std::function<bool(QQuickItem*)>& click) {return static_cast<Original*>(value)->apply(root,window,shown,input,click);}
'''
with tempfile.TemporaryDirectory(prefix='snapshot-cancel-originals-') as directory:
    stage=Path(directory);runtime=stage/'runtime';runtime.mkdir(mode=0o700)
    source=Path(__file__).with_name('snapshot-cancel-originals-test.cpp')
    tsi=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
    bridge=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp').read_text()
    (stage/'original-snapshot-cancel-tsi.inc').write_text(body(tsi,'QVariantMap TestScriptingInterface::featurePicoSnapshotCancel('))
    (stage/'original-snapshot-cancel-bridge.inc').write_text(body(bridge,'    struct SnapshotCancelRoots {').rstrip()+';\n'+''.join(body(bridge,marker) for marker in (
        '    SnapshotCancelRoots snapshotCancelRoots(',
        '    QVariantMap snapshotCancelRequest(','    void snapshotCancelTick(','    void installSnapshotCancelProvider(')))
    (stage/'original-snapshot-cancel-writer.inc').write_text(body(bridge,'bool writeJson('))
    (stage/'original-snapshot-cancel-vm.inc').write_text(original_vm);(stage/'normal.cpp').write_text(normal)
    subprocess.run([str(moc),str(source),'-o',str(stage/'snapshot-cancel-originals-test.moc')],check=True,timeout=30,env=environment)
    common=['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-I'+str(ROOT),'-I'+str(ROOT/'libraries/ui/src'),'-I'+str(stage)]
    subprocess.run([*(flag for flag in common if flag!='-Wextra'),'-c',str(stage/'normal.cpp'),'-o',str(stage/'normal.o'),*flags],check=True,timeout=60,env=environment)
    subprocess.run([*common,'-c',str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(stage/'field.o'),*flags],check=True,timeout=60,env=environment)
    # Compile the unchanged getter's non-Pico arm too. It has no UI/provider
    # dependency and must remain unavailable even with the runtime switch.
    other=stage/'other.cpp'
    other.write_text('#include <QCoreApplication>\n#include <QVariantMap>\n#include <cassert>\n'
        'class TestScriptingInterface {public:QVariantMap featurePicoSnapshotCancel(const QVariantMap&);};\n'
        +body(tsi,'QVariantMap TestScriptingInterface::featurePicoSnapshotCancel(')
        +'int main(int argc,char** argv){QCoreApplication app(argc,argv);TestScriptingInterface source;assert(source.featurePicoSnapshotCancel({}).isEmpty());}\n')
    subprocess.run([*common,'-DOVERTE_E2E_FEATURE_TESTS',str(other),'-o',str(stage/'other'),*library,*flags],check=True,timeout=60,env=environment)
    subprocess.run([str(stage/'other'),'--testScript'],check=True,timeout=10,env=environment)
    executable=stage/'test'
    subprocess.run([*common,'-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',str(source),str(stage/'normal.o'),str(stage/'field.o'),'-o',str(executable),*library,*flags],
        check=True,timeout=60,env=environment)
    environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',XDG_RUNTIME_DIR=str(runtime))
    for mode in ('complete','ack-only','generation','native-started','upload','stale','unowned-name','wrong-mode'):
        options=[str(executable),str(ROOT/'scripts/system/snapshot/NativeSnapshotReview.qml'),str(ROOT),mode,'--testScript']
        raw=subprocess.check_output(['unshare','--user','--map-root-user','--net',*options],text=True,timeout=20,env=environment)
        output=json.loads(raw);packet=output['packet'];value=packet['source']
        validate(packet,output['command'],packet['processId'],packet['capturedEpochMs'])
        for key in ('before','pending','cancelled','retirement','current'):
            if value[key]:original(value[key],value['observedEpochMs'])
        if mode=='complete':
            assert value['phase']=='complete' and value['retired'] and not value['timerActive']
            assert len(value['pending']['script']['history']['events'])==1 and len(value['cancelled']['script']['history']['events'])==2
            reader_boundaries(output,stage)
            faults=(lambda row:row['before']['review'].update(snapshotReviewObservationVersion=1),
                lambda row:row['before']['review']['review'].update(captureName='foreign-name'),
                lambda row:row['before']['review']['review'].update(mode=0),
                lambda row:row['before']['script'].update(activeUploads=1),
                lambda row:row['cancelled']['script']['history']['events'].pop(),
                lambda row:row.update(timerActive=True),lambda row:row['captureInput'].update(performed=False),
                lambda row:row['cancelCommand'].update(sequence=row['captureCommand']['sequence']))
            for fault in faults:
                broken=deepcopy(packet);fault(broken['source'])
                try:validate(broken,output['command'],packet['processId'],packet['capturedEpochMs'])
                except (NativeUIError,ValueError,RuntimeError):pass
                else:raise AssertionError('Changed original accepted')
    subprocess.run(['unshare','--user','--map-root-user','--net',str(executable),
        str(ROOT/'scripts/system/snapshot/NativeSnapshotReview.qml'),str(ROOT),'complete'],check=True,timeout=20,env=environment)
print('PASS: original FastCancel + actual full normal Pico UI/QML/Qt timer recipe; explicit VM/VR service seams (Qt'+major+')')
