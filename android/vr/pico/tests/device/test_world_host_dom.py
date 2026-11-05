"""Four finite World HOST DOM components, no Native/device/public qualification."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
CASE_NAMES=('self_tests.test_pico_world_host_dom.WorldHostDomTests.test_one_unicode_commit_full_original_trace_and_new_same_child_document', 'self_tests.test_pico_world_host_dom.WorldHostDomTests.test_beforeinput_cancel_never_promotes_transport_to_dom_effect', 'self_tests.test_pico_world_host_dom.WorldHostDomTests.test_actual_child_exit_keeps_first_tb_and_refuses_next_getter', 'self_tests.test_pico_world_host_dom.WorldHostDomTests.test_exact_string_identity_extent_eight_edges')
def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)
if __name__=='__main__':unittest.main()
