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
int main(int argc,char**argv) {
    QGuiApplication app(argc,argv);using namespace overte::e2e;
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
    auto capture=[&]{return ui.observe(root,&window);};
    const auto before=capture();for(const auto& raw:before.value("controls").toArray()){assert(!raw.toObject().value("inputReady").toBool());}
    QProcess backend;backend.setProcessChannelMode(QProcess::ForwardedErrorChannel);
    backend.start("node",QStringList{path+"/android/vr/pico/tests/device/avatar-original-backend.js",path});assert(backend.waitForStarted(2000));
    auto response=[&]{if(!backend.canReadLine()){assert(backend.waitForReadyRead(2000));}const auto raw=backend.readLine();auto value=QJsonDocument::fromJson(raw).object();assert(!value.isEmpty());return value;};
    auto applyProducer=[&](const QJsonObject& value){for(const auto& raw:value.value("qml").toArray()){QVariant actual=raw.toObject().toVariantMap();assert(QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,actual)));}};
    auto boot=response();assert(boot.value("source")==QJsonValue("hifi/AvatarApp.qml"));applyProducer(boot);
    int delivered=0;QJsonObject backendResult;
    auto drain=[&]{
        for(int pass=0;pass<8 && delivered<messages.size();++pass){QJsonArray pending;
            while(delivered<messages.size()){pending.append(QJsonObject::fromVariantMap(createVariant(messages.at(delivered++).first()).toMap()));}
            const auto raw=QJsonDocument(QJsonObject{{"messages",pending}}).toJson(QJsonDocument::Compact)+'\n';assert(backend.write(raw)==raw.size());assert(backend.waitForBytesWritten(2000));
            backendResult=response();applyProducer(backendResult);
        }assert(delivered==messages.size());
    };
    drain();QTest::qWait(80);
    OffscreenQmlSurface surface(root,&window);int pointers=0;
    auto pointerAt=[&](QQuickItem* item,const QPointF& point){++pointers;const auto result=sendPointerAt(item,&surface,point);QCoreApplication::processEvents();return result;};
    auto click=[&](QQuickItem* item){return pointerAt(item,item->mapToScene(QPointF(item->width()/2,item->height()/2)));};
    auto row=[&](const QString& id){auto value=capture();assert(value.value("ready").toBool());for(const auto& raw:value.value("controls").toArray()){if(raw.toObject().value("id")==id){return raw.toObject();}}
        qFatal("missing %s: %s",qPrintable(id),QJsonDocument(value).toJson(QJsonDocument::Compact).constData());return QJsonObject();};
    auto command=[&](const QString& id,const QString& action,const QJsonValue& arg=QJsonValue()){
        const auto r=row(id),value=capture();QJsonObject c{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},{"instance",value.value("instance")},{"generation",value.value("generation")},{"sequence",value.value("lastCommandSequence").toInt()+1},{"observedElapsedMs",value.value("elapsedMs")},{"controlId",id},{"controlToken",r.value("token")},{"action",action}};
        if(action=="replace"){c["text"]=arg;}return c;};
    auto input=[&](const QString& id,const QString& action,const QJsonValue& arg=QJsonValue()){
        const auto result=ui.apply(root,&window,command(id,action,arg),click,{},pointerAt);if(!result.value("performed").toBool()){qFatal("refused %s/%s",qPrintable(id),qPrintable(action));}drain();QTest::qWait(40);renderControl.polishItems();QCoreApplication::processEvents();};
    assert(row("avatar.page").value("inputReady")==QJsonValue(false));
    QJsonArray urls,snapshots;snapshots.append(capture());
    for(const auto& url:QStringList{"https://controlled.invalid/owned/avatar-a.fst","qrc:/meshes/defaultAvatar_full.fst"}) {
        input("avatar.url","activate");input("avatar.dialog.input","activate");input("avatar.dialog.input","replace",url);
        snapshots.append(capture());assert(row("avatar.dialog.input").value("text")==QJsonValue(url));input("avatar.dialog.confirm","activate");
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
    backend.closeWriteChannel();assert(backend.waitForFinished(2000));assert(backend.exitStatus()==QProcess::NormalExit && backend.exitCode()==0);
    QTextStream(stdout)<<QJsonDocument(QJsonObject{{"normalUrlMessages",urls},{"originalScriptAvatarCalls",backendResult.value("avatarCalls")},{"snapshots",snapshots},{"counterexamples",QJsonArray{"uninitialized","wrong-root","moved-token","window-source","disabled","higher-overlay","outside-child","hidden-child","disabled-painted-child","clipped","negative-z"}},{"pointerCalls",pointers},{"hmdActive",true}}).toJson(QJsonDocument::Compact)<<'\n';
}
