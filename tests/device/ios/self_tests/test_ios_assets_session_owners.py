"""Historical ownership and canonical refusal before SDK/session effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_session_owners import inspect_directory,owners_absent
from ios.self_tests import assets_picker_fixture as picker
from ios.self_tests import assets_reply_fixture as replies
from ios.self_tests import assets_upload_fixture as upload
from ios.self_tests.test_ios_installed_adapter import InstalledAdapterTests


def canonicalize(fixture,directory):
    for attribute,kind in (('file_store','files'),('picker_store','picker'),('reply_store','replies'),('upload_store','upload')):
        store=getattr(fixture,attribute,None)
        if store is not None:store.path=directory/('ios-assets-'+picker.RUN+'-primary-'+kind+'.json')


class AssetsSessionOwnersTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.path=Path(directory.name);self.path.chmod(0o700)
        self.adapter=SimpleNamespace(state_path=lambda _selector:self.path/'session.json')

    def fixture(self,kind=picker.Fixture):
        fixture=kind(self.path);self.addCleanup(fixture.close);canonicalize(fixture,self.path);return fixture

    def test_empty_inspection_is_read_only_and_does_not_create_a_source_lock(self):
        before=list(self.path.iterdir());self.assertEqual([],inspect_directory(self.path));self.assertTrue(owners_absent(self.adapter,'test-only'))
        self.assertEqual(before,list(self.path.iterdir()))

    def test_reserved_original_files_are_owned_before_any_native_mutation(self):
        fixture=self.fixture();fixture.files.reserve(picker.TICKET);before=deepcopy(fixture.boundary.requests)
        rows=inspect_directory(self.path);self.assertEqual(['input-files'],rows[0]['responsibilities']);self.assertFalse(owners_absent(self.adapter,'test-only'))
        self.assertEqual(before,fixture.boundary.requests);self.assertEqual('reserved',fixture.files.state['phase'])

    def test_negative_picker_retirement_is_decoded_without_reopening_native_sources(self):
        fixture=self.fixture();fixture.unavailable();fixture.picker.cancel();fixture.picker.close_page();fixture.picker.release()
        before=deepcopy(fixture.boundary.requests);inputs=deepcopy(fixture.boundary.inputs)
        rows=inspect_directory(self.path);self.assertEqual([],rows[0]['responsibilities']);self.assertFalse(rows[0]['successor'])
        self.assertTrue(owners_absent(self.adapter,'test-only'));self.assertEqual(before,fixture.boundary.requests);self.assertEqual(inputs,fixture.boundary.inputs)

    def reply_owner(self):
        fixture=replies.Fixture(self.path);self.addCleanup(fixture.close)
        path=self.path/('ios-assets-'+replies.RUN+'-primary-replies.json');fixture.store.path.rename(path);fixture.store.path=path
        fixture.owner.read('historical');fixture.owner.close();return fixture

    def test_closed_independent_reads_are_historical_without_adopting_server_data(self):
        fixture=self.reply_owner();before=deepcopy(fixture.boundary.requests);data=deepcopy(fixture.boundary.data)
        rows=inspect_directory(self.path);self.assertEqual([],rows[0]['responsibilities']);self.assertTrue(owners_absent(self.adapter,'test-only'))
        self.assertEqual(before,fixture.boundary.requests);self.assertEqual(data,fixture.boundary.data)

    def test_upload_successor_covers_the_unchanged_picker_phase_and_exact_file_owner(self):
        fixture=self.fixture(upload.Fixture);fixture.start();owner=fixture.owner();owner.reserve();owner.capture()
        before=deepcopy(fixture.boundary.requests);clocks=len(fixture.boundary.native_clock.commands)
        rows=inspect_directory(self.path);self.assertTrue(rows[0]['successor']);self.assertFalse(rows[0]['clientRetired'])
        self.assertNotIn('picker',rows[0]['responsibilities']);self.assertIn('upload-client',rows[0]['responsibilities']);self.assertIn('server-retirement',rows[0]['responsibilities'])
        self.assertEqual('primary-chosen',fixture.picker.state['phase']);self.assertEqual(before,fixture.boundary.requests);self.assertEqual(clocks,len(fixture.boundary.native_clock.commands))
        value=fixture.upload_store.read();changed=dict(value,fileOwnerToken='f'*64);fixture.upload_store.write(changed,value)
        with self.assertRaises(NativeUIError):inspect_directory(self.path)
        self.assertEqual(clocks,len(fixture.boundary.native_clock.commands))

    def test_client_retired_upload_keeps_server_retirement_blocking_and_picker_phase_original(self):
        fixture=self.fixture(upload.Fixture);fixture.start();owner=fixture.owner();owner.reserve();owner.review();owner.destination();owner.start_upload();owner.uploaded();owner.cleanup()
        before=deepcopy(fixture.boundary.requests);clocks=len(fixture.boundary.native_clock.commands);data=deepcopy(fixture.boundary.reads.data)
        rows=inspect_directory(self.path);self.assertTrue(rows[0]['clientRetired']);self.assertEqual(['server-retirement'],rows[0]['responsibilities'])
        self.assertFalse(owners_absent(self.adapter,'test-only'));self.assertEqual('primary-chosen',fixture.picker.state['phase'])
        self.assertEqual(before,fixture.boundary.requests);self.assertEqual(clocks,len(fixture.boundary.native_clock.commands));self.assertEqual(data,fixture.boundary.reads.data)

    def test_orphan_original_or_unsupported_assets_owner_cannot_become_absence(self):
        path=self.path/('assets-upload-frame-sources-'+picker.RUN+'-primary-0001-'+'f'*64+'.json');path.write_bytes(b'orphan original');path.chmod(0o600)
        with self.assertRaises(NativeUIError):owners_absent(self.adapter,'test-only')
        path.unlink();PrivateFeatureState(self.path/'ios-assets-unknown.json').write({},None)
        with self.assertRaises(NativeUIError):owners_absent(self.adapter,'test-only')


class AssetsInstalledAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.f=InstalledAdapterTests('test_canonical_subclass_emits_identity_only_after_measured_bytes_and_clean_sources');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.adapter.describe('test-only')

    def test_unresolved_or_malformed_assets_blocks_describe_invoke_and_cleanup_before_sdk_effects(self):
        f=self.f;store=PrivateFeatureState(f.root/('ios-assets-'+picker.RUN+'-primary-upload.json'));store.write({'unknown-owned-upload':True},None)
        before=(f.sessions,f.launches,f.preflights,deepcopy(f.commands),deepcopy(f.process),f.adapter.read_session('test-only'))
        for action in (lambda:f.adapter.describe('test-only'),lambda:f.adapter.invoke('test-only','app.stop',{}),lambda:f.adapter.cleanup('test-only')):
            with self.assertRaises(NativeUIError):action()
            self.assertEqual(before,(f.sessions,f.launches,f.preflights,f.commands,f.process,f.adapter.read_session('test-only')))
        self.assertEqual({'unknown-owned-upload':True},store.read())

    def test_closed_read_only_ownership_preserves_existing_canonical_cleanup(self):
        f=self.f;fixture=replies.Fixture(f.root);self.addCleanup(fixture.close)
        path=f.root/('ios-assets-'+replies.RUN+'-primary-replies.json');fixture.store.path.rename(path);fixture.store.path=path;fixture.owner.close()
        before=deepcopy(fixture.boundary.requests);result=f.adapter.cleanup('test-only')
        self.assertEqual({'cleaned':True},result);self.assertIsNone(f.process);self.assertEqual(before,fixture.boundary.requests)
        self.assertIsNotNone(PrivateFeatureState(path).read())
