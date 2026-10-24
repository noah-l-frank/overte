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
import subprocess
import sys
import tempfile
import time
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device'),str(HERE)]
import test_pico_browser_originals as assembly
from test_create_polyvox_controls_native import pointer_source,original


class WorldWebResumeNativeTests(unittest.TestCase):
    def test_original_retained_page_foreground_rotates_grant_without_new_finish_or_query(self):
        directory=tempfile.TemporaryDirectory(prefix='world-web-retained-resume-');directory._finalizer.detach()
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
        java=stage/'org/overte/web/EmbeddedWebView.java';java.parent.mkdir(parents=True)
        java.write_text(assembly.JAVA.rsplit('}',1)[0]+''' public static int worldReads;public static String worldQueries="",runtimeQueries="";
 public static void featureRead(long h,long g,long p,String id){worldReads++;worldQueries+=h+","+g+","+p+","+id+";";}
 public static void featureRuntimeSnapshot(String id,String root,String known){runtimeQueries+=id+";"+root+";"+known;}
}
''')
        run([jdk/'bin/javac','-d',stage,java])
        run([tools/'moc','-DOVERTE_E2E_FEATURE_TESTS',web/'src/NativeWebViewItem.h','-o',stage/'moc.cpp'])
        for name in ('embedded-web','feature-web'):
            run([tools/'rcc','-name',name.replace('-','_'),web/(name+'.qrc'),'-o',stage/(name+'.cpp')])
        sources=[web/'src/NativeWebViewItem.cpp',HERE/'world-web-retained-resume-native.cpp',HERE/'pico-browser-originals.cpp',
            ROOT/'libraries/shared/src/EmbeddedWebPolicy.h',web/'src/PicoBrowserFeatureE2E.inc',
            web/'java/org/overte/web/EmbeddedWebView.java',web/'java/org/overte/web/WebAudioLifecycle.java']
        provenance=[dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sources]
        path=stage/'original-inputs.json';path.write_text(json.dumps(provenance));path.chmod(0o600)
        run(['c++','-std=c++17','-fPIC','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
            '-I'+str(stage),'-I'+str(ROOT),'-I'+str(web/'src'),'-I'+str(ROOT/'libraries/shared/src'),
            '-I'+str(ROOT/'libraries/ui/src'),'-I'+str(ROOT/'libraries/script-engine/src'),
            '-isystem',str(Path(env['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),
            '-I'+str(jdk/'include'),'-I'+str(jdk/'include/linux'),
            HERE/'world-web-retained-resume-native.cpp',stage/'moc.cpp',stage/'embedded-web.cpp',stage/'feature-web.cpp',
            '-L'+str(prefix/'usr/lib64'),'-L'+str(jdk/'lib/server'),'-Wl,-rpath,'+str(jdk/'lib/server'),'-ljvm','-o',stage/'test',*flags])
        result=run(['unshare','--user','--map-root-user','--net',stage/'test',stage,'--testScript','host-boundary','--testResultsLocation',stage],build=False)
        self.assertIn('PASS actual original World foreground grant rotation',result.stdout)
        proof=json.loads((stage/'retained-resume-originals.json').read_bytes())
        self.assertEqual('ready',proof['before']['status']);self.assertEqual('pending',proof['after']['status'])
        self.assertEqual({},proof['historicalCacheReply'])
        self.assertEqual(proof['before']['source']['documents'],proof['retainedFinishHistory'])
        self.assertEqual(1,proof['worldReads']);self.assertEqual(0,proof['geometryReads'])
        self.assertEqual(1,proof['finishedEventsDelivered']);self.assertEqual(0,proof['reloadsDelivered'])
        for row in provenance:self.assertEqual(row['sha256'],hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
