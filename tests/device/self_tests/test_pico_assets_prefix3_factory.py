"""Actual private factory/default admission; native/backend data are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_prefix import PicoAssetsPrefix
from adapters.pico4.assets_uploads import PicoAssetsUploads
from adapters.observer_return import state as file_state
from adapters.script_journey.history import same,canonical
from copy import deepcopy
from adapters.pico4.assets_backend_originals import PicoAssetsBackendOriginals
from self_tests.pico_assets_prefix_fixture import AssetsPrefixModel
from self_tests.pico_assets_upload_fixture import AssetsUploadModel
import test_normal_scripts as normal


class AssetsPrefix3FactoryTests(unittest.TestCase):
    def setUp(self):
        self.normal=normal.PicoNormalScriptsTests(methodName='runTest');self.normal.setUp()
        self.addCleanup(self.normal.doCleanups)
        temporary=self.normal.fixture.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None
        self.root=Path(tempfile.mkdtemp(prefix='pico-assets-prefix3-factory-'));self.root.chmod(0o700)
        print('Retained factory admission originals:',self.root,flush=True)

    def test_default_none_remains_original_prefix2_with_no_wire_or_input(self):
        model=AssetsPrefixModel(self,self.root,self.normal,manual_owner=False)
        model.lock=model.adapter._script_journey()._lock(model.native.target)
        with model.lock.held(),patch('adapters.pico4.assets_prefix._warm_signature',side_effect=AssertionError('No Prefix3 seal in default2')):
            owner=model.adapter._assets_prefix(model.native.target,model.run,model.url,model.phase,source_lock=model.lock)
            owner.bound()
        self.addCleanup(owner.raw_archive.close_host)
        self.assertIs(type(owner),PicoAssetsPrefix);self.assertEqual(2,owner.version)
        self.assertEqual(1,owner.scope['assetsRawOriginalLayoutVersion']);self.assertIsNone(owner.wire)
        self.assertEqual([],model.calls);self.assertEqual([],model.inputs);self.assertNotIn('transportReceipts',owner.state)

    def test_wrong_backend_type_refused_before_runtime_or_original_source(self):
        model=AssetsPrefixModel(self,self.root,self.normal,manual_owner=False)
        lock=model.adapter._script_journey()._lock(model.native.target)
        with lock.held(),patch.object(model.adapter,'_script_runtime',side_effect=AssertionError('No runtime before exact backend')) as source:
            with self.assertRaises(ValueError):
                model.adapter._assets_prefix(model.native.target,model.run,model.url,model.phase,source_lock=lock,backend=object())
        source.assert_not_called();self.assertFalse(model.inputs)

    def test_exact_but_nonfresh_backend_refused_before_runtime_or_guard(self):
        model=AssetsPrefixModel(self,self.root,self.normal,manual_owner=False)
        lock=model.adapter._script_journey()._lock(model.native.target)
        backend=object.__new__(PicoAssetsBackendOriginals)
        backend.history=[dict(declaredNegativeOnly=True)];backend.last=None;backend.pending=None
        with lock.held(),patch.object(model.adapter,'_script_runtime',side_effect=AssertionError('No runtime for nonfresh backend')) as source:
            with self.assertRaises(ValueError):
                model.adapter._assets_prefix(model.native.target,model.run,model.url,model.phase,source_lock=lock,backend=backend)
        source.assert_not_called();self.assertFalse(model.inputs)

    def fresh_model(self):
        self.normal.native.identity='123:314159'
        native=patch.object(self.normal.native,'require_process_identity',
            side_effect=lambda identity:self.assertEqual('123:314159',identity))
        native.start();self.addCleanup(native.stop)
        return AssetsUploadModel(self,self.root,self.normal,binary_transport=True,canonical_prefix=True)

    def test_actual_baseline_preserves_upload_capture_once_and_three_original_sdk_returns(self):
        model=self.fresh_model();owner=model.owner;model.activate('baseline')
        result=owner.observe();self.assertFalse(result['open'])
        self.assertEqual(3,len(model.sdk_calls));self.assertEqual(3,len(owner.state['rawReads']))
        self.assertEqual(1,len(owner.uploads.history));self.assertEqual(1,len(owner.mappings.history))
        raw=owner.uploads.history[0]['raw'];self.assertEqual(raw,owner.uploads._seen_raw)
        with owner.lock.held():self.assertEqual(raw.encode(),owner.literal(1))
        calls=[]
        with self.assertRaises(NativeUIError):owner.uploads.bind_raw_reader(lambda:calls.append('forbidden'))
        self.assertFalse(calls);self.assertEqual(3,len(model.sdk_calls));self.assertFalse(model.inputs)

    def test_default_uploads_capture_uses_original_getter_exactly_once(self):
        model=AssetsPrefixModel(self,self.root,self.normal,manual_owner=False);calls=[]
        def raw():calls.append('original');return model.original()
        reader=PicoAssetsUploads(model.send,raw,model.epoch,model.guard,123,monotonic=lambda:model.clock,sleep=model.sleep)
        value=reader.read(model.run)
        self.assertEqual(['original'],calls);self.assertEqual(reader.history[0]['raw'],reader._seen_raw)
        self.assertEqual(value,reader.last);self.assertFalse(reader._raw_reader_bound)

    def test_cold_raw_hook_once_reentry_and_changed_callback_refuse_before_original_getter(self):
        model=AssetsPrefixModel(self,self.root,self.normal,manual_owner=False);calls=[]
        reader=PicoAssetsUploads(model.send,lambda:calls.append('forbidden original'),model.epoch,model.guard,123)
        invoked=[]
        def reenter():invoked.append('actual callback');return reader.original()
        reader.bind_raw_reader(reenter)
        with self.assertRaises(NativeUIError):reader.bind_raw_reader(lambda:'foreign')
        with self.assertRaises(NativeUIError):reader.original()
        self.assertEqual(['actual callback'],invoked);self.assertFalse(calls);self.assertIsNone(reader._seen_raw)
        reader._raw_reader=lambda:calls.append('foreign hook')
        with self.assertRaises(NativeUIError):reader.original()
        self.assertFalse(calls);self.assertIsNone(reader._seen_raw)

    def current_control(self):
        model=self.fresh_model();model.activate('baseline');model.owner.observe();return model,model.owner

    def refuse_more_sdk(self,model,owner):
        before=len(model.sdk_calls)
        with self.assertRaises(NativeUIError):owner.observe()
        self.assertEqual(before,len(model.sdk_calls));self.assertFalse(model.inputs)

    def old_control_refuses(self,owner):
        with self.assertRaises(NativeUIError):
            actual,raw,physical=file_state(owner.store)
            from adapters.native_feature_observation import need
            need(same(actual,owner.disk) and tuple(physical)==owner.stamp)

    def test_original_control_candidate_substitution_refuses_before_further_sdk(self):
        model,owner=self.current_control();owner.control_candidate=tuple(list(owner.control_candidate))
        self.refuse_more_sdk(model,owner)

    def test_nested_expected_disk_mutation_refuses_before_further_sdk(self):
        model,owner=self.current_control();owner.disk['rawReads'][0]['role']='foreign-memory-role'
        self.old_control_refuses(owner);self.refuse_more_sdk(model,owner)

    def test_expected_disk_boolean_type_mutation_refuses_before_further_sdk(self):
        model,owner=self.current_control();owner.disk['observations']=True
        self.old_control_refuses(owner);self.refuse_more_sdk(model,owner)

    def test_actual_changed_control_bytes_refuse_old_and_new_before_further_sdk(self):
        model,owner=self.current_control();value=deepcopy(owner.disk);value['phase']='foreign-current-control'
        owner.store.path.write_bytes(canonical(value)+b'\n');owner.store.path.chmod(0o600)
        self.old_control_refuses(owner);self.refuse_more_sdk(model,owner)

    def test_actual_equal_byte_replacement_control_inode_refuses_old_and_new(self):
        model,owner=self.current_control();path=owner.store.path;replacement=path.with_suffix('.fixture-replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        self.old_control_refuses(owner);self.refuse_more_sdk(model,owner)

    def test_original_control_memory_inspection_order_and_deepcopy_remain_compatible(self):
        model,owner=self.current_control();inspection=owner.disk['rawReads'][0]
        owner.disk=dict(reversed(list(owner.disk.items())));owner.disk=deepcopy(owner.disk)
        with owner.lock.held():owner.bound()
        self.assertEqual(3,len(model.sdk_calls));self.assertEqual('mappings',inspection['role'])
        self.assertFalse(owner.observe()['open']);self.assertEqual(6,len(model.sdk_calls))

    def test_unknown_successful_cas_never_reseals_control_candidate(self):
        model,owner=self.current_control();original=owner.control_candidate;write=owner.store.write
        def unknown(value,previous):write(value,previous);raise NativeUIError('declared uncertain post-CAS result')
        with owner.lock.held():
            owner.state['observations']+=1
            with patch.object(owner.store,'write',side_effect=unknown),self.assertRaises(NativeUIError):owner.save()
            self.assertIs(original,owner.control_candidate)
        self.refuse_more_sdk(model,owner)

    def test_failed_cas_never_reseals_control_candidate(self):
        model,owner=self.current_control();original=owner.control_candidate;before=owner.store.path.read_bytes()
        with owner.lock.held():
            owner.state['observations']+=1
            with patch.object(owner.store,'write',side_effect=NativeUIError('declared pre-CAS failure')),self.assertRaises(NativeUIError):owner.save()
        self.assertIs(original,owner.control_candidate);self.assertEqual(before,owner.store.path.read_bytes())
        # Caller failure does not manufacture another live source operation.
        self.assertEqual(3,len(model.sdk_calls))

    def test_actual_fresh_backend_factory_has_same_parent_lock_wire_and_no_input(self):
        self.normal.native.identity='123:314159'
        native=patch.object(self.normal.native,'require_process_identity',
            side_effect=lambda identity:self.assertEqual('123:314159',identity))
        native.start();self.addCleanup(native.stop)
        model=AssetsUploadModel(self,self.root,self.normal,binary_transport=True,canonical_prefix=True)
        owner=model.owner;self.assertIs(type(owner),PicoAssetsPrefix);self.assertEqual(3,owner.version)
        self.assertIs(owner.lock,model.lock);self.assertIs(owner.wire.parent,owner)
        self.assertIs(owner.wire.adapter,model.adapter);self.assertIsNone(owner.upload_owner)
        self.assertEqual([],model.backend.history);self.assertEqual([],model.inputs);self.assertEqual([],model.sdk_calls)
        self.assertEqual(2,owner.scope['assetsRawOriginalLayoutVersion']);self.assertEqual(1,owner.scope['assetsWireOriginalLayoutVersion'])
        self.assertIsNone(model.process.poll());self.assertFalse(owner.state['steps'])


if __name__=='__main__':unittest.main()
