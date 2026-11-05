"""Cold retained HOST dataflow; Qt/JNI/Java/Chromium/device remain unqualified."""
from pathlib import Path
import tempfile,unittest
from self_tests import pico_world_host_dom_fixture as component
from self_tests.pico_world_live_strings_fixture import pure_live_strings

class WorldHostDomTests(unittest.TestCase):
    def run_component(self,name):
        path=Path(tempfile.mkdtemp(prefix='pico-world-host-dom-',dir='/tmp'))
        path.chmod(0o700)
        print('Retained World HOST DOM originals:',path,flush=True)
        proof=getattr(component,name)(path)
        self.assertEqual(name,proof['case'])
        self.assertTrue(all(proof['knownHostCloses']))
        return proof
    def test_one_unicode_commit_full_original_trace_and_new_same_child_document(self):
        proof=self.run_component('normal_cold_product_dom_current')
        self.assertEqual(18,proof['actualRawReceipts'])
        self.assertTrue(proof['hostModeledDocumentEffect'])
        self.assertFalse(proof['qtJniJavaQualified'])
    def test_beforeinput_cancel_never_promotes_transport_to_dom_effect(self):
        proof=self.run_component('dom_beforeinput_no_effect')
        self.assertTrue(proof['noFalseEffect'])
        self.assertFalse(proof['successQualified'])
    def test_actual_child_exit_keeps_first_tb_and_refuses_next_getter(self):
        proof=self.run_component('dom_source_child_exit')
        self.assertTrue(proof['firstOwnerTBHeldAfterTestRefsAndGC'])
        self.assertEqual(0,proof['newGetterOrRaw'])
    def test_exact_string_identity_extent_eight_edges(self):
        proof=pure_live_strings(None)
        self.assertEqual(8,proof['count'])
        self.assertLessEqual(proof['actualScratchBytes'],proof['existingWindow'])
