"""Pure literal reuse over actual captured fixture frames; no native proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pure_original_validation import scope,AVATAR_FINAL_PROFILE
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.self_tests import test_ios_avatar_sources as fixture


class AvatarSourcePureValidationTests(unittest.TestCase):
    def setUp(self):
        model=fixture.AvatarSourcesTests();model.setUp();self.addCleanup(model.doCleanups)
        self.enterContext(model.lock.held());self.owner=model.owner()
        self.before=self.owner.read();self.frame=self.owner.read()
    def test_default_revalidates_and_only_explicit_scope_shares_literal_success(self):
        validate=IOSAvatarSources._validate_frame
        calls=[]
        def counted(*arguments):calls.append(True);return validate(*arguments)
        with patch.object(IOSAvatarSources,'_validate_frame',staticmethod(counted)):
            first=self.owner.validate_frame(self.frame,self.before)
            self.owner.validate_frame(deepcopy(self.frame),deepcopy(self.before))
            self.assertEqual(2,len(calls))
            with scope(AVATAR_FINAL_PROFILE,lambda:True):
                self.assertEqual(first,self.owner.validate_frame(self.frame,self.before))
                self.assertEqual(first,self.owner.validate_frame(deepcopy(self.frame),deepcopy(self.before)))
            self.assertEqual(3,len(calls))
            self.owner.validate_frame(self.frame,self.before);self.assertEqual(4,len(calls))
    def test_prior_frame_pid_and_run_are_distinct_validated_arguments(self):
        validate=IOSAvatarSources._validate_frame;calls=[]
        def counted(*arguments):calls.append(True);return validate(*arguments)
        with patch.object(IOSAvatarSources,'_validate_frame',staticmethod(counted)),scope(AVATAR_FINAL_PROFILE,lambda:True):
            self.owner.validate_frame(self.frame,self.before)
            self.owner.validate_frame(self.frame,None);self.assertEqual(2,len(calls))
            self.owner.pid=43
            with self.assertRaises(NativeUIError):self.owner.validate_frame(self.frame,self.before)
            self.owner.pid=42;self.owner.run='a'*32
            with self.assertRaises(NativeUIError):self.owner.validate_frame(self.frame,self.before)
    def test_nested_mutation_never_borrows_a_prior_success_or_escapes_the_scope(self):
        with scope(AVATAR_FINAL_PROFILE,lambda:True):
            self.owner.validate_frame(self.frame,self.before)
            changed=deepcopy(self.frame);changed['acquisitions']['state']['originalSha256']='0'*64
            with self.assertRaises(NativeUIError):self.owner.validate_frame(changed,self.before)
            changed=deepcopy(self.before);changed['ui']['scope']['sourceSequence']=self.frame['ui']['scope']['sourceSequence']
            with self.assertRaises(NativeUIError):self.owner.validate_frame(self.frame,changed)
        self.owner.validate_frame(self.frame,self.before)


if __name__=='__main__':unittest.main()
