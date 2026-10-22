"""Compile passive Create identities against Qt and load unchanged product QML.

Native entity instrumentation and the Android binary are not compiled here.
Only native file services and the unused touch-style service are doubled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]

SOURCE=r'''
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQmlContext>
#include <QDebug>
#include <iostream>
#include <QElapsedTimer>
#include <QThread>
#include <memory>
#include "tests/device/native/NormalScriptControls.h"
#include "tests/device/native/NormalAudioControls.h"
#include "tests/device/native/NormalCreateControls.h"
using namespace overte::e2e;
QQuickItem* find(QQuickItem* item,const QString& name) {
    if (item->objectName()==name) { return item; }
    for (auto child:item->childItems()) { if (auto result=find(child,name)) { return result; } }
    return nullptr;
}
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);QQmlEngine engine;engine.addImportPath(argv[1]);
    QQmlComponent helper(&engine);
    helper.setData(R"(import QtQml
QtObject {
 signal documentsSelected(string id,var urls)
 signal documentSelectionCanceled(string id)
 signal documentSelectionFailed(string id,string message)
 signal contentsChanged()
 function home() { return "file:///tmp" }
 function urlToPath(url) { return String(url).replace("file://","") }
 function drives() { return [] }
})",QUrl("file:///create-test-helper.qml"));
    std::unique_ptr<QObject> service(helper.create());if (!service) { return 1; }
    engine.rootContext()->setContextProperty("fileDialogHelper",service.get());
    QQmlComponent component(&engine,QUrl::fromLocalFile(QString::fromLocal8Bit(argv[2])));
    std::unique_ptr<QObject> object(component.create());
    if (!object) { qWarning()<<component.errors();return 2; }
    auto root=qobject_cast<QQuickItem*>(object.get());
    if (!root || createControlId(root)!="create.page") { return 3; }
    QJsonObject page;appendCreateControlObservation(page,root,"create.page");
    if (page.value("profile")!="native-create-v1" || !page.value("selectedIds").toArray().isEmpty()) { return 4; }
    if (page.contains("toolSettings")) { return 19; }
    const QVariantMap settings{{"createAppMode","voxel"},{"voxelEditMode","cube"},{"voxelSphereSize",2.0},
        {"voxelEditDynamics","click"},{"voxelRemove",true},{"voxelPointerMode","laser"},{"voxelBrushLength",3.0}};
    const QVariant message=QVariantMap{{"method","nativeCreate.settings"},{"params",settings}};
    if (!QMetaObject::invokeMethod(root,"fromScript",Q_ARG(QVariant,message))) { return 20; }
    page={};appendCreateControlObservation(page,root,"create.page");
    if (page.value("toolSettings").toObject()!=QJsonObject::fromVariantMap(settings)) { return 21; }
    const QHash<QString,QString> ids{{"NativeCreateEditMode","create.edit-mode"},{"NativeCreateVoxelShape","create.voxel-shape"},
      {"NativeCreateVoxelDynamics","create.voxel-dynamics"},{"NativeCreateVoxelPointer","create.voxel-pointer"},
      {"NativeCreateVoxelDiameter","create.voxel-diameter"},{"NativeCreateVoxelReach","create.voxel-reach"},
      {"NativeCreateVoxelRemove","create.voxel-remove"},{"NativeCreatePropertySearch","create.property-filter"}};
    for (auto iter=ids.begin();iter!=ids.end();++iter) {
        auto item=find(root,iter.key());if (!item || createControlId(item)!=iter.value()) { qWarning()<<iter.key();return 5; }
        QJsonObject row;appendCreateControlObservation(row,item,iter.value());
        if (createChoice(iter.value()) && (!row.value("count").isDouble() || !row.value("currentIndex").isDouble())) { return 6; }
        if (createField(iter.value()) && !row.value("text").isString()) { return 7; }
        if (iter.value()=="create.voxel-remove" && !row.value("checked").isBool()) { return 8; }
    }
    QQmlComponent browser(&engine,QUrl::fromLocalFile(QString::fromLocal8Bit(argv[3])));
    QElapsedTimer wait;wait.start();
    while (browser.isLoading() && wait.elapsed()<2000) { app.processEvents();QThread::msleep(1); }
    std::unique_ptr<QObject> file(browser.create());if (!file) { for (auto error:browser.errors()) { std::cerr<<error.toString().toStdString()<<"\n"; } return 9; }
    auto picker=qobject_cast<QQuickItem*>(file.get());picker->setProperty("destroyOnCompletion",false);
    auto name=find(picker,"fileNameInput"),accept=find(picker,"fileAccept"),cancel=find(picker,"fileCancel");
    if (!name || !accept || !cancel || !createControlId(name).isEmpty()) { return 10; }
    picker->setProperty("caption","Select .json to Import");picker->setProperty("filter","*.json");
    if (createControlId(name)!="create-file.name" || createControlId(accept)!="create-file.accept"
            || createControlId(cancel)!="create-file.cancel") { return 11; }
    QJsonObject row;appendCreateControlObservation(row,name,"create-file.name");
    if (row.value("picker").toObject().value("save")!=false || !row.value("text").isString()) { return 12; }
    const auto original=createControlSource(name,"create-file.name");
    picker->setProperty("requestId","pending-system-document");
    if (createControlSource(name,"create-file.name")==original) { return 13; }
    row={};appendCreateControlObservation(row,name,"create-file.name");
    if (row.value("inputReady").toBool() || !row.value("picker").toObject().value("pendingDocuments").toBool()) { return 14; }
    picker->setProperty("requestId","");picker->setProperty("closing",true);
    row={};appendCreateControlObservation(row,name,"create-file.name");if (row.value("inputReady").toBool()) { return 15; }
    picker->setProperty("closing",false);picker->setProperty("saveDialog",true);
    if (!createControlId(name).isEmpty()) { return 16; }
    picker->setProperty("caption","Select Where to Save");
    if (createControlId(name)!="create-file.name") { return 17; }
    picker->setProperty("bundleMode",true);if (!createControlId(name).isEmpty()) { return 18; }
    return 0;
}
'''


class CreateNativeUITests(unittest.TestCase):
    def test_native_identities_read_unchanged_create_and_file_browser_widgets(self):
        self.assertIsNotNone(shutil.which('c++'),'A prepared Qt/compiler host is required')
        flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui','Qt6Quick','Qt6Qml'],text=True).split()
        build=ROOT/'build/create-native-contract';build.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='check-',dir=build) as temporary:
            stage=Path(temporary)
            (stage/'controlsUit').mkdir();(stage/'hifi/dialogs').mkdir(parents=True);(stage/'dialogs').mkdir()
            (stage/'controlsUit/qmldir').write_text('module controlsUit\nTouchUiMetrics 1.0 TouchUiMetrics.qml\n')
            (stage/'controlsUit/TouchUiMetrics.qml').write_text('import QtQml\nQtObject {}\n')
            (stage/'hifi/dialogs/NativeKeyboardHost.qml').write_text('import QtQuick\nItem { property bool inputFocused: false }\n')
            browser=stage/'dialogs/NativeFileBrowser.qml'
            shutil.copyfile(ROOT/'interface/resources/qml/dialogs/NativeFileBrowser.qml',browser)
            (stage/'source.cpp').write_text(SOURCE)
            subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
                '-I'+str(ROOT),str(stage/'source.cpp'),'-o',str(stage/'check'),*flags],check=True,timeout=60)
            subprocess.run([str(stage/'check'),str(stage),str(ROOT/'scripts/system/create/qml/NativeCreate.qml'),str(browser),'--testScript'],
                check=True,timeout=30,env=os.environ|{'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software','QT_LOGGING_RULES':'*.warning=true'})


if __name__=='__main__':unittest.main()
