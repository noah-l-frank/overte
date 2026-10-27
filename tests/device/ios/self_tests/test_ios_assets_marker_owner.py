"""Actual original marker child under a separate durable Assets parent intent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.self_tests.test_ios_assets_marker_scope import AssetsMarkerScopeTests
from ios.self_tests.assets_marker_scope_fixture import AssetsMarkerDomain


class AssetsMarkerParentCodecTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AssetsMarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.scope=self.fixture.scope;self.store=PrivateFeatureState(self.scope.store.path.with_name('ios-assets-marker-'+self.scope.run+'-'+self.scope.role+'.json'))
        self.owner=OwnedAssetsMarker(self.scope,self.store)
    def test_reserved_parent_binds_canonical_actual_child_root_and_no_native_input(self):
        self.owner.reserve();self.assertEqual('reserved',self.owner.state['phase']);self.assertIsNone(self.scope.store.read())
        self.assertEqual([],self.fixture.domain.io.actions);self.assertIsNone(self.scope.files.store.read())
        for key,value in (('childFile','unowned.json'),('artifactRoot','/unowned'),('role','actor')):
            bad=deepcopy(self.store.read());bad[key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.owner.decode(bad)
        bad=deepcopy(self.store.read());bad['artifactRootIdentity']['inode']+=1
        with self.assertRaises(NativeUIError):self.owner.decode(bad)
        bad=deepcopy(self.store.read());bad['payload']=pack([dict(phase='released',pending=None,child=None)])
        with self.assertRaises(NativeUIError):self.owner.decode(bad)
    def test_child_cannot_be_adopted_after_activity_preceding_parent_reservation(self):
        self.scope.save();before=(self.scope.store.path.stat().st_ino,self.scope.store.path.read_bytes())
        with self.assertRaises(NativeUIError):self.owner.reserve()
        self.assertIsNone(self.store.read());self.assertEqual(before,(self.scope.store.path.stat().st_ino,self.scope.store.path.read_bytes()))
        self.assertEqual([],self.fixture.domain.io.actions)
    def test_orphan_actual_marker_original_blocks_before_parent_reservation_or_mutation(self):
        path=self.scope.root/('assets-marker-frame-inputs-'+self.scope.run+'-'+self.scope.role+'-0001-'+'f'*64+'.json')
        path.write_bytes(b'{}');path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner.reserve()
        self.assertIsNone(self.store.read());self.assertIsNone(self.scope.store.read());self.assertEqual([],self.fixture.domain.io.actions)
    def test_child_change_without_saved_parent_intent_cannot_trigger_new_setup_or_cleanup(self):
        self.owner.reserve();self.scope.save();inputs=deepcopy(self.fixture.domain.io.actions)
        with self.assertRaises(NativeUIError):self.owner.prepare()
        with self.assertRaises(NativeUIError):self.owner.cleanup()
        self.assertEqual(inputs,self.fixture.domain.io.actions);self.assertEqual('reserved',self.owner.state['phase'])
    def test_pure_current_parent_archive_requires_explicit_binding_root_and_preserves_all_originals(self):
        self.owner.reserve();before={path.name:(path.stat().st_ino,path.read_bytes()) for path in self.scope.root.iterdir() if path.is_file()}
        def archived(value,**changes):
            options=dict(artifact_root=self.scope.root,binding=self.scope.binding,run=self.scope.run,role=self.scope.role,
                fixture_url=self.scope.fixture_url,ticket=self.scope.ticket,lock=self.scope.lock);options.update(changes)
            return OwnedAssetsMarker.from_archive(value,self.store,**options)
        with patch.object(self.scope,'guard',side_effect=AssertionError('pure archive SDK')):
            self.assertEqual(self.owner.state,archived(self.store.read()).state)
            with self.assertRaises(NativeUIError):archived(self.store.read(),artifact_root=self.scope.root/'untrusted')
            with self.assertRaises(NativeUIError):archived(self.store.read(),ticket='f'*32)
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in self.scope.root.iterdir() if path.is_file()})
    def test_impossible_intermediate_parent_states_are_rejected_before_any_input(self):
        self.owner.reserve()
        for phase,pending in (('preparing',None),('preparing','render'),('cleaning',None),('ready',None)):
            bad=deepcopy(self.store.read());bad['payload']=pack([dict(phase=phase,pending=pending,child=None)])
            with self.subTest(phase=phase,pending=pending),self.assertRaises(NativeUIError):self.owner.decode(bad)
        self.assertEqual([],self.fixture.domain.io.actions)
    def test_primary_setup_error_is_preserved_if_latest_child_retention_also_fails(self):
        self.owner.reserve();primary=RuntimeError('original child setup failure');secondary=OSError('retaining parent failed')
        save=self.owner.save;calls=[]
        def failing_save():
            calls.append(True)
            if len(calls)==2:raise secondary
            save()
        with patch.object(self.scope,'prepare',side_effect=primary),patch.object(self.owner,'save',side_effect=failing_save),self.assertRaises(RuntimeError) as caught:
            self.owner.prepare()
        self.assertIs(primary,caught.exception);self.assertTrue(any('OSError' in note for note in primary.__notes__))
        self.assertIsNone(self.scope.store.read());self.assertEqual([],self.fixture.domain.io.actions)
        self.assertEqual('prepare',self.owner.decode(self.store.read())['pending'])


class AssetsMarkerParentFactoryTests(unittest.TestCase):
    def test_canonical_factory_binds_actual_child_and_host_clock_before_any_normal_input(self):
        from ios.self_tests.assets_runtime_fixture import RuntimeBoundary
        from ios.self_tests.assets_reply_fixture import RUN,URL,TICKET
        from ios.adapters.assets_runtime import IOSAssetsRuntime
        b=RuntimeBoundary(self);host=lambda:1900000000000;b.runtime=IOSAssetsRuntime(b.f.adapter,monotonic=lambda:b.now,epoch_ms=host)
        parts=b.runtime._assets_marker_components('test-only',RUN,'primary',URL,TICKET,b.root,b.lock)
        self.assertIs(parts['marker'].scope,parts['marker_scope']);self.assertIs(host,parts['marker_scope'].epoch_ms)
        self.assertEqual('assets',parts['marker_scope'].namespace);self.assertEqual('42',parts['marker_scope'].binding['processIdentity'])
        self.assertEqual(b.root/('ios-assets-marker-'+RUN+'-primary.json'),parts['marker'].store.path)
        self.assertIsNone(parts['marker'].state);self.assertIsNone(parts['marker_scope'].store.read())
        b.f.process['foreground']=False
        with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_REJECTED'):parts['marker'].reserve()
        self.assertIsNone(parts['marker'].store.read());self.assertIsNone(parts['marker_scope'].store.read())
        self.assertEqual([],b.asset_requests);self.assertEqual([],b.afc)


class PaintedDomain(AssetsMarkerDomain):
    def start(self):
        super().start()
        # A declared Web-renderer producer observes the actual newly created
        # marker. It is not an input/owner verdict or a native pixel source.
        self.paint()


class MarkerParentFixture(unittest.TestCase):
    def setUp(self):
        self.fixture=AssetsMarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.scope=self.fixture.scope;self.domain=PaintedDomain(self.scope);self.fixture.domain=self.domain
        self.store=PrivateFeatureState(self.scope.store.path.with_name('ios-assets-marker-'+self.scope.run+'-'+self.scope.role+'.json'))
        self.owner=OwnedAssetsMarker(self.scope,self.store);self.owner.reserve()
    def restore(self):
        child=self.fixture.fixture.owner('assets');self.domain.attach(child);return OwnedAssetsMarker(child,self.store)


class AssetsMarkerParentFlowTests(MarkerParentFixture):
    def test_parent_owns_original_ready_child_and_marker_only_cleanup_without_repeating_setup(self):
        prepared=self.owner.prepare();self.assertEqual(self.domain.vm['added'][0]['id'],prepared.state['admission']['marker']['id'])
        self.assertEqual('ready',self.owner.state['phase']);inputs=deepcopy(self.domain.io.actions);restored=self.restore()
        self.assertEqual(prepared.state,restored.prepare().state);self.assertEqual(inputs,self.domain.io.actions)
        self.assertEqual({'performed':True},restored.cleanup());self.assertEqual('released',restored.state['phase'])
        self.assertFalse(self.domain.running);self.assertFalse(self.domain.files.root.exists())
        snapshot=self.store.read();before={path.name:(path.stat().st_ino,path.read_bytes()) for path in self.scope.root.iterdir() if path.is_file()}
        with patch.object(self.domain.io,'observe',side_effect=AssertionError('pure child query')):
            historical=OwnedAssetsMarker.from_archive(snapshot,self.store,artifact_root=self.scope.root,binding=self.scope.binding,run=self.scope.run,
                role=self.scope.role,fixture_url=self.scope.fixture_url,ticket=self.scope.ticket,lock=self.scope.lock)
            self.assertEqual('released',historical.state['phase'])
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in self.scope.root.iterdir() if path.is_file()})
        self.assertEqual(self.fixture.legacy,(self.fixture.old.store.path.stat().st_ino,self.fixture.old.store.path.read_bytes()))
    def test_completed_original_child_with_lost_return_is_adopted_then_lost_stop_is_not_resent(self):
        prepare=self.scope.prepare;failure=RuntimeError('lost completed original child prepare return')
        def lost_prepare():prepare();raise failure
        with patch.object(self.scope,'prepare',side_effect=lost_prepare),self.assertRaises(RuntimeError) as caught:self.owner.prepare()
        self.assertIs(failure,caught.exception);self.assertEqual('prepare',self.owner.state['pending']);self.assertEqual('ready',self.scope.state['phase'])
        restored=self.restore();restored.prepare();self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'))
        activate=self.domain.io.activate;stop_failure=NativeUIError('lost original marker stop')
        def lost_stop(identifier,**kwargs):
            result=activate(identifier,**kwargs)
            if identifier=='scripts.stop.0':raise stop_failure
            return result
        with patch.object(self.domain.io,'activate',side_effect=lost_stop),self.assertRaises(NativeUIError) as stopped:restored.cleanup()
        self.assertIs(stop_failure,stopped.exception);self.assertEqual('cleanup',restored.state['pending'])
        final=self.restore();self.assertEqual({'performed':True},final.cleanup());self.assertEqual('released',final.state['phase'])
        self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'));self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'))


class AssetsMarkerParentInterruptedCleanupTests(MarkerParentFixture):
    def assert_released_without_second_load(self):
        final=self.restore();self.assertEqual({'performed':True},final.cleanup())
        self.assertEqual('released',final.state['phase']);self.assertFalse(self.domain.running)
        self.assertEqual(1,self.domain.io.actions.count('script-file.confirm'))
        self.assertEqual(1,self.domain.io.actions.count('scripts.stop.0'))
        return final
    def test_pending_prepare_passive_failure_can_cleanup_without_finishing_setup(self):
        activate=self.domain.io.activate
        def loaded(identifier,**kwargs):
            result=activate(identifier,**kwargs)
            if identifier=='script-file.confirm':self.domain.web_failure=True
            return result
        with patch.object(self.domain.io,'activate',side_effect=loaded),self.assertRaises(OSError):self.owner.prepare()
        self.assertEqual('prepare',self.owner.state['pending']);self.assertIsNotNone(self.scope.state['pending'])
        self.domain.web_failure=False;final=self.assert_released_without_second_load()
        records=list(self.scope.root.glob('assets-marker-read-abandoned-'+self.scope.run+'-'+self.scope.role+'-*.json'))
        self.assertEqual(1,len(records));path=records[0];raw=path.read_bytes();inode=path.stat().st_ino
        try:
            path.write_bytes(b'{}')
            with self.assertRaises(NativeUIError):
                OwnedAssetsMarker.from_archive(self.store.read(),self.store,artifact_root=self.scope.root,binding=self.scope.binding,
                    run=self.scope.run,role=self.scope.role,fixture_url=self.scope.fixture_url,ticket=self.scope.ticket,lock=self.scope.lock)
        finally:path.write_bytes(raw)
        self.assertEqual(inode,path.stat().st_ino);self.assertEqual(raw,path.read_bytes());final.decode(final.previous)
    def test_lost_completed_prepare_return_can_cleanup_directly_without_render_admission(self):
        prepare=self.scope.prepare;failure=RuntimeError('lost prepare return before render admission')
        def lost():prepare();raise failure
        with patch.object(self.scope,'prepare',side_effect=lost),self.assertRaises(RuntimeError) as caught:self.owner.prepare()
        self.assertIs(failure,caught.exception);self.assertEqual('prepare',self.owner.state['pending'])
        self.assertIsNone(self.scope.state['webAdmission']);before=deepcopy(self.owner.state['child']);final=self.assert_released_without_second_load()
        with patch.dict(final.state,pending='render'),self.assertRaises(NativeUIError):final.prefix(before,final.scope.store.read())
    def test_lost_render_admission_return_can_cleanup_without_new_render_query(self):
        render=self.scope.admit_rendered;failure=RuntimeError('lost completed render admission return')
        def lost():render();raise failure
        with patch.object(self.scope,'admit_rendered',side_effect=lost),self.assertRaises(RuntimeError) as caught:self.owner.prepare()
        self.assertIs(failure,caught.exception);self.assertEqual('render',self.owner.state['pending'])
        self.assertIsNotNone(self.scope.state['webAdmission']);self.assert_released_without_second_load()
