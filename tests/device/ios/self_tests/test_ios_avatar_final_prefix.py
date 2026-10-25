"""One live capture reuses only fully decoded immutable old Final rows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_final import IOSAvatarFinal
from ios.adapters.avatar_final_prefix import FinalCapturePrefix
from ios.self_tests import test_ios_avatar_final as fixture


class AvatarFinalPrefixTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarFinalTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def original(self):
        owner=self.f.owner();ref=self.f.capture(owner,1);self.f.clock[0]+=1.6;return owner,ref
    def test_every_new_group_and_both_complete_boundaries_decode_without_old_rows_repeated_at_each_save(self):
        owner,first=self.original();calls=[];method=IOSAvatarFinal._group
        def actual(current,value):calls.append(value['sequence']);return method(current,value)
        with patch.object(IOSAvatarFinal,'_group',new=actual):second=self.f.capture(owner,2)
        self.assertEqual(2,calls.count(1));self.assertGreaterEqual(calls.count(2),3)
        self.assertIsNone(getattr(owner,'_capture_prefix',None));before=len(calls)
        # A subsequent historical construction uses the full original decoder.
        with patch.object(IOSAvatarFinal,'_group',new=actual):self.f.archive(owner)
        self.assertEqual([1,2],calls[before:]);self.assertEqual(2,second['index']);self.assertEqual(first,owner.state['rows'][0]['reference'])
    def test_mutated_old_row_binding_or_same_inode_original_cannot_send_the_next_query(self):
        owner,_ref=self.original();calls={s:len(c.f.calls) for s,c in self.f.cases.items()}
        for fault in ('row','binding','inode'):
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                with FinalCapturePrefix(owner):
                    value=deepcopy(owner.previous)
                    if fault=='row':
                        state=deepcopy(owner.state);state['rows'][0]['reference']['sha256']='0'*64;value=owner.envelope(state)
                    elif fault=='binding':owner.bindings['primary']['generation']+=1
                    else:
                        path=next(owner.root.glob('avatar-primary-tail-parts-*'));inode=path.stat().st_ino
                        with path.open('ab') as stream:stream.write(b' ')
                        self.assertEqual(inode,path.stat().st_ino)
                    owner.parse(value)
            if fault=='binding':owner.bindings=deepcopy(self.f.bindings)
        self.assertEqual(calls,{s:len(c.f.calls) for s,c in self.f.cases.items()})
    def test_dangling_reserved_original_or_changed_nested_component_is_never_an_absent_old_prefix(self):
        owner,_ref=self.original();before={s:len(c.f.calls) for s,c in self.f.cases.items()}
        with self.assertRaises(NativeUIError):
            with FinalCapturePrefix(owner):
                owner.file(2).path.symlink_to('missing-final-original');owner.parse(owner.previous)
        owner.file(2).path.unlink()
        with self.assertRaises(NativeUIError):
            with FinalCapturePrefix(owner):
                path=next(owner.root.glob('avatar-final-component-*-1-primary-tail.json'))
                with path.open('ab') as stream:stream.write(b' ')
                owner.parse(owner.previous)
        self.assertEqual(before,{s:len(c.f.calls) for s,c in self.f.cases.items()})
    def test_actual_private_parent_mode_change_cannot_reuse_old_originals(self):
        owner,_ref=self.original();counts={s:len(c.f.calls) for s,c in self.f.cases.items()}
        mode=owner.root.stat().st_mode&0o777
        try:
            with self.assertRaises(NativeUIError):
                with FinalCapturePrefix(owner):
                    owner.root.chmod(0o755);owner.parse(owner.previous)
        finally:owner.root.chmod(mode)
        self.assertEqual(counts,{s:len(c.f.calls) for s,c in self.f.cases.items()})

    def test_lost_new_query_keeps_actual_pending_owner_and_recovery_never_reissues_it(self):
        owner,_ref=self.original();factory=owner.factory;hit=[]
        def uncertain(subject):
            actual=factory(subject)
            if subject=='primary' and not hit:
                capture=actual['tail'].capture
                def lost():hit.append(True);capture();raise OSError('Lost original return after actual capture')
                actual['tail'].capture=lost
            return actual
        owner.factory=uncertain
        with self.assertRaises(OSError):self.f.capture(owner,2)
        self.assertIsNotNone(owner.state['pending']);self.assertIsNone(getattr(owner,'_capture_prefix',None))
        counts={s:len(c.f.calls) for s,c in self.f.cases.items()};rebuilt=self.f.owner();rebuilt.recover()
        self.assertEqual(counts,{s:len(c.f.calls) for s,c in self.f.cases.items()})
    def test_full_exit_validation_remains_inside_original_final_freshness(self):
        owner=self.f.owner();method=owner.parse;armed=[]
        def parse(value):
            result=method(value)
            if owner.state['rows'] and getattr(owner,'_capture_prefix',None) is None and not armed:
                armed.append(True);self.f.clock[0]+=1.501
            return result
        with patch.object(owner,'parse',side_effect=parse),self.assertRaises(NativeUIError):self.f.capture(owner,1)
        self.assertTrue(armed);self.assertIsNone(owner.state['pending']);self.assertEqual(1,len(owner.state['rows']))
        self.f.archive(owner)


if __name__=='__main__':unittest.main()
