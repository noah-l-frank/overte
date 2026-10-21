"""Original Graphics inventory on iOS HTTP/AFC seams; no app/device execution."""
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
from ios.adapters import feature_observation
from self_tests.test_native_graphics_subject import Boundary,RUN
from adapters.normal_ui import NativeUIError


class IOSGraphicsSubjectTests(unittest.TestCase):
    def setUp(self):
        self.source=Boundary();self.source.source.update(subjectVersion=2,
            avatarPose=dict(feetPosition=[0,-.2,0],orientation=[0,0,0,1],modelScale=1.25))
        self.source.epoch=1700000000000+86400000
        self.target=dict(platform='ios',physical=True,appId='org.example.client',probe={'kind':'ios-documents'},
            testBuild=dict(fixtureOrigin='http://controlled.invalid:49121',resultsDirectory='owned-results'))
        self.reads=[];self.running=True
        self.observer=feature_observation.FeatureObservation(self,'owned-session',self.target,self.process,
            epoch_ms=lambda:self.source.epoch,monotonic=lambda:self.source.clock,sleep=self.source.sleep)
        boundary=patch.object(feature_observation,'post_request',side_effect=self.post)
        boundary.start();self.addCleanup(boundary.stop)

    def process(self):return dict(bundleId=self.target['appId'],pid=31,foreground=self.running)
    def post(self,request,timeout):
        command=json.loads(request.data);self.source.send(command);self.echo=json.dumps(command).encode();return self
    def __enter__(self):return self
    def __exit__(self,*_):return False
    status=200
    def read(self,limit):return self.echo[:limit]
    def execute(self,session,operation,values):
        self.assertEqual('owned-session',session);self.assertEqual('mobile: pullFile',operation)
        self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/feature-graphics-subject.json'},values)
        self.reads.append(deepcopy(values));return base64.b64encode(self.source.original().encode()).decode()

    def test_factory_retains_native_epoch_original_inventory_and_own_nonce(self):
        reader=self.observer.graphics_subject();value=reader.read(RUN,require_avatar=True)
        self.assertTrue(value['requestId'].startswith('ios-'));self.assertTrue(reader.clock_bound)
        self.assertEqual(self.source.epoch,value['capturedEpochMs'])
        self.assertEqual(self.source.source,value['source']);self.assertEqual(1,len(self.source.commands))
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(self.source.commands[0]))

    def test_stale_foreign_process_and_missing_original_cannot_produce_a_snapshot(self):
        for fault in ('stale','foreign','missing'):
            with self.subTest(fault=fault):
                reader=self.observer.graphics_subject()
                def edit(value):
                    if fault=='stale':value.update(requestedEpochMs=1000,capturedEpochMs=1000)
                    elif fault=='foreign':value['processId']=32
                    else:value.clear()
                self.source.edit=edit
                with self.assertRaises(NativeUIError):reader.read(RUN,require_avatar=True)
                self.assertIsNone(reader.last)
        self.assertEqual(3,len(self.source.commands))


if __name__=='__main__':unittest.main()
