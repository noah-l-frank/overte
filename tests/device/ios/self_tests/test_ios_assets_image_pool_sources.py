"""Actual original/WAL durability counterexamples; native sources are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile,unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_image_pool_ownership import inspect_pool
from ios.self_tests.assets_image_pool_sources_fixture import Fixture


def files(root):
    return {p.name:(p.stat().st_dev,p.stat().st_ino,p.stat().st_mode,p.stat().st_size,
        p.stat().st_mtime_ns,p.stat().st_ctime_ns,p.read_bytes()) for p in root.iterdir() if p.is_file()}


class AssetsImagePoolSourcesTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='assets-image-pool-small-'));self.root.chmod(0o700)
        print('retained original root',self.root,flush=True)
        self.fixture=Fixture(self.root);self.addCleanup(self.fixture.close);self.owner=self.fixture.owner();self.owner.reserve()
    def test_actual_three_sources_and_reread_parent_originals_reload_without_queries_or_inode_changes(self):
        sample=self.owner.capture(self.fixture.boundary.clock());commands=self.fixture.commands();before=files(self.root)
        restored=self.fixture.owner();self.assertEqual(sample,restored._cached[-1]['sample'])
        self.assertEqual(commands,self.fixture.commands());self.assertEqual(before,files(self.root))
        records=[restored.raws.read_record(ref) for ref in restored.raws.refs]
        self.assertGreaterEqual(len(records),7) # Native bracket, Pool, Storage, parent and literal rereads.
        report=inspect_pool(self.root,list(self.root.iterdir()))
        self.assertEqual(['image-pool-resource-retirement'],report[0]['responsibilities'])
    def test_saved_frame_lost_adoption_recovers_exact_bytes_without_query_or_delete_replay(self):
        original=self.owner.originals.intent;failure=RuntimeError('saved storage adoption lost')
        def interrupted(kind,ref):
            result=original(kind,ref)
            if ref['phase']=='saved':raise failure
            return result
        self.owner.originals.intent=interrupted
        with self.assertRaises(RuntimeError) as caught:self.owner.capture(self.fixture.boundary.clock())
        self.assertIs(failure,caught.exception);commands=self.fixture.commands();restored=self.fixture.owner()
        sample=restored.recover_capture();self.assertEqual(1,sample['assetImagePoolSourceFrameVersion'])
        self.assertEqual(commands,self.fixture.commands());self.assertIsNone(restored.state['pending'])
    def test_opened_raw_prefix_and_query_intent_are_retained_and_block_reacquisition(self):
        original=self.owner.raws.store.intent
        def interrupted(kind,ref):
            result=original(kind,ref)
            if ref['phase']=='opened':raise RuntimeError('held raw original prefix')
            return result
        self.owner.raws.store.intent=interrupted
        with self.assertRaises(NativeUIError):self.owner.capture(self.fixture.boundary.clock())
        pending=deepcopy(self.owner.raws.pending);commands=self.fixture.commands();before=files(self.root)
        restored=self.fixture.owner()
        with self.assertRaises(NativeUIError):restored.capture(self.fixture.boundary.clock())
        with self.assertRaises(NativeUIError):restored.freeze_interrupted()
        self.assertEqual(pending,restored.raws.pending);self.assertEqual(commands,self.fixture.commands());self.assertEqual(before,files(self.root))
        report=inspect_pool(self.root,list(self.root.iterdir()))
        self.assertIn('image-pool-source-write',report[0]['responsibilities'])
    def test_unknown_pool_delivery_intent_is_durable_before_send_and_never_replayed(self):
        failure=RuntimeError('actual query transport outcome unknown')
        def failed_send(query):raise failure
        self.owner.readers['pool'].send=failed_send
        with self.assertRaises(NativeUIError):self.owner.capture(self.fixture.boundary.clock())
        self.assertEqual('pool',self.owner.state['pending']['queries'][-1]['kind'])
        commands=self.fixture.commands();restored=self.fixture.owner()
        with self.assertRaises(NativeUIError):restored.capture(self.fixture.boundary.clock())
        restored.freeze_interrupted();self.assertEqual(commands,self.fixture.commands())
        report=inspect_pool(self.root,list(self.root.iterdir()))
        self.assertIn('image-pool-source-write',report[0]['responsibilities'])
    def test_same_bytes_replaced_inode_and_current_guard_loss_refuse_previous_success(self):
        self.owner.capture(self.fixture.boundary.clock());commands=self.fixture.commands();self.fixture.boundary.live=False
        with self.assertRaises(NativeUIError):self.owner.capture(self.fixture.boundary.clock())
        self.assertEqual(commands,self.fixture.commands());self.fixture.boundary.live=True
        ref=self.owner.raws.refs[0];path=self.owner.raws.store.path(self.owner.raws.store.expand(ref))
        raw=path.read_bytes();path.rename(self.root/'retained-original');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.fixture.owner()
        self.assertEqual(commands,self.fixture.commands())

    def test_orphan_own_original_and_missing_inventory_path_never_become_a_clean_owner(self):
        self.owner.capture(self.fixture.boundary.clock());commands=self.fixture.commands()
        entries=list(self.root.iterdir());frame=self.owner.originals.expand(self.owner.state['frames'][0]);actual=self.owner.originals.path(frame)
        with self.assertRaises(NativeUIError):inspect_pool(self.root,[path for path in entries if path!=actual])
        orphan=self.root/('assets-image-pool-source-frame-sources-'+self.owner.run+'-primary-0032-'+'a'*64+'.json')
        orphan.write_bytes(actual.read_bytes());orphan.chmod(0o600)
        with self.assertRaises(NativeUIError):inspect_pool(self.root,list(self.root.iterdir()))
        self.assertEqual(commands,self.fixture.commands());self.assertTrue(orphan.exists())

    def test_exact_pool_paths_route_to_their_own_positive_session_inventory_without_image_context(self):
        from ios.adapters.assets_image_ownership import inventory_path
        from ios.adapters.assets_session_owners import inspect_directory
        self.owner.capture(self.fixture.boundary.clock());commands=self.fixture.commands();before=files(self.root)
        rows=inspect_directory(self.root)
        self.assertEqual(1,len(rows));self.assertEqual(['image-pool-resource-retirement'],rows[0]['responsibilities'])
        self.assertFalse(inventory_path(self.owner.store.path.name))
        for path in self.root.iterdir():
            if path.name.startswith('assets-image-pool-'):self.assertFalse(inventory_path(path.name))
        self.assertEqual(commands,self.fixture.commands());self.assertEqual(before,files(self.root))

    def test_real_image_and_marker_namespace_still_require_independent_image_context(self):
        from ios.adapters.assets_image_ownership import inventory_path
        from ios.adapters.assets_session_owners import inspect_directory
        for index,name in enumerate(('ios-assets-image-'+self.owner.run+'-primary-'+'a'*32+'.json',
                'ios-assets-marker-'+self.owner.run+'-primary.json')):
            # Separate actual private roots prevent the first negative from
            # masking the next one; every original fake file is retained.
            directory=self.root/('independent-context-negative-'+str(index));directory.mkdir(mode=0o700)
            self.assertTrue(inventory_path(name));path=directory/name;path.write_bytes(b'{}');path.chmod(0o600)
            before=files(directory);self.assertEqual(1,len(before))
            with self.subTest(name=name),self.assertRaises(NativeUIError):inspect_directory(directory)
            self.assertEqual(before,files(directory))

    def test_unknown_pool_lookalike_stays_blocking_in_both_namespace_handlers(self):
        from ios.adapters.assets_image_ownership import inventory_path
        from ios.adapters.assets_session_owners import inspect_directory
        name='ios-assets-image-pool-not-an-original.json';path=self.root/name
        path.write_bytes(b'{}');path.chmod(0o600);before=files(self.root);self.assertTrue(inventory_path(name))
        with self.assertRaises(NativeUIError):inspect_directory(self.root)
        with self.assertRaises(NativeUIError):inspect_pool(self.root,list(self.root.iterdir()))
        self.assertEqual(before,files(self.root))

    def test_syntactically_closed_orphan_pool_original_is_still_rejected_by_full_session(self):
        from ios.adapters.assets_image_ownership import inventory_path
        from ios.adapters.assets_session_owners import inspect_directory
        path=self.root/('assets-image-pool-source-frame-sources-'+self.owner.run+'-primary-0032-'+'a'*64+'.json')
        path.write_bytes(b'{}');path.chmod(0o600);before=files(self.root);self.assertFalse(inventory_path(path.name))
        with self.assertRaises(NativeUIError):inspect_directory(self.root)
        self.assertEqual(before,files(self.root))

    def test_component_image_namespace_can_exclude_only_exact_pool_names(self):
        from ios.adapters.assets_image_ownership import inventory_path
        from ios.adapters.assets_image_pool_ownership import pool_path
        good=('ios-assets-image-pool-'+self.owner.run+'.json',
            'assets-image-pool-native-frame-sources-'+self.owner.run+'-primary-0001-'+'a'*64+'.json')
        for name in good:self.assertTrue(pool_path(name));self.assertFalse(inventory_path(name))
        for name in (good[0]+'.bak',good[1].replace('-primary-','-actor-'),good[1].replace('-0001-','-1-')):
            self.assertFalse(pool_path(name));self.assertTrue(inventory_path(name))
