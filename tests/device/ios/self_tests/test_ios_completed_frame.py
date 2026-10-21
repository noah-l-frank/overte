"""iOS completed-frame HTTP/AFC original transport; GPU/SDK is synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from self_tests.test_native_completed_frame import Boundary,query
from fixture.serve import FixtureState
from ios.adapters import feature_observation
from adapters.normal_ui import NativeUIError


class SDK(Boundary):
    def __init__(self):
        super().__init__();self.pid=42;self.reads=[];self.drop_process=False;self.fixture=FixtureState()
        self.target=dict(platform='ios',physical=True,appId='org.example.client',probe={'kind':'ios-documents'},
            testBuild=dict(fixtureOrigin='http://controlled.invalid:49121',resultsDirectory='owned-results'))
    def process(self):return dict(bundleId=self.target['appId'],pid=self.pid,foreground=True)
    def post(self,request,timeout):
        command=self.fixture.set_client_command(json.loads(request.data));self.send(command);self.echo=json.dumps(command).encode()
        if self.drop_process:self.pid=43
        return self
    def __enter__(self):return self
    def __exit__(self,*_):return False
    status=200
    def read(self,limit):return self.echo[:limit]
    def execute(self,session,operation,values):
        assert session=='owned-session' and operation=='mobile: pullFile'
        assert values=={'remotePath':'@org.example.client:documents/owned-results/feature-completed-frame.json'}
        self.reads.append(deepcopy(values));return base64.b64encode(self.original().encode()).decode()
    def observer(self):return feature_observation.FeatureObservation(self,'owned-session',self.target,self.process,
        epoch_ms=self.epoch,monotonic=lambda:self.clock,sleep=self.sleep)


class IOSCompletedFrameTests(unittest.TestCase):
    def test_factory_keeps_native_fence_frame_originals_and_typed_private_afc_file(self):
        b=SDK()
        with patch.object(feature_observation,'post_request',side_effect=b.post):
            reader=b.observer().completed_frame(b.intent);value=reader.perform(query())
        self.assertEqual(b.value,value);self.assertEqual([query()],b.commands);self.assertEqual(b.commands,b.intents)
        self.assertGreaterEqual(len(b.reads),2);self.assertEqual(b.epoch(),value['capturedEpochMs'])
        self.assertEqual('vulkan',value['source']['backend']);self.assertNotIn('image',value['source'])

    def test_process_replacement_after_http_receipt_prevents_afc_adoption(self):
        b=SDK();b.drop_process=True
        with patch.object(feature_observation,'post_request',side_effect=b.post),self.assertRaises(NativeUIError):
            b.observer().completed_frame(b.intent).perform(query())
        self.assertEqual([query()],b.commands);self.assertEqual([],b.reads);self.assertEqual([query()],b.intents)


if __name__=='__main__':unittest.main()
