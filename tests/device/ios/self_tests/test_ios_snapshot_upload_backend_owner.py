"""Durable real original files around the modeled native/backend boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_upload_backend_owner import IOSSnapshotUploadBackendOwner
from ios.self_tests.snapshot_upload_backend_owner_domain import SnapshotBackendOriginalDomain


class SnapshotUploadBackendOwnerTests(unittest.TestCase):
    def test_normal_upload_joins_independently_admitted_read_only_source_and_exact_original_body(self):
        d=SnapshotBackendOriginalDomain(self);d.prepare_native()
        with d.backend_owner() as owner:
            result=owner.original();self.assertTrue(result['authenticatedProtocolOriginalJoined']);self.assertTrue(result['backendBodyOriginalRetained']);self.assertTrue(result['readOnlyRoleAdmitted'])
            self.assertTrue(result['backendFixtureRetirementRequired']);self.assertTrue(result['transportProcessProofRequired']);native=owner.native
        requests=deepcopy(d.private_calls)
        with native.lock.held():
            historical=IOSSnapshotUploadBackendOwner.history(native);self.assertIs(historical.monotonic,time.monotonic);self.assertEqual(result,historical.proof())
        self.assertEqual(requests,d.private_calls);self.assertEqual(1,d.upload_count)
        self.assertTrue(all(row['method']=='GET' for row in requests));self.assertEqual(4,len(requests))
        for path in d.ctx.root.glob('snapshot-upload-backend-*.json'):
            self.assertNotIn(d._adapter.encode(),path.read_bytes());self.assertNotIn(d.backend._authorization.encode(),path.read_bytes())
    def test_lost_source_read_uses_same_cached_original_nonce_without_retiming_or_upload_replay(self):
        d=SnapshotBackendOriginalDomain(self);d.prepare_native();d.lost_source=True
        with d.backend_owner() as owner,self.assertRaises(ValueError):owner.original()
        old=d.private_calls[-1]['nonce'];first=deepcopy(d.backend.provider.runs[owner.run]['queries'][old]['packet'])
        with d.backend_owner() as owner:owner.original();self.assertEqual(first,owner.packet(owner.state['admission']))
        sources=[row for row in d.private_calls if row['path'].endswith('/snapshots/source')];self.assertEqual([old,old],[row['nonce'] for row in sources]);self.assertEqual(1,d.upload_count)
    def test_actual_late_original_is_retained_then_fresh_admission_keeps_first_process_and_scope(self):
        d=SnapshotBackendOriginalDomain(self);d.prepare_native();d.lost_source=True
        with d.backend_owner() as owner,self.assertRaises(ValueError):owner.original()
        nonce=d.private_calls[-1]['nonce'];first=deepcopy(d.backend.provider.runs[owner.run]['queries'][nonce]['packet']);d.sleep(1.65)
        with d.backend_owner() as owner:
            owner.original();retained=[owner.packet(index) for index,slot in enumerate(owner.state['slots'],1) if slot['query']['kind']=='source']
            self.assertEqual(2,len(retained));self.assertEqual(first,retained[0]);self.assertEqual(owner.scope(first),owner.state['scope'])
            self.assertNotEqual(retained[0]['requestId'],retained[1]['requestId']);self.assertGreater(retained[1]['clock']['epochMs']-retained[0]['clock']['epochMs'],1500)
        reads=[row for row in d.private_calls if row['path'].endswith('/snapshots/source')];self.assertEqual([nonce,nonce],[row['nonce'] for row in reads[:2]]);self.assertEqual(1,d.upload_count)
    def test_saved_source_frame_before_parent_CAS_adopts_same_inode_without_second_source_get(self):
        d=SnapshotBackendOriginalDomain(self);d.prepare_native()
        with d.backend_owner() as owner:
            save=owner.save
            def interrupted():
                if owner.state['slots'] and owner.state['slots'][-1]['label']=='admission' and owner.state['slots'][-1]['phase']=='retained':raise OSError('Original saved frame before parent retained CAS')
                return save()
            with patch.object(owner,'save',side_effect=interrupted),self.assertRaises(OSError):owner.original()
            slot=owner.state['slots'][-1];path=owner.frames().path(slot['storage']);before=(path.stat().st_ino,path.read_bytes())
        with d.backend_owner() as owner:owner.original()
        self.assertEqual(before,(path.stat().st_ino,path.read_bytes()));self.assertEqual(1,sum(row['path'].endswith('/snapshots/source') for row in d.private_calls))
    def test_same_bytes_replaced_original_inode_is_rejected_without_new_http_or_native_input(self):
        d=SnapshotBackendOriginalDomain(self);d.prepare_native()
        with d.backend_owner() as owner:
            owner.original();slot=owner.state['slots'][-1];path=owner.frames().path(slot['storage']);raw=path.read_bytes()
        other=path.with_name('owned-test-replacement');other.write_bytes(raw);other.chmod(0o600);os.replace(other,path);before=deepcopy(d.private_calls)
        with self.assertRaises(NativeUIError):
            with d.backend_owner():pass
        self.assertEqual(before,d.private_calls);self.assertEqual(1,d.upload_count)
    def test_actual_foreign_account_authority_blocks_body_fetch_after_retaining_source_responsibility(self):
        d=SnapshotBackendOriginalDomain(self);d.prepare_native();d.foreign_authority=True
        with d.backend_owner() as owner,self.assertRaises(NativeUIError):owner.original()
        self.assertIsNone(owner.state['result']);self.assertFalse(any('/bodies/' in row['path'] for row in d.private_calls));self.assertEqual(1,d.upload_count)


if __name__=='__main__':unittest.main()
