// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/NormalControlUi.h"
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QSignalSpy>
#include <QtTest/QTest>
#include <cassert>

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    const bool enabled=app.arguments().contains("--testScript");
    const auto path=app.arguments().last();
    PathUtils::scripts=QUrl::fromLocalFile(path+"/scripts/");
    PathUtils::qml=QUrl::fromLocalFile(path+"/interface/resources/qml/");
    using namespace overte::e2e;
    NormalControlUi controls(NormalControlUi::Surface::Lifecycle);
    if (!enabled) { assert(controls.observe(nullptr,nullptr).isEmpty());return 0; }
    QQmlEngine engine;QQuickWindow window;window.resize(640,900);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(640,900));
    QQuickItem loader(&root);loader.setObjectName("loader");loader.setSize(root.size());
    auto load=[&] {
        QQmlComponent component(&engine,lifecycleCreateSource());auto page=qobject_cast<QQuickItem*>(component.create());
        if (!page) { qFatal("%s",qPrintable(component.errorString())); }
        page->setParentItem(&loader);page->setSize(loader.size());QTest::qWait(30);return page;
    };
    auto page=load();auto field=page->findChild<QQuickItem*>("NativeCreateText");assert(field);
    QSignalSpy scriptCalls(page,SIGNAL(sendToScript(QVariant)));
    auto observe=[&] { return controls.observe(&root,&window); };
    auto row=[&] { auto value=observe();assert(value.value("ready").toBool());auto rows=value.value("controls").toArray();assert(rows.size()==1);return rows.first().toObject(); };
    auto initial=row();assert(initial.value("id")=="lifecycle.create.text" && initial.value("text")=="");
    for (const auto& key:{"fieldId","pageId","contextId","windowId"}) { assert(!initial.value(key).toString().isEmpty()); }
    int clicks{0};
    auto pointer=[&](QQuickItem* item) {
        ++clicks;QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,item->mapToScene(QPointF(item->width()/2,item->height()/2)).toPoint());
        QCoreApplication::processEvents();return item->hasActiveFocus();
    };
    auto request=[&](const QString& action,const QString& text=QString()) {
        auto current=observe();auto selected=current.value("controls").toArray().first().toObject();
        QJsonObject command{{"schemaVersion",1},{"commandId",QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},
            {"instance",current.value("instance")},{"generation",current.value("generation")},
            {"sequence",current.value("lastCommandSequence").toInt()+1},{"observedElapsedMs",current.value("elapsedMs")},
            {"controlId","lifecycle.create.text"},{"controlToken",selected.value("token")},{"action",action}};
        if (action=="replace") { command["text"]=text; }return command;
    };
    auto apply=[&](const QJsonObject& command) { return controls.apply(&root,&window,command,pointer); };
    assert(apply(request("activate")).value("performed").toBool());assert(field->hasActiveFocus() && clicks==1);
    const auto text=QStringLiteral("Overte ä Ω 東京 ")+QString(32,'a');
    auto pending=request("replace",text);assert(apply(pending).value("performed").toBool());
    assert(field->property("text").toString()==text && row().value("text")==text && scriptCalls.count()==0);
    assert(!apply(pending).value("performed").toBool()); // Consumed input cannot replay.
    auto clear=request("replace","");assert(apply(clear).value("performed").toBool());
    assert(field->property("text").toString().isEmpty());
    assert(!apply(request("replace","foreign arbitrary text")).value("performed").toBool());
    assert(!apply(request("submit")).value("performed").toBool());assert(scriptCalls.count()==0);
    auto stale=request("replace",text);delete page;QCoreApplication::processEvents();
    page=load();field=page->findChild<QQuickItem*>("NativeCreateText");auto fresh=row();
    for (const auto& key:{"fieldId","pageId","contextId"}) { assert(fresh.value(key)!=initial.value(key)); }
    assert(fresh.value("windowId")==initial.value("windowId"));
    assert(!apply(stale).value("performed").toBool());assert(field->property("text").toString().isEmpty());
    page->setProperty("currentTab",1);QCoreApplication::processEvents();assert(observe().value("controls").toArray().isEmpty());
    page->setProperty("currentTab",0);QCoreApplication::processEvents();assert(row().value("text")=="");
    auto lookalike=new QQuickItem(&root);lookalike->setObjectName("NativeCreateText");lookalike->setSize(QSizeF(50,50));
    assert(lifecycleControlId(lookalike).isEmpty());delete lookalike;delete page;
    qInfo("PASS actual NativeCreate field + normal pointer/IME/Unicode, original weak identities, stale token/gate and no entity request; VR keyboard is a host boundary");
}
