"""Actual private native file receipts; C++ and native transport modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts,receipt
from ios.adapters.emote_marker_files import OwnedEmoteMarkerFiles
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from self_tests.test_native_script_files import Boundary as Files
from self_tests.test_native_feature_observation import Boundary as Native


class FileReceiptsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.boundary=Files(self.root);self.boundary.root=self.root/('feature-script-'+RUN);self.files=self.boundary.native(ios=True)
        self.native=Native();self.native.mutate=lambda p:p.update(processId=31)
        self.owner=OwnedEmoteMarkerFiles(self.files,PrivateFeatureState(self.root/'owned.json'),BINDING)
        self.ownership=self.owner.reserve_marker(RUN,'http://fixture.invalid/feature-fixture/v1/runs/'+RUN+'/','a'*32)
        self.owner.stage_reserved();self.store=PrivateFeatureState(self.root/'ios-emote-primary-file-receipts.json')
    def tearDown(self):self.held.__exit__(None,None,None);self.temp.cleanup()
    def reader(self):
        native=NativeFeatureObservation(self.native.send,self.native.original,lambda:20000,lambda:True,31,ios=True,native_clock_bound=True,
            monotonic=lambda:0.,sleep=lambda _:None)
        return IOSEmoteFileReceipts(self.store,self.root,BINDING,RUN,'primary',self.lock,lambda:True,native=native,files=self.files,
            epoch_ms=lambda:90000.,monotonic=lambda:0.)
    def test_exact_native_original_bytes_and_later_observed_absence_remain_immutable(self):
        reader=self.reader();first=reader.capture('bytes',self.ownership);before=reader.original(first)
        self.owner.release();last=reader.capture('absent',self.ownership);after=reader.original(last)
        self.assertEqual(dict(exists=False,files=[]),after['packet']['source']);self.assertTrue(before['packet']['source']['exists'])
        self.assertGreater(after['packet']['sequence'],before['packet']['sequence'])
        self.assertEqual(before,self.reader().original(first));self.assertFalse(self.boundary.root.exists())
        self.assertEqual(self.ownership['ownerToken'],before['query']['ownerToken'])
        reader.guard=lambda:(_ for _ in ()).throw(AssertionError('historical live guard'))
        archived=IOSEmoteFileReceipts.archive(reader.store.read(),store=reader.store,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock)
        self.assertEqual(after,archived.original(last))
    def test_lost_original_observe_is_abandoned_without_resending_its_nonce(self):
        reader=self.reader();send=self.files.send
        def lost(query):send(query);raise OSError('Synthetic lost file observation reply')
        with patch.object(self.files,'send',side_effect=lost),self.assertRaises(NativeUIError):reader.capture('bytes',self.ownership)
        before=deepcopy(self.boundary.commands);self.assertTrue(self.reader().abandon());self.assertEqual(before,self.boundary.commands)
        reader=self.reader();ref=reader.capture('bytes',self.ownership);self.assertEqual(1,len(reader.state['abandoned']))
        self.assertNotEqual(before[-1]['commandId'],reader.original(ref)['query']['commandId'])
    def test_changed_native_raw_receipt_or_claimed_absence_with_present_files_is_rejected(self):
        reader=self.reader();ref=reader.capture('bytes',self.ownership);original=reader.original(ref)
        altered=deepcopy(original);altered['kind']='absent'
        with self.assertRaises(NativeUIError):receipt(altered,root=self.root,binding=BINDING,run=RUN,role='primary')
        reader.record_store(ref['index']).path.write_bytes(b'{}')
        with self.assertRaises(NativeUIError):self.reader()
    def test_lost_local_record_return_adopts_the_same_original_without_another_native_request(self):
        reader=self.reader();original=reader.resolve;count=[0]
        def lost():
            count[0]+=1
            if count[0]==2:raise OSError('Synthetic lost receipt metadata return')
            return original()
        with patch.object(reader,'resolve',side_effect=lost),self.assertRaises(OSError):reader.capture('bytes',self.ownership)
        before=len(self.boundary.commands);rebuilt=self.reader();self.assertTrue(rebuilt.resolve())
        self.assertEqual(before,len(self.boundary.commands));self.assertEqual(1,len(rebuilt.state['records']))


if __name__=='__main__':unittest.main()
