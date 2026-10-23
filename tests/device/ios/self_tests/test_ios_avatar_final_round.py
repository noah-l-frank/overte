"""One real historical traversal reuses typed originals, never live facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.adapters.avatar_final import IOSAvatarFinal,validation_round
from ios.self_tests import test_ios_avatar_final as fixture


class AvatarFinalRoundTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarFinalTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def capture(self,count=1):
        owner=self.f.owner();refs=[]
        for sequence in range(1,count+1):
            if refs:self.f.clock[0]+=1.6
            refs.append(self.f.capture(owner,sequence))
        return owner,refs

    def test_one_complete_round_reuses_each_original_group_and_restores_actual_read_membership(self):
        owner,refs=self.capture(3);expected=owner.quiet(refs,sequence=4);calls=[];method=IOSAvatarFinal._group
        started=time.monotonic();plain=self.f.archive(owner)
        self.assertEqual(expected,plain.quiet(refs,sequence=4));self.assertEqual(expected,plain.quiet(refs,sequence=4))
        uncached=time.monotonic()-started;native={s:len(c.f.calls) for s,c in self.f.cases.items()}
        def original(actual,value):calls.append(value['sequence']);return method(actual,value)
        started=time.monotonic()
        with patch.object(IOSAvatarFinal,'_group',new=original):
            with validation_round(),read_scope(fresh=True) as first:
                archived=self.f.archive(owner);self.assertEqual(expected,archived.quiet(refs,sequence=4))
                self.assertEqual(expected,archived.quiet(refs,sequence=4));self.assertEqual([1,2,3],calls)
                cached=time.monotonic()-started
                with read_scope(fresh=True) as distinct:
                    # A distinct original collector gets a complete independent
                    # decode, rather than claiming the previous collection.
                    self.assertEqual(expected,archived.quiet(refs,sequence=4))
                self.assertTrue(distinct);self.assertTrue(distinct<=first)
            before=len(calls)
            with validation_round():self.assertEqual(expected,self.f.archive(owner).quiet(refs,sequence=4))
            self.assertEqual(3,len(calls)-before)
        self.assertEqual(native,{s:len(c.f.calls) for s,c in self.f.cases.items()})
        print('Avatar final matched actual traversal seconds: '+str(dict(uncached=round(uncached,3),checked=round(cached,3))),flush=True)

    def test_same_inode_raw_original_change_refuses_reuse_without_new_native_queries(self):
        owner,refs=self.capture();before={s:len(c.f.calls) for s,c in self.f.cases.items()}
        with self.assertRaises(NativeUIError):
            with validation_round():
                archived=self.f.archive(owner);parts=archived.group(archived.record(refs[0]))['primary'];tail=parts['tail']
                paths=list(tail.root.glob('avatar-primary-tail-parts-*'));self.assertTrue(paths)
                path=paths[0];inode=path.stat().st_ino
                with path.open('ab') as stream:stream.write(b' ')
                self.assertEqual(inode,path.stat().st_ino)
                archived.group(archived.record(refs[0]))
        self.assertEqual(before,{s:len(c.f.calls) for s,c in self.f.cases.items()})

    def test_context_or_new_dangling_entry_cannot_reuse_a_previously_checked_group(self):
        owner,refs=self.capture()
        with self.assertRaises(NativeUIError):
            with validation_round():
                archived=self.f.archive(owner);value=archived.record(refs[0]);archived.group(value)
                archived.bindings['primary']['generation']+=1;archived.group(value)
        with self.assertRaises(NativeUIError):
            with validation_round():
                archived=self.f.archive(owner);value=archived.record(refs[0]);archived.group(value)
                path=archived.file(len(archived.state['rows'])+1).path;path.symlink_to('missing-original')
                archived.group(value)

    def test_mutated_checked_child_is_rejected_and_copied_output_cannot_poison_later_reads(self):
        owner,refs=self.capture()
        with self.assertRaises(NativeUIError):
            with validation_round():
                archived=self.f.archive(owner);value=archived.record(refs[0]);first=archived.group(value)
                prior=deepcopy(first['primary']['ui']);first['primary']['ui']['index']=999
                actual=archived.group(value);self.assertEqual(prior,actual['primary']['ui'])
                actual['primary']['tail'].state['rows']=[];archived.group(value)


if __name__=='__main__':unittest.main()
