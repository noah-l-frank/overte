"""Execute unchanged production Java reader bodies with explicit Android seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_create_polyvox_controls_native import original

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]


class WorldCurrentDocumentJavaTests(unittest.TestCase):
    def test_original_read_owner_two_bookends_and_document_state(self):
        source=ROOT/'android/common/web/java/org/overte/web/EmbeddedWebView.java'
        text=source.read_text()
        methods='\n'.join(original(text,signature) for signature in (
            'public static void featurePicoCurrentDocumentRead(',
            'private static boolean featurePicoCurrentOwner(',
            'private static JSONObject featurePicoCurrentSnapshot(',
            'private static void featurePicoCurrentReply('))
        directory=tempfile.TemporaryDirectory(prefix='world-current-document-java-');directory._finalizer.detach()
        stage=Path(directory.name);stage.chmod(0o700);print('Original Java body stage:',stage,flush=True)
        java=stage/'org/overte/web/EmbeddedWebView.java';java.parent.mkdir(parents=True)
        java.write_text((HERE/'world-current-document-java-body.java.inc').read_text().replace('// ORIGINAL_METHODS',methods));java.chmod(0o600)
        android=Path.home()/'.gradle/caches/modules-2/files-2.1/org.robolectric/android-all/15-robolectric-13954326/78f2fb1d753164d153cf9e5bb60003fa8d57b0a1/android-all-15-robolectric-13954326.jar'
        self.assertTrue(android.is_file())
        document=ROOT/'android/common/web/java/org/overte/web/WebDocumentState.java'
        manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,document,HERE/'world-current-document-java-body.java.inc')}
        (stage/'original-inputs.json').write_text(json.dumps(manifest));(stage/'original-inputs.json').chmod(0o600)
        byte_only=os.environ.get('OVERTE_CURRENT_DOCUMENT_UTF8_ONLY')=='1'
        from test_world_current_document_reader import fixture
        from adapters.native_web_dom import dom
        request,packet=fixture();value=packet['source']['dom'];value['editor']['text']='中'*512
        value['echoes']=[dict(sequence=i,surface='world',message=json.dumps(dict(contract='overte-web-parity-v1',action='echo',sequence=i,surface='world'),separators=(',',':')),
            receivedEpochMs=10000,observedEpochMs=10001) for i in range(1,28)]
        dom(value,dict(request,surface='world'),10004)
        raw=json.dumps(json.dumps(value,ensure_ascii=False,separators=(',',':')),ensure_ascii=False,separators=(',',':'))
        self.assertGreater(len(raw.encode()),8192);self.assertLessEqual(len(raw),8192)
        (stage/'quoted-dom.json').write_text(raw);(stage/'quoted-dom.json').chmod(0o600)
        commands=[['/usr/lib/jvm/temurin-21-jdk/bin/javac','-cp',str(android),'-d',str(stage),str(java),str(document)],
                  ['/usr/lib/jvm/temurin-21-jdk/bin/java','-ea','-cp',str(stage)+os.pathsep+str(android),'org.overte.web.EmbeddedWebView','--utf8-only',str(stage/'quoted-dom.json')]]
        if not byte_only:
            commands.insert(1,['/usr/lib/jvm/temurin-21-jdk/bin/java','-ea','-cp',str(stage)+os.pathsep+str(android),'org.overte.web.EmbeddedWebView'])
        for ordinal,command in enumerate(commands):
            result=subprocess.run(command,capture_output=True,text=True,timeout=45)
            log=stage/(str(ordinal)+'.json');log.write_text(json.dumps(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)));log.chmod(0o600)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
            if ordinal:
                self.assertIn('PASS original Java current-document UTF8 cap' if '--utf8-only' in command else 'PASS unchanged Java current-document bodies',result.stdout)
        for path,digest in manifest.items():self.assertEqual(digest,hashlib.sha256((ROOT/path).read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
