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
    delete page;QCoreApplication::processEvents();
    auto retired=capture(true,true);assert(!retired.isEmpty());
    auto old=retired["source"].toMap()["editors"].toList().first().toMap();
    assert(!old["alive"].toBool() && !old["attached"].toBool() && !old["focused"].toBool());
    assert(retired["source"].toMap()["current"].toString().isEmpty());
    page=load();auto replacement=capture();rows=replacement["source"].toMap()["editors"].toList();assert(rows.size()==2);
    const auto fresh=rows.last().toMap();assert(fresh["id"]!=row["id"] && fresh["fieldId"]!=row["fieldId"]);
    assert(fresh["contextId"]!=row["contextId"] && fresh["pageId"]!=row["pageId"]);
    assert(fresh["windowId"]==row["windowId"] && fresh["loaderId"]==row["loaderId"]);
    assert(rows.first().toMap()["firstObservedEpochMs"]==row["firstObservedEpochMs"]);
    assert(capture(true,true).isEmpty()); // Home cannot coexist with a real current editor.
    auto foreign=new QQuickItem(&loader);foreign->setObjectName("NativeCreateText");foreign->setSize(QSizeF(50,50));
    assert(capture()["source"].toMap()["editors"].toList().size()==2); // A name alone cannot qualify source.
    delete foreign;delete page;
    assert(reader.observe(nullptr,nullptr,false,false,run,keyboard)["source"].toMap()["current"].toString().isEmpty());
    Q_UNUSED(rootPath)
    qInfo("PASS actual NativeCreate Qt identities/focus/destruction/replacement; keyboard is an explicit host boundary");
}
