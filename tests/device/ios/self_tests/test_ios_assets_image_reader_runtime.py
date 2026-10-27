"""Canonical host AFC/candidate/native-clock route with an explicit SDK model.

No device, actual ImageReader, Qt pool, C++ exception or GPU is executed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import assets_image_reader as source,feature_observation
from ios.self_tests.assets_image_reader_fixture import Boundary,RUN
from ios.self_tests import test_ios_keyboard_runtime as keyboard


class AssetsImageReaderRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=keyboard.KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        # Select both clocks before this producer's first construction or read.
        self.b=Boundary(epoch=20000,initial_monotonic=20);self.task=self.b.create();self.afc=[]
        def native_clock(packet):self.k.b.time=self.b.time;self.k.native_clock(packet)
        self.f.clock.mutate=native_clock
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=source.ACTION:return self.k.post(request,timeout)
            FixtureState().set_client_command(query);self.b.send(query);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post));execute=self.k.client.execute
        def read(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+source.FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(self.b.raw.encode()).decode()
            return execute(session,operation,values)
        self.k.client.execute=read;self.sources=self.k.fixture.runtime._sources('test-only')
    def reader(self):return self.sources['observer'].assets_image_reader(clock_source=self.sources['clock_source'])

    def test_factory_preserves_actual_native_clock_afc_original_and_existing_session(self):
        before=(self.f.sessions,self.f.launches);reader=self.reader();packet=reader.read(RUN);facts=source.tasks(packet)
        self.assertEqual(before,(self.f.sessions,self.f.launches));self.assertEqual(1,len(self.afc));self.assertEqual(1,len(self.b.queries))
        self.assertEqual(self.task.id,facts['tasks'][0]['id']);self.assertLess(packet['clockAfter']['epochMs'],100000)
        self.assertEqual(packet,reader.last)
        for key in source.UNAVAILABLE:self.assertFalse(facts[key])

    def test_changed_candidate_refuses_before_dispatch_or_afc(self):
        reader=self.reader();self.f.artifact.write_bytes(b'changed installed candidate')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.b.queries);self.assertEqual([],self.afc)

    def test_changed_process_or_background_refuses_before_dispatch_or_afc(self):
        for change in (dict(pid=43),dict(foreground=False)):
            original=deepcopy(self.f.process);reader=self.reader();self.f.process.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):reader.read(RUN)
            self.f.process=original;self.assertEqual([],self.b.queries);self.assertEqual([],self.afc)
