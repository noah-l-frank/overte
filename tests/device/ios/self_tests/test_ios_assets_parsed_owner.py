"""Actual owned bytes and original QML, with explicit native/parser/oven seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_parsed_fixture import Fixture


class AssetsParsedOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.f))
        self.model,self.baking=self.f.prepared();self.o=self.f.parsed(self.model,self.baking);self.o.reserve()

    def test_original_parser_input_matches_independent_rebaked_blob_and_actual_new_model(self):
        proof=self.o.observe();self.assertEqual(self.model.state['creation']['proof']['entityId'],proof['entityId'])
        self.assertEqual(self.baking.state['result']['proof']['outputHash'],proof['sha256']);self.assertGreater(proof['bytes'],25196)
        self.assertFalse(self.o.frame(self.o.state['sourceIndex'])['originals']['origin']['source']['resourceRetirementAvailable'])
        inputs=deepcopy(self.f.boundary.inputs);requests=deepcopy(self.f.requests);clocks=deepcopy(self.f.boundary.native_clock.commands)
        restored=self.f.parsed(self.model,self.baking);self.assertEqual(proof,restored.observe())
        self.assertEqual(inputs,self.f.boundary.inputs);self.assertEqual(requests,self.f.requests);self.assertEqual(clocks,self.f.boundary.native_clock.commands)
        rows=inspect_directory(self.path);self.assertIn('parsed-resource-retirement',rows[0]['responsibilities']);self.assertIn('model-resource-origin',rows[0]['responsibilities'])
        self.assertEqual(inputs,self.f.boundary.inputs);self.assertEqual(requests,self.f.requests);self.assertEqual(clocks,self.f.boundary.native_clock.commands)
        reference=restored.sources.state['frames'][0];path=restored.sources.originals.path(restored.sources.originals.expand(reference));raw=path.read_bytes()
        path.rename(self.path/'retained-origin-frame');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):inspect_directory(self.path)

    def test_saved_logical_source_before_parent_adoption_recovers_without_another_native_query(self):
        intent=self.o.sources.originals.intent;failed=[False]
        def crash(kind,reference):
            result=intent(kind,reference)
            if reference['phase']=='saved' and not failed[0]:failed[0]=True;raise RuntimeError('lost logical source adoption')
            return result
        self.o.sources.originals.intent=crash
        with self.assertRaises(RuntimeError):self.o.observe()
        native=deepcopy(self.f.boundary.native_clock.commands);inputs=deepcopy(self.f.boundary.inputs)
        restored=self.f.parsed(self.model,self.baking);self.assertIsNotNone(restored.observe())
        self.assertEqual(native,self.f.boundary.native_clock.commands);self.assertEqual(inputs,self.f.boundary.inputs)

    def test_foreign_parser_body_cannot_be_replaced_with_requested_hash_or_server_output(self):
        raw=b'foreign actual parser input'
        def foreign(packet):packet['source']['history']['downloads'][0].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())
        self.f.boundary.origin_fault=foreign
        with self.assertRaises(NativeUIError):self.o.observe()
        self.assertEqual('backend',self.o.state['phase']);self.assertIsNone(self.o.state['result']);inputs=deepcopy(self.f.boundary.inputs)
        restored=self.f.parsed(self.model,self.baking)
        with self.assertRaises(NativeUIError):restored.observe()
        frame=restored.frame(restored.state['sourceIndex']);self.assertEqual(hashlib.sha256(raw).hexdigest(),frame['originals']['origin']['source']['history']['downloads'][0]['sha256'])
        self.assertEqual(inputs,self.f.boundary.inputs)

    def test_pending_delivery_body_never_becomes_consumed_from_loaded_wrapper_flags(self):
        self.f.boundary.origin_fault=lambda packet:packet['source']['history']['downloads'][0].update(deliveryReturned=None)
        with self.assertRaises(NativeUIError):self.o.observe()
        self.assertEqual('backend',self.o.state['phase']);self.assertIsNone(self.o.state['result'])

    def test_lost_backend_result_polls_same_original_without_repeating_source_or_input(self):
        opened=self.f.open;failed=[False]
        def lost(request,timeout):
            result=opened(request,timeout)
            if not failed[0]:failed[0]=True;raise RuntimeError('lost backend readonly result')
            return result
        self.f.open=lost
        with self.assertRaisesRegex(RuntimeError,'lost backend readonly result'):self.o.observe()
        native=deepcopy(self.f.boundary.native_clock.commands);inputs=deepcopy(self.f.boundary.inputs);last=self.f.requests[-1]
        self.f.open=opened;restored=self.f.parsed(self.model,self.baking);self.assertIsNotNone(restored.observe())
        self.assertEqual(last['commandId'],self.f.requests[-1]['commandId']);self.assertEqual('poll',self.f.requests[-1]['operation'])
        self.assertEqual(native,self.f.boundary.native_clock.commands);self.assertEqual(inputs,self.f.boundary.inputs)

    def test_opened_raw_prefix_remains_exact_owned_bytes_and_blocks_reacquisition(self):
        intent=self.o.sources.raws.store.intent
        def crash(kind,reference):
            result=intent(kind,reference)
            if reference['phase']=='opened':raise RuntimeError('interrupted raw source holder')
            return result
        self.o.sources.raws.store.intent=crash
        with self.assertRaises(NativeUIError):self.o.observe()
        native=deepcopy(self.f.boundary.native_clock.commands);pending=deepcopy(self.o.sources.raws.pending);restored=self.f.parsed(self.model,self.baking)
        with self.assertRaises(NativeUIError):restored.observe()
        with self.assertRaises(NativeUIError):restored.freeze_failed_source()
        self.assertEqual(native,self.f.boundary.native_clock.commands);self.assertEqual(pending,restored.sources.raws.pending)
        self.assertFalse(restored.sources._cached);self.assertIsNone(restored.state['result'])
        self.assertIn('parsed-source-write',inspect_directory(self.path)[0]['responsibilities'])

    def test_lost_readonly_origin_retains_attempt_then_new_bracket_uses_fresh_nonce(self):
        send=self.o.sources.origin_reader.send;lost=[]
        def fail(query):send(query);lost.append(deepcopy(query));raise NativeUIError('lost readonly origin result')
        self.o.sources.origin_reader.send=fail
        with self.assertRaises(NativeUIError):self.o.observe()
        self.assertFalse(self.o.sources._cached);inputs=deepcopy(self.f.boundary.inputs)
        self.o.freeze_failed_source();self.o.sources.origin_reader.send=send;proof=self.o.observe()
        self.assertEqual(1,len(self.o.sources.state['interrupted']));self.assertNotEqual(lost[0]['commandId'],proof['originRequestId'])
        self.assertEqual(inputs,self.f.boundary.inputs)

    def test_lost_freeze_parent_adopts_exact_saved_interrupted_attempt_without_repeating_query(self):
        send=self.o.sources.origin_reader.send
        def fail(query):send(query);raise NativeUIError('lost origin result before freeze')
        self.o.sources.origin_reader.send=fail
        with self.assertRaises(NativeUIError):self.o.observe()
        native=deepcopy(self.f.boundary.native_clock.commands);write=self.o.store.write
        def lost(value,previous):raise RuntimeError('lost freeze parent save')
        self.o.store.write=lost
        with self.assertRaisesRegex(RuntimeError,'lost freeze parent save'):self.o.freeze_failed_source()
        with self.assertRaises(NativeUIError):self.o.observe()
        self.o.store.write=write;restored=self.f.parsed(self.model,self.baking);restored.freeze_failed_source()
        self.assertEqual(native,self.f.boundary.native_clock.commands);self.assertEqual(1,len(restored.sources.state['interrupted']))
        self.assertIsNotNone(restored.observe());self.assertEqual(1,len(restored.sources.state['interrupted']))

    def test_orphan_prior_backend_slot_cannot_be_adopted_as_a_fresh_output_query(self):
        self.baking.backend.checkpoint('parsed-output-1',self.f.files.state['ticket']);native=deepcopy(self.f.boundary.native_clock.commands)
        with self.assertRaises(NativeUIError):self.o.observe()
        self.assertEqual(native,self.f.boundary.native_clock.commands);self.assertFalse(self.o.sources.state and self.o.sources.state['frames'])


class AssetsParsedInputOriginTests(unittest.TestCase):
    def test_original_consumer_body_cannot_be_reconstructed_from_later_correct_server_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary);path.chmod(0o700);fixture=Fixture(path)
            try:
                with patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    actual_input=b'actual foreign bytes consumed by the declared native loader'
                    fixture.boundary.resolve_model=lambda _url:actual_input
                    model,baking=fixture.prepared();id_=model.state['creation']['proof']['entityId']
                    original=deepcopy(fixture.boundary.origin_rows[id_]);self.assertEqual(hashlib.sha256(actual_input).hexdigest(),original['sha256'])
                    fixture.boundary.resolve_model=fixture.resolve_model
                    owner=fixture.parsed(model,baking);owner.reserve()
                    with self.assertRaises(NativeUIError):owner.observe()
                    self.assertEqual(original,fixture.boundary.origin_rows[id_]);self.assertIsNone(owner.state['result'])
                    restored=fixture.parsed(model,baking)
                    with self.assertRaises(NativeUIError):restored.observe()
                    self.assertEqual(original,fixture.boundary.origin_rows[id_]);self.assertIsNone(restored.state['result'])
            finally:fixture.close()


if __name__=='__main__':unittest.main()
