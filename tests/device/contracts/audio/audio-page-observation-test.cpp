// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "tests/device/native/AudioPageObservation.h"
#include <QGuiApplication>
#include <QJsonDocument>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QtTest/QTest>
#include <cassert>
#include <cstdio>

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);assert(argc==6);
    const auto repository=QString::fromLocal8Bit(argv[2]),imports=QString::fromLocal8Bit(argv[3]);
    const auto source=QUrl::fromLocalFile(repository+"/interface/resources/qml/hifi/audio/Audio.qml");
    QQmlEngine engine;engine.addImportPath(repository+"/interface/resources/qml");engine.addImportPath(imports);
    QQmlComponent servicesComponent(&engine,QUrl::fromLocalFile(repository+"/tests/device/contracts/audio/qml/AudioPageServices.qml"));
    std::unique_ptr<QObject> services(servicesComponent.create());
    if(!services)qFatal("%s",qPrintable(servicesComponent.errorString()));
    engine.rootContext()->setContextProperty("AudioScriptingInterface",services.get());
    const auto devices=services->property("devices").value<QObject*>();assert(devices);
    const auto input=devices->property("input").value<QObject*>();assert(input);
    const bool originalPeak=QString::fromLocal8Bit(argv[4])=="true";assert(input->setProperty("peakValuesEnabled",originalPeak));
    QQuickWindow window;window.resize(800,1000);window.show();window.requestActivate();
    QQuickItem root(window.contentItem());root.setSize(QSizeF(800,1000));
    overte::e2e::AudioPageObservation reader(source);auto empty=reader.observe(&root,&window,true);
    assert(empty.value("originals").toArray().isEmpty());
    QQmlComponent component(&engine,source);auto page=qobject_cast<QQuickItem*>(component.create());
    if(!page)qFatal("%s",qPrintable(component.errorString()));
    page->setParentItem(&root);page->setSize(root.size());QTest::qWait(50);
    assert(input->property("peakValuesEnabled").toBool());assert(page->property("peakValuesWereEnabled").toBool()==originalPeak);
    auto opened=reader.observe(&root,&window,true);auto rows=opened.value("originals").toArray();assert(rows.size()==1);
    const auto original=rows.first().toObject();assert(original.value("originalPeakValuesEnabled").toBool()==originalPeak);
    assert(original.value("pageAlive").toBool()&&original.value("contextAlive").toBool()&&original.value("current").toBool());
    auto foreign=new QQuickItem(&root);foreign->setObjectName("settings.audio");foreign->setProperty("title","Audio Settings");
    assert(reader.observe(&root,&window,true).value("originals").toArray().size()==1);delete foreign;
    page->setVisible(false);auto hidden=reader.observe(&root,&window,true).value("originals").toArray().first().toObject();
    assert(hidden.value("alive").toBool()&&hidden.value("attached").toBool()&&!hidden.value("current").toBool());
    assert(input->property("peakValuesEnabled").toBool()); // Hiding is not destruction/restore.
    page->setVisible(true);page->setParentItem(nullptr);auto detached=reader.observe(&root,&window,true).value("originals").toArray().first().toObject();
    assert(detached.value("pageAlive").toBool()&&detached.value("contextAlive").toBool()&&!detached.value("attached").toBool());
    page->setParentItem(&root);auto reattached=reader.observe(&root,&window,true).value("originals").toArray().first().toObject();
    assert(reattached.value("id")==original.value("id")&&reattached.value("current").toBool());
    const QPointer<QQmlContext> context(qmlContext(page));
    delete page;QCoreApplication::processEvents();
    assert(input->property("peakValuesEnabled").toBool()==originalPeak);
    auto closed=reader.observe(&root,&window,true);auto gone=closed.value("originals").toArray().first().toObject();
    assert(gone.value("id")==original.value("id")&&!gone.value("pageAlive").toBool());
    assert(gone.value("contextAlive").toBool()==!context.isNull()&&gone.value("alive").toBool()==!context.isNull());
    assert(!gone.value("current").toBool()&&gone.value("rootAlive").toBool()&&gone.value("windowAlive").toBool());
    assert(closed.value("current").toString().isEmpty());
    std::puts(QJsonDocument(opened).toJson(QJsonDocument::Compact).constData());
    std::puts(QJsonDocument(closed).toJson(QJsonDocument::Compact).constData());
    // Do not delete internal Qt contexts to force a retirement claim.
    qInfo("PASS actual original Audio.qml completion/hidden/detached/destruction peak restore; explicit native audio/tablet sound seams");
}
