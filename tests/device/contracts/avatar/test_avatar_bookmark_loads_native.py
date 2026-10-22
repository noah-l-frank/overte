"""Complete original Bookmark/MyAvatar calls and real Qt contextless functor."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.avatar_bookmark_loads import validate,continuity


def function(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


class AvatarBookmarkLoadsNativeTests(unittest.TestCase):
    def test_original_cached_url_functor_pending_capture_and_observer_queue(self):
        avatar=(ROOT/'interface/src/AvatarBookmarks.cpp').read_text()
        code='\n'.join(function(avatar,s) for s in ('QVariantMap AvatarBookmarks::e2eBookmarkLoads(', 'void AvatarBookmarks::loadBookmark(', 'void AvatarBookmarks::loadBookmarkInternal('))
        code+='\n'+function((ROOT/'interface/src/avatar/MyAvatar.cpp').read_text(),'void MyAvatar::useFullAvatarURL(')
        code+='\n'+function((ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text(),'QVariantMap TestScriptingInterface::featurePicoAvatarBookmarkLoads(')
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','5');extra=[]
        if major=='5':
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            extra=['-L'+str(prefix/'usr/lib64')];moc=prefix/'usr/lib64/qt5/bin/moc'
        else:moc=Path(subprocess.check_output(['pkg-config','--variable=libexecdir','Qt6Core'],text=True).strip())/'moc'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],env=environment,text=True))
        with tempfile.TemporaryDirectory(prefix='pico-avatar-bookmark-loads-') as directory:
            stage=Path(directory);stage.chmod(0o700);cpp=stage/'test.cpp';cpp.write_text(Path(__file__).with_name('avatar-bookmark-loads-native.cpp').read_text());binary=stage/'test'
            (stage/'actual-avatar-bookmark-loads.inc').write_text(code)
            subprocess.run([str(moc),str(cpp),'-o',str(stage/'test.moc')],check=True,timeout=20,env=environment)
            built=subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-UNDEBUG','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE','-I'+str(ROOT),str(cpp),'-o',str(binary),*extra,*flags],capture_output=True,text=True,timeout=60,env=environment)
            self.assertEqual(0,built.returncode,built.stderr[:10000])
            subprocess.run([str(binary)],check=True,timeout=10,env=environment)
            result=subprocess.run([str(binary),'--testScript'],capture_output=True,text=True,timeout=10,env=environment)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        rows=[json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(['baseline','cached-same-url','pending-original-load','original-load-callback','original-sender-dead','observer-dispatch-retired','observer-worker-retired','replacement'],[row['kind'] for row in rows])
        previous=None
        for row in rows:
            value=row['packet'];validate(value,row['request'],value['processId'],value['capturedEpochMs'])
            if row['kind']=='replacement':
                with self.assertRaises(RuntimeError):continuity(previous,value)
            else:continuity(previous,value)
            previous=value
        sample=rows[1]
        for field,bad in (('action','foreign-observe'),('schemaVersion',True),('commandId','bad')):
            request=deepcopy(sample['request']);request[field]=bad
            with self.subTest(original_request=field),self.assertRaises(RuntimeError):validate(sample['packet'],request,sample['packet']['processId'],sample['packet']['capturedEpochMs'])
        for field,bad in (('captureAlive',1),('dispatches',True),('active',2),('createdEpochMs',0),('returnedEpochMs',0),('id','0'),('avatarInstance','bad'),('sessionId','00000000-0000-0000-0000-000000000000'),('completed',False)):
            changed=deepcopy(sample['packet']);actual=changed['source']['loads']['rows'][0];actual[field]=bad
            if field=='completed':
                changed['sequence']+=1;changed['requestId']='f'*32
                with self.assertRaises(RuntimeError):continuity(sample['packet'],changed)
            else:
                with self.assertRaises(RuntimeError):validate(changed,sample['request'],changed['processId'],changed['capturedEpochMs'])

if __name__=='__main__':unittest.main()
