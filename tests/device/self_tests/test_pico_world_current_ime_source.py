"""Static source contracts only; no Qt/Native/C++/compiler execution."""
from pathlib import Path
import hashlib,json,unittest,subprocess
REPO=Path(__file__).resolve().parents[3]
def text(rel):return (REPO/rel).read_text()
def function(source,name):
    start=source.index(name);at=source.index('{',start);depth=0
    for end in range(at,len(source)):
        if source[end]=='{':depth+=1
        elif source[end]=='}':
            depth-=1
            if depth==0:return source[start:end+1]
    raise AssertionError(name)
EXPECTED_BODIES={'android/common/web/src/NativeWebViewItem.cpp\x00void NativeWebViewItem::inputMethodEvent(': '7768078ee266eb2592f9a1a19e0608cfced67e7a55b9e5bfaa05c46c71368b84', 'android/common/web/src/NativeWebViewItem.cpp\x00void NativeWebViewItem::editorCommand(': '4e2e813441c844e0ecaae721c0918ebcbfc05972a1c4a74cdaf9fce0a855eebe', 'android/common/web/src/NativeWebViewItem.cpp\x00void NativeWebViewItem::keyPressEvent(': 'c3bd91ef93a68917c2fe990328ea4e1cf9742208b007f6e69dd35c621a2c714e', 'interface/src/scripting/TestScriptingInterface.cpp\x00QVariantMap TestScriptingInterface::featurePicoWorldCurrentInput(': 'f133d51bc88702a1b64c213b88538ab7ddc70cec7df09a715660ca43443df873', 'interface/src/scripting/TestScriptingInterface.cpp\x00QVariantMap TestScriptingInterface::featurePicoWorldCurrentDocument(': '570312ff253f5181fd259d51cb66cbe0e7ddd243926a0525497165d3781c7af9', 'android/common/web/src/PicoWorldCurrentDocumentBridge.cpp\x00PicoCurrentAnchor picoCurrentInputAnchor(': '03c96411761d8b3bcee66583eb6601ec5a981dee9d85002363169d51280eb7d4', 'android/common/web/src/PicoWorldCurrentDocumentBridge.cpp\x00PicoCurrentAnchor picoCurrentAnchor(': 'fd03c205912855eeef7c2b6c1c25c0b2fd9c9fcf7857e4df61e82d749cf8c052'}
EXPECTED_READONLY_PROBE='196b7d30e7bb36929436f6913250607428422a97e0b9a5b5ef3e4d3238dff5b2'

class SourceJoins(unittest.TestCase):
    def test_product_editor_and_readonly_source_bodies_are_exact_originals(self):
        for key,sha in EXPECTED_BODIES.items():
            rel,name=key.split('\0')
            self.assertEqual(sha,hashlib.sha256(function(text(rel),name).encode()).hexdigest())
    def test_exact_string_and_numeric_admission_precedes_qjson_and_nonce(self):
        h=text('tests/device/native/PicoWorldCurrentImeBridge.h')
        self.assertLess(h.index('userType()!=QMetaType::QString'),h.index('QJsonObject::fromVariantMap'))
        self.assertLess(h.index('schemaType!='),h.index('QJsonObject::fromVariantMap'))
        self.assertIn('text.size()>512',h);self.assertIn('c.isLowSurrogate()',h);self.assertIn('toDouble()!=1',h)
        anchor=function(text('android/common/web/src/PicoWorldCurrentDocumentBridge.cpp'),'PicoCurrentAnchor picoCurrentImeAnchor(')
        self.assertLess(anchor.index('picoWorldCurrentImeCommand(command)'),anchor.index('records.insert'))
    def test_once_outcome_and_focus_ownership_precede_existing_provider(self):
        s=text('android/common/web/src/PicoWorldCurrentImeE2E.inc')
        self.assertLess(s.index('scope->attempts.contains(id)'),s.index('std::make_shared<PicoCurrentImeAttempt>'))
        self.assertLess(s.index('scope->attempts.insert(id,a)'),s.index('const auto focus=picoCurrentInputLookup'))
        self.assertLess(s.index('scope->focusOwners.insert(focusId,id)'),s.index('a->issued=true'))
        self.assertLess(s.index('a->issued=true'),s.index('accepted=provider('))
        self.assertIn('std::current_exception()',s)
    def test_current_doc_weak_lifetime_image_and_original_age_are_rechecked(self):
        s=text('android/common/web/src/PicoWorldCurrentImeE2E.inc')
        for item in ('focus->clock->fresh()','focus->document->clock->fresh()','picoCurrentInputDocument(focus)',
            'activeFocusItem()!=item','editor!=expectedEditor','now-epoch>1500','!imageCurrent()','a->after.value("finish")!=a->before.value("finish")'):
            self.assertIn(item,s)
        for wrong in ('forceActiveFocus','requestFocus','evaluateJavascript','setText','setPlainText'):
            self.assertNotIn(wrong,s)
    def test_distinct_tsi_queue_and_provider_use_prequeue_original_anchor(self):
        s=function(text('interface/src/scripting/TestScriptingInterface.cpp'),'QVariantMap TestScriptingInterface::featurePicoWorldCurrentIme(')
        self.assertLess(s.index('picoCurrentImeAnchor(command)'),s.index('queue->read'))
        for guard in ('previewDirectory','_featureLifecycle','--testScript','queue->settled','PicoCurrentImeProvider','anchor->fresh()'):
            self.assertIn(guard,s)
        bridge=text('android/common/web/src/NativeWebViewItem.cpp');self.assertIn('picoCurrentImeProperty()',bridge)
        self.assertIn('#include "PicoWorldCurrentImeE2E.inc"',bridge)
    def test_original_readonly_probe_branch_is_unchanged(self):
        new=text('tests/device/probe/overte_e2e_probe.js')
        begin='        if (command && command.action === "pico-world-web"\n                && (command.operation === "measure-current-ray"'
        end='        if (command && command.action === "pico-world-web" && command.operation === "observe-current-document")'
        self.assertEqual(EXPECTED_READONLY_PROBE,hashlib.sha256(new[new.index(begin):new.index(end,new.index(begin))].encode()).hexdigest())

class ProbeContract(unittest.TestCase):
    def test_actual_probe_five_boundaries(self):
        run=subprocess.run(['node',str(REPO/'android/vr/pico/tests/device/world-current-ime-probe-test.js')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,check=False)
        self.assertEqual(0,run.returncode,run.stderr.decode(errors='replace'))
        proof=json.loads(run.stdout)
        self.assertTrue(proof['green']);self.assertEqual(5,proof['cases'])
        self.assertTrue(proof['actualProbeBranch']);self.assertEqual(0,proof['nativeQtCalls'])
        print('World IME actual Probe boundary:',run.stdout.decode().strip())

