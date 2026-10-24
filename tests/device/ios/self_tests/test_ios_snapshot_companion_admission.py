"""Structural artifact and explicit native/SDK boundaries; no native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import plistlib
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_companion_owner import IOSSnapshotCompanionOwner,CompanionInspectionPending
from ios.adapters.snapshot_companion_artifact import artifact
from ios.adapters.bundle_identity import artifact_bundle
from ios.self_tests.snapshot_companion_domain import SnapshotCompanionDomain,RUN


class SnapshotCompanionAdmissionTests(unittest.TestCase):
    def pins(self,d):
        result={}
        for path in d.root.iterdir():
            if path.name.startswith('ios-snapshot-companion-frame-'):
                stat=path.stat();result[path.name]=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
        return result

    def test_existing_separate_driver_normal_nonce_inputs_actual_AFC_bytes_and_independent_native_clocks_admit(self):
        d=SnapshotCompanionDomain(self)
        with d.owner() as owner:
            result=owner.admit('d'*32);self.assertTrue(result['companionCodeVerified']);self.assertTrue(result['photosOutcomeRequired'])
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
            self.assertNotIn(b'PRIVATE-PROVISIONING-ACCOUNT-MODEL',store.path.read_bytes())
        before=self.pins(d);requests=deepcopy(d.requests);sdk=deepcopy(d.sdk)
        with lock.held():
            archived=IOSSnapshotCompanionOwner.archive(store,lock,binding,RUN,url,d.ipa);self.assertEqual(result,archived.result())
        self.assertEqual(before,self.pins(d));self.assertEqual(requests,d.requests);self.assertEqual(sdk,d.sdk);self.assertEqual(['clock','identity','clock'],d.clicks)

    def test_unknown_identity_return_reconstruction_pulls_original_without_second_native_click(self):
        d=SnapshotCompanionDomain(self);d.loss='identity'
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.admit('d'*32)
        d.loss=None
        with d.owner() as owner:self.assertTrue(owner.admit('d'*32)['companionCodeVerified'])
        self.assertEqual(1,d.clicks.count('identity'));self.assertEqual(3,len(d.nonces))

    def test_unknown_nonce_clear_and_write_returns_are_resolved_from_actual_field_without_resend(self):
        for fault in ('clear','value'):
            with self.subTest(fault=fault):
                d=SnapshotCompanionDomain(self);d.loss=fault
                with d.owner() as owner,self.assertRaises(NativeUIError):owner.admit('d'*32)
                d.loss=None
                with d.owner() as owner:self.assertTrue(owner.admit('d'*32)['companionCodeVerified'])
                self.assertEqual(3,sum(path.endswith('/clear') for method,path,_body in d.requests if method=='POST'))
                self.assertEqual(3,sum(path.endswith('/value') for method,path,_body in d.requests if method=='POST'))

    def test_ignored_actual_inspection_keeps_responsibility_and_never_replays_the_button(self):
        d=SnapshotCompanionDomain(self);d.ignore=True
        for _ in range(2):
            with d.owner() as owner,self.assertRaises((NativeUIError,OSError)):owner.admit('d'*32)
        self.assertEqual(['clock'],d.clicks)

    def test_selected_archive_and_original_installed_bytes_must_match_including_signature_and_provisioning(self):
        for name in ('photos-test','_CodeSignature/CodeResources','embedded.mobileprovision'):
            with self.subTest(file=name):
                d=SnapshotCompanionDomain(self);(d.installed/name).write_bytes(b'Changed actual installed bytes')
                with d.owner() as owner,self.assertRaises((NativeUIError,ValueError)):owner.admit('d'*32)
                self.assertEqual(['clock','identity'],d.clicks)

    def test_wrong_driver_bundle_is_rejected_before_any_companion_normal_input(self):
        d=SnapshotCompanionDomain(self);d.driver_bundle='org.example.overte'
        with self.assertRaises((NativeUIError,ValueError)):d.runtime()
        self.assertFalse(d.clicks);self.assertFalse(any(method=='POST' for method,_path,_body in d.requests))

    def test_mutated_or_replaced_selected_IPA_after_runtime_construction_blocks_every_normal_input(self):
        for fault in ('mutated','replaced'):
            with self.subTest(fault=fault):
                d=SnapshotCompanionDomain(self);runtime=d.runtime();raw=d.ipa.read_bytes()
                if fault=='mutated':d.ipa.write_bytes(raw+b'Changed selected archive bytes')
                else:
                    replacement=d.root/'replacement.ipa';replacement.write_bytes(raw);replacement.replace(d.ipa)
                with self.assertRaises((NativeUIError,ValueError,OSError)):
                    with runtime.owner(RUN,d.client()) as owner:owner.admit('d'*32)
                self.assertFalse(d.clicks);self.assertFalse(any(method=='POST' for method,_path,_body in d.requests))

    def test_added_actual_installed_file_cannot_reuse_the_selected_forest_identity(self):
        d=SnapshotCompanionDomain(self);(d.installed/'_CodeSignature'/'unexpected-resource').write_bytes(b'Unselected actual file')
        with d.owner() as owner,self.assertRaises((NativeUIError,ValueError)):owner.admit('d'*32)
        self.assertEqual(['clock','identity'],d.clicks)

    def test_changed_process_source_instance_PID_or_session_cannot_reconstruct_or_send_input(self):
        for fault in ('source','pid','session'):
            with self.subTest(fault=fault):
                d=SnapshotCompanionDomain(self);runtime=d.runtime()
                if fault=='source':d.source='1'*32
                elif fault=='pid':d.pid+=1
                else:
                    before=d.session.read();d.session.write(dict(before,generation=2),before)
                with self.assertRaises((NativeUIError,ValueError)):
                    with runtime.owner(RUN,d.client()):pass
                self.assertFalse(d.clicks)

    def test_foreign_native_PID_or_broken_native_clock_cannot_supply_admission(self):
        for fault in ('foreign','clock','native-birth'):
            with self.subTest(fault=fault):
                d=SnapshotCompanionDomain(self)
                if fault=='foreign':d.foreign=True
                elif fault=='clock':d.corrupt_clock=True
                else:d.replace_birth=True
                with d.owner() as owner,self.assertRaises((NativeUIError,ValueError)):owner.admit('d'*32)
                self.assertEqual(['clock','identity'] if fault=='native-birth' else ['clock'],d.clicks)

    def test_reconstruction_cannot_adopt_new_OS_source_birth_after_an_unknown_button_return(self):
        d=SnapshotCompanionDomain(self);d.loss='identity'
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.admit('d'*32)
        before=deepcopy(d.clicks);d.source='2'*32;d.loss=None
        with self.assertRaises((NativeUIError,ValueError)):
            with d.owner():pass
        self.assertEqual(before,d.clicks)

    def test_pending_actual_hash_never_supplies_code_admission(self):
        d=SnapshotCompanionDomain(self);d.pending=True
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.admit('d'*32)
        self.assertEqual(['clock','identity'],d.clicks)
        with d.owner() as owner:self.assertIsNone(owner.state['result'])

    def test_pending_hash_then_ready_recovery_retains_old_unqualified_group_and_uses_entirely_new_nonces(self):
        d=SnapshotCompanionDomain(self);d.pending=True
        with d.owner() as owner,self.assertRaises(CompanionInspectionPending):owner.admit('d'*32)
        old=self.pins(d);self.assertEqual(2,len(old));first_nonces=set(d.nonces);self.assertEqual(2,len(first_nonces))
        d.pending=False
        with d.owner() as owner,self.assertRaises(CompanionInspectionPending):owner.admit('d'*32)
        self.assertEqual(['clock','identity','clock'],d.clicks);closed=self.pins(d);self.assertEqual(3,len(closed))
        self.assertEqual(old,{name:closed[name] for name in old})
        with d.owner() as owner:
            self.assertTrue(owner.admit('d'*32)['companionCodeVerified']);self.assertEqual(6,len(owner.state['queries']))
            self.assertEqual('pending',owner.original(owner.state['queries'][1])['status'])
            self.assertTrue(first_nonces.isdisjoint({query['nonce'] for query in owner.state['queries'][3:]}))
        self.assertEqual(closed,{name:self.pins(d)[name] for name in closed});self.assertEqual(6,len(d.nonces))
        self.assertEqual(['clock','identity','clock','clock','identity','clock'],d.clicks)

    def test_saved_original_before_owner_CAS_reconstructs_exact_inode_bytes_without_repeating_input(self):
        d=SnapshotCompanionDomain(self)
        with d.owner() as owner:
            save=owner.save
            def lost():
                if owner.state['queries'] and owner.state['queries'][-1]['frame'] is not None:raise OSError('Explicit saved original before final owner CAS')
                return save()
            with patch.object(owner,'save',side_effect=lost),self.assertRaises(OSError):owner.admit('d'*32)
        before=self.pins(d);self.assertTrue(before)
        with d.owner() as owner:self.assertTrue(owner.admit('d'*32)['companionCodeVerified'])
        self.assertEqual(before,{name:self.pins(d)[name] for name in before});self.assertEqual(['clock','identity','clock'],d.clicks)

    def test_repeated_admission_queries_new_native_nonces_and_rejects_old_AFC_file(self):
        d=SnapshotCompanionDomain(self)
        with d.owner() as owner:owner.admit('d'*32)
        d.stale=True
        with d.owner() as owner,self.assertRaises((NativeUIError,ValueError)):owner.admit('d'*32)
        self.assertEqual(4,len(d.clicks));self.assertEqual(4,len(d.nonces))

    def test_foreign_original_frame_in_namespace_prevents_first_input(self):
        d=SnapshotCompanionDomain(self);path=d.root/'ios-snapshot-companion-frame-foreign.json';path.write_text('{}');path.chmod(0o600)
        with self.assertRaises((NativeUIError,ValueError)):
            with d.owner():pass
        self.assertFalse(d.clicks)


class SnapshotCompanionArtifactTests(unittest.TestCase):
    def test_product_artifact_reader_remains_closed_to_the_companion_and_wrong_companion_role_is_rejected(self):
        d=SnapshotCompanionDomain(self);value=artifact(d.ipa,d.scope['artifactSha256']);self.assertEqual('photos',value['role'])
        with self.assertRaises((NativeUIError,ValueError)):artifact_bundle(d.ipa,d.scope['artifactSha256'])
        files=deepcopy(d.files);info=plistlib.loads(files['Info.plist']);info['OVTSnapshotCompanionRole']='share-extension';files['Info.plist']=plistlib.dumps(info)
        d.write_archive(files)
        with self.assertRaises((NativeUIError,ValueError)):artifact(d.ipa,hashlib.sha256(d.ipa.read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
