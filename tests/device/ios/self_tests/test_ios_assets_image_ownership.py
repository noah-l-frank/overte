"""Closed image-only namespace admission; no SDK/current image or end verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_image_ownership import inspect_directory,ImageInventoryContext
from ios.adapters.assets_session_owners import inspect_directory as inspect_session
from ios.self_tests.test_ios_assets_image_sample import AssetsImageSampleFactoryTests
from ios.self_tests.assets_reply_fixture import RUN
from ios.self_tests.assets_image_combined_fixture import Fixture


class AssetsImageOwnershipAdmissionTests(unittest.TestCase):
    setUp=AssetsImageSampleFactoryTests.setUp
    def inspect(self,**changes):
        options=dict(directory=self.b.root,artifact_root=self.b.root,binding=self.parts['binding'],run=RUN,
            lock=self.b.lock,parsed=self.parts['parsed'],marker=self.marker);options.update(changes)
        return inspect_directory(**options)
    def test_empty_image_namespace_needs_independently_bound_parents_and_does_not_query_or_write(self):
        native=deepcopy(self.b.f.clock.commands)
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure ownership write')):
            report=self.inspect();self.assertEqual([],report['owners']);self.assertEqual(set(),report['paths'])
        self.assertEqual(native,self.b.f.clock.commands);self.assertEqual([],self.b.asset_requests)
    def test_orphan_raw_or_logical_original_cannot_become_empty_image_ownership(self):
        for namespace in ('native','source'):
            path=self.b.root/('assets-image-'+namespace+'-frame-sources-'+RUN+'-primary-0001-'+'f'*64+'.json')
            path.write_bytes(b'{}');path.chmod(0o600);before=(path.stat().st_ino,path.read_bytes())
            with self.subTest(namespace=namespace),self.assertRaises(NativeUIError):self.inspect()
            self.assertEqual(before,(path.stat().st_ino,path.read_bytes()));path.unlink()
    def test_unknown_owner_profile_or_foreign_role_is_never_ignored(self):
        for name in ('ios-assets-image-'+RUN+'-actor-'+'a'*32+'.json','assets-image-native-migration-'+RUN+'-primary.json',
                'ios-assets-image-'+RUN+'-primary-'+'a'*32+'.json'):
            path=self.b.root/name;path.write_bytes(b'{}');path.chmod(0o600)
            with self.subTest(name=name),self.assertRaises(NativeUIError):self.inspect()
            path.unlink()
    def test_untrusted_root_binding_or_loose_parent_cannot_authorize_even_empty_inventory(self):
        binding=deepcopy(self.parts['binding']);binding['processIdentity']='43'
        for change in (dict(artifact_root=self.b.root/'untrusted'),dict(binding=binding),dict(parsed={}),dict(run='f'*32)):
            with self.subTest(change=next(iter(change))),self.assertRaises(NativeUIError):self.inspect(**change)

    def test_session_inventory_never_ignores_orphan_image_sources_without_explicit_context(self):
        path=self.b.root/('assets-image-native-frame-sources-'+RUN+'-primary-0001-'+'f'*64+'.json')
        path.write_bytes(b'{}');path.chmod(0o600)
        before=(path.stat().st_ino,path.read_bytes())
        with self.assertRaises(NativeUIError):inspect_session(self.b.root)
        self.assertEqual(before,(path.stat().st_ino,path.read_bytes()))


class AssetsImageOwnershipOriginalTests(unittest.TestCase):
    def test_explicit_session_context_covers_original_marker_image_and_retains_model_resource_responsibility(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        f=Fixture(self,root);f.marker.prepare();owner,source=f.sample('ios-'+'d'*32)
        owner.capture(f.scope.ticket,1900000000000+f.f.boundary.elapsed);owner.qualify(source.regions())
        authorization=ImageInventoryContext(root,deepcopy(f.scope.binding),RUN,f.scope.ticket,f.f.lock)
        # An active marker is still an independently outstanding child.
        with self.assertRaises(NativeUIError):inspect_session(root,image_context=authorization)
        owner.retire_runtime();f.marker.cleanup()
        before={path.name:(path.stat().st_ino,path.read_bytes()) for path in root.iterdir() if path.is_file()}
        native=deepcopy(f.f.boundary.native_clock.commands);gpu=deepcopy(source.gpu.commands)
        with (patch.object(f.scope.native,'send',side_effect=AssertionError('pure SDK')),
                patch.object(f.f.boundary.clock_reader,'send',side_effect=AssertionError('pure parent SDK')),
                patch.object(f.f,'open',side_effect=AssertionError('pure HTTP')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure write'))):
            with self.assertRaises(NativeUIError):inspect_session(root)
            rows=inspect_session(root,image_context=authorization)
            self.assertEqual(2,len(rows));self.assertIn('parsed-resource-retirement',rows[0]['responsibilities'])
            self.assertEqual(['marker-originals','image-originals'],rows[1]['responsibilities'])
            for change in (dict(artifact_root=root/'untrusted'),dict(initial_ticket='f'*32),dict(binding=dict(f.scope.binding,processIdentity='43'))):
                values=dict(artifact_root=root,binding=f.scope.binding,run=RUN,initial_ticket=f.scope.ticket,lock=f.f.lock);values.update(change)
                with self.subTest(change=next(iter(change))),self.assertRaises(NativeUIError):inspect_session(root,image_context=ImageInventoryContext(**values))
            orphan=root/('assets-marker-read-abandoned-'+RUN+'-primary-128.json')
            try:
                orphan.write_bytes(b'{}');orphan.chmod(0o600)
                with self.assertRaises(NativeUIError):inspect_session(root,image_context=authorization)
            finally:orphan.unlink()
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in root.iterdir() if path.is_file()})
        self.assertEqual(native,f.f.boundary.native_clock.commands);self.assertEqual(gpu,source.gpu.commands)

    def test_actual_sample_and_current_gpu_metadata_have_closed_pure_coverage_after_marker_cleanup(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        f=Fixture(self,root);f.marker.prepare();owner,source=f.sample('ios-'+'c'*32);policy=source.regions()
        owner.capture(f.scope.ticket,1900000000000+f.f.boundary.elapsed);qualified=owner.qualify(policy)
        owner.retire_runtime();f.marker.cleanup()
        def inspect(**changes):
            options=dict(directory=root,artifact_root=root,binding=f.scope.binding,run=RUN,lock=f.f.lock,parsed=f.parsed,marker=f.marker)
            options.update(changes);return inspect_directory(**options)
        before={path.name:(path.stat().st_ino,path.read_bytes()) for path in root.iterdir() if path.is_file()}
        native=deepcopy(f.f.boundary.native_clock.commands);gpu=deepcopy(source.gpu.commands)
        with (patch.object(f.scope.native,'send',side_effect=AssertionError('pure SDK')),
                patch.object(f.f.boundary.clock_reader,'send',side_effect=AssertionError('pure parent SDK')),
                patch.object(f.f,'open',side_effect=AssertionError('pure HTTP')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure write'))):
            report=inspect();self.assertEqual(['image-originals'],report['responsibilities']);self.assertEqual(1,len(report['owners']))
            saved=report['owners'][0];self.assertEqual(qualified,saved['owner'].state['qualification'])
            self.assertIn(root/owner.frame_owner.name,report['paths']);self.assertIn(owner.frame_owner.store.path,report['paths'])
            self.assertEqual({owner.store.path,owner.frame_owner.store.path,root/owner.frame_owner.name,owner.frames.path(owner.state['original'])}
                |owner.raws.owned_paths(),report['paths'])
            extra=root/('assets-image-native-frame-sources-'+RUN+'-primary-0001-'+'f'*64+'.json')
            try:
                extra.write_bytes(b'{}');extra.chmod(0o600)
                with self.assertRaises(NativeUIError):inspect()
            finally:extra.unlink()
            child=owner.frame_owner.store.path;held=child.with_name('retained-native-image-child.json');child.rename(held)
            try:
                with self.assertRaises(NativeUIError):inspect()
            finally:held.rename(child)
            with self.assertRaises(NativeUIError):inspect(artifact_root=root/'untrusted')
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in root.iterdir() if path.is_file()})
        self.assertEqual(native,f.f.boundary.native_clock.commands);self.assertEqual(gpu,source.gpu.commands)
