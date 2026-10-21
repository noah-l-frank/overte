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
