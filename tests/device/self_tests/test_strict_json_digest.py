"""Exact JSON DTO types without invoking foreign type/iterator callbacks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

from adapters.chat_journey import source_chunks as source
from adapters.normal_ui import NativeUIError


class StrictJsonDigestTests(unittest.TestCase):
    def alias(self,base,value,operations):
        class EqualityAlias(type):
            def __eq__(cls,other):
                operations.append('equality');return other is base
        def forbidden_iteration(_self):
            operations.append('iteration');raise AssertionError('Foreign iteration')
        kind=EqualityAlias('Alias',(base,),dict(__iter__=forbidden_iteration))
        return kind(value)

    def refuse(self,value):
        with patch.object(source,'digest',side_effect=AssertionError('No encoding before exact-type admission')):
            with self.assertRaises(NativeUIError):source.json_digest(value)

    def test_deceptive_container_and_scalar_types_refuse_before_foreign_equality_iteration_or_encoding(self):
        for base,value in ((list,[1]),(dict,{'field':(1,)}),(str,'original'),(int,1),(float,1.5)):
            operations=[];alias=self.alias(base,value,operations)
            with self.subTest(base=base.__name__):self.refuse(alias)
            self.assertEqual([],operations)

    def test_nested_deceptive_alias_does_not_inherit_plain_container_admission(self):
        operations=[];value={'original':[{'nested':self.alias(list,[1,2],operations)}]}
        self.refuse(value);self.assertEqual([],operations)

    def test_nonstring_and_string_subclass_keys_refuse_before_encoding_or_type_equality(self):
        operations=[];alias=self.alias(str,'key',operations)
        for key in (1,True,alias):
            with self.subTest(key_type=type(key).__name__):self.refuse({key:'original'})
        self.assertEqual([],operations)

    def test_plain_json_types_and_repeated_container_references_keep_original_digest(self):
        shared=[None,True,False,0,-12,1.5,'original Ω \U0001f600']
        value={'second':shared,'first':{'data':shared}}
        self.assertEqual(source.digest(value),source.json_digest(value))
        self.assertEqual(source.json_digest(value),source.json_digest({'first':{'data':list(shared)},'second':list(shared)}))

    def test_tuple_nonfinite_and_cycle_keep_original_refusal(self):
        self.refuse({'tuple':(1,2)})
        for value in (float('nan'),float('inf')):
            with self.assertRaises(ValueError):source.json_digest(value)
        cycle=[];cycle.append(cycle)
        with self.assertRaises(ValueError):source.json_digest(cycle)


if __name__=='__main__':unittest.main()
