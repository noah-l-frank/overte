"""Bounded exact independent-reply originals; native/wire sources modeled."""
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
from adapters.script_feature.history import MAX_PACKED,pack,unpack
from feature_journeys.fixtures import pinned_resource
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_reply_fixture import Fixture,RUN,URL,BINDING


class AssetsReplyStorageTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.f=Fixture(self.path,'asset-stand.fbx');self.addCleanup(self.f.close);self.b=self.f.boundary;self.o=self.f.owner
        old=self.f.store.path;self.f.store.path=self.path/('ios-assets-'+RUN+'-primary-replies.json');old.rename(self.f.store.path)

    def restored(self,role='primary'):
        return OwnedAssetsReplyReads(self.b.native(),self.f.store,BINDING,RUN,URL,lock=self.f.lock,role=role)

    def legacy(self):
        self.o.read('original-inventory');previous=self.f.store.read();value=dict(iosAssetsReplyOwnerVersion=1,binding=BINDING,runId=RUN,fixtureUrl=URL,payload=pack([self.o.state]))
        self.f.store.write(value,previous)
        for path in self.o.sources.owned_paths():path.unlink()
        self.o=self.restored();return self.f.store.path.read_bytes(),self.f.store.path.stat()

    def test_actual_pinned_fbx_wire_bytes_and_all_read_lease_cleanup_fit_old_limits(self):
        proof=self.o.observe_bundle();raw=base64.b64decode(proof['files'][0]['body']['base64'],validate=True);self.assertEqual(pinned_resource('asset-stand.fbx'),raw);self.assertEqual(25196,len(raw))
        self.assertEqual(48*1024,MAX_PACKED);self.assertLess(len(self.f.store.path.read_bytes()),65536);self.assertNotIn('originals',unpack(self.f.store.read()['payload'])[0])
        before=deepcopy(self.b.data);self.o.close();requests=deepcopy(self.b.requests);rows=inspect_directory(self.path)
        self.assertEqual([],rows[0]['responsibilities']);self.assertEqual(requests,self.b.requests);self.assertEqual(before,self.b.data);self.assertEqual('closed',self.restored().state['phase'])

    def test_native_carrier_formatting_is_preserved_verbatim(self):
        self.o.native.original=lambda:json.dumps(self.b.packet,indent=4);self.o.read('inventory');record=self.o.sources.read_record(self.o.sources.refs[0])
        self.assertEqual(json.dumps(self.b.packet,indent=4),record['raw']);self.assertEqual(self.o.state,self.restored().state)

    def test_saved_original_before_parent_cas_recovers_without_repeating_start(self):
        save=self.o.sources.save_owner;failed=[False]
        def crash():
            save();pending=self.o.sources.pending
            if pending and pending['original'] and pending['original']['phase']=='saved' and not failed[0]:failed[0]=True;raise RuntimeError('modeled lost source adoption')
        self.o.sources.save_owner=crash
        with self.assertRaises(RuntimeError):self.o.read('uncertain')
        before=deepcopy(self.b.requests);restored=self.restored();packet=restored.recover_capture();self.assertEqual(before,self.b.requests)
        captured=deepcopy(packet['source']['job']['events']);restored.recover('uncertain');self.assertEqual(1,sum(query['operation']=='inventory' for query in self.b.requests))
        self.assertEqual(captured,restored.state['originals'][0]['packet']['source']['job']['events'])

    def test_opened_prefix_remains_owned_and_cannot_be_resent_or_declared_closed(self):
        intent=self.o.sources.store.intent
        def crash(kind,reference):
            intent(kind,reference)
            if reference['phase']=='opened':
                with self.o.sources.store.path(reference).open('ab') as stream:stream.write(b'{"retained-prefix":');stream.flush();os.fsync(stream.fileno())
                raise RuntimeError('modeled source interruption')
            return True
        self.o.sources.store.intent=crash
        with self.assertRaises(RuntimeError):self.o.read('uncertain')
        before=deepcopy(self.b.requests);restored=self.restored();self.assertEqual(len(b'{"retained-prefix":'),restored.sources.pending['snapshot']['bytes'])
        for invoke in (restored.recover_capture,restored.close,lambda:restored.recover('uncertain')):
            with self.assertRaises(NativeUIError):invoke()
        self.assertEqual(before,self.b.requests);self.assertIn('read-source-write',inspect_directory(self.path)[0]['responsibilities'])

    def test_equal_bytes_replaced_reply_carrier_and_foreign_role_are_rejected(self):
        self.o.read('inventory')
        with self.assertRaises(NativeUIError):self.restored('actor')
        ref=self.o.sources.refs[0];path=self.o.sources.store.path(self.o.sources.store.expand(ref));raw=path.read_bytes();path.rename(self.path/'saved-reply-original');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.restored()

    def test_literal_v1_history_migrates_exact_old_wal_without_native_reads(self):
        raw,info=self.legacy();before=deepcopy(self.b.requests);self.o.save();record=self.o.sources.read_record(self.o.sources.refs[0])
        self.assertEqual(raw,base64.b64decode(record['rawBase64']));self.assertEqual(info.st_ino,record['identity']['inode']);self.assertEqual(before,self.b.requests)
        self.assertEqual(self.o.state,self.restored().state);self.restored().close();self.assertEqual([],inspect_directory(self.path)[0]['responsibilities'])

    def test_saved_migration_child_survives_failed_parent_cas_without_rewriting(self):
        raw,info=self.legacy();write=self.f.store.write
        def crash(value,previous):
            if value['iosAssetsReplyOwnerVersion']==2:raise RuntimeError('modeled parent CAS failure')
            return write(value,previous)
        with patch.object(self.f.store,'write',side_effect=crash),self.assertRaises(RuntimeError):self.o.save()
        self.assertEqual(raw,self.f.store.path.read_bytes());self.assertIn('read-source-write',inspect_directory(self.path)[0]['responsibilities'])
        files={path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.glob('assets-replies-*')};before=deepcopy(self.b.requests);self.restored().save()
        self.assertEqual(before,self.b.requests);self.assertEqual(files,{path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.glob('assets-replies-*')})

    def test_interrupted_migration_keeps_old_wal_and_exact_prefix_blocking(self):
        raw,info=self.legacy();intent=self.o.sources.store.intent
        def crash(kind,reference):
            intent(kind,reference)
            if reference['phase']=='opened':raise RuntimeError('modeled migration interruption')
            return True
        self.o.sources.store.intent=crash
        with self.assertRaises(RuntimeError):self.o.save()
        self.assertEqual(raw,self.f.store.path.read_bytes());before=deepcopy(self.b.requests);restored=self.restored()
        with self.assertRaises(NativeUIError):restored.save()
        self.assertEqual(before,self.b.requests);self.assertIn('read-source-write',inspect_directory(self.path)[0]['responsibilities'])

    def test_orphan_original_cannot_become_empty_read_lease_ownership(self):
        path=self.path/('assets-replies-native-frame-sources-'+RUN+'-primary-0001-'+'f'*64+'.json');path.write_bytes(b'orphan');path.chmod(0o600)
        with self.assertRaises(NativeUIError):inspect_directory(self.path)


if __name__=='__main__':unittest.main()
