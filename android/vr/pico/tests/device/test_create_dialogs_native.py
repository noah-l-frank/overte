"""Actual original Qt picker→ModalDialogListener→Window delivery/source test."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

import test_create_file_ui_native as browser

HERE=Path(__file__).resolve().parent
ROOT=browser.ROOT
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.create_dialogs import active,continuity,validate,ui_bindings,joined


class CreateDialogsNativeTests(unittest.TestCase):
    def test_original_file_dialog_listener_and_window_callback_delivery(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
        moc=shutil.which('moc'+major) or shutil.which('moc')
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            moc=str(prefix/'usr/lib64/qt5/bin/moc')
            environment['LD_LIBRARY_PATH']=str(prefix/'usr/lib64')
        self.assertIsNotNone(moc)
        source=(ROOT/'libraries/ui/src/OffscreenUi.cpp').read_text()
        declaration=(ROOT/'libraries/ui/src/OffscreenUi.h').read_text()
        window=(ROOT/'interface/src/scripting/WindowScriptingInterface.cpp').read_text()
        modal=declaration[declaration.index('class ModalDialogListener :'):declaration.index('class OffscreenUi :')]
        listener=browser.function(source,'class FileDialogListener :')+';\n'
        header='''#pragma once
#define OVERTE_E2E_FEATURE_TESTS 1
#define ANDROID_APP_PICO_INTERFACE 1
#include "PicoCreateDialogs.h"
#include <QFileDialog>
#include <QFileInfo>
#include <QTimer>
#include <QRegularExpression>
#include <QSharedPointer>
#include <type_traits>
'''+modal+listener+'''
class TabletProxy:public QObject {public:QQuickItem* root=nullptr;bool getToolbarMode(){return false;}QQuickItem* getTabletRoot(){return root;}};
class TabletScriptingInterface:public QObject {public:TabletProxy tablet;QObject* getTablet(const QString&){return &tablet;}void tabletNotification(){}};
class OffscreenUi:public QObject {
 Q_OBJECT
public:
 static ModalDialogListener* getOpenFileNameAsync(void*,const QString&,const QString&,const QString&,QString* =nullptr,QFileDialog::Options ={});
 static ModalDialogListener* getSaveFileNameAsync(void*,const QString&,const QString&,const QString&,QString* =nullptr,QFileDialog::Options ={});
 Q_INVOKABLE ModalDialogListener* fileOpenDialogAsync(const QString&,const QString&,const QString&,QString*,QFileDialog::Options);
 Q_INVOKABLE ModalDialogListener* fileSaveDialogAsync(const QString&,const QString&,const QString&,QString*,QFileDialog::Options);
 ModalDialogListener* fileDialogAsync(const QVariantMap&);
 void registerModalDialog(ModalDialogListener*);void removeModalDialog(QObject*);
 QVariantMap featureCreateDialogs(){return _featureCreateDialogs->snapshot();}
 QVariantMap featureCreateDialogIdentity(QQuickItem* root){return _featureCreateDialogs->rootIdentity(root);}
 QQuickItem* _desktop=nullptr;QList<QObject*> _modalDialogListeners;
 std::shared_ptr<overte::e2e::CreateDialogs> _featureCreateDialogs {std::make_shared<overte::e2e::CreateDialogs>()};
};
inline std::shared_ptr<OffscreenUi> offscreen;
inline std::shared_ptr<TabletScriptingInterface> tablets;
inline bool offscreenAvailable=true;inline int offscreenGets=0;
struct DependencyManager {template<typename T>static bool isSet(){return offscreenAvailable;}
 template<typename T>static std::shared_ptr<T> get(){
 if constexpr(std::is_same<T,OffscreenUi>::value){++offscreenGets;}
 if constexpr(std::is_same<T,OffscreenUi>::value){return offscreen;}else{return tablets;}
}};
class WindowScriptingInterface:public QObject {
 Q_OBJECT
public:
 Q_INVOKABLE void browseAsync(const QString&,const QString&,const QString&);Q_INVOKABLE void saveAsync(const QString&,const QString&,const QString&);
 void ensureReticleVisible(){}QString previous;QString getPreviousBrowseLocation() const{return previous;}
 void setPreviousBrowseLocation(const QString& value){previous=value;}
signals:
 void browseChanged(const QString&);void saveFileChanged(const QString&);
};
struct Lifecycle {QVariantMap snapshot()const{return {{"launches",1}};}};
class TestScriptingInterface:public QObject {
public:
 QVariantMap featureCreateDialogs(const QString&);
 QString _testResultsLocation="/owned-private-results",_featureObservationInstance=QString(32,'a');
 std::shared_ptr<Lifecycle> _featureLifecycle {std::make_shared<Lifecycle>()};
 quint64 _featureCreateDialogsSequence=0;QHash<QString,QVariantMap> _featureCreateDialogsResults;
};
#define BLOCKING_INVOKE_METHOD(object,name,...) QMetaObject::invokeMethod(object,name,Qt::BlockingQueuedConnection,__VA_ARGS__)
'''
        signatures=('void OffscreenUi::removeModalDialog(', 'void OffscreenUi::registerModalDialog(',
            'ModalDialogListener* OffscreenUi::fileDialogAsync(', 'ModalDialogListener* OffscreenUi::fileOpenDialogAsync(',
            'ModalDialogListener* OffscreenUi::fileSaveDialogAsync(', 'ModalDialogListener* OffscreenUi::getOpenFileNameAsync(',
            'ModalDialogListener* OffscreenUi::getSaveFileNameAsync(', 'ModalDialogListener::ModalDialogListener(',
            'ModalDialogListener::~ModalDialogListener(', 'QVariant ModalDialogListener::waitForResult(',
            'void ModalDialogListener::finish(', 'void ModalDialogListener::onDestroyed(')
        originals='\n'.join(browser.function(source,s) for s in signatures)
        originals+='\n'+'\n'.join(browser.function(window,s) for s in ('QString fixupPathForMac(',
            'void WindowScriptingInterface::browseAsync(', 'void WindowScriptingInterface::saveAsync('))
        getter=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        originals+='\n'+browser.function(getter,'QVariantMap TestScriptingInterface::featureCreateDialogs(')
        with tempfile.TemporaryDirectory(prefix='pico-create-dialogs-') as directory:
            stage=Path(directory);(stage/'DialogHarness.h').write_text(header);(stage/'OriginalDialogs.inc').write_text(originals)
            shutil.copyfile(HERE/'create-dialogs-native.cpp',stage/'create-dialogs-native.cpp')
            subprocess.run([moc,'-I'+str(ROOT/'tests/device/native'),str(stage/'DialogHarness.h'),'-o',str(stage/'moc_DialogHarness.cpp')],
                check=True,timeout=20,env=environment)
            fixture=browser.CreateFileUINativeTests();fixture.native_source=stage/'create-dialogs-native.cpp'
            fixture.additional_qml=('dialogs/TabletFileDialog.qml',)
            tablet=(ROOT/'interface/resources/qml/hifi/tablet/TabletRoot.qml').read_text()
            factory=browser.function(tablet,'    function fileDialog(properties)').replace('../../dialogs/TabletFileDialog.qml','dialogs/TabletFileDialog.qml')
            fixture.extra_host='\n property var tabletRoot:root\n property var openModal:null\n'+factory
            def original_packets(output):
                values=[json.loads(line) for line in output.splitlines()];join=values.pop()
                packets=values;self.assertGreaterEqual(len(packets),4)
                previous=None
                for packet in packets:
                    validate(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'])
                    continuity(previous,packet);previous=packet
                self.assertTrue(active(packets[0]));self.assertTrue(active(packets[1]))
                actual=ui_bindings(join['dialogBindings'],join['uiInventory'])
                self.assertTrue(actual['complete']);self.assertEqual(1,len(actual['bindings']))
                original=joined(actual['bindings'][0]['native'],packets[0])
                self.assertTrue(original['pending']);self.assertTrue(original['componentSource'].endswith('/dialogs/TabletFileDialog.qml'))
            fixture.native_output=original_packets
            fixture.test_actual_browser_cancel_import_save_and_weak_resource_retirement()


if __name__=='__main__':unittest.main()
