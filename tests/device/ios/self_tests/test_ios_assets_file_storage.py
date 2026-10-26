"""Real bounded source files with explicitly modeled native/Qt acquisition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as original_reads
from adapters.script_feature.history import MAX_PACKED,pack,unpack
from ios.adapters.assets_files import OwnedAssetsFiles
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_picker_fixture import Fixture,RUN,TICKET,URL,BINDING


class AssetsFileStorageTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700);self.f=Fixture(self.path);self.addCleanup(self.f.close)
        self.o=self.f.files;self.b=self.f.boundary
        self.f.file_store.path=self.path/('ios-assets-'+RUN+'-primary-files.json')

    def restored(self,role='primary'):
        return OwnedAssetsFiles(self.b.files_native(),self.f.file_store,BINDING,RUN,URL,lock=self.f.lock,role=role)

    def legacy(self,observed=False):
        self.o.reserve(TICKET)
        if observed:self.o.stage()
        previous=self.f.file_store.read();value=dict(iosAssetsFileOwnerVersion=1,runId=RUN,fixtureUrl=URL,binding=BINDING,payload=pack([self.o.state]))
        self.f.file_store.write(value,previous)
        # Explicit historical-format fixture: preserve the real modeled native
        # packets inline under their old grammar; v1 owns no external sources.
        for path in self.o.sources.owned_paths():path.unlink()
        self.o=self.restored();return self.f.file_store.path.read_bytes(),self.f.file_store.path.stat()

    def test_actual_pinned_fbx_stage_and_release_fit_unchanged_parent_limits(self):
        self.o.reserve(TICKET,'asset-stand.fbx');expected=base64.b64decode(next(iter(self.o.state['files'].values())))
        self.assertEqual(25196,len(expected));self.o.stage()
        self.assertEqual(expected,(self.b.root/'stand.fbx').read_bytes())
        self.assertEqual(48*1024,MAX_PACKED);self.assertLess(len(self.f.file_store.path.read_bytes()),65536)
        stored=unpack(self.f.file_store.read()['payload'])[0];self.assertNotIn('originals',stored);self.assertNotIn('files',stored)
        self.assertEqual(2,len(self.o.sources.refs));self.o.release();self.assertFalse(self.b.root.exists())
        self.assertEqual([],inspect_directory(self.path)[0]['responsibilities'])

    def test_raw_alternate_native_json_bytes_are_retained_without_reencoding(self):
        self.o.reserve(TICKET);native=self.o.native;native.original=lambda:json.dumps(self.b.packet,indent=3)
        self.o.stage();record=self.o.sources.read_record(self.o.sources.refs[-1])
        self.assertEqual(json.dumps(self.b.packet,indent=3),record['raw']);self.assertEqual(self.o.state,self.restored().state)

    def test_equal_bytes_replacement_original_inode_is_rejected(self):
        self.o.reserve(TICKET);self.o.stage();source=self.o.sources.store.path(self.o.sources.store.expand(self.o.sources.refs[0]));raw=source.read_bytes()
        source.rename(self.path/'retained-original');source.write_bytes(raw);source.chmod(0o600)
        with self.assertRaises(NativeUIError):self.restored()

    def test_input_manifest_tamper_and_role_mismatch_are_rejected(self):
        self.o.reserve(TICKET);value=deepcopy(self.f.file_store.read());state=unpack(value['payload'])[0];state['inputManifest'][0]['sha256']='0'*64;value['payload']=pack([state])
        with self.assertRaises(NativeUIError):self.o.decode(value)
        with self.assertRaises(NativeUIError):self.restored('actor')

    def test_saved_before_parent_adoption_recovers_without_native_resend(self):
        self.o.reserve(TICKET);original=self.o.sources.save_owner;failed=[False]
        def fail_after_saved():
            original()
            pending=self.o.sources.pending
            if pending and pending['original'] and pending['original']['phase']=='saved' and not failed[0]:failed[0]=True;raise RuntimeError('modeled crash after saved original')
        self.o.sources.save_owner=fail_after_saved
        with self.assertRaises(RuntimeError):self.o.stage()
        before=deepcopy(self.b.requests);restored=self.restored();restored.recover_capture()
        self.assertEqual(before,self.b.requests);restored.recover_stage()
        self.assertEqual(1,sum(row['operation']=='stage' for row in self.b.requests));self.assertEqual('staged',restored.state['phase'])

    def test_opened_actual_prefix_is_frozen_and_never_resent_or_retired(self):
        self.o.reserve(TICKET);original=self.o.sources.store.intent
        def interrupt(kind,reference):
            original(kind,reference)
            if reference['phase']=='opened':
                with self.o.sources.store.path(reference).open('ab') as stream:stream.write(b'{"actual-prefix":');stream.flush();os.fsync(stream.fileno())
                raise RuntimeError('modeled interrupted source writer')
            return True
        self.o.sources.store.intent=interrupt
        with self.assertRaises(RuntimeError):self.o.stage()
        before=deepcopy(self.b.requests);restored=self.restored();pending=restored.sources.pending
        self.assertEqual(len(b'{"actual-prefix":'),pending['snapshot']['bytes']);self.assertFalse(pending['snapshot']['complete'])
        with self.assertRaises(NativeUIError):restored.recover_capture()
        with self.assertRaises(NativeUIError):restored.observe()
        self.assertEqual(before,self.b.requests);self.assertIn('input-source-write',inspect_directory(self.path)[0]['responsibilities'])
        path=restored.sources.store.path(pending['original']);path.write_bytes(b'changed')
        with self.assertRaises(NativeUIError):self.restored()

    def test_secondary_prefix_save_failure_preserves_primary_and_blocking_owner(self):
        self.o.reserve(TICKET);original=self.o.sources.store.intent;primary=RuntimeError('original modeled source interruption')
        def interrupt(kind,reference):
            original(kind,reference)
            if reference['phase']=='opened':
                self.o.sources.save_owner=lambda:(_ for _ in ()).throw(ValueError('secondary WAL failure'))
                raise primary
            return True
        self.o.sources.store.intent=interrupt
        with self.assertRaises(RuntimeError) as caught:self.o.stage()
        self.assertIs(primary,caught.exception);self.assertIn('ValueError',primary.__notes__[0])
        before=deepcopy(self.b.requests);restored=self.restored()
        with self.assertRaises(NativeUIError):restored.recover_capture()
        self.assertEqual(before,self.b.requests);self.assertIn('input-source-write',inspect_directory(self.path)[0]['responsibilities'])

    def test_legacy_owner_remains_literal_until_exact_raw_migration(self):
        raw,info=self.legacy();before=deepcopy(self.b.requests);self.assertEqual(1,self.f.file_store.read()['iosAssetsFileOwnerVersion'])
        self.assertEqual(['input-files'],inspect_directory(self.path)[0]['responsibilities']);self.o.save()
        record=self.o.sources.read_record(self.o.sources.refs[0]);self.assertEqual(raw,base64.b64decode(record['rawBase64']));self.assertEqual(info.st_ino,record['identity']['inode'])
        self.assertEqual(before,self.b.requests);self.assertEqual(self.o.state,self.restored().state)
        with original_reads(fresh=True) as reads:inspect_directory(self.path)
        self.assertTrue(self.o.sources.owned_paths()<=reads)

    def test_saved_migration_child_survives_parent_cas_failure_without_rewrite(self):
        raw,info=self.legacy();original=self.f.file_store.write
        def fail_parent(value,previous):
            if value['iosAssetsFileOwnerVersion']==2:raise RuntimeError('modeled lost parent CAS')
            return original(value,previous)
        with patch.object(self.f.file_store,'write',side_effect=fail_parent),self.assertRaises(RuntimeError):self.o.save()
        self.assertEqual(raw,self.f.file_store.path.read_bytes());rows=inspect_directory(self.path);self.assertIn('input-source-write',rows[0]['responsibilities'])
        originals={path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.glob('assets-files-*')};before=deepcopy(self.b.requests)
        restored=self.restored();restored.save();self.assertEqual(before,self.b.requests)
        self.assertEqual(originals,{path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.glob('assets-files-*')})

    def test_observed_legacy_history_migrates_without_retiming_or_native_read(self):
        raw,info=self.legacy(observed=True);old=deepcopy(self.o.state);before=deepcopy(self.b.requests);self.b.elapsed+=5000
        self.o.save();restored=self.restored();self.assertEqual(old,restored.state);self.assertEqual(before,self.b.requests)
        record=restored.sources.read_record(restored.sources.refs[0]);self.assertEqual(raw,base64.b64decode(record['rawBase64']))
        restored.observe();self.assertEqual(len(before)+1,len(self.b.requests));self.assertEqual(3,len(restored.state['originals']))
        self.b.live=False
        with self.assertRaises(NativeUIError):restored.observe()
        self.assertEqual(len(before)+1,len(self.b.requests))

    def test_foreign_or_replaced_migration_journal_is_not_adopted(self):
        self.legacy();self.o.save();path=self.o.sources.migration_store.path;raw=path.read_bytes();path.rename(self.path/'saved-journal');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.restored()

    def test_incomplete_legacy_migration_preserves_exact_opened_prefix(self):
        raw,info=self.legacy();original=self.o.sources.store.intent
        def interrupt(kind,reference):
            original(kind,reference)
            if reference['phase']=='opened':raise RuntimeError('modeled interrupted migration writer')
            return True
        self.o.sources.store.intent=interrupt
        with self.assertRaises(RuntimeError):self.o.save()
        self.assertEqual(raw,self.f.file_store.path.read_bytes());journal=self.o.sources.migration_store.read()
        self.assertEqual(dict(bytes=0,sha256=__import__('hashlib').sha256(b'').hexdigest(),complete=False),journal['snapshot'])
        self.assertIn('input-source-write',inspect_directory(self.path)[0]['responsibilities'])
        before=deepcopy(self.b.requests);restored=self.restored()
        with self.assertRaises(NativeUIError):restored.save()
        self.assertEqual(before,self.b.requests);path=self.o.sources.store.path(journal['original']);path.write_bytes(b'changed')
        with self.assertRaises(NativeUIError):inspect_directory(self.path)

    def test_orphan_file_source_and_migration_cannot_look_absent(self):
        path=self.path/('assets-files-migration-'+RUN+'-primary.json');path.write_bytes(b'{}');path.chmod(0o600)
        with self.assertRaises(NativeUIError):inspect_directory(self.path)

    def test_live_weak_consumer_and_callback_block_fbx_release(self):
        self.o.reserve(TICKET,'asset-stand.fbx');self.o.stage();self.b.hold_consumer(pending=1)
        with self.assertRaises(NativeUIError):self.o.release()
        self.assertTrue(self.b.root.exists());self.assertFalse(any(row['operation']=='release' for row in self.b.requests))


if __name__=='__main__':unittest.main()
