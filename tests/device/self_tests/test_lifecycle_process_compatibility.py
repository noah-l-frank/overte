"""Actual versioned producer, cold bytes and original domain protocol rules."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_process as process
from adapters.pico4.lifecycle_world_codec import unpack
from adapters.script_journey.history import pack
from self_tests import test_pico_lifecycle_process as fixture


class LifecycleProcessCompatibilityTests(unittest.TestCase):
    def model(self,version):
        with patch.object(process,'VERSION',version):
            model=fixture.LifecycleProcessTests();model.setUp()
        self.addCleanup(model.doCleanups);return model

    def test_actual_v1_cold_bytes_and_further_operations_keep_original_codec(self):
        model=self.model(1);owner=model.process;raw=owner.store.path.read_bytes();disk=deepcopy(owner.disk)
        cold=process.PicoLifecycleProcessRetirement(owner.store.path,owner.run,owner.profile,owner.guard,owner.lock,
            monotonic=owner.monotonic,sleep=owner.sleep)
        self.assertEqual(raw,cold.store.path.read_bytes());self.assertEqual(disk,cold.disk)
        model.process=cold;model.shutdown();self.assertEqual(1,cold.disk['lifecycleProcessOwnerVersion'])
        self.assertEqual('zlib-base64-json',cold.disk['payload']['encoding'])
        self.assertNotIn('frames',cold.state['shutdown']);self.assertNotIn('pending',cold.state['shutdown'])

    def test_actual_v2_payload_and_legacy_writer_preserve_complete_canonical_state(self):
        model=self.model(2);state=model.process.state
        legacy=process.process_payload(state,1);new=process.process_payload(state,2)
        self.assertEqual(pack([state]),legacy)
        self.assertEqual([state],unpack(new,2));self.assertEqual([state],unpack(legacy,1))
        for payload,wrong in ((new,1),(legacy,2)):
            with self.assertRaises(NativeUIError):unpack(payload,wrong)
        for version in (True,False,0,3,2.0):
            with self.subTest(version=version),self.assertRaises(NativeUIError):process.process_payload(state,version)

    def test_independently_acquired_domain2_and3_connected_or_disconnected_keep_v1_strict(self):
        model=self.model(2)
        for version in (2,3):
            for connected in (True,False):
                boundary,reader=model.domains(model.native,123,'9'*32,'1'*32,'2'*32,19000)
                original=boundary.mutate
                def mutate(value):
                    original(value);value['chatVersion']=version
                    if version==3:value['source'].update(openedCommandId='',retiredCommandId='')
                    if not connected:value['source']['session'].update(connected=False,connectionBirth='',connectedEpochMs=0,mixerActive=False)
                boundary.mutate=mutate;packet=reader.read(owner_run:=model.process.run)
                self.assertIs(packet,process.domain(packet,owner_run,123,version=2))
                if version==2 and connected:self.assertIs(packet,process.domain(packet,owner_run,123,version=1))
                else:
                    with self.assertRaises(NativeUIError):process.domain(packet,owner_run,123,version=1)


if __name__=='__main__':unittest.main()
