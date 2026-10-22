// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original Bookmarks writer/cache and complete passive TSI getter. Native
// avatar-to-bookmark data is a declared actor; no wearable/model is simulated
// as an independently loaded native effect in this storage test.
#include <QCoreApplication>
#include <QThread>
#include <QTimer>
#include <QTemporaryDir>
#include <QJsonArray>
#include <QSharedPointer>
#include <QElapsedTimer>
#include <QRegularExpression>
#include <QUuid>
#include <QDebug>
#include <cassert>
#include <thread>
#include <iostream>
#include "tests/device/native/AvatarBookmarkStorage.h"
#include "tests/device/native/AudioSettingsQueue.h"
class PathUtils {public:inline static QString root;static QString getAppDataPath(){return root;}static QString resourcesPath(){return root+"/resources/";}};
class Bookmarks:public QObject {public:
    void insert(const QString&,const QVariant&);void remove(const QString&);bool contains(const QString&)const;
    void readFromFile();void persistToFile();QVariantMap _bookmarks;QString _bookmarksFilename,_bookmarkError;
};
class AvatarBookmarks:public Bookmarks {Q_OBJECT
public:
    AvatarBookmarks();QVariantMap e2eBookmarkStorage()const;void addBookmarkInternal(const QString&);void removeBookmarkInternal(const QString&);
    QVariantMap getAvatarDataToBookmark(){return currentAvatarActor;}
    QVariantMap currentAvatarActor{{"version",3},{"avatarUrl","https://controlled.invalid/owned/avatar-a.fst"},{"avatarScale",1.0},{"avatarEntites",QVariantList{}},{"avatarIcon",""}};
    const QString AVATARBOOKMARKS_FILENAME="avatarbookmarks.json";
signals:void bookmarkAdded(const QString&);void bookmarkDeleted(const QString&);
};
// The foreign-thread mutation branch is not exercised here. Passive worker
// observation below uses the entire original bounded queue and native getter.
#define BLOCKING_INVOKE_METHOD(...) qFatal("Unexpected foreign-thread mutation in this storage test")
#define qCDebug(...) qDebug()
QSharedPointer<AvatarBookmarks> manager;int managerReads=0;
class DependencyManager {public:template<class T>static bool isSet(){return bool(manager);}
    template<class T>static QSharedPointer<T> get(){++managerReads;return manager;}};
struct Lifecycle {QVariantMap snapshot()const{return {{"active",true}};}};
class TestScriptingInterface:public QObject {public:
    QVariantMap featurePicoAvatarBookmarks(const QVariantMap&);
    QString _testResultsLocation{"private-results"};std::unique_ptr<Lifecycle>_featureLifecycle{new Lifecycle};
    std::shared_ptr<overte::e2e::AudioSettingsQueue>_featureAvatarBookmarksQueue{new overte::e2e::AudioSettingsQueue};
    quint64 _featureAvatarBookmarksSequence{0};QSet<QString>_featureAvatarBookmarksRequests;QPointer<QObject>_featureAvatarBookmarkObject;
    QString _featureAvatarBookmarkBirth,_featureObservationInstance{QString(32,'a')};
};
#include "actual-avatar-bookmarks.inc"
void turn(){QTimer::singleShot(1,[]{QCoreApplication::quit();});QCoreApplication::exec();}
int main(int argc,char**argv) {
    QCoreApplication app(argc,argv);TestScriptingInterface test;int n=0;
    const auto request=[&]{return QVariantMap{{"schemaVersion",1},{"commandId",QString::number(++n,16).rightJustified(32,'0')},{"action","feature-pico-avatar-bookmarks-observe"}};};
    if(!app.arguments().contains("--testScript")){assert(test.featurePicoAvatarBookmarks(request()).isEmpty()&&managerReads==0);return 0;}
    assert(test.featurePicoAvatarBookmarks(request()).isEmpty()&&managerReads==0);
    QTemporaryDir profile;assert(profile.isValid());assert(QFile::setPermissions(profile.path(),QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner));PathUtils::root=profile.path();
    const auto path=profile.path()+"/avatarbookmarks.json";
    const QByteArray original="{\n  \"unowned\": {\"version\":3,\"avatarUrl\":\"qrc:/meshes/foreign.fst\",\"avatarScale\":1,\"avatarEntites\":[]}\n}\n";
    auto write=[&](const QByteArray& bytes){QFile file(path);assert(file.open(QIODevice::WriteOnly|QIODevice::Truncate));assert(file.write(bytes)==bytes.size());file.close();assert(file.setPermissions(QFile::ReadOwner|QFile::WriteOwner));};
    write(original);manager.reset(new AvatarBookmarks);
    auto publish=[&](const QString& kind){const auto command=request(),packet=test.featurePicoAvatarBookmarks(command);assert(!packet.isEmpty());
        std::cout<<QJsonDocument(QJsonObject::fromVariantMap({{"kind",kind},{"request",command},{"packet",packet}})).toJson(QJsonDocument::Compact).constData()<<'\n';
        assert(test.featurePicoAvatarBookmarks(command).isEmpty());return packet;};
    const auto baseline=publish("original");const auto bytesBefore=baseline.value("source").toMap().value("storage").toMap().value("rawBase64");
    publish("read-only");QFile unchanged(path);assert(unchanged.open(QIODevice::ReadOnly)&&unchanged.readAll()==original);unchanged.close();
    const auto owned="e2e-"+QString(32,'d');manager->addBookmarkInternal(owned);publish("saved");
    manager->removeBookmarkInternal(owned);const auto restored=publish("deleted");
    assert(restored.value("source").toMap().value("storage").toMap().value("rawBase64")!=bytesBefore); // Original writer canonicalizes; no exact byte-restoration claim.
    write("{\"foreign\":true}\n");assert(test.featurePicoAvatarBookmarks(request()).isEmpty()); // Cache equality never substitutes physical bytes.
    write(original);assert(!test.featurePicoAvatarBookmarks(request()).isEmpty());
    const auto backup=path+".owned-backup";assert(QFile::rename(path,backup));assert(QFile::link(backup,path));assert(test.featurePicoAvatarBookmarks(request()).isEmpty());assert(QFile::remove(path));assert(QFile::rename(backup,path));
    assert(::link(QFile::encodeName(path).constData(),QFile::encodeName(backup).constData())==0);assert(test.featurePicoAvatarBookmarks(request()).isEmpty());assert(QFile::remove(backup));
    assert(QFile::setPermissions(path,QFile::ReadOwner|QFile::WriteOwner|QFile::WriteGroup));assert(test.featurePicoAvatarBookmarks(request()).isEmpty());assert(QFile::setPermissions(path,QFile::ReadOwner|QFile::WriteOwner));
    auto savedMap=manager->_bookmarks;manager->_bookmarks["large"]=QString(100000,'x');manager->persistToFile();assert(test.featurePicoAvatarBookmarks(request()).isEmpty());manager->_bookmarks=savedMap;write(original);
    const auto sequence=test._featureAvatarBookmarksSequence;
    std::thread blocked([&]{assert(test.featurePicoAvatarBookmarks(request()).isEmpty());});blocked.join();assert(test._featureAvatarBookmarksSequence==sequence);
    assert(test.featurePicoAvatarBookmarks(request()).isEmpty());turn();publish("after-dispatch-retired");
    // Actual dependency worker is blocked: 200-ms queue bound, no late capture.
    QThread worker;worker.start();manager->moveToThread(&worker);QSemaphore entered,release;
    assert(QMetaObject::invokeMethod(manager.data(),[&]{entered.release();release.acquire();},Qt::QueuedConnection));assert(entered.tryAcquire(1,1000));
    QElapsedTimer elapsed;elapsed.start();assert(test.featurePicoAvatarBookmarks(request()).isEmpty()&&elapsed.elapsed()<1000);
    assert(test.featurePicoAvatarBookmarks(request()).isEmpty());release.release();
    QSemaphore returned;assert(QMetaObject::invokeMethod(manager.data(),[&]{manager->moveToThread(app.thread());returned.release();},Qt::QueuedConnection));assert(returned.tryAcquire(1,1000));worker.quit();assert(worker.wait(1000));publish("after-worker-retired");
    const auto birth=test._featureAvatarBookmarkBirth;manager.reset(new AvatarBookmarks);publish("replacement");assert(test._featureAvatarBookmarkBirth!=birth);
    assert(QFile::remove(path));manager->_bookmarks.clear();publish("absent");
    while(test._featureAvatarBookmarksRequests.size()<512){assert(!test.featurePicoAvatarBookmarks(request()).isEmpty());}
    assert(test.featurePicoAvatarBookmarks(request()).isEmpty());manager.reset();
}
#include "test.moc"
