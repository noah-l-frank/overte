"""Fresh original normal Model and marker parents on one declared target."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from copy import deepcopy
import os
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_image_basis import marker_original,parsed_original
from ios.self_tests.assets_image_combined_fixture import Fixture,ParsedFixture


class AssetsImageCombinedParentsTests(unittest.TestCase):
    def test_fresh_fixture_selects_canonical_lock_before_any_original_owner_activity(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        fixture=ParsedFixture(root);self.addCleanup(fixture.close)
        self.assertEqual(root/'script-feature-sources.lock',fixture.lock.path)
        self.assertIs(fixture.lock,fixture.files.lock);self.assertIs(fixture.lock,fixture.picker.lock)
        self.assertIsNone(fixture.files.state);self.assertIsNone(fixture.picker.state)
        self.assertEqual([],fixture.boundary.inputs);self.assertFalse((root/'assets.lock').exists())

    def test_original_normal_model_and_marker_share_target_tree_run_and_clock_from_start(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        fixture=Fixture(self,root);marker=fixture.marker;prepared=marker.prepare()
        self.assertEqual(fixture.parsed.sources.binding,marker.scope.binding);self.assertEqual(fixture.parsed.sources.run,marker.run)
        self.assertEqual('42',marker.scope.binding['processIdentity'])
        original=marker_original(marker,marker.previous);self.assertEqual(prepared.state['admission']['marker']['id'],original['id'])
        self.assertEqual(fixture.proof,parsed_original(fixture.parsed,fixture.parsed.previous))
        before=marker.scope.frames[marker.scope.state['baseline']-1]['create']['source'];after=marker.scope.frames[-1]['create']['source']
        self.assertEqual({fixture.proof['entityId']},{row['id'] for row in before['entities']})
        self.assertEqual({fixture.proof['entityId'],original['id']},{row['id'] for row in after['entities']})
        self.assertEqual(fixture.f.boundary.entity_tree_instance,after['tree']['treeInstance'])
        self.assertEqual(fixture.f.boundary.native_clock.sample['sequence'],marker.scope.native.sequence)
        marker.cleanup();self.assertIn(fixture.proof['entityId'],fixture.f.boundary.entities)
        self.assertTrue(fixture.f.boundary.models[fixture.proof['entityId']].loaded)
        self.assertEqual(1,fixture.domain.io.actions.count('script-file.confirm'));self.assertEqual(1,fixture.domain.io.actions.count('scripts.stop.0'))

    def test_actual_owned_sampler_retains_raw_sources_png_and_replays_after_marker_cleanup(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        fixture=Fixture(self,root);fixture.marker.prepare();request='ios-'+'7'*32
        owner,source=fixture.sample(request);policy=source.regions();owner.capture(fixture.scope.ticket,1900000000000+fixture.f.boundary.elapsed)
        result=owner.qualify(policy)
        self.assertEqual(fixture.proof['entityId'],result['entityId']);self.assertEqual(fixture.proof['sha256'],result['bodySha256'])
        self.assertEqual('qualified',owner.state['phase']);self.assertTrue((root/owner.frame_owner.name).exists())
        self.assertTrue(owner.state['frameOwnership']['absence']['source']['retired']);self.assertGreater(len(owner.state['rawRefs']),6)
        self.assertEqual(1,sum(row['operation']=='read' for row in source.gpu.commands))
        fixture.marker.cleanup();before={path.name:(path.stat().st_ino,path.read_bytes()) for path in root.iterdir() if path.is_file()}
        native=deepcopy(fixture.f.boundary.native_clock.commands);inputs=deepcopy(fixture.f.boundary.inputs);http=deepcopy(fixture.f.requests);gpu=deepcopy(source.gpu.commands)
        with (patch.object(fixture.scope.native,'send',side_effect=AssertionError('historical native')),
                patch.object(fixture.f.boundary.clock_reader,'send',side_effect=AssertionError('historical parent native')),
                patch.object(fixture.f.boundary,'exchange',side_effect=AssertionError('historical input')),
                patch.object(fixture.f,'open',side_effect=AssertionError('historical HTTP')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('historical state write'))):
            restored,new=fixture.sample(request);self.assertEqual(result,restored.state['qualification']);self.assertIs(source,new);self.assertEqual(gpu,new.gpu.commands)
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in root.iterdir() if path.is_file()})
        self.assertEqual(native,fixture.f.boundary.native_clock.commands);self.assertEqual(inputs,fixture.f.boundary.inputs);self.assertEqual(http,fixture.f.requests)

    def test_lost_native_read_delivery_keeps_same_actual_gpu_child_and_is_never_recaptured(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        fixture=Fixture(self,root);fixture.marker.prepare();request='ios-'+'8'*32;owner,source=fixture.sample(request)
        send=source.gpu.send
        def lost(query):
            result=send(query)
            if query['operation']=='read':raise OSError('lost actual native image read return')
            return result
        source.gpu.send=lost
        with self.assertRaises(NativeUIError):owner.capture(fixture.scope.ticket,1900000000000+fixture.f.boundary.elapsed)
        self.assertTrue(owner.state['gpuStarted']);self.assertNotIn('capture',owner.state['originals'])
        source.gpu.send=send;restored,same=fixture.sample(request);self.assertIs(source,same)
        before=deepcopy(source.gpu.commands)
        with self.assertRaises(NativeUIError):restored.capture(fixture.scope.ticket,1900000000000+fixture.f.boundary.elapsed)
        with self.assertRaises(NativeUIError):restored.recover_completed_capture()
        self.assertEqual(before,source.gpu.commands)
        proof=restored.retire_runtime();self.assertTrue(proof['source']['retired']);self.assertFalse(proof['source']['present'])
        self.assertEqual(1,sum(row['operation']=='read' for row in source.gpu.commands))
        self.assertEqual('reading',restored.state['phase']);self.assertIsNone(restored.state['qualification'])
        self.assertTrue((root/restored.frame_owner.name).exists());fixture.marker.cleanup()

    def test_saved_complete_logical_original_recovers_lost_parent_return_without_native_queries(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        fixture=Fixture(self,root);fixture.marker.prepare();request='ios-'+'9'*32;owner,source=fixture.sample(request);policy=source.regions()
        intent=owner.frames.intent;failure=RuntimeError('lost complete image original adoption')
        def lost(kind,value):
            result=intent(kind,value)
            if value['phase']=='saved':raise failure
            return result
        owner.frames.intent=lost
        with self.assertRaises(RuntimeError) as caught:owner.capture(fixture.scope.ticket,1900000000000+fixture.f.boundary.elapsed)
        self.assertIs(failure,caught.exception);self.assertEqual('saved',owner.state['original']['phase']);self.assertEqual('reading',owner.state['phase'])
        native=deepcopy(fixture.f.boundary.native_clock.commands);gpu=deepcopy(source.gpu.commands)
        restored,same=fixture.sample(request);self.assertIs(source,same);restored.recover_completed_capture();result=restored.qualify(policy)
        self.assertEqual(fixture.proof['entityId'],result['entityId']);self.assertEqual(native,fixture.f.boundary.native_clock.commands);self.assertEqual(gpu,source.gpu.commands)
        self.assertEqual(1,sum(row['operation']=='read' for row in source.gpu.commands));fixture.marker.cleanup()

    def test_opened_raw_prefix_is_retained_with_closed_fd_and_cannot_be_recaptured_or_changed(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        fixture=Fixture(self,root);fixture.marker.prepare();request='ios-'+'a'*32;owner,source=fixture.sample(request)
        intent=owner.raws.store.intent
        def interrupted(kind,value):
            result=intent(kind,value)
            if value['phase']=='opened':raise RuntimeError('actual raw prefix write interrupted')
            return result
        owner.raws.store.intent=interrupted
        with self.assertRaises((NativeUIError,RuntimeError)):owner.capture(fixture.scope.ticket,1900000000000+fixture.f.boundary.elapsed)
        original=owner.raws.pending['original'];path=owner.raws.store.path(original);inode=path.stat().st_ino;raw=path.read_bytes()
        self.assertEqual(b'',raw);self.assertFalse(owner.state['gpuStarted']);self.assertEqual([],source.gpu.commands)
        if Path('/proc/self/fd').is_dir():
            for descriptor in Path('/proc/self/fd').iterdir():
                try:target=os.readlink(descriptor)
                except OSError:continue
                self.assertNotEqual(str(path),target)
        restored,same=fixture.sample(request);self.assertIs(source,same);native=deepcopy(fixture.f.boundary.native_clock.commands)
        with self.assertRaises(NativeUIError):restored.capture(fixture.scope.ticket,1900000000000+fixture.f.boundary.elapsed)
        self.assertIsNone(restored.retire_runtime());self.assertEqual(native,fixture.f.boundary.native_clock.commands);self.assertEqual([],source.gpu.commands)
        try:
            path.write_bytes(b'changed actual prefix')
            with self.assertRaises(NativeUIError):fixture.sample(request)
        finally:path.write_bytes(raw)
        self.assertEqual(inode,path.stat().st_ino);self.assertEqual(raw,path.read_bytes());fixture.marker.cleanup()

    def test_changed_actual_png_raw_or_logical_original_never_becomes_a_qualified_image(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        fixture=Fixture(self,root);fixture.marker.prepare();request='ios-'+'b'*32;owner,source=fixture.sample(request);policy=source.regions()
        owner.capture(fixture.scope.ticket,1900000000000+fixture.f.boundary.elapsed)
        paths=[root/owner.frame_owner.name,owner.raws.store.path(owner.raws.store.expand(owner.state['rawRefs'][0])),owner.frames.path(owner.state['original'])]
        native=deepcopy(fixture.f.boundary.native_clock.commands);gpu=deepcopy(source.gpu.commands)
        for path in paths:
            original=path.read_bytes();inode=path.stat().st_ino
            try:
                path.write_bytes(b'{}')
                with self.subTest(path=path.name),self.assertRaises(NativeUIError):fixture.sample(request)
            finally:path.write_bytes(original)
            self.assertEqual(inode,path.stat().st_ino);self.assertEqual(original,path.read_bytes())
        self.assertEqual(native,fixture.f.boundary.native_clock.commands);self.assertEqual(gpu,source.gpu.commands)
        self.assertEqual(fixture.proof['entityId'],owner.qualify(policy)['entityId']);fixture.marker.cleanup()
