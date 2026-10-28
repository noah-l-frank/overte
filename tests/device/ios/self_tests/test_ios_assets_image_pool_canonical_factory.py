"""Canonical existing SDK/HTTP/AFC and durable Pool owner, native modeled.

No allocator/Qt execution, byte/GPU retirement, normal input or whole Assets
qualification. This connects the existing selected source owner to runtime.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_image_pool_sources import AssetsImageReaderPoolSources
from ios.adapters.assets_image_pool_ownership import owned_prefix
from ios.adapters import assets_image_reader_pool as pool_source
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests import test_ios_assets_image_pool_runtime as existing
from ios.self_tests.assets_image_pool_fixture import RUN


def files(root):
    result={}
    for path in sorted(root.rglob('*')):
        info=path.lstat()
        if path.is_file() and owned_prefix(path.name):result[str(path.relative_to(root))]=(info.st_dev,info.st_ino,info.st_mode,info.st_size,
            info.st_mtime_ns,info.st_ctime_ns,path.read_bytes())
    return result


class AssetsImagePoolCanonicalFactoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=existing.AssetsImagePoolRuntimeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        # Select the existing declared producer clocks BEFORE factory/capture.
        # Feature readers and their containing original bracket share this
        # same fresh model host clock; no retained packet is edited/retimed.
        actual_init=existing.feature_observation.FeatureObservation.__init__;model=self.fixture.b
        def selected(observer,*args,**kwargs):
            kwargs['monotonic']=model.monotonic;kwargs['sleep']=model.sleep
            return actual_init(observer,*args,**kwargs)
        self.enterContext(patch.object(existing.feature_observation.FeatureObservation,'__init__',selected))
        self.runtime=IOSAssetsRuntime(self.fixture.f.adapter,monotonic=model.monotonic,epoch_ms=lambda:model.clock()+5000)
        self.root=self.fixture.f.root;self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.enterContext(self.lock.held())
    def factory(self):return self.runtime._assets_image_pool_source('test-only',RUN,self.lock)
    def commands(self):
        f=self.fixture
        return deepcopy((f.b.pool.queries,f.b.storage.queries,f.b.images.parent.queries,f.afc,f.storage_afc,f.parent_afc))
    def test_factory_binds_original_candidate_three_readers_and_actual_lock_without_reserve_or_query(self):
        f=self.fixture;before=(f.f.sessions,f.f.launches);parts=self.factory();owner=parts['image_pool_sources']
        self.assertIs(type(owner),AssetsImageReaderPoolSources);self.assertIs(owner.lock,self.lock)
        self.assertEqual(parts['binding'],owner.binding);self.assertEqual('42',owner.binding['processIdentity'])
        self.assertEqual(self.root/('ios-assets-image-pool-'+RUN+'.json'),owner.store.path)
        self.assertTrue(owner.native.native_clock_bound);self.assertEqual(42,owner.native.pid)
        self.assertEqual({'pool','storage','reader'},set(owner.readers))
        self.assertTrue(all(reader.pid==42 for reader in owner.readers.values()))
        self.assertIsNone(owner.state);self.assertIsNone(owner.store.read())
        self.assertEqual(([],[],[],[],[],[]),self.commands());self.assertEqual(before,(f.f.sessions,f.f.launches))
    def test_actual_canonical_capture_and_cold_original_reconstruction_preserve_pool_wal_without_pool_requery(self):
        f=self.fixture;before=(f.f.sessions,f.f.launches);owner=self.factory()['image_pool_sources'];owner.reserve()
        sample=owner.capture(self.runtime.epoch_ms());self.assertEqual(1,sample['assetImagePoolSourceFrameVersion'])
        self.assertEqual(1,len(f.b.pool.queries));self.assertEqual(1,len(f.b.storage.queries));self.assertEqual(1,len(f.b.images.parent.queries))
        self.assertEqual((1,2,2),(len(f.afc),len(f.storage_afc),len(f.parent_afc)))
        self.assertEqual(sample['originals']['pool'],owner.readers['pool'].last)
        self.assertEqual(sample['originals']['storage'],owner.readers['pool'].storage_original)
        self.assertEqual(sample['originals']['reader'],owner.readers['pool'].parent_original)
        for flag in pool_source.UNAVAILABLE:self.assertIs(False,owner.readers['pool'].bound_facts[flag])
        commands=self.commands();originals=files(self.root)
        write=PrivateFeatureState.write
        def writing(store,value,previous):
            if owned_prefix(store.path.name):raise AssertionError('Cold source factory attempted a Pool original/WAL write')
            return write(store,value,previous)
        # Existing _sources legitimately refreshes its installed binding.
        # The Pool source journal/carriers alone must remain read-only.
        with patch.object(PrivateFeatureState,'write',writing):
            reopened=self.factory()['image_pool_sources'];self.assertEqual(sample,reopened._cached[-1]['sample'])
            self.assertEqual(owner.state,reopened.state)
        self.assertEqual(commands,self.commands());self.assertEqual(originals,files(self.root))
        self.assertEqual(before,(f.f.sessions,f.f.launches))
        self.assertEqual(['image-pool-resource-retirement'],inspect_directory(self.root)[0]['responsibilities'])
    def test_changed_candidate_or_foreground_or_pid_refuses_reserved_owner_before_any_source_post_or_afc(self):
        f=self.fixture;owner=self.factory()['image_pool_sources'];owner.reserve();body=owner.store.path.read_bytes()
        initial=deepcopy(f.f.process)
        for update in (dict(foreground=False),dict(pid=43)):
            f.f.process=dict(initial,**update)
            with self.subTest(update=update),self.assertRaises((NativeUIError,ValueError,RuntimeError)):owner.capture(self.runtime.epoch_ms())
            self.assertEqual(([],[],[],[],[],[]),self.commands());self.assertEqual(body,owner.store.path.read_bytes())
        f.f.process=initial;f.f.artifact.write_bytes(b'Foreign candidate after original source factory')
        with self.assertRaises((NativeUIError,ValueError,RuntimeError)):owner.capture(self.runtime.epoch_ms())
        self.assertEqual(([],[],[],[],[],[]),self.commands());self.assertEqual(body,owner.store.path.read_bytes())
    def test_foreign_sdk_lock_refuses_before_owner_birth_or_source_query(self):
        other_root=self.root/'foreign-sdk';other_root.mkdir(mode=0o700)
        other=ScriptSourceLock(other_root/'script-feature-sources.lock')
        with other.held(),self.assertRaises(NativeUIError):self.runtime._assets_image_pool_source('test-only',RUN,other)
        self.assertFalse((self.root/('ios-assets-image-pool-'+RUN+'.json')).exists())
        self.assertEqual(([],[],[],[],[],[]),self.commands())
    def test_target_loss_after_durable_pool_intent_before_actual_http_cannot_deliver(self):
        f=self.fixture;owner=self.factory()['image_pool_sources'];owner.reserve()
        actual=owner.readers['pool'].send;attempted=[]
        def lost_target(query):
            attempted.append(deepcopy(query));f.f.process=dict(f.f.process,foreground=False)
            return actual(query)
        with patch.object(owner.readers['pool'],'send',side_effect=lost_target),self.assertRaises(NativeUIError):owner.capture(self.runtime.epoch_ms())
        self.assertEqual(1,len(attempted));self.assertEqual(([],[],[],[],[],[]),self.commands())
        self.assertIsNotNone(owner.state['pending']);self.assertEqual('pool',owner.state['pending']['queries'][-1]['kind'])
        saved=PrivateFeatureState(owner.store.path).read();self.assertIsNotNone(saved)

    def test_same_bytes_replaced_original_inode_cannot_be_adopted_by_canonical_reopen(self):
        owner=self.factory()['image_pool_sources'];owner.reserve();owner.capture(self.runtime.epoch_ms())
        commands=self.commands();wire=owner.raws.refs[0];path=owner.raws.store.path(owner.raws.store.expand(wire));raw=path.read_bytes()
        path.rename(self.root/'retained-original-before-inode-replacement');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.factory()
        self.assertEqual(commands,self.commands())
    def test_lost_pool_delivery_stays_durably_owned_across_canonical_reopen_without_resend(self):
        f=self.fixture;owner=self.factory()['image_pool_sources'];owner.reserve();actual=f.b.pool.send;delivered=[]
        def lost(query):
            delivered.append(deepcopy(query));actual(query)
            raise NativeUIError('Declared source delivery returned no original response')
        with patch.object(f.b.pool,'send',side_effect=lost),self.assertRaises(NativeUIError):owner.capture(self.runtime.epoch_ms())
        self.assertEqual(1,len(delivered));self.assertIsNotNone(owner.state['pending'])
        self.assertEqual('pool',owner.state['pending']['queries'][-1]['kind'])
        commands=self.commands();body=owner.store.path.read_bytes();originals=files(self.root)
        reopened=self.factory()['image_pool_sources']
        with self.assertRaises(NativeUIError):reopened.capture(self.runtime.epoch_ms())
        self.assertEqual(commands,self.commands());self.assertEqual(body,owner.store.path.read_bytes());self.assertEqual(originals,files(self.root))
        reports=inspect_directory(self.root)
        self.assertIn('image-pool-source-write',[item for row in reports for item in row['responsibilities']])


if __name__=='__main__':unittest.main()
