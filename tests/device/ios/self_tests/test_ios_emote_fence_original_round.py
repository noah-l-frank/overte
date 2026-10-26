"""Real local fence originals; declared Qt/native producers, no paired end claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as file_reads
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters import emote_native_prefix,emote_rooted_fence_original as fence
from ios.self_tests.test_ios_emote_rooted_fence_original import RootedFenceOriginalTests


class FenceOriginalRoundTests(unittest.TestCase):
    def setUp(self):
        self.f=RootedFenceOriginalTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.scope.root
    def pins(self):
        result={}
        for path in self.root.iterdir():
            if path.is_file():
                info=path.stat();result[path.name]=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
        return result
    def test_shared_pure_successes_preserve_literal_reads_and_do_not_survive_return(self):
        calls=[];real=emote_native_prefix._follow;before=self.pins();actions=deepcopy(self.f.f.domain.io.actions);sequences=deepcopy(self.f.f.domain.sequences)
        def validated(*arguments):calls.append(None);return real(*arguments)
        with patch.object(emote_native_prefix,'_follow',validated):
            with file_reads(fresh=True) as first:result=self.f.decoded()
            first_calls=len(calls);self.assertGreater(first_calls,0)
            result['keys'].state['records'].clear()
            with file_reads(fresh=True) as second:again=self.f.decoded()
            self.assertTrue(again['keys'].state['records']);self.assertEqual(first,second)
            self.assertEqual(first_calls,len(calls)-first_calls)
            previous=len(calls);scope=self.f.scope
            with file_reads(fresh=True) as literal:
                baseline=fence._local(self.f.value,self.f.copies,root=scope.root,binding=scope.binding,run=scope.run,role=scope.role,lock=scope.lock)
            self.assertGreater(len(calls)-previous,first_calls);self.assertEqual(literal,first)
            self.assertEqual(baseline['metadata'],again['metadata'])
        self.assertEqual(before,self.pins());self.assertEqual(actions,self.f.f.domain.io.actions);self.assertEqual(sequences,self.f.f.domain.sequences)
        self.assertTrue(any(path.name.startswith('emote-keys-') for path in first))

    def changed_on_repeat(self,mutate):
        seen=set();changed=[];real=IOSEmoteKeys.original
        def original(owner,reference):
            key=(str(owner.store.path),reference['index'],reference['sha256'])
            if owner.historical and key in seen and not changed:
                mutate(owner,reference);changed.append(key)
            seen.add(key);return real(owner,reference)
        with patch.object(IOSEmoteKeys,'original',original),self.assertRaises((NativeUIError,OSError)):
            self.f.decoded()
        self.assertEqual(1,len(changed))
    def test_same_inode_same_bytes_and_restored_mtime_invalidates_the_read_batch(self):
        def rewrite(owner,reference):
            path=owner.file(reference['index']).path;before=path.stat();path.write_bytes(path.read_bytes())
            os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
            self.assertEqual(before.st_ino,path.stat().st_ino);self.assertEqual(before.st_mtime_ns,path.stat().st_mtime_ns)
        self.changed_on_repeat(rewrite)
    def test_original_deletion_invalidates_the_read_batch(self):
        self.changed_on_repeat(lambda owner,reference:owner.file(reference['index']).path.unlink())
    def test_new_unknown_carrier_invalidates_the_complete_inventory_before_return(self):
        self.changed_on_repeat(lambda owner,reference:(self.root/'ios-emote-unowned.json').write_text('{"unknown":true}\n'))


if __name__=='__main__':unittest.main()
