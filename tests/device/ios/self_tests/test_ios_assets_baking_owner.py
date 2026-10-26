"""Normal checkbox/backend causal joins; explicit native/server/oven models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from adapters.asset_backend_client import AssetsBackendClient
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from ios.adapters.assets_baking_owner import OwnedAssetsBaking
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_usage_backend_fixture import Fixture,RUN
from test_asset_backend_source import NativeWorkModel


class AssetsBakingOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.b=self.f.boundary
        for attribute,kind in (('file_store','files'),('picker_store','picker'),('upload_store','upload'),('reply_store','replies')):getattr(self.f,attribute).path=self.path/('ios-assets-'+RUN+'-primary-'+kind+'.json')
        self.usage=self.f.owned_existing_source();old=self.usage.store.path;self.usage.store.path=self.path/('ios-assets-'+RUN+'-primary-usage.json');old.rename(self.usage.store.path);self.usage.select()
        self.opener=patch('adapters.asset_backend_client.build_opener',return_value=self.f);self.opener.start();self.addCleanup(self.opener.stop)
        self.backend_store=PrivateFeatureState(self.path/('ios-assets-'+RUN+'-primary-backend.json'));self.store=PrivateFeatureState(self.path/('ios-assets-'+RUN+'-primary-baking.json'));self.o=self.owner(self.usage);self.o.reserve()

    def owner(self,usage):
        backend=OwnedAssetsBackend(usage.source,AssetsBackendClient(self.f.backend.config,usage.guard),self.backend_store,lock=self.f.lock)
        return OwnedAssetsBaking(usage,backend,self.store,lock=self.f.lock)

    def restored(self):return self.owner(OwnedAssetsUsage(self.f.owner(),self.usage.store,lock=self.f.lock))

    def test_normal_checkbox_and_new_original_run_join_current_meta_and_real_output_bytes(self):
        self.o.start();proof=self.o.qualify();self.assertIsNotNone(proof);self.assertEqual('qualified',self.o.state['phase'])
        self.assertEqual(self.usage.path(),proof['path']);self.assertNotEqual(proof['originalHash'],proof['outputHash']);self.assertGreater(proof['outputBytes'],25196)
        before=deepcopy(self.b.inputs);requests=deepcopy(self.f.requests);restored=self.restored();self.assertEqual(proof,restored.qualify());self.assertEqual(before,self.b.inputs);self.assertEqual(requests,self.f.requests)
        self.assertEqual('ready',restored.usage.source.state['phase']);self.assertEqual(0,self.b.host_state['uploads'])
        requests=deepcopy(self.f.requests);clocks=deepcopy(self.b.native_clock.commands);rows=inspect_directory(self.path)
        self.assertIn('server-retirement',rows[0]['responsibilities']);self.assertIn('usage-client',rows[0]['responsibilities']);self.assertNotIn('baking-actions',rows[0]['responsibilities'])
        self.assertEqual(requests,self.f.requests);self.assertEqual(clocks,self.b.native_clock.commands)

    def test_lost_checkbox_result_recovers_owned_input_without_resending_backend_mutation(self):
        self.b.configure(lost='assets.baking')
        with self.assertRaises(NativeUIError):self.o.start()
        self.assertEqual('issued',self.o.state['phase']);before=deepcopy(self.b.inputs);restored=self.restored();restored.recover();self.assertIsNotNone(restored.qualify());self.assertEqual(before,self.b.inputs)
        self.assertEqual(1,len([event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='baking-started']))

    def test_ui_callback_return_and_output_do_not_replace_pending_native_bodies(self):
        self.f.hold_bodies=True;self.o.start();self.assertIsNone(self.o.qualify());self.assertEqual('issued',self.o.state['phase'])
        before=deepcopy(self.b.inputs)
        for item in self.f.tasks.values():self.f.finish(item)
        self.assertIsNotNone(self.o.qualify());self.assertEqual(before,self.b.inputs)

    def test_ignored_checkbox_never_becomes_bake_from_existing_server_bytes(self):
        self.b.configure(ignore='assets.baking')
        with self.assertRaises(NativeUIError):self.o.start()
        self.assertFalse(self.f.tasks);before=deepcopy(self.b.inputs);restored=self.restored()
        with self.assertRaises(NativeUIError):restored.recover()
        with self.assertRaises(NativeUIError):restored.start()
        self.assertEqual(before,self.b.inputs);self.assertIsNone(restored.state['result'])

    def test_lost_checkbox_and_secondary_parent_save_keep_original_error_and_resume_once(self):
        self.b.configure(lost='assets.baking');write=self.store.write
        def fail_issued(value,previous):
            from adapters.script_feature.history import unpack
            if unpack(value['payload'])[0]['phase']=='issued':raise ValueError('modeled secondary parent failure')
            return write(value,previous)
        with patch.object(self.store,'write',side_effect=fail_issued),self.assertRaises(NativeUIError) as caught:self.o.start()
        self.assertIn('ValueError',caught.exception.__notes__[0]);before=deepcopy(self.b.inputs);restored=self.restored();self.assertEqual('baseline',restored.state['phase'])
        restored.recover();self.assertIsNotNone(restored.qualify());self.assertEqual(before,self.b.inputs)

    def test_replaced_exact_ui_original_cannot_reuse_an_old_qualification(self):
        self.o.start();self.assertIsNotNone(self.o.qualify());index=self.o.input()['before'];source=self.usage.source
        path=source.originals.path(source.originals.expand(source.state['frames'][index-1]));raw=path.read_bytes();path.rename(self.path/'retained-input-original');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.o.qualify()

    def test_closed_runtime_factory_retains_exact_same_normal_source_and_backend_binding(self):
        runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.b.monotonic)
        parts=dict(upload=self.usage.source,usage=self.usage,check=self.usage.guard)
        with patch.object(runtime,'state_path',return_value=self.path/'session.json'):
            produced=runtime._assets_baking_components('test-only',RUN,'primary',self.f.files.url,self.f.lock,self.f.backend.config,parts=parts)
        self.assertIs(self.usage,produced['baking'].usage);self.assertIs(self.usage.source,produced['backend'].upload)
        self.assertEqual(self.o.previous,produced['baking'].previous);self.assertEqual([],self.f.requests)

    def test_busy_baseline_recovers_by_new_original_read_before_any_checkbox_delivery(self):
        task=NativeWorkModel('send');self.f.backend.work.add(task);body=task.enter();before=deepcopy(self.b.inputs)
        self.assertIsNone(self.o.start());self.assertEqual(before,self.b.inputs);self.assertEqual(1,len(self.o.state['admissions']))
        task.leave(body);task.expire('lease');self.o.start();self.assertIsNotNone(self.o.qualify())
        self.assertEqual(2,len(self.o.state['admissions']));self.assertEqual(1,len([event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='baking-started']))


if __name__=='__main__':unittest.main()
