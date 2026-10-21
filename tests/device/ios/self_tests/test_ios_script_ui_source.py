"""Original iOS HTTP/AFC Script UI acquisition; native SDK execution is synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from adapters.script_feature.ui_source import validate
from adapters.script_ui_inventory import ui_state
from ios.adapters.script_ui_source import IOSScriptUISource
from ios.adapters import normal_input
from ios.self_tests.test_ios_normal_input import Boundary as InputBoundary
from self_tests.test_script_ui_inventory import inventory, picker
from self_tests.test_script_manager_status import observed as manager


class Boundary(InputBoundary):
    def __init__(self):
        super().__init__();self.source_sequence=0;self.epoch=20000;self.edit=None
        self.inventory=inventory(tabletShown=False)
    def observed(self):
        self.source_sequence+=1
        value=super().observed()
        value.update(sampleEpochMs=self.epoch,controls=[],fileControlsVersion=1,
            scriptObservationVersion=1,scriptSourceSequence=self.source_sequence,
            scriptInventory=deepcopy(self.inventory))
        if self.edit:self.edit(value)
        return value
    def source(self):
        native=self.input()
        source=IOSScriptUISource(native,lambda:20000,lambda:native._check(),42,
                                 monotonic=lambda:self.clock)
        return native,source


class IOSScriptUISourceTests(unittest.TestCase):
    def test_keeps_native_time_original_nonce_and_full_original_packet_under_host_clock_skew(self):
        boundary=Boundary()
        with patch.object(normal_input,'urlopen',boundary.post):
            native,reader=boundary.source();value=reader.capture()
        self.assertEqual(20000,value['capturedEpochMs'])
        self.assertEqual(boundary.receipt,value['originalReceipt'])
        self.assertEqual(boundary.requests[0]['commandId'],value['commandId'])
        self.assertEqual(boundary.instance,value['instance']);self.assertEqual(boundary.instance,value['generation'])
        self.assertEqual(1,value['sourceSequence']);self.assertEqual([],value['controls'])
        value['originalReceipt']['observation']['scriptInventory']['tabletShown']=True
        self.assertFalse(native.last_receipt['observation']['scriptInventory']['tabletShown'])
        self.assertEqual(1,len(boundary.requests))

    def test_actual_hidden_root_and_pending_callback_inventory_is_not_reduced_to_fake_absence(self):
        boundary=Boundary();boundary.inventory=inventory([manager(rootVisible=False,labelVisible=False)],
            [picker(visible=False,requestId='actual-pending-request')],tabletShown=False)
        with patch.object(normal_input,'urlopen',boundary.post):
            _native,reader=boundary.source();value=reader.capture()
        self.assertEqual(1,len(value['scriptInventory']['managers']))
        self.assertEqual('actual-pending-request',value['scriptInventory']['pickers'][0]['requestId'])
        self.assertTrue(ui_state(value)['systemPending'])
        self.assertFalse(ui_state(value)['open'])

    def test_incomplete_inventory_cannot_qualify_a_closed_manager_or_picker(self):
        boundary=Boundary();boundary.inventory=inventory(complete=False,tabletShown=False)
        with patch.object(normal_input,'urlopen',boundary.post):
            _native,reader=boundary.source();value=reader.capture()
        with self.assertRaises(NativeUIError):ui_state(value)

    def test_current_nonce_does_not_retime_stale_native_originals(self):
        boundary=Boundary();boundary.epoch=19000
        with patch.object(normal_input,'urlopen',boundary.post):
            _native,reader=boundary.source()
            with self.assertRaises(NativeUIError):reader.capture()
        self.assertEqual(1,len(boundary.requests))

    def test_nonadvancing_source_counter_cannot_become_a_second_observation(self):
        boundary=Boundary();boundary.edit=lambda v:v.update(scriptSourceSequence=1)
        with patch.object(normal_input,'urlopen',boundary.post):
            _native,reader=boundary.source();reader.capture()
            with self.assertRaises(NativeUIError):reader.capture()
        self.assertEqual(1,reader.sequence)

    def test_foreign_native_instance_and_missing_version_are_rejected(self):
        boundary=Boundary()
        with patch.object(normal_input,'urlopen',boundary.post):
            _native,reader=boundary.source();reader.capture()
            boundary.instance='11111111-2222-3333-4444-777777777777'
            with self.assertRaises(NativeUIError):reader.capture()
        for edit in (lambda v:v.pop('scriptObservationVersion'),lambda v:v.update(scriptObservationVersion=True),
                     lambda v:v.update(scriptSourceSequence=True)):
            boundary=Boundary();boundary.edit=edit
            with patch.object(normal_input,'urlopen',boundary.post):
                _native,reader=boundary.source()
                with self.assertRaises(NativeUIError):reader.capture()

    def test_projection_cannot_invent_original_counter_epoch_or_visibility(self):
        boundary=Boundary()
        with patch.object(normal_input,'urlopen',boundary.post):
            _native,reader=boundary.source();original=reader.capture()
        for edit in ({'sourceSequence':2},{'capturedEpochMs':20001},{'generation':'a'*32},
                     {'scriptInventory':inventory(tabletShown=True)},{'controls':[{'id':'script-file.confirm'}]}):
            value=deepcopy(original);value.update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):validate(value,value['commandId'],42,20000)

    def test_lost_read_receipt_does_not_reuse_previous_original_or_resend_request(self):
        boundary=Boundary()
        with patch.object(normal_input,'urlopen',boundary.post):
            native,reader=boundary.source();reader.capture();boundary.mutation='foreign-nonce'
            with self.assertRaises(NativeUIError):reader.capture()
        self.assertIsNone(native.last_receipt);self.assertEqual(2,len(boundary.requests))


if __name__=='__main__':unittest.main()
