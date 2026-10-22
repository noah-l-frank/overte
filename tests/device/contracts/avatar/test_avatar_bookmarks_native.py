"""Original Bookmark writer/cache, raw physical bytes and complete bounded getter."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from copy import deepcopy
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.avatar_bookmarks import validate,continuity


def function(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


class AvatarBookmarksNativeTests(unittest.TestCase):
    def test_original_store_physical_cache_queue_and_identity(self):
        native=(ROOT/'interface/src/Bookmarks.cpp').read_text();avatar=(ROOT/'interface/src/AvatarBookmarks.cpp').read_text()
        code='\n'.join(function(native,s) for s in ('void Bookmarks::insert(', 'void Bookmarks::remove(', 'bool Bookmarks::contains(', 'void Bookmarks::readFromFile(', 'void Bookmarks::persistToFile('))
        code+='\n'+'\n'.join(function(avatar,s) for s in ('AvatarBookmarks::AvatarBookmarks()', 'QVariantMap AvatarBookmarks::e2eBookmarkStorage(', 'void AvatarBookmarks::addBookmarkInternal(', 'void AvatarBookmarks::removeBookmarkInternal('))
        code+='\n'+function((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featurePicoAvatarBookmarks(')
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','5');extra=[]
        if major=='5':
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            extra=['-L'+str(prefix/'usr/lib64')];moc=prefix/'usr/lib64/qt5/bin/moc'
        else:moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],env=environment,text=True))
        with tempfile.TemporaryDirectory(prefix='pico-avatar-bookmarks-') as directory:
            stage=Path(directory);cpp=stage/'test.cpp';cpp.write_text(Path(__file__).with_name('avatar-bookmarks-native.cpp').read_text());binary=stage/'test'
            (stage/'actual-avatar-bookmarks.inc').write_text(code)
            subprocess.run([str(moc),str(cpp),'-o',str(stage/'test.moc')],check=True,timeout=20,env=environment)
            built=subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE','-I'+str(ROOT),str(cpp),'-o',str(binary),*extra,*flags],capture_output=True,text=True,timeout=60,env=environment)
            self.assertEqual(0,built.returncode,built.stderr[:6000])
            subprocess.run([str(binary)],check=True,timeout=10,env=environment)
            result=subprocess.run([str(binary),'--testScript'],capture_output=True,text=True,timeout=10,env=environment)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        rows=[json.loads(line) for line in result.stdout.splitlines()];self.assertEqual(['original','read-only','saved','deleted','after-dispatch-retired','after-worker-retired','replacement','absent'],[r['kind'] for r in rows])
        previous=None
        for row in rows:
            value=row['packet'];validate(value,row['request'],value['processId'],value['capturedEpochMs'])
            if row['kind']=='replacement':
                with self.assertRaises(RuntimeError):continuity(previous,value)
            else:continuity(previous,value)
            previous=value
        a,b=(rows[i]['packet']['source']['storage'] for i in (0,3));self.assertEqual(a['bookmarks'],b['bookmarks']);self.assertNotEqual(a['rawSha256'],b['rawSha256'])
        self.assertTrue(rows[2]['packet']['source']['storage']['bookmarks']['e2e-'+'d'*32]['avatarScale']==1)
        first=rows[0]
        for field,bad in (('capturedEpochMs',first['packet']['requestedEpochMs']-1),('rawSha256','0'*64),
                ('mapSha256','0'*64),('avatarBookmarkStorageVersion',True),('rawBase64','not base64')):
            changed=deepcopy(first['packet']);changed['source']['storage'][field]=bad
            with self.subTest(original_field=field),self.assertRaises(RuntimeError):
                validate(changed,first['request'],changed['processId'],changed['capturedEpochMs'])

if __name__=='__main__':unittest.main()
