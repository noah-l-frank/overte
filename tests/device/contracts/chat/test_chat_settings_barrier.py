"""Original Qt worker methods, real queued thread and independent physical bytes.

One check compiles the complete Manager translation unit and QObject metadata;
the worker-only check has an explicit cache seam. No application/device runs.
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

    QSemaphore begin,racing,finish;std::thread concurrent([&] {
        begin.acquire();overte::e2e::ChatSettingsBarrier::Mutation mutation(barrier,"ArmoredChat-Messages");
        racing.release();finish.acquire();
        assert(QMetaObject::invokeMethod(&worker,[&]{worker.setValue("ArmoredChat-Messages",QString("racing enqueue"));},Qt::QueuedConnection));
    });
    const auto raced=barrier.read([&]{return cache;},[&] {
        begin.release();assert(racing.tryAcquire(1,1000));
        assert(barrier.pendingMutations()==1);return QVariantMap{{"original",true}};
    });
    assert(raced.isEmpty());finish.release();concurrent.join();assert(!snapshot().isEmpty());
    // A mutation that fully finishes during the acquisition is also rejected.
    const auto completed=barrier.read([&]{return cache;},[&] {
        {overte::e2e::ChatSettingsBarrier::Mutation mutation(barrier,"ArmoredChat-Messages");}
        return QVariantMap{{"original",true}};
    });
    assert(completed.isEmpty());assert(!snapshot().isEmpty());

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
class SettingsTests {
public:
    static Setting::WriteWorker* worker(Setting::Manager& manager){return manager._featureChatWorker.data();}
    static std::shared_ptr<Setting::ChatSnapshotJob> job(Setting::Manager& manager){return manager._featureChatRead;}
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
    // An actual contended Manager cache never blocks this UI-thread reader.
    QSemaphore locked,unlock;std::thread cacheHolder([&] {
        manager.withWriteLock([&]{locked.release();unlock.acquire();});
    });
    locked.acquire();QElapsedTimer elapsed;elapsed.start();const auto priorJob=SettingsTests::job(manager);
    assert(manager.featureChatSnapshot().isEmpty() && elapsed.elapsed()<500);
    assert(SettingsTests::job(manager)==priorJob);unlock.release();cacheHolder.join();

    // A queued worker mutator must be free to finish while this query waits.
    // Holding the barrier mutex across the worker wait would deadlock here.
    auto* worker=SettingsTests::worker(manager);assert(worker);
    QSemaphore workerEntered,workerBegin,workerMutated;
    assert(QMetaObject::invokeMethod(worker,[&] {
        workerEntered.release();workerBegin.acquire();
        manager.setValue("ArmoredChat-Messages",QString("actual worker mutation"));workerMutated.release();
    },Qt::QueuedConnection));
    workerEntered.acquire();std::thread startWorker([&]{QThread::msleep(75);workerBegin.release();});
    elapsed.restart();assert(manager.featureChatSnapshot().isEmpty());assert(elapsed.elapsed()<1400);
    assert(workerMutated.tryAcquire(1,500));startWorker.join();
    assert(!manager.featureChatSnapshot().isEmpty());

    // Real worker->UI BlockingQueued cycle: source times out, retains exactly
    // one original queued job, and cannot return its later result as fresh.
    QSemaphore waitingForUi,uiFinished;
    assert(QMetaObject::invokeMethod(worker,[&] {
        waitingForUi.release();
        assert(QMetaObject::invokeMethod(&manager,[&] {
            manager.setValue("ArmoredChat-Messages",QString("after actual UI recovery"));
        },Qt::BlockingQueuedConnection));
        uiFinished.release();
    },Qt::QueuedConnection));
    waitingForUi.acquire();elapsed.restart();assert(manager.featureChatSnapshot().isEmpty());
    assert(elapsed.elapsed()>=1400 && elapsed.elapsed()<2500);
    const auto lateJob=SettingsTests::job(manager);assert(lateJob && !lateJob->done.load());
    elapsed.restart();assert(manager.featureChatSnapshot().isEmpty() && elapsed.elapsed()<500);
    assert(SettingsTests::job(manager)==lateJob);
    QCoreApplication::processEvents();assert(uiFinished.tryAcquire(1,1000));
    QSemaphore drained;assert(QMetaObject::invokeMethod(worker,[&]{drained.release();},Qt::QueuedConnection));
    assert(drained.tryAcquire(1,1000));assert(lateJob->done.load());
    const auto fresh=manager.featureChatSnapshot();assert(!fresh.isEmpty());
    assert(SettingsTests::job(manager)!=lateJob);
    assert(fresh.value("cache").toMap().value("ArmoredChat-Messages").toMap().value("value").toString()=="after actual UI recovery");
    assert(fresh.value("writer").toMap().value("values").toMap().value("ArmoredChat-Messages").toMap().value("value").toString()=="after actual UI recovery");
    manager.remove("ArmoredChat-Messages");const auto removed=manager.featureChatSnapshot();assert(!removed.isEmpty());
    assert(removed.value("cache").toMap().value("ArmoredChat-Messages").toMap().value("present")==false);
    assert(removed.value("writer").toMap().value("physical").toMap().value("ArmoredChat-Messages").toMap().value("present")==false);
    manager.clearAllSettings();const auto cleared=manager.featureChatSnapshot();assert(!cleared.isEmpty());
    assert(cleared.value("writer").toMap().value("physical").toMap().value("ArmoredChat-Config").toMap().value("present")==false);
}
'''


PROFILE=r'''
#include "tests/device/native/ChatProfileOwner.h"
#include <QTemporaryDir>
#include <QJsonDocument>
#include <cassert>
class OwnedManager:public Setting::Manager {public:~OwnedManager(){terminateThread();}};
class SettingsTests {
public:static Setting::WriteWorker* worker(Setting::Manager& manager){return manager._featureChatWorker.data();}
};
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir scratch;assert(scratch.isValid());
    QCoreApplication::setOrganizationName("OverteActualProfile");QCoreApplication::setApplicationName("Settings");
    QSettings::setDefaultFormat(QSettings::IniFormat);QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,scratch.path());
    assert(::chmod(QFile::encodeName(scratch.path()).constData(),0700)==0);
    assert(QDir().mkpath(scratch.path()+"/OverteActualProfile"));OwnedManager manager;
    const QVariantMap config{{"enabled",true},{"privateMarker","original private configuration"}};
    manager.setValue("ArmoredChat-Config",config);bool viewClosed{true};qint64 viewSequence{0};
    const auto view=[&](const QString& run) {
        return QVariantMap{{"chatViewVersion",2},{"runId",run},{"instance",QString(32,'a')},{"sequence",++viewSequence},
            {"processId",QCoreApplication::applicationPid()},{"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},
            {"source",QVariantMap{{"editorFocused",false},{"editorHasDraft",false},{"keyboard",QVariantMap{{"available",true},{"visible",false}}},
                {"ui",QVariantMap{{"present",!viewClosed}}}}}};
    };
    auto command=[](const QString& run,const QString& operation) {
        return QVariantMap{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"runId",run},{"action","feature-chat-profile"},{"operation",operation}};
    };
    for (const auto original:{QVariant(),QVariant(QVariantList()),QVariant(QStringList()),QVariant(QString()),QVariant(QString(""))}) {
        manager.remove("ArmoredChat-Messages");manager.setValue("ArmoredChat-Messages",original);
        overte::e2e::ChatProfileOwner owner(&manager,view);const auto run=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        viewClosed=false;assert(owner.request(command(run,"acquire")).isEmpty());viewClosed=true;
        const auto acquire=command(run,"acquire"),saved=owner.request(acquire);assert(!saved.isEmpty());
        assert(owner.request(acquire).isEmpty());
        assert(!QJsonDocument::fromVariant(saved).toJson().contains("original private configuration"));
        manager.setValue("ArmoredChat-Messages",QVariantList{QVariantMap{{"message","unowned original row"}}});
        assert(owner.request(command(run,"restore")).isEmpty());
        // This is a storage seam, not a claimed normal UI Erase operation.
        manager.setValue("ArmoredChat-Messages",QVariant());
        manager.setValue("ArmoredChat-Config",QVariantMap{{"enabled",false}});
        assert(owner.request(command(run,"restore")).isEmpty());
        manager.setValue("ArmoredChat-Config",config);
        const auto restored=owner.request(command(run,"restore"));assert(!restored.isEmpty());
        assert(restored.value("owned")==true && restored.value("restored")==true);
        assert(restored.value("original")==restored.value("current"));
        assert(owner.request(command(run,"restore")).isEmpty());
        assert(owner.request(command(QString(32,'b'),"inspect")).isEmpty());
    }
    // Qt's original worker equality optimization can retain a different live
    // type even when empty list/string-list values compare equal. Refuse it.
    manager.remove("ArmoredChat-Messages");manager.setValue("ArmoredChat-Messages",QVariantList());
    assert(!manager.featureChatSnapshot().isEmpty());manager.setValue("ArmoredChat-Messages",QStringList());
    overte::e2e::ChatProfileOwner unequalTypes(&manager,view);
    assert(unequalTypes.request(command(QString(32,'e'),"acquire")).isEmpty());
    manager.remove("ArmoredChat-Messages");
    overte::e2e::ChatProfileOwner absent(&manager,view);const auto absentRun=QString(32,'c');
    assert(!absent.request(command(absentRun,"acquire")).isEmpty());
    manager.setValue("ArmoredChat-Messages",QVariant());
    const auto back=absent.request(command(absentRun,"restore"));assert(back.value("restored")==true);
    assert(!manager.contains("ArmoredChat-Messages"));

    // Original cache/file refusal: the physical parser never calls a shared
    // QSettings reader or labels a nonempty row as empty from live variants.
    const auto ini=scratch.path()+"/unowned.ini";QFile file(ini);assert(file.open(QIODevice::WriteOnly));
    file.write("[General]\nArmoredChat-Messages=unowned-file-history\n");file.close();
    assert(overte::e2e::chatSettingsFile(ini).value("ArmoredChat-Messages").toMap().value("empty")==false);
    const auto expected=manager.featureChatSnapshot();assert(!expected.isEmpty());
    manager.setValue("ArmoredChat-Messages",QVariantList{QString("changed after acquisition")});
    assert(!manager.featureChatRestoreHistory(expected,QVariantMap{{"present",false},{"value",QVariant()}}));
    assert(manager.value("ArmoredChat-Messages").toList()==QVariantList{QString("changed after acquisition")});

    // Post-write uncertainty retains native ownership and cannot repeat input.
    manager.setValue("ArmoredChat-Messages",QString(""));
    overte::e2e::ChatProfileOwner late(&manager,view);const auto lateRun=QString(32,'d');
    assert(!late.request(command(lateRun,"acquire")).isEmpty());manager.setValue("ArmoredChat-Messages",QVariant());
    auto* worker=SettingsTests::worker(manager);QSemaphore blocked,release;int writes{0};
    const auto connection=QObject::connect(&manager,&Setting::Manager::valueChanged,&manager,[&](QString key,QVariant) {
        if(key!="ArmoredChat-Messages")return;++writes;
        assert(QMetaObject::invokeMethod(worker,[&]{blocked.release();release.acquire();},Qt::QueuedConnection));
    },Qt::DirectConnection);
    assert(late.request(command(lateRun,"restore")).isEmpty());assert(blocked.tryAcquire(1,500));
    assert(late.request(command(lateRun,"restore")).isEmpty() && writes==1);
    assert(late.request(command(lateRun,"inspect")).isEmpty());
    QObject::disconnect(connection);release.release();
    QSemaphore drained;assert(QMetaObject::invokeMethod(worker,[&]{drained.release();},Qt::QueuedConnection));assert(drained.tryAcquire(1,1000));
    const auto resolved=late.request(command(lateRun,"inspect"));assert(resolved.value("restored")==true && resolved.value("owned")==true);
    assert(writes==1);
}
'''


JSON_PHYSICAL=r'''
#include "tests/device/native/ChatProfileOwner.h"
#include <QTemporaryDir>
#include <QJsonObject>
#include <cassert>
class OwnedManager:public Setting::Manager {public:~OwnedManager(){terminateThread();}};
class SettingsTests {
public:static Setting::WriteWorker* worker(Setting::Manager& manager){return manager._featureChatWorker.data();}
};
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);QTemporaryDir scratch;assert(scratch.isValid());
    assert(::chmod(QFile::encodeName(scratch.path()).constData(),0700)==0);
    const auto path=scratch.path()+"/literal.json";
    auto write=[&](const QByteArray& bytes) {
        QFile file(path);assert(file.open(QIODevice::WriteOnly|QIODevice::Truncate));assert(file.write(bytes)==bytes.size());file.close();
        assert(::chmod(QFile::encodeName(path).constData(),0600)==0);
    };
    auto produce=[](const QSettings::SettingsMap& values) {
        QByteArray bytes;QBuffer output(&bytes);assert(output.open(QIODevice::WriteOnly));assert(writeJSONFile(output,values));return bytes;
    };
    assert(!overte::e2e::chatSettingsFile(path,JSON_FORMAT).isEmpty()); // Actual missing file.
    write("");assert(overte::e2e::chatSettingsFile(path,JSON_FORMAT).isEmpty());
    const QVariantMap config{{"ArmoredChat-Messages",QVariantMap{{"quoted","a,\\\"b"},{"array",QVariantList{1,2}}}},{"private","secret"}};
    for(const auto value:{QVariant(),QVariant(QString()),QVariant(QString("")),QVariant(QVariantList()),QVariant(QStringList())}) {
        const auto bytes=produce({{"ArmoredChat-Messages",value},{"ArmoredChat-Config",config}});write(bytes);
        const auto physical=overte::e2e::chatSettingsFile(path,JSON_FORMAT);assert(!physical.isEmpty());
        assert(physical.value("ArmoredChat-Messages").toMap().value("empty")==true);
        assert(!QJsonDocument::fromVariant(physical).toJson().contains("secret"));
        QBuffer input;input.setData(bytes);assert(input.open(QIODevice::ReadOnly));QSettings::SettingsMap decoded;
        assert(readJSONFile(input,decoded));
        if(value.userType()==QMetaType::QStringList) {assert(decoded.value("ArmoredChat-Messages").userType()==QMetaType::QStringList);}
    }
    for(const auto value:{QVariant(QString("@Variant(malformed)")),QVariant(QStringList{"row"}),QVariant(QVariantList{QString("row")}),QVariant(QVariantMap()),QVariant(false),QVariant(0)}) {
        write(produce({{"ArmoredChat-Messages",value}}));const auto physical=overte::e2e::chatSettingsFile(path,JSON_FORMAT);
        assert(!physical.isEmpty() && physical.value("ArmoredChat-Messages").toMap().value("empty")==false);
    }
    // Literal malformed serialized data is never deserialized or called empty.
    write("{\n    \"ArmoredChat-Messages\": \"@Variant(malformed)\"\n}\n");
    assert(overte::e2e::chatSettingsFile(path,JSON_FORMAT).value("ArmoredChat-Messages").toMap().value("empty")==false);
    const auto canonical=produce({{"ArmoredChat-Messages",QVariantList()},{"ArmoredChat-Config",config}});
    for(const auto malformed:{QByteArray("[]\n"),canonical.trimmed(),QByteArray("\xEF\xBB\xBF")+canonical,
            QByteArray("{\n    \"ArmoredChat-Messages\": null,\n    \"ArmoredChat-Messages\": []\n}\n"),
            QByteArray("{\n    \"ArmoredChat-\\u004dessages\": []\n}\n"),canonical.left(canonical.size()-2)}) {
        write(malformed);assert(overte::e2e::chatSettingsFile(path,JSON_FORMAT).isEmpty());
    }
    for(const auto alias:{" ArmoredChat-Messages","%41rmoredChat-Messages","/ArmoredChat-Messages/","\"ArmoredChat-Config\""}) {
        write(produce({{alias,QVariantList()}}));assert(overte::e2e::chatSettingsFile(path,JSON_FORMAT).isEmpty());
    }
    write(canonical);assert(overte::e2e::chatSettingsFile(path,QSettings::NativeFormat).isEmpty());
    assert(::chmod(QFile::encodeName(path).constData(),0666)==0);assert(overte::e2e::chatSettingsFile(path,JSON_FORMAT).isEmpty());
    assert(::chmod(QFile::encodeName(path).constData(),0600)==0);
    const auto hard=scratch.path()+"/hard";assert(::link(QFile::encodeName(path).constData(),QFile::encodeName(hard).constData())==0);
    assert(overte::e2e::chatSettingsFile(path,JSON_FORMAT).isEmpty());assert(QFile::remove(hard));
    assert(QFile::remove(path));assert(QFile::link(scratch.path()+"/missing",path));assert(overte::e2e::chatSettingsFile(path,JSON_FORMAT).isEmpty());
    assert(QFile::remove(path));

    // Actual Manager cache stays original while a separate writer changes
    // physical JSON. Original worker sync may reload it; no new QSettings reader.
    QCoreApplication::setOrganizationName("OverteOriginalJSON");QCoreApplication::setApplicationName("Settings");
    QSettings::setDefaultFormat(JSON_FORMAT);QSettings::setPath(JSON_FORMAT,QSettings::UserScope,scratch.path());
    assert(QDir().mkpath(scratch.path()+"/OverteOriginalJSON"));OwnedManager manager;
    manager.setValue("ArmoredChat-Messages",QVariantList());manager.setValue("ArmoredChat-Config",config);
    const auto original=manager.featureChatSnapshot();assert(!original.isEmpty());const auto actualPath=manager.fileName();
    QFile originalFile(actualPath);assert(originalFile.open(QIODevice::ReadOnly));const auto originalBytes=originalFile.readAll();originalFile.close();
    QFile changed(actualPath);assert(changed.open(QIODevice::WriteOnly|QIODevice::Truncate));
    const auto foreign=produce({{"ArmoredChat-Messages",QVariantList{QString("foreign physical history")}},{"ArmoredChat-Config",config}});
    assert(changed.write(foreign)==foreign.size());changed.close();
    const auto observed=manager.featureChatSnapshot();assert(!observed.isEmpty());
    assert(observed.value("cache")==original.value("cache"));
    assert(observed.value("writer").toMap().value("values")!=original.value("writer").toMap().value("values"));
    assert(observed.value("writer").toMap().value("values").toMap().value("ArmoredChat-Messages").toMap().value("value").toList()==QVariantList{QString("foreign physical history")});
    assert(observed.value("writer").toMap().value("physical").toMap().value("ArmoredChat-Messages").toMap().value("empty")==false);
    assert(!manager.featureChatRestoreHistory(original,{{"present",false},{"value",QVariant()}}));
    assert(changed.open(QIODevice::WriteOnly|QIODevice::Truncate));assert(changed.write(originalBytes)==originalBytes.size());changed.close();
    assert(manager.featureChatSnapshot().value("writer").toMap().value("physical")==original.value("writer").toMap().value("physical"));
}
'''


class SettingsBarrierTests(unittest.TestCase):
    def test_actual_manager_translation_unit_and_original_worker(self):
        self.compile_manager(FULL_MANAGER)

    def test_actual_profile_owner_saved_types_physical_refusal_and_one_restore(self):
        self.compile_manager(PROFILE)

    def test_actual_json_manager_translation_unit_and_original_worker(self):
        self.compile_manager(FULL_MANAGER.replace('QSettings::IniFormat','JSON_FORMAT'))

    def test_actual_json_profile_saved_types_and_conditional_restore(self):
        self.compile_manager(PROFILE.replace('QSettings::IniFormat','JSON_FORMAT'))

    def test_actual_json_producer_literal_rows_aliases_and_cache_file_disagreement(self):
        self.compile_manager(JSON_PHYSICAL)

    def compile_manager(self,program):
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True))
        library=subprocess.check_output(['pkg-config','--variable=libdir','Qt5Core'],text=True).strip()
        moc=os.environ.get('OVERTE_CHAT_MOC') or shutil.which('moc-qt5') or shutil.which('moc')
        if not moc and os.environ.get('PKG_CONFIG_SYSROOT_DIR'):
            moc=str(Path(os.environ['PKG_CONFIG_SYSROOT_DIR'])/'usr/bin/moc-qt5')
        self.assertTrue(moc and Path(moc).is_file(),'Existing Qt5 moc is required')
        with tempfile.TemporaryDirectory(prefix='overte-chat-settings-manager-') as scratch:
            unit=Path(scratch)/'test.cpp';binary=Path(scratch)/'test';generated=Path(scratch)/'moc.cpp';unit.write_text(program)
            includes=['-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),*[flag for flag in flags if flag.startswith(('-I','-D'))]]
            meta=subprocess.run([moc,'-DOVERTE_E2E_FEATURE_TESTS',*includes,
                str(ROOT/'libraries/shared/src/SettingManager.h'),'-o',str(generated)],capture_output=True,text=True,timeout=30)
            self.assertEqual(0,meta.returncode,meta.stderr[:6000])
            compiled=subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-DOVERTE_E2E_FEATURE_TESTS',*includes,
                str(unit),str(ROOT/'libraries/shared/src/SettingManager.cpp'),str(ROOT/'libraries/shared/src/SettingHelpers.cpp'),str(ROOT/'libraries/shared/src/SharedLogging.cpp'),str(generated),'-o',str(binary),
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
            compiled=subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(ROOT),'-I'+str(ROOT/'libraries/shared/src'),
                str(unit),str(ROOT/'libraries/shared/src/SettingHelpers.cpp'),str(ROOT/'libraries/shared/src/SharedLogging.cpp'),'-o',str(binary),'-L'+library,'-Wl,-rpath,'+library,*flags],capture_output=True,text=True,timeout=45)
            self.assertEqual(0,compiled.returncode,compiled.stderr[:6000])
            executed=subprocess.run([str(binary),'--testScript'],capture_output=True,text=True,timeout=10)
            self.assertEqual(0,executed.returncode,executed.stderr[:2000])


if __name__=='__main__':unittest.main()
