"""Adjacent Snapshot history floors retain complete independent originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_snapshots_role import distinct


class SnapshotDistinctTests(unittest.TestCase):
    def test_only_adjacent_duplicates_are_removed(self):
        a=dict(instance='original',sequence=1,events=[])
        b=dict(instance='original',sequence=2,events=[dict(kind='completed')])
        self.assertEqual(distinct(iter([a,deepcopy(a),b,a])),[a,b,a])
        self.assertEqual(distinct([]),[])

    def test_complete_nested_original_compared_not_just_sequence(self):
        a=dict(sequence=4,source=dict(owner='original',pending=0),events=[])
        b=deepcopy(a);b['source']['pending']=1
        c=deepcopy(b);c['events']=[dict(kind='cancelled')]
        self.assertEqual(distinct([a,b,c,c]),[a,b,c])
        self.assertEqual(distinct([dict(a=1,b=2),dict(b=2,a=1)]),[dict(a=1,b=2)])

    def test_output_has_no_input_or_cross_row_mutable_alias(self):
        shared=[];a=dict(sequence=1,left=shared,right=shared)
        b=dict(sequence=2,left=shared,right=shared)
        result=distinct([a,b])
        self.assertIs(result[0]['left'],result[0]['right'])
        self.assertIsNot(result[0]['left'],shared)
        self.assertIsNot(result[0]['left'],result[1]['left'])
        result[0]['left'].append('changed')
        self.assertEqual(shared,[])
        self.assertEqual(result[1]['left'],[])
        shared.append('input-change')
        self.assertEqual(result[0]['left'],['changed'])

    def test_deepcopy_types_preserved_without_json_clone(self):
        self.assertEqual(distinct([(1,2),[1,2]]),[(1,2)])
        self.assertIsInstance(distinct([(1,2),[1,2]])[0],tuple)
        result=distinct([{1:'original'},{'1':'original'}])
        self.assertEqual(list(result[0]),[1])
        self.assertIs(type(next(iter(result[0]))),int)

    def test_singleton_does_not_introduce_a_comparison(self):
        nan=float('nan')
        result=distinct([nan])
        self.assertEqual(len(result),1)
        self.assertTrue(math.isnan(result[0]))
        opaque=b'not-json'
        self.assertEqual(distinct([opaque]),[opaque])

    def test_invalid_comparison_remains_rejected(self):
        with self.assertRaises(ValueError):distinct([float('nan'),float('nan')])
        with self.assertRaises(TypeError):distinct([dict(sequence=1),b'not-json'])

    def test_primitive_json_types_and_signed_zero_are_not_collapsed(self):
        result=distinct([True,1,1.0,False,0,-0.0,0.0,None,None])
        self.assertEqual([type(value) for value in result],
                         [bool,int,float,bool,int,float,float,type(None)])
        self.assertEqual(math.copysign(1,result[5]),-1)
        self.assertEqual(math.copysign(1,result[6]),1)


if __name__=='__main__':unittest.main()
