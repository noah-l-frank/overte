"""Actual common engine callback and private files; receiver remains a seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.source_bundles import original as original_bundle
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_common_export import JourneyConsumptionExport,UNRESOLVED
from feature_journeys.engine import Journey
from feature_journeys.contract import json_document
from self_tests.test_feature_journeys import Boundary,POLICY,RUN


class BrowserCommonExportTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700)
        self.boundary=Boundary('tablet-web');self.calls=[];self.fault=None
        self.url=f'http://controlled.test/feature-fixture/v1/runs/{RUN}/'
        def send(request):
            self.calls.append(request)
            if self.fault:self.fault(request)
            return dict(journeyConsumptionReceivedVersion=2,
                **{key:request[key] for key in ('nonce','recordSha256','commonSha256')})
        self.export=JourneyConsumptionExport(self.path,'tablet-web',RUN,self.url,'a'*32,send,lambda:None)
        self.addCleanup(lambda:self.assertTrue(self.export.close_host()))
        self.addCleanup(lambda:UNRESOLVED.__setitem__(slice(None),[owner for owner in UNRESOLVED if owner is not self.export]))
        boundary=self.boundary
        self.journey=Journey('tablet-web',RUN,self.url,invoke=boundary.invoke,witness=boundary.witness,
            activate=boundary.activate,read_artifact=boundary.files.__getitem__,image_policy=POLICY,
            continuity=boundary.continuity,monotonic=lambda:boundary.clock,epoch_ms=boundary.epoch,
            sleep=boundary.sleep,report=boundary.reports.append,after_cleanup_baseline=self.export.callback)
        self.export.attach(self.journey)

    def record(self):
        state=self.export.previous
        return original_bundle(self.export.history,state['chunks'],[state['reference']],0)

    def test_actual_common_callback_seals_exact_native_and_witness_projection_before_transport(self):
        def before_reply(request):
            self.assertEqual([],self.boundary.reports)
            self.assertTrue(self.journey.cleanup_hook_started)
            self.assertEqual(2,sum(op.endswith('.cleanup') for op,_ in self.boundary.actions))
            value,raw=self.record();self.assertEqual(self.export.record_raw,raw)
            self.assertEqual('sealed',self.export.store.read()['phase'])
            self.assertTrue(json_document(value['commonRaw'])['sequenceSucceeded'])
            self.assertEqual(self.export.raw,value['commonRaw'].encode('utf-8'))
            self.assertEqual(self.journey.sequence,value['journey']['finalSequence'])
            self.assertEqual(len(self.journey.samples),len(value['journey']['samples']))
            for original,projected in zip(self.journey.samples,value['journey']['samples']):
                self.assertEqual(original['witness'],projected['witness'])
                self.assertNotIn('evidence',projected);self.assertNotIn('imagePolicy',projected)
            self.assertEqual(request['rootStamp'],list(self.export.file.stamp))
        self.fault=before_reply;self.journey.execute()
        self.assertTrue(self.export.complete);self.assertEqual(self.calls[0],self.export.receipt())
        self.assertIs(self.export.raw,self.journey.cleanup_consumption)
        self.assertTrue(self.boundary.reports[-1]['sequenceCompleted'])
        self.assertEqual('sealed',self.export.store.read()['phase'])
        before=self.export.store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.export.consume(self.export.raw)
        self.assertEqual(1,len(self.calls));self.assertEqual(before,self.export.store.path.read_bytes())

    def test_caller_created_bytes_cannot_emit_without_original_common_callback(self):
        with self.assertRaises(NativeUIError):self.export.consume(b'{}')
        self.assertEqual([],self.calls);self.assertIsNone(self.export.store.read())
        self.assertTrue(self.export.failed)

    def test_equal_but_distinct_callback_bytes_refuse_before_any_file_or_send(self):
        # Interpose only this explicit test transport to the existing callback.
        consume=self.export.consume
        def substituted(raw):return consume(bytes(bytearray(raw)))
        self.export.callback=substituted;self.journey.after_cleanup_baseline=substituted
        with self.assertRaises(NativeUIError):self.journey.execute()
        self.assertTrue(self.export.failed);self.assertIsNone(self.export.store.read())
        self.assertEqual([],self.calls);self.assertFalse(self.boundary.reports[-1]['sequenceCompleted'])

    def test_lost_delivery_keeps_sealed_originals_and_never_replays_callback(self):
        failure=OSError('Declared export delivery return lost')
        def lost(_request):raise failure
        self.fault=lost
        with self.assertRaises(OSError) as caught:self.journey.execute()
        self.assertIs(failure,caught.exception);self.assertTrue(self.export.failed)
        self.assertEqual('sealed',self.export.store.read()['phase']);self.assertEqual(1,len(self.calls))
        self.assertTrue(self.export.history.identities)
        self.assertFalse(self.boundary.reports[-1]['cleanupSucceeded'])
        before=self.export.store.path.read_bytes()
        with self.assertRaises(ValueError):self.journey.execute()
        self.assertEqual(before,self.export.store.path.read_bytes());self.assertEqual(1,len(self.calls))

    def test_same_bytes_new_root_inode_after_send_cannot_become_a_transport_receipt(self):
        def replaced(_request):
            store=PrivateFeatureState(self.export.store.path);store.write(store.read(),store.read())
        self.fault=replaced
        with self.assertRaises(NativeUIError):self.journey.execute()
        self.assertTrue(self.export.failed);self.assertFalse(self.export.complete)
        self.assertEqual('sealed',self.export.store.read()['phase']);self.assertEqual(1,len(self.calls))

    def test_transport_callback_replacement_refuses_before_encoding_or_send(self):
        self.export.send=lambda _request:None
        with self.assertRaises(NativeUIError):self.journey.execute()
        self.assertIsNone(self.export.store.read());self.assertEqual([],self.calls)

    def test_caught_nested_callback_poison_prevents_outer_transport_acknowledgement(self):
        def nested(_request):
            with self.assertRaises(NativeUIError):self.export.consume(self.export.raw)
        self.fault=nested
        with self.assertRaises(NativeUIError):self.journey.execute()
        self.assertTrue(self.export.failed);self.assertEqual(1,len(self.calls))
        self.assertEqual('sealed',self.export.store.read()['phase'])
        self.assertFalse(self.boundary.reports[-1]['sequenceCompleted'])

    def test_real_projection_capacity_refuses_before_compression_and_root_creation(self):
        consumed=self.journey.consumed_cleanup
        def enlarged(*args):
            # Hostile historical data cannot force allocation before preflight.
            # It is deliberately not claimed to be an accepted native original.
            self.journey.samples[0]['state']['text']='\0'*350000
            return consumed(*args)
        self.journey.consumed_cleanup=enlarged
        with patch('adapters.pico4.browser_common_export.prepare',side_effect=AssertionError('Must not allocate codec')) as codec:
            with self.assertRaises(NativeUIError):self.journey.execute()
            codec.assert_not_called()
        self.assertIsNone(self.export.store.read());self.assertEqual([],self.calls)


if __name__=='__main__':unittest.main()
