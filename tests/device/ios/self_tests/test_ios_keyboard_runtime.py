"""Canonical existing installed session plus real HTTP/AFC keyboard codecs.

Native, installed-byte and SDK producers are explicit host models. This does
not compile UIKit or qualify an actual keyboard or device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation
from ios.adapters.keyboard_source import measured,FILE
from ios.self_tests import test_ios_keyboard_source as keyboard
from ios.self_tests.test_ios_script_runtime import IOSScriptRuntimeTests


class KeyboardRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=IOSScriptRuntimeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture.f;self.client=self.fixture.client;self.afc=[]
        self.enterContext(patch.object(keyboard,'EPOCH',20000));self.b=keyboard.Boundary();self.b.notify('did-hide',valid=False)
        self.original_post=feature_observation.post_request.side_effect;self.original_execute=self.client.execute
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=self.post))
        self.client.execute=self.execute;self.f.clock.mutate=self.native_clock
    def native_clock(self,packet):
        # A new independent clock producer snapshot; no saved packet is retimed.
        def fields(value):
            if type(value) is dict:
                for key,child in value.items():
                    if key.endswith('EpochMs'):value[key]=20000+self.b.time
                    else:fields(child)
            elif type(value) is list:
                for child in value:fields(child)
        fields(packet)
        packet['processId']=42
    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action']!='feature-ios-keyboard':return self.original_post(request,timeout)
        self.b.send(query);raw=json.dumps(query).encode()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,limit):return raw[:limit]
        return Response()
    def execute(self,session,operation,values):
        if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+FILE):
            self.afc.append(values['remotePath']);return base64.b64encode(self.b.raw.encode()).decode()
        return self.original_execute(session,operation,values)

    def test_existing_canonical_factory_reads_original_keyboard_and_independent_native_clocks(self):
        original=(self.f.sessions,self.f.launches);reader=self.f.adapter._keyboard_source('test-only')
        value=reader.read(keyboard.RUN);self.assertFalse(measured(value)['keyboard'])
        self.assertEqual(original,(self.f.sessions,self.f.launches));self.assertEqual(1,len(self.b.queries));self.assertEqual(1,len(self.afc))
        self.assertEqual('iosKeyboardAcquisitionVersion',next(key for key in reader.acquisition if key.endswith('Version')))
        self.assertGreaterEqual(value['clockBefore']['epochMs'],reader.acquisition['nativeRequestedEpochMs'])

    def test_changed_candidate_prevents_original_keyboard_transport_and_does_not_launch(self):
        reader=self.f.adapter._keyboard_source('test-only');original=(self.f.sessions,self.f.launches)
        self.f.artifact.write_bytes(b'Foreign candidate after source construction')
        with self.assertRaises(NativeUIError):reader.read(keyboard.RUN)
        self.assertEqual([],self.b.queries);self.assertEqual([],self.afc);self.assertEqual(original,(self.f.sessions,self.f.launches))

    def test_foreign_process_or_lost_foreground_cannot_reuse_original_keyboard_reader(self):
        for update in (dict(pid=43),dict(foreground=False)):
            with self.subTest(update=update):
                original=dict(self.f.process);reader=self.f.adapter._keyboard_source('test-only');self.f.process.update(update)
                with self.assertRaises(NativeUIError):reader.read(keyboard.RUN)
                self.f.process=original;self.assertEqual([],self.b.queries)


if __name__=='__main__':unittest.main()
