"""Exact canonical sizing rejects foreign types before their callbacks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_namespace_bill as source
from adapters.script_journey.history import canonical
from self_tests import test_strict_json_digest as aliases


class StrictJsonSizeTests(unittest.TestCase):
    def refuse(self,value):
        with patch.object(source,'canonical',side_effect=AssertionError('No encoding for foreign types')):
            with self.assertRaises(NativeUIError):source.canonical_size(value)

    def test_deceptive_container_and_numeric_types_never_invoke_foreign_equality_or_iteration(self):
        for base,value in ((list,[1]),(dict,{'value':(1,)}),(str,'original'),(int,1),(float,1.5)):
            operations=[];alias=aliases.StrictJsonDigestTests.alias(self,base,value,operations)
            with self.subTest(base=base.__name__):self.refuse(alias)
            self.assertEqual([],operations)

    def test_nested_alias_and_nonstring_or_subclass_keys_are_not_sized_as_plain_json(self):
        operations=[];alias=aliases.StrictJsonDigestTests.alias(self,list,[],operations)
        self.refuse({'original':[alias]})
        key=aliases.StrictJsonDigestTests.alias(self,str,'key',operations)
        for field in (1,True,key):self.refuse({field:'original'})
        self.assertEqual([],operations)

    def test_plain_values_and_escaping_keep_exact_original_canonical_byte_extent(self):
        shared=[None,True,False,-12,-0.0,1e200]
        for value in (shared,{'first':shared,'second':shared},'\x00\b\f\n\r\t\x7f"\\ Ω \U0001f600','\ud83d\ude00'):
            with self.subTest(kind=type(value).__name__):
                self.assertEqual(len(canonical(value)),source.canonical_size(value))

    def test_exact_existing_limit_and_one_byte_short_limit_remain_distinct(self):
        value={'original':['x'*100,None]};size=len(canonical(value))
        self.assertEqual(size,source.canonical_size(value,size))
        with self.assertRaises(NativeUIError):source.canonical_size(value,size-1)

    def test_tuple_cycle_and_nonfinite_values_still_refuse(self):
        self.refuse({'tuple':(1,2)})
        cycle=[];cycle.append(cycle)
        with self.assertRaises(NativeUIError):source.canonical_size(cycle)
        for value in (float('nan'),float('inf')):
            with self.assertRaises(ValueError):source.canonical_size(value)


if __name__=='__main__':unittest.main()
