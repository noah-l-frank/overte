"""Lossless oversize originals; every part retains existing storage bounds."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import base64
import contextlib
import io
import random
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from adapters.chat_journey import source_bundles as bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import canonical,pack,MAX_PACKED
from self_tests import chat_diagnostic


class SourceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.value=dict(originalOpaqueBytes=base64.b64encode(random.Random(74).randbytes(90000)).decode('ascii'))

    def test_actual_oversize_pack_input_is_losslessly_fragmented_without_raising_any_leaf_limit(self):
        with self.assertRaises(NativeUIError):pack([self.value])
        with self.assertRaises(NativeUIError):PrivateFeatureState(self.root/'flat.json').write(self.value,None)
        ref,parts=bundles.prepare(self.value,0,[]);self.assertGreater(len(parts),1)
        self.assertTrue(all(len(pack([part])['data'])<=MAX_PACKED for part in parts))
        self.assertEqual((self.value,canonical(self.value)),bundles.decode_parts(parts,ref,0))
        store=chat_diagnostic.write(self.root,'original-large-report',self.value)
        self.assertEqual((self.value,canonical(self.value)),chat_diagnostic.read(store))
        self.assertTrue(all(path.stat().st_size<=65536 for path in self.root.iterdir()))

    def test_reordering_missing_cross_bundle_or_alias_parts_cannot_reconstruct(self):
        ref,parts=bundles.prepare(self.value,0,[])
        for fault in ('order','missing','bundle','bool','extra','sha'):
            with self.subTest(fault=fault):
                changed=deepcopy(parts);header=deepcopy(ref)
                if fault=='order':changed.reverse()
                elif fault=='missing':changed.pop()
                elif fault=='bundle':changed[0]['bundle']=1
                elif fault=='bool':changed[0]['part']=False
                elif fault=='extra':changed[0]['requestedSuccess']=True
                else:header['sha256']='0'*64
                with self.assertRaises(NativeUIError):bundles.decode_parts(changed,header,0)

    def test_all_parts_and_logical_original_bytes_count_against_existing_limits(self):
        with patch.object(bundles,'MAX_FRAMES',2),self.assertRaises(NativeUIError):bundles.prepare(self.value,0,[])
        with patch.object(bundles,'MAX_RAW',1024),self.assertRaises(NativeUIError):bundles.prepare(self.value,0,[])

    def test_suppressed_failure_keeps_exact_unpublished_pack_bytes_and_original_limit(self):
        try:
            try:pack([self.value])
            except NativeUIError:raise NativeUIError('Outer source owner refused') from None
        except NativeUIError as error:diagnostic=chat_diagnostic.exception(error)
        inputs=[frame['failedPackInput'] for context in diagnostic['contexts'] for frame in context['frames'] if 'failedPackInput' in frame]
        self.assertEqual(1,len(inputs));self.assertFalse(inputs[0]['committedSourceSample'])
        self.assertGreater(inputs[0]['encodedBytes'],MAX_PACKED)
        self.assertEqual(canonical([self.value]),base64.b64decode(inputs[0]['rawBase64']))
        store=chat_diagnostic.write(self.root,'original-failure',diagnostic)
        self.assertEqual(diagnostic,chat_diagnostic.read(store)[0])

    def test_existing_or_incomplete_diagnostic_cannot_be_overwritten_or_adopted(self):
        store=chat_diagnostic.write(self.root,'original-report',self.value);raw=store.path.read_bytes()
        with self.assertRaises(NativeUIError):chat_diagnostic.write(self.root,'original-report',self.value)
        self.assertEqual(raw,store.path.read_bytes());root=store.read()
        store.write({**root,'phase':'reading'},root)
        with self.assertRaises(NativeUIError):chat_diagnostic.read(store)

    def test_report_failure_never_masks_original_source_error_and_diagnostic_is_not_retried(self):
        from self_tests import test_chat_remote_journey as fixture
        case=fixture.RemoteJourneyTests();case.full=True;case.host_root=self.root;case.reports=[]
        case.report_error=None;case.error_diagnostic_issued=False;case.started=time.monotonic()
        report=dict(sequenceCompleted=False,cleanupSucceeded=False,original=self.value)
        with (patch.object(chat_diagnostic,'write',side_effect=NativeUIError('Lost diagnostic write')) as write,
                contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO())):
            try:raise NativeUIError('Actual original source error')
            except NativeUIError as original:
                case.report(report);self.assertIs(original,sys.exc_info()[1]);case.preserve_error(original)
            self.assertEqual(2,write.call_count)
        self.assertIsNotNone(case.report_error);self.assertTrue(case.error_diagnostic_issued)

    def test_lost_actual_part_write_keeps_reading_root_and_original_parts_without_retry(self):
        write=PrivateFeatureState.write;attempts=[]
        def lost(store,value,previous):
            result=write(store,value,previous)
            if store.path.name.endswith('.frame-001.json'):
                attempts.append(store.path);raise OSError('Actual part write reply lost')
            return result
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(OSError):chat_diagnostic.write(self.root,'lost-report',self.value)
        store=PrivateFeatureState(self.root/'lost-report.json');self.assertEqual('reading',store.read()['phase'])
        first=self.root/'lost-report.json.frame-000.json';raw=first.read_bytes()
        self.assertEqual(1,len(attempts));self.assertTrue(attempts[0].exists())
        with self.assertRaises(NativeUIError):chat_diagnostic.write(self.root,'lost-report',self.value)
        with self.assertRaises(NativeUIError):chat_diagnostic.read(store)
        self.assertEqual(raw,first.read_bytes());self.assertEqual(1,len(attempts))

    def test_original_part_identity_still_refuses_same_byte_replacement(self):
        store=chat_diagnostic.write(self.root,'identity-report',self.value);root=store.read()
        history=ChatSourceChunks(store,{key:root[key] for key in ('chatHostDiagnosticVersion','scope','name')})
        history.load(root['chunks']);child=history.store(0);value=child.read();child.write(value,value)
        with self.assertRaises(NativeUIError):bundles.original(history,root['chunks'],root['bundles'],0)

    def test_historical_v1_record_keeps_missing_clocks_and_fragments_missing(self):
        from adapters.chat_journey.remote_publication import original_record
        from self_tests.test_chat_script_source import BINDING
        store=PrivateFeatureState(self.root/'legacy-v1.json')
        scope=dict(chatRemotePublicationVersion=1,runId='a'*32,fixtureUrl='http://controlled.test/runs/'+'a'*32+'/',
            binding=BINDING,peerBinding=BINDING,hostProcessIdentity='31:original-host',instance='b'*32,journal=store.path.name)
        history=ChatSourceChunks(store,scope);reading={**scope,'phase':'reading','chunks':[]};store.write(reading,None)
        value=dict(legacyOriginal='retained historical JSON only')
        manifest=history.append(value,[]);ready={**scope,'phase':'ready','chunks':manifest};store.write(ready,reading)
        cold=ChatSourceChunks(store,scope);cold.load(manifest)
        self.assertEqual(value,original_record(cold,ready,0));self.assertNotIn('freshness',value)
        self.assertNotIn('bundles',store.read());self.assertEqual(1,store.read()['chatRemotePublicationVersion'])


if __name__=='__main__':unittest.main()
