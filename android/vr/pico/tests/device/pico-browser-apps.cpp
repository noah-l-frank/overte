// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original TabletButton QML and normal Pico pointer bodies; Tablet singleton,
// button proxy construction and script API delivery are explicit host seams.
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickRenderControl>
#include <QSignalSpy>
#include <QTest>
#include <QTouchDevice>
#include <QWheelEvent>
#include <QJsonArray>
#include <QJsonDocument>
#include <PointerEvent.h>
#include <map>
#include <cassert>
#include "PathUtils.h"
#include "tests/device/native/PicoBrowserAppControls.h"
#include "tests/device/native/NormalControlUi.h"
#include "actual-pointer-route.inc"
#include "actual-browser-app-input.inc"
using namespace overte::e2e;
int main(int argc,char**argv) {
    QGuiApplication app(argc,argv);assert(argc==3);
    PathUtils::qml=QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1])+"/interface/resources/qml/");
    QQmlEngine engine;engine.addImportPath(QString::fromLocal8Bit(argv[2]));
    QQmlComponent component(&engine,PathUtils::qmlUrl("hifi/tablet/TabletButton.qml"));
    auto item=qobject_cast<QQuickItem*>(component.create());if(!item)qFatal("%s",qPrintable(component.errorString()));
    QQuickRenderControl render;QQuickWindow window(&render);window.resize(640,480);window.contentItem()->setSize(QSizeF(640,480));
    QQuickItem root(window.contentItem());root.setSize(QSizeF(640,480));item->setParentItem(&root);item->setPosition(QPointF(30,30));
    item->setProperty("text","WEB TEST");item->setProperty("uuid",QUuid("{11111111-2222-3333-4444-555555555555}"));
    QTest::qWait(50);assert(picoBrowserAppControlId(item)=="browser-app.web");
    const auto first=picoBrowserAppControlSource(item,"browser-app.web");assert(!first.isEmpty());
    QJsonObject observed;appendPicoBrowserAppObservation(observed,item,"browser-app.web");
    assert(observed.value("buttonId")=="11111111-2222-3333-4444-555555555555" && observed.value("inputReady").toBool());
    OffscreenQmlSurface surface(&root,&window);QSignalSpy clicked(item,SIGNAL(clicked()));int pointers=0;
    auto pointer=[&](QQuickItem* actual){++pointers;return sendPointerClick(actual,&surface);};
    assert(originalBrowserAppInput(item,&window,"browser-app.web","activate",pointer).value("performed").toBool());
    assert(clicked.count()==1 && pointers==1);
    QQuickItem overlay(&root);overlay.setSize(root.size());overlay.setZ(100);
    assert(!originalBrowserAppInput(item,&window,"browser-app.web","activate",pointer).value("performed").toBool());
    assert(clicked.count()==1 && pointers==1);overlay.setVisible(false);
    assert(!originalBrowserAppInput(item,&window,"browser-app.web","replace",pointer).value("performed").toBool());
    item->setProperty("uuid",QUuid("{66666666-2222-3333-4444-555555555555}"));
    assert(first!=picoBrowserAppControlSource(item,"browser-app.web"));
    item->setProperty("text","INLINE TEST");assert(picoBrowserAppControlId(item)=="browser-app.inline");
    assert(originalBrowserAppInput(item,&window,"browser-app.inline","activate",pointer).value("performed").toBool());
    assert(clicked.count()==2 && pointers==2);
    item->setEnabled(false);assert(!originalBrowserAppInput(item,&window,"browser-app.inline","activate",pointer).value("performed").toBool());item->setEnabled(true);
    item->setProperty("uuid","not-an-original-uuid");assert(picoBrowserAppControlId(item).isEmpty());
    // Same visible label/signal from another component never becomes this tile.
    QQmlComponent foreign(&engine);foreign.setData("import QtQuick 2.7;Item {property string text:'WEB TEST';property string uuid:'11111111-2222-3333-4444-555555555555';signal clicked()}",QUrl("file:///foreign.qml"));
    QScopedPointer<QObject> substitute(foreign.create());assert(substitute);assert(picoBrowserAppControlId(qobject_cast<QQuickItem*>(substitute.data())).isEmpty());
    delete item;puts("PASS original TabletButton component UUID/caption and original Pico surface click; explicit Tablet/proxy/script seams");
}
