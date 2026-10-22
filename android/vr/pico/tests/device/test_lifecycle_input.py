"""Actual Pico wrapper plus explicit native/OpenXR boundaries; no device runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import test_normal_scripts as sources
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.pico4.lifecycle_source import COMMAND,FILE
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_pico_lifecycle_source import Boundary,RUN,LifecycleSourceTests
from self_tests.test_pico_lifecycle_back import LifecycleBackTests
from self_tests.test_pico_lifecycle_x_mapping import PicoLifecycleXMappingTests
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class PicoLifecycleBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native
        self.boundary=Boundary();original_write=self.native.write_debug_app_file;original_read=self.native.read_debug_app_file
        def write(target,package,path,raw):
            if path!=COMMAND:return original_write(target,package,path,raw)
            self.assertEqual('org.overte.pico',package);self.boundary.send(json.loads(raw))
            self.boundary.value['processId']=int(self.native.identity.split(':')[0])
            self.boundary.value['capturedEpochMs']=self.native.epoch_milliseconds(target)
        def read(target,package,path,**options):
            if path!='files/overte-e2e/'+FILE:return original_read(target,package,path,**options)
            self.assertEqual({'attempts':1},options);return self.boundary.read()
        for binding in (patch.object(self.native,'write_debug_app_file',side_effect=write),
                patch.object(self.native,'read_debug_app_file',side_effect=read)):
            binding.start();self.addCleanup(binding.stop)
    def test_actual_wrapper_reads_original_lifecycle_source_and_rechecks_installed_candidate(self):
        source=self.adapter._lifecycle_ui_source(self.native.target);value=source.capture(RUN)
        self.assertEqual('create',value['source']['editors'][0]['kind']);self.assertEqual(1,len(self.boundary.commands))
        self.native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):source.capture(RUN)
        self.assertEqual(1,len(self.boundary.commands));self.assertEqual([],self.native.inputs)
    def test_base_cleanup_keeps_unresolved_lifecycle_ownership_after_actual_teardown(self):
        store=self.adapter._lifecycle_back_store(self.native.target)
        original=dict(explicitSyntheticBoundary='unresolved lifecycle proof')
        store.write(original,None)
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.cleanup(self.native.target)
        self.assertEqual(original,store.read())
        self.assertIn(('am','force-stop','org.overte.pico'),self.native.events)

    def test_actual_back_factory_shares_original_process_session_and_private_candidate_binding(self):
        directory=self.fixture.fixture.state_root
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-synthetic-target',directory)
        session.begin(self.native.identity)
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            owner=self.adapter._lifecycle_back(self.native.target,RUN)
            self.assertIsInstance(owner,PicoLifecycleBack);self.assertIs(owner.session,session)
            self.assertEqual(self.native.identity,owner.binding['processIdentity'])
            self.assertEqual(directory,owner.store.path.parent);self.assertIsNone(owner.state)
            self.assertFalse(any(cap.startswith('feature.lifecycle-input.') for cap in self.adapter.capabilities(self.native.target)))
        self.assertEqual([],self.native.inputs)


if __name__=='__main__':unittest.main()
