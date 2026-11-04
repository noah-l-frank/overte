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
        self.assertGreaterEqual(owner.catalog.value_cache.auxiliary_credit(owner._admission_wrapper_bytes),0)
        self.assertIs(original,owner.admission_bytes())
        self.assertEqual(canonical(owner.admission()),owner.admission_bytes())

    def test_changed_original_metadata_is_sticky_instead_of_resealing(self):
        owner=self.capture_owner();owner.freeze_admission_values()
        self.assertIsNotNone(owner._admission_values)
        owner.proofs[0]['original'][2]['source']='different'
        with self.assertRaises(NativeUIError):owner.admission_bytes()
        self.assertTrue(owner.failed)
        owner.proofs[0]['original'][2]['source']='actual old value'
        with self.assertRaises(NativeUIError):owner.admission_bytes()

    def test_active_seal_eviction_is_sticky_instead_of_canonical_fallback(self):
        owner=self.capture_owner();owner.freeze_admission_values()
        original=owner._admission_values;self.assertIsNotNone(original)
        owner._admission_values=None
        with self.assertRaises(NativeUIError):owner.admission_bytes()
        self.assertTrue(owner.failed)
        owner._admission_values=original
        with self.assertRaises(NativeUIError):owner.admission_bytes()

    def test_insufficient_released_metadata_credit_keeps_original_serialization(self):
        from adapters.script_journey.history import canonical
        owner=self.capture_owner(small=True);owner.freeze_admission_values()
        self.assertIsNone(owner._admission_values)
        self.assertEqual(canonical(owner.admission()),owner.admission_bytes())


if __name__=='__main__':unittest.main()
