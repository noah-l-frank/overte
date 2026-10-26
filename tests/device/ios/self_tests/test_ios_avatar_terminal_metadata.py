"""Real metadata files on the declared modeled native/SDK terminal boundary.

No feature preparation, Scene, end or device result is claimed by these tests.
Loopback authority, Node owner startup and actual private Installed codecs run;
native/SDK/candidate services remain the existing explicit fixture models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.self_tests.avatar_terminal_domain import TerminalDomain
from self_tests import test_account_provider as tls


class AvatarTerminalMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def setUp(self):self.domain=TerminalDomain(self);self.base=self.domain.runtime.adapter
    def test_original_installed_bytes_and_inode_move_to_actual_canonical_slots_before_feature_admission(self):
        for role,admission in self.domain.metadata_admissions.items():
            with self.subTest(role=role):
                path=admission['installedPath'];self.assertEqual(self.base.state_path(role).with_name('installed-code-binding.json'),path)
                self.assertEqual(admission['installedOriginal'],(path.stat().st_dev,path.stat().st_ino,path.read_bytes()))
                self.assertFalse(admission['previousInstalledPath'].exists())
                self.assertEqual(path,self.base._binding_store(role).path)
                self.assertEqual(self.domain.natives[role].state,self.base.read_session(role))
                self.assertEqual('bound',self.domain.installed[role].make().record()['phase'])
    def test_actual_private_metadata_read_is_independent_and_has_no_in_memory_fallback_after_cas(self):
        role='primary';native=self.domain.natives[role];before=deepcopy(native.state);inputs=list(native.lifecycle_inputs)
        value=self.base.read_session(role);value['sessionId']='caller-mutated'
        self.assertEqual(before,self.base.read_session(role));store=PrivateFeatureState(self.base.state_path(role));store.discard(before)
        self.assertIsNone(self.base.read_session(role));self.assertEqual(before,native.state)
        with self.assertRaises(NativeUIError):self.base.save_session(role,before)
        self.assertIsNone(store.read());self.assertEqual(inputs,native.lifecycle_inputs)
    def test_actual_reset_removes_launch_flags_in_the_owned_file_without_process_or_sdk_input(self):
        role='actor';native=self.domain.natives[role];inputs=list(native.lifecycle_inputs)
        state=self.base.read_session(role);state.update(iosE2ELaunchCompleted=True,iosE2ESceneUrl='modeled-ordinary-scene')
        self.base.save_session(role,state);self.base.reset_launch_state(role,self.base.read_session(role))
        actual=self.base.read_session(role)
        self.assertTrue(all(key not in actual for key in ('processIdentity','iosE2ELaunchCompleted','iosE2ESceneUrl')))
        self.assertEqual({key:state[key] for key in ('sessionId','generation','targetFingerprint')},actual)
        self.assertEqual(actual,native.state);self.assertEqual(inputs,native.lifecycle_inputs)
    def test_frozen_installed_decoder_checks_candidate_bundle_and_foreign_scope_without_native_reads(self):
        role='primary';store=self.base._binding_store(role);record=store.read();path=store.path
        before=(path.stat().st_ino,path.read_bytes());inputs=list(self.domain.natives[role].lifecycle_inputs)
        self.assertEqual(record,self.base._avatar_retired_binding_record(role,record['scope'],record))
        changed=deepcopy(record);changed['observation']['bundle']['bundleSha256']='f'*64
        with self.assertRaises((NativeUIError,ValueError)):self.base._avatar_retired_binding_record(role,record['scope'],changed)
        with self.assertRaises((NativeUIError,ValueError)):
            self.base._avatar_retired_binding_record(role,dict(record['scope'],generation=2),record)
        self.assertEqual(before,(path.stat().st_ino,path.read_bytes()));self.assertEqual(inputs,self.domain.natives[role].lifecycle_inputs)


if __name__=='__main__':unittest.main()
