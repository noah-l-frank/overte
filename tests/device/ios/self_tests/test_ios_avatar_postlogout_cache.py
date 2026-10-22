"""Exact typed AccountReads originals remain checked on cache reuse."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from ios.self_tests.test_ios_avatar_postlogout_reads import AvatarPostLogoutReadsTests


class AvatarPostLogoutCacheTests(AvatarPostLogoutReadsTests):
    def test_cache_account_boundary_is_copied_and_every_native_file_is_guarded(self):
        owner=self.owner();row=owner.capture();value=owner.record(row)['before'];actual=owner.account(value)
        original=deepcopy(actual);actual['sequence']+=1
        self.assertEqual(original,owner.account(value))
        # The targeted actual account native file is a different namespace;
        # it belongs to the exact boundary's actual Native AccountRead owner.
        account=owner.accounts();path=account.originals.path(value['row']['original']);before=path.stat();data=path.read_bytes()
        path.write_bytes(data);self.assertEqual(before.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):owner.account(value)

    def test_cache_context_change_cannot_reuse_another_native_subject_prefix(self):
        owner=self.owner();row=owner.capture();value=owner.record(row)['before'];owner.account(value);calls=[];decode=owner.account_original
        def actual(boundary):calls.append(True);return decode(boundary)
        owner.account_original=actual
        owner.account(value);self.assertEqual([],calls)
        original=owner.subject;owner.subject='actor'
        try:
            with self.assertRaises(NativeUIError):owner.account(value)
        finally:owner.subject=original
        self.assertEqual([True],calls)

    def test_cache_parts_restore_actual_read_membership_and_recheck_same_inode_bytes(self):
        owner=self.owner();row=owner.capture();parts=owner.row_parts(row);calls=[];decode=owner.row_partial_original
        def actual(value):calls.append(True);return decode(value)
        owner.row_partial_original=actual
        with scope(fresh=True) as reads:copy=owner.row_parts(row)
        self.assertEqual([],calls);self.assertEqual(parts,copy)
        copy['model']['sequence']+=1;self.assertEqual(parts,owner.row_parts(row))
        parent=owner.row_partial(row)['parts']['model'];path=owner.segments.store.path(parent['chunks'][0])
        self.assertIn(path,reads);before=path.stat();raw=path.read_bytes();path.write_bytes(raw)
        self.assertEqual(before.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):owner.row_parts(row)

    def test_cache_parts_preserve_planned_absence_including_dangling_symlinks(self):
        owner=self.owner();intent=owner.segments.intent;lost=[]
        def callback(parent):
            intent(parent)
            if parent['label']=='parts' and parent['chunks'] and parent['chunks'][-1]['phase']=='planned' and not lost:
                lost.append(True);raise OSError('Lost actual planned part return')
        owner.segments.intent=callback
        with self.assertRaises(OSError):owner.capture()
        again=self.owner();row=again.recover();self.assertEqual('abandoned',row['status']);self.assertEqual({},again.row_parts(row))
        parent=again.row_partial(row)['parts']['before'];path=again.segments.store.path(parent['chunks'][0])
        path.symlink_to(path.with_name('never-created-source'))
        with self.assertRaises(NativeUIError):again.row_parts(row)

    def test_cache_parts_do_not_cache_model_prefix_or_account_verdicts(self):
        owner=self.owner();row=owner.capture();parts=owner.row_parts(row)
        owner.part(parts)
        with self.assertRaises(NativeUIError):owner.part(owner.row_parts(row),previous=parts['model'])
        calls=[];decode=owner.row_partial_original
        def actual(value):calls.append(True);return decode(value)
        owner.row_partial_original=actual;owner.row_parts(row);self.assertEqual([],calls)
        original=owner.subject;owner.subject='actor'
        try:
            with self.assertRaises(NativeUIError):owner.row_parts(row)
        finally:owner.subject=original
        self.assertEqual([True],calls)

    def test_cache_parse_rechecks_actual_part_after_using_local_material(self):
        owner=self.owner();row=owner.capture();parent=owner.row_partial(row)['parts']['model']
        path=owner.segments.store.path(parent['chunks'][0]);original=owner._record_fields;changed=[]
        def actual(current,material):
            value=original(current,material)
            if not changed:
                raw=path.read_bytes();path.write_bytes(raw);changed.append(True)
            return value
        owner._record_fields=actual
        with self.assertRaises(NativeUIError):owner.parse(owner.previous)
        self.assertEqual([True],changed)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarPostLogoutCacheTests(name) for name in loader.getTestCaseNames(AvatarPostLogoutCacheTests) if name.startswith('test_cache_'))


if __name__=='__main__':unittest.main()
