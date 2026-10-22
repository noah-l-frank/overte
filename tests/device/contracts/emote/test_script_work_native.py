"""Compile original queued Script work bodies with real Qt thread/timer objects.

Manager/code/engine lifecycle values are explicit seams. This is neither the
full ScriptManager translation unit nor a V8/application qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
HARNESS=r'''
#include <QCoreApplication>
#include <QThread>
#include <QTimer>
#include <QSemaphore>
#include <QVariantMap>
#include <QMap>
#include <QDateTime>
#include <cassert>
#include <atomic>
#include <memory>
#include <mutex>
#include <map>
class ScriptManager:public QObject {
public:
    SCOPE
    void featureCallbackBoundary(bool timer,bool entering,int scriptId);
    void featureTimerRegistered(int scriptId);
    QVariantMap featureWorkObservation(const QString& requestId);
    bool isRunning()const{return running;}bool isStopping()const{return false;}
    bool isFinished()const{return false;}
    QVariantMap featureLoadMembership()const{return {{"instance",QString(32,'a')}};}
    QVariantMap featureSourceIdentity()const{return {{"submitted",true}};}
    QVariantMap featureCompiledSources()const{return {{"complete",true}};}
    bool running{true},_isDoneRunning{false};
    struct Engine{bool isEvaluating()const{return false;}};
    std::unique_ptr<Engine> _engine{new Engine};
    struct Data{int featureFunctionScriptId{8};};
    std::map<int,std::pair<std::unique_ptr<QTimer>,Data>>_timerFunctionMap;
    struct FeatureWorkActivity{quint64 signalCallbacks{0},timerCallbacks{0},signalInvocations{0},timerInvocations{0},timerRegistrations{0};};
    QMap<int,FeatureWorkActivity>_featureWorkActivity;
    const bool _featureWorkEnabled{QCoreApplication::arguments().contains("--testScript")};
    std::atomic<bool>_featureWorkValid{true};quint64 _featureSignalCallbacks{0},_featureTimerCallbacks{0};
    std::mutex _featureWorkMutex;QString _featureWorkRequest;QVariantMap _featureWorkResult;
    bool _featureWorkPending{false};quint64 _featureWorkSequence{0};
};
BOUNDARY
REGISTER
OBSERVE
QVariantMap complete(ScriptManager& m,const QString& request){
    for(int i=0;i<500;++i){auto value=m.featureWorkObservation(request);if(!value.value("pending").toBool())return value;QThread::msleep(2);}
    assert(false);return {};
}
int main(int argc,char**argv){
    QCoreApplication app(argc,argv);QThread thread;thread.start();
    auto manager=new ScriptManager;manager->moveToThread(&thread);
    if(!app.arguments().contains("--testScript")){
        assert(manager->featureWorkObservation(QString(32,'a')).isEmpty());
    }else{
        QMetaObject::invokeMethod(manager,[&]{
            auto timer=std::make_unique<QTimer>();timer->setSingleShot(true);timer->start(60000);
            manager->_timerFunctionMap.emplace(1,std::make_pair(std::move(timer),ScriptManager::Data{}));
            manager->featureTimerRegistered(8);
        },Qt::BlockingQueuedConnection);
        QSemaphore entered,release;
        QMetaObject::invokeMethod(manager,[&]{entered.release();assert(release.tryAcquire(1,5000));},Qt::QueuedConnection);
        assert(entered.tryAcquire(1,5000));const auto a=QString(32,'a'),b=QString(32,'b');
        assert(manager->featureWorkObservation(a).value("pending").toBool());
        assert(manager->featureWorkObservation(a).value("pending").toBool());
        assert(manager->featureWorkObservation(b).isEmpty());release.release();
        const auto first=complete(*manager,a);const auto work=first.value("work").toMap();
        assert(work.value("scriptWorkVersion")==QVariant(2)&&work.value("timerEntries")==QVariant(1));
        assert(work.value("timers").toList()[0].toMap().value("functionScriptId")==QVariant(8));
        assert(complete(*manager,a)==first);
        QMetaObject::invokeMethod(manager,[&]{ScriptManager::FeatureCallbackScope scope(manager,false,8);},Qt::BlockingQueuedConnection);
        const auto second=complete(*manager,b).value("work").toMap();
        assert(second.value("signalCallbacks").toULongLong()==0);
        assert(second.value("activity").toList()[0].toMap().value("signalInvocations").toULongLong()==1);
        // Actual nested event-loop delivery while an original callback lives.
        QSemaphore active,finish;
        QMetaObject::invokeMethod(manager,[&]{
            ScriptManager::FeatureCallbackScope scope(manager,true,8);active.release();
            while(!finish.tryAcquire()){QCoreApplication::processEvents();QThread::msleep(1);}
        },Qt::QueuedConnection);
        assert(active.tryAcquire(1,5000));const auto retained=complete(*manager,QString(32,'c')).value("work").toMap();
        assert(retained.value("timerCallbacks").toULongLong()==1);finish.release();
        QMetaObject::invokeMethod(manager,[&]{
            manager->_timerFunctionMap.clear();ScriptManager::FeatureCallbackScope unknown(manager,false,0);
        },Qt::BlockingQueuedConnection);
        const auto final=complete(*manager,QString(32,'d')).value("work").toMap();
        assert(final.value("timers").toList().isEmpty()&&final.value("timerCallbacks").toULongLong()==0);
        assert(final.value("activityEntries").toInt()==2);
        manager->running=false;assert(manager->featureWorkObservation(QString(32,'e')).isEmpty());manager->running=true;
        {ScriptManager::FeatureCallbackScope wrongThread(manager,false,8);}
        assert(manager->featureWorkObservation(QString(32,'f')).isEmpty());
    }
    QMetaObject::invokeMethod(manager,[&]{delete manager;},Qt::BlockingQueuedConnection);
    thread.quit();assert(thread.wait(5000));return 0;
}
'''


def function(source,signature):
    start=source.index(signature);return source[start:source.index('\n}\n',start)+3]


class ScriptWorkNativeTests(unittest.TestCase):
    def test_original_owner_queue_pending_timer_and_callback_boundaries(self):
        env=dict(os.environ);major=env.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'));libraries=[]
        if major=='5' and env.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(env['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            env.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            libraries=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],env=env,text=True))
        source=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text();header=(ROOT/'libraries/script-engine/src/ScriptManager.h').read_text()
        start=header.index('    class FeatureCallbackScope {');scope=header[start:header.index('\n    };',start)+7]
        harness=HARNESS.replace('SCOPE',scope)
        for marker,signature in [('BOUNDARY','void ScriptManager::featureCallbackBoundary('),('REGISTER','void ScriptManager::featureTimerRegistered('),('OBSERVE','QVariantMap ScriptManager::featureWorkObservation(')]:
            harness=harness.replace(marker,function(source,signature))
        with tempfile.TemporaryDirectory(prefix='pico-original-script-work-') as directory:
            path=Path(directory);(path/'work.cpp').write_text(harness);binary=path/'work-test'
            subprocess.run(['c++','-std=c++20','-fPIC','-pthread',str(path/'work.cpp'),'-o',str(binary),*libraries,*flags],env=env,check=True,timeout=60)
            for arguments in ([],['--testScript']):subprocess.run([str(binary),*arguments],env=env,check=True,timeout=15)


if __name__=='__main__':unittest.main()
