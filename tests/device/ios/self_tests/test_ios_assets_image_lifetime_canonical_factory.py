"""Actual canonical four-owner assembly with declared HTTP/AFC SDK responses.

Existing host resource graph/weak objects, original source codecs and durable
journals execute. No Qt/C++ allocator, global pool, physical device, independent
peer, image resource-end or whole Assets qualification is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from fixture.serve import FixtureState
from ios.adapters import assets_image_reader_queue as queue_source,assets_image_reader_processing as processing_source
from ios.adapters import assets_image_reader_lifecycle_sources as lifecycle,assets_image_processing_sources as processing
from ios.adapters import assets_image_storage_sources as storage,assets_image_pool_sources as pool
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests import test_ios_assets_image_pool_canonical_factory as canonical
from ios.self_tests.assets_image_pool_fixture import RUN

OWNERS=(('image_lifecycle_sources',lifecycle.AssetsImageReaderLifecycleSources),
    ('image_processing_sources',processing.AssetsImageReaderProcessingSources),
    ('image_storage_sources',storage.AssetsImageReaderStorageSources),
    ('image_pool_sources',pool.AssetsImageReaderPoolSources))


class AssetsImageLifetimeCanonicalFactoryTests(unittest.TestCase):
    def setUp(self):
        # Existing fixture creates a real retained mkdtemp root and real owner
        # lock. Its declared SDK response model is selected before capture;
        # its normal InstalledBinding WAL refresh is intentionally permitted.
        canonical.AssetsImagePoolCanonicalFactoryTests.setUp(self)
        f=self.fixture;self.queue_afc=[];self.processing_afc=[]
        from ios.adapters import feature_observation
        previous_post=feature_observation.post_request.side_effect
        def post(request,timeout):
            query=json.loads(request.data)
            producer={queue_source.ACTION:f.b.images,processing_source.ACTION:f.b.processing}.get(query['action'])
            if producer is None:return previous_post(request,timeout)
            FixtureState().set_client_command(query);producer.send(query);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post))
        previous_execute=f.k.client.execute
        def execute(session,operation,values):
            if operation=='mobile: pullFile':
                for module,producer,reads in ((queue_source,f.b.images,self.queue_afc),(processing_source,f.b.processing,self.processing_afc)):
                    if values['remotePath'].endswith('/'+module.FILE):
                        reads.append(values['remotePath']);return base64.b64encode(producer.raw.encode()).decode()
            return previous_execute(session,operation,values)
        f.k.client.execute=execute
    def factory(self):return self.runtime._assets_image_lifetime_sources('test-only',RUN,self.lock)
    def commands(self):
        f=self.fixture
        return deepcopy((f.b.images.queries,f.b.processing.queries,f.b.storage.queries,f.b.pool.queries,f.b.images.parent.queries,
            self.queue_afc,self.processing_afc,f.storage_afc,f.afc,f.parent_afc))
    def no_source_io(self):self.assertTrue(all(not row for row in self.commands()))
    def test_canonical_four_owners_bind_actual_session_lock_and_independent_readers_without_query_or_reserve(self):
        f=self.fixture;before=(f.f.sessions,f.f.launches);parts=self.factory();parents=[];natives=[]
        for key,kind in OWNERS:
            owner=parts[key];self.assertIs(type(owner),kind);self.assertIs(owner.lock,self.lock)
            self.assertEqual(parts['binding'],owner.binding);self.assertEqual(RUN,owner.run);self.assertEqual('primary',owner.role)
            self.assertIsNone(owner.state);self.assertIsNone(owner.store.read());parents.append(owner.readers['reader']);natives.append(owner.native)
        self.assertEqual(4,len({id(v) for v in parents}));self.assertEqual(4,len({id(v) for v in natives}))
        self.assertIsNot(parts['image_storage_sources'].readers['storage'],parts['image_pool_sources'].readers['storage'])
        self.assertTrue(all(reader.last is None for reader in parents));self.no_source_io()
        self.assertEqual(before,(f.f.sessions,f.f.launches))
    def test_actual_four_captures_reopen_each_original_without_requery_or_rewinding_other_cursors(self):
        parts=self.factory();samples={}
        for key,_kind in OWNERS:
            owner=parts[key];owner.reserve();samples[key]=owner.capture(self.runtime.epoch_ms())
        previous_readers={key:(owner.native.sequence,deepcopy({name:reader.last for name,reader in owner.readers.items()}))
            for key,owner in ((key,parts[key]) for key,_ in OWNERS)}
        commands=self.commands();originals={str(path):path.read_bytes() for path in self.root.iterdir() if path.is_file() and path.name.startswith(('ios-assets-image-','assets-image-'))}
        actual_write=PrivateFeatureState.write
        def writing(store,value,previous):
            if store.path.name.startswith(('ios-assets-image-','assets-image-')):raise AssertionError('Cold assembly attempted an image-source journal write')
            return actual_write(store,value,previous)
        with patch.object(PrivateFeatureState,'write',writing):reopened=self.factory()
        for key,_kind in OWNERS:
            self.assertEqual(samples[key],reopened[key]._cached[-1]['sample']);self.assertEqual(parts[key].state,reopened[key].state)
            self.assertEqual(previous_readers[key],(parts[key].native.sequence,{name:reader.last for name,reader in parts[key].readers.items()}))
        self.assertEqual(commands,self.commands())
        self.assertEqual(originals,{str(path):path.read_bytes() for path in self.root.iterdir() if path.is_file() and path.name.startswith(('ios-assets-image-','assets-image-'))})
        responsibilities={item for row in inspect_directory(self.root) for item in row['responsibilities']}
        self.assertTrue({'image-reader-resource-retirement','image-processing-resource-retirement',
            'image-storage-resource-retirement','image-pool-resource-retirement'}<=responsibilities)
    def test_foreign_sdk_lock_refuses_before_any_image_owner_or_source_command(self):
        root=self.root/'foreign-sdk';root.mkdir(mode=0o700);foreign=ScriptSourceLock(root/'script-feature-sources.lock')
        with foreign.held(),self.assertRaises(NativeUIError):self.runtime._assets_image_lifetime_sources('test-only',RUN,foreign)
        self.no_source_io();self.assertFalse(any(path.name.startswith('ios-assets-image-') for path in self.root.iterdir()))
    def test_existing_foreign_run_responsibility_is_not_adopted_or_replaced(self):
        foreign='c'*32;owner=self.runtime._assets_image_pool_source('test-only',foreign,self.lock)['image_pool_sources'];owner.reserve()
        body=owner.store.path.read_bytes()
        with self.assertRaises(NativeUIError):self.factory()
        self.assertEqual(body,owner.store.path.read_bytes());self.no_source_io()
    def test_orphan_created_by_actual_first_constructor_is_refused_before_later_owners(self):
        entered=[];actual=lifecycle.AssetsImageReaderLifecycleSources.__init__
        def constructing(owner,*args,**kwargs):
            entered.append('lifecycle');actual(owner,*args,**kwargs)
            orphan=self.root/'assets-image-storage-unowned.json';orphan.write_bytes(b'{}');orphan.chmod(0o600)
        with patch.object(lifecycle.AssetsImageReaderLifecycleSources,'__init__',constructing),self.assertRaises(NativeUIError):self.factory()
        self.assertEqual(['lifecycle'],entered);self.no_source_io()
        self.assertFalse(any((self.root/('ios-assets-'+kind+'-'+RUN+'.json')).exists() for kind in ('image-processing','image-storage','image-pool')))
    def test_same_bytes_foreign_original_inode_refuses_whole_assembly_before_source_io(self):
        owner=self.factory()['image_pool_sources'];owner.reserve();owner.capture(self.runtime.epoch_ms());commands=self.commands()
        wire=owner.raws.refs[0];path=owner.raws.store.path(owner.raws.store.expand(wire));body=path.read_bytes()
        path.rename(self.root/'retained-prior-image-original');path.write_bytes(body);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.factory()
        self.assertEqual(commands,self.commands())
    def test_same_inode_changed_original_bytes_refuse_whole_assembly_before_source_io(self):
        owner=self.factory()['image_pool_sources'];owner.reserve();owner.capture(self.runtime.epoch_ms());commands=self.commands()
        wire=owner.raws.refs[0];path=owner.raws.store.path(owner.raws.store.expand(wire));before=path.stat()
        path.write_bytes(path.read_bytes()+b' ');self.assertEqual((before.st_dev,before.st_ino),(path.stat().st_dev,path.stat().st_ino))
        with self.assertRaises(NativeUIError):self.factory()
        self.assertEqual(commands,self.commands())


if __name__=='__main__':unittest.main()
