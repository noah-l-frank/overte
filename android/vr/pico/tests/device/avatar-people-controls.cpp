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
#include "actual-pointer-route.inc"
#include "tests/device/native/NormalControlUi.h"
#include "actual-avatar-input.inc"
#include "actual-avatar-preference-host.inc"
// Unrelated NavigationUi services keep their declared unavailable registry.
#define DependencyManager AvatarObservationDependencies
#include "avatar-navigation-observation-seams.h"
#include "actual-avatar-observe.inc"
#undef DependencyManager
#include "avatar-bookmark-store-actor.h"
#include "actual-avatar-preference-observer.inc"
int main(int argc,char**argv) {
    HostApplication app(argc,argv);::umask(0077);using namespace overte::e2e;
    NormalControlUi ui(NormalControlUi::Surface::AvatarPeople);
    if(!app.arguments().contains("--testScript")){assert(ui.observe(nullptr,nullptr).isEmpty());return 0;}
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
    TestScriptingInterface preferenceObserver;quint64 preferenceNonce=0;QJsonArray originalFavoritePreferences;
    auto physicalPreferences=[&]{QFile file(preferenceManager->fileName());assert(file.open(QIODevice::ReadOnly));
        const auto bytes=file.read(65537);assert(bytes.size()<=65536 && file.atEnd());return QString::fromLatin1(bytes.toBase64());};
    auto preferences=[&]{const QVariantMap request{{"schemaVersion",1},{"commandId",QString::number(++preferenceNonce,16).rightJustified(32,'0')},
        {"action","feature-pico-avatar-preferences-observe"}};
        const auto packet=preferenceObserver.featurePicoAvatarPreferences(request);assert(!packet.isEmpty());
        assert(preferenceObserver.featurePicoAvatarPreferences(request).isEmpty());
        return QJsonObject{{"request",QJsonObject::fromVariantMap(request)},{"packet",QJsonObject::fromVariantMap(packet)}};};
    int originalLoaded=0,cachedOriginalLoads=0,declaredModelCompletions=0;
    QObject::connect(&nativeBookmarks,&avatar_bookmark_host::AvatarBookmarks::bookmarkLoaded,[&](const QString&){++originalLoaded;});
    overte::pico::e2e::NavigationUi actualObserver;
    auto capture=[&]{return ui.observe(root,&window);};
    auto originalCapture=[&]{return actualObserver.observe(root,&window,true);};
    const auto before=capture();for(const auto& raw:before.value("controls").toArray()){assert(!raw.toObject().value("inputReady").toBool());}
    QProcess backend;backend.setProcessChannelMode(QProcess::ForwardedErrorChannel);
    backend.start("node",QStringList{path+"/android/vr/pico/tests/device/avatar-original-backend.js",path,"--native-bookmarks"});assert(backend.waitForStarted(2000));const auto backendProcessId=backend.processId();
    QJsonArray normalInputJournal,normalMessageJournal;
    auto response=[&]{for(int calls=0;calls<32;++calls){if(!backend.canReadLine()){assert(backend.waitForReadyRead(2000));}const auto raw=backend.readLine();auto value=QJsonDocument::fromJson(raw).object();assert(!value.isEmpty());
        if(!value.contains("nativeBookmarkCall")){return value;}
        const auto call=value.value("nativeBookmarkCall").toObject();const auto method=call.value("method").toString(),name=call.value("name").toString();
        nativeBookmarks.currentAvatarActor={{"version",3},{"avatarUrl",call.value("avatarUrl").toString()},{"avatarScale",call.value("scale").toDouble()},{"avatarEntites",QVariantList{}},{"avatarIcon",""}};
        QJsonObject nativeLoad;
        if(method=="save"){assert(name=="e2e-"+QString(32,'a'));nativeBookmarks.addBookmarkInternal(name);}
        else if(method=="delete"){assert(name=="e2e-"+QString(32,'a'));nativeBookmarks.removeBookmarkInternal(name);}
        else if(method=="load"){
            // Live URL/scale and actual asynchronous model completion are
            // declared native actors. The entire original Qt connection,
            // cached-sameURL signal branch and callback body execute unchanged.
            nativeAvatar->skeletonActor=QUrl(call.value("avatarUrl").toString());nativeAvatar->_fullAvatarURLFromPreferences=nativeAvatar->skeletonActor;
            nativeAvatar->_targetScale=call.value("scale").toDouble();assert(nativeAvatar->_packedAvatarEntityData.isEmpty());const int requested=nativeAvatar->modelRequestsActor,loadedBefore=originalLoaded;
            const auto beforePhysical=physicalPreferences();const auto beforePreferences=preferences();const auto beforeLoads=QJsonObject::fromVariantMap(nativeBookmarks.e2eBookmarkLoads());
            nativeBookmarks.loadBookmark(name);
            if(nativeAvatar->modelRequestsActor!=requested){++declaredModelCompletions;emit nativeAvatar->onLoadComplete();}
            else{++cachedOriginalLoads;}
            assert(originalLoaded==loadedBefore+1);const auto observed=nativeBookmarks.e2eBookmarkLoads();assert(!observed.isEmpty());
            const auto afterPreferences=preferences();
            originalFavoritePreferences.append(QJsonObject{{"cached",nativeAvatar->modelRequestsActor==requested},{"normalInput",normalInputJournal.size()},{"normalMessages",normalMessageJournal.size()},
                {"bookmarkName",name},{"avatarInstance",nativeAvatar->avatarBirthActor},{"before",beforePreferences},{"after",afterPreferences},
                {"beforePhysicalBase64",beforePhysical},{"afterPhysicalBase64",physicalPreferences()},
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
        const auto r=row(id),value=capture();QJsonObject c{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"instance",value.value("instance")},{"generation",value.value("generation")},{"sequence",value.value("lastCommandSequence").toInt()+1},{"observedElapsedMs",value.value("elapsedMs")},{"controlId",id},{"controlToken",r.value("token")},{"action",action}};
        if(action=="replace"){c["text"]=arg;}if(action=="set-value"){c["value"]=arg;}if(action=="scroll"){c["direction"]=arg;}return c;};
    auto input=[&](const QString& id,const QString& action,const QJsonValue& arg=QJsonValue()){
        const auto sent=command(id,action,arg),observed=capture();
        const auto result=ui.apply(root,&window,sent,click,{},pointerAt);normalInputJournal.append(QJsonObject{{"command",sent},{"snapshot",observed},{"reply",result}});if(!result.value("performed").toBool()){qFatal("refused %s/%s",qPrintable(id),qPrintable(action));}drain();QTest::qWait(40);renderControl.polishItems();QCoreApplication::processEvents();};
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
    page->setX(2);assert(row("avatar.url").value("token")!=token);assert(!ui.apply(root,&window,held,click,{},pointerAt).value("performed").toBool());page->setX(0);
    const auto sourceBeforeWindow=avatarPeopleControlSource(actualUrl,"avatar.url");
    QQuickRenderControl alternateRender;QQuickWindow alternateWindow(&alternateRender);alternateWindow.resize(640,1000);alternateWindow.contentItem()->setSize(QSizeF(640,1000));
    root->setParentItem(alternateWindow.contentItem());assert(avatarPeopleControlSource(actualUrl,"avatar.url")!=sourceBeforeWindow);
    assert(!ui.apply(root,&window,held,click,{},pointerAt).value("performed").toBool());root->setParentItem(window.contentItem());
    // Each refusal gets a fresh original command; sequence replay is not the
    // reason disabled, foreign-overlay or clipped controls are rejected.
    page->setEnabled(false);assert(!ui.apply(root,&window,command("avatar.url","activate"),click,{},pointerAt).value("performed").toBool());page->setEnabled(true);
    QQmlComponent overlayComponent(&engine);overlayComponent.setData("import QtQuick 2.7; Rectangle {color:'red';width:640;height:1000;z:999}",{});
    QScopedPointer<QObject> overlayObject(overlayComponent.create());auto overlay=qobject_cast<QQuickItem*>(overlayObject.data());assert(overlay);overlay->setParentItem(window.contentItem());
    assert(!ui.apply(root,&window,command("avatar.url","activate"),click,{},pointerAt).value("performed").toBool());overlay->setVisible(false);
    // A non-clipping foreign parent can have an input/drawn child beyond its
    // own bounds. Clipping and hidden/disabled children are measured by Qt.
    QQmlComponent outside(&engine);outside.setData("import QtQuick 2.7; Item {width:1;height:1;z:999;Rectangle {width:640;height:1000;color:'red';MouseArea{anchors.fill:parent}}}",{});
    QScopedPointer<QObject> outsideObject(outside.create());auto foreign=qobject_cast<QQuickItem*>(outsideObject.data());assert(foreign);foreign->setParentItem(window.contentItem());
    assert(!ui.apply(root,&window,command("avatar.url","activate"),click,{},pointerAt).value("performed").toBool());foreign->setClip(true);
    const auto actualPoint=avatarPeopleActivatePoint(actualUrl,"avatar.url");assert(avatarPeopleOwnsPoint(actualUrl,&window,actualPoint));
    foreign->setClip(false);foreign->childItems().first()->setVisible(false);assert(avatarPeopleOwnsPoint(actualUrl,&window,actualPoint));
    foreign->childItems().first()->setVisible(true);foreign->childItems().first()->setEnabled(false);
    // A disabled foreign painted Rectangle still obscures the original field.
    assert(!avatarPeopleOwnsPoint(actualUrl,&window,actualPoint));
    foreign->setVisible(false);
    auto clipCommand=command("avatar.url","activate");QQuickItem clip(window.contentItem());clip.setClip(true);clip.setSize(QSizeF(1,1));root->setParentItem(&clip);
    assert(!ui.apply(root,&window,clipCommand,click,{},pointerAt).value("performed").toBool());root->setParentItem(window.contentItem());
    // Actual negative-z opaque parent is conservatively blocked, even when its
    // low child claims input. A higher non-clipping foreign child also blocks.
    QQmlComponent negative(&engine);negative.setData("import QtQuick 2.7; Rectangle {width:640;height:1000;color:'blue';z:999;MouseArea{anchors.fill:parent;z:-1}}",{});
    QScopedPointer<QObject> negativeObject(negative.create());auto n=qobject_cast<QQuickItem*>(negativeObject.data());assert(n);n->setParentItem(window.contentItem());
    assert(!ui.apply(root,&window,command("avatar.url","activate"),click,{},pointerAt).value("performed").toBool());n->setVisible(false);assert(prior==pointers);
    assert(!originalAvatarInput(actualUrl,&window,"avatar.url","activate",{},pointerAt,2).value("performed").toBool());
    assert(originalAvatarInput(actualUrl,&window,"avatar.url","activate",{},pointerAt).value("performed").toBool());QTest::qWait(40);
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
    assert(!ui.apply(root,&window,command("avatar.dialog.confirm","activate"),click,{},pointerAt).value("performed").toBool());
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
        assert(!ui.apply(root,&window,command(bookmarkId,"activate"),click,{},pointerAt).value("performed").toBool());foreignItem->setVisible(false);
    }
    assert(pointers==beforeForeign);assert(avatarPeopleOwnsPoint(actualBookmark,&window,bookmarkPoint));
    input(bookmarkId,"activate");input("avatar.dialog.confirm","activate");
    assert(!backendResult.value("bookmarks").toObject().contains(ownedName));assert(backendResult.value("bookmarks").toObject().contains("unowned"));
    backend.closeWriteChannel();assert(backend.waitForFinished(2000));assert(backend.exitStatus()==QProcess::NormalExit && backend.exitCode()==0);
    SettingsTests::stop(preferenceManager.data());
    QTextStream(stdout)<<QJsonDocument(QJsonObject{{"normalInputJournal",normalInputJournal},{"normalMessageJournal",normalMessageJournal},{"nativeProcessId",QCoreApplication::applicationPid()},{"originalBackendProcessId",backendProcessId},{"originalFavoritePreferences",originalFavoritePreferences},{"normalUrlMessages",urls},{"originalScriptAvatarCalls",urlCalls},{"bookmarkCalls",backendResult.value("bookmarkCalls")},{"scaleCalls",backendResult.value("scaleCalls")},{"snapshots",snapshots},{"originalSnapshots",originalSnapshots},{"originalBookmarkStorage",originalBookmarkStorage},{"originalBookmarkLoads",originalBookmarkLoads},{"cachedOriginalLoads",cachedOriginalLoads},{"declaredModelCompletions",declaredModelCompletions},{"counterexamples",QJsonArray{"uninitialized","wrong-root","moved-token","window-source","disabled","higher-overlay","outside-child","hidden-child","disabled-painted-child","clipped","negative-z"}},{"pointerCalls",pointers},{"hmdActive",true},{"wholeOriginalObserver",true}}).toJson(QJsonDocument::Compact)<<'\n';
}
#include "avatar-bookmark-store-actor.moc"
