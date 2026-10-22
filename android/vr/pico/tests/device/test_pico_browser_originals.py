"""Compile the selected backend and original Pico pointer/provider, with explicit Android seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from copy import deepcopy
import json
import sys
from pathlib import Path
import shlex
import subprocess
import tempfile
import zipfile
import unittest
from test_create_polyvox_controls_native import pointer_source, original

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
JAVA='''package org.overte.web;
// Explicit Android WebView/scheduler boundary. No product behavior is asserted.
public class EmbeddedWebView {
 public static long handle,birth; public static int pointers,geometryReads,focusReads,edits,ownedReads,wheels; public static String lastEdit;
 public static void create(long h,long g,String u,String a,boolean b,boolean o,int x,int y,int w,int z,int cx,int cy,int cw,int ch,String boot,String editor){handle=h;birth=g;}
 public static void destroy(long h){} public static void visibility(long h,boolean v){} public static void focus(long h,boolean v){}
 public static void featurePicoGeometry(long h,long g,long p,String id,String control){geometryReads++;}
 public static void featurePicoFocus(long h,long g,long p,String id,String control){focusReads++;}
 public static void featurePicoReadOwned(long h,long g,long p,String id){ownedReads++;}
 public static void edit(long h,long g,long p,String url,String command){edits++;lastEdit=command;}
 public static void wheel(long h,long g,long p,String u,float x,float y,float dx,float dy,float ax,float ay,boolean inverted){wheels++;}
 public static void pointer(long h,int action,float x,float y){if(action==0 || action==1)pointers++;}
}
'''

class PicoBrowserOriginalTests(unittest.TestCase):
    def test_actual_production_java_compiles_against_existing_android_and_webkit_apis(self):
        sdk=Path.home()/'Android/Sdk/platforms/android-34/android.jar'
        webkit=Path.home()/'.gradle/caches/modules-2/files-2.1/androidx.webkit/webkit/1.12.1/952ea5c16ab05a40f3b95c68e38c56cdc1ef2e97/webkit-1.12.1.aar'
        annotation=Path.home()/'.gradle/caches/modules-2/files-2.1/androidx.annotation/annotation-jvm/1.8.1/b8a16fe526014b7941c1debaccaf9c5153692dbb/annotation-jvm-1.8.1.jar'
        with tempfile.TemporaryDirectory(prefix='pico-browser-java-api-') as temporary:
            stage=Path(temporary)
            with zipfile.ZipFile(webkit) as archive:(stage/'webkit.jar').write_bytes(archive.read('classes.jar'))
            subprocess.run(['/usr/lib/jvm/temurin-21-jdk/bin/javac','-cp',os.pathsep.join(map(str,(sdk,stage/'webkit.jar',annotation))),
                '-d',str(stage),*map(str,sorted((ROOT/'android/common/web/java/org/overte/web').glob('*.java')))],check=True,timeout=45)

    def test_actual_tablet_button_component_and_original_pico_app_pointer(self):
        prefix=Path(os.environ['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        env=dict(os.environ,PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),
            QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Quick','Qt5Test'],env=env,text=True))
        with tempfile.TemporaryDirectory(prefix='pico-browser-app-original-') as temporary:
            stage=Path(temporary);pointer_source(stage);imports=stage/'imports/TabletScriptingInterface';imports.mkdir(parents=True)
            (imports/'qmldir').write_text('module TabletScriptingInterface\nsingleton Tablet 1.0 Tablet.qml\nsingleton TabletEnums 1.0 TabletEnums.qml\n')
            (imports/'Tablet.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject {function playSound(value){}}\n')
            (imports/'TabletEnums.qml').write_text('pragma Singleton\nimport QtQuick 2.7\nQtObject {readonly property int buttonClick:1;readonly property int buttonHover:2}\n')
            (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:inline static QUrl qml;static QUrl defaultScriptsLocation(){return QUrl("file:///host/scripts/");}static QUrl qmlUrl(const QString& s){return qml.resolved(QUrl(s));}};\n')
            native=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
            start=native.index('    } else if (controlId.startsWith("browser-app.")) {');end=native.index('\n    } else if (',start+10)
            branch=native[start:end].split('{',1)[1]
            (stage/'actual-browser-app-input.inc').write_text('QJsonObject originalBrowserAppInput(QQuickItem* item,QQuickWindow* window,const QString& controlId,const QString& action,const std::function<bool(QQuickItem*)>& pointerClick){\n'
                'QJsonObject result,current{{"picoBrowserAppControlsVersion",1}};bool delivered=false;struct {QQuickItem* item;} control{item};\n'+branch+'\nresult["performed"]=delivered;return result;}\n')
            binary=stage/'test'
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-I'+str(stage),'-I'+str(ROOT),
                '-I'+str(ROOT/'libraries/ui/src'),'-I'+str(ROOT/'libraries/script-engine/src'),'-isystem',str(Path(env['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),
                str(HERE/'pico-browser-apps.cpp'),'-L'+str(prefix/'usr/lib64'),'-o',str(binary),*flags],check=True,env=env,timeout=60)
            output=subprocess.check_output(['unshare','--user','--map-root-user','--net',str(binary),str(ROOT),str(stage/'imports')],text=True,env=env,timeout=20)
            self.assertIn('PASS original TabletButton',output)

    def test_actual_private_factory_binds_original_source_lock_candidate_and_read_only_role(self):
        import test_normal_scripts as original
        from unittest.mock import patch
        from adapters.normal_ui import NativeUIError
        from self_tests.test_pico_browser_io import Boundary,RUN,URL,OWNER
        from adapters.pico4.browser_source import FILE
        fixture=original.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        adapter,native=fixture.instance,fixture.native;boundary=Boundary()
        saved_write,saved_read=native.write_debug_app_file,native.read_debug_app_file
        def write(target,package,path,raw):
            call=json.loads(raw)
            if call.get('action')!='pico-tablet-web':return saved_write(target,package,path,raw)
            boundary.epoch=native.epoch_milliseconds(target);boundary.send(call)
            boundary.packet['processId']=int(native.identity.split(':')[0])
        def read(target,package,path,**options):
            if path!='files/overte-e2e/'+FILE:return saved_read(target,package,path,**options)
            self.assertEqual({'attempts':1},options);return json.dumps(boundary.packet)
        with patch.object(native,'write_debug_app_file',side_effect=write),patch.object(native,'read_debug_app_file',side_effect=read):
            lock=adapter._script_journey()._lock(native.target)
            reader=adapter._browser_originals(native.target,source_lock=lock,read_only=False)
            self.assertIs(lock,reader.lock)
            with lock.held():
                actor=adapter._browser_originals(native.target,source_lock=lock)
                with self.assertRaises(NativeUIError):actor.request(RUN,URL,OWNER,'reserve')
                packet=reader.request(RUN,URL,OWNER,'reserve')
                self.assertTrue(packet['source']['reserved'])
            self.assertEqual(1,len(boundary.calls));self.assertEqual([],native.inputs)
            native.digest='f'*64
            with lock.held(),self.assertRaises(NativeUIError):reader.request(RUN,URL,OWNER,'reserve')
            self.assertEqual(1,len(boundary.calls))

    def test_actual_native_scope_and_original_pico_pointer_with_native_ime(self):
        prefix=Path(os.environ['OVERTE_QT5_HOST_ROOT']).resolve(strict=True);jdk=Path('/usr/lib/jvm/temurin-21-jdk')
        env=dict(os.environ,PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Quick','Qt5WebChannel','Qt5Network','Qt5Test'],env=env,text=True))
        with tempfile.TemporaryDirectory(prefix='pico-browser-original-') as temporary:
            stage=Path(temporary);web=ROOT/'android/common/web';tools=prefix/'usr/lib64/qt5/bin'
            pointer_source(stage)
            route=stage/'actual-pointer-route.inc'
            route.write_text(route.read_text()+original((ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp').read_text(),'bool sendPointerScroll('))
            bridge=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp').read_text()
            (stage/'actual-browser-provider.inc').write_text(original(bridge,'void installBrowserInputProvider() {'))
            (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:static QUrl defaultScriptsLocation(){return QUrl("file:///host/scripts/");} static QUrl qmlUrl(const QString& s){return QUrl("file:///host/qml/"+s);}};\n')
            java=stage/'org/overte/web/EmbeddedWebView.java';java.parent.mkdir(parents=True);java.write_text(JAVA)
            subprocess.run([str(jdk/'bin/javac'),'-d',str(stage),str(java)],check=True,timeout=30)
            subprocess.run([str(tools/'moc'),'-DOVERTE_E2E_FEATURE_TESTS',str(web/'src/NativeWebViewItem.h'),'-o',str(stage/'moc.cpp')],check=True,timeout=30)
            for name in ('embedded-web','feature-web'):
                subprocess.run([str(tools/'rcc'),'-name',name.replace('-','_'),str(web/(name+'.qrc')),'-o',str(stage/(name+'.cpp'))],check=True,timeout=30)
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
                '-I'+str(stage),'-I'+str(ROOT),'-I'+str(web/'src'),'-I'+str(ROOT/'libraries/shared/src'),
                '-I'+str(ROOT/'libraries/ui/src'),'-I'+str(ROOT/'libraries/script-engine/src'),
                '-isystem',str(Path(env['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),
                '-I'+str(jdk/'include'),'-I'+str(jdk/'include/linux'),str(web/'src/NativeWebViewItem.cpp'),
                str(HERE/'pico-browser-originals.cpp'),str(stage/'moc.cpp'),str(stage/'embedded-web.cpp'),str(stage/'feature-web.cpp'),
                '-L'+str(prefix/'usr/lib64'),'-L'+str(jdk/'lib/server'),'-Wl,-rpath,'+str(jdk/'lib/server'),'-ljvm',
                '-o',str(stage/'test'),*flags],env=env,check=True,timeout=90)
            result=subprocess.run(['unshare','--user','--map-root-user','--net',str(stage/'test'),str(stage),
                '--testScript','host-boundary','--testResultsLocation',str(stage)],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            self.assertIn('PASS actual selected native browser',result.stdout)
            from adapters.pico4.browser_source import validate
            actual=json.loads((stage/'native-originals.json').read_text());packet=actual['packet']
            validate(packet,actual['request'],packet['processId'],packet['capturedEpochMs'])
            validate(actual['measurePacket'],actual['measureRequest'],packet['processId'],actual['measurePacket']['capturedEpochMs'])
            self.assertEqual('old',packet['source']['current']['source']['dom']['editor']['text'])
            self.assertEqual(['ready','unavailable','unavailable','ready','unavailable'],[row['completion']['status'] for row in packet['source']['inputs']])
            from adapters.normal_ui import NativeUIError
            # Historical v1 remains readable without invented wheel originals.
            historic=deepcopy(packet);historic['picoBrowserVersion']=1;historic['source']['inputs']=historic['source']['inputs'][:3]
            for row in historic['source']['inputs']:row.pop('wheelEpochMs')
            validate(historic,actual['request'],historic['processId'],historic['capturedEpochMs'])
            for mutation in ('missing-wheel','pointer-for-wheel','foreign-document','bad-scroll-point','v1-wheel'):
                corrupt=deepcopy(packet);row=corrupt['source']['inputs'][3]
                if mutation=='missing-wheel':row['wheelEpochMs']=None
                if mutation=='pointer-for-wheel':row['pointerEpochMs']=row['wheelEpochMs']
                if mutation in ('foreign-document','bad-scroll-point'):
                    geometry=json.loads(json.loads(row['geometryRaw']))
                    if mutation=='foreign-document':geometry['document']['runId']='f'*32
                    else:geometry['rect']['x']=1;geometry['center']['x']+=1
                    row['geometryRaw']=json.dumps(json.dumps(geometry))
                if mutation=='v1-wheel':
                    corrupt['picoBrowserVersion']=1
                    for item in corrupt['source']['inputs']:item.pop('wheelEpochMs')
                with self.subTest(mutation=mutation),self.assertRaises(NativeUIError):
                    validate(corrupt,actual['request'],corrupt['processId'],corrupt['capturedEpochMs'])


if __name__=='__main__':unittest.main()
