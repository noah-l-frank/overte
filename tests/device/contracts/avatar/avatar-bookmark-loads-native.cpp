// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual Qt connection/functor plus complete original Bookmark/MyAvatar call
// bodies. Model loading, wearable operations and application services below
// are explicit actors; the cached-sameURL signal branch is original C++.
#include <QCoreApplication>
#include <QDebug>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSemaphore>
#include <QSharedPointer>
#include <QTimer>
#include <QUrl>
#include <cassert>
#include <iostream>
#include <thread>
#include "tests/device/native/AvatarBookmarkLoads.h"
#include "tests/device/native/AudioSettingsQueue.h"
class MyAvatar:public QObject {Q_OBJECT
public:
    void useFullAvatarURL(const QUrl&,const QString& name=QString());
    QVariantMap e2eAvatarLoads(){return {{"instance",avatarBirthActor}};}
    QUuid getSessionUUID()const{return QUuid("77777777-7777-4777-8777-777777777777");}
    QUrl getSkeletonModelURL()const{return skeletonActor;}
    void setSkeletonModelURL(const QUrl& url){skeletonActor=url;++modelRequestsActor;}
    void clearWornAvatarEntities(){++clearsActor;}
    void setAvatarScale(float value){scaleActor=value;}
    QUrl _fullAvatarURLFromPreferences,skeletonActor;QString _fullAvatarModelName,avatarBirthActor{QUuid::createUuid().toString(QUuid::Id128)};
    int modelRequestsActor{0},clearsActor{0};float scaleActor{1};
signals:void onLoadComplete();
};
class AvatarManager {public:std::shared_ptr<MyAvatar> avatar;std::shared_ptr<MyAvatar> getMyAvatar(){return avatar;}};
using EntityTreePointer=std::shared_ptr<int>;
class EntityTreeRenderer {public:EntityTreePointer getTree(){return {};}};
class AvatarBookmarks:public QObject {Q_OBJECT
public:
    void loadBookmark(const QString&);void loadBookmarkInternal(const QString&);QVariantMap e2eBookmarkLoads()const;
    QVariantMap _bookmarks;overte::e2e::AvatarBookmarkLoads _featureBookmarkLoads;
    const QString ENTRY_AVATAR_URL="avatarUrl",ENTRY_AVATAR_SCALE="avatarScale",ENTRY_AVATAR_ENTITIES="avatarEntites";
signals:void bookmarkLoaded(const QString&);
};
QSharedPointer<AvatarBookmarks> bookmarks;QSharedPointer<AvatarManager> avatars(new AvatarManager);QSharedPointer<EntityTreeRenderer> renderer(new EntityTreeRenderer);
class DependencyManager {public:template<class T>static bool isSet(){return !get<T>().isNull();}template<class T>static QSharedPointer<T>get();};
template<>QSharedPointer<AvatarBookmarks>DependencyManager::get<AvatarBookmarks>(){return bookmarks;}
template<>QSharedPointer<AvatarManager>DependencyManager::get<AvatarManager>(){return avatars;}
template<>QSharedPointer<EntityTreeRenderer>DependencyManager::get<EntityTreeRenderer>(){return renderer;}
class ScriptPermissions {public:enum class Permission{SCRIPT_PERMISSION_GET_AVATAR_URL};static bool isCurrentScriptAllowed(Permission){return true;}};
class UserActivityLogger {public:static UserActivityLogger&getInstance(){static UserActivityLogger value;return value;}void changedModel(const QString&,const QString&){++callsActor;}int callsActor{0};};
QVariantList entitiesActor;int additionsActor=0;
void addAvatarEntities(const QVariantList& entities){entitiesActor=entities;++additionsActor;}
#define BLOCKING_INVOKE_METHOD(...) qFatal("Unexpected foreign-thread mutation in bookmark-load proof")
#define qCDebug(...) qDebug()
struct Lifecycle {QVariantMap snapshot()const{return {{"active",true}};}};
class TestScriptingInterface:public QObject {public:
    QVariantMap featurePicoAvatarBookmarkLoads(const QVariantMap&);
    QString _testResultsLocation{"private-results"};std::unique_ptr<Lifecycle>_featureLifecycle{new Lifecycle};
    std::shared_ptr<overte::e2e::AudioSettingsQueue>_featureAvatarBookmarkLoadsQueue{new overte::e2e::AudioSettingsQueue};
    quint64 _featureAvatarBookmarkLoadsSequence{0};QSet<QString>_featureAvatarBookmarkLoadsRequests;QPointer<QObject>_featureAvatarBookmarkLoadObject;
    QString _featureAvatarBookmarkLoadBirth,_featureObservationInstance{QString(32,'a')};
};
#include "actual-avatar-bookmark-loads.inc"
void turn(){QTimer::singleShot(1,[]{QCoreApplication::quit();});QCoreApplication::exec();}
int main(int argc,char**argv){
    QCoreApplication app(argc,argv);TestScriptingInterface source;int requests=0;
    const auto request=[&]{return QVariantMap{{"schemaVersion",1},{"commandId",QString::number(++requests,16).rightJustified(32,'0')},{"action","feature-pico-avatar-bookmark-loads-observe"}};};
    auto avatar=std::make_shared<MyAvatar>();avatars->avatar=avatar;bookmarks.reset(new AvatarBookmarks);
    const QUrl a("https://controlled.invalid/owned/a.fst"),b("https://controlled.invalid/owned/b.fst");
    avatar->skeletonActor=a;avatar->_fullAvatarURLFromPreferences=a;
    bookmarks->_bookmarks["same"] = QVariantMap{{"avatarUrl",a.toString()},{"avatarScale",1.5},{"avatarEntites",QVariantList{}}};
    if(!app.arguments().contains("--testScript")){
        bookmarks->loadBookmark("same");assert(avatar->scaleActor==1.5f);assert(bookmarks->e2eBookmarkLoads().isEmpty());
        assert(source.featurePicoAvatarBookmarkLoads(request()).isEmpty());bookmarks.reset();avatars->avatar.reset();return 0;
    }
    auto publish=[&](const QString& kind){const auto command=request(),packet=source.featurePicoAvatarBookmarkLoads(command);assert(!packet.isEmpty());
        std::cout<<QJsonDocument(QJsonObject::fromVariantMap({{"kind",kind},{"request",command},{"packet",packet}})).toJson(QJsonDocument::Compact).constData()<<'\n';
        assert(source.featurePicoAvatarBookmarkLoads(command).isEmpty());return packet.value("source").toMap().value("loads").toMap();};
    publish("baseline");int loaded=0;QVariantMap inside;
    QObject::connect(bookmarks.data(),&AvatarBookmarks::bookmarkLoaded,[&](const QString&){++loaded;inside=bookmarks->e2eBookmarkLoads();});
    bookmarks->loadBookmark("same");assert(loaded==1&&avatar->scaleActor==1.5f&&avatar->clearsActor==1&&additionsActor==1&&entitiesActor.isEmpty());
    assert(avatar->modelRequestsActor==0&&UserActivityLogger::getInstance().callsActor==0);
    auto row=inside.value("rows").toList().last().toMap();assert(row.value("active").toInt()==1&&row.value("captureAlive").toBool()&&!row.value("completed").toBool());
    const auto same=publish("cached-same-url");row=same.value("rows").toList().last().toMap();assert(!row.value("captureAlive").toBool()&&row.value("active").toInt()==0&&row.value("completed").toBool()&&row.value("disconnected").toBool());
    assert(row.value("avatarInstance").toString()==avatar->avatarBirthActor&&row.value("sessionId").toString()==avatar->getSessionUUID().toString(QUuid::WithoutBraces));
    emit avatar->onLoadComplete();assert(loaded==1); // Original disconnect prevents duplicate effects.
    bookmarks->loadBookmark("missing-entry");assert(bookmarks->e2eBookmarkLoads().value("rows").toList().size()==1);
    bookmarks->_bookmarks["pending"] = QVariantMap{{"avatarUrl",b.toString()},{"avatarScale",.75},{"avatarEntites",QVariantList{}}};
    bookmarks->loadBookmark("pending");assert(loaded==1&&avatar->modelRequestsActor==1&&avatar->scaleActor==1.5f);
    auto pending=publish("pending-original-load");row=pending.value("rows").toList().last().toMap();assert(row.value("captureAlive").toBool()&&row.value("dispatches").toInt()==0);
    std::weak_ptr<MyAvatar> weak=avatar;QPointer<MyAvatar> actualWeak=avatar.get();avatars->avatar.reset();avatar.reset();assert(!weak.expired()&&!actualWeak.isNull());
    // The *original* contextless functor keeps MyAvatar alive while pending.
    auto retained=weak.lock();avatars->avatar=retained;emit retained->onLoadComplete();assert(loaded==2&&retained->scaleActor==.75f&&retained->clearsActor==2&&additionsActor==2);
    auto finished=publish("original-load-callback");assert(!finished.value("rows").toList().last().toMap().value("captureAlive").toBool());
    avatars->avatar.reset();retained.reset();assert(weak.expired()&&actualWeak.isNull());publish("original-sender-dead");
    // Bounded foreign observer dispatch cannot block the GUI or adopt late data.
    const auto sequence=source._featureAvatarBookmarkLoadsSequence;
    std::thread blocked([&]{assert(source.featurePicoAvatarBookmarkLoads(request()).isEmpty());});blocked.join();assert(source._featureAvatarBookmarkLoadsSequence==sequence);
    assert(source.featurePicoAvatarBookmarkLoads(request()).isEmpty());turn();publish("observer-dispatch-retired");
    // Diagnostic affinity seam: the real observer's existing weak queue also
    // refuses a blocked manager worker and discards its late original result.
    QThread worker;worker.start();bookmarks->moveToThread(&worker);QSemaphore entered,release;
    assert(QMetaObject::invokeMethod(bookmarks.data(),[&]{entered.release();release.acquire();},Qt::QueuedConnection));assert(entered.tryAcquire(1,1000));
    QElapsedTimer elapsed;elapsed.start();assert(source.featurePicoAvatarBookmarkLoads(request()).isEmpty()&&elapsed.elapsed()<1000);
    assert(source.featurePicoAvatarBookmarkLoads(request()).isEmpty());release.release();QSemaphore returned;
    assert(QMetaObject::invokeMethod(bookmarks.data(),[&]{bookmarks->moveToThread(app.thread());returned.release();},Qt::QueuedConnection));
    assert(returned.tryAcquire(1,1000));worker.quit();assert(worker.wait(1000));publish("observer-worker-retired");
    const auto birth=source._featureAvatarBookmarkLoadBirth;bookmarks.reset(new AvatarBookmarks);publish("replacement");assert(source._featureAvatarBookmarkLoadBirth!=birth);
    // Source overflow refuses observation; ordinary product loading is unchanged.
    auto last=std::make_shared<MyAvatar>();avatars->avatar=last;last->skeletonActor=a;last->_fullAvatarURLFromPreferences=a;
    bookmarks->_bookmarks["same"]=QVariantMap{{"avatarUrl",a.toString()},{"avatarScale",1.25}};
    for(int index=0;index<129;++index){bookmarks->loadBookmark("same");}assert(last->scaleActor==1.25f&&last->clearsActor==129);
    assert(source.featurePicoAvatarBookmarkLoads(request()).isEmpty());bookmarks.reset();avatars->avatar.reset();
}
#include "test.moc"
