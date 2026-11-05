"""Cold selection and before-constructor rejection; no cleanup success claim."""
import unittest,time
from copy import deepcopy
from self_tests.pico_audio_source_batch_fixture import AuthBundleFixture
from self_tests.pico_audio_authenticated_recipe_fixture import TARGET
from adapters.pico4.audio_cleanup_profile import AudioCleanupBudget1,PROSPECTIVE_BYTES
from adapters.pico4.audio_cleanup_io import PicoAudioCleanupIO1
from adapters.pico4.audio_cleanup_owner import PicoAudioCleanupOwner1
class WorkspaceTests(unittest.TestCase):
 def fixture(self):
  f=AuthBundleFixture();self.addCleanup(f.doCleanups);f.setUp();self.pc=f.fixture;return self.pc
 def test_cold3_refuses_both_cleanup_constructors_before_any_owner_file_or_sdk(self):
  pc=self.fixture();budget=pc.budget;self.assertEqual(0,budget.prospective)
  before=sorted(str(p) for p in pc.f.path.rglob('*'))
  with self.assertRaises(Exception):PicoAudioCleanupIO1(object(),TARGET,budget)
  with self.assertRaises(Exception):PicoAudioCleanupOwner1(pc.owner,budget,pc.f.source,action_started=time.monotonic())
  self.assertFalse(hasattr(budget,'restart_io'));self.assertFalse(hasattr(budget,'cleanup_owner'))
  self.assertEqual(before,sorted(str(p) for p in pc.f.path.rglob('*')));self.assertFalse(budget.failed)
 def test_cold3_cannot_book_early_and_default2_still_charges_full_original_domain(self):
  pc=self.fixture();budget=pc.budget;reads=pc.actor.raws.state['reads']
  with self.assertRaises(Exception):budget.begin_cleanup()
  self.assertEqual(reads,pc.actor.raws.state['reads']);self.assertEqual((False,None),budget.workspace)
  value=deepcopy(budget.value);value.pop('cleanupWorkspacePolicy');value['picoAudioCleanupProfileVersion']=2
  original=AudioCleanupBudget1(value,budget.lock);self.assertEqual(PROSPECTIVE_BYTES,original.prospective)
  original.require_cleanup_workspace();self.assertEqual((True,None),original.workspace)
