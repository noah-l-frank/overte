"""Canonical Assets factories and failure ownership; all native sources modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests.assets_reply_fixture import RUN,TICKET,URL
from ios.self_tests.assets_runtime_fixture import RuntimeBoundary


class AssetsRuntimeTests(unittest.TestCase):
    def setUp(self):self.b=RuntimeBoundary(self)
    def test_factories_keep_actual_candidate_existing_session_and_role_owned_stores(self):
        b=self.b;sessions,launches=b.f.sessions,b.f.launches;parts=b.components()
        self.assertEqual('42',parts['binding']['processIdentity'])
        self.assertEqual(b.f.adapter.fingerprint(),parts['binding']['targetFingerprint'])
        self.assertEqual(42,parts['files'].pid);self.assertEqual(42,parts['replies'].pid)
        for kind,name in (('files','owned_files'),('picker','picker'),('replies','owned_replies')):
            self.assertEqual(b.root/('ios-assets-'+RUN+'-primary-'+kind+'.json'),parts[name].store.path)
            self.assertIsNone(parts[name].store.read())
        self.assertNotEqual(b.runtime._assets_store('test-only',RUN,'primary','files').path,
            b.runtime._assets_store('test-only',RUN,'actor','files').path)
        self.assertEqual((sessions,launches),(b.f.sessions,b.f.launches));self.assertEqual([],b.asset_requests)

    def test_parsed_factory_keeps_existing_model_usage_and_backend_before_any_read(self):
        from ios.self_tests.assets_usage_backend_fixture import Fixture
        from pathlib import Path
        import tempfile
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);path=Path(temporary.name);path.chmod(0o700)
        fixture=Fixture(path);self.addCleanup(fixture.close)
        b=self.b;parts=b.runtime._assets_parsed_components('test-only',RUN,'primary',URL,b.lock,fixture.backend.config)
        self.assertIs(parts['usage'],parts['parsed'].model.usage);self.assertIs(parts['usage'],parts['baking'].usage)
        self.assertIs(parts['upload'],parts['baking'].backend.upload)
        self.assertEqual(b.root/('ios-assets-'+RUN+'-primary-parsed-sources.json'),parts['parsed_sources'].store.path)
        self.assertIsNone(parts['parsed'].state);self.assertIsNone(parts['parsed_sources'].state)
        self.assertEqual([],b.asset_requests);self.assertEqual([],b.afc);self.assertEqual([],fixture.requests)

    def test_independent_file_absence_and_server_bundle_flow_use_real_http_afc_factories(self):
        b=self.b;parts=b.components();packet=parts['files'].request('observe',RUN,TICKET,'a'*64,'gltf-bundle/main.gltf')
        self.assertEqual(dict(exists=False,files=[]),packet['source']['files'])
        result=b.readback();self.assertEqual({'main.gltf','mesh/triangle.bin','textures/checker.png'},
            {row['relativePath'] for row in result['files']})
        self.assertTrue(any(path.endswith('feature-ios-assets-files.json') for path in b.afc))
        self.assertTrue(any(path.endswith('feature-ios-assets-replies.json') for path in b.afc))
        self.assertNotIn('uploaded',result);self.assertNotIn('bakeState',result)
        restored=b.components()['owned_replies'];self.assertEqual('closed',restored.state['phase'])
        self.assertTrue(all(job['phase']=='retired' for job in restored.state['jobs']))
        self.assertEqual([],b.runtime.cleanup_errors)

    def test_removal_factory_keeps_existing_parsed_owner_without_any_native_input_or_read(self):
        from ios.self_tests.assets_usage_backend_fixture import Fixture
        from pathlib import Path
        import tempfile
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);path=Path(temporary.name);path.chmod(0o700)
        fixture=Fixture(path);self.addCleanup(fixture.close)
        b=self.b;parts=b.runtime._assets_model_removal_components('test-only',RUN,'primary',URL,b.lock,fixture.backend.config)
        self.assertIs(parts['parsed'],parts['model_removal'].parsed);self.assertIs(parts['usage'],parts['model_removal'].usage)
        self.assertEqual(b.root/('ios-assets-'+RUN+'-primary-model-removal.json'),parts['model_removal'].store.path)
        self.assertIsNone(parts['model_removal'].state);self.assertEqual([],b.asset_requests);self.assertEqual([],b.afc);self.assertEqual([],fixture.requests)

    def test_baked_tree_factory_keeps_existing_parsed_backend_without_any_input_or_read(self):
        from ios.self_tests.assets_usage_backend_fixture import Fixture
        from pathlib import Path
        import tempfile
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);path=Path(temporary.name);path.chmod(0o700)
        fixture=Fixture(path);self.addCleanup(fixture.close)
        b=self.b;parts=b.runtime._assets_baked_tree_components('test-only',RUN,'primary',URL,b.lock,fixture.backend.config)
        self.assertIs(parts['parsed'],parts['baked_tree'].parsed);self.assertIs(parts['backend'],parts['baked_tree'].backend)
        self.assertEqual(b.root/('ios-assets-'+RUN+'-primary-baked-tree.json'),parts['baked_tree'].store.path)
        self.assertIsNone(parts['baked_tree'].state);self.assertEqual([],b.asset_requests);self.assertEqual([],b.afc);self.assertEqual([],fixture.requests)

    def test_changed_candidate_blocks_before_any_native_asset_read(self):
        b=self.b;parts=b.components();b.f.artifact.write_bytes(b'Changed independently pinned candidate')
        with self.assertRaises((ValueError,RuntimeError,NativeUIError)):
            parts['files'].request('observe',RUN,TICKET,'a'*64,'gltf-bundle/main.gltf')
        self.assertEqual([],b.asset_requests);self.assertEqual([],b.afc)

    def test_process_replacement_or_foreground_loss_cannot_reuse_a_factory(self):
        b=self.b;parts=b.components();process=deepcopy(b.f.process)
        for update in (dict(pid=43),dict(foreground=False)):
            b.f.process=dict(process,**update)
            with self.subTest(update=update),self.assertRaises((ValueError,RuntimeError,NativeUIError)):
                parts['replies'].guard()
            self.assertEqual([],b.asset_requests)
        b.f.process=process

    def test_candidate_changed_at_the_final_http_cut_prevents_delivery(self):
        b=self.b;parts=b.components();transport=parts['observer'];guard=transport.before_send
        def replaced():b.f.artifact.write_bytes(b'Changed after the initial source check');return guard()
        transport.before_send=replaced
        with self.assertRaises((ValueError,RuntimeError,NativeUIError)):
            parts['files'].request('observe',RUN,TICKET,'a'*64,'gltf-bundle/main.gltf')
        self.assertEqual([],b.asset_requests);self.assertEqual([],b.afc)

    def test_original_outer_budget_is_rechecked_after_candidate_work_before_http(self):
        b=self.b;guard=b.f.adapter._candidate_guard
        def delayed():
            result=guard();b.now+=21;return result
        with patch.object(b.f.adapter,'_candidate_guard',side_effect=delayed),self.assertRaises(NativeUIError):b.readback()
        self.assertEqual([],b.asset_requests)

    def test_refused_final_normal_input_guard_never_reaches_http(self):
        b=self.b;parts=b.components();parts['native'].assets_guard=lambda:False
        with self.assertRaises(NativeUIError):parts['native'].capture()
        self.assertEqual([],b.asset_requests)

    def test_unknown_start_is_not_resent_and_actual_read_lease_cleanup_preserves_primary_error(self):
        b=self.b;b.replies.lost='inventory'
        with self.assertRaises(NativeUIError) as caught:b.readback()
        self.assertIs(caught.exception,b.errors[0]);self.assertEqual([],b.runtime.cleanup_errors)
        self.assertEqual(1,sum(query['operation']=='inventory' for query in b.replies.requests))
        self.assertGreaterEqual(sum(query['operation']=='observe' for query in b.replies.requests),1)
        self.assertEqual('closed',b.components()['owned_replies'].state['phase'])

    def test_secondary_cleanup_failure_retains_exact_primary_error_and_durable_issued_job(self):
        b=self.b;b.replies.lost='inventory';b.replies.defer=True;b.observe_error=RuntimeError('Declared lost cleanup observation')
        with self.assertRaises(NativeUIError) as caught:b.readback()
        self.assertIs(caught.exception,b.errors[0]);self.assertEqual([b.observe_error],b.runtime.cleanup_errors)
        owner=b.components()['owned_replies'];self.assertEqual('open',owner.state['phase']);self.assertEqual('issued',owner.state['jobs'][0]['phase'])
        self.assertEqual(1,sum(query['operation']=='inventory' for query in b.replies.requests))
        self.assertFalse(any(query['operation']=='retire' for query in b.replies.requests))

    def test_lost_retirement_return_is_recovered_without_second_cancel(self):
        b=self.b;b.replies.lost='inventory';b.replies.defer=True
        b.after_lost_start=lambda:setattr(b.replies,'lost','retire')
        with self.assertRaises(NativeUIError) as caught:b.readback()
        self.assertIs(caught.exception,b.errors[0]);self.assertEqual(1,len(b.runtime.cleanup_errors))
        owner=b.components()['owned_replies'];self.assertEqual('retiring',owner.state['jobs'][0]['phase'])
        owner.close();self.assertEqual('closed',owner.state['phase'])
        self.assertEqual(1,sum(query['operation']=='inventory' for query in b.replies.requests))
        self.assertEqual(1,sum(query['operation']=='retire' for query in b.replies.requests))


if __name__=='__main__':unittest.main()
