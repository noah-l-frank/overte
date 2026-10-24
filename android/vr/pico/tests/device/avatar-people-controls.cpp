// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original AvatarApp.qml through a real Loader, original Pico touch bodies and
// whole NativeFieldInput. Initial script/context services are declared actors;
// emitted messages prove normal UI routing, never a loaded model or HTTP effect.
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickItem>
#include <QQuickRenderControl>
#include <QSignalSpy>
#include <QTest>
#include <QJsonDocument>
#include <QProcess>
#include <QTextStream>
#include <cassert>
#include <PointerEvent.h>
#include <QMouseEvent>
#include <QTouchDevice>
#include <QTouchEvent>
#include <QWheelEvent>
#include <map>
#include <unistd.h>
#if defined(AVATAR_ORIGINAL_PARENT_SERVICE)
#include <poll.h>
#include <cstdio>
#endif
#include "actual-pointer-route.inc"
#include "tests/device/native/NormalControlUi.h"
#include "actual-avatar-preference-host.inc"
// Unrelated NavigationUi services keep their declared unavailable registry.
#define AVATAR_ORIGINAL_PLACES
#define DependencyManager AvatarObservationDependencies
#include "avatar-navigation-observation-seams.h"
#include "actual-avatar-observe.inc"
#undef DependencyManager
#include "avatar-bookmark-store-actor.h"
#include "actual-avatar-preference-observer.inc"
int main(int argc,char**argv) {
    HostApplication app(argc,argv);::umask(0077);using namespace overte::e2e;
    overte::pico::e2e::NavigationUi ui;
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
    const QString nativeCallerProfile="original-model-persistence";
#else
    const QString nativeCallerProfile="preference-noop";
#endif
    if(!app.arguments().contains("--testScript")){
        const auto ordinary=ui.observe(nullptr,nullptr,false);assert(!ordinary.value("ready").toBool() && ordinary.value("controls").toArray().isEmpty());
        assert(!ui.apply(nullptr,nullptr,false,{}, {}, {}, {}).value("performed").toBool());return 0;}
    const auto path=app.arguments().at(app.arguments().size()-2),imports=app.arguments().last();
    PathUtils::scripts=QUrl::fromLocalFile(path+"/scripts/");PathUtils::qml=QUrl::fromLocalFile(path+"/interface/resources/qml/");
    qmlRegisterModule("Hifi",1,0);qmlRegisterModule("TabletScriptingInterface",1,0);
    QQmlEngine engine;engine.addImportPath(path+"/interface/resources/qml");engine.addImportPath(imports);
    engine.rootContext()->setContextProperty("HMD",QVariantMap{{"active",true},{"mounted",true}});
    engine.rootContext()->setContextProperty("AddressManager",QVariantMap{{"isConnected",true}});
    engine.rootContext()->setContextProperty("Entities",QVariant::fromValue(engine.evaluate("({canRezAvatarEntities:function(){return true;},getEntityProperties:function(){return {};},getJointNames:function(){return [];}})")));
    engine.rootContext()->setContextProperty("MyAvatar",QVariant::fromValue(engine.evaluate("({getJointNames:function(){return ['Hips'];}})")));
    engine.rootContext()->setContextProperty("actualAvatarUrl",PathUtils::qmlUrl("hifi/AvatarApp.qml"));
    QQuickRenderControl renderControl;QQuickWindow window(&renderControl);window.resize(640,1000);window.contentItem()->setSize(QSizeF(640,1000));
    QQmlComponent loaderComponent(&engine);loaderComponent.setData("import QtQuick 2.7; Loader { width:640; height:1000; source:actualAvatarUrl }",QUrl::fromLocalFile(path+"/android/vr/pico/tests/device/declared-avatar-loader.qml"));
    QScopedPointer<QObject> loaded(loaderComponent.create());auto root=qobject_cast<QQuickItem*>(loaded.data());
    if(!root){qFatal("%s",qPrintable(loaderComponent.errorString()));}root->setParentItem(window.contentItem());
    QTest::qWait(50);auto page=qobject_cast<QQuickItem*>(root->property("item").value<QObject*>());assert(page);
    QQmlComponent wrongType(&engine);wrongType.setData("import QtQuick 2.7;Item {id:root;width:640;height:1000}",PathUtils::qmlUrl("hifi/AvatarApp.qml"));
    QScopedPointer<QObject> wrongObject(wrongType.create());assert(wrongObject);assert(avatarPeopleControlId(qobject_cast<QQuickItem*>(wrongObject.data())).isEmpty());
    QSignalSpy messages(page,SIGNAL(sendToScript(QVariant)));
    QTemporaryDir bookmarkProfile;assert(bookmarkProfile.isValid());assert(QFile::setPermissions(bookmarkProfile.path(),QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner));
    avatar_bookmark_host::PathUtils::profile=bookmarkProfile.path();
    QFile originalFile(bookmarkProfile.path()+"/avatarbookmarks.json");assert(originalFile.open(QIODevice::WriteOnly));
    const auto unowned=QJsonDocument(QJsonObject{{"unowned",QJsonObject{{"version",3},{"avatarUrl","qrc:/meshes/unowned.fst"},{"avatarScale",1},{"avatarEntites",QJsonArray{}}}}}).toJson();
    assert(originalFile.write(unowned)==unowned.size());originalFile.close();avatar_bookmark_host::AvatarBookmarks nativeBookmarks;QJsonArray originalBookmarkStorage,originalBookmarkLoads;
    const auto nativeAvatar=avatar_bookmark_host::DependencyManager::get<avatar_bookmark_host::AvatarManager>()->getMyAvatar();
    QTemporaryDir preferenceProfile;assert(preferenceProfile.isValid());
    assert(QFile::setPermissions(preferenceProfile.path(),QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner));
    app.setOrganizationName("OwnedAvatarFavoriteHost");app.setApplicationName("settings");
    QSettings::setDefaultFormat(JSON_FORMAT);QSettings::setPath(JSON_FORMAT,QSettings::UserScope,preferenceProfile.path());
    auto preferenceManager=::DependencyManager::set<Setting::Manager>();
    preferenceManager->setValue("unrelated",QByteArray("untouched"));SettingsTests::flush(preferenceManager.data());
    ::DependencyManager::set<::AvatarManager>(nativeAvatar);
    // Complete original MyAvatar URL/model-setter/save callers establish the
    // actual initial Handle/cache/writer state before the original baseline.
    // Base Avatar, Skeleton/scene inputs and completion remain declared actors.
    nativeAvatar->useFullAvatarURL(QUrl("qrc:/meshes/defaultAvatar_full.fst"));
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
    nativeAvatar->completeDeclaredModel();
#endif
    TestScriptingInterface preferenceObserver;quint64 preferenceNonce=0;QJsonArray originalFavoritePreferences;
    auto physicalPreferences=[&]{QFile file(preferenceManager->fileName());assert(file.open(QIODevice::ReadOnly));
        const auto bytes=file.read(65537);assert(bytes.size()<=65536 && file.atEnd());return QString::fromLatin1(bytes.toBase64());};
    QJsonArray preferenceSettleOriginals;
    QFile unsettledTrace(qEnvironmentVariable("OVERTE_AVATAR_NATIVE_TRACE")+".unsettled.jsonl");
    QFile observationJournal(qEnvironmentVariable("OVERTE_AVATAR_NATIVE_TRACE")+".originals.jsonl");QElapsedTimer observationClock;observationClock.start();int observationCount=0;
    auto journalOriginal=[&](const QString& kind,const QJsonObject& source){
        if(!observationJournal.isOpen()){assert(observationJournal.open(QIODevice::WriteOnly|QIODevice::NewOnly));assert(observationJournal.setPermissions(QFile::ReadOwner|QFile::WriteOwner));}
        const QJsonObject event{{"avatarObservationJournalVersion",1},{"sequence",++observationCount},{"kind",kind},{"source",source},
            {"nativeMonotonicNs",static_cast<double>(observationClock.nsecsElapsed())},{"capturedEpochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},{"processId",QCoreApplication::applicationPid()}};
        const auto raw=QJsonDocument(event).toJson(QJsonDocument::Compact)+'\n';assert(observationCount<=512 && raw.size()<=65536 && observationJournal.size()+raw.size()<=16*1024*1024);
        assert(observationJournal.write(raw)==raw.size() && observationJournal.flush() && ::fsync(observationJournal.handle())==0);
    };
    auto preferences=[&](bool settle=false){QElapsedTimer waiting;waiting.start();for(int attempt=0;attempt<83;++attempt){const QVariantMap request{{"schemaVersion",1},{"commandId",QString::number(++preferenceNonce,16).rightJustified(32,'0')},
        {"action","feature-pico-avatar-preferences-observe"}};
        const auto packet=preferenceObserver.featurePicoAvatarPreferences(request);
        const auto observed=QJsonObject{{"request",QJsonObject::fromVariantMap(request)},{"packet",QJsonObject::fromVariantMap(packet)}};
        journalOriginal("preferences",observed);assert(!packet.isEmpty());
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
        journalOriginal("model-connections",QJsonObject::fromVariantMap(nativeAvatar->e2eModelConnections()));
#endif
        assert(preferenceObserver.featurePicoAvatarPreferences(request).isEmpty());
        const auto actual=packet.value("source").toMap().value("snapshot").toMap();
        if(!settle || (actual.value("cacheMatchesWriter")==QVariant(true) && actual.value("writer").toMap().value("matchesPhysical")==QVariant(true))) {return observed;}
        // Every unsettled actual query remains original evidence. The reader
        // never calls sync()/reload()/forceSave() to manufacture persistence.
        if(!unsettledTrace.isOpen()){assert(unsettledTrace.open(QIODevice::WriteOnly|QIODevice::NewOnly));assert(unsettledTrace.setPermissions(QFile::ReadOwner|QFile::WriteOwner));}
        const auto raw=QJsonDocument(observed).toJson(QJsonDocument::Compact)+'\n';assert(raw.size()<=65536 && unsettledTrace.size()+raw.size()<=16*1024*1024);
        assert(unsettledTrace.write(raw)==raw.size() && unsettledTrace.flush() && ::fsync(unsettledTrace.handle())==0);
        preferenceSettleOriginals.append(observed);assert(waiting.elapsed()<20000);QTest::qWait(10);
        }qFatal("Original Settings writer did not settle within its existing bound");return QJsonObject{};};
    const auto originalDataPreferences=preferences(true);const auto originalDataPhysical=physicalPreferences();
    const auto avatar=nativeAvatar;const auto model=nativeAvatar->getSkeletonModel();
#include "actual-avatar-native-data.inc"
    auto& typedOwner=*preferenceObserver._featureAvatarPreferences;
    const auto originalUrlHandle=typedOwner.remember(nativeAvatar.get(),nativeAvatar->_fullAvatarURLSetting,typedHandles);
    assert(originalUrlHandle.valid());
    auto lastOwnedHandle=originalUrlHandle;
    auto currentHandle=[&]{return typedOwner.remember(nativeAvatar.get(),nativeAvatar->_fullAvatarURLSetting,typedHandles);};
    auto guardData=[&]{const auto actual=currentHandle();assert(typedOwner.unchanged(lastOwnedHandle,actual));return actual.original();};
    auto ownedEffect=[&](const QJsonObject& before,const QJsonObject& after,const QString& beforePhysical,const QString& afterPhysical,bool uri,bool scale){
        const auto current=currentHandle();assert(typedOwner.otherSettings(lastOwnedHandle,current));
        const auto first=before.value("packet").toObject().value("source").toObject().value("snapshot").toObject();
        const auto last=after.value("packet").toObject().value("source").toObject().value("snapshot").toObject();
        auto a=first.value("cache").toObject().value("native").toObject(),b=last.value("cache").toObject().value("native").toObject();
        auto x=a.value("live").toObject(),y=b.value("live").toObject();
        if(uri){x.remove("preferenceUrl");y.remove("preferenceUrl");}
        if(scale){for(const auto& key:{"scale","targetScale"}){x.remove(key);y.remove(key);}}
        assert(x==y);auto handlesA=a.value("handles").toObject().value("handles").toObject(),handlesB=b.value("handles").toObject().value("handles").toObject();
        const auto key=handlesB.value("fullAvatarURL").toObject().value("key").toString();assert(!key.isEmpty());
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
        if(uri){
            const auto handle=handlesB.value("fullAvatarURL").toObject();assert(handle.value("initialized").toBool() && handle.value("managerBound").toBool() && handle.value("isSet").toBool());
            assert(last.value("cache").toObject().value("rows").toObject().value(key)==handle.value("value"));
            const auto actualUrl=b.value("live").toObject().value("preferenceUrl").toString();
            const auto persisted=actualUrl==::AvatarData::defaultFullAvatarModelUrl().toString() ? QString() : actualUrl;
            const auto physical=QJsonDocument::fromJson(QByteArray::fromBase64(afterPhysical.toLatin1())).object();assert(physical.value(key)==QJsonValue(persisted));
        }
#endif
        if(uri){handlesA.remove("fullAvatarURL");handlesB.remove("fullAvatarURL");}assert(handlesA==handlesB);
        auto diskA=QJsonDocument::fromJson(QByteArray::fromBase64(beforePhysical.toLatin1())).object(),diskB=QJsonDocument::fromJson(QByteArray::fromBase64(afterPhysical.toLatin1())).object();
        if(uri){diskA.remove(key);diskB.remove(key);}assert(diskA==diskB);
        if(!uri){assert(beforePhysical==afterPhysical);assert(first.value("mutationSequence")==last.value("mutationSequence"));}
        lastOwnedHandle=current;
    };
    const auto originalDataBookmarks=QJsonObject::fromVariantMap(nativeBookmarks.e2eBookmarkStorage());assert(!originalDataBookmarks.isEmpty());
    int originalLoaded=0,cachedOriginalLoads=0,declaredModelCompletions=0;
    QObject::connect(&nativeBookmarks,&avatar_bookmark_host::AvatarBookmarks::bookmarkLoaded,[&](const QString&){++originalLoaded;});
    overte::pico::e2e::NavigationUi actualObserver;
    auto capture=[&]{return ui.observe(root,&window,true);};
    auto originalCapture=[&]{return actualObserver.observe(root,&window,true);};
    const auto before=capture();for(const auto& raw:before.value("controls").toArray()){assert(!raw.toObject().value("inputReady").toBool());}
    QProcess backend;backend.setProcessChannelMode(QProcess::ForwardedErrorChannel);
    backend.start("node",QStringList{path+"/android/vr/pico/tests/device/avatar-original-backend.js",path,"--native-bookmarks","--native-avatar"});assert(backend.waitForStarted(2000));const auto backendProcessId=backend.processId();
    QJsonArray normalInputJournal,normalMessageJournal,originalAvatarInputs;
    auto response=[&]{for(int calls=0;calls<32;++calls){if(!backend.canReadLine()){assert(backend.waitForReadyRead(2000));}const auto raw=backend.readLine();auto value=QJsonDocument::fromJson(raw).object();assert(!value.isEmpty());
        if(value.contains("nativeAvatarCall")){
            guardData();
            const auto call=value.value("nativeAvatarCall").toObject();assert(call.size()==2);
            const auto before=preferences();const auto beforePhysical=physicalPreferences();const auto method=call.value("method").toString();
            if(method=="useFullAvatarURL"){assert(call.value("value").isString());const auto count=nativeAvatar->modelRequestsActor;nativeAvatar->useFullAvatarURL(QUrl(call.value("value").toString()));
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
                if(nativeAvatar->modelRequestsActor!=count){nativeAvatar->completeDeclaredModel();}
#endif
            }
            else {assert(method=="setAvatarScale" && call.value("value").isDouble());nativeAvatar->setAvatarScale(call.value("value").toDouble());}
            const auto after=preferences(true);const auto afterPhysical=physicalPreferences();
            ownedEffect(before,after,beforePhysical,afterPhysical,method=="useFullAvatarURL",method=="setAvatarScale");
            originalAvatarInputs.append(QJsonObject{{"call",call},{"before",before},{"after",after},
                {"beforePhysicalBase64",beforePhysical},{"afterPhysicalBase64",afterPhysical},
                {"normalInput",normalInputJournal.size()},{"normalMessages",normalMessageJournal.size()}});
            const auto raw=QJsonDocument(QJsonObject{{"nativeAvatarReply",QJsonObject{{"avatarUrl",nativeAvatar->getFullAvatarURLFromPreferences().toString()},
                {"scale",nativeAvatar->getTargetScale()}}}}).toJson(QJsonDocument::Compact)+'\n';
            assert(backend.write(raw)==raw.size());assert(backend.waitForBytesWritten(2000));continue;
        }
        if(!value.contains("nativeBookmarkCall")){return value;}
        guardData();
        const auto call=value.value("nativeBookmarkCall").toObject();const auto method=call.value("method").toString(),name=call.value("name").toString();
        assert(nativeAvatar->getFullAvatarURLFromPreferences()==QUrl(call.value("avatarUrl").toString()));
        assert(qAbs(nativeAvatar->getTargetScale()-call.value("scale").toDouble())<.00001);
        nativeBookmarks.currentAvatarActor={{"version",3},{"avatarUrl",call.value("avatarUrl").toString()},{"avatarScale",call.value("scale").toDouble()},{"avatarEntites",QVariantList{}},{"avatarIcon",""}};
        QJsonObject nativeLoad;
        if(method=="save"){assert(name=="e2e-"+QString(32,'a'));nativeBookmarks.addBookmarkInternal(name);}
        else if(method=="delete"){assert(name=="e2e-"+QString(32,'a'));nativeBookmarks.removeBookmarkInternal(name);}
        else if(method=="load"){
            // Normal URL/scale already reached the original native methods.
            // Full model setter/completion remains a declared actor; the
            // whole Qt connection, cached signal and callback are original.
            assert(nativeAvatar->getFullAvatarURLFromPreferences()==QUrl(call.value("avatarUrl").toString()));
            assert(qAbs(nativeAvatar->getTargetScale()-call.value("scale").toDouble())<.00001);
            assert(nativeAvatar->_packedAvatarEntityData.isEmpty());const int requested=nativeAvatar->modelRequestsActor,loadedBefore=originalLoaded;
            const auto beforePhysical=physicalPreferences();const auto beforePreferences=preferences();const auto beforeLoads=QJsonObject::fromVariantMap(nativeBookmarks.e2eBookmarkLoads());
            nativeBookmarks.loadBookmark(name);
            if(nativeAvatar->modelRequestsActor!=requested){++declaredModelCompletions;nativeAvatar->completeDeclaredModel();}
            else{++cachedOriginalLoads;}
            assert(originalLoaded==loadedBefore+1);const auto observed=nativeBookmarks.e2eBookmarkLoads();assert(!observed.isEmpty());
            const auto afterPreferences=preferences(true);
            const auto afterPhysical=physicalPreferences();ownedEffect(beforePreferences,afterPreferences,beforePhysical,afterPhysical,true,true);
            originalFavoritePreferences.append(QJsonObject{{"cached",nativeAvatar->modelRequestsActor==requested},{"normalInput",normalInputJournal.size()},{"normalMessages",normalMessageJournal.size()},
                {"bookmarkName",name},{"avatarInstance",nativeAvatar->avatarBirthActor},{"before",beforePreferences},{"after",afterPreferences},
                {"beforePhysicalBase64",beforePhysical},{"afterPhysicalBase64",afterPhysical},
                {"beforeLoads",beforeLoads},{"afterLoads",QJsonObject::fromVariantMap(observed)}});
            originalBookmarkLoads.append(QJsonObject::fromVariantMap(observed));const auto work=observed.value("rows").toList().last().toMap();
            assert(!work.value("captureAlive").toBool()&&work.value("completed").toBool()&&work.value("disconnected").toBool()&&work.value("active").toInt()==0);
            nativeLoad={{"bookmarkLoaded",true},{"avatarUrl",nativeAvatar->skeletonActor.toString()},{"scale",nativeAvatar->getTargetScale()}};
        }
        else {assert(method=="get" || method=="all");}
        const auto actual=nativeBookmarks.e2eBookmarkStorage();assert(!actual.isEmpty());originalBookmarkStorage.append(QJsonObject::fromVariantMap(actual));
        const auto reply=QJsonDocument(QJsonObject{{"nativeBookmarkReply",QJsonObject{{"bookmarks",QJsonObject::fromVariantMap(nativeBookmarks.getBookmarks())},{"bookmark",QJsonObject::fromVariantMap(nativeBookmarks.getBookmarkInternal(name))},{"nativeLoad",nativeLoad}}}}).toJson(QJsonDocument::Compact)+'\n';
        assert(backend.write(reply)==reply.size());assert(backend.waitForBytesWritten(2000));
        }qFatal("Native bookmark call recursion exceeded its original host bound");return QJsonObject{};};
    auto applyProducer=[&](const QJsonObject& value){for(const auto& raw:value.value("qml").toArray()){QVariant actual=raw.toObject().toVariantMap();assert(QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,actual)));}};
    auto boot=response();assert(boot.value("source")==QJsonValue("hifi/AvatarApp.qml"));applyProducer(boot);
    int delivered=0;QJsonObject backendResult;
    auto drain=[&]{
        for(int pass=0;pass<8 && delivered<messages.size();++pass){QJsonArray pending;
            while(delivered<messages.size()){pending.append(QJsonObject::fromVariantMap(createVariant(messages.at(delivered++).first()).toMap()));}
            normalMessageJournal.append(pending);
            const auto raw=QJsonDocument(QJsonObject{{"messages",pending}}).toJson(QJsonDocument::Compact)+'\n';assert(backend.write(raw)==raw.size());assert(backend.waitForBytesWritten(2000));
            backendResult=response();applyProducer(backendResult);
        }if(delivered!=messages.size()){qFatal("Original UI bridge did not settle; last method %s",qPrintable(createVariant(messages.last().first()).toMap().value("method").toString()));}
    };
    drain();QTest::qWait(80);
    OffscreenQmlSurface surface(root,&window);int pointers=0;
    auto pointerAt=[&](QQuickItem* item,const QPointF& point){++pointers;const auto result=sendPointerAt(item,&surface,point);QCoreApplication::processEvents();return result;};
    auto click=[&](QQuickItem* item){return pointerAt(item,item->mapToScene(QPointF(item->width()/2,item->height()/2)));};
    auto row=[&](const QString& id){auto value=capture();assert(value.value("ready").toBool());for(const auto& raw:value.value("controls").toArray()){if(raw.toObject().value("id")==id){return raw.toObject();}}
        qFatal("missing %s: %s",qPrintable(id),QJsonDocument(value).toJson(QJsonDocument::Compact).constData());return QJsonObject();};
    auto command=[&](const QString& id,const QString& action,const QJsonValue& arg=QJsonValue()){
        const auto r=row(id),value=capture();QJsonObject c{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces)},{"bridgeId",value.value("bridgeId")},{"generation",value.value("generation")},{"sequence",value.value("lastCommandSequence").toInt()+1},{"observedElapsedMs",value.value("elapsedMs")},{"controlId",id},{"controlToken",r.value("token")},{"action",action}};
        if(action=="replace"){c["text"]=arg;}if(action=="set-value"){c["value"]=arg;}if(action=="scroll"){c["direction"]=arg;}return c;};
    auto input=[&](const QString& id,const QString& action,const QJsonValue& arg=QJsonValue()){
        const auto nativeBeforeInput=guardData();
        const auto sent=command(id,action,arg),observed=capture();
        const auto result=ui.apply(root,&window,true,sent,click,pointerAt,{});normalInputJournal.append(QJsonObject{{"command",sent},{"snapshot",observed},{"reply",result},{"nativeBeforeInput",QJsonObject::fromVariantMap(nativeBeforeInput)}});if(!result.value("performed").toBool()){qFatal("refused %s/%s",qPrintable(id),qPrintable(action));}drain();QTest::qWait(40);renderControl.polishItems();QCoreApplication::processEvents();};
#if defined(AVATAR_ORIGINAL_PARENT_SERVICE)
#include "avatar-parent-service.inc"
#endif
    assert(row("avatar.page").value("inputReady")==QJsonValue(false));
    auto actualObserved=originalCapture();assert(actualObserved.value("ready").toBool());
    assert(actualObserved.value("avatarPeopleControlsVersion")==QJsonValue(1));
    auto actualRow=[&](const QString& id){const auto value=originalCapture();assert(value.value("ready").toBool());
        for(const auto& raw:value.value("controls").toArray()){if(raw.toObject().value("id")==id){return raw.toObject();}}
        qFatal("Original observer missing %s",qPrintable(id));return QJsonObject();};
    assert(actualRow("avatar.url").value("inputReady")==QJsonValue(true));
    const auto actualToken=actualRow("avatar.url").value("token");page->setX(2);
    assert(actualRow("avatar.url").value("token")!=actualToken);page->setX(0);
    QJsonArray urls,snapshots,originalSnapshots;snapshots.append(capture());originalSnapshots.append(originalCapture());
    for(const auto& url:QStringList{"https://controlled.invalid/owned/avatar-a.fst","qrc:/meshes/defaultAvatar_full.fst"}) {
        input("avatar.url","activate");input("avatar.dialog.input","activate");input("avatar.dialog.input","replace",url);
        snapshots.append(capture());originalSnapshots.append(originalCapture());
        assert(row("avatar.dialog.input").value("text")==QJsonValue(url));assert(actualRow("avatar.dialog.input").value("text")==QJsonValue(url));input("avatar.dialog.confirm","activate");
        bool found=false;for(const auto& args:messages){const auto m=createVariant(args.first()).toMap();if(m.value("method")=="applyExternalAvatar" && m.value("avatarURL")==url){found=true;}}
        assert(found);urls.append(url);
    }
    QQuickItem* actualUrl=nullptr;
    std::function<void(QQuickItem*)> find=[&](QQuickItem* item){if(avatarPeopleControlId(item)=="avatar.url"){assert(!actualUrl);actualUrl=item;}for(auto child:item->childItems()){find(child);}};find(root);assert(actualUrl);
    auto held=command("avatar.url","activate");const auto token=row("avatar.url").value("token");const int prior=pointers;
    page->setX(2);assert(row("avatar.url").value("token")!=token);assert(!ui.apply(root,&window,true,held,click,pointerAt,{}).value("performed").toBool());page->setX(0);
    const auto sourceBeforeWindow=avatarPeopleControlSource(actualUrl,"avatar.url");
    QQuickRenderControl alternateRender;QQuickWindow alternateWindow(&alternateRender);alternateWindow.resize(640,1000);alternateWindow.contentItem()->setSize(QSizeF(640,1000));
    root->setParentItem(alternateWindow.contentItem());assert(avatarPeopleControlSource(actualUrl,"avatar.url")!=sourceBeforeWindow);
    assert(!ui.apply(root,&window,true,held,click,pointerAt,{}).value("performed").toBool());root->setParentItem(window.contentItem());
    // Each refusal gets a fresh original command; sequence replay is not the
    // reason disabled, foreign-overlay or clipped controls are rejected.
    page->setEnabled(false);assert(!ui.apply(root,&window,true,command("avatar.url","activate"),click,pointerAt,{}).value("performed").toBool());page->setEnabled(true);
    QQmlComponent overlayComponent(&engine);overlayComponent.setData("import QtQuick 2.7; Rectangle {color:'red';width:640;height:1000;z:999}",{});
    QScopedPointer<QObject> overlayObject(overlayComponent.create());auto overlay=qobject_cast<QQuickItem*>(overlayObject.data());assert(overlay);overlay->setParentItem(window.contentItem());
    assert(!ui.apply(root,&window,true,command("avatar.url","activate"),click,pointerAt,{}).value("performed").toBool());overlay->setVisible(false);
    // A non-clipping foreign parent can have an input/drawn child beyond its
    // own bounds. Clipping and hidden/disabled children are measured by Qt.
    QQmlComponent outside(&engine);outside.setData("import QtQuick 2.7; Item {width:1;height:1;z:999;Rectangle {width:640;height:1000;color:'red';MouseArea{anchors.fill:parent}}}",{});
    QScopedPointer<QObject> outsideObject(outside.create());auto foreign=qobject_cast<QQuickItem*>(outsideObject.data());assert(foreign);foreign->setParentItem(window.contentItem());
    assert(!ui.apply(root,&window,true,command("avatar.url","activate"),click,pointerAt,{}).value("performed").toBool());foreign->setClip(true);
    const auto actualPoint=avatarPeopleActivatePoint(actualUrl,"avatar.url");assert(avatarPeopleOwnsPoint(actualUrl,&window,actualPoint));
    foreign->setClip(false);foreign->childItems().first()->setVisible(false);assert(avatarPeopleOwnsPoint(actualUrl,&window,actualPoint));
    foreign->childItems().first()->setVisible(true);foreign->childItems().first()->setEnabled(false);
    // A disabled foreign painted Rectangle still obscures the original field.
    assert(!avatarPeopleOwnsPoint(actualUrl,&window,actualPoint));
    foreign->setVisible(false);
    auto clipCommand=command("avatar.url","activate");QQuickItem clip(window.contentItem());clip.setClip(true);clip.setSize(QSizeF(1,1));root->setParentItem(&clip);
    assert(!ui.apply(root,&window,true,clipCommand,click,pointerAt,{}).value("performed").toBool());root->setParentItem(window.contentItem());
    // Actual negative-z opaque parent is conservatively blocked, even when its
    // low child claims input. A higher non-clipping foreign child also blocks.
    QQmlComponent negative(&engine);negative.setData("import QtQuick 2.7; Rectangle {width:640;height:1000;color:'blue';z:999;MouseArea{anchors.fill:parent;z:-1}}",{});
    QScopedPointer<QObject> negativeObject(negative.create());auto n=qobject_cast<QQuickItem*>(negativeObject.data());assert(n);n->setParentItem(window.contentItem());
    assert(!ui.apply(root,&window,true,command("avatar.url","activate"),click,pointerAt,{}).value("performed").toBool());n->setVisible(false);assert(prior==pointers);
    auto wrongVersion=command("avatar.url","activate");wrongVersion["schemaVersion"]=2;
    assert(!ui.apply(root,&window,true,wrongVersion,click,pointerAt,{}).value("performed").toBool());
    assert(ui.apply(root,&window,true,command("avatar.url","activate"),click,pointerAt,{}).value("performed").toBool());QTest::qWait(40);
    input("avatar.dialog.cancel","activate");
    const auto urlCalls=backendResult.value("avatarCalls");
    const QString ownedName="e2e-"+QString(32,'a'),aUrl="https://controlled.invalid/owned/avatar-a.fst",originalUrl="qrc:/meshes/defaultAvatar_full.fst";
    auto setUrl=[&](const QString& url){input("avatar.url","activate");input("avatar.dialog.input","activate");input("avatar.dialog.input","replace",url);input("avatar.dialog.confirm","activate");};
    auto findBookmark=[&]{const auto current=capture();QString found;
        for(const auto& raw:current.value("controls").toArray()){const auto r=raw.toObject();if(r.value("bookmarkName")==QJsonValue(ownedName)){assert(found.isEmpty());found=r.value("id").toString();}}
        assert(!found.isEmpty());return found;};
    setUrl(aUrl);input("avatar.bookmark.add","activate");input("avatar.dialog.input","activate");input("avatar.dialog.input","replace",ownedName);input("avatar.dialog.confirm","activate");
    assert(backendResult.value("bookmarks").toObject().value(ownedName).toObject().value("avatarScale")==QJsonValue(1));
    setUrl(originalUrl);const auto beforeDuplicate=nativeBookmarks.e2eBookmarkStorage();input("avatar.bookmark.add","activate");
    input("avatar.dialog.input","activate");input("avatar.dialog.input","replace",ownedName);
    assert(row("avatar.dialog.confirm").value("inputReady")==QJsonValue(false));const int duplicatePointers=pointers;
    assert(!ui.apply(root,&window,true,command("avatar.dialog.confirm","activate"),click,pointerAt,{}).value("performed").toBool());
    assert(pointers==duplicatePointers);input("avatar.dialog.cancel","activate");
    assert(nativeBookmarks.e2eBookmarkStorage().value("rawSha256")==beforeDuplicate.value("rawSha256"));setUrl(aUrl);
    input("avatar.settings","activate");snapshots.append(capture());originalSnapshots.append(originalCapture());
    input("avatar.scale","set-value",15.0);assert(qAbs(backendResult.value("scale").toDouble()-1.5)<.001);
    auto has=[&](const QString& id){for(const auto& raw:capture().value("controls").toArray()){if(raw.toObject().value("id")==id && raw.toObject().value("inputReady").toBool()){return true;}}return false;};
    for(int i=0;i<32&&!has("avatar.settings.confirm");++i){input("avatar.settings.scrollbar","scroll","down");}
    input("avatar.settings.confirm","activate");
    // Original QML updateCurrentAvatarInBookmarks has already requested the
    // matching favorite through whole avatarapp.js during normal UI updates.
    // Its same-URL completion came solely from the original MyAvatar branch.
    assert(cachedOriginalLoads>=1);
    setUrl(originalUrl);input(findBookmark(),"activate");input("avatar.dialog.confirm","activate");
    assert(backendResult.value("scale")==QJsonValue(1));assert(backendResult.value("avatarCalls").toArray().last()==QJsonValue(aUrl));
    assert(declaredModelCompletions>=1);
    setUrl(originalUrl);input("avatar.bookmark.manage","activate");
    QQuickItem* actualBookmark=nullptr;const auto bookmarkId=findBookmark();
    std::function<void(QQuickItem*)> locateBookmark=[&](QQuickItem* item){if(avatarPeopleControlId(item)==bookmarkId){assert(!actualBookmark);actualBookmark=item;}for(auto child:item->childItems()){locateBookmark(child);}};locateBookmark(root);assert(actualBookmark);
    const auto bookmarkPoint=avatarPeopleActivatePoint(actualBookmark,bookmarkId);assert(avatarPeopleOwnsPoint(actualBookmark,&window,bookmarkPoint));
    const int beforeForeign=pointers;
    for(const auto& qml:QList<QByteArray>{"import QtQuick 2.7;Rectangle {width:92;height:92;z:999;color:'#AFAFAF';opacity:.4;radius:5}",
            "import QtQuick 2.7;import stylesUit 1.0;HiFiGlyphs {width:92;height:92;z:999;text:'{';size:56;horizontalAlignment:Text.AlignHCenter}"}) {
        QQmlComponent foreignDecoration(&engine);foreignDecoration.setData(qml,QUrl::fromLocalFile(path+"/android/vr/pico/tests/device/declared-foreign-decoration.qml"));
        QScopedPointer<QObject> foreignObject(foreignDecoration.create());auto foreignItem=qobject_cast<QQuickItem*>(foreignObject.data());assert(foreignItem);
        foreignItem->setParentItem(actualBookmark->parentItem()->parentItem());assert(!avatarPeopleOwnsPoint(actualBookmark,&window,bookmarkPoint));
        assert(!ui.apply(root,&window,true,command(bookmarkId,"activate"),click,pointerAt,{}).value("performed").toBool());foreignItem->setVisible(false);
    }
    assert(pointers==beforeForeign);assert(avatarPeopleOwnsPoint(actualBookmark,&window,bookmarkPoint));
    input(bookmarkId,"activate");input("avatar.dialog.confirm","activate");
    assert(!backendResult.value("bookmarks").toObject().contains(ownedName));assert(backendResult.value("bookmarks").toObject().contains("unowned"));
    backend.closeWriteChannel();assert(backend.waitForFinished(2000));assert(backend.exitStatus()==QProcess::NormalExit && backend.exitCode()==0);
    QJsonObject originalDataAfter;int quietSamples=0;
    const auto tracePath=qEnvironmentVariable("OVERTE_AVATAR_NATIVE_TRACE");assert(!tracePath.isEmpty());
    QFile quietTrace(tracePath);assert(quietTrace.open(QIODevice::WriteOnly|QIODevice::NewOnly));
    assert(quietTrace.setPermissions(QFile::ReadOwner|QFile::WriteOwner));
    QElapsedTimer quietClock;quietClock.start();qint64 firstNative=-1,firstEpoch=-1;bool quietComplete=false;
    for(int attempt=0;attempt<83;++attempt){
        const auto currentUrlHandle=typedOwner.remember(nativeAvatar.get(),nativeAvatar->_fullAvatarURLSetting,typedHandles);
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
        assert(typedOwner.originalData(originalUrlHandle,currentUrlHandle));
#else
        assert(typedOwner.unchanged(originalUrlHandle,currentUrlHandle));
#endif
        const auto pref=preferences(),book=QJsonObject::fromVariantMap(nativeBookmarks.e2eBookmarkStorage()),work=QJsonObject::fromVariantMap(nativeBookmarks.e2eBookmarkLoads());
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
        const auto modelConnections=QJsonObject::fromVariantMap(nativeAvatar->e2eModelConnections());
#endif
        const auto physical=physicalPreferences();const qint64 nativeNs=quietClock.nsecsElapsed(),epoch=QDateTime::currentMSecsSinceEpoch();
        assert(!book.isEmpty()&&!work.isEmpty());if(firstNative<0){firstNative=nativeNs;firstEpoch=epoch;}
        originalDataAfter=QJsonObject{{"preferences",pref},{"bookmarks",book},{"loads",work},{"settingsRawBase64",physical}};
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
        originalDataAfter["modelConnections"]=modelConnections;constexpr int quietVersion=2;
#else
        constexpr int quietVersion=1;
#endif
        const auto frame=QJsonObject{{"avatarOriginalDataQuietVersion",quietVersion},{"sequence",++quietSamples},{"nativeMonotonicNs",static_cast<double>(nativeNs)},
            {"capturedNativeEpochMs",static_cast<double>(epoch)},{"data",originalDataAfter}};
        const auto raw=QJsonDocument(frame).toJson(QJsonDocument::Compact)+'\n';assert(quietTrace.write(raw)==raw.size());assert(quietTrace.flush());assert(::fsync(quietTrace.handle())==0);
#if defined(AVATAR_ORIGINAL_MODEL_PERSISTENCE)
        assert(!modelConnections.isEmpty());for(const auto& value:modelConnections.value("rows").toArray()){const auto row=value.toObject();assert(row.value("completed").toBool() && row.value("disconnected").toBool() && !row.value("captureAlive").toBool() && row.value("active").toInt()==0);}
#endif
        // Measured feedback from the independent existing host receipt reader.
        // This never supplies data or replaces a native original observation.
        QFile received(tracePath.left(tracePath.lastIndexOf('.'))+".host-receipts.jsonl");
        if(received.open(QIODevice::ReadOnly)){
            const auto observedBytes=received.read(16*1024*1024+1);assert(observedBytes.size()<=16*1024*1024);
            const auto lines=observedBytes.left(observedBytes.lastIndexOf('\n')+1).split('\n');QJsonObject first,last;
            for(const auto& line:lines){if(line.isEmpty())continue;const auto row=QJsonDocument::fromJson(line).object();assert(!row.isEmpty());if(first.isEmpty())first=row;last=row;}
            if(!first.isEmpty()&&last.value("sequence")==QJsonValue(quietSamples)
                    && last.value("capturedHostMonotonicNs").toDouble()-first.value("capturedHostMonotonicNs").toDouble()>=3000000000.0
                    && nativeNs-firstNative>=3000000000LL&&epoch-firstEpoch>=3000){quietComplete=true;break;}
        }
        assert(quietClock.elapsed()<20000);QTest::qWait(250);
    }
    assert(quietComplete);quietTrace.close();
    if(unsettledTrace.isOpen()){unsettledTrace.close();}
    observationJournal.close();
    SettingsTests::stop(preferenceManager.data());
    QTextStream(stdout)<<QJsonDocument(QJsonObject{{"nativeCallerProfile",nativeCallerProfile},{"originalObservationCount",observationCount},{"originalDataBefore",QJsonObject{{"preferences",originalDataPreferences},{"bookmarks",originalDataBookmarks},{"settingsRawBase64",originalDataPhysical}}},{"originalDataAfter",originalDataAfter},{"originalDataQuietSamples",quietSamples},{"originalAvatarInputs",originalAvatarInputs},{"preferenceSettleOriginals",preferenceSettleOriginals},{"normalInputJournal",normalInputJournal},{"normalMessageJournal",normalMessageJournal},{"nativeProcessId",QCoreApplication::applicationPid()},{"originalBackendProcessId",backendProcessId},{"originalFavoritePreferences",originalFavoritePreferences},{"normalUrlMessages",urls},{"originalScriptAvatarCalls",urlCalls},{"bookmarkCalls",backendResult.value("bookmarkCalls")},{"scaleCalls",backendResult.value("scaleCalls")},{"snapshots",snapshots},{"originalSnapshots",originalSnapshots},{"originalBookmarkStorage",originalBookmarkStorage},{"originalBookmarkLoads",originalBookmarkLoads},{"cachedOriginalLoads",cachedOriginalLoads},{"declaredModelCompletions",declaredModelCompletions},{"counterexamples",QJsonArray{"uninitialized","wrong-root","moved-token","window-source","disabled","higher-overlay","outside-child","hidden-child","disabled-painted-child","clipped","negative-z"}},{"pointerCalls",pointers},{"hmdActive",true},{"wholeOriginalObserver",true},{"wholeOriginalWriter",true}}).toJson(QJsonDocument::Compact)<<'\n';
}
#include "avatar-bookmark-store-actor.moc"
