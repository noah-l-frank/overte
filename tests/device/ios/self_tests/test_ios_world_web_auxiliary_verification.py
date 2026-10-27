"""Shared auxiliary projections retain actual byte and inode verification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from ios.adapters.world_web_original_parts import WorldWebOriginalParts
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebAuxiliaryVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.owner=SimpleNamespace(store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json'),binding=BINDING,
            run='a'*32,role='primary',guard=lambda:True,monotonic=lambda:1.,storage_intent=lambda *args:None,
            state=dict(pending=dict(start=dict(nativeBefore=dict(requestId='ios-'+secrets.token_hex(16))))))
        self.parts=WorldWebOriginalParts(self.owner)
        self.inputs=dict(widgetReceipt=dict(schemaVersion=1,commandId='actual-widget-query',observation=dict(shown=False)),
            uikit=dict(actualGeometry=17),browser=dict(actualReply=29))
        self.refs=self.parts.write_aux(1,self.inputs)
    def test_four_projections_execute_one_complete_actual_parent_reader_per_call(self):
        with patch.object(self.parts,'aux_original',wraps=self.parts.aux_original) as reader:
            self.parts.verify_frame(self.refs);self.assertEqual(1,reader.call_count)
            self.parts.verify_frame(self.refs);self.assertEqual(2,reader.call_count)
        changed=self.parts.read(self.refs['browser']);changed['actualReply']=999
        self.assertEqual(self.inputs['browser'],self.parts.read(self.refs['browser']))
    def test_independent_read_census_reopens_actual_parent_without_inferred_membership(self):
        parent=self.refs['browser']['parent'];expected=set(self.parts.paths(parent))
        with scope(fresh=True) as first:self.parts.verify_frame(self.refs)
        with scope(fresh=True) as second:
            self.assertFalse(second);self.parts.verify_frame(self.refs)
        self.assertIsNot(first,second);self.assertEqual(expected,first);self.assertEqual(expected,second)
    def test_changed_projection_name_index_or_parent_acquisition_cannot_share_a_success(self):
        for field,value in (('name','world'),('index',2),('acquisitionId','ios-'+'f'*32)):
            changed=deepcopy(self.refs);changed['browser'][field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.parts.verify_frame(changed)
    def test_same_bytes_replaced_inode_between_projections_refuses(self):
        parent=self.refs['browser']['parent'];path=self.parts.paths(parent)[0];actual=self.parts.aux_original
        def replaced(value):
            result=actual(value);temporary=path.with_suffix('.replacement')
            temporary.write_bytes(path.read_bytes());temporary.chmod(0o600);temporary.replace(path);return result
        with patch.object(self.parts,'aux_original',side_effect=replaced),self.assertRaises(NativeUIError):
            self.parts.verify_frame(self.refs)
    def test_changed_actual_chunk_or_malformed_typed_bundle_refuses(self):
        parent=self.refs['browser']['parent'];path=self.parts.paths(parent)[0]
        raw=path.read_bytes();path.write_bytes(raw.replace(b'world',b'other',1))
        with self.assertRaises(NativeUIError):self.parts.verify_frame(self.refs)
        malformed=self.parts.legacy.write('widgets',2,dict(actual='not an auxiliary bundle'))
        changed=deepcopy(self.refs['browser']);changed.update(index=2,parent=malformed)
        with self.assertRaises(NativeUIError):self.parts.verify_frame(dict(browser=changed))


if __name__=='__main__':unittest.main()
