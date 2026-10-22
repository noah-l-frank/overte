"""Actual private immutable large carriers; native key producers are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from adapters.original_key_packets import OriginalKeyPackets
from ios.self_tests.test_ios_world_web_keys import QtKeys,RUN
from ios.self_tests.test_ios_avatar_input_owner import BINDING
from ios.adapters import world_web_keys


class OriginalKeyPacketTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.root.chmod(0o700);self.intents=[]
        self.owner=OriginalKeyPackets(self.root,BINDING,RUN,'primary','primary',lambda:True,lambda kind,value:self.intents.append((kind,deepcopy(value))),profile='avatar')
    def carrier(self,large=False):
        qt=QtKeys()
        if large:
            for _ in range(240):qt.finish(qt.enter('key-press'));qt.finish(qt.enter('key-release'))
        packet=qt.packet();query=dict(schemaVersion=1,commandId=packet['requestId'],action=world_web_keys.ACTION,runId=RUN)
        return packet,query,json.dumps(packet,separators=(',',':'))
    def test_actual_large_original_uses_private_file_and_preserves_native_DTO_and_all_storage_phases(self):
        packet,query,raw=self.carrier(True);self.assertGreater(len(raw.encode()),400000)
        with self.assertRaises(NativeUIError):decode(raw)
        ref=self.owner.write(1,query,raw);self.assertEqual(packet,self.owner.packet(self.intents[-1][1]));self.assertEqual(raw,self.owner.read(self.intents[-1][1])['raw'])
        self.assertEqual(['planned','opened','saved'],[row['phase'] for _,row in self.intents]);self.assertEqual(packet,self.owner.packet(ref))
        self.assertEqual(0o600,self.owner.originals.path(self.intents[-1][1]).stat().st_mode&0o777)
        partial=self.owner.inspect_partial(ref);self.assertTrue(partial['complete']);self.assertEqual(ref['file'],partial['file'])
    def test_historical_profile_subject_context_and_actual_inodes_cannot_be_relabelled(self):
        packet,query,raw=self.carrier();self.owner.write(1,query,raw);ref=self.intents[-1][1]
        for profile,subject in (('emote','primary'),('worldweb','primary'),('avatar','actor')):
            other=OriginalKeyPackets(self.root,BINDING,RUN,'primary',subject,lambda:True,lambda *_:self.fail('Historical read must not write'),profile=profile)
            with self.subTest(profile=profile,subject=subject),self.assertRaises(NativeUIError):other.packet(ref)
        path=self.owner.originals.path(ref);(self.root/'foreign-hardlink').hardlink_to(path)
        with self.assertRaises(NativeUIError):self.owner.packet(ref)
    def test_actual_opened_partial_or_complete_inode_is_inspectable_after_lost_writer_return(self):
        _packet,query,raw=self.carrier();callback=self.owner.originals.intent
        def opened(kind,value):
            callback(kind,value)
            if value['phase']=='opened':raise OSError('Lost opened writer return')
        self.owner.originals.intent=opened
        with self.assertRaises(OSError):self.owner.write(1,query,raw)
        original=self.intents[-1][1];path=self.owner.originals.path(original);inode=path.stat().st_ino
        value=self.owner.inspect_partial(original);self.assertEqual(0,value['bytes']);self.assertFalse(value['complete'])
        with self.assertRaises(NativeUIError):self.owner.packet(original)
        self.assertEqual(inode,path.stat().st_ino);self.owner.originals.intent=callback
        with patch('adapters.original_frame_store.os.fsync',side_effect=OSError('Lost complete file flush return')),self.assertRaises(OSError):self.owner.write(2,query,raw)
        original=self.intents[-1][1];self.assertEqual('opened',original['phase']);self.assertTrue(self.owner.inspect_partial(original)['complete'])
        self.assertEqual(json.loads(raw),self.owner.packet(original))

    def test_malformed_or_foreign_nonce_bytes_are_refused_before_any_host_original_is_created(self):
        packet,query,raw=self.carrier();packet['requestId']='ios-'+'f'*32
        with self.assertRaises(NativeUIError):self.owner.write(1,query,json.dumps(packet))
        with self.assertRaises(ValueError):self.owner.write(2,query,'{')
        self.assertEqual([],self.intents);self.assertEqual([],list(self.root.iterdir()))

    def test_legacy_raw_is_readable_but_a_stale_unsafe_afc_response_is_never_written_by_the_new_owner(self):
        from ios.self_tests.test_ios_world_web_keys import LegacyQtKeys
        producer=LegacyQtKeys();producer.finish(producer.enter('input-method',commit='dummy-private-login'))
        packet=producer.packet();query=dict(schemaVersion=1,commandId=packet['requestId'],action=world_web_keys.ACTION,runId=RUN)
        raw=json.dumps(packet)
        with self.assertRaises(NativeUIError):self.owner.write(1,query,raw)
        self.assertEqual([],self.intents);self.assertEqual([],list(self.root.iterdir()))
        # This is the actual former raw writer, before its first file exists.
        # Read compatibility retains version 1; no old packet is relabelled.
        compact=self.owner.originals.write(1,dict(nativeKeysRawVersion=1,profile='avatar',runId=RUN,role='primary',
            subject='primary',binding=BINDING,query=query,raw=raw));ref=self.owner.originals.expand(compact)
        self.assertEqual(packet,self.owner.packet(ref))
        with self.assertRaises(NativeUIError):world_web_keys.privacy_qualified(self.owner.packet(ref))

    def test_actual_saved_inner_context_cannot_replace_an_integer_generation_with_a_boolean(self):
        _packet,query,raw=self.carrier();binding=deepcopy(BINDING)
        self.assertEqual(1,binding['generation']);binding['generation']=True
        compact=self.owner.originals.write(1,dict(nativeKeysRawVersion=1,profile='avatar',runId=RUN,role='primary',
            subject='primary',binding=binding,query=query,raw=raw))
        with self.assertRaises(NativeUIError):self.owner.read(self.owner.originals.expand(compact))


if __name__=='__main__':unittest.main()
