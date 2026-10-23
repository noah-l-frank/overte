"""Immutable pure memory is neither a current source nor a live owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch

from adapters.chat_journey.original_memory import ChatOriginalMemory
from adapters.normal_ui import NativeUIError


class OriginalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.scope=dict(run='original',binding={'processIdentity':'123:456'})
        self.memory=ChatOriginalMemory(self.scope)
        self.value=dict(original={'rows':[1,2],'text':'Grüße'},available=True)
        self.memory.append(self.value,self.scope)

    def test_inspection_and_input_are_copies_and_single_row_never_decodes_whole_history(self):
        self.value['original']['rows'].append(3)
        for _index in range(4):self.memory.append({'later':True},self.scope)
        observed=self.memory.inspect();observed[0]['original']['rows'].append(4)
        import json
        with patch('adapters.chat_journey.original_memory.json.loads',wraps=json.loads) as loads:
            self.assertEqual([1,2],self.memory.row(0)['original']['rows'])
            self.assertEqual(1,loads.call_count)
            self.assertEqual(5,self.memory.count());self.assertEqual(1,loads.call_count)
        self.memory.control(self.scope)

    def test_same_value_replacement_tuple_is_not_adopted(self):
        self.memory.raws=tuple(list(self.memory.raws))
        with self.assertRaises(NativeUIError):self.memory.control(self.scope)

    def test_changed_bytes_are_hashed_even_with_coherently_replaced_tuple_pin(self):
        self.memory.raws=self.memory._raws=(self.memory.raws[0]+b' ',)
        with self.assertRaises(NativeUIError):self.memory.control(self.scope)

    def test_changed_hash_is_not_admitted(self):
        self.memory.hashes=self.memory._hashes=('0'*64,)
        with self.assertRaises(NativeUIError):self.memory.control(self.scope)

    def test_scope_cannot_be_rebound_even_if_new_raw_and_hash_match(self):
        self.memory.scope=self.memory._scope=b'{"foreign":true}'
        self.memory.scope_sha=hashlib.sha256(self.memory.scope).hexdigest()
        with self.assertRaises(NativeUIError):self.memory.control(self.scope)

    def test_source_aliases_are_rejected_before_freezing(self):
        class ForeignDict(dict):pass
        class ForeignList(list):pass
        for value in ({'alias':(1,2)},{'alias':ForeignDict(a=1)},{'alias':ForeignList([1])}):
            with self.subTest(value=value),self.assertRaises(NativeUIError):self.memory.append(value,self.scope)
        for scope in ([],ForeignDict(self.scope)):
            with self.subTest(scope=scope),self.assertRaises(NativeUIError):ChatOriginalMemory(scope)
        self.assertEqual(1,self.memory.count());self.memory.control(self.scope)

    def test_immutable_storage_type_and_byte_count_cannot_be_forged(self):
        class ForeignBytes(bytes):pass
        before=deepcopy(self.memory.__dict__)
        for value in (bytearray(self.memory.raws[0]),ForeignBytes(self.memory.raws[0])):
            self.memory.__dict__.update(before);self.memory.raws=self.memory._raws=(value,)
            with self.subTest(kind=type(value)),self.assertRaises(NativeUIError):self.memory.control(self.scope)
        self.memory.__dict__.update(before);self.memory.raw_bytes+=1
        with self.assertRaises(NativeUIError):self.memory.control(self.scope)


if __name__=='__main__':unittest.main()
