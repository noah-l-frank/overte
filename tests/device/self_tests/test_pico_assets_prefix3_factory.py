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

    def fresh_model(self,**model_options):
        self.normal.native.identity='123:314159'
        native=patch.object(self.normal.native,'require_process_identity',
            side_effect=lambda identity:self.assertEqual('123:314159',identity))
        native.start();self.addCleanup(native.stop)
        return AssetsUploadModel(self,self.root,self.normal,binary_transport=True,canonical_prefix=True,**model_options)

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

    def test_explicit_compact_layout_uses_actual_factory_and_passive_originals(self):
        from adapters.pico4.assets_prefix_originals import AssetsPrefixOriginals
        model=self.fresh_model(receipt_layout=1);owner=model.owner
        self.assertEqual(1,owner.receipt_layout);self.assertEqual(1,owner.scope['assetsRawReceiptLayoutVersion'])
        model.activate('baseline');owner.observe()
        self.assertEqual(3,len(model.sdk_calls));self.assertFalse(model.inputs)
        self.assertTrue(all(type(row) is list for row in owner.disk['rawReads']))
        with owner.lock.held():
            expected=owner.uploads.history[0]['raw'].encode()
            self.assertEqual(expected,owner.literal(1))
            reader=AssetsPrefixOriginals(owner.store.path);self.addCleanup(reader.close_host)
            self.assertEqual(1,reader.receipt_layout);self.assertEqual(expected,reader.literal(1))
            self.assertTrue(reader.close_host())

    def test_changed_compact_hash_cannot_replace_original_literal(self):
        model=self.fresh_model(receipt_layout=1);owner=model.owner
        model.activate('baseline');owner.observe();calls=len(model.sdk_calls)
        with owner.lock.held():
            owner.state['rawReads'][0][3]='f'*64;owner.save()
            with self.assertRaises(NativeUIError):owner.literal(0)
        self.assertEqual(calls,len(model.sdk_calls));self.assertFalse(model.inputs)

    def test_wrong_receipt_policy_refuses_before_factory_runtime(self):
        model=AssetsPrefixModel(self,self.root,self.normal,manual_owner=False)
        for policy in (True,-1,2,'1'):
            with patch.object(model.adapter,'_script_runtime',side_effect=AssertionError('No runtime before receipt policy')) as source:
                with self.assertRaises(ValueError):
                    model.adapter._assets_prefix(model.native.target,model.run,model.url,model.phase,
                        source_lock=model.lock,receipt_layout=policy)
            source.assert_not_called()
        self.assertFalse(model.inputs);self.assertFalse(model.calls)

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


class AssetsRawReceiptCodecTests(unittest.TestCase):
    def test_all_roles_views_and_tail_references_roundtrip_without_aliases(self):
        from adapters.pico4.assets_raw_archive import pack_receipt,unpack_receipt
        rows=[]
        for index in range(256):
            role=('mappings','uploads','files','ui','backend','download','ui-observation','ui-status')[index%8]
            tag='role' if index%2 else 'childSource'
            row={tag:role,'rawOriginal':dict(assetsRawCompactVersion=2,read=index,sha256='a'*64,tailBundle=index if index%3 else None)}
            if index%4:row['wireView']=dict(assetsWireViewVersion=1,nonce='b'*32,bytes=index,sha256='c'*64)
            rows.append(row)
        packed=[pack_receipt(row) for row in rows]
        self.assertEqual(rows,[unpack_receipt(row) for row in packed])
        self.assertLess(len(canonical(packed)),len(canonical(rows))-30000)
        decoded=unpack_receipt(packed[1]);decoded['wireView']['bytes']=999
        self.assertEqual(1,packed[1][5][1])
        stored=pack_receipt(decoded);decoded['wireView']['bytes']=1000
        self.assertEqual(999,stored[5][1])

    def test_invalid_codes_types_and_reference_fields_refuse(self):
        from adapters.pico4.assets_raw_archive import unpack_receipt
        valid=[0,'mappings',0,'a'*64,None,None]
        for index,value in ((0,True),(0,2),(1,'other'),(2,True),(2,-1),(3,'g'*64),(4,True),(5,[])):
            row=deepcopy(valid);row[index]=value
            with self.assertRaises(NativeUIError):unpack_receipt(row)
        for value in (tuple(valid),valid[:-1],valid+[None]):
            with self.assertRaises(NativeUIError):unpack_receipt(value)

    def test_wire_view_fields_and_exact_scalars_are_preserved(self):
        from adapters.pico4.assets_raw_archive import pack_receipt,unpack_receipt
        valid=[1,'ui-status',2,'b'*64,3,['c'*32,100,'d'*64]]
        self.assertEqual(valid,pack_receipt(unpack_receipt(valid)))
        for index,value in ((0,'c'*31),(1,True),(1,-1),(2,'d'*63)):
            row=deepcopy(valid);row[5][index]=value
            with self.assertRaises(NativeUIError):unpack_receipt(row)
        row=unpack_receipt(valid);row['foreign']=True
        with self.assertRaises(NativeUIError):pack_receipt(row)
