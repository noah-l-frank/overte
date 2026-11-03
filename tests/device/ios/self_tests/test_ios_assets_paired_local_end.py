"""Fresh actual normal Assets graph and shared local end/CAS host integration.

SDK/native/process boundaries are declared models, never installed device or
whole Assets acceptance. Old byte/pool/GPU positive originals remain as-of
positive; only independent typed process/SDK end permits local metadata CAS.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest
import weakref
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_paired_end import completed_replay
from ios.self_tests.assets_paired_end_fixture import Fixture
from ios.self_tests.assets_picker_fixture import RUN,TICKET


class AssetsPairedLocalEndTests(unittest.TestCase):
    def test_normal_original_graph_server_restore_then_two_process_sdk_ends_and_file_only_replay(self):
        f=Fixture(self);f.freeze()
        cached=f.image.f.boundary.model_resource_cache
        self.assertTrue(cached);cached_originals={key:weakref.ref(value) for key,value in cached.items()};originals={str(p):(p.read_bytes(),p.stat().st_ino) for root in f.roots.values() for p in root.rglob('*')
            if p.is_file() and ('-frame-' in p.name or p.suffix=='.png')}
        result=f.complete();self.assertTrue(result['performed']);self.assertEqual(['actor','primary'],f.sdk.stops)
        self.assertEqual({'actor','primary'},f.sdk.deleted);self.assertEqual('complete',f.selected.state['phase'])
        for field in ('wholeAssetsComplete','byteDecoderRetirementProven','globalPoolRetirementProven','gpuRetirementProven'):self.assertIs(False,result[field])
        self.assertTrue(cached)  # The adapter did not evict a cache to manufacture native absence.
        self.assertEqual(set(cached_originals),set(cached))
        self.assertTrue(all(reference() is cached[key] for key,reference in cached_originals.items()))
        for name,(raw,inode) in originals.items():self.assertEqual((raw,inode),(Path(name).read_bytes(),Path(name).stat().st_ino))
        counts=f.counts()
        def forbidden(*args,**kwargs):raise AssertionError('Completed replay must use files only')
        with (patch('ios.adapters.appium_adapter.WebDriver',side_effect=forbidden),patch.object(f.sdk.runtime,'_existing',side_effect=forbidden),
              patch.object(PrivateFeatureState,'write',side_effect=forbidden),patch.object(PrivateFeatureState,'discard',side_effect=forbidden)):
            again=completed_replay(f.sdk.runtime,RUN,f.url,TICKET,f.roles,f.locks)
        self.assertEqual(result,again);self.assertTrue(counts==f.counts())

    def test_lost_actual_stop_reply_cold_owner_observes_independent_os_without_resend(self):
        f=Fixture(self,fault='lost-stop');f.freeze()
        with self.assertRaises(OSError):f.complete()
        self.assertEqual(['actor'],f.sdk.stops);self.assertEqual('stop-issued',f.tx.processes['actor'].state['phase'])
        f.reopen_end();result=f.complete()
        self.assertTrue(result['performed']);self.assertEqual(['actor','primary'],f.sdk.stops)
        self.assertEqual(1,sum(role=='actor' and operation=='mobile: terminateApp' for role,operation,*_ in f.sdk.calls))
        self.assertEqual('restored',f.image.f.normal_parts['backend'].state['phase']);self.assertTrue(f.image.f.boundary.model_resource_cache)

    def test_lost_actual_sdk_delete_cold_owner_uses_original_404_without_second_delete(self):
        f=Fixture(self,fault='lost-delete');f.freeze()
        with self.assertRaises(OSError):f.complete()
        self.assertEqual('delete-issued',f.tx.sessions['actor'].state['phase']);self.assertIn('actor',f.sdk.deleted)
        f.reopen_end();result=f.complete();self.assertTrue(result['performed'])
        self.assertEqual(1,sum(role=='actor' and operation=='DELETE' for role,operation,*_ in f.sdk.calls))
        self.assertEqual(['actor','primary'],f.sdk.stops);self.assertEqual({'actor','primary'},f.sdk.deleted)
        self.assertTrue(f.image.f.boundary.model_resource_cache)

    def test_new_unknown_actual_file_after_freeze_blocks_before_any_stop_or_sdk_delete(self):
        f=Fixture(self);f.freeze();path=f.roots['actor']/'unknown-live-server-responsibility.json'
        path.write_bytes(b'{"ownedBy":"foreign"}\n');path.chmod(0o600);before=f.counts();body=path.read_bytes();inode=path.stat().st_ino
        with self.assertRaises(NativeUIError):f.step_end()
        self.assertTrue(before==f.counts());self.assertEqual([],f.sdk.stops);self.assertEqual(set(),f.sdk.deleted)
        self.assertEqual((body,inode),(path.read_bytes(),path.stat().st_ino));self.assertTrue(f.image.f.boundary.model_resource_cache)

    def test_foreign_same_body_frozen_child_inode_blocks_before_any_stop_or_sdk_delete(self):
        f=Fixture(self);f.freeze();path=f.image.f.file_store.path;raw=path.read_bytes();old=path.stat()
        path.rename(path.with_name('retained-before-foreign-metadata-inode'));path.write_bytes(raw);path.chmod(0o600)
        self.assertNotEqual(old.st_ino,path.stat().st_ino);before=f.counts()
        with self.assertRaises(NativeUIError):f.step_end()
        self.assertTrue(before==f.counts());self.assertEqual([],f.sdk.stops);self.assertEqual(set(),f.sdk.deleted)
        self.assertTrue(all(p.read() is not None for p in f.selected.paths if p.path==path));self.assertTrue(f.image.f.boundary.model_resource_cache)


if __name__=='__main__':unittest.main()
