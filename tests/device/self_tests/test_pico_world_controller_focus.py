# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Finite controller-to-IME HOST join; no physical controller/Qt/device claim."""
from pathlib import Path
import tempfile,unittest
from self_tests import pico_world_controller_focus_fixture as component
from self_tests.pico_world_document_format_fixture import pure_actual_document_format_bounds

class WorldControllerHostTests(unittest.TestCase):
    def run_component(self,name):
        path=Path(tempfile.mkdtemp(prefix='pico-world-ime-',dir='/tmp'));path.chmod(0o700)
        print('Retained World controller HOST originals:',path,flush=True)
        proof=getattr(component,name)(path)
        self.assertEqual(name,proof['case']);self.assertTrue(all(proof['knownHostCloses']))
        self.assertFalse(proof['nativeQtDeviceQualified']);self.assertFalse(proof['wholeClaim'])
        return proof
    def test_controller_envelope_fresh_focus_once_ime_trace_and_new_document(self):
        proof=self.run_component('normal_controller_focus_ime_new_document')
        self.assertEqual(1,proof['actualSessionPrimaryEnvelopes']);self.assertEqual(22,proof['rawReceipts'])
        self.assertTrue(proof['issuedUnicodeOnce']);self.assertTrue(proof['freshIndependentFocus'])
        self.assertLessEqual(proof['globalBill']['decodedBytes'],16777216)
    def test_no_focus_effect_refuses_actual_ime_factory_and_replay(self):
        proof=self.run_component('controller_no_effect')
        self.assertEqual(0,proof['newImeInputs']);self.assertTrue(proof['actualImeFactoryRefusedBeforeAllocations'])
        self.assertTrue(proof['firstGateTBRetained']);self.assertTrue(proof['noInputReplay'])
    def test_original_foreign_scene_guard_refuses_before_controller_envelope(self):
        proof=self.run_component('controller_foreign_scene')
        self.assertEqual(0,proof['actualSessionPrimaryEnvelopes']);self.assertEqual(4,proof['rawReceipts'])
        self.assertEqual(0,proof['newImeInputs']);self.assertTrue(proof['noInputReplay'])
    def test_actual_nested_producer_format_bounds_twenty_four_domains(self):
        proof=pure_actual_document_format_bounds()
        self.assertEqual(24,proof['cases']);self.assertTrue(proof['actualProducerFormatter'])
        self.assertTrue(proof['old16CoefficientUnderstates']);self.assertEqual(20,proof['correctedCoefficient'])
        self.assertEqual(0,proof['owners']);self.assertEqual(0,proof['sourceSDK'])
