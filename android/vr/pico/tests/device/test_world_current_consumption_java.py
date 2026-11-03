"""Original Java edit/queue/input/trace bodies; Android/JNI are explicit seams."""
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


class WorldCurrentConsumptionJavaTests(unittest.TestCase):
    def test_original_edit_dispatch_and_trace_do_not_bypass_input_or_invent_dom_effect(self):
        source = ROOT/'android/common/web/java/org/overte/web/EmbeddedWebView.java'
        body = source.read_text()
        signatures = (
            'public static void featurePicoCurrentDocumentRead(',
            'private static boolean featurePicoCurrentOwner(',
            'private static JSONObject featurePicoCurrentSnapshot(',
            'private static void featurePicoCurrentReply(',
            'public static void featurePicoCurrentInputRead(',
            'private static void featurePicoCurrentInputReply(',
            'private static void post(long handle, Command command) {',
            'private static void post(long handle, Command command, boolean suspendedAllowed)',
            'private static void input(long handle, Command command) {',
            'private static void input(long handle, Command command, boolean suspendedAllowed)',
            'public static void edit(',
            'private static String featurePicoConsumptionId(',
            'private static String featurePicoConsumptionUtf16(',
            'private static String featurePicoConsumptionUtf8(',
            'private static JSONObject featurePicoConsumptionCommand(',
            'private static void featurePicoConsumptionEmit(',
            'private static void featurePicoConsumptionEntry(',
            'private static JSONObject featurePicoConsumptionSnapshot(',
            'private static void featurePicoConsumptionConsumed(')
        methods = '\n'.join(original(body, signature) for signature in signatures)
        template = (HERE/'world-current-input-java-body.java.inc').read_text()
        # Declared Android Handler/Instance dependencies only. Production queue,
        # WebInputGate and document admission bodies run unchanged.
        template = template.replace('void post(Runnable job){pending.add(job);}',
            'boolean post(Runnable job){pending.add(job);return true;}')
        template = template.replace('final long handle=1,creationRevision=3;',
            'boolean visible=true;int failures;void fail(int code){failures++;}\n        final long handle=1,creationRevision=3;')
        template = template.replace('VIEWS.put(1L,value);return value;',
            'VIEWS.put(1L,value);INPUT.update(owner,true);trace.clear();idFault=emitFault=false;return value;')
        template = template[:template.index('    public static void main(')]
        seam = (HERE/'world-current-consumption-java-body.java.inc').read_text()
        template = template.replace('// ORIGINAL_METHODS', methods+'\n'+seam)
        directory = tempfile.TemporaryDirectory(prefix='world-current-consumption-java-')
        directory._finalizer.detach()
        stage = Path(directory.name); stage.chmod(0o700)
        print('Retained original Java Consumption stage:', stage, flush=True)
        java = stage/'org/overte/web/EmbeddedWebView.java'; java.parent.mkdir(parents=True)
        java.write_text(template+'}\n'); java.chmod(0o600)
        android = Path.home()/'.gradle/caches/modules-2/files-2.1/org.robolectric/android-all/15-robolectric-13954326/78f2fb1d753164d153cf9e5bb60003fa8d57b0a1/android-all-15-robolectric-13954326.jar'
        self.assertTrue(android.is_file())
        document = source.with_name('WebDocumentState.java')
        gate = source.with_name('WebInputGate.java')
        paths = (source, document, gate, HERE/'world-current-input-java-body.java.inc',
            HERE/'world-current-consumption-java-body.java.inc', Path(__file__))
        manifest = {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        (stage/'original-inputs.json').write_text(json.dumps(manifest))
        commands = [
            ['/usr/lib/jvm/temurin-21-jdk/bin/javac','-cp',str(android),'-d',str(stage),str(java),str(document),str(gate)],
            ['/usr/lib/jvm/temurin-21-jdk/bin/java','-ea','-cp',str(stage)+os.pathsep+str(android),'org.overte.web.EmbeddedWebView',str(stage)]]
        for ordinal, command in enumerate(commands):
            result = subprocess.run(command, capture_output=True, text=True, timeout=45)
            log = stage/(str(ordinal)+'.json')
            log.write_text(json.dumps(dict(command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)))
            log.chmod(0o600)
            self.assertEqual(0, result.returncode, result.stdout+result.stderr)
            if ordinal: self.assertIn('PASS actual Java edit/queue/input and consumption', result.stdout)
        receipts = json.loads((stage/'consumption-java-originals.json').read_bytes())
        self.assertEqual(['java-entry','java-consume'], [row['kind'] for row in receipts])
        for row in receipts:
            raw = json.loads(row['raw'])
            self.assertEqual(bytes.fromhex(raw['commandUtf16Hex']).decode('utf-16-be').encode().hex(),raw['commandUtf8Hex'])
        for path, digest in manifest.items(): self.assertEqual(digest,hashlib.sha256((ROOT/path).read_bytes()).hexdigest())


if __name__ == '__main__': unittest.main()
