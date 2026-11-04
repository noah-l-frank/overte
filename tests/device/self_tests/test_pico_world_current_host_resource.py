"""Cold actual World Root resource components, not public World readiness."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile,unittest
from self_tests import pico_world_current_host_fixture as fixture

class WorldRootResourceTests(unittest.TestCase):
    def run_component(self,name):
        artifacts=Path(tempfile.mkdtemp(prefix='pico-world-root-host-'))
        artifacts.chmod(0o700)
        print('Retained World HOST originals:',artifacts,flush=True)
        proof=getattr(fixture,name)(artifacts)
        self.assertEqual(name,proof['case'])
        return proof
    def test_actual_cold_parent_census(self):
        proof=self.run_component('normal_cold_parent_census')
        self.assertTrue(proof['normalParentConstructor'])
        self.assertFalse(proof['parentPrepared'])
    def test_actual_owned_root_inode_change_holds_first_error_and_both_originals(self):
        proof=self.run_component('actual_root_inode_replacement')
        self.assertTrue(proof['custody']['afterTestExceptionRefsDroppedAndGC'])
    def test_bool_credit_data_refuses_without_next_read(self):
        proof=self.run_component('credit_data_refusal')
        self.assertEqual(0,proof['actualNewFiles'])
    def test_absent_current_stage_refuses_real_factory(self):
        proof=self.run_component('absent_current_stage')
        self.assertEqual(0,proof['currentFactoryCalls'])
    def test_one_original_document_read_uses_same_root_two_raw_receipts(self):
        proof=self.run_component('normal_cold_document')
        self.assertEqual(2,proof['actualModelProtocolReceipts'])
        self.assertEqual(0,proof['actualSDKCalls'])
        self.assertFalse(proof['normalFocusImeEffectQualified'])
