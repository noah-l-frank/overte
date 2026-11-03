"""Warm metadata must preserve the original closed JSON/canonical boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.pico4 import navigation_scene_metadata as metadata
from adapters.normal_ui import NativeUIError


class NavigationSceneMetadataTests(unittest.TestCase):
    def example(self):return dict(runId='a'*32,binding=dict(processIdentity='31:10001'),originals=[dict(physical=[1,2,3],ready=True)])
    def test_current_full_nested_metadata_mutation_is_refused(self):
        value=self.example();seal=metadata.NavigationMetadataSeal(value)
        value['originals'][0]['physical'][2]=4
        with self.assertRaises(NativeUIError):seal.require(value,seal.digest)
    def test_tuple_alias_cannot_replace_original_json_list(self):
        value=self.example();seal=metadata.NavigationMetadataSeal(value)
        value['originals'][0]['physical']=tuple(value['originals'][0]['physical'])
        with self.assertRaises(NativeUIError):seal.require(value,seal.digest)
    def test_subclass_cannot_replace_original_exact_json_types(self):
        class Changed(dict):pass
        value=self.example();seal=metadata.NavigationMetadataSeal(value);value['binding']=Changed(value['binding'])
        with self.assertRaises(NativeUIError):seal.require(value,seal.digest)
    def test_boolean_integer_alias_is_refused(self):
        value=self.example();seal=metadata.NavigationMetadataSeal(value);value['originals'][0]['ready']=1
        with self.assertRaises(NativeUIError):seal.require(value,seal.digest)
    def test_foreign_scope_and_foreign_expected_digest_are_refused(self):
        value=self.example();seal=metadata.NavigationMetadataSeal(value);foreign=deepcopy(value);foreign['runId']='b'*32
        with self.assertRaises(NativeUIError):seal.require(foreign,seal.digest)
        with self.assertRaises(NativeUIError):seal.require(value,metadata.json_digest(foreign))
    def test_replacement_equal_seal_tuple_is_refused(self):
        value=self.example();seal=metadata.NavigationMetadataSeal(value);seal.seal=tuple(v for v in seal.seal)
        with self.assertRaises(NativeUIError):seal.require(value,seal.digest)
    def test_canonical_unicode_alias_uses_original_validation_without_resealing(self):
        value={'\U0001f600':['\U0001f600']};seal=metadata.NavigationMetadataSeal(value);original=seal.seal
        alias={'\ud83d\ude00':['\ud83d\ude00']};old=metadata.json_digest
        with patch.object(metadata,'json_digest',wraps=old) as strict:seal.require(alias,seal.digest)
        self.assertEqual(1,strict.call_count);self.assertIs(original,seal.seal)
    def test_dict_order_and_unrelated_inspection_references_preserve_same_original(self):
        value=self.example();seal=metadata.NavigationMetadataSeal(value);references=[value,value['originals']]
        reordered=dict(reversed(list(value.items())))
        seal.require(reordered,seal.digest);self.assertIs(references[1],value['originals'])


if __name__=='__main__':unittest.main()
