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
        commands=[['/usr/lib/jvm/temurin-21-jdk/bin/javac','-cp',str(android),'-d',str(stage),str(java),str(document)],
                  ['/usr/lib/jvm/temurin-21-jdk/bin/java','-ea','-cp',str(stage)+os.pathsep+str(android),'org.overte.web.EmbeddedWebView']]
        for ordinal,command in enumerate(commands):
            result=subprocess.run(command,capture_output=True,text=True,timeout=45)
            log=stage/(str(ordinal)+'.json');log.write_text(json.dumps(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)));log.chmod(0o600)
            self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertIn('PASS unchanged Java current-document bodies',result.stdout)
        for path,digest in manifest.items():self.assertEqual(digest,hashlib.sha256((ROOT/path).read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
