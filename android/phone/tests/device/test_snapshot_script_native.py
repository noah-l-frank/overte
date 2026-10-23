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
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_snapshot_script_history import validate

PREFIX=r'''
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonDocument>
#include <QThread>
#include <QTimer>
#include <QMap>
#include <QVariantMap>
#include <memory>
#include <map>
#include <cstdio>
#include "tests/device/native/PhoneSnapshotScriptHistory.h"
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
class Snapshot {
public:
    std::shared_ptr<overte::e2e::PhoneSnapshotScriptHistory> _featureSnapshotScriptHistory=
        std::make_shared<overte::e2e::PhoneSnapshotScriptHistory>();
    void featureCaptureEvent(const QString& kind,const QString& id,const QString& mode,int revision);
};
'''
SUFFIX=r'''
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);const auto mode=QString::fromLocal8Bit(argv[1]);
    ScriptManager manager;Snapshot snapshot;
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
        return snapshot._featureSnapshotScriptHistory->snapshot().isEmpty() ? 0 : 1;
    }
    const auto initial=snapshot._featureSnapshotScriptHistory->snapshot();
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
        return snapshot._featureSnapshotScriptHistory->snapshot().value("complete")==false ? 0 : 3;
    }
    if(mode=="overflow") {
        for(int index=1;index<=257;++index) {
            ScriptManager::FeatureNativeCallScope scope(&manager,"featureCaptureEvent",2);
            snapshot.featureCaptureEvent("pending","snap_100_"+QString::number(index),"animated",index);
        }
        const auto result=snapshot._featureSnapshotScriptHistory->snapshot();
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
    auto result=snapshot._featureSnapshotScriptHistory->snapshot();
    if(result.value("complete")!=true || result.value("sequence")!=5 || result.value("instance")!=initial.value("instance")) { return 9; }
    auto rows=result.value("events").toList();auto altered=rows[0].toMap();altered["kind"]="complete";rows[0]=altered;
    if(snapshot._featureSnapshotScriptHistory->snapshot().value("events").toList()==rows) { return 10; }
    std::puts(QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).constData());
}
'''


class SnapshotScriptNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-script-native-contract';parent.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='original-',dir=parent);cls.addClassCleanup(temporary.cleanup)
        stage=Path(temporary.name);cls.executable=stage/'check'
        manager=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        actual_scope=manager[manager.index('thread_local QVariantMap ScriptManager::_featureNativeCallContext;'):manager.index('void ScriptManager::featureCallbackBoundary(')]
        snapshot=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
        start=snapshot.index('void Snapshot::featureCaptureEvent(')
        actual_bridge=snapshot[start:snapshot.index('\n}',start)+2]
        source=stage/'original.cpp';source.write_text(PREFIX+actual_scope+actual_bridge+SUFFIX)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
            '-I'+str(ROOT),str(source),'-o',str(cls.executable),*flags],check=True,timeout=60)

    def run_case(self,mode,enabled=True):
        return subprocess.check_output([str(self.executable),mode,*(['--testScript'] if enabled else [])],text=True,timeout=5)

    def test_original_scope_lookup_bridge_recorder_and_python_contract_agree(self):
        value=json.loads(self.run_case('events'));validate(value,max(row['capturedEpochMs'] for row in value['events']))
        self.assertEqual(['pending','cancelled','pending','processing','complete'],[row['kind'] for row in value['events']])
        self.assertTrue(all(row['caller']['compilation']['scriptId']==2 for row in value['events']))

    def test_disabled_source_has_no_recording_or_observation(self):self.run_case('disabled',False)

    def test_missing_unknown_wrong_thread_or_uncompiled_caller_stays_permanently_incomplete(self):
        for mode in ('no-scope','unknown','wrong-thread','uncompiled','disabled-manager'):
            with self.subTest(mode=mode):self.run_case(mode)

    def test_overflow_retains_original_prefix_and_is_permanently_incomplete(self):self.run_case('overflow')

    def test_actual_qt_timer_inventory_observes_registration_and_cancellation_without_touching_foreign_timers(self):self.run_case('timer-work')


class ScriptSubmissionNativeTests(unittest.TestCase):
    """Actual submission block/recorder; engine syntax/evaluation is a seam, not V8."""
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/script-submission-native-contract';parent.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='original-',dir=parent);cls.addClassCleanup(temporary.cleanup)
        stage=Path(temporary.name)
        manager=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        start=manager.index('    {\n        PROFILE_RANGE(script, _fileNameString);')
        original=manager[start:manager.index('\n#ifdef _WIN32',start)]
        prefix=r'''
#include <QCoreApplication>
#include <QDateTime>
#include <QDebug>
#include <QJsonDocument>
#include <QThread>
#include <memory>
#include <cstdio>
#include "libraries/script-engine/src/RequiredModuleObservation.h"
#define PROFILE_RANGE(category,name) ((void)0)
#define qCWarning(category) qWarning()
enum class ScriptSyntaxCheckResult { Valid, Error };
struct Syntax {
    bool valid; ScriptSyntaxCheckResult state() const {
        return valid ? ScriptSyntaxCheckResult::Valid : ScriptSyntaxCheckResult::Error;
    }
};
struct Engine;
struct Program { Engine* engine; std::shared_ptr<Syntax> checkSyntax(); };
struct Engine {
    overte::e2e::RequiredModuleObservation* records;
    QString source,mode; int checks{0},evaluations{0};
    std::shared_ptr<Program> newProgram(const QString& code,const QString&) {
        source=code; return std::make_shared<Program>(Program{this});
    }
    int evaluate(const std::shared_ptr<Program>&) { return ++evaluations; }
    int evaluate(const QString& code,const QString&) {
        source=code;
#if defined(OVERTE_E2E_FEATURE_TESTS)
        records->compiled(17,QStringLiteral("owned.js"),source);
#endif
        return ++evaluations;
    }
    bool hasUncaughtException() const { return mode=="exception"; }
};
std::shared_ptr<Syntax> Program::checkSyntax() {
    ++engine->checks; const bool valid=engine->mode!="invalid";
#if defined(OVERTE_E2E_FEATURE_TESTS)
    if(valid) engine->records->compiled(17,QStringLiteral("owned.js"),engine->source);
#endif
    // Make an erroneous later submission observably later than compilation.
    QThread::msleep(4); return std::make_shared<Syntax>(Syntax{valid});
}
struct Manager {
    overte::e2e::RequiredModuleObservation _e2eRequiredModules;
    QString _scriptContents=QString::fromUtf8("var actual = 'Ω 東京';\n");
    QString _fileNameString=QStringLiteral("owned.js"),mode;
    std::unique_ptr<Engine> _engine;
    int _returnValue{0},errors{0},stops{0}; bool _abortOnUncaughtException{false};
    Manager(const QString& value):mode(value),_engine(new Engine{&_e2eRequiredModules,{},value}) {}
    bool isUserLoaded() const { return mode!="builtin"; }
    QString getFilename() const { return _fileNameString; }
    void errorLoadingScript(const QString&) { ++errors; }
    void stop() { ++stops; }
    void runInitial() {
'''
        suffix=r'''
    }
};
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv); Manager manager(QString::fromLocal8Bit(argv[1]));
    manager.runInitial();
    QVariantMap result{{"code",manager._e2eRequiredModules.sourceIdentity()},
        {"compiled",manager._e2eRequiredModules.compiledSources()},
        {"checks",manager._engine->checks},{"evaluations",manager._engine->evaluations},
        {"errors",manager.errors},{"stops",manager.stops}};
    std::puts(QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).constData());
}
'''
        source=stage/'original.cpp';source.write_text(prefix+original+suffix)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True))
        cls.executables={}
        for enabled in (True,False):
            executable=stage/('enabled' if enabled else 'disabled')
            subprocess.run(['c++','-std=c++17','-fPIC',*(['-DOVERTE_E2E_FEATURE_TESTS'] if enabled else []),
                '-I'+str(ROOT),str(source),'-o',str(executable),*flags],check=True,timeout=60)
            cls.executables[enabled]=executable
        # Reproduce the former integration error using the same source block,
        # recorder, compiler boundary and real clocks; no timestamp is rewritten.
        submission='        _e2eRequiredModules.submitted(_scriptContents);\n'
        if original.count(submission)!=1:
            raise AssertionError('Expected one original source submission')
        late=original.replace(submission,'').replace(
            '                _returnValue = _engine->evaluate(program);',
            submission+'                _returnValue = _engine->evaluate(program);',1)
        source.write_text(prefix+late+suffix)
        cls.late_executable=stage/'late-submission'
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS',
            '-I'+str(ROOT),str(source),'-o',str(cls.late_executable),*flags],check=True,timeout=60)

    def assert_submission_order(self,value):
        self.assertGreaterEqual(value['compiled']['compilations'][0]['compiledEpochMs'],
            value['code']['submittedEpochMs'])

    def test_actual_submission_precedes_user_syntax_compilation_and_builtin_evaluation(self):
        for enabled in (True,False):
            for mode in ('user','invalid','exception','builtin'):
                with self.subTest(enabled=enabled,mode=mode):
                    value=json.loads(subprocess.check_output([str(self.executables[enabled]),mode,'--testScript'],
                        text=True,timeout=5))
                    self.assertEqual(int(mode!='builtin'),value['checks'])
                    self.assertEqual(int(mode!='invalid'),value['evaluations'])
                    self.assertEqual(int(mode in ('invalid','exception')),value['errors'])
                    self.assertEqual(value['errors'],value['stops'])
                    code=value['code'];rows=value['compiled']['compilations']
                    self.assertEqual(enabled,code['submitted'])
                    if not enabled:
                        self.assertEqual(0,code['submittedEpochMs']);self.assertEqual([],rows)
                        continue
                    raw="var actual = 'Ω 東京';\n".encode('utf-16-le')
                    self.assertEqual(len(raw)//2,code['codeUnits'])
                    import hashlib
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),code['sha256'])
                    self.assertGreater(code['submittedEpochMs'],0)
                    self.assertEqual(int(mode!='invalid'),len(rows))
                    if rows:
                        self.assert_submission_order(value)
                        self.assertEqual(code['sha256'],rows[0]['sha256'])
        late=json.loads(subprocess.check_output([str(self.late_executable),'user','--testScript'],
            text=True,timeout=5))
        self.assertEqual(1,late['checks']);self.assertEqual(1,late['evaluations'])
        with self.assertRaises(AssertionError):self.assert_submission_order(late)


if __name__=='__main__':unittest.main()
