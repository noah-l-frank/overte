"""Explicit existing backend factory join to original Capture2/Upload2."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.self_tests.snapshot_combined_backend_domain import CombinedBackendDomain
from ios.self_tests.snapshot_pending_domain import REAL_TIME,REAL_MONOTONIC,REAL_SLEEP


class SnapshotCombinedBackendTests(unittest.TestCase):
    def test_normal_actual_script_and_protected_originals_bind_same_combined_capture_upload_without_archive_queries(self):
        d=CombinedBackendDomain(self);d.prepare_native()
        with d.backend_owner() as owner:
            result=owner.original();native=owner.native;self.assertTrue(native.combined);self.assertTrue(native.capture.combined)
            self.assertEqual(2,result['snapshotUploadBackendResultVersion']);self.assertTrue(result['frontendResponseConsumptionRequired'])
            self.assertTrue(native.proof()['frontendHTTPConsumerRequired']);self.assertTrue(result['controlledDomainPreflightOriginalJoined'])
            self.assertEqual(d.native_birth_preflight,[result['preflight']['requestId']]);self.assertEqual(d.domain_policy,result['domainPolicy'])
            packet=native.capture.history('work',native.capture.state['settled']['work']).historical()['packet']
            self.assertEqual('qrc:/scripts/defaultScripts.js',packet['source']['workers'][0]['manager']['url'])
            artifact=native.capture.history('artifact',native.capture.state['artifact']);host=artifact.path();original=(host.stat().st_ino,host.read_bytes())
            self.assertEqual(original[1],d.backend.independent_body(result['upload'])[1])
        calls=deepcopy(d.private_calls);commands=deepcopy(d.commands)
        with native.lock.held():
            historical=IOSSnapshotUploadBackendOwner.history(native,domain_policy=d.domain_policy);self.assertEqual(result,historical.proof())
        self.assertEqual(calls,d.private_calls);self.assertEqual(commands,d.commands);self.assertEqual(1,d.upload_count)
        self.assertEqual(original,(host.stat().st_ino,host.read_bytes()))

    def test_default_factory_cannot_adopt_combined_native_owner_before_read_only_backend_query(self):
        d=CombinedBackendDomain(self);d.prepare_native();calls=deepcopy(d.private_calls);commands=deepcopy(d.commands)
        with self.assertRaises(NativeUIError),d.backend_owner(combined=False):pass
        self.assertEqual(calls,d.private_calls);self.assertEqual(commands,d.commands);self.assertEqual(1,d.upload_count)

    def test_lost_preflight_original_retains_first_nonce_bytes_before_fresh_admission_without_second_upload(self):
        d=CombinedBackendDomain(self);d.prepare_native();d.lost_preflight=True
        with d.backend_owner() as owner,self.assertRaises(ValueError):owner.original()
        nonce=d.private_calls[-1]['nonce'];original=deepcopy(d.backend.provider.concurrency.original(owner.run,nonce))
        # An actual late return remains an original fact. The unchanged 1.5s
        # qualification may select a fresh GET rather than retime that export.
        wall,mono=REAL_TIME(),REAL_MONOTONIC();REAL_SLEEP(1.65)
        self.assertGreaterEqual((REAL_TIME()-wall)*1000,1500);self.assertGreaterEqual((REAL_MONOTONIC()-mono)*1000,1500)
        with d.backend_owner() as owner:
            owner.original();old=[(index,slot) for index,slot in enumerate(owner.state['slots'],1)
                if slot['query']['kind']=='preflight' and slot['query']['requestId']==nonce]
            self.assertEqual(1,len(old));index,_slot=old[0];first=owner.frame(index)
            self.assertEqual(original,first['response']);self.assertFalse(owner.timely(first))
            selected=owner.frame(owner.state['preflight']);fresh=selected['query']['requestId']
            self.assertNotEqual(nonce,fresh);self.assertTrue(owner.timely(selected))
            before,after=owner.packet(index),owner.packet(owner.state['preflight'])
            self.assertEqual(owner.scope(before),owner.scope(after));self.assertEqual(before['snapshot'],after['snapshot'])
            self.assertEqual(before['responses'],after['responses'])
        self.assertEqual(original,d.backend.provider.concurrency.original(owner.run,nonce))
        reads=[row for row in d.private_calls if row['path'].endswith('/preflight/original')]
        self.assertEqual([nonce,nonce,fresh],[row['nonce'] for row in reads]);self.assertEqual(1,d.upload_count)


if __name__=='__main__':unittest.main()
