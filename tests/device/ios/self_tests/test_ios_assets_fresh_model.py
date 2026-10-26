"""One fresh upload/rebake/import/parser-body component; not full Assets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from feature_journeys.fixtures import pinned_resource
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_session_owners import inspect_directory
from ios.adapters.assets_usage_controls import project as usage_controls
from ios.self_tests.assets_fresh_model_fixture import Fixture,RUN


class AssetsFreshModelTests(unittest.TestCase):
    def test_fresh_unseeded_pinned_upload_rebake_actual_model_and_independent_parser_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary);path.chmod(0o700);fixture=Fixture(path)
            try:
                prefix='/e2e-'+RUN+'/';self.assertFalse(any(name.startswith(prefix) for name in fixture.boundary.reads.data));self.assertFalse(any(name.startswith(prefix) for name in fixture.backend.mappings))
                fixture.boundary.reads.resource='asset-stand.fbx';parts=fixture.parts()
                runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=fixture.boundary.monotonic)
                with patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    proof=runtime._assets_upload_model_bytes('test-only',RUN,'primary',fixture.files.url,'b'*32,fixture.lock,fixture.backend.config,parts=parts)
                self.assertIsNotNone(proof);self.assertEqual(1,fixture.boundary.host_state['uploads'])
                self.assertEqual(pinned_resource('asset-stand.fbx'),fixture.boundary.reads.data[prefix+'stand.fbx'])
                self.assertEqual('uploaded',parts['upload'].state['phase']);self.assertEqual('qualified',parts['baking'].state['phase'])
                off=[entry for entry in parts['usage'].state['inputs'] if entry['slot']=='usage-bake-off'];self.assertEqual(1,len(off))
                self.assertTrue(usage_controls(parts['usage'].packet(off[0]['before']),parts['upload'].state['page'])['baking']['checked'])
                admitted=parts['usage'].packet(parts['baking'].input()['before']);self.assertFalse(usage_controls(admitted,parts['upload'].state['page'])['baking']['checked'])
                self.assertEqual(1,len([event for event in fixture.boundary.host_state['bundleInfo']['serviceEvents'] if event['kind']=='baking-started' and event['enabled']]))
                self.assertEqual(1,len(fixture.implicit_jobs));self.assertNotEqual(fixture.implicit_jobs[0],parts['baking'].state['result']['proof']['jobId'])
                baseline=parts['backend'].packet(parts['baking'].row(parts['baking'].state['baseline']))
                self.assertIn(fixture.implicit_jobs[0],[row['id'] for row in baseline['source']['workAfter']['jobs']])
                self.assertEqual(parts['model'].state['creation']['proof']['entityId'],proof['entityId']);self.assertEqual('observed',parts['parsed'].state['phase'])
                self.assertEqual(parts['baking'].state['result']['proof']['outputHash'],proof['sha256']);self.assertGreater(proof['bytes'],25196)
                inputs=deepcopy(fixture.boundary.inputs);requests=deepcopy(fixture.requests);clocks=deepcopy(fixture.boundary.native_clock.commands)
                with patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    resumed=fixture.parts();again=runtime._assets_upload_model_bytes('test-only',RUN,'primary',fixture.files.url,'b'*32,fixture.lock,fixture.backend.config,parts=resumed)
                self.assertEqual(proof,again);self.assertEqual(inputs,fixture.boundary.inputs);self.assertEqual(requests,fixture.requests);self.assertEqual(clocks,fixture.boundary.native_clock.commands)
                responsibilities=inspect_directory(path)[0]['responsibilities'];self.assertIn('server-retirement',responsibilities);self.assertIn('parsed-resource-retirement',responsibilities)
                self.assertEqual('primary-chosen',fixture.picker.state['phase']);self.assertEqual([],runtime.cleanup_errors)
            finally:fixture.close()


class AssetsFreshStatusTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);path=Path(temporary.name);path.chmod(0o700)
        self.f=Fixture(path);self.addCleanup(self.f.close);self.source=self.f.backend
        self.path='/e2e-'+RUN+'/stand.fbx';self.digest=self.source.blob(pinned_resource('asset-stand.fbx'));self.source.mappings[self.path]=self.digest
        self.prefix='/.baked/'+self.digest+'/'

    def test_pending_disabled_alias_and_actual_output_follow_server_mapping_rules(self):
        self.assertEqual((2,''),self.f.get_status(self.path,self.digest))
        self.source.mappings[self.prefix+'asset.fbx']=self.digest
        self.assertEqual((1,''),self.f.get_status(self.path,self.digest))
        self.source.mappings[self.prefix+'asset.fbx']=self.source.blob(b'actual declared output')
        self.assertEqual((4,''),self.f.get_status(self.path,self.digest))
        self.f.pending_status[self.digest]=2;self.assertEqual((2,''),self.f.get_status(self.path,self.digest))
        self.f.pending_status[self.digest]=3;self.assertEqual((3,''),self.f.get_status(self.path,self.digest))

    def test_real_meta_error_redirect_and_irrelevant_types_do_not_invent_baking_availability(self):
        meta=dict(bake_version=1,failed_last_bake=True,last_bake_errors='actual declared failure',redirect_target='')
        self.source.mappings[self.prefix+'meta.json']=self.source.blob(json.dumps(meta).encode())
        self.assertEqual((5,'actual declared failure'),self.f.get_status(self.path,self.digest))
        self.assertEqual((0,''),self.f.get_status('/foreign.txt',self.digest))
        meta['redirect_target']=self.prefix+'redirect.fbx';self.source.mappings[self.prefix+'meta.json']=self.source.blob(json.dumps(meta).encode())
        self.source.mappings[meta['redirect_target']]=self.digest
        self.assertEqual((1,''),self.f.get_status(self.path,self.digest))
        self.source.mappings[meta['redirect_target']]=self.source.blob(b'actual redirected output')
        self.assertEqual((4,''),self.f.get_status(self.path,self.digest))


if __name__=='__main__':unittest.main()
