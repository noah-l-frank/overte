// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/LifecycleUiObservation.h"
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QtTest/QTest>
#include <cassert>

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);assert(argc==4);
    const auto source=QUrl::fromLocalFile(QString::fromLocal8Bit(argv[2]));
    const auto rootPath=QString::fromLocal8Bit(argv[2]);
    QQmlEngine engine;
    overte::e2e::LifecycleUiObservation reader({{"create",source},{"chat",QUrl("file:///not-loaded-chat.qml")},
        {"scripts",QUrl("file:///not-loaded-scripts.qml")}});
    QQuickWindow window;window.resize(640,900);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(640,900));
    QQuickItem loader(&root);loader.setObjectName("loader");loader.setSize(root.size());
    auto load=[&] {
        QQmlComponent component(&engine,source);auto page=qobject_cast<QQuickItem*>(component.create());
        if (!page) { qFatal("%s",qPrintable(component.errorString())); }
        page->setParentItem(&loader);page->setSize(loader.size());QTest::qWait(30);return page;
    };
    auto page=load();auto field=page->findChild<QQuickItem*>("NativeCreateText");assert(field);
    const auto run=QString(32,'a');const QVariantMap keyboard{{"explicitHostBoundary",true}};
    auto capture=[&](bool shown=true,bool home=false) { return reader.observe(&root,&window,shown,home,run,keyboard); };
    auto first=capture();assert(!first.isEmpty());
    auto rows=first["source"].toMap()["editors"].toList();assert(rows.size()==1);
    auto row=rows.first().toMap();assert(row["kind"]=="create" && row["alive"].toBool() && row["attached"].toBool());
    assert(first["source"].toMap()["current"]==row["id"]);
    QTest::mouseClick(&window,Qt::LeftButton,Qt::NoModifier,field->mapToScene(QPointF(5,5)).toPoint());
    QCoreApplication::processEvents();assert(field->hasActiveFocus());
    auto focused=capture();assert(focused["source"].toMap()["editors"].toList().first().toMap()["focused"].toBool());
    const QPointer<QQmlContext> firstContext(qmlContext(field));assert(firstContext);
    delete page;QCoreApplication::processEvents();
    auto partial=capture(true,true)["source"].toMap()["editors"].toList().first().toMap();
    assert(!partial["fieldAlive"].toBool() && !partial["pageAlive"].toBool());
    // Qt can retain the original QQmlContext wrapper after its QML page dies.
    // It must remain retained until that original QObject itself is gone.
    assert(partial["contextAlive"].toBool()==!firstContext.isNull());
    assert(partial["alive"].toBool()==!firstContext.isNull());
    assert(partial["windowAlive"].toBool() && partial["loaderAlive"].toBool());
    assert(capture(true,true)["source"].toMap()["current"].toString().isEmpty());
    page=load();auto replacement=capture();rows=replacement["source"].toMap()["editors"].toList();assert(rows.size()==2);
    const auto fresh=rows.last().toMap();assert(fresh["id"]!=row["id"] && fresh["fieldId"]!=row["fieldId"]);
    assert(fresh["contextId"]!=row["contextId"] && fresh["pageId"]!=row["pageId"]);
    assert(fresh["windowId"]==row["windowId"] && fresh["loaderId"]==row["loaderId"]);
    assert(rows.first().toMap()["firstObservedEpochMs"]==row["firstObservedEpochMs"]);
    assert(capture(true,true).isEmpty()); // Home cannot coexist with a real current editor.
    auto foreign=new QQuickItem(&loader);foreign->setObjectName("NativeCreateText");foreign->setSize(QSizeF(50,50));
    assert(capture()["source"].toMap()["editors"].toList().size()==2); // A name alone cannot qualify source.
    delete foreign;
    page->setVisible(false);
    auto hidden=capture(true,true)["source"].toMap()["editors"].toList().last().toMap();
    assert(hidden["alive"].toBool() && hidden["pageAlive"].toBool() && hidden["attached"].toBool());
    assert(!hidden["visible"].toBool() && !hidden["current"].toBool());
    page->setVisible(true);page->setParentItem(nullptr);QCoreApplication::processEvents();
    auto detached=capture(true,true)["source"].toMap()["editors"].toList().last().toMap();
    assert(detached["alive"].toBool() && detached["pageAlive"].toBool());
    assert(!detached["attached"].toBool() && !detached["visible"].toBool() && !detached["current"].toBool());
    page->setParentItem(&loader);QCoreApplication::processEvents();
    field=page->findChild<QQuickItem*>("NativeCreateText");assert(field);
    delete field;QCoreApplication::processEvents();
    auto fieldGone=capture(true,true)["source"].toMap()["editors"].toList().last().toMap();
    assert(!fieldGone["fieldAlive"].toBool() && fieldGone["pageAlive"].toBool());
    assert(fieldGone["contextAlive"].toBool() && fieldGone["alive"].toBool());
    assert(!fieldGone["current"].toBool() && !fieldGone["visible"].toBool());
    delete page;
    // Leave original page/field alive while retiring their engine and context.
    // Qt may retain an invalid context wrapper after engine destruction. Only
    // then delete that orphan wrapper; never delete an engine-owned context.
    auto contextEngine=new QQmlEngine;
    auto contextComponent=new QQmlComponent(contextEngine,source);
    page=qobject_cast<QQuickItem*>(contextComponent->create());assert(page);
    page->setParentItem(&loader);page->setSize(loader.size());capture();
    field=page->findChild<QQuickItem*>("NativeCreateText");assert(field);
    const QPointer<QQmlContext> originalContext(qmlContext(field));assert(originalContext);
    const QPointer<QQuickItem> originalPage(page),originalField(field);
    delete contextComponent;delete contextEngine;QCoreApplication::processEvents();
    if (originalContext) {
        assert(!originalContext->isValid());
        auto invalid=capture(true,true)["source"].toMap()["editors"].toList().last().toMap();
        assert(invalid["alive"].toBool() && invalid["contextAlive"].toBool() && !invalid["current"].toBool());
        delete originalContext.data();QCoreApplication::processEvents();
    }
    assert(originalContext.isNull() && originalPage && originalField);
    auto contextGone=capture(true,true)["source"].toMap()["editors"].toList().last().toMap();
    assert(!contextGone["contextAlive"].toBool() && contextGone["pageAlive"].toBool());
    assert(contextGone["fieldAlive"].toBool() && contextGone["alive"].toBool());
    assert(!contextGone["current"].toBool());
    delete page;
    auto last=capture(true,true)["source"].toMap()["editors"].toList().last().toMap();
    assert(!last["alive"].toBool() && !last["fieldAlive"].toBool() && !last["pageAlive"].toBool()
        && !last["contextAlive"].toBool() && last["windowAlive"].toBool() && last["loaderAlive"].toBool());
    assert(reader.observe(nullptr,nullptr,false,false,run,keyboard)["source"].toMap()["current"].toString().isEmpty());
    Q_UNUSED(rootPath)
    qInfo("PASS actual NativeCreate Qt identities/focus/partial/hidden/detached/destruction/replacement; keyboard is an explicit host boundary");
}
