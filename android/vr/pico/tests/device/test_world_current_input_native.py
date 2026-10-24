"""Actual original World retained-page foreground/finish-source boundary.

No producer/protocol changes: Java WebView/DOM/inventory callbacks are explicit
recorders, while the complete original native endpoint and JNI execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device'),str(HERE)]
import test_pico_browser_originals as assembly
from test_create_polyvox_controls_native import pointer_source,original


class WorldCurrentInputNativeTests(unittest.TestCase):
    def test_actual_same_authority_readonly_ray_normal_pointer_focus_and_dom(self):
        byte_only=False
        directory=tempfile.TemporaryDirectory(prefix='world-current-input-');directory._finalizer.detach()
        stage=Path(directory.name);stage.chmod(0o700)
        print('Retained original World resume/native stage:',stage,flush=True)
        prefix=Path(os.environ['OVERTE_QT5_HOST_ROOT']).resolve(strict=True);jdk=Path('/usr/lib/jvm/temurin-21-jdk')
        env=dict(os.environ,PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'),QT_PLUGIN_PATH=str(prefix/'usr/lib64/qt5/plugins'),
            QML2_IMPORT_PATH=str(prefix/'usr/lib64/qt5/qml'),QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
        deadline=time.monotonic()+90;commands=[]
        def run(arguments,*,build=True):
            arguments=[str(value) for value in arguments];commands.append(arguments)
            (stage/'commands.json').write_text(json.dumps(commands));(stage/'commands.json').chmod(0o600)
            remaining=deadline-time.monotonic() if build else 30
            self.assertGreater(remaining,0)
            result=subprocess.run(arguments,env=env,capture_output=True,text=True,timeout=remaining)
            log=stage/('command-'+str(len(commands))+'.json')
            log.write_text(json.dumps(dict(arguments=arguments,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)));log.chmod(0o600)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr);return result
        flags=shlex.split(run(['pkg-config','--cflags','--libs','Qt5Quick','Qt5WebChannel','Qt5Network','Qt5Test']).stdout)
        web=ROOT/'android/common/web';tools=prefix/'usr/lib64/qt5/bin';pointer_source(stage)
        route=stage/'actual-pointer-route.inc';bridge=(ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eTabletBridge.cpp').read_text()
        route.write_text(route.read_text()+original(bridge,'bool sendPointerScroll('))
        (stage/'actual-browser-provider.inc').write_text(original(bridge,'void installBrowserInputProvider() {')+'\n'+original(bridge,'void installWorldWebTextProvider() {'))
        (stage/'PathUtils.h').write_text('#pragma once\n#include <QUrl>\nclass PathUtils {public:static QUrl defaultScriptsLocation(){return QUrl("file:///host/scripts/");}static QUrl qmlUrl(const QString& s){return QUrl("file:///host/qml/"+s);}};\n')
        # Reuse the existing declared JNI recorder. No producer lifecycle body
        # is copied/repaired here. These two methods record dispatch only.
        # Only declared host dependency types are substituted. Provider,
        # RayPick and renderer function bodies remain complete originals.
        base=(HERE/'pico-browser-originals.cpp').read_text()
        old=original(base,'struct DependencyManager {')+';'
        base=base.replace(old,(HERE/'world-current-input-boundaries.inc').read_text())
        (stage/'current-browser-assembly.inc').write_text(base)
        provider=stage/'actual-browser-provider.inc'
        provider.write_text(provider.read_text()+'\n'+original(bridge,'void installWorldWebRayProvider() {'))
        renderer=(ROOT/'libraries/entities-renderer/src/RenderableWebEntityItem.cpp').read_text()
        raypick=(ROOT/'interface/src/raypick/RayPick.cpp').read_text()
        constants='\n'.join(line for line in renderer.splitlines() if line.startswith('const float METERS_TO_INCHES ='))
        (stage/'current-renderer-raypick.inc').write_text(constants+'\n'+original(renderer,'void WebEntityRenderer::handlePointerEventAsMouse(')+'\n'+original(raypick,'glm::vec2 RayPick::projectOntoXYPlane('))
        java_boundary=assembly.JAVA.replace('handle=h;birth=g;', 'handle=h;birth=g;modelFocused=false;modelDOMSequence=0;modelDOMInstance=java.util.UUID.randomUUID().toString().replace("-","");').replace('if(action==0 || action==1)pointers++;',
            'if(action==0 || action==1)pointers++;if(action==0 && x>=80 && x<=240 && y>=60 && y<=140)modelFocused=true;')
        java=stage/'org/overte/web/EmbeddedWebView.java';java.parent.mkdir(parents=True)
        java.write_text(java_boundary.rsplit('}',1)[0]+''' public static boolean modelFocused;public static String modelText="",modelDOMInstance;
 public static int currentInputReads,modelDOMSequence;
 public static void featurePicoCurrentInputRead(long h,long c,long g,long p,String run,String id,String source,String control){currentInputReads++;modelDOMSequence++;}
 public static int currentReads;
 public static void featurePicoCurrentDocumentRead(long h,long c,long g,long p,String run,String id,String source){currentReads++;modelDOMSequence++;}
 public static int worldReads;public static String worldQueries="",runtimeQueries="";
 public static void featureRead(long h,long g,long p,String id){worldReads++;modelDOMSequence++;worldQueries+=h+","+g+","+p+","+id+";";}
 public static void featureRuntimeSnapshot(String id,String root,String known){runtimeQueries+=id+";"+root+";"+known;}
}
''')
        run([jdk/'bin/javac','-d',stage,java])
        run([tools/'moc','-DOVERTE_E2E_FEATURE_TESTS',web/'src/NativeWebViewItem.h','-o',stage/'moc.cpp'])
        for name in ('embedded-web','feature-web'):
            run([tools/'rcc','-name',name.replace('-','_'),web/(name+'.qrc'),'-o',stage/(name+'.cpp')])
        (stage/'original-current-getter.inc').write_text(original((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featurePicoWorldCurrentDocument('))
        sources=[web/'src/PicoWorldCurrentDocumentBridge.cpp',ROOT/'tests/device/native/PicoWorldCurrentDocumentBridge.h',ROOT/'interface/src/scripting/TestScriptingInterface.cpp',HERE/'world-current-document-getter.cpp',web/'src/NativeWebViewItem.cpp',HERE/'world-current-input-native.cpp',HERE/'pico-browser-originals.cpp',
            ROOT/'libraries/shared/src/EmbeddedWebPolicy.h',web/'src/PicoBrowserFeatureE2E.inc',
            web/'java/org/overte/web/EmbeddedWebView.java',web/'java/org/overte/web/WebAudioLifecycle.java']
        provenance=[dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sources]
        path=stage/'original-inputs.json';path.write_text(json.dumps(provenance));path.chmod(0o600)
        run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
            '-I'+str(stage),'-I'+str(ROOT),'-I'+str(web/'src'),'-I'+str(ROOT/'libraries/shared/src'),
            '-I'+str(ROOT/'libraries/ui/src'),'-I'+str(ROOT/'libraries/script-engine/src'),
            '-isystem',str(Path(env['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),
            '-I'+str(jdk/'include'),'-I'+str(jdk/'include/linux'),
            HERE/'world-current-input-native.cpp',web/'src/PicoWorldCurrentDocumentBridge.cpp',stage/'moc.cpp',stage/'embedded-web.cpp',stage/'feature-web.cpp',
            '-L'+str(prefix/'usr/lib64'),'-L'+str(jdk/'lib/server'),'-Wl,-rpath,'+str(jdk/'lib/server'),'-ljvm','-o',stage/'test',*flags])
        (stage/'original-current-input-getter.inc').write_text(original((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featurePicoWorldCurrentInput('))
        for pico in (False,True):
            binary=stage/('input-getter-pico' if pico else 'input-getter-non-pico')
            run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS',*(['-DANDROID_APP_PICO_INTERFACE'] if pico else []),
                '-I'+str(stage),'-I'+str(ROOT),HERE/'world-current-input-getter.cpp',web/'src/PicoWorldCurrentDocumentBridge.cpp',
                '-L'+str(prefix/'usr/lib64'),'-o',binary,*flags])
            run([binary,stage,'--testScript','host-boundary','--testResultsLocation',stage],build=False)
        result=run(['unshare','--user','--map-root-user','--net',stage/'test',stage,'--testScript','host-boundary','--testResultsLocation',stage,*(['--current-document-byte-cap'] if byte_only else [])],build=False)
        self.assertIn('PASS actual current-authority ray',result.stdout)
        proof=json.loads((stage/'retained-resume-originals.json').read_bytes())
        self.assertEqual('ready',proof['before']['status']);self.assertEqual('pending',proof['after']['status'])
        self.assertEqual({},proof['historicalCacheReply'])
        self.assertEqual(proof['before']['source']['documents'],proof['retainedFinishHistory'])
        self.assertEqual(1,proof['worldReads']);self.assertEqual(0,proof['geometryReads'])
        self.assertEqual(1,proof['finishedEventsDelivered']);self.assertEqual(0,proof['reloadsDelivered'])
        from adapters.pico4.world_current_input import validate
        for name in ('current-input-ray','current-input-focus'):
            entry=json.loads((stage/(name+'.json')).read_bytes());packet=entry['packet']
            validate(packet,entry['request'],packet['processId'],packet['capturedEpochMs'],entry['documentOriginal'])
        proof=json.loads((stage/'current-input-proof.json').read_bytes());self.assertEqual(2,proof['pointers']);self.assertEqual(2,proof['geometryQueries'])
        for case in ('foreign','grant','page','source','death','recreate','context','window','late','overlay'):
            folder=stage/case;folder.mkdir(mode=0o700);shutil.copytree(stage/'org',folder/'org')
            result=run(['unshare','--user','--map-root-user','--net',stage/'test',folder,'--testScript','host-boundary','--testResultsLocation',folder,
                '--current-input-case',case],build=False)
            self.assertIn('PASS original CurrentInput disjoint counter',result.stdout)
            entry=json.loads((folder/'current-input-counter.json').read_bytes());self.assertEqual(0,entry['pointers']);self.assertEqual(1,entry['geometryQueries'])
            self.assertEqual(1,entry['rawOriginals']);self.assertEqual('ready' if case=='foreign' else 'unavailable',entry['packet']['status'])
            validate(entry['packet'],entry['request'],entry['packet']['processId'],entry['packet']['capturedEpochMs'],entry['documentOriginal'])
            if case=='recreate':
                fresh=json.loads((folder/'current-input-recreated.json').read_bytes());self.assertEqual('ready',fresh['packet']['status'])
                validate(fresh['packet'],fresh['request'],fresh['packet']['processId'],fresh['packet']['capturedEpochMs'],fresh['documentOriginal'])
        for row in provenance:self.assertEqual(row['sha256'],hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
