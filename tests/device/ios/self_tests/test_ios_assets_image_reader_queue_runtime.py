"""Canonical actual host methods/AFC with explicit SDK model; no native/device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import assets_image_reader as source1,assets_image_reader_queue as source,feature_observation
from ios.self_tests.assets_image_reader_queue_fixture import Boundary,Holder,RUN
from ios.self_tests import test_ios_keyboard_runtime as keyboard


class AssetsImageReaderQueueRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=keyboard.KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.b=Boundary(epoch=20000,initial_monotonic=20);self.task=self.b.create();self.gpu=Holder()
        self.b.invoke(self.task,self.gpu);self.b.finish(self.task);self.b.parent.deliver()
        self.afc=[];self.parent_afc=[]
        def native_clock(packet):self.k.b.time=self.b.time;self.k.native_clock(packet)
        self.f.clock.mutate=native_clock
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action'] not in (source.ACTION,source1.ACTION):return self.k.post(request,timeout)
            FixtureState().set_client_command(query)
            (self.b if query['action']==source.ACTION else self.b.parent).send(query)
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
                    self.afc.append(values['remotePath']);return base64.b64encode(self.b.raw.encode()).decode()
                if values['remotePath'].endswith('/'+source1.FILE):
                    self.parent_afc.append(values['remotePath']);return base64.b64encode(self.b.parent.raw.encode()).decode()
            return execute(session,operation,values)
        self.k.client.execute=read;self.sources=self.k.fixture.runtime._sources('test-only')

    def readers(self):
        observer=self.sources['observer'];clock=self.sources['clock_source']
        return observer.assets_image_reader_queue(clock_source=clock),observer.assets_image_reader(clock_source=clock)

    def test_factory_preserves_both_actual_afc_originals_clocks_and_existing_session(self):
        before=(self.f.sessions,self.f.launches);reader,parent=self.readers();packet=reader.read(RUN,source1=parent)
        self.assertEqual(before,(self.f.sessions,self.f.launches))
        self.assertEqual(1,len(self.afc));self.assertEqual(2,len(self.parent_afc))
        self.assertEqual(1,len(self.b.queries));self.assertEqual(1,len(self.b.parent.queries))
        self.assertEqual(parent.last,reader.parent_original);self.assertEqual(parent.acquisition,reader.parent_acquisition)
        self.assertLess(packet['clockAfter']['epochMs'],100000)
        self.assertTrue(reader.bound_facts['entries'][0]['argumentValuesDestroyed'])
        self.assertTrue(all(reader.bound_facts[key] is False for key in source.UNAVAILABLE))

    def test_changed_candidate_refuses_before_either_source_query_or_afc(self):
        reader,parent=self.readers();self.f.artifact.write_bytes(b'changed installed candidate')
        with self.assertRaises(NativeUIError):reader.read(RUN,source1=parent)
        self.assertEqual([],self.b.queries);self.assertEqual([],self.b.parent.queries)
        self.assertEqual([],self.afc);self.assertEqual([],self.parent_afc)

    def test_changed_pid_or_background_refuses_before_either_source_query_or_afc(self):
        for change in (dict(pid=43),dict(foreground=False)):
            reader,parent=self.readers();original=deepcopy(self.f.process);self.f.process.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):reader.read(RUN,source1=parent)
            self.f.process=original
            self.assertEqual([],self.b.queries);self.assertEqual([],self.b.parent.queries)
            self.assertEqual([],self.afc);self.assertEqual([],self.parent_afc)

    def test_matching_shape_from_foreign_actual_parent_original_is_refused(self):
        reader,parent=self.readers()
        self.b.parent.mutate=lambda packet:packet['source'].update(instance='b'*32)
        with self.assertRaises(NativeUIError):reader.read(RUN,source1=parent)
        self.assertEqual(1,len(self.b.queries));self.assertEqual(1,len(self.b.parent.queries))
        self.assertIsNone(reader.bound_facts)
