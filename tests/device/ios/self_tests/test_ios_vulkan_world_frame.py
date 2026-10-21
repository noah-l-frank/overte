"""Actual iOS HTTP/AFC framing for original world PNGs; synthetic GPU/SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation
from self_tests.test_native_vulkan_world_frame import World,request


class SDK(World):
    def __init__(self):
        super().__init__();self.fixture=FixtureState();self.pid=42;self.paths=[];self.drop=False
        self.target=dict(platform='ios',physical=True,appId='org.example.client',probe={'kind':'ios-documents'},
                        testBuild=dict(fixtureOrigin='http://controlled.invalid:49121',resultsDirectory='owned-results'))
    def post(self,message,timeout):
        assert message.full_url==self.target['testBuild']['fixtureOrigin']+'/e2e-client-command.json'
        value=self.fixture.set_client_command(json.loads(message.data));self.send(value);self.echo=json.dumps(value).encode()
        if self.drop:self.pid=43
        return self
    def __enter__(self):return self
    def __exit__(self,*_):return False
    status=200
    def read(self,limit):return self.echo[:limit]
    def process(self):return dict(bundleId=self.target['appId'],pid=self.pid,foreground=True)
    def execute(self,session,operation,values):
        assert session=='owned-session' and operation=='mobile: pullFile'
        assert values=={'remotePath':'@org.example.client:documents/owned-results/feature-vulkan-world-frame.json'}
        self.paths.append(values.copy());return base64.b64encode(self.original().encode()).decode()
    def observer(self):return feature_observation.FeatureObservation(self,'owned-session',self.target,self.process,
        epoch_ms=self.epoch,monotonic=lambda:self.clock,sleep=self.sleep)


class IOSWorldFrameTests(unittest.TestCase):
    def test_factory_acquires_actual_typed_original_png_chunks_through_existing_transport(self):
        b=SDK()
        with patch.object(feature_observation,'post_request',side_effect=b.post):
            reader=b.observer().vulkan_world_frame(b.intent);frame=reader.perform(request());raw=reader.image(frame)
            release=reader.perform(request('release','e'))
        self.assertEqual(b.png,raw);self.assertGreater(len(b.paths),3);self.assertEqual(b.commands,b.intents)
        self.assertEqual(0,release['source']['pngBytes']);self.assertEqual(0,release['source']['gpuBufferBytes'])
        self.assertGreater(frame['capturedEpochMs'],1700000000000+86400000)
        self.assertEqual('vulkan',frame['source']['backend']);self.assertEqual('tone-map-before-hud',frame['source']['stage'])

    def test_process_replacement_after_request_prevents_original_file_adoption(self):
        b=SDK();b.drop=True
        with patch.object(feature_observation,'post_request',side_effect=b.post),self.assertRaises(NativeUIError):
            b.observer().vulkan_world_frame(b.intent).perform(request())
        self.assertEqual([],b.paths);self.assertEqual(1,len(b.commands));self.assertEqual(b.commands,b.intents)


if __name__=='__main__':unittest.main()
