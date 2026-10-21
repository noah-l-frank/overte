"""Actual preference facts must admit an already controlled dedicated sandbox."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.adapters.account_preferences import validate,require_owned
from adapters.normal_ui import NativeUIError

ORIGIN='https://owned.invalid'


class IOSAccountPreferenceTests(unittest.TestCase):
    def original(self):
        digest=hashlib.sha256(ORIGIN.encode()).hexdigest()
        return dict(accountPreferenceVersion=1,present=True,valueType='string',valueSha256=digest,
            canonicalOrigin=True,processOverridePresent=True,processOverrideSha256=digest,processOverrideCanonical=True)

    def version_two(self,**changes):
        return self.original()|dict(accountPreferenceVersion=2,rememberPresent=True,rememberType='bool',rememberValue=False,
            savedUsernamePresent=True,savedUsernameType='string',savedUsernameSha256=hashlib.sha256(b'').hexdigest())|changes

    def test_version_two_initial_owner_requires_original_empty_saved_username_and_existing_boolean(self):
        original=self.version_two();self.assertEqual(original,require_owned(original,ORIGIN,initial=True))
        for changes in (dict(savedUsernameSha256='e'*64),dict(rememberPresent=False,rememberType='absent',rememberValue=None),
                        dict(savedUsernamePresent=False,savedUsernameType='absent',savedUsernameSha256=None)):
            with self.assertRaises(NativeUIError):require_owned(self.version_two(**changes),ORIGIN,initial=True)
        with self.assertRaises(NativeUIError):require_owned(self.original(),ORIGIN,initial=True)

    def test_only_owned_saved_username_is_admissible_during_run_and_cleanup_requires_exact_originals(self):
        run='a'*32;original=self.version_two()
        changed=self.version_two(rememberValue=True,savedUsernameSha256=hashlib.sha256(('e2e-'+run).encode()).hexdigest())
        self.assertEqual(changed,require_owned(changed,ORIGIN,run=run))
        with self.assertRaises(NativeUIError):require_owned(changed,ORIGIN,run=run,baseline=original)
        self.assertEqual(original,require_owned(original,ORIGIN,run=run,baseline=original))
        with self.assertRaises(NativeUIError):require_owned(self.version_two(savedUsernameSha256='e'*64),ORIGIN,run=run)

    def test_exact_original_hash_and_type_are_returned_without_mutating_or_manufacturing_them(self):
        source=self.original();actual=require_owned(source,ORIGIN);self.assertEqual(source,actual)
        actual['present']=False;self.assertTrue(source['present'])

    def test_absent_or_foreign_original_preference_is_rejected_instead_of_overwritten(self):
        for change in (dict(present=False,valueType='absent',valueSha256=None,canonicalOrigin=False),
                       dict(valueType='url'),dict(valueSha256='e'*64),dict(canonicalOrigin=False),
                       dict(valueType='unsupported',valueSha256=None,canonicalOrigin=False)):
            value=self.original()|change;before=deepcopy(value);validate(value)
            with self.assertRaises(NativeUIError):require_owned(value,ORIGIN)
            self.assertEqual(before,value)

    def test_missing_foreign_or_noncanonical_process_override_cannot_admit_credentials(self):
        for change in (dict(processOverridePresent=False,processOverrideSha256=None,processOverrideCanonical=False),
                       dict(processOverrideSha256='f'*64),dict(processOverrideCanonical=False)):
            with self.assertRaises(NativeUIError):require_owned(self.original()|change,ORIGIN)

    def test_boolean_versions_extra_fields_missing_originals_and_wrong_types_fail(self):
        for change in (dict(accountPreferenceVersion=True),dict(present=1),dict(valueSha256=True),
                       dict(valueType='absent'),dict(processOverrideSha256=None),dict(extra='unmeasured')):
            with self.assertRaises(NativeUIError):validate(self.original()|change)
        with self.assertRaises(NativeUIError):validate(None)


if __name__=='__main__':unittest.main()
