"""Original Qt VR menu delegates/native QAction bridge with host window seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]


def function(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


class ViewMenuNativeTests(unittest.TestCase):
    def test_original_tablet_menu_pointer_reaches_original_native_exclusive_actions(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');libraries=[]
        self.assertIn(major,('5','6'));prefix=None
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
                LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
                QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QML_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'))
            libraries=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',
            *('Qt'+major+module for module in ('Core','Gui','Qml','Quick','Widgets','Test'))],text=True,env=environment))
        header=(ROOT/'libraries/ui/src/VrMenu.h').read_text();code=(ROOT/'libraries/ui/src/VrMenu.cpp').read_text()
        declaration=header[header.index('class MenuUserData :'):header.index('class VrMenu :')]
        declaration=declaration[:declaration.rindex('};')+2]
        methods='\n'.join(function(code,signature) for signature in (
            'MenuUserData::MenuUserData(', 'MenuUserData::~MenuUserData()',
            'void MenuUserData::updateQmlItemFromAction()', 'void MenuUserData::clear()',
            'bool MenuUserData::hasData(', 'MenuUserData* MenuUserData::forObject(',
            'void bindActionToQmlAction('))
        with tempfile.TemporaryDirectory(prefix='pico-view-menu-') as directory:
            stage=Path(directory);binary=stage/'test'
            (stage/'ActualMenuBinding.h').write_text('#pragma once\n#include <QAction>\n#include <QMenu>\n#include <QUuid>\n'+declaration+'\n')
            (stage/'ActualMenuBinding.inc').write_text(methods)
            native=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
            branch=function(native,'    if (controlId.startsWith("view-menu.")) {')
            (stage/'ActualViewInput.inc').write_text('static overte::e2e::ViewMenuContext fixtureViewContext;\nstatic auto viewMenuContext(){return fixtureViewContext;}\nQJsonObject originalViewInput(QQuickItem* item,QQuickWindow* window,const QString& controlId,\nconst QString& action,const std::function<bool(QQuickItem*)>& pointerClick){\nQJsonObject result{{"performed",false}},current{{"viewMenuControlsVersion",1}};bool delivered=false;\nstruct {QQuickItem* item;}control{item};\n'+branch+'\nresult["performed"]=delivered;return result;}\n')
            (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public: inline static QUrl qml,scripts;\n'
                'static QUrl defaultScriptsLocation(){return scripts;}static QUrl qmlUrl(const QString& s){return qml.resolved(QUrl(s));}};\n')
            if prefix:
                moc=prefix/'usr/bin/moc-qt5'
                if not moc.is_file():moc=prefix/'usr/lib64/qt5/bin/moc'
            else:
                moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt'+major+'Core'],text=True,env=environment).strip())/'moc'
            subprocess.run([str(moc),str(stage/'ActualMenuBinding.h'),'-o',str(stage/'moc.cpp')],check=True,timeout=20,env=environment)
            built=subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS',
                '-I'+directory,'-I'+str(ROOT),'-I'+str(ROOT/'libraries/ui/src'),
                str(Path(__file__).with_name('view-menu-native.cpp')),str(stage/'moc.cpp'),
                str(ROOT/'libraries/ui/src/ui/NativeFieldInput.cpp'),'-o',str(binary),*libraries,*flags],
                capture_output=True,text=True,timeout=90,env=environment)
            self.assertEqual(0,built.returncode,built.stderr[:6000])
            for arguments in ([],['--testScript']):
                ran=subprocess.run(['unshare','--user','--map-root-user','--net',str(binary),*arguments,str(ROOT)],
                    capture_output=True,text=True,timeout=30,
                    env={**environment,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software'})
                self.assertEqual(0,ran.returncode,ran.stdout+ran.stderr)


if __name__=='__main__':unittest.main()
