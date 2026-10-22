"""Large original bytes retain actual file hashes/inodes without widening pack."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters.world_web_parts import WorldWebParts
from ios.self_tests.test_ios_create_files import BINDING


class WorldWebPartsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700);self.intents=[]
        pending=dict(start=dict(nativeBefore=dict(requestId='ios-'+secrets.token_hex(16))))
        self.owner=SimpleNamespace(store=PrivateFeatureState(self.root/'ios-world-web-primary-sources.json'),binding=BINDING,run='a'*32,role='primary',
            guard=lambda:True,monotonic=lambda:1.,state=dict(pending=pending),storage_intent=lambda *args:self.intents.append(deepcopy(args)))
        self.parts=WorldWebParts(self.owner)
    def test_large_incompressible_original_exceeds_old_pack_and_roundtrips_actual_inode_bound_chunks(self):
        value=dict(original=secrets.token_hex(350000),sequence=71)
        with self.assertRaises(NativeUIError):pack([value])
        ref=self.parts.write('ledgerAfter',1,value);self.assertEqual(2,len(ref['chunks']));self.assertEqual(value,self.parts.read(ref))
        returned=self.parts.read(ref);returned['sequence']=999;self.assertEqual(71,self.parts.read(ref)['sequence'])
        self.assertEqual(['planned','opened','saved']*2,[row[2]['phase'] for row in self.intents])
    def test_four_actual_512k_chunks_keep_full_original_envelopes_below_unchanged_ofs_1mib(self):
        # JSON escaping expands the native value, then base64 adds 4/3. Test
        # actual written OFS envelopes, not just raw chunk payload length.
        value=dict(original=('"\\\n' * 300000))
        ref=self.parts.write('ledgerBefore',1,value);self.assertEqual(4,len(ref['chunks']))
        sizes=[]
        for compact in ref['chunks']:
            store=self.parts.store('ledgerBefore');original=store.expand(compact);path=store.path(original)
            sizes.append(path.stat().st_size);self.assertEqual(original['bytes'],path.stat().st_size)
            self.assertLess(path.stat().st_size,1048576)
        self.assertEqual(value,self.parts.read(ref));self.assertGreater(max(sizes),512*1024)
        self.actual_envelope_sizes=sizes

    def test_identical_value_at_an_interrupted_same_index_uses_distinct_original_acquisition_and_never_overwrites(self):
        first=self.parts.write('document',1,None);old=[path for path in self.root.iterdir()]
        self.owner.state['pending']['start']['nativeBefore']['requestId']='ios-'+secrets.token_hex(16)
        second=self.parts.write('document',1,None);self.assertNotEqual(first['chunks'],second['chunks']);self.assertIsNone(self.parts.read(first));self.assertIsNone(self.parts.read(second))
        self.assertTrue(all(path.exists() for path in old))
    def test_changed_actual_chunk_bytes_or_replaced_inode_refuse_even_with_identical_public_value(self):
        for fault in ('bytes','inode'):
            with self.subTest(fault=fault):
                ref=self.parts.write('world',1,dict(value=fault));store=self.parts.store('world');path=store.path(store.expand(ref['chunks'][0]));raw=path.read_bytes()
                if fault=='bytes':path.write_bytes(raw.replace(b'world',b'other',1))
                else:
                    previous=path.with_name(path.name+'.original');path.rename(previous);path.write_bytes(raw);path.chmod(0o600)
                with self.assertRaises(NativeUIError):self.parts.read(ref)
    def test_foreign_reference_chunk_order_or_acquisition_header_cannot_substitute_saved_original(self):
        ref=self.parts.write('entities',1,dict(original=secrets.token_hex(350000)))
        for fault in ('order','name','acquisition'):
            changed=deepcopy(ref)
            if fault=='order':changed['chunks'].reverse()
            elif fault=='name':changed['name']='world'
            else:changed['acquisitionId']='ios-'+secrets.token_hex(16)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,FileNotFoundError)):self.parts.read(changed)


if __name__=='__main__':unittest.main()
