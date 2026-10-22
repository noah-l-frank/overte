"""Original Qt worker methods, real queued thread and independent physical bytes.

The manager's in-memory map is an explicit seam. No application/device runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]


def body(source,marker):
    start=source.index(marker);opening=source.index('{',start);depth=1;end=opening+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


HARNESS=r'''
#include "tests/device/native/ChatSettingsBarrier.h"
#include <QSettings>
#include <QThread>
#include <QTemporaryDir>
#include <QSemaphore>
#include <cassert>
#include <thread>
namespace Setting {
class WriteWorker:public QObject {
public:
    void setValue(const QString key,const QVariant value);
    void sync();QVariantMap featureChatSnapshot();
    void init(){if(!_qSettings)_qSettings=new QSettings();}
    QSettings* _qSettings{nullptr};QString _featureChatInstance{QString(32,'a')};
};
SET_VALUE
SYNC
SNAPSHOT
}
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir scratch;assert(scratch.isValid());
    assert(::chmod(QFile::encodeName(scratch.path()).constData(),0700)==0);
    QCoreApplication::setOrganizationName("OverteChatSynthetic");QCoreApplication::setApplicationName("Settings");
    QSettings::setDefaultFormat(QSettings::IniFormat);QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,scratch.path());
    const auto parent=scratch.path()+"/OverteChatSynthetic";assert(QDir().mkpath(parent));assert(::chmod(QFile::encodeName(parent).constData(),0755)==0);
    QThread thread;Setting::WriteWorker worker;worker.moveToThread(&thread);thread.start();
    overte::e2e::ChatSettingsBarrier barrier;QVariantMap cache{{"initial",true}};int writerCalls{0};
    auto snapshot=[&] {
        return barrier.read([&]{return cache;},[&] {
            ++writerCalls;QVariantMap actual;
            assert(QMetaObject::invokeMethod(&worker,[&]{actual=worker.featureChatSnapshot();},Qt::BlockingQueuedConnection));return actual;
        });
    };
    auto set=[&](QVariant value) {
        overte::e2e::ChatSettingsBarrier::Mutation mutation(barrier,"ArmoredChat-Messages");
        cache.insert("history",value);
        assert(QMetaObject::invokeMethod(&worker,[&,value]{worker.setValue("ArmoredChat-Messages",value);},Qt::QueuedConnection));
    };
    const auto empty=snapshot();assert(!empty.isEmpty());
    set(QVariantList());auto list=snapshot();assert(!list.isEmpty());
    const auto listWriter=list.value("writer").toMap();const auto listValues=listWriter.value("values").toMap();
    assert(listValues.value("ArmoredChat-Messages").toMap().value("value").userType()==QMetaType::QVariantList);
    const auto listDisk=listWriter.value("physical").toMap();assert(listDisk.value("ArmoredChat-Messages").toMap().value("present")==true);
    set(QVariant());const auto nullValue=snapshot();
    const auto nullWriter=nullValue.value("writer").toMap();
    assert(!nullWriter.value("values").toMap().value("ArmoredChat-Messages").toMap().value("value").isValid());
    assert(nullWriter.value("physical").toMap()==listDisk); // Same bytes do not manufacture equal live types.
    set(QString());const auto stringValue=snapshot();
    assert(stringValue.value("writer").toMap().value("physical").toMap()!=listDisk);
    assert(stringValue.value("mutationSequence").toLongLong()==3);

    QSemaphore entered,release;
    std::thread delayed([&] {
        overte::e2e::ChatSettingsBarrier::Mutation mutation(barrier,"ArmoredChat-Messages");
        entered.release();release.acquire();
        assert(QMetaObject::invokeMethod(&worker,[&]{worker.setValue("ArmoredChat-Messages",QString("after enqueue"));},Qt::QueuedConnection));
    });
    entered.acquire();const auto calls=writerCalls;assert(barrier.pendingMutations()==1);
    assert(snapshot().isEmpty() && writerCalls==calls);release.release();delayed.join();assert(!snapshot().isEmpty());

    QSemaphore begin;std::thread concurrent([&] {
        begin.acquire();overte::e2e::ChatSettingsBarrier::Mutation mutation(barrier,"ArmoredChat-Messages");
        assert(QMetaObject::invokeMethod(&worker,[&]{worker.setValue("ArmoredChat-Messages",QString("racing enqueue"));},Qt::QueuedConnection));
    });
    const auto raced=barrier.read([&]{return cache;},[&] {
        begin.release();QElapsedTimer wait;wait.start();
        while(barrier.pendingMutations()==0 && wait.elapsed()<1000)QThread::msleep(1);
        assert(barrier.pendingMutations()==1);return QVariantMap{{"original",true}};
    });
    assert(raced.isEmpty());concurrent.join();assert(!snapshot().isEmpty());

    QString path;assert(QMetaObject::invokeMethod(&worker,[&]{path=worker._qSettings->fileName();},Qt::BlockingQueuedConnection));
    auto physical=overte::e2e::chatSettingsFile(path);assert(!physical.isEmpty());
    assert(::chmod(QFile::encodeName(path).constData(),0666)==0);assert(overte::e2e::chatSettingsFile(path).isEmpty());
    assert(::chmod(QFile::encodeName(path).constData(),0644)==0);
    QFile duplicate(path);assert(duplicate.open(QIODevice::WriteOnly|QIODevice::Truncate));
    duplicate.write("[General]\nArmoredChat-Messages=first\nArmoredChat-Messages=second\n");duplicate.close();
    assert(overte::e2e::chatSettingsFile(path).isEmpty());
    assert(QFile::remove(path));assert(QFile::link(parent+"/missing",path));assert(overte::e2e::chatSettingsFile(path).isEmpty());QFile::remove(path);
    assert(QMetaObject::invokeMethod(&worker,[&]{delete worker._qSettings;worker._qSettings=nullptr;},Qt::BlockingQueuedConnection));
    thread.quit();assert(thread.wait(2000));
}
'''

FULL_MANAGER=r'''
#include "SettingManager.h"
#include <QTemporaryDir>
#include <QSemaphore>
#include <cassert>
#include <thread>
class OwnedManager:public Setting::Manager {
public:~OwnedManager(){terminateThread();}
};
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir scratch;assert(scratch.isValid());
    QCoreApplication::setOrganizationName("OverteActualManager");QCoreApplication::setApplicationName("Settings");
    QSettings::setDefaultFormat(QSettings::IniFormat);QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,scratch.path());
    assert(::chmod(QFile::encodeName(scratch.path()).constData(),0700)==0);
    assert(QDir().mkpath(scratch.path()+"/OverteActualManager"));
    OwnedManager manager;
    const auto original=manager.featureChatSnapshot();assert(!original.isEmpty());
    manager.setValue("ArmoredChat-Messages",QVariantList());
    manager.setValue("ArmoredChat-Config",QVariantMap{{"enabled",true},{"fontSize",22}});
    const auto current=manager.featureChatSnapshot();assert(!current.isEmpty());
    assert(current.value("pending")==0 && current.value("mutationSequence")==2);
    const auto cache=current.value("cache").toMap();const auto writer=current.value("writer").toMap();
    assert(cache.value("ArmoredChat-Messages").toMap().value("value").userType()==QMetaType::QVariantList);
    assert(writer.value("values").toMap().value("ArmoredChat-Messages").toMap().value("value").userType()==QMetaType::QVariantList);
    assert(writer.value("physical").toMap().value("ArmoredChat-Config").toMap().value("present")==true);
    QSemaphore entered,release;
    const auto connection=QObject::connect(&manager,&Setting::Manager::valueChanged,&manager,[&](QString key,QVariant) {
        if(key=="ArmoredChat-Messages"){entered.release();release.acquire();}
    },Qt::DirectConnection);
    std::thread active([&]{manager.setValue("ArmoredChat-Messages",QString("original signal body still active"));});
    entered.acquire();assert(manager.featureChatSnapshot().isEmpty());release.release();active.join();QObject::disconnect(connection);
    assert(!manager.featureChatSnapshot().isEmpty());
    manager.remove("ArmoredChat-Messages");const auto removed=manager.featureChatSnapshot();assert(!removed.isEmpty());
    assert(removed.value("cache").toMap().value("ArmoredChat-Messages").toMap().value("present")==false);
    assert(removed.value("writer").toMap().value("physical").toMap().value("ArmoredChat-Messages").toMap().value("present")==false);
    manager.clearAllSettings();const auto cleared=manager.featureChatSnapshot();assert(!cleared.isEmpty());
    assert(cleared.value("writer").toMap().value("physical").toMap().value("ArmoredChat-Config").toMap().value("present")==false);
}
'''


class SettingsBarrierTests(unittest.TestCase):
    def test_actual_manager_translation_unit_and_original_worker(self):
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True))
        library=subprocess.check_output(['pkg-config','--variable=libdir','Qt5Core'],text=True).strip()
        moc=os.environ.get('OVERTE_CHAT_MOC') or shutil.which('moc-qt5') or shutil.which('moc')
        if not moc and os.environ.get('PKG_CONFIG_SYSROOT_DIR'):
            moc=str(Path(os.environ['PKG_CONFIG_SYSROOT_DIR'])/'usr/bin/moc-qt5')
        self.assertTrue(moc and Path(moc).is_file(),'Existing Qt5 moc is required')
        with tempfile.TemporaryDirectory(prefix='overte-chat-settings-manager-') as scratch:
            unit=Path(scratch)/'test.cpp';binary=Path(scratch)/'test';generated=Path(scratch)/'moc.cpp';unit.write_text(FULL_MANAGER)
            includes=['-I'+str(ROOT/'libraries/shared/src'),*[flag for flag in flags if flag.startswith(('-I','-D'))]]
            meta=subprocess.run([moc,'-DOVERTE_E2E_FEATURE_TESTS',*includes,
                str(ROOT/'libraries/shared/src/SettingManager.h'),'-o',str(generated)],capture_output=True,text=True,timeout=30)
            self.assertEqual(0,meta.returncode,meta.stderr[:6000])
            compiled=subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-DOVERTE_E2E_FEATURE_TESTS',*includes,
                str(unit),str(ROOT/'libraries/shared/src/SettingManager.cpp'),str(generated),'-o',str(binary),
                '-L'+library,'-Wl,-rpath,'+library,*flags],capture_output=True,text=True,timeout=45)
            self.assertEqual(0,compiled.returncode,compiled.stderr[:6000])
            executed=subprocess.run([str(binary),'--testScript'],capture_output=True,text=True,timeout=10)
            self.assertEqual(0,executed.returncode,executed.stderr[:2500])

    def test_actual_worker_queue_fence_and_physical_ini_read(self):
        source=(ROOT/'libraries/shared/src/SettingManager.cpp').read_text()
        program=HARNESS.replace('SET_VALUE',body(source,'void WriteWorker::setValue('))
        program=program.replace('SYNC',body(source,'void WriteWorker::sync('))
        program=program.replace('SNAPSHOT',body(source,'QVariantMap WriteWorker::featureChatSnapshot('))
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True))
        library=subprocess.check_output(['pkg-config','--variable=libdir','Qt5Core'],text=True).strip()
        with tempfile.TemporaryDirectory(prefix='overte-chat-settings-barrier-') as scratch:
            unit=Path(scratch)/'test.cpp';binary=Path(scratch)/'test';unit.write_text(program)
            compiled=subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),
                str(unit),'-o',str(binary),'-L'+library,'-Wl,-rpath,'+library,*flags],capture_output=True,text=True,timeout=45)
            self.assertEqual(0,compiled.returncode,compiled.stderr[:6000])
            executed=subprocess.run([str(binary),'--testScript'],capture_output=True,text=True,timeout=10)
            self.assertEqual(0,executed.returncode,executed.stderr[:2000])


if __name__=='__main__':unittest.main()
