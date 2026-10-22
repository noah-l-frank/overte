"""Actual Qt ownership, blocked-owner cancellation and paused-lease retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
from test_snapshot_handoff_native import PREFIX as GATEWAY_PREFIX
GATEWAY_SOURCE=r'''
class PausedAccountThread:public QThread {
public: QSemaphore started,resume;AccountManager* account{nullptr};
 void run() override { started.release();resume.acquire();QCoreApplication::sendPostedEvents(account,QEvent::MetaCall);account->moveToThread(QCoreApplication::instance()->thread()); }
};
int main(int argc,char** argv) {
 QCoreApplication app(argc,argv);QTemporaryDir root;TestScriptingInterface test;test._testResultsLocation=root.path();
 auto account=DependencyManager::get<AccountManager>();const QString mode=QString::fromLocal8Bit(argv[1]);
 const auto query=[](const QString& operation) { return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
  {"action","phone-snapshot-handoff"},{"runId",QString(32,'a')},{"handoffId",QString(32,'b')},{"operation",operation}}; };
 if(mode=="account-queued") {
  QThread worker;worker.start();account->moveToThread(&worker);
  const auto value=test.phoneSnapshotHandoff(query("start"));
  if(value.isEmpty() || !value.value("source").toMap().value("source").toMap().value("context").toMap().value("account").toMap().value("actualOwnerThread").toBool())return 1;
  if(test.phoneSnapshotHandoff(query("retire")).isEmpty())return 2;
  QMetaObject::invokeMethod(account.data(),[account,&app] { account->moveToThread(app.thread()); },Qt::BlockingQueuedConnection);worker.quit();worker.wait();return 0;
 }
 PausedAccountThread worker;worker.account=account.data();account->moveToThread(&worker);worker.start();worker.started.acquire();
 QElapsedTimer elapsed;elapsed.start();const auto value=test.phoneSnapshotHandoff(query("start"));
 if(!value.isEmpty() || elapsed.elapsed()>1400 || account->reads.load()!=0)return 3;
 const auto owner=test._phoneSnapshotHandoffs.value(QString(32,'b'));if(!owner || owner->observation().value("complete").toBool())return 4;
 if(test.phoneSnapshotHandoff(query("retire")).isEmpty() || !owner->retired() || owner->observation().value("complete").toBool())return 5;
 worker.resume.release();worker.wait();if(account->reads.load()!=0)return 6;return 0;
}
'''
SOURCE=r'''
#include <QGuiApplication>
#include <QTemporaryDir>
#include <QTest>
#include <atomic>
#include "tests/device/native/PhoneSnapshotHandoff.h"
#include "tests/device/native/FeatureLifecycle.h"
using Handoff=overte::e2e::PhoneSnapshotHandoff;
class DelayedOwner:public QThread {
public:
 QSemaphore created,resume;QObject* original{nullptr};std::atomic<int> calls{0};
 void run() override { QObject object;original=&object;created.release();resume.acquire();QCoreApplication::sendPostedEvents(&object,QEvent::MetaCall); }
};
int main(int argc,char** argv) {
 QGuiApplication app(argc,argv);const QString mode=QString::fromLocal8Bit(argv[1]);
 if(mode=="lease-paused") {
  int samples=0;QVariantMap published;
  Handoff owner(QString(32,'a'),QString(32,'b'),[&] { ++samples;return QVariantMap{{"actualReadEpochMs",QDateTime::currentMSecsSinceEpoch()}}; },[&](const QVariantMap& value) { published=value; });
  if(!owner.start() || samples!=1)return 1;
  // Deliberately process no Qt timer events. This is one actual full native
  // monotonic lease, with no shortened constant or injected clock/result.
  QThread::msleep(Handoff::LEASE_MS+30);
  if(!owner.retire())return 2;
  const auto original=owner.observation();
  if(!owner.retired() || original.value("complete").toBool() || original.value("error").toString()!="lease-expired"
    || original.value("timerActive").toBool() || samples!=2 || published!=original)return 3;
  if(!owner.retire() || owner.observation().value("complete").toBool())return 4;return 0;
 }
 if(mode=="owner-thread") {
  QThread worker;worker.start();QObject object;object.moveToThread(&worker);std::atomic<bool> exact{false};
  QObject direct;
  const auto relocated=Handoff::ownedRead(&direct,[&] { direct.moveToThread(&worker);return QVariantMap{{"moved",true}}; });
  if(!relocated.isEmpty())return 13;
  QMetaObject::invokeMethod(&direct,[&] { direct.moveToThread(app.thread()); },Qt::BlockingQueuedConnection);
  auto value=Handoff::ownedRead(&object,[&] { exact=QThread::currentThread()==object.thread() && object.thread()==&worker;
    const auto result=QVariantMap{{"actualEpochMs",QDateTime::currentMSecsSinceEpoch()}};object.moveToThread(app.thread());return result; });
  // Moving the owner during the callback must refuse its result.
  if(!value.isEmpty() || !exact.load())return 5;
  object.moveToThread(&worker);
  value=Handoff::ownedRead(&object,[&] { exact=QThread::currentThread()==object.thread();return QVariantMap{{"actualEpochMs",QDateTime::currentMSecsSinceEpoch()}}; });
  if(value.isEmpty() || !exact.load())return 6;
  QMetaObject::invokeMethod(&object,[&] { object.moveToThread(app.thread()); },Qt::BlockingQueuedConnection);worker.quit();worker.wait();return 0;
 }
 if(mode=="stalled-owner") {
  DelayedOwner worker;worker.start();worker.created.acquire();QElapsedTimer elapsed;elapsed.start();
  auto value=Handoff::ownedRead(worker.original,[&] { ++worker.calls;return QVariantMap{{"late",true}}; });
  if(!value.isEmpty() || elapsed.elapsed()<900 || elapsed.elapsed()>1400)return 7;
  worker.resume.release();worker.wait();if(worker.calls.load()!=0)return 8;return 0;
 }
 if(mode=="stopped-owner") {
  DelayedOwner worker;worker.start();worker.created.acquire();worker.resume.release();worker.wait();
  QThread stopped;QObject object;object.moveToThread(&stopped);QElapsedTimer elapsed;elapsed.start();
  const auto value=Handoff::ownedRead(&object,[] { return QVariantMap{{"wrong",true}}; });
  if(!value.isEmpty() || elapsed.elapsed()>200)return 9;return 0;
 }
 if(mode=="lifecycle-original") {
  QTemporaryDir directory;overte::e2e::FeatureLifecycle lifecycle(&app);
  if(!directory.isValid() || !lifecycle.start(directory.path()) || lifecycle.snapshot().value("launches").toInt()!=1)return 10;
  std::atomic<bool> refused{false};auto worker=QThread::create([&] { refused=lifecycle.snapshot().isEmpty(); });worker->start();worker->wait();delete worker;
  if(!refused.load() || lifecycle.snapshot().isEmpty())return 11;return 0;
 }
 return 12;
}
'''


class SnapshotHandoffAuditNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'build/snapshot-handoff-audit-native';parent.mkdir(parents=True,exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='qt-',dir=parent);cls.addClassCleanup(temporary.cleanup);stage=Path(temporary.name);cls.binary=stage/'audit'
        cpp=stage/'audit.cpp';cpp.write_text(SOURCE)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui','Qt6Test'],text=True))
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE','-I'+str(ROOT),str(cpp),'-o',str(cls.binary),*flags],check=True,timeout=60)
        source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text();start=source.index('QVariantMap TestScriptingInterface::phoneSnapshotHandoff(')
        method=source[start:source.index('\n}',start)+2]
        prefix=GATEWAY_PREFIX.replace('class AccountManager:public QObject { public: QVariantMap featureAccountObservation() { return {{"explicitHostAccountSeam",true}}; } };',
            'class AccountManager:public QObject { public: std::atomic<int> reads{0};QVariantMap featureAccountObservation() { ++reads;return {{"explicitHostAccountSeam",true},{"actualOwnerThread",QThread::currentThread()==thread()}}; } };')
        gateway=stage/'gateway.cpp';gateway.write_text(prefix+method+GATEWAY_SOURCE);cls.gateway=stage/'gateway'
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE','-I'+str(ROOT),str(gateway),'-o',str(cls.gateway),*flags],check=True,timeout=60)
    def execute(self,mode):subprocess.run([str(self.binary),mode,'--testScript'],env=dict(os.environ,QT_QPA_PLATFORM='offscreen'),check=True,timeout=65)
    def test_actual_expired_paused_qt_lease_cannot_be_laundered_by_first_retirement(self):self.execute('lease-paused')
    def test_account_style_original_qobject_thread_is_measured_and_relocation_is_refused(self):self.execute('owner-thread')
    def test_stalled_original_owner_has_bounded_wait_and_queued_late_getter_is_cancelled(self):self.execute('stalled-owner')
    def test_stopped_owner_is_unavailable_without_waiting_on_its_dead_queue(self):self.execute('stopped-owner')
    def test_actual_feature_lifecycle_accepts_only_its_original_gui_owner_thread(self):self.execute('lifecycle-original')
    def test_actual_gateway_acquires_account_only_on_original_running_owner_thread(self):subprocess.run([str(self.gateway),'account-queued','--testScript'],check=True,timeout=5)
    def test_actual_gateway_retains_source_error_after_stalled_account_and_cancels_late_callbacks(self):subprocess.run([str(self.gateway),'account-stalled','--testScript'],check=True,timeout=5)


if __name__=='__main__':unittest.main()
