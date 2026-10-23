"""Actual raw-read/Handle/Snapshot bodies; no global writer or device.

Manager storage/DI, ordinary Handle initialization/write delivery and product UI
are explicit seams. The whole actual Handle header, protected initialization
flag, raw read lock/body, typed serializer and Snapshot bridge are compiled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('snapshot_context_fixture',Path(__file__).with_name('test_snapshot_context_native.py'))
context=importlib.util.module_from_spec(spec);spec.loader.exec_module(context)
PREFIX=r'''
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QSemaphore>
#include <QThread>
#include <QUuid>
#include <QHash>
#include <thread>
#include <cstdio>
#include "libraries/shared/src/SettingHandle.h"
#include "libraries/shared/src/shared/ReadWriteLockable.h"
#include "tests/device/native/SnapshotSettingsOriginals.h"
#include "tests/device/native/AudioSettingsQueue.h"
#include "tests/device/native/PrivatePreviewFiles.h"
Q_LOGGING_CATEGORY(settings_handle,"host.snapshot.handle")
namespace Setting {
int initializations=0,writes=0;
// Explicit storage/writer seams. Any lazy initialization is observable here.
void Interface::init() { ++initializations;_isInitialized=true; }
void Interface::maybeInit() const { if(!_isInitialized)const_cast<Interface*>(this)->init(); }
void Interface::deinit() {}
void Interface::save() { ++writes; }
void Interface::load() {}
class Manager : public ReadWriteLockable {
public:
    QHash<QString,QVariant> _settings;
    MANAGER_BIRTH
    QVariantMap featureSnapshotSettingsEntries() const;
};
}
class Snapshot;
class DependencyManager {
public:
    static QSharedPointer<Setting::Manager> original;static QSharedPointer<Snapshot> client;static int reads;
    template<class T> static bool isSet() { if constexpr(std::is_same<T,Setting::Manager>::value)return !original.isNull();else return !client.isNull(); }
    template<class T> static QSharedPointer<T> get() { ++reads;if constexpr(std::is_same<T,Setting::Manager>::value)return original;else return client; }
};
QSharedPointer<Setting::Manager> DependencyManager::original;
QSharedPointer<Snapshot> DependencyManager::client;
int DependencyManager::reads=0;
class Snapshot : public QObject {
public:
    Setting::Handle<QString> _snapshotFormat{"snapshotFormat"};
    SNAPSHOT_BIRTH
    QSet<QString> _featureSettingsQueries;QString _featureSettingsRun;quint64 _featureSettingsSequence{0};
    bool nativeReviewEnabled() const { return true; }
    QVariantMap featureSnapshotSettingsOriginals(const QVariantMap& command);
};
struct HmdGate { bool isHMDMode() const {return true;} } hmdGate;
HmdGate* activeHmdGate=&hmdGate;
#undef qApp
#define qApp activeHmdGate
struct LifecycleGate {QVariantMap snapshot() const {return {{"original",true}};}};
class TestScriptingInterface : public QObject {
public:
    QString _testResultsLocation{QCoreApplication::applicationDirPath()};
    std::shared_ptr<LifecycleGate> _featureLifecycle{std::make_shared<LifecycleGate>()};
    std::shared_ptr<overte::e2e::AudioSettingsQueue> _featureSnapshotQueue{std::make_shared<overte::e2e::AudioSettingsQueue>()};
    QVariantMap featureSnapshotSettingsOriginals(const QVariantMap& command);
};
'''
MAIN=r'''
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);const QString mode=QString::fromLocal8Bit(argv[1]);
    auto settings=QSharedPointer<Setting::Manager>::create();DependencyManager::original=settings;
    settings->_settings={{"alsoTakeAnimatedSnapshot",true},{"previousSnapshotHref","hifi://original/place"}};
    Snapshot snapshot;QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'a')},{"runId",QString(32,'b')}};
    const auto before=settings->_settings;
    if(mode=="tsi") {
        auto original=QSharedPointer<Snapshot>::create();DependencyManager::client=original;TestScriptingInterface observer;
        auto input=command;input.insert("action","feature-pico-snapshot-settings-originals");const auto value=observer.featureSnapshotSettingsOriginals(input);
        if(value.value("snapshotSettingsOriginalsVersion")!=1 || value.value("source").toMap().value("snapshotInstance")!=original->_featureSettingsInstance
            || Setting::initializations!=0 || Setting::writes!=0 || settings->_settings!=before)return 11;
        input["commandId"]=QString(32,'c');input["action"]="foreign";
        return observer.featureSnapshotSettingsOriginals(input).isEmpty() && original->_featureSettingsQueries.size()==1 ? 0 : 12;
    }
    if(mode=="disabled") {
        return snapshot._snapshotFormat.featureSnapshotFormatState().isEmpty() && settings->featureSnapshotSettingsEntries().isEmpty()
            && snapshot.featureSnapshotSettingsOriginals(command).isEmpty() && Setting::initializations==0 && Setting::writes==0 && settings->_settings==before ? 0 : 1;
    }
    if(mode=="missing") {
        DependencyManager::original.clear();const auto absent=snapshot.featureSnapshotSettingsOriginals(command);
        DependencyManager::original=settings;
        return absent.isEmpty() && DependencyManager::reads==0 && snapshot.featureSnapshotSettingsOriginals(command).isEmpty() ? 0 : 2;
    }
    if(mode=="wrong-thread") {
        QVariantMap unavailable;std::thread worker([&]{unavailable=snapshot.featureSnapshotSettingsOriginals(command);});worker.join();
        return unavailable.isEmpty() && snapshot._featureSettingsQueries.isEmpty() && Setting::initializations==0 && settings->_settings==before ? 0 : 3;
    }
    if(mode=="blocked") {
        QSemaphore entered,release;std::thread worker([&]{QWriteLocker lock(&settings->getLock());entered.release();release.acquire();});entered.acquire();
        QElapsedTimer elapsed;elapsed.start();const auto unavailable=snapshot.featureSnapshotSettingsOriginals(command);const auto duration=elapsed.elapsed();release.release();worker.join();
        if(!unavailable.isEmpty() || duration<15 || duration>1000 || !snapshot.featureSnapshotSettingsOriginals(command).isEmpty())return 4;
        command["commandId"]=QString(32,'c');return !snapshot.featureSnapshotSettingsOriginals(command).isEmpty() && Setting::initializations==0 && Setting::writes==0 ? 0 : 5;
    }
    if(mode=="invalid") {
        settings->_settings["previousStillSnapPath"]=QVariantList{true};const auto unavailable=snapshot.featureSnapshotSettingsOriginals(command);
        settings->_settings.remove("previousStillSnapPath");
        return unavailable.isEmpty() && snapshot.featureSnapshotSettingsOriginals(command).isEmpty() && Setting::initializations==0 && Setting::writes==0 ? 0 : 6;
    }
    const auto value=snapshot.featureSnapshotSettingsOriginals(command),source=value.value("source").toMap(),entries=source.value("entries").toMap(),cache=source.value("formatCache").toMap();
    if(value.value("snapshotSettingsOriginalsVersion")!=1 || entries.size()!=13 || entries.value("snapshotFormat").toMap().value("present")!=false
        || entries.value("snapshotFormat").toMap().value("value").isValid() || cache.value("initialized")!=false || cache.value("set")!=false
        || cache.value("value")!="" || cache.value("defaultValue")!="" || Setting::initializations!=0 || Setting::writes!=0 || settings->_settings!=before
        || !snapshot.featureSnapshotSettingsOriginals(command).isEmpty())return 7;
    const auto original=value;const auto unused=snapshot._snapshotFormat.get();Q_UNUSED(unused)
    command["commandId"]=QString(32,'c');const auto initialized=snapshot.featureSnapshotSettingsOriginals(command);
    if(initialized.value("source").toMap().value("formatCache").toMap().value("initialized")!=true || Setting::initializations!=1 || Setting::writes!=0
        || initialized.value("source").toMap().value("typedSha256")==source.value("typedSha256") || value!=original)return 8;
    snapshot._snapshotFormat.set("webp");command["commandId"]=QString(32,'d');const auto updated=snapshot.featureSnapshotSettingsOriginals(command);
    if(updated.value("source").toMap().value("formatCache").toMap().value("value")!="webp" || Setting::initializations!=1 || Setting::writes!=1)return 9;
    DependencyManager::original=QSharedPointer<Setting::Manager>::create();command["commandId"]=QString(32,'e');const auto replaced=snapshot.featureSnapshotSettingsOriginals(command);
    if(replaced.value("source").toMap().value("managerInstance")==source.value("managerInstance"))return 10;
    std::puts(QJsonDocument::fromVariant(QVariantList{value,initialized,updated,replaced}).toJson(QJsonDocument::Compact).constData());
}
'''


class SnapshotSettingsNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stage=tempfile.TemporaryDirectory(prefix='snapshot-settings-native-');cls.addClassCleanup(stage.cleanup);stage=Path(stage.name);cls.executable=stage/'check'
        manager=(ROOT/'libraries/shared/src/SettingManager.h').read_text();snapshot=(ROOT/'interface/src/ui/Snapshot.h').read_text()
        manager_birth=next(line.strip() for line in manager.splitlines() if 'const QString _featureSnapshotContextInstance{' in line)
        snapshot_birth=next(line.strip() for line in snapshot.splitlines() if 'const QString _featureSettingsInstance{' in line)
        source=stage/'actual.cpp';source.write_text(PREFIX.replace('MANAGER_BIRTH',manager_birth).replace('SNAPSHOT_BIRTH',snapshot_birth)
            +context.body((ROOT/'libraries/shared/src/SettingManager.cpp').read_text(),'QVariantMap Setting::Manager::featureSnapshotSettingsEntries(')
            +context.body((ROOT/'interface/src/ui/Snapshot.cpp').read_text(),'QVariantMap Snapshot::featureSnapshotSettingsOriginals(')
            +context.body((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featureSnapshotSettingsOriginals(')+MAIN)
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');library=[]
        if major not in ('5','6'):raise ValueError('Unsupported Qt major')
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            library=['-L'+str(prefix/'usr/lib64')]
        glm=environment.get('OVERTE_TEST_GLM_INCLUDE') or environment.get('OVERTE_HOST_GLM_INCLUDE');glm_flags=[] if not glm else ['-I'+str(Path(glm).resolve(strict=True))]
        cls.environment=environment;flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
            '-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),*glm_flags,str(source),'-o',str(cls.executable),*library,*flags],check=True,timeout=60,env=environment)
        # Compile the unchanged other-platform getter side too. It must not
        # reference Pico/Android-owned classes or construct an observation.
        other=stage/'other.cpp';cls.other=stage/'other'
        other.write_text('#include <QCoreApplication>\n#include <QVariantMap>\nclass TestScriptingInterface {public: QVariantMap featureSnapshotSettingsOriginals(const QVariantMap& command);};\n'
            +context.body((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featureSnapshotSettingsOriginals(')
            +'int main(int argc,char** argv){QCoreApplication app(argc,argv);TestScriptingInterface original;return original.featureSnapshotSettingsOriginals({}).isEmpty()?0:1;}\n')
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS',str(other),'-o',str(cls.other),*library,*flags],check=True,timeout=60,env=environment)

    def test_actual_thirteen_key_read_passive_cache_births_lock_runtime_and_no_setter(self):
        from adapters.pico4.snapshot_settings_originals import validate,accept
        subprocess.run([str(self.other),'--testScript'],check=True,timeout=5,env=self.environment)
        for mode in ('original','disabled','missing','blocked','invalid','wrong-thread','tsi'):
            with self.subTest(mode=mode):
                raw=subprocess.check_output([str(self.executable),mode,*([] if mode=='disabled' else ['--testScript'])],text=True,timeout=5,env=self.environment)
                if mode=='original':
                    rows=json.loads(raw)
                    for row in rows:validate(row,row['runId'],row['commandId'],row['pid'],row['capturedEpochMs'])
                    accept(rows[0],rows[1]);accept(rows[1],rows[2])
                    with self.assertRaises(Exception):accept(rows[2],rows[3])


if __name__=='__main__':unittest.main()
