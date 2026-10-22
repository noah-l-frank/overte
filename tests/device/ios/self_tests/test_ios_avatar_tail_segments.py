"""Real bounded private byte carriers, interrupted inodes and exact reconstruction."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from ios.adapters.avatar_tail_segments import AvatarTailSegments,CHUNK_BYTES
from ios.self_tests.test_ios_avatar_input_owner import BINDING
from ios.self_tests.test_ios_world_web_keys import RUN


class AvatarTailSegmentsTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.root.chmod(0o700);self.parents=[]
        self.owner=self.make();self.tag=hashlib.sha256(b'actual-native-query').hexdigest()
    def make(self,subject='primary'):
        return AvatarTailSegments(self.root,BINDING,RUN,'primary',subject,lambda:True,lambda value:self.parents.append(deepcopy(value)),monotonic=lambda:0.)
    def test_two_mebibyte_actual_bytes_have_four_real_bounded_original_files(self):
        raw=os.urandom(2*1024*1024);parent=self.owner.write('uikit',self.tag,raw,1)
        self.assertEqual(4,len(parent['chunks']));self.assertEqual(raw,self.owner.read(parent))
        for ref in parent['chunks']:
            path=self.owner.store.path(ref);self.assertLess(path.stat().st_size,1024*1024);self.assertEqual(0o600,path.stat().st_mode&0o777)
        self.assertEqual([],self.parents[0]['chunks']);self.assertFalse(self.parents[0]['complete']);self.assertTrue(self.parents[-1]['complete'])
        with scope(fresh=True) as actual:self.assertEqual(raw,self.owner.read(parent))
        self.assertEqual({self.owner.store.path(ref) for ref in parent['chunks']},actual)
    def test_largest_valid_uikit2_callback_original_near_native_limit_uses_exact_segments(self):
        from ios.adapters import uikit_input
        from ios.self_tests.avatar_uikit_fixture import UIKit2Boundary
        from ios.self_tests.test_ios_uikit_input import query
        def actual(count):
            clock=[90000];boundary=UIKit2Boundary(lambda:clock[0],lambda:clock[0]-80000)
            for _ in range(count):clock[0]+=1;boundary.touch(lambda:None)
            # A fresh version2 producer owns its original lifecycle before
            # its first emitted packet; no old DTO is retimed or relabelled.
            value=boundary.packet(query());return value,json.dumps(value,separators=(',',':')).encode()
        low,high,last=0,2048,None
        while low<=high:
            count=(low+high)//2;candidate=actual(count)
            if len(candidate[1])<=uikit_input.LIMIT:last=candidate;low=count+1
            else:high=count-1
        self.assertIsNotNone(last);value,raw=last
        self.assertGreater(len(raw),uikit_input.LIMIT-8192)
        uikit_input.original(value);self.assertFalse(value['pendingDispatches'])
        parent=self.owner.write('uikit',self.tag,raw,1);self.assertEqual(4,len(parent['chunks']))
        actual=self.owner.read(parent);self.assertEqual(raw,actual);self.assertEqual(value,json.loads(actual))
        uikit_input.original(json.loads(actual))

    def test_actual_opened_empty_prefix_is_retained_and_never_treated_as_complete(self):
        callback=self.owner.intent
        def lost(value):
            callback(value)
            if value['chunks'] and value['chunks'][-1]['phase']=='opened':raise OSError('Opened actual part return lost')
        self.owner.intent=lost
        with self.assertRaises(OSError):self.owner.write('uikit',self.tag,b'actual-native-bytes',1)
        parent=self.parents[-1];ref=parent['chunks'][0];path=self.owner.store.path(ref);inode=path.stat().st_ino
        self.assertEqual([dict(bytes=0,sha256=hashlib.sha256(b'').hexdigest(),complete=False)],self.owner.inspect(parent))
        with self.assertRaises(NativeUIError):self.owner.read(parent)
        self.assertEqual(inode,path.stat().st_ino);self.assertEqual(b'',path.read_bytes())
    def test_complete_opened_last_part_can_be_read_without_a_saved_ack_or_rewrite(self):
        with patch('adapters.original_frame_store.os.fsync',side_effect=OSError('Actual complete part flush return lost')),self.assertRaises(OSError):self.owner.write('uikit',self.tag,b'{}',1)
        parent=self.parents[-1];self.assertEqual('opened',parent['chunks'][0]['phase']);self.assertFalse(parent['complete'])
        self.assertEqual(b'{}',self.owner.read(parent));self.assertTrue(self.owner.inspect(parent)[0]['complete'])
    def test_different_subject_parent_hash_offset_or_hardlink_cannot_relabel_parts(self):
        parent=self.owner.write('uikit',self.tag,os.urandom(CHUNK_BYTES+1),1)
        for key,value in (('sha256','0'*64),('tag','0'*64),('bytes',parent['bytes']-1)):
            bad=deepcopy(parent);bad[key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.owner.read(bad)
        with self.assertRaises((NativeUIError,FileNotFoundError)):self.make('actor').read(parent)
        path=self.owner.store.path(parent['chunks'][0]);os.link(path,self.root/'foreign-hardlink')
        with self.assertRaises(NativeUIError):self.owner.read(parent)
    def test_retained_empty_opened_prefix_rejects_same_inode_append_and_truncate(self):
        callback=self.owner.intent
        def lost(value):
            callback(value)
            if value['chunks'] and value['chunks'][-1]['phase']=='opened':raise OSError('Real opened prefix lost')
        self.owner.intent=lost
        with self.assertRaises(OSError):self.owner.write('uikit',self.tag,b'{}',1)
        parent=self.parents[-1];snapshot=self.owner.inspect(parent);self.owner.retained(parent,snapshot)
        path=self.owner.store.path(parent['chunks'][0]);inode=path.stat().st_ino;path.write_bytes(b'{')
        self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.owner.retained(parent,snapshot)
        appended=self.owner.inspect(parent);path.write_bytes(b'')
        with self.assertRaises(NativeUIError):self.owner.retained(parent,appended)

    def test_planned_dangling_symlink_is_not_original_absence(self):
        callback=self.owner.intent
        def lost(value):
            callback(value)
            if value['chunks'] and value['chunks'][-1]['phase']=='planned':raise OSError('Planned actual part stopped')
        self.owner.intent=lost
        with self.assertRaises(OSError):self.owner.write('uikit',self.tag,b'{}',1)
        parent=self.parents[-1];path=self.owner.store.path(parent['chunks'][0]);os.symlink(self.root/'missing-original',path)
        self.assertFalse(path.exists())
        with self.assertRaises(NativeUIError):self.owner.inspect(parent)


if __name__=='__main__':unittest.main()
