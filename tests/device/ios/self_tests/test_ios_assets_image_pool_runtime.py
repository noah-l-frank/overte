"""Canonical actual host methods/AFC with explicit SDK model; no native/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import assets_image_reader as source1,assets_image_reader_pool as source,assets_image_reader_storage as storage_source,feature_observation
from ios.self_tests.assets_image_pool_fixture import Boundary,RUN
from ios.self_tests import test_ios_keyboard_runtime as keyboard


class AssetsImagePoolRuntimeTests(unittest.TestCase):
    def setUp(self):
        class RetainedDirectory:
            def __init__(self):
                self.name=tempfile.mkdtemp(prefix='assets-image-pool-runtime-');Path(self.name).chmod(0o700)
                print('retained runtime root',self.name,flush=True)
            def cleanup(self):pass
        from ios.self_tests import test_ios_installed_adapter as installed_fixture
        self.enterContext(patch.object(installed_fixture,'tempfile',SimpleNamespace(TemporaryDirectory=RetainedDirectory)))
        self.k=keyboard.KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.b=Boundary(epoch=20000);self.addCleanup(self.b.release_product)
        self.afc=[];self.storage_afc=[];self.parent_afc=[]
        def native_clock(packet):self.k.b.time=self.b.elapsed;self.k.native_clock(packet)
        self.f.clock.mutate=native_clock
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action'] not in (source.ACTION,storage_source.ACTION,source1.ACTION):return self.k.post(request,timeout)
            FixtureState().set_client_command(query)
            (self.b.pool if query['action']==source.ACTION else self.b.storage if query['action']==storage_source.ACTION else self.b.images.parent).send(query)
            raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post));execute=self.k.client.execute
        def read(session,operation,values):
            if operation=='mobile: pullFile':
                if values['remotePath'].endswith('/'+source.FILE):
                    self.afc.append(values['remotePath']);return base64.b64encode(self.b.pool.raw.encode()).decode()
                if values['remotePath'].endswith('/'+storage_source.FILE):
                    self.storage_afc.append(values['remotePath']);return base64.b64encode(self.b.storage.raw.encode()).decode()
                if values['remotePath'].endswith('/'+source1.FILE):
                    self.parent_afc.append(values['remotePath']);return base64.b64encode(self.b.images.parent.raw.encode()).decode()
            return execute(session,operation,values)
        self.k.client.execute=read;self.sources=self.k.fixture.runtime._sources('test-only')

    def readers(self):
        observer=self.sources['observer'];clock=self.sources['clock_source']
        return observer.assets_image_reader_pool(clock_source=clock),observer.assets_image_reader_storage(clock_source=clock),observer.assets_image_reader(clock_source=clock)

    def test_factory_preserves_three_actual_afc_originals_clocks_and_existing_session(self):
        before=(self.f.sessions,self.f.launches);reader,storage,parent=self.readers();packet=reader.read(RUN,storage=storage,source1=parent)
        self.assertEqual(before,(self.f.sessions,self.f.launches))
        self.assertEqual(1,len(self.afc));self.assertEqual(2,len(self.storage_afc));self.assertEqual(2,len(self.parent_afc))
        self.assertEqual(1,len(self.b.pool.queries));self.assertEqual(1,len(self.b.storage.queries));self.assertEqual(1,len(self.b.images.parent.queries))
        self.assertEqual(parent.last,reader.parent_original);self.assertEqual(parent.acquisition,reader.parent_acquisition)
        self.assertLess(packet['clockAfter']['epochMs'],100000)
        self.assertIsNotNone(reader.storage_original['source']['allocations'][0]['allocationReturned'])
        self.assertIsNotNone(reader.storage_original['source']['allocations'][0]['sourceAttached'])
        self.assertTrue(reader.storage_original['source']['allocations'][0]['derivedMarkerAlive'])
        self.assertTrue(all(reader.bound_facts[key] is False for key in source.UNAVAILABLE))

    def test_changed_candidate_refuses_before_either_source_query_or_afc(self):
        reader,storage,parent=self.readers();self.f.artifact.write_bytes(b'changed installed candidate')
        with self.assertRaises(NativeUIError):reader.read(RUN,storage=storage,source1=parent)
        self.assertEqual([],self.b.pool.queries);self.assertEqual([],self.b.storage.queries);self.assertEqual([],self.b.images.parent.queries)
        self.assertEqual([],self.afc);self.assertEqual([],self.storage_afc);self.assertEqual([],self.parent_afc)

    def test_changed_pid_or_background_refuses_before_either_source_query_or_afc(self):
        for change in (dict(pid=43),dict(foreground=False)):
            reader,storage,parent=self.readers();original=deepcopy(self.f.process);self.f.process.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):reader.read(RUN,storage=storage,source1=parent)
            self.f.process=original
            self.assertEqual([],self.b.pool.queries);self.assertEqual([],self.b.storage.queries);self.assertEqual([],self.b.images.parent.queries)
            self.assertEqual([],self.afc);self.assertEqual([],self.storage_afc);self.assertEqual([],self.parent_afc)

    def test_matching_shape_from_foreign_actual_parent_original_is_refused(self):
        reader,storage,parent=self.readers()
        self.b.images.parent.mutate=lambda packet:packet['source'].update(instance='b'*32)
        with self.assertRaises(NativeUIError):reader.read(RUN,storage=storage,source1=parent)
        self.assertEqual(1,len(self.b.pool.queries));self.assertEqual(1,len(self.b.storage.queries));self.assertEqual(1,len(self.b.images.parent.queries))
        self.assertIsNone(reader.bound_facts)
