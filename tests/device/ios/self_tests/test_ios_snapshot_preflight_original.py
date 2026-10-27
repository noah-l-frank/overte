"""Actual normal Script→Upload joined to immutable preflight byte originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.self_tests.snapshot_preflight_original_domain import SnapshotPreflightOriginalDomain


class SnapshotPreflightOriginalOwnerTests(unittest.TestCase):
    def test_normal_actual_script_upload_retains_preflight_bytes_and_pure_parent_bound_history(self):
        d=SnapshotPreflightOriginalDomain(self);d.prepare_native()
        with d.backend_owner() as owner:
            result=owner.original();native=owner.native
            self.assertEqual(2,result['snapshotUploadBackendResultVersion']);self.assertTrue(result['controlledDomainPreflightOriginalJoined'])
            self.assertTrue(result['frontendResponseConsumptionRequired']);self.assertTrue(result['externalMetaverseRegistrationRequired'])
            self.assertEqual(d.native_birth_preflight,[result['preflight']['requestId']]);self.assertEqual(d.domain_policy,result['domainPolicy'])
            preflight=owner.packet(owner.state['preflight']);self.assertEqual(1,len(preflight['responses']))
        calls=deepcopy(d.private_calls)
        with native.lock.held():
            historical=IOSSnapshotUploadBackendOwner.history(native,domain_policy=d.domain_policy)
            self.assertEqual(result,historical.proof());self.assertIs(historical.monotonic,time.monotonic)
            with self.assertRaises(NativeUIError):IOSSnapshotUploadBackendOwner.history(native)
        self.assertEqual(calls,d.private_calls);self.assertEqual(1,d.upload_count);self.assertEqual(5,len(calls))
    def test_lost_preflight_GET_retains_same_original_nonce_and_never_replays_native_upload(self):
        d=SnapshotPreflightOriginalDomain(self);d.prepare_native();d.lost_preflight=True
        with d.backend_owner() as owner,self.assertRaises(ValueError):owner.original()
        nonce=d.private_calls[-1]['nonce'];original=deepcopy(d.backend.provider.concurrency.original(owner.run,nonce))
        with d.backend_owner() as owner:owner.original();self.assertEqual(original,owner.frame(owner.state['preflight'])['response'])
        reads=[row for row in d.private_calls if row['path'].endswith('/preflight/original')]
        self.assertEqual([nonce,nonce],[row['nonce'] for row in reads]);self.assertEqual(1,d.upload_count)
    def test_saved_preflight_original_before_parent_CAS_adopts_original_inode_without_another_GET(self):
        d=SnapshotPreflightOriginalDomain(self);d.prepare_native()
        with d.backend_owner() as owner:
            save=owner.save
            def interrupted():
                if owner.state['slots'] and owner.state['slots'][-1]['label']=='preflight' and owner.state['slots'][-1]['phase']=='retained':raise OSError('Actual preflight original saved before parent CAS')
                return save()
            with patch.object(owner,'save',side_effect=interrupted),self.assertRaises(OSError):owner.original()
            slot=owner.state['slots'][-1];path=owner.frames().path(slot['storage']);original=(path.stat().st_ino,path.read_bytes())
        with d.backend_owner() as owner:owner.original()
        self.assertEqual(original,(path.stat().st_ino,path.read_bytes()));self.assertEqual(1,sum(row['path'].endswith('/preflight/original') for row in d.private_calls));self.assertEqual(1,d.upload_count)
    def test_foreign_independent_domain_binding_refuses_original_before_backend_body_reads(self):
        d=SnapshotPreflightOriginalDomain(self);d.prepare_native();d.domain_policy['binding']['processId']+=1
        with d.backend_owner() as owner,self.assertRaises(NativeUIError):owner.original()
        self.assertFalse(any('/bodies/' in row['path'] for row in d.private_calls));self.assertEqual(1,d.upload_count)


if __name__=='__main__':unittest.main()
