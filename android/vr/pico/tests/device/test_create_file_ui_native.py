"""Selected actual Qt Create JSON/Save source/input test, without an app/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]


def function(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


class CreateFileUINativeTests(unittest.TestCase):
    native_source=None
    extra_host=''
    additional_qml=()
    native_output=None
    def test_actual_browser_cancel_import_save_and_weak_resource_retirement(self):
        major=os.environ.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'))
        environment=dict(os.environ);library_paths=[];moc=shutil.which('moc'+major) or shutil.which('moc')
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
                LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
                QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
            library_paths=['-L'+str(prefix/'usr/lib64')];moc=str(prefix/'usr/lib64/qt5/bin/moc')
        self.assertIsNotNone(moc)
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt'+major+module for module in ('Core','Gui','Qml','Quick','Widgets','Test'))],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-create-file-ui-') as directory:
            stage=Path(directory);(stage/'dialogs').mkdir();(stage/'hifi/dialogs').mkdir(parents=True);(stage/'controlsUit').mkdir()
            shutil.copyfile(ROOT/'interface/resources/qml/dialogs/NativeFileBrowser.qml',stage/'dialogs/NativeFileBrowser.qml')
            for relative in self.additional_qml:
                shutil.copyfile(ROOT/'interface/resources/qml'/relative,stage/relative)
            (stage/'hifi/dialogs/NativeKeyboardHost.qml').write_text('import QtQuick 2.7\nItem {property bool inputFocused:false;implicitHeight:0}\n')
            (stage/'controlsUit/qmldir').write_text('module controlsUit\nTouchUiMetrics 1.0 TouchUiMetrics.qml\n')
            (stage/'controlsUit/TouchUiMetrics.qml').write_text('import QtQuick 2.7\nQtObject {}\n')
            host_source='''import QtQuick 2.7
Item {
 id: root
 function showPicker(role) {
  var component=Qt.createComponent("dialogs/NativeFileBrowser.qml");
  if(component.status!==Component.Ready){console.warn(component.errorString());return null;}
  return component.createObject(root,{width:root.width,height:root.height,dir:fixtureDirectory,
   caption:role==="import"?"Select .json to Import":"Select Where to Save",filter:"*.json",saveDialog:role==="export"});
 }
}'''
            (stage/'Host.qml').write_text(host_source[:-1]+self.extra_host+'\n}')
            original=(ROOT/'tests/device/native/NormalControlUi.h').read_text()
            geometry=function(original,'    static QRectF visibleRect(')+'\n'+function(original,'    static bool ownsPoint(')
            native=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
            start=native.index('    } else if (controlId.startsWith("create-file.")) {')
            end=native.index('    } else if (controlId.startsWith("create.")) {',start)
            branch=native[start:end].split('{',1)[1]
            (stage/'CreateFileAdmission.inc').write_text('namespace overte::e2e { class NormalControlUi {public:\n'+geometry+'\n};}\n'
                'QJsonObject originalCreateFileInput(QQuickItem* item,QQuickWindow* window,const QString& controlId,const QString& action,const QJsonObject& command){\n'
                'QJsonObject result{{"performed",false}},current{{"createFileControlsVersion",1}};bool delivered=false;struct {QQuickItem* item;} control{item};\n'
                'std::function<bool(QQuickItem*)> pointerClick=[&](QQuickItem* target){const auto p=target->mapToScene(QPointF(target->width()/2,target->height()/2));QTest::mouseClick(window,Qt::LeftButton,Qt::NoModifier,p.toPoint());return true;};\n'
                +branch+'\nresult["performed"]=delivered;return result;}\n')
            helper=ROOT/'libraries/ui/src/FileDialogHelper.h'
            subprocess.run([moc,str(helper),'-o',str(stage/'moc_FileDialogHelper.cpp')],check=True,timeout=20,env=environment)
            binary=stage/'create-ui-test'
            subprocess.run(['c++','-std=c++17','-fPIC','-I'+directory,'-I'+str(ROOT/'tests/device/native'),
                '-I'+str(ROOT/'libraries/ui/src'),str(self.native_source or HERE/'create-file-ui-native.cpp'),str(stage/'moc_FileDialogHelper.cpp'),
                str(ROOT/'libraries/ui/src/FileDialogHelper.cpp'),str(ROOT/'libraries/ui/src/ui/Logging.cpp'),
                str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(binary),*library_paths,*flags],
                check=True,timeout=90,env=environment)
            runtime=stage/'runtime';runtime.mkdir(mode=0o700)
            environment.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QSG_RENDER_LOOP='basic',XDG_RUNTIME_DIR=str(runtime))
            if self.native_output is None:
                subprocess.run([str(binary),directory,'--testScript'],check=True,timeout=30,env=environment)
            else:self.native_output(subprocess.check_output([str(binary),directory,'--testScript'],timeout=30,env=environment,text=True))


if __name__=='__main__':unittest.main()
