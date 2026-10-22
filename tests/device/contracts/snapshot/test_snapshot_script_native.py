"""Compile real recorder/bridge and caller scope with explicit VM manager seam.

Uses real Qt clocks, maps and thread identity. This does not compile V8, the
complete Snapshot translation unit, an Android APK or execute a device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.snapshot_script_history import validate

PREFIX=r'''
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonDocument>
#include <QThread>
#include <QTimer>
#include <QMap>
#include <QSet>
#include <QHash>
#include <QPointer>
#include <QVariantMap>
#include <memory>
#include <map>
#include <cstdio>
#include "tests/device/native/SnapshotScriptHistory.h"
// Only manager-owned VM/source seams are synthetic. The scope and bridge
// function bodies below are extracted unchanged from the actual client.
class ScriptManager {
public:
    class FeatureNativeCallScope {
    public:
        FeatureNativeCallScope(const QVariantMap& original);
        FeatureNativeCallScope(ScriptManager* manager,const QByteArray& method,int originalScriptId);
        ~FeatureNativeCallScope();
    private:QVariantMap _previous;
    };
    static thread_local QVariantMap _featureNativeCallContext;
    static QVariantMap featureNativeCallContext();
    QVariantMap featureCaptureWorkObservation(int originalScriptId) const;
    bool _featureWorkEnabled{true},wrongThread{false};qulonglong _featureNativeCallSequence{0};
    bool _featureWorkValid{true};
    struct Activity {quint64 signalCallbacks{0},timerCallbacks{0},signalInvocations{0},timerInvocations{0},timerRegistrations{0};};
    QMap<int,Activity> _featureWorkActivity{{2,Activity{}}};
    struct CallbackData {int featureFunctionScriptId;};
    std::map<int,std::pair<std::unique_ptr<QTimer>,CallbackData>> _timerFunctionMap;
    QThread* thread() const { return wrongThread ? nullptr : QThread::currentThread(); }
    QVariantMap featureLoadMembership() { return {{"instance",QString(32,'a')},{"assigned",true},
        {"url","file:///packaged/scripts/defaultScripts.js"},{"loadGeneration",1},{"assignedEpochMs",1}}; }
    QVariantMap featureSourceIdentity() { return {{"submitted",true},{"encoding","utf-16le-code-units"},
        {"codeUnits",20},{"sha256",QString(64,'b')},{"submittedEpochMs",2}}; }
    struct Required {
        QVariantMap compilation(int id) { return id!=2 ? QVariantMap{} : QVariantMap{{"scriptId",2},
            {"resourceName","file:///packaged/scripts/system/snapshot.js"},{"encoding","utf-16le-code-units"},
            {"codeUnits",40},{"sha256",QString(64,'c')},{"compiledEpochMs",3}}; }
    } _e2eRequiredModules;
};
class Snapshot : public QObject {
public:
    overte::e2e::SnapshotScriptHistory _featureCaptureScriptHistory;
    QHash<QString,QPointer<QObject>> _uploads;
    QSet<QString> _featureCaptureScriptQueries;QString _featureCaptureScriptRun;quint64 _featureCaptureScriptSequence{0};
    bool nativeReviewEnabled() const {return true;}
    QVariantMap featureSnapshotScriptOriginals(const QVariantMap& command);
    void featureCaptureEvent(const QString& kind,const QString& id,const QString& mode,int revision);
};
'''
SUFFIX=r'''
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);const auto mode=QString::fromLocal8Bit(argv[1]);
    ScriptManager manager;Snapshot snapshot;
    if(mode=="query") {
        QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'a')},{"runId",QString(32,'b')}};
        const auto first=snapshot.featureSnapshotScriptOriginals(command);
        if(first.value("snapshotScriptOriginalsVersion")!=2 || first.value("activeUploads")!=0 || first.value("sequence")!=1
                || first.value("pid").toLongLong()!=app.applicationPid() || first.value("history").toMap().value("sequence")!=0
                || !snapshot.featureSnapshotScriptOriginals(command).isEmpty()) {return 14;}
        command["commandId"]=QString(32,'c');command["runId"]=QString(32,'d');
        if(!snapshot.featureSnapshotScriptOriginals(command).isEmpty()) {return 15;}
        command["runId"]=QString(32,'b');command["expectedPending"]=true;
        if(!snapshot.featureSnapshotScriptOriginals(command).isEmpty()) {return 16;}
        command.remove("expectedPending");snapshot._uploads.insert("original-retained-map-entry",nullptr);
        const auto next=snapshot.featureSnapshotScriptOriginals(command);
        return next.value("sequence")==2 && next.value("activeUploads")==1 && next.value("history")==first.value("history") ? 0 : 17;
    }
    if(mode=="timer-work") {
        for(int index=1;index<=3;++index) {
            auto timer=std::make_unique<QTimer>();timer->setSingleShot(true);timer->start(index==1 ? 350 : 60000);
            manager._timerFunctionMap.emplace(index,std::make_pair(std::move(timer),ScriptManager::CallbackData{index==3 ? 3 : 2}));
        }
        manager._featureWorkActivity[2].timerRegistrations=2;
        const auto pending=manager.featureCaptureWorkObservation(2);const auto timers=pending.value("timers").toList();
        if(timers.size()!=2 || timers[0].toMap().value("intervalMs")!=350 || timers[1].toMap().value("intervalMs")!=60000
            || !timers[0].toMap().value("active").toBool() || timers[0].toMap().value("remainingMs").toInt()<0) { return 11; }
        manager._timerFunctionMap.erase(1);manager._timerFunctionMap.erase(2);
        const auto cancelled=manager.featureCaptureWorkObservation(2);
        if(!cancelled.value("timers").toList().isEmpty() || manager._timerFunctionMap.size()!=1
            || cancelled.value("timerRegistrations")!=2 || !manager.featureCaptureWorkObservation(0).isEmpty()) { return 12; }
        manager._featureWorkValid=false;
        return manager.featureCaptureWorkObservation(2).isEmpty() ? 0 : 13;
    }
    if(mode=="disabled") {
        snapshot.featureCaptureEvent("pending","snap_100_1","animated",1);
        return snapshot._featureCaptureScriptHistory.snapshot().isEmpty() ? 0 : 1;
    }
    const auto initial=snapshot._featureCaptureScriptHistory.snapshot();
    if(initial.value("complete")!=true || initial.value("sequence")!=0) { return 2; }
    if(mode=="no-scope" || mode=="unknown" || mode=="wrong-thread" || mode=="uncompiled" || mode=="disabled-manager") {
        manager.wrongThread=mode=="wrong-thread";manager._featureWorkEnabled=mode!="disabled-manager";
        if(mode=="no-scope")snapshot.featureCaptureEvent("pending","snap_100_1","animated",1);
        else {
            ScriptManager::FeatureNativeCallScope scope(&manager,mode=="unknown" ? "inventedMethod" : "featureCaptureEvent",mode=="uncompiled" ? 0 : 2);
            snapshot.featureCaptureEvent("pending","snap_100_1","animated",1);
        }
        // An invalid observer event permanently prevents empty-success reuse.
        { ScriptManager::FeatureNativeCallScope scope(&manager,"featureCaptureEvent",2);
          snapshot.featureCaptureEvent("pending","snap_100_2","animated",2); }
        return snapshot._featureCaptureScriptHistory.snapshot().value("complete")==false ? 0 : 3;
    }
    if(mode=="overflow") {
        for(int index=1;index<=257;++index) {
            ScriptManager::FeatureNativeCallScope scope(&manager,"featureCaptureEvent",2);
            snapshot.featureCaptureEvent("pending","snap_100_"+QString::number(index),"animated",index);
        }
        const auto result=snapshot._featureCaptureScriptHistory.snapshot();
        return result.value("complete")==false && result.value("events").toList().size()==256 ? 0 : 4;
    }
    const QStringList phases{"pending","cancelled","pending","processing","complete"};
    for(int index=0;index<phases.size();++index) {
        if(!ScriptManager::featureNativeCallContext().isEmpty()) { return 5; }
        { ScriptManager::FeatureNativeCallScope scope(&manager,"featureCaptureEvent",2);
          const auto context=ScriptManager::featureNativeCallContext();
          { ScriptManager::FeatureNativeCallScope nested(&manager,"overrideAnimation",2);
            if(ScriptManager::featureNativeCallContext().value("method")!="overrideAnimation") { return 6; } }
          if(ScriptManager::featureNativeCallContext()!=context) { return 7; }
          snapshot.featureCaptureEvent(phases[index],index<2 ? "snap_100_1" : "snap_100_2","animated",index<2 ? 1 : 2); }
    }
    if(!ScriptManager::featureNativeCallContext().isEmpty()) { return 8; }
    auto result=snapshot._featureCaptureScriptHistory.snapshot();
    if(result.value("complete")!=true || result.value("sequence")!=5 || result.value("instance")!=initial.value("instance")) { return 9; }
    auto rows=result.value("events").toList();auto altered=rows[0].toMap();altered["kind"]="complete";rows[0]=altered;
    if(snapshot._featureCaptureScriptHistory.snapshot().value("events").toList()==rows) { return 10; }
    std::puts(QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).constData());
}
'''


class SnapshotScriptNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-script-original-');cls.addClassCleanup(temporary.cleanup)
        stage=Path(temporary.name);cls.executable=stage/'check'
        manager=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        def body(text,marker):
            start=text.index(marker);opening=text.index('{',start);depth=1;end=opening+1
            while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
            return text[start:end]+'\n'
        actual_scope='thread_local QVariantMap ScriptManager::_featureNativeCallContext;\n'+''.join(body(manager,marker) for marker in (
            'QVariantMap ScriptManager::featureNativeCallContext(',
            'ScriptManager::FeatureNativeCallScope::FeatureNativeCallScope(const QVariantMap&',
            'ScriptManager::FeatureNativeCallScope::FeatureNativeCallScope(ScriptManager*',
            'ScriptManager::FeatureNativeCallScope::~FeatureNativeCallScope(',
            'QVariantMap ScriptManager::featureCaptureWorkObservation('))
        snapshot=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
        actual_bridge=''.join(body(snapshot,marker) for marker in ('void Snapshot::featureCaptureEvent(',
            'QVariantMap Snapshot::featureSnapshotScriptOriginals('))
        source=stage/'original.cpp';source.write_text(PREFIX+actual_scope+actual_bridge+SUFFIX)
        import os
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');library=[]
        if major not in ('5','6'):raise ValueError('Unsupported Qt major')
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
                LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            library=['-L'+str(prefix/'usr/lib64')]
        cls.environment=environment
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS',
            '-I'+str(ROOT),str(source),'-o',str(cls.executable),*library,*flags],check=True,timeout=60,env=environment)

    def run_case(self,mode,enabled=True):
        return subprocess.check_output([str(self.executable),mode,*(['--testScript'] if enabled else [])],text=True,timeout=5,env=self.environment)

    def test_original_scope_lookup_bridge_recorder_and_python_contract_agree(self):
        value=json.loads(self.run_case('events'));validate(value,max(row['capturedEpochMs'] for row in value['events']))
        self.assertEqual(['pending','cancelled','pending','processing','complete'],[row['kind'] for row in value['events']])
        self.assertTrue(all(row['caller']['compilation']['scriptId']==2 for row in value['events']))

    def test_actual_source_query_has_fixed_run_bounded_closed_commands_and_no_reset(self):self.run_case('query')

    def test_disabled_source_has_no_recording_or_observation(self):self.run_case('disabled',False)

    def test_missing_unknown_wrong_thread_or_uncompiled_caller_stays_permanently_incomplete(self):
        for mode in ('no-scope','unknown','wrong-thread','uncompiled','disabled-manager'):
            with self.subTest(mode=mode):self.run_case(mode)

    def test_overflow_retains_original_prefix_and_is_permanently_incomplete(self):self.run_case('overflow')

    def test_actual_qt_timer_inventory_observes_registration_and_cancellation_without_touching_foreign_timers(self):self.run_case('timer-work')


if __name__=='__main__':unittest.main()
