"""Actual canonical factories keep host brackets separate from native clocks.

Source producers are declared models instantiated before original acquisition;
neither retained samples nor native epochs are retimed as host timestamps.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fixture.serve import FixtureState
from ios.adapters import feature_observation,create_state,emote_world,assets_model_origin
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.self_tests import assets_scene_sources_fixture as scene_fixture
from ios.self_tests import test_ios_create_state as create
from ios.self_tests.assets_runtime_fixture import RuntimeBoundary
from ios.self_tests.assets_reply_fixture import RUN,URL


class AssetsHostClockTests(unittest.TestCase):
    def test_model_and_parsed_factories_use_actual_host_callback_without_native_host_timer_queries(self):
        from ios.self_tests.assets_usage_backend_fixture import Fixture
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        backend=Fixture(root);self.addCleanup(backend.close);b=RuntimeBoundary(self);host=lambda:1900000000123
        b.runtime=IOSAssetsRuntime(b.f.adapter,monotonic=lambda:b.now,epoch_ms=host)
        parts=b.runtime._assets_parsed_components('test-only',RUN,'primary',URL,b.lock,backend.backend.config)
        before=list(b.f.commands)
        self.assertIs(host,parts['model_sources'].epoch_ms);self.assertIs(host,parts['parsed_sources'].epoch_ms)
        self.assertEqual(1900000000123,parts['model_sources'].epoch_ms());self.assertEqual(1900000000123,parts['parsed_sources'].epoch_ms())
        self.assertEqual(before,b.f.commands);self.assertEqual([],b.asset_requests);self.assertEqual([],b.afc);self.assertEqual([],backend.requests)

    def test_canonical_scene_capture_keeps_distant_host_and_native_originals_with_no_native_host_callback(self):
        self.enterContext(patch.object(create,'EPOCH',20000));self.enterContext(patch.object(scene_fixture,'EPOCH',20000))
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        model=scene_fixture.Fixture(root);self.addCleanup(model.close);b=RuntimeBoundary(self)
        b.runtime=IOSAssetsRuntime(b.f.adapter,monotonic=model.monotonic,epoch_ms=model.epoch)
        def native(value):b.replies.elapsed=model.now;b.native_clock(value)
        b.f.clock.mutate=native;post=feature_observation.post_request.side_effect
        kinds={create_state.ACTION:'state',emote_world.ACTION:'domain',assets_model_origin.ACTION:'origin'}
        def send(request,timeout):
            query=json.loads(request.data)
            if query['action'] not in kinds:return post(request,timeout)
            FixtureState().set_client_command(query);model.send(kinds[query['action']],query);raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=send));execute=b.client.execute;pulls=[]
        files={create_state.FILE:'state',emote_world.FILE:'domain',assets_model_origin.FILE:'origin'}
        def read(session,operation,values):
            if operation=='mobile: pullFile':
                name=values['remotePath'].rsplit('/',1)[-1]
                if name in files:
                    pulls.append(name);return base64.b64encode(model.raw[files[name]].encode()).decode()
            return execute(session,operation,values)
        b.client.execute=read;source=b.runtime._assets_scene_source('test-only',RUN,'actor-primary',b.lock)['scene']
        source.reserve();sample=source.capture(model.epoch());clock=sample['clockJoin']
        self.assertGreaterEqual(clock['hostBeforeEpochMs'],1900000000000);self.assertLess(clock['nativeBefore']['capturedEpochMs'],100000)
        self.assertGreaterEqual(clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']);self.assertEqual(4,len(pulls))
        self.assertEqual(['state','domain','origin','state'],[kind for kind,_query in model.queries])
        self.assertEqual(6,len(source.raws.refs));self.assertEqual('actor-primary',sample['role'])
