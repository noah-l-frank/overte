// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/NormalScriptControls.h"
#include "tests/device/native/NormalControlUi.h"
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QSignalSpy>
#include <QtTest/QTest>
#include <cassert>

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    using namespace overte::e2e;
    NormalControlUi controls(NormalControlUi::Surface::Create);
    if (!app.arguments().contains("--testScript")) { assert(controls.observe(nullptr,nullptr).isEmpty());return 0; }
    const auto path=app.arguments().last();
    PathUtils::scripts=QUrl::fromLocalFile(path+"/scripts/");
    PathUtils::qml=QUrl::fromLocalFile(path+"/interface/resources/qml/");
    QQmlEngine engine;QQuickWindow window;window.resize(1200,1800);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(1200,1800));
    QQuickItem loader(&root);loader.setObjectName("loader");loader.setSize(root.size());
    auto load=[&] {
        QQmlComponent component(&engine,QUrl::fromLocalFile(path+"/scripts/system/create/qml/NativeCreate.qml"));
        auto page=qobject_cast<QQuickItem*>(component.create());
        if (!page) { qFatal("%s",qPrintable(component.errorString())); }
        page->setParentItem(&loader);page->setSize(loader.size());QTest::qWait(50);return page;
    };
    auto page=load();assert(!createComponentSource(page).isEmpty());
    QSignalSpy calls(page,SIGNAL(sendToScript(QVariant)));
    auto observe=[&] { return controls.observe(&root,&window); };
    auto row=[&](const QString& id) {
        auto value=observe();assert(value.value("ready").toBool());
        for (const auto& raw:value.value("controls").toArray()) { if (raw.toObject().value("id")==id) { return raw.toObject(); } }
        qFatal("missing actual normal control: %s",qPrintable(id));return QJsonObject();
    };
    auto request=[&](const QString& id,const QString& action,const QString& text=QString()) {
        auto actual=row(id);auto current=observe();
        QJsonObject command{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"instance",current.value("instance")},{"generation",current.value("generation")},
            {"sequence",current.value("lastCommandSequence").toInt()+1},{"observedElapsedMs",current.value("elapsedMs")},
            {"controlId",id},{"controlToken",actual.value("token")},{"action",action}};
        if (action=="replace") { command["text"]=text; }return command;
    };
    int clicks{0};
    auto pointer=[&](QQuickItem* item) {
        ++clicks;QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,
            item->mapToScene(QPointF(item->width()/2,item->height()/2)).toPoint());
        QCoreApplication::processEvents();return true;
    };
    auto apply=[&](const QJsonObject& command) { return controls.apply(&root,&window,command,pointer); };
    auto activate=[&](const QString& id) { auto result=apply(request(id,"activate"));assert(result.value("performed").toBool()); };
    assert(row("create.host").value("currentIndex").toInt()==0); // Original domain default.
    activate("create.resource");const auto url=QStringLiteral("http://controlled.test/feature-fixture/v1/runs/")+QString(32,'a')+
        "/tickets/"+QString(32,'b')+"/gltf-bundle/main.gltf";
    auto replacement=request("create.resource","replace",url);assert(apply(replacement).value("performed").toBool());
    assert(row("create.resource").value("text")==url && calls.count()==0);
    assert(!apply(replacement).value("performed").toBool());
    auto create=request("create.new-model","activate");assert(apply(create).value("performed").toBool());
    assert(calls.count()==1 && page->property("currentTab").toInt()==2);
    auto original=createVariant(calls.takeFirst().first()).toMap();auto params=createVariant(original.value("params")).toMap();
    auto properties=createVariant(params.value("properties")).toMap();
    assert(original.value("method")=="nativeCreate.create" && params.value("host")=="domain"
        && properties.size()==2 && properties.value("type")=="Model" && properties.value("modelURL")==url);
    assert(!apply(create).value("performed").toBool() && calls.count()==0); // No replay after page transition.
    // Original NEW-tab navigation is normal pointer input; another entity is
    // never created by changing a native observation or by invoking a handler.
    activate("create.tab.0");auto stale=request("create.new-model","activate");
    delete page;QCoreApplication::processEvents();page=load();
    assert(!apply(stale).value("performed").toBool());
    auto field=page->findChild<QQuickItem*>("NativeCreateResourceUrl");assert(field && field->property("text").toString().isEmpty());
    QSignalSpy replacementCalls(page,SIGNAL(sendToScript(QVariant)));
    activate("create.new-model");assert(replacementCalls.count()==0 && page->property("statusError").toBool()); // Original error, no entity request.
    assert(clicks>=4);delete page;
    qInfo("PASS actual NativeCreate NEW Model via original NormalControlUi pointer/NativeFieldInput, exact original domain URL callback, no replay, original missing-URL error; visible Qt host window and entity actor are explicit boundaries");
}
