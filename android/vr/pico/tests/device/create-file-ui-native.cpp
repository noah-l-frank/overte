// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#define OVERTE_E2E_FEATURE_TESTS 1
#include "PicoCreateFileControls.h"
#include <ui/NativeFieldInput.h>
#include <FileDialogHelper.h>
#include <QApplication>
#include <QQmlComponent>
#include <QSignalSpy>
#include <QTest>
#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QTemporaryDir>
#include <cassert>
#include <cmath>

// Exact production geometry/admission and Create file input branch, extracted
// at compile time. Only the pointer boundary uses host Qt test input here.
#include "CreateFileAdmission.inc"

QQuickItem* named(QQuickItem* root,const QString& name) {
    if (root->objectName()==name) { return root; }
    for (auto child:root->childItems()) { if (auto result=named(child,name)) { return result; } }
    return nullptr;
}
int main(int argc,char** argv) {
    QApplication app(argc,argv);assert(argc>=3);
    QQmlEngine engine;engine.addImportPath(QString::fromLocal8Bit(argv[1]));
    QTemporaryDir storage;assert(storage.isValid());
    const auto leaf="feature-create-"+QString(32,'a')+'-'+QString(32,'b');
    assert(QDir(storage.path()).mkdir(leaf));const auto directory=storage.path()+'/'+leaf;
    QFile input(directory+"/entity-import.json");assert(input.open(QIODevice::WriteOnly));input.write("{\"DataVersion\":3,\"Entities\":[]}");input.close();
    FileDialogHelper helper;engine.rootContext()->setContextProperty("fileDialogHelper",&helper);
    engine.rootContext()->setContextProperty("fixtureDirectory",QUrl::fromLocalFile(directory));
    QQmlComponent component(&engine,QUrl::fromLocalFile(QString::fromLocal8Bit(argv[1])+"/Host.qml"));
    auto host=qobject_cast<QQuickItem*>(component.create());
    if (!host) {qWarning()<<component.errors();return 2;}
    QQuickWindow window;window.resize(900,1000);host->setParentItem(window.contentItem());host->setWidth(900);host->setHeight(1000);
    window.show();window.requestActivate();QTest::qWait(50);
    auto& inventory=overte::e2e::createUiInventory();auto before=inventory.observe(host,&window);
    assert(before.value("complete").toBool());assert(before.value("roots").toArray().isEmpty());
    const auto open=[&](const QString& role){
        QVariant returned;assert(QMetaObject::invokeMethod(host,"showPicker",Q_RETURN_ARG(QVariant,returned),Q_ARG(QVariant,role)));
        auto picker=qobject_cast<QQuickItem*>(returned.value<QObject*>());
        if (!picker && returned.userType()==qMetaTypeId<QJSValue>()) {picker=qobject_cast<QQuickItem*>(returned.value<QJSValue>().toQObject());}
        assert(picker);QTest::qWait(60);return picker;
    };
    QPointer<QQuickItem> picker=open("import");
    auto observed=inventory.observe(host,&window);assert(observed.value("complete").toBool());
    assert(observed.value("roots").toArray().size()==1);const auto id=inventory.identity(picker);assert(!id.isEmpty());
    assert(overte::e2e::createFileControlId(picker)=="create-file.page");
    QJsonObject page;overte::e2e::appendCreateFileObservation(page,picker,"create-file.page");
    assert(page.value("role")==QJsonValue("import"));assert(!page.value("inputReady").toBool());
    const auto source=overte::e2e::createFileControlSource(named(picker,"fileNameInput"),"create-file.name");assert(!source.isEmpty());
    // Actual scene geometry and native window identity are part of the original
    // token source, independently of text, focus and the picker role.
    const auto fileName=named(picker,"fileNameInput");
    host->setX(9);assert(overte::e2e::createFileControlSource(fileName,"create-file.name")!=source);host->setX(0);
    host->setWidth(880);QTest::qWait(20);
    assert(overte::e2e::createFileControlSource(fileName,"create-file.name")!=source);
    host->setWidth(900);QTest::qWait(20);
    assert(overte::e2e::createFileControlSource(fileName,"create-file.name")==source);
    QQuickWindow otherWindow;otherWindow.resize(window.width(),window.height());
    host->setParentItem(otherWindow.contentItem());
    const auto moved=overte::e2e::createFileControlSource(fileName,"create-file.name");assert(!moved.isEmpty() && moved!=source);
    const auto oldWindow=QJsonDocument::fromJson(source.toUtf8()).object().value("nativeWindow").toObject();
    assert(QJsonDocument::fromJson(moved.toUtf8()).object().value("nativeWindow").toObject().value("id")!=oldWindow.value("id"));
    host->setParentItem(window.contentItem());assert(overte::e2e::createFileControlSource(fileName,"create-file.name")==source);
    host->setScale(1e12);assert(overte::e2e::createFileControlSource(fileName,"create-file.name").isEmpty());host->setScale(1);
    QSignalSpy selected(picker,SIGNAL(selectedFile(QVariant)));
    const auto name=named(picker,"fileNameInput");assert(name);
    assert(originalCreateFileInput(name,&window,"create-file.name","activate",{}).value("performed").toBool());
    assert(originalCreateFileInput(name,&window,"create-file.name","replace",{{"text",directory+"/entity-import.json"}}).value("performed").toBool());
    assert(name->property("text").toString()==directory+"/entity-import.json");
    assert(!originalCreateFileInput(name,&window,"create-file.name","replace",{{"text","/foreign/entity-import.json"}}).value("performed").toBool());
    assert(originalCreateFileInput(named(picker,"fileAccept"),&window,"create-file.accept","activate",{}).value("performed").toBool());
    QTest::qWait(60);assert(selected.count()==1);assert(selected.at(0).at(0).toUrl()==QUrl::fromLocalFile(directory+"/entity-import.json"));
    assert(!picker);observed=inventory.observe(host,&window);assert(observed.value("roots").toArray().isEmpty());assert(observed.value("retiredRoots").toArray().contains(id));
    // Actual Cancel and QObject retirement are required independently.
    picker=open("import");inventory.observe(host,&window);const auto canceledId=inventory.identity(picker);
    QSignalSpy canceled(picker,SIGNAL(canceled()));
    picker->setVisible(false);observed=inventory.observe(host,&window);
    assert(observed.value("roots").toArray().size()==1);assert(!observed.value("roots").toArray()[0].toObject().value("visible").toBool());
    assert(!originalCreateFileInput(named(picker,"fileCancel"),&window,"create-file.cancel","activate",{}).value("performed").toBool());
    picker->setVisible(true);
    assert(originalCreateFileInput(named(picker,"fileCancel"),&window,"create-file.cancel","activate",{}).value("performed").toBool());
    QTest::qWait(60);assert(canceled.count()==1);assert(!picker);observed=inventory.observe(host,&window);
    assert(observed.value("retiredRoots").toArray().contains(canceledId));
    // The real Save browser emits its original selected URL. No storage helper
    // or reference payload creates an export during this input/source test.
    picker=open("export");inventory.observe(host,&window);QSignalSpy saved(picker,SIGNAL(selectedFile(QVariant)));
    assert(overte::e2e::createFileRole(picker)=="export");
    assert(originalCreateFileInput(named(picker,"fileNameInput"),&window,"create-file.name","activate",{}).value("performed").toBool());
    assert(originalCreateFileInput(named(picker,"fileNameInput"),&window,"create-file.name","replace",{{"text",directory+"/export.json"}}).value("performed").toBool());
    assert(originalCreateFileInput(named(picker,"fileAccept"),&window,"create-file.accept","activate",{}).value("performed").toBool());
    QTest::qWait(60);assert(saved.count()==1);assert(saved.at(0).at(0).toUrl()==QUrl::fromLocalFile(directory+"/export.json"));
    assert(!QFileInfo::exists(directory+"/export.json"));assert(!picker);inventory.observe(host,&window);
    // Changing a live browser's role cannot inherit its earlier identity.
    picker=open("import");inventory.observe(host,&window);
    picker->setProperty("saveDialog",true);picker->setProperty("caption","Select Where to Save");
    assert(!inventory.observe(host,&window).value("complete").toBool());
    picker->setParentItem(nullptr);assert(!inventory.observe(host,&window).value("complete").toBool());delete picker;
    assert(inventory.observe(host,&window).value("complete").toBool());
    delete host;return 0;
}
