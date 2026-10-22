"""Compile the passive reader and load unchanged native Snapshot review QML.

The Snapshot service is a synthetic script boundary, the desktop export backend
is unchanged. This is not an Android export or device acceptance test.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
SOURCE=r'''
#include <QGuiApplication>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickWindow>
#include <QDebug>
#include <memory>
#include "tests/device/native/PhoneSnapshotReviewObservation.h"
using namespace overte::e2e;
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);QQmlEngine engine;engine.addImportPath(argv[1]);
    QQmlComponent helper(&engine);helper.setData(R"(import QtQml
QtObject { property string format:"png"
 function getAvailableSnapshotFormats(){return ["png","jpg","webp"]}
 function getSnapshotFormat(){return format}
 function setSnapshotFormat(value){format=value}
 function snapshotFileUrl(path){return ""}
})",QUrl("file:///snapshot-service-double.qml"));
    std::unique_ptr<QObject> service(helper.create());if(!service) { return 1; }
    engine.rootContext()->setContextProperty("Snapshot",service.get());
    QQmlComponent component(&engine,QUrl::fromLocalFile(QString::fromLocal8Bit(argv[2])));
    std::unique_ptr<QObject> object(component.create());if(!object) { qWarning()<<component.errors();return 2; }
    auto page=qobject_cast<QQuickItem*>(object.get());QQuickWindow window;
    window.setGeometry(0,0,480,900);page->setWidth(480);page->setHeight(900);page->setParentItem(window.contentItem());
    QQuickItem absent;absent.setParentItem(window.contentItem());
    auto state=phoneSnapshotReviewObservation(&absent);
    if (state.value("present")!=false || !state.value("review").isNull()) { return 3; }
    state=phoneSnapshotReviewObservation(page);auto view=state.value("review").toMap();
    if (state.value("present")!=true || view.value("capturing")!=false || view.value("mode")!=0 || view.value("format")!="png") {
        qWarning()<<state;return 4;
    }
    auto deliver=[&](const QVariantMap& payload) {
        QVariant value=payload;
        return QMetaObject::invokeMethod(page,"fromScript",Q_ARG(QVariant,value));
    };
    if(!deliver({{"type","snapshot"},{"action","captureSettings"},{"setting",false}})
            || !deliver({{"type","snapshot"},{"action","clearPreviousImages"}})) { return 5; }
    view=phoneSnapshotReviewObservation(page).value("review").toMap();
    if(view.value("capturing")!=true || view.value("processing")!=false || view.value("captureSettingsLoaded")!=true) { return 6; }
    if(!deliver({{"type","snapshot"},{"action","captureStatus"},{"phase","cancelled"}})) { return 7; }
    view=phoneSnapshotReviewObservation(page).value("review").toMap();
    if(view.value("capturing")!=false || !view.value("images").toList().isEmpty()) { return 8; }
    page->setVisible(false);state=phoneSnapshotReviewObservation(page);
    if(state.value("present")!=true || state.value("review").toMap().value("visible")!=false) { return 9; }
    page->setVisible(true);
    QQuickItem foreign;foreign.setObjectName("snapshotReview");foreign.setParentItem(page);
    if(!phoneSnapshotReviewObservation(page).isEmpty()) { return 10; }
    foreign.setParentItem(nullptr);
    std::unique_ptr<QObject> second(component.create());auto duplicate=qobject_cast<QQuickItem*>(second.get());
    if(!duplicate) { return 11; }duplicate->setParentItem(page);
    if(!phoneSnapshotReviewObservation(page).isEmpty()) { return 12; }
    duplicate->setParentItem(nullptr);
    if(phoneSnapshotReviewObservation(page).value("present")!=true) { return 13; }
    page->setParentItem(nullptr);absent.setParentItem(nullptr);
    return 0;
}
'''


class SnapshotNativeReviewTests(unittest.TestCase):
    def test_original_component_pending_cancel_hidden_absence_foreign_and_duplicate_pages(self):
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core','Qt6Gui','Qt6Qml','Qt6Quick'],text=True))
        build=ROOT/'build/snapshot-native-contract';build.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='review-',dir=build) as temporary:
            stage=Path(temporary);(stage/'controls').mkdir();page=stage/'system/snapshot/NativeSnapshotReview.qml'
            page.parent.mkdir(parents=True)
            for name in ('NativeSnapshotReview.qml','SnapshotPlatform.qml'):
                shutil.copyfile(ROOT/'scripts/system/snapshot'/name,page.parent/name)
            shutil.copyfile(ROOT/'interface/resources/qml/controls/SnapshotPlatformBackend.qml',stage/'controls/SnapshotPlatformBackend.qml')
            (stage/'controls/qmldir').write_text('module controls\nSnapshotPlatformBackend 1.0 SnapshotPlatformBackend.qml\n')
            cpp=stage/'source.cpp';cpp.write_text(SOURCE)
            subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
                '-I'+str(ROOT),str(cpp),'-o',str(stage/'check'),*flags],check=True,timeout=60)
            subprocess.run([str(stage/'check'),str(stage),str(page),'--testScript'],check=True,timeout=15,
                env=os.environ|{'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'})


if __name__=='__main__':unittest.main()
