"""Connected two-prefix original file cleanup; device/native producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
import json
from types import SimpleNamespace
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_journey_files import IOSSnapshotJourneyFilesOwner
from ios.self_tests.snapshot_journey_files_domain import SnapshotJourneyFilesDomain,RUN


class SnapshotJourneyFilesTests(unittest.TestCase):
    def captured(self):
        d=SnapshotJourneyFilesDomain(self);d.complete_pending()
        with d.capture_owner() as owner:owner.capture('c'*32)
        return d
    def test_actual_pending_then_PNG_and_two_prefix_quiet_preserve_all_original_ownership(self):
        d=SnapshotJourneyFilesDomain(self);d.complete_pending()
        with d.capture_owner() as owner:image=owner.capture('c'*32);self.assertEqual('png',image['image']['format'])
        self.assertEqual((2,1,1),(d.capture_count,d.png_count,d.cancel_count));self.assertTrue(d.f.f.h.path.exists())
        with d.files_owner() as owner:
            proof=owner.cleanup();self.assertEqual(['parity-'+RUN[:16]+'-animated','parity-'+RUN[:16]+'-still-png'],proof['fileChannel']['prefixes'])
            self.assertTrue(proof['hostOriginalRetained']);self.assertTrue(proof['wholeFeatureRequired']);self.assertFalse(proof['standaloneCaptureFinalized'])
            self.assertEqual('cleaning',owner.capture.state['phase']);self.assertEqual([],owner.capture.state['quiet']);url=owner.fixture_url
        self.assertFalse(d.f.f.h.path.exists());self.assertEqual('',d.f.input_native.name)
        self.assertEqual(1,sum(query['action']=='feature-ios-snapshot-file-remove' for query in d.commands))
        d.good=False
        with d.ctx.lock.held():
            history=IOSSnapshotJourneyFilesOwner.archive(PrivateFeatureState(d.ctx.root/'ios-snapshot-journey-files-owner.json'),d.ctx.lock,d.ctx.binding,RUN,url)
            self.assertEqual(proof,history.proof())

    def test_lost_delete_return_reads_original_receipt_before_any_new_probe_and_never_unlinks_twice(self):
        d=self.captured();d.lose_remove=True
        with d.files_owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertFalse(d.f.f.h.path.exists());before=len(d.trace)
        with d.files_owner() as owner:self.assertTrue(owner.cleanup()['hostOriginalRetained'])
        self.assertEqual('original-remove-receipt',d.trace[before]);self.assertEqual(1,sum(q['action']=='feature-ios-snapshot-file-remove' for q in d.commands))

    def test_actual_retained_remove_callback_blocks_quiet_until_real_weak_expiry_without_resend(self):
        d=self.captured();d.keep_remove=True
        with d.files_owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertFalse(d.f.f.h.path.exists());self.assertTrue(d.held_removes);d.held_removes.clear();d.keep_remove=False
        with d.files_owner() as owner:self.assertTrue(owner.cleanup()['hostOriginalRetained'])
        self.assertEqual(1,sum(q['action']=='feature-ios-snapshot-file-remove' for q in d.commands))

    def test_unowned_third_prefix_blocks_before_any_delete(self):
        d=self.captured();query=dict(schemaVersion=1,action='snapshot-files',commandId='ios-'+uuid.uuid4().hex,operation='list',prefix='parity-'+RUN[:16]+'-panorama')
        d.post(SimpleNamespace(data=json.dumps(query).encode()),5)
        with d.files_owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertTrue(d.f.f.h.path.exists());self.assertFalse(any(q['action']=='feature-ios-snapshot-file-remove' for q in d.commands))

    def test_another_initial_empty_manifest_nonce_cannot_replace_the_owned_pending_original(self):
        d=self.captured();row=next(row for row in d.owned.prefixes if row['prefix'].endswith('-animated'));row['query']['commandId']='ios-'+uuid.uuid4().hex
        with d.files_owner() as owner,self.assertRaises(NativeUIError):owner.cleanup()
        self.assertTrue(d.f.f.h.path.exists());self.assertFalse(any(q['action']=='feature-ios-snapshot-file-remove' for q in d.commands))

    def test_expired_original_file_admission_remains_owned_without_retiming_or_sending_delete(self):
        d=self.captured()
        with d.files_owner() as owner:
            actual=owner.capture.slot;paused=False
            def delayed(label,kind):
                nonlocal paused
                if kind=='remove' and not paused:paused=True;d.sleep(1.6)
                return actual(label,kind)
            with patch.object(owner.capture,'slot',delayed),self.assertRaises(NativeUIError):owner.cleanup()
            stored=owner.capture.history('owned',owner.state['owned']);frame=deepcopy(stored.historical());reference=deepcopy(stored.state['storage'])
            path=stored.files().path(reference);identity=(path.stat().st_dev,path.stat().st_ino,path.read_bytes())
        with d.files_owner() as owner:
            with self.assertRaises(NativeUIError):owner.cleanup()
            self.assertEqual(frame,owner.capture.history('owned',owner.state['owned']).historical())
        self.assertEqual(identity,(path.stat().st_dev,path.stat().st_ino,path.read_bytes()))
        self.assertTrue(d.f.f.h.path.exists());self.assertFalse(any(q['action']=='feature-ios-snapshot-file-remove' for q in d.commands))


if __name__=='__main__':unittest.main()
