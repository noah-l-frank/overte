"""Closed World v2 bytes and original v1 operation compatibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import lzma
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_world_codec as codec
from adapters.pico4.lifecycle_process import archived,original_snapshot
from adapters.script_journey import history
from self_tests import test_pico_lifecycle_world as fixture


def raw_payload(raw):
    return dict(encoding='xz-base64-json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
        data=base64.b64encode(lzma.compress(raw,format=lzma.FORMAT_XZ,preset=3)).decode())


class LifecycleWorldCodecTests(unittest.TestCase):
    def setUp(self):self.frames=[dict(text='Unicode: Grüße 🐧',empty=[],values=[None,True,False,1,1.5])]

    def test_complete_canonical_bytes_roundtrip_and_legacy_codec_remain_distinct(self):
        for version,encoding in ((1,'zlib-base64-json'),(2,'xz-base64-json')):
            with self.subTest(version=version):
                value=codec.pack(self.frames,version)
                self.assertEqual(encoding,value['encoding']);self.assertEqual(self.frames,codec.unpack(value,version))
                self.assertEqual(hashlib.sha256(history.canonical(self.frames)).hexdigest(),value['sha256'])
                with self.assertRaises(NativeUIError):codec.unpack(value,3-version)
        self.assertEqual(history.pack(self.frames),codec.pack(self.frames,1))

    def test_version_and_metadata_aliases_are_refused(self):
        for version in (True,False,0,3,2.0,'2'):
            with self.subTest(version=version),self.assertRaises(NativeUIError):codec.pack(self.frames,version)
        original=codec.pack(self.frames,2)
        for key,value in (('bytes',True),('bytes',2.),('bytes',history.MAX_RAW+1),('sha256','a'*63),
                          ('encoding','zlib-base64-json'),('data',original['data']+'\n')):
            changed=deepcopy(original);changed[key]=value
            with self.subTest(key=key,value=str(value)[:30]),self.assertRaises(NativeUIError):codec.unpack(changed,2)
        changed=deepcopy(original);changed['extra']=None
        with self.assertRaises(NativeUIError):codec.unpack(changed,2)

    def test_json_type_aliases_and_cycles_cannot_enter_new_storage(self):
        class Dict(dict):pass
        for value in (({'row':1},),[Dict(row=1)],[{1:'integer-key'}],[dict(row=(1,2))],[float('nan')]):
            with self.subTest(value=repr(value)),self.assertRaises(NativeUIError):codec.pack(value,2)
        value=[];value.append(value)
        with self.assertRaises(NativeUIError):codec.pack(value,2)

    def test_raw_packed_and_top_level_frame_limits_are_unchanged(self):
        with self.assertRaises(NativeUIError):codec.pack(['a'*history.MAX_RAW],2)
        with self.assertRaises(NativeUIError):codec.pack([None]*(history.MAX_FRAMES+1),2)
        incompressible=''.join(hashlib.sha256(str(index).encode()).hexdigest() for index in range(2000))
        with self.assertRaises(NativeUIError):codec.pack([incompressible],2)
        value=codec.pack(self.frames,2);value['data']='A'*(history.MAX_PACKED+4)
        with self.assertRaises(NativeUIError):codec.unpack(value,2)

    def test_truncated_concatenated_trailing_and_wrong_length_streams_are_refused(self):
        value=codec.pack(self.frames,2);compressed=base64.b64decode(value['data'])
        for changed in (compressed[:-1],compressed+b'tail',compressed+compressed):
            bad=deepcopy(value);bad['data']=base64.b64encode(changed).decode()
            with self.subTest(size=len(changed)),self.assertRaises(NativeUIError):codec.unpack(bad,2)
        for size in (value['bytes']-1,value['bytes']+1):
            bad=deepcopy(value);bad['bytes']=size
            with self.subTest(size=size),self.assertRaises(NativeUIError):codec.unpack(bad,2)
        bad=deepcopy(value);bad['sha256']='0'*64
        with self.assertRaises(NativeUIError):codec.unpack(bad,2)

    def test_duplicate_keys_noncanonical_json_and_nonlist_payloads_are_refused(self):
        for raw in (b'[{"a":1,"a":1}]',b'[{"a":1,"\\u0061":1}]',b'[ {"a":1}]',b'{"a":1}',b'[NaN]'):
            with self.subTest(raw=raw),self.assertRaises(NativeUIError):codec.unpack(raw_payload(raw),2)

    def test_real_decoder_memory_limit_is_enforced(self):
        value=codec.pack(self.frames,2);self.assertEqual(self.frames,codec.unpack(value,2))
        self.assertEqual(16*1024*1024,codec.MEMORY_LIMIT)
        with patch.object(codec,'MEMORY_LIMIT',256*1024),self.assertRaises(NativeUIError):codec.unpack(value,2)


class LifecycleWorldCodecOwnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.LifecycleWorldTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)

    def test_new_v2_owner_and_actual_cold_history_preserve_original_rows_and_snapshots(self):
        owner=self.fixture.started();self.assertEqual(2,owner.disk['lifecycleWorldOwnerVersion'])
        owner.world_input();owner.release();saved=deepcopy(owner.disk)
        current=self.fixture.owner();self.assertEqual(saved,current.disk)
        self.assertEqual(owner.state,current.state);self.assertEqual(saved,original_snapshot(archived(saved)))
        before=len(current.state['frames'])
        with current.lock.held():current.current()
        self.assertEqual(before+1,len(current.state['frames']));self.assertEqual(2,current.disk['lifecycleWorldOwnerVersion'])
        self.assertEqual(saved['payload']['encoding'],current.disk['payload']['encoding'])

    def test_original_v1_owner_retains_codec_and_permitted_operations_without_migration(self):
        # Select the unchanged legacy producer before any owner exists; never
        # rewrite a live v2 file to manufacture a legacy original.
        with patch('adapters.pico4.lifecycle_world.VERSION',1):owner=self.fixture.started()
        first=owner.store.path.read_bytes();saved=deepcopy(owner.disk)
        current=self.fixture.owner();self.assertEqual(first,current.store.path.read_bytes())
        self.assertEqual(saved,current.disk);self.assertEqual(saved,original_snapshot(archived(saved)))
        current.world_input();current.release()
        self.assertEqual(1,current.disk['lifecycleWorldOwnerVersion'])
        self.assertEqual('zlib-base64-json',current.disk['payload']['encoding'])
        self.assertEqual(1,self.fixture.owner().reconcile()['worldAttempts'])

    def test_v2_cross_version_codec_relabel_is_rejected_before_source_query(self):
        owner=self.fixture.started();disk=deepcopy(owner.disk)
        disk['lifecycleWorldOwnerVersion']=1;owner.store.write(disk,owner.disk)
        before=[len(item.commands) for item in (self.fixture.native.ui,self.fixture.native.axes,self.fixture.native.drive)]
        with self.assertRaises(NativeUIError):self.fixture.owner()
        self.assertEqual(before,[len(item.commands) for item in (self.fixture.native.ui,self.fixture.native.axes,self.fixture.native.drive)])


if __name__=='__main__':unittest.main()
