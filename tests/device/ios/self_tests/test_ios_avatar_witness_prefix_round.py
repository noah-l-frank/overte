"""Actual immutable Final prefixes; no quiet verdict or native result is cached."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.adapters.avatar_final import IOSAvatarFinal, immutable_prefix_round, validation_round
from ios.self_tests import test_ios_avatar_final as fixture


class AvatarWitnessPrefixRoundTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarFinalTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def prefixes(self):
        owner=self.f.owner();first=self.f.capture(owner,1);early=deepcopy(owner.previous)
        self.f.clock[0]+=1.6;second=self.f.capture(owner,2)
        return owner,early,[first,second]

    def archive(self,owner,value):
        return IOSAvatarFinal.archive(value,store=owner.store,root=owner.root,bindings=owner.bindings,
            run=owner.run,role=owner.role,locks=owner.locks,authority=owner.authority,inputs=owner.inputs)

    @staticmethod
    def carrier(owner):
        return next(owner.root.glob('avatar-final-component-*-primary-post.json'))

    def test_only_explicit_prefix_scope_shares_identical_old_group_between_complete_owner_prefixes(self):
        owner,early,refs=self.prefixes();method=IOSAvatarFinal._group;calls=[]
        def actual(subject,value):calls.append(value['sequence']);return method(subject,value)
        native={s:len(c.f.calls) for s,c in self.f.cases.items()}
        with patch.object(IOSAvatarFinal,'_group',actual):
            with validation_round():
                self.archive(owner,early);ordinary=self.archive(owner,owner.previous)
            self.assertEqual([1,1,2],calls)
            calls.clear()
            with immutable_prefix_round(),read_scope(fresh=True) as reads:
                self.archive(owner,early);shared=self.archive(owner,owner.previous)
                self.assertEqual([1,2],calls)
                self.assertEqual(ordinary.state,shared.state)
                self.assertTrue(reads)
                # A separate actual read collection must not inherit membership.
                with read_scope(fresh=True) as independent:
                    other=self.archive(owner,owner.previous)
                    self.assertEqual(ordinary.state,other.state)
                self.assertEqual([1,2,1,2],calls);self.assertTrue(independent)
            calls.clear()
            with immutable_prefix_round():self.archive(owner,owner.previous)
            self.assertEqual([1,2],calls)
        self.assertEqual(native,{s:len(c.f.calls) for s,c in self.f.cases.items()})

    def test_each_borrowing_owner_retains_its_exact_whole_envelope_and_current_state(self):
        owner,early,refs=self.prefixes()
        for fault in ('state-only','coordinated-envelope-and-state'):
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                with immutable_prefix_round():
                    first=self.archive(owner,early);second=self.archive(owner,owner.previous)
                    first.state['rows']=[]
                    if fault=='coordinated-envelope-and-state':
                        # A matching newly fabricated envelope must not replace
                        # the exact old owner pin that admitted this borrower.
                        first.previous=first.envelope(first.state)
                    second.group(second.record(refs[0]))

    def test_foreign_binding_or_original_input_cannot_borrow_a_matching_old_group(self):
        owner,early,_refs=self.prefixes()
        with immutable_prefix_round():
            self.archive(owner,early)
            for fault in ('binding','input'):
                value=deepcopy(owner.previous)
                if fault=='binding':value['bindings']['primary']['sessionId']='foreign-session'
                else:value['inputs']['primary']['childRunId']='c'*32
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                    self.archive(owner,value)

    def test_actual_equal_bytes_new_inode_and_unknown_child_are_detected_before_reuse(self):
        owner,early,refs=self.prefixes();path=self.carrier(owner)
        with self.assertRaises(NativeUIError):
            with immutable_prefix_round():
                self.archive(owner,early)
                replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
                os.replace(replacement,path)
                self.archive(owner,owner.previous)
        # A later independent scope still executes the original full reader.
        # Unknown inventory growth inside that scope cannot be hidden either.
        with self.assertRaises(NativeUIError):
            with immutable_prefix_round():
                archived=self.archive(owner,early)
                unknown=owner.root/'unknown-avatar-prefix-child';unknown.write_bytes(b'owned test mutation');unknown.chmod(0o600)
                archived.group(archived.record(refs[0]))

    def test_replaced_group_parser_cannot_inherit_an_earlier_literal_success(self):
        owner,early,refs=self.prefixes();calls=[]
        def changed(_owner,_value):calls.append(True);raise NativeUIError('Declared replacement parser')
        with immutable_prefix_round():
            self.archive(owner,early)
            with patch.object(IOSAvatarFinal,'_group',changed),self.assertRaises(NativeUIError):
                self.archive(owner,owner.previous)
        self.assertEqual([True],calls)


if __name__=='__main__':unittest.main()
