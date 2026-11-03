"""Exact existing text grammar over Unicode and length/type boundaries.

The old predicate below is the actual source expression. No UI packet, input,
original byte read, ownership requirement or image/native fact is replaced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_controls import text


def original_predicate(value,limit=4096):
    return type(value) is str and len(value)<=limit and all(ord(char)>=32 and ord(char)!=127 for char in value)


class AssetsControlsTextTests(unittest.TestCase):
    def equivalent(self,value,limit):
        try:result=text(value,limit);accepted=True
        except NativeUIError:result=None;accepted=False
        self.assertEqual(original_predicate(value,limit),accepted)
        if accepted:self.assertIs(value,result)
    def test_every_Unicode_codepoint_matches_actual_original_predicate_including_surrogates_and_C1(self):
        for codepoint in range(0x110000):self.equivalent(chr(codepoint),1)
    def test_mixed_text_exact_length_types_C0_DEL_and_allowed_Unicode_keep_literal_boundaries(self):
        class StringSubclass(str):pass
        for value in ('','a','asset/renamed-file.gltf','ä Ω 東京','\u0080\u009f','\ud800\udfff',
                'before\x00after','before\x1fafter','before\x7fafter','a'*4095,'a'*4096,'a'*4097,
                None,False,42,b'asset',StringSubclass('asset')):
            for limit in (0,1,31,64,4095,4096,4097):
                with self.subTest(valueType=type(value).__name__,length=len(value) if isinstance(value,(str,bytes)) else None,limit=limit):self.equivalent(value,limit)


if __name__=='__main__':unittest.main()
