"""Real Snapshot QML/Qt controls with explicit script/OS producer seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from copy import deepcopy
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_snapshot_controls import validate
from overte_phone_snapshot_cancel import validate as validate_cancel


class SnapshotNativeControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-normal-controls-contract';parent.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='qt6-',dir=parent);cls.addClassCleanup(temporary.cleanup)
        cls.stage=Path(temporary.name);production=cls.stage/'system/snapshot';production.mkdir(parents=True)
        for name in ('NativeSnapshotReview.qml','SnapshotPlatform.qml'):
            shutil.copyfile(ROOT/'scripts/system/snapshot'/name,production/name)
        controls=cls.stage/'controls';controls.mkdir()
        shutil.copyfile(ROOT/'interface/resources/qml/controls/+android/SnapshotPlatformBackend.qml',controls/'SnapshotPlatformBackend.qml')
        (controls/'qmldir').write_text('module controls\nSnapshotPlatformBackend 1.0 SnapshotPlatformBackend.qml\n')
        original=ROOT/'android/phone/tests/device/snapshot-controls-runtime.cpp'
        binding=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        actual=binding[binding.index('QVariantMap TestScriptingInterface::phoneSnapshotCancel('):binding.index('QVariantMap TestScriptingInterface::phoneCreateFiles(')]
        # Only DependencyManager/OffscreenUi/lifecycle/source producers are
        # explicit seams. The complete original Test method runs unchanged.
        seams=r'''
#include <QSharedPointer>
class Snapshot : public QObject {
public:std::function<QVariantMap()> read;
    QVariantMap featureSnapshotObservation() { return read ? read() : QVariantMap{}; }
};
class OffscreenUi : public QObject {
public:QQuickItem* root{nullptr};QQuickWindow* window{nullptr};
    QQuickItem* getRootItem() { return root; }QQuickWindow* getWindow() { return window; }
};
struct SnapshotTestDependencies {
    template<class T> static QSharedPointer<T>& service() { static QSharedPointer<T> object;return object; }
    template<class T> static bool isSet() { return !service<T>().isNull(); }
    template<class T> static QSharedPointer<T> get() { return service<T>(); }
};
class TestScriptingInterface : public QObject {
public:
    struct Lifecycle { QVariantMap snapshot() { return {{"present",true}}; } };
    QString _testResultsLocation{"private-test-only"},_featureObservationInstance{QString(32,'f')};
    std::shared_ptr<Lifecycle> _featureLifecycle=std::make_shared<Lifecycle>();
    quint64 _phoneSnapshotCancelSequence{0};
    std::shared_ptr<overte::e2e::SnapshotUi> _phoneSnapshotUi;
    QMap<QString,std::shared_ptr<overte::e2e::PhoneSnapshotFastCancel>> _phoneSnapshotCancelJobs;
    QVariantMap phoneSnapshotCancel(const QVariantMap& command);
};
'''
        cpp=cls.stage/'snapshot-controls-runtime.cpp'
        cpp.write_text(original.read_text().replace('// ORIGINAL_TEST_BINDING',seams+'\n#define DependencyManager SnapshotTestDependencies\n'+actual+'\n#undef DependencyManager\n'))
        subprocess.run(['/usr/lib64/qt6/libexec/moc',str(cpp),'-o',str(cls.stage/'snapshot-controls-runtime.moc')],check=True,timeout=30)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Quick','Qt6Qml','Qt6Gui','Qt6Core','Qt6Test','Qt6Network'],text=True))
        cls.executable=cls.stage/'check'
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
            '-DOVERTE_SOURCE_ROOT="'+str(ROOT)+'"',
            '-I'+str(ROOT),'-I'+str(cls.stage),'-I'+str(ROOT/'libraries/shared/src'),'-I'+str(ROOT/'libraries/ui/src'),
            str(cpp),str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(cls.executable),*flags],check=True,timeout=120)

    def run_case(self,mode):
        raw=subprocess.check_output([str(self.executable),str(self.stage),mode,'--testScript'],text=True,timeout=15,
            env=os.environ|{'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software','XDG_CONFIG_HOME':str(self.stage/'config')})
        lines=raw.splitlines();original=json.loads(lines[0]);original.update(commandId='a'*32,action='observe')
        validate(original,'a'*32,original['processId'],original['capturedEpochMs'])
        if mode=='fast-normal':
            state=json.loads(next(line[5:] for line in lines if line.startswith('FAST:')))
            epoch=state['observedEpochMs'];request=dict(schemaVersion=1,commandId='d'*32,action='phone-snapshot-cancel',
                runId=state['runId'],jobId=state['job'],operation='observe',request={})
            packet=dict(schemaVersion=1,requestId=request['commandId'],runId=state['runId'],instance='f'*32,sequence=1,
                processId=original['processId'],requestedEpochMs=epoch,capturedEpochMs=epoch,source=state,
                jobs=[{key:state[key] for key in ('job','runId','instance','phase','timerActive','retired')}])
            # Only the transport envelope is synthetic. All helper, QML,
            # physical input, clock and timer originals below are unchanged.
            validate_cancel(packet,request,original['processId'],epoch)
            actual=json.loads(next(line[8:] for line in lines if line.startswith('BINDING:')))
            observed=dict(request,commandId=actual['requestId'],operation='retire')
            validate_cancel(actual,observed,original['processId'],actual['capturedEpochMs'])
            for fault in ('stale','foreign','missing','ignored','timer','native','inventory','unfinished'):
                changed=deepcopy(packet)
                if fault=='stale':changed['source']['pending']['capturedEpochMs']=1
                elif fault=='foreign':changed['source']['cancelled']['native']['scriptHistory']['events'][-1]['id']='snap_1_999'
                elif fault=='missing':changed['source']['pending']={}
                elif fault=='ignored':changed['source']['cancelInput']['performed']=False
                elif fault=='timer':changed['source']['pending']['native']['scriptHistory']['events'][-1]['caller']['snapshotWork']['timers'][0]['intervalMs']=999
                elif fault=='native':changed['source']['cancelled']['native']['history']['sequence']=1
                elif fault=='inventory':changed['jobs']=[]
                else:changed['source']['timerActive']=True
                with self.subTest(original_fault=fault),self.assertRaises((RuntimeError,ValueError,KeyError)):
                    validate_cancel(changed,request,original['processId'],epoch)

    def test_actual_name_mode_format_capture_cancel_and_exact_image_export_inputs(self):self.run_case('normal')
    def test_unknown_token_consumes_intent_and_cannot_be_replayed(self):self.run_case('stale')
    def test_foreign_and_duplicate_original_components_never_qualify_controls(self):self.run_case('foreign')
    def test_actual_foreign_overlay_blocks_input(self):self.run_case('obstruction')
    def test_fast_cancel_uses_actual_pending_timers_and_normal_qt_cancel_input(self):self.run_case('fast-normal')
    def test_fast_cancel_ignored_capture_does_not_become_idle_cancel_success(self):self.run_case('fast-ignored')
    def test_fast_cancel_ignored_cancel_retains_actual_late_native_work_as_failure(self):self.run_case('fast-ignore-cancel')
    def test_fast_cancel_stale_pending_original_cannot_authorize_cancellation(self):self.run_case('fast-stale')
    def test_fast_cancel_foreign_completion_cannot_borrow_the_owned_pending_context(self):self.run_case('fast-foreign')
    def test_fast_cancel_native_history_replacement_cannot_hide_render_submission(self):self.run_case('fast-native-replacement')
    def test_fast_cancel_retirement_never_clears_or_masks_late_product_work(self):self.run_case('fast-late-work')


if __name__=='__main__':unittest.main()
