"""Original QObject lifetime registry, native getter and disconnect body in real Qt.

Manager/engine are QObject producer seams, not V8 or the full ScriptManager TU.
Actual weak-holder expiry, deleteLater and a real stopped worker are exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))

HARNESS=r'''
#include <QCoreApplication>
#include <QDateTime>
#include <QEvent>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QTextStream>
#include <QThread>
#include <memory>
#include <vector>
#include <cassert>
#include "libraries/script-engine/src/ScriptObjectLifetimes.h"
#include "libraries/script-engine/src/RequiredModuleObservation.h"
class ScriptManager:public QObject {
public:
    QVariantMap featureLoadMembership()const{return required.loadMembership();}
    void disconnectNonEssentialSignals();
    static QVariantMap featureObjectLifetimes();
    overte::e2e::RequiredModuleObservation required;bool _isThreaded{false};
};
DISCONNECT
LIFETIMES
class TestScriptingInterface:public QObject {
public:
    struct Lifecycle {QVariantMap snapshot(){return {{"actualHostTestLifecycle",true}};}};
    QVariantMap featureScriptObjectLifetimes(const QVariantMap&);
    QString _testResultsLocation{"private-host-test"},_featureObservationInstance{QString(32,'a')};
    Lifecycle lifecycle;Lifecycle* _featureLifecycle{&lifecycle};
    quint64 _featureScriptObjectLifetimesSequence{0};QSet<QString> _featureScriptObjectLifetimesRequests;
};
GETTER
int main(int argc,char**argv){
    QCoreApplication app(argc,argv);using namespace overte::e2e;TestScriptingInterface native;int serial=0;QJsonArray frames;
    auto request=[&]{return QVariantMap{{"schemaVersion",1},{"commandId",QString::number(++serial,16).rightJustified(32,'0')},
        {"action","feature-script-object-lifetimes-observe"}};};
    auto query=[&]{auto packet=native.featureScriptObjectLifetimes(request());assert(!packet.isEmpty());
        frames.append(QJsonObject::fromVariantMap(packet));return packet.value("source").toMap();};
    if(!app.arguments().contains("--testScript")){
        assert(native.featureScriptObjectLifetimes(request()).isEmpty());
        ScriptManager manager;QObject engine;scriptObjectLifetimes().created(QString(32,'b'),&manager,&engine);
        assert(scriptObjectLifetimes().snapshot().isEmpty());return 0;
    }
    assert(query().value("objects").toList().isEmpty());
    std::shared_ptr<ScriptManager> manager(new ScriptManager,[](ScriptManager* object){object->deleteLater();});
    std::weak_ptr<ScriptManager> holder=manager;auto engine=std::make_unique<QObject>();auto worker=std::make_unique<QThread>();
    const auto id=manager->featureLoadMembership().value("instance").toString();
    scriptObjectLifetimes().created(id,manager.get(),engine.get());scriptObjectLifetimes().worker(id,worker.get());
    auto row=[&]{const auto rows=query().value("objects").toList();assert(rows.size()==1);return rows[0].toMap();};
    assert(row().value("managerAlive").toBool());worker->start();worker->quit();assert(worker->wait(5000));
    // A stopped thread object remains owned. The real disconnect method must
    // preserve only the original lifetime observation alongside existing wiring.
    manager->disconnectNonEssentialSignals();manager.reset();assert(holder.expired());
    assert(row().value("managerAlive").toBool());assert(row().value("workerAlive").toBool());
    QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
    auto after=row();assert(!after.value("managerAlive").toBool());assert(after.value("engineAlive").toBool());
    engine->deleteLater();engine.release();QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
    after=row();assert(!after.value("engineAlive").toBool()&&after.value("workerAlive").toBool());
    worker.reset();after=row();assert(!after.value("workerAlive").toBool());
    auto duplicate=request();assert(!native.featureScriptObjectLifetimes(duplicate).isEmpty());
    assert(native.featureScriptObjectLifetimes(duplicate).isEmpty());
    auto forged=request();forged.insert("expectedDestroyed",true);assert(native.featureScriptObjectLifetimes(forged).isEmpty());
    {
        ScriptObjectLifetimes original;QObject first,second,foreign;original.created(QString(32,'c'),&first,&second);
        original.reconnect(QString(32,'c'),&foreign);assert(original.snapshot().isEmpty());
    }
    {
        ScriptObjectLifetimes bounded;std::vector<std::unique_ptr<QObject>> actuals;
        for(int i=0;i<129;++i){actuals.emplace_back(new QObject);actuals.emplace_back(new QObject);
            bounded.created(QString::number(i+1,16).rightJustified(32,'0'),actuals[actuals.size()-2].get(),actuals.back().get());}
        assert(bounded.snapshot().isEmpty());
    }
    QTextStream(stdout)<<QJsonDocument(frames).toJson(QJsonDocument::Compact)<<'\n';
}
'''


def function(source,signature):
    start=source.index(signature);return source[start:source.index('\n}\n',start)+3]


class ScriptObjectLifetimesNativeTests(unittest.TestCase):
    def test_actual_qobject_death_getter_delete_later_weak_holder_and_worker_are_distinct(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'));libraries=[]
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            libraries=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        manager=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        native=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        harness=HARNESS.replace('DISCONNECT',function(manager,'void ScriptManager::disconnectNonEssentialSignals()'))
        harness=harness.replace('LIFETIMES',function(manager,'QVariantMap ScriptManager::featureObjectLifetimes()'))
        harness=harness.replace('GETTER',function(native,'QVariantMap TestScriptingInterface::featureScriptObjectLifetimes('))
        with tempfile.TemporaryDirectory(prefix='pico-script-object-lifetimes-') as temporary:
            stage=Path(temporary);source=stage/'original.cpp';source.write_text(harness);binary=stage/'test'
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
                '-I'+str(ROOT),str(source),'-o',str(binary),*libraries,*flags],check=True,timeout=60,env=environment,capture_output=True)
            subprocess.run([str(binary)],check=True,timeout=10,env=environment,capture_output=True)
            result=subprocess.check_output([str(binary),'--testScript'],text=True,timeout=15,env=environment)
        from adapters.native_script_object_lifetimes import validate,command,destroyed,ACTION
        frames=json.loads(result);previous=None
        for packet in frames:
            request=command(dict(schemaVersion=1,commandId=packet['commandId'],action=ACTION))
            validate(packet,request,packet['processId'],packet['capturedEpochMs'],previous=previous);previous=packet
        self.assertGreater(len(frames),5);original=frames[1]['source']['objects'][0]['instance']
        self.assertFalse(destroyed(frames[-1],original)['managerAlive'])
        with self.assertRaises((ValueError,RuntimeError)):destroyed(frames[-2],original)


if __name__=='__main__':unittest.main()
