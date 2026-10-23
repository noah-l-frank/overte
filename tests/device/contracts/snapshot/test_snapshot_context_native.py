"""Actual bounded Setting read and Pico VM bridge; no global writer startup.

The Manager constructor/storage/DI and VM are explicit seams. The original read
method, birth initializer, locks, caller scope, recorder and bridge are compiled.
No device, renderer, APK or complete client translation unit is exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('snapshot_scope_fixture',Path(__file__).with_name('test_snapshot_script_native.py'))
scope=importlib.util.module_from_spec(spec);spec.loader.exec_module(scope)


def body(text,marker):
    start=text.index(marker);opening=text.index('{',start);depth=1;end=opening+1
    while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]+'\n'


SETTING=r'''
#include <QUrl>
#include <QSharedPointer>
#include <QSemaphore>
#include <thread>
#include "libraries/shared/src/shared/ReadWriteLockable.h"
namespace Setting {
class Manager : public ReadWriteLockable {
public:
    QHash<QString,QVariant> _settings;
    BIRTH_INITIALIZER
    QVariantMap featureSnapshotCaptureContext() const;
};
}
class DependencyManager {
public:
    static QSharedPointer<Setting::Manager> original;
    static int reads;
    template<class T> static bool isSet() { return !original.isNull(); }
    template<class T> static QSharedPointer<T> get() { ++reads;return original; }
};
QSharedPointer<Setting::Manager> DependencyManager::original;
int DependencyManager::reads=0;
'''
MAIN=r'''
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);const QString mode=QString::fromLocal8Bit(argv[1]);
    auto settings=QSharedPointer<Setting::Manager>::create();DependencyManager::original=settings;
    settings->_settings={{"previousSnapshotDomainID","{01234567-89ab-cdef-0123-456789abcdef}"},
        {"previousSnapshotHref","hifi://original/with space"},{"previousStillSnapPath","/original/capture.png"}};
    ScriptManager vm;Snapshot snapshot;
    QVariantMap command{{"schemaVersion",1},{"commandId",QString(32,'a')},{"runId",QString(32,'b')}};
    if(mode=="disabled") {
        snapshot.featureCaptureEvent("pending","snap_100_1","still",1);
        return settings->featureSnapshotCaptureContext().isEmpty() && snapshot.featureSnapshotScriptOriginals(command).isEmpty()
            && snapshot._featureCaptureScriptHistory.snapshot().isEmpty() && DependencyManager::reads==0 ? 0 : 1;
    }
    if(mode=="missing") {
        DependencyManager::original.clear();const auto result=snapshot.featureSnapshotScriptOriginals(command);
        return result.isEmpty() && DependencyManager::reads==0 ? 0 : 2;
    }
    if(mode=="blocked") {
        QSemaphore entered,release;std::thread worker([&]{QWriteLocker lock(&settings->getLock());entered.release();release.acquire();});entered.acquire();
        QElapsedTimer elapsed;elapsed.start();const auto unavailable=snapshot.featureSnapshotScriptOriginals(command);const auto duration=elapsed.elapsed();
        release.release();worker.join();
        if(!unavailable.isEmpty() || duration<15 || duration>1000 || !snapshot.featureSnapshotScriptOriginals(command).isEmpty())return 3;
        command["commandId"]=QString(32,'c');return snapshot.featureSnapshotScriptOriginals(command).value("snapshotScriptOriginalsVersion")==3 ? 0 : 4;
    }
    if(mode=="invalid") {
        settings->_settings["previousSnapshotDomainID"]=true;
        {ScriptManager::FeatureNativeCallScope scope(&vm,"featureCaptureEvent",2);snapshot.featureCaptureEvent("pending","snap_100_1","still",1);}
        settings->_settings["previousSnapshotDomainID"]="original";
        return snapshot._featureCaptureScriptHistory.snapshot().value("complete")==false && snapshot.featureSnapshotScriptOriginals(command).isEmpty() ? 0 : 5;
    }
    const auto absent=QSharedPointer<Setting::Manager>::create()->featureSnapshotCaptureContext();
    if(absent.value("entries").toMap().size()!=3 || absent.value("instance")==settings->_featureSnapshotContextInstance)return 9;
    for(const auto& value:absent.value("entries").toMap())if(value.toMap().value("present")!=false || value.toMap().value("value").isValid())return 6;
    {ScriptManager::FeatureNativeCallScope scope(&vm,"featureCaptureEvent",2);snapshot.featureCaptureEvent("pending","snap_100_1","still",1);}
    const auto result=snapshot.featureSnapshotScriptOriginals(command);const auto current=result.value("captureContext").toMap();
    const auto events=result.value("history").toMap().value("events").toList();
    if(result.value("snapshotScriptOriginalsVersion")!=3 || events.size()!=1 || current.value("instance")!=settings->_featureSnapshotContextInstance
        || events[0].toMap().value("context").toMap().value("instance")!=current.value("instance")
        || current.value("normalizedHref")!=QUrl("hifi://original/with space").toString())return 7;
    settings->_settings["previousSnapshotHref"]="hifi://later";command["commandId"]=QString(32,'c');
    const auto after=snapshot.featureSnapshotScriptOriginals(command);
    if(after.value("history")!=result.value("history") || after.value("captureContext").toMap().value("normalizedHref")!="hifi://later")return 8;
    std::puts(QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).constData());
}
'''


class SnapshotContextNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stage=tempfile.TemporaryDirectory(prefix='snapshot-context-native-');cls.addClassCleanup(stage.cleanup);stage=Path(stage.name);cls.executable=stage/'check'
        header=(ROOT/'libraries/shared/src/SettingManager.h').read_text()
        birth=next(line.strip() for line in header.splitlines() if 'const QString _featureSnapshotContextInstance{' in line)
        manager=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        actual='thread_local QVariantMap ScriptManager::_featureNativeCallContext;\n'+''.join(body(manager,marker) for marker in (
            'QVariantMap ScriptManager::featureNativeCallContext(',
            'ScriptManager::FeatureNativeCallScope::FeatureNativeCallScope(const QVariantMap&',
            'ScriptManager::FeatureNativeCallScope::FeatureNativeCallScope(ScriptManager*',
            'ScriptManager::FeatureNativeCallScope::~FeatureNativeCallScope(',
            'QVariantMap ScriptManager::featureCaptureWorkObservation('))
        actual+=body((ROOT/'libraries/shared/src/SettingManager.cpp').read_text(),'QVariantMap Setting::Manager::featureSnapshotCaptureContext(')
        snapshot=(ROOT/'interface/src/ui/Snapshot.cpp').read_text()
        actual+=''.join(body(snapshot,marker) for marker in ('void Snapshot::featureCaptureEvent(','QVariantMap Snapshot::featureSnapshotScriptOriginals('))
        source=stage/'original.cpp';source.write_text(scope.PREFIX+SETTING.replace('BIRTH_INITIALIZER',birth)+actual+MAIN)
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');library=[]
        if major not in ('5','6'):raise ValueError('Unsupported Qt major')
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            library=['-L'+str(prefix/'usr/lib64')]
        cls.environment=environment
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        subprocess.run(['c++','-std=c++17','-fPIC','-Wall','-Wextra','-Werror','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
            '-I'+str(ROOT),str(source),'-o',str(cls.executable),*library,*flags],check=True,timeout=60,env=environment)

    def test_actual_context_read_original_event_current_query_unavailable_and_runtime_gate(self):
        import json
        for mode in ('original','missing','blocked','invalid','disabled'):
            with self.subTest(mode=mode):
                output=subprocess.check_output([str(self.executable),mode,*([] if mode=='disabled' else ['--testScript'])],text=True,timeout=5,env=self.environment)
                if mode=='original':
                    value=json.loads(output);scope.validate(value['history'],value['capturedEpochMs'])
                    from adapters.pico4.snapshot_script_originals import validate
                    validate(value,value['runId'],value['commandId'],value['pid'],value['capturedEpochMs'])


if __name__=='__main__':unittest.main()
