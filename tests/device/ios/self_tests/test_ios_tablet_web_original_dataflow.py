"""Reuse one successful decode; current actual WALs still bind the result.

Actual generated app JS and private ownership files run normally. Native/WDA
and clocks are explicit page boundary models, not native execution evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.self_tests import test_ios_tablet_web_page_flow as page_fixture


class TabletOriginalDataflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture=page_fixture.TabletPageFlowTests();self.addCleanup(self.fixture.doCleanups)
        self.b=self.fixture.opened();self.original=self.b.runtime.observe()
    def test_runtime_uses_one_full_original_source_decode_without_requery_or_published_internal_state(self):
        before=deepcopy(self.b.raw);details=self.b.runtime.observer._decoded_original(self.original['observation'])
        with patch('ios.adapters.tablet_web_observer.TabletWebSourceOwner',wraps=TabletWebSourceOwner) as constructors:
            actual=self.b.runtime._validate_original(self.original,require_current=True)
        self.assertEqual(1,constructors.call_count);self.assertEqual(before,self.b.raw)
        self.assertEqual(details[0]['public']['state'],actual['public']['state'])
        self.assertEqual({'ticket','public','acquisition'},set(actual))
        self.assertNotIn('children',repr(actual));self.assertNotIn('reference',actual['public'])
        # Mutating a separately returned ephemeral tuple does not change any
        # original bytes or the next full original decode.
        details[2]['browser']['responses'].clear();details[3]['sources']['roots'].clear()
        self.assertEqual(actual,self.b.runtime._validate_original(self.original,require_current=True))
    def test_new_actual_pending_parent_or_child_after_successful_decode_cannot_qualify_current(self):
        observer=self.b.runtime.observer;decode=observer._decoded_original
        for kind in ('parent','child'):
            store=self.b.source.store if kind=='parent' else self.b.source.children['state'].store
            old=store.read()
            def changed(value):
                answer=decode(value)
                # This is a newly persisted ownership intent, not a native
                # effect. A current verdict must not reuse the earlier WAL.
                pending=deepcopy(old);pending['pending']=dict(actualNewUnansweredQuery=True)
                store.write(pending,old);return answer
            before=deepcopy(self.b.raw)
            try:
                with self.subTest(kind=kind),patch.object(observer,'_decoded_original',side_effect=changed):
                    with self.assertRaises(NativeUIError):self.b.runtime._validate_original(self.original,require_current=True)
                self.assertEqual(before,self.b.raw)
            finally:store.write(old,store.read())
    def test_partial_original_decode_exception_never_falls_back_to_reusing_an_earlier_success(self):
        self.b.runtime._validate_original(self.original,require_current=True);before=deepcopy(self.b.raw)
        with patch.object(self.b.runtime.observer,'_decoded_original',side_effect=OSError('Actual original decoder failed')):
            with self.assertRaises(OSError):self.b.runtime._validate_original(self.original,require_current=True)
        self.assertEqual(before,self.b.raw)


if __name__=='__main__':unittest.main()
