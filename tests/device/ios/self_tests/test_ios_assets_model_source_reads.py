"""Same-call raw dataflow; actual file guards and custom hooks still execute."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_model_sources as sources
from ios.self_tests.test_ios_assets_model_sources import AssetsModelSourcesTests


class AssetsModelSourceReadOnceTests(unittest.TestCase):
    setUp=AssetsModelSourcesTests.setUp
    capture=AssetsModelSourcesTests.capture

    def test_each_call_reads_every_actual_raw_once_and_decodes_each_matching_carrier_once(self):
        frame=self.capture();count=len(frame['rawRefs']);native=deepcopy(self.b.native_clock.commands);inputs=deepcopy(self.b.inputs)
        before={path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.iterdir() if path.is_file()}
        for _attempt in range(2):
            with (patch.object(self.o.raws,'read_record',wraps=self.o.raws.read_record) as records,
                    patch.object(sources,'decode',wraps=sources.decode) as packets,
                    patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure frame write'))):
                self.assertEqual(frame,self.o.frame(frame));self.assertEqual(count,records.call_count);self.assertEqual(count,packets.call_count)
        self.assertEqual(native,self.b.native_clock.commands);self.assertEqual(inputs,self.b.inputs)
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.iterdir() if path.is_file()})

    def test_custom_pending_hook_and_foreign_nonce_query_or_changed_original_still_refuse_or_execute(self):
        frame=self.capture();count=len(frame['rawRefs']);native=deepcopy(self.b.native_clock.commands)
        with (patch.object(self.o,'pending',wraps=self.o.pending) as pending,
                patch.object(self.o.raws,'read_record',wraps=self.o.raws.read_record) as records):
            self.assertEqual(frame,self.o.frame(frame));pending.assert_called_once();self.assertEqual(2*count,records.call_count)
        changed=deepcopy(frame);changed['queries'][0]['command']['commandId']='ios-'+'f'*32
        with self.assertRaises(NativeUIError):self.o.frame(changed)
        read=self.o.raws.read_record
        def foreign(reference):
            record=read(reference);packet=json.loads(record['raw']);packet['requestId']='ios-'+'e'*32
            record['raw']=json.dumps(packet);return record
        with patch.object(self.o.raws,'read_record',side_effect=foreign),self.assertRaises(NativeUIError):self.o.frame(frame)
        path=self.o.raws.store.path(self.o.raws.store.expand(frame['rawRefs'][0]));original=path.read_bytes();inode=path.stat().st_ino
        try:
            path.write_bytes(b'{}')
            with self.assertRaises(NativeUIError):self.o.frame(frame)
        finally:path.write_bytes(original)
        self.assertEqual(inode,path.stat().st_ino);self.assertEqual(frame,self.o.frame(frame));self.assertEqual(native,self.b.native_clock.commands)

    def test_class_pending_hook_is_never_bypassed_by_local_record_reuse(self):
        frame=self.capture();original=sources.AssetsModelSources.pending;calls=[]
        def hook(owner,*args):calls.append(owner);return original(owner,*args)
        with patch.object(sources.AssetsModelSources,'pending',hook):self.assertEqual(frame,self.o.frame(frame))
        self.assertEqual([self.o],calls)
