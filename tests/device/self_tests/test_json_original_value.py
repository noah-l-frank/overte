"""Pure historical value metadata, with no product or source authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import sys
import unittest
from adapters.json_original_value import capture,dimensions,matches,scratch_bound,matches_original_refs


class JsonOriginalValueTests(unittest.TestCase):
    def test_values_order_and_retained_payload_identity(self):
        payload = 'x' * 64000
        value = {'b': [None, True, 2, 2.5, payload], 'a': {'nested': 'value'}}
        seal, resident, peak = capture(value)
        self.assertTrue(matches(deepcopy(value), seal))
        self.assertTrue(matches(dict(reversed(list(value.items()))), seal))
        self.assertTrue(any(item is payload for item in seal[1]))
        actual = sys.getsizeof(seal) + sys.getsizeof(seal[0]) + sys.getsizeof(seal[1])
        self.assertLess(actual, resident)
        self.assertLess(resident, peak)
        value['a']['nested'] = 'changed'
        self.assertFalse(matches(value, seal))

    def test_types_unicode_signed_zero_and_unusual_json(self):
        for before, after in ((True, 1), (1, 1.), ([1], (1,)), (0., -0.),
                              ('\U0001f600', '\ud83d\ude00'), ({'a': 1}, {'b': 1})):
            seal, _, _ = capture(before)
            self.assertFalse(matches(after, seal))
        for value in (float('nan'), float('inf'), {1: 'bad'}, (1,), b'bytes'):
            self.assertIsNone(capture(value))
        for value in ({'a': -0.0}, {'\ud800': '\udfff'}, 10**1000):
            seal, _, _ = capture(value)
            self.assertTrue(matches(deepcopy(value), seal))

    def test_no_user_equality_on_unknown_values_or_keys(self):
        calls = []
        class Alias(str):
            __hash__ = str.__hash__
            def __eq__(self, other):
                calls.append(True)
                return True
        seal, _, _ = capture({'key': 'value'})
        self.assertFalse(matches({'key': Alias('value')}, seal))
        self.assertFalse(matches({Alias('key'): 'value'}, seal))
        self.assertIsNone(capture({'key': Alias('value')}))
        self.assertIsNone(capture({Alias('key'): 'value'}))
        self.assertEqual([], calls)

    def test_finite_depth_node_and_preheld_capacity_fallback(self):
        value = {'many': list(range(1500))}
        plan = dimensions(value)
        self.assertIsNotNone(plan)
        self.assertIsNone(capture(value, capacity=plan[4]-1))
        seal, resident, peak = capture(value, capacity=plan[4])
        self.assertEqual((resident, peak), plan[3:])
        self.assertTrue(matches(value, seal))
        self.assertIsNone(capture(value, max_nodes=512))
        cycle = []; cycle.append(cycle)
        self.assertIsNone(capture(cycle))
        value = {'a': [1]}
        seal, _, _ = capture(value)
        value['a'][0] = value['a']
        self.assertFalse(matches(value, seal))
        self.assertGreaterEqual(scratch_bound(64), 65536)



    def test_original_reference_match_rejects_equal_new_payload_or_key(self):
        key='key-original-'+str(401);payload='same original payload'*500
        value={key:payload};seal,_,_=capture(value)
        self.assertTrue(matches_original_refs(value,seal))
        copy=payload.encode().decode();self.assertEqual(copy,payload);self.assertIsNot(copy,payload)
        value[key]=copy;self.assertFalse(matches_original_refs(value,seal))
        value={key:payload};new_key=key.encode().decode();self.assertIsNot(key,new_key)
        self.assertFalse(matches_original_refs({new_key:payload},seal))

import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError


class JsonOriginalCatalogTests(unittest.TestCase):
    def make(self,direct=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);owner=ChatArchiveCatalog(hold_files=False,closed_file_windows=direct)
        self.addCleanup(lambda:self.assertTrue(owner.close_host()))
        for i in range(3):
            store=PrivateFeatureState(root/f'original-{i}.json')
            value={'payload':('original-'+str(i))*4000,'small':[True,None,-0.0]}
            store.write(value,None);owner.add('primary/'+store.path.name,store,value)
        return owner

    def test_default_keeps_original_canonical_bytes_and_three_checks(self):
        owner=self.make();guard=owner.verify_parent
        with patch.object(owner,'verify_parent',wraps=guard) as calls:owner.verify_all()
        self.assertEqual(9,calls.call_count)
        self.assertTrue(all(type(entry[3]) is bytes for entry in owner._json_originals))
        self.assertIsNone(owner.value_cache)

    def test_replacement_releases_original_canonical_storage_within_its_old_peak(self):
        import tracemalloc
        tracemalloc.start()
        try:
            owner=self.make(True)
            verify=owner.verify_all;baseline=[]
            def verified_originals():
                verify()
                # The unchanged full-file pread/close window has its own
                # existing workspace. Measure metadata construction AFTER it.
                baseline.append(tracemalloc.get_traced_memory()[0]);tracemalloc.reset_peak()
            with patch.object(owner,'verify_all',side_effect=verified_originals):
                result=owner.freeze_expected_values()
            after,peak=tracemalloc.get_traced_memory()
        finally:tracemalloc.stop()
        self.assertEqual(1,len(baseline));before=baseline[0]
        self.assertEqual(3,result['sealed']);self.assertGreater(result['releasedCanonicalCredit'],0)
        self.assertLess(after,before)
        self.assertLessEqual(peak,before+result['originalTemporaryWorkspace'])
        self.assertLessEqual(result['constructionHighwater'],
            result['originalCanonicalBytes']+result['originalTemporaryWorkspace'])

    def test_explicit_cache_retains_actual_full_reads_and_before_after_parent_checks(self):
        import os
        owner=self.make(True);memory=owner.freeze_expected_values()
        self.assertEqual(3,memory['sealed']);self.assertGreater(memory['releasedCanonicalCredit'],0)
        guard=owner.verify_parent;pread=os.pread
        with patch.object(owner,'verify_parent',wraps=guard) as calls,patch.object(os,'pread',wraps=pread) as reads:
            owner.verify_all()
        self.assertEqual(6,calls.call_count);self.assertEqual(3,reads.call_count)
        self.assertTrue(all(type(entry[3]) is tuple for entry in owner._json_originals))
        for row in owner.rows.values():owner.expected_digest(row)

    def test_original_byte_change_is_refused_with_same_expected_objects(self):
        owner=self.make(True);owner.freeze_expected_values();row=next(iter(owner.rows.values()))
        path=row['store'].path;raw=path.read_bytes();path.write_bytes(raw.replace(b'original',b'changed!',1))
        with self.assertRaises(NativeUIError):owner.verify_all()
        self.assertTrue(row['owner'].failed)

    def test_equal_new_scalar_is_sticky_before_any_new_file_read(self):
        import os
        owner=self.make(True);owner.freeze_expected_values();row=next(iter(owner.rows.values()))
        value=row['expected'];old=value['payload'];new=old.encode().decode()
        self.assertIsNot(old,new);self.assertEqual(old,new);value['payload']=new
        pread=os.pread
        with patch.object(os,'pread',wraps=pread) as reads:
            with self.assertRaises(NativeUIError):owner.verify_all()
        self.assertEqual(0,reads.call_count);self.assertTrue(owner.failed)
        value['payload']=old
        with self.assertRaises(NativeUIError):owner.verify_all()


class JsonAdmissionValuesTests(unittest.TestCase):
    """Pure historical admission fields over actual already-owned file rows."""
    make=JsonOriginalCatalogTests.make
    def capture_owner(self,*,small=False):
        from adapters.pico4.browser_capture_retirement import PicoBrowserCaptureRetirement
        catalog=self.make(True)
        if small:
            # A separate actual tiny source has insufficient released credit;
            # normal canonical admission remains available without a new quota.
            self.assertTrue(catalog.close_host())
            temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
            catalog=ChatArchiveCatalog(hold_files=False,closed_file_windows=True)
            self.addCleanup(catalog.close_host)
            store=PrivateFeatureState(Path(temp.name)/'tiny.json');store.write({'value':1},None)
            catalog.add('primary/tiny.json',store,store.read())
        owner=PicoBrowserCaptureRetirement.__new__(PicoBrowserCaptureRetirement)
        owner.catalog=catalog;owner.scope={'runId':'a'*32};owner.owner={'ownerToken':'b'*32}
        owner.proofs=[{'original':[True,None,{'source':'actual old value'}]}]
        owner.initialize_pngs();owner._admission_values=owner._sealed_admission_values=None
        owner._admission_wrapper_bytes=0;owner.failed=False
        owner.admitted=owner._sealed_admitted=owner.admission_bytes()
        catalog.freeze_expected_values();return owner

    def test_admission_reuses_only_original_bytes_after_fresh_complete_metadata_walk(self):
        from adapters.script_journey.history import canonical
        owner=self.capture_owner();original=owner.admitted;before=owner.catalog.value_cache.metadata
        owner.freeze_admission_values()
        self.assertIsNotNone(owner._admission_values)
        self.assertGreater(owner.catalog.value_cache.metadata,before)
        self.assertGreaterEqual(owner.catalog.value_cache.auxiliary_credit(0),0)
        self.assertIs(original,owner.admission_bytes())
        self.assertEqual(canonical(owner.admission()),owner.admission_bytes())

    def test_direct_seal_construction_and_live_charge_fit_actual_released_credit(self):
        import tracemalloc
        from adapters.json_original_value import container_dimensions
        owner=self.capture_owner();cache=owner.catalog.value_cache
        before=cache.metadata;credit=cache.auxiliary_credit(0)
        tracemalloc.start()
        try:
            owner.freeze_admission_values()
            live,peak=tracemalloc.get_traced_memory()
        finally:tracemalloc.stop()
        self.assertIsNotNone(owner._admission_values)
        roots,seal,rows,pngs=owner._admission_values
        bound=512*len(owner.catalog.rows)+65536
        self.assertEqual(bound,owner._admission_wrapper_bytes)
        resident=container_dimensions(roots,max_nodes=65536,max_depth=16)[3]
        self.assertEqual(resident+bound,cache.metadata-before)
        self.assertLessEqual(live,cache.metadata-before)
        self.assertLessEqual(peak,credit)
        self.assertGreaterEqual(cache.auxiliary_credit(0),0)
        self.assertEqual(len(owner.catalog.rows),len(rows))
        self.assertIs(owner.scope,roots['scope'])
        self.assertIs(owner._png_bytes,pngs[0])
        self.assertIs(owner.admitted,owner.admission_bytes())

    def assert_sticky_mutation(self,mutate):
        owner=self.capture_owner();owner.freeze_admission_values()
        self.assertIsNotNone(owner._admission_values)
        restore=mutate(owner)
        with self.assertRaises(NativeUIError):owner.admission_bytes()
        self.assertTrue(owner.failed)
        restore()
        with self.assertRaises(NativeUIError):owner.admission_bytes()

    def test_original_roots_and_equal_nested_containers_are_retained(self):
        for field in ('scope','owner','proofs'):
            with self.subTest(root=field):
                def change(owner):
                    old=getattr(owner,field);setattr(owner,field,deepcopy(old))
                    return lambda:setattr(owner,field,old)
                self.assert_sticky_mutation(change)
        def change(owner):
            old=owner.proofs[0]['original'];owner.proofs[0]['original']=list(old)
            return lambda:owner.proofs[0].__setitem__('original',old)
        self.assert_sticky_mutation(change)

    def test_current_catalog_row_store_path_stamp_sha_and_key_order_are_fresh(self):
        for field in ('row','store','path','stamp','stamp-part','sha256','label','order'):
            with self.subTest(field=field):
                def change(owner):
                    label,row=next(iter(owner.catalog.rows.items()))
                    if field=='order':
                        old=tuple(owner.catalog.rows.items());owner.catalog.rows=dict(reversed(old))
                        return lambda:setattr(owner.catalog,'rows',dict(old))
                    if field=='label':
                        old=owner.catalog.rows;new=label.encode().decode();self.assertIsNot(new,label)
                        owner.catalog.rows={new if key is label else key:value for key,value in old.items()}
                        return lambda:setattr(owner.catalog,'rows',old)
                    if field=='row':
                        owner.catalog.rows[label]=dict(row)
                        return lambda:owner.catalog.rows.__setitem__(label,row)
                    if field=='path':
                        old=row['store'].path;new=Path(str(old));self.assertIsNot(new,old)
                        row['store'].path=new
                        return lambda:setattr(row['store'],'path',old)
                    if field=='stamp-part':
                        old=row['stamp'][0];row['stamp'][0]=old+1
                        return lambda:row['stamp'].__setitem__(0,old)
                    old=row[field]
                    new=(PrivateFeatureState(old.path) if field=='store' else
                        list(old) if field=='stamp' else old.encode().decode())
                    self.assertIsNot(new,old);row[field]=new
                    return lambda:row.__setitem__(field,old)
                self.assert_sticky_mutation(change)

    def test_original_png_references_and_both_current_and_sealed_pins_are_checked(self):
        for field in ('bytes','sha','windows'):
            for pins in ('current','sealed','both'):
                with self.subTest(field=field,pins=pins):
                    def change(owner):
                        current='_png_'+field;sealed='_sealed_png_'+field
                        old=getattr(owner,current)
                        new=(bytes(bytearray(old)) if field=='bytes' else
                            old.encode().decode() if field=='sha' else ('foreign window',))
                        self.assertIsNot(new,old)
                        names=(current,) if pins=='current' else (sealed,) if pins=='sealed' else (current,sealed)
                        for name in names:setattr(owner,name,new)
                        def restore():
                            for name in names:setattr(owner,name,old)
                        return restore
                    self.assert_sticky_mutation(change)

    def test_changed_original_metadata_is_sticky_instead_of_resealing(self):
        owner=self.capture_owner();owner.freeze_admission_values()
        self.assertIsNotNone(owner._admission_values)
        owner.proofs[0]['original'][2]['source']='different'
        with self.assertRaises(NativeUIError):owner.admission_bytes()
        self.assertTrue(owner.failed)
        owner.proofs[0]['original'][2]['source']='actual old value'
        with self.assertRaises(NativeUIError):owner.admission_bytes()

    def test_active_seal_eviction_is_sticky_instead_of_canonical_fallback(self):
        for pins in ('current','sealed','both'):
            with self.subTest(pins=pins):
                owner=self.capture_owner();owner.freeze_admission_values()
                original=owner._admission_values;self.assertIsNotNone(original)
                names=(('_admission_values',) if pins=='current' else
                    ('_sealed_admission_values',) if pins=='sealed' else
                    ('_admission_values','_sealed_admission_values'))
                for name in names:setattr(owner,name,None)
                with self.assertRaises(NativeUIError):owner.admission_bytes()
                self.assertTrue(owner.failed)
                for name in names:setattr(owner,name,original)
                with self.assertRaises(NativeUIError):owner.admission_bytes()

    def test_insufficient_released_metadata_credit_keeps_original_serialization(self):
        from adapters.script_journey.history import canonical
        owner=self.capture_owner(small=True);owner.freeze_admission_values()
        self.assertIsNone(owner._admission_values)
        self.assertEqual(canonical(owner.admission()),owner.admission_bytes())




class JsonOriginalContainerTests(unittest.TestCase):
    def test_every_original_edge_is_checked_without_foreign_equality(self):
        from adapters.json_original_value import capture_containers, matches_containers
        payload='actual historical payload '+str(721)
        key='actual historical key '+str(812)
        child=[payload,True,1,1.,-0.,None];value={key:child,'tail':{'same':True}}
        seal,_,_=capture_containers(value)
        self.assertTrue(matches_containers(value,seal))
        self.assertIs(seal[1][0][2][0],child)
        self.assertIs(seal[1][1][2][0],payload)
        for replacement in (payload.encode().decode(),False,1.,0.):
            child[0]=replacement
            self.assertFalse(matches_containers(value,seal))
        child[0]=payload;self.assertTrue(matches_containers(value,seal))
        value[key]=list(child);self.assertFalse(matches_containers(value,seal))
        value[key]=child
        other=key.encode().decode();self.assertIsNot(key,other)
        value.pop(key);value[other]=child
        self.assertFalse(matches_containers(value,seal))
        calls=[]
        class Foreign(str):
            __hash__=str.__hash__
            def __eq__(self,other):calls.append('eq');return True
        child[0]=Foreign(payload)
        self.assertFalse(matches_containers(value,seal));self.assertEqual([],calls)

    def test_original_cycles_bounds_and_foreign_types_refuse_admission(self):
        from adapters.json_original_value import capture_containers,container_dimensions,matches_containers
        for value in (float('nan'),float('inf'),{1:'bad'},(1,),b'bytes'):
            self.assertIsNone(capture_containers(value))
        cycle=[];cycle.append(cycle);self.assertIsNone(capture_containers(cycle))
        for value in ({'a':-0.0},{'\ud800':'\udfff'},10**1000):
            seal,_,_=capture_containers(value);self.assertTrue(matches_containers(value,seal))
        shared=['old'];value={'one':shared,'two':shared}
        seal,_,_=capture_containers(value);self.assertTrue(matches_containers(value,seal))
        self.assertIsNone(capture_containers(value,max_depth=0))
        self.assertIsNone(capture_containers(value,max_nodes=2))
        calls=[]
        class EqualType(type):
            def __eq__(self,other):calls.append('eq');return True
        class Foreign(str,metaclass=EqualType):pass
        self.assertIsNone(container_dimensions({'key':Foreign('value')}))
        self.assertEqual([],calls)

    def test_small_and_branched_construction_stays_within_preheld_bytes(self):
        import tracemalloc
        from adapters.json_original_value import capture_containers,container_dimensions,matches_containers
        values=[{'rows':[{'name':'existing payload '+str(n),'nested':[n,1.]} for n in range(300)]}]
        values.extend({'name':'held before construction '+str(n)} for n in range(64))
        plans=[container_dimensions(value) for value in values]
        results=[None]*len(values)
        tracemalloc.start()
        try:
            for index,value in enumerate(values):
                results[index]=capture_containers(value,capacity=plans[index][4])
            live,peak=tracemalloc.get_traced_memory()
        finally:tracemalloc.stop()
        self.assertTrue(all(result is not None for result in results))
        resident=sum(result[1] for result in results)
        self.assertLessEqual(live,resident)
        self.assertLessEqual(peak,resident+max(plan[4]-plan[3] for plan in plans))
        for value,plan,result in zip(values,plans,results):
            self.assertEqual(plan[3:],result[1:])
            self.assertTrue(matches_containers(value,result[0]))
            self.assertIsNone(capture_containers(value,capacity=plan[4]-1))
        tracemalloc.start()
        try:
            self.assertTrue(matches_containers(values[0],results[0][0]))
            _,peak=tracemalloc.get_traced_memory()
        finally:tracemalloc.stop()
        self.assertLessEqual(peak,2048)


class JsonOriginalContainerCatalogTests(unittest.TestCase):
    make=JsonOriginalCatalogTests.make
    def test_equal_nested_container_replacement_is_sticky_before_new_file_read(self):
        owner=self.make(True);owner.freeze_expected_values();row=next(iter(owner.rows.values()))
        original=row['expected']['small'];row['expected']['small']=list(original)
        with patch.object(os,'pread',wraps=os.pread) as reads:
            with self.assertRaises(NativeUIError):owner.verify_all()
        self.assertEqual(0,reads.call_count);self.assertTrue(owner.failed)
        row['expected']['small']=original
        with self.assertRaises(NativeUIError):owner.verify_all()


if __name__=='__main__':unittest.main()
