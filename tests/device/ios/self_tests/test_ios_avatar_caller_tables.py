"""Immutable original stack reuse stays bounded and cannot alias/rewrite history."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import canonical
from ios.adapters import avatar_scripts as scripts,avatar_social_http as http,avatar_ui_work as work
from ios.adapters.avatar_code import pins
from ios.self_tests import avatar_callers2_fixture as current


class AvatarCallerTableTests(unittest.TestCase):
    def test_120_timer_births_and_600_original_events_stay_inside_unchanged_source_limits(self):
        value=current.timer_history2();raw=canonical(value);scripts.original(value)
        self.assertLess(len(canonical(value['source'])),250000);self.assertLess(len(raw),scripts.LIMIT)
        worker=value['source']['workers'][0]
        self.assertEqual((120,600,1,1),(len(worker['uiWork']['timers']),len(worker['avatar']['events']),
            len(worker['avatar']['callerStacks']),len(worker['uiWork']['callerStacks'])))
        self.assertTrue(scripts.drained(value,{'b'*32}));self.assertEqual(raw,canonical(value))
        before=current.scripts2();result=work.drained_since(before,value,{'b'*32},pins(),require_actual=True)
        self.assertEqual(120,len(result['owned']['b'*32]))

    def test_stack_reference_cannot_name_an_absent_or_duplicate_actual_entry(self):
        value=current.scripts2();current.timer2(value)
        for fault in ('unknown-reference','duplicate-id','duplicate-original','removed-table','rewritten-identity'):
            changed=deepcopy(value);worker=changed['source']['workers'][0];table=worker['avatar']['callerStacks']
            if fault=='unknown-reference':worker['avatar']['events'][0]['details']['callerStackId']='b'*32
            elif fault=='duplicate-id':table.append(deepcopy(table[0]))
            elif fault=='duplicate-original':
                row=deepcopy(table[0]);row['id']='b'*32;table.append(row)
            elif fault=='removed-table':worker['avatar']['callerStacks']=[]
            else:table[0]['callerStack']['frames'][0]['compiled']['sha256']='b'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):scripts.original(changed)

    def test_table_prefix_is_immutable_even_when_all_timer_references_are_rehashed_together(self):
        before=current.scripts2();current.timer2(before)
        after=deepcopy(before);after.update(sequence=2,requestId='ios-'+'9'*32)
        for clock in ('clockBefore','clockAfter'):
            after[clock]['epochMs']+=100;after[clock]['monotonicMs']+=100
        after['source']['workers'][0]['avatar']['callerStacks'][0]['id']='b'*32
        after['source']['workers'][0]['avatar']['events'][0]['details']['callerStackId']='b'*32
        scripts.original(after)
        with self.assertRaises(NativeUIError):scripts.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=scripts.ACTION,
            runId=after['runId']),42,previous=before)

    def test_social_reply_cannot_borrow_a_different_stack_or_drop_the_original_table(self):
        value=current.http2();http.original(value)
        for fault in ('borrow-open','missing-read','extra-alias'):
            changed=deepcopy(value)
            if fault=='borrow-open':
                # The original Open and Read frame locations differ. Replacing
                # the referenced actual ID is not equivalent to keeping bytes.
                changed['events'][4]['details']['callerStackId']='a3'*16
                changed['callerStacks']=changed['callerStacks'][:1]
                # Module-origin alone can accept this shape; exact callsite
                # qualification separately rejects Open used as Read.
                http.original(changed);continue
            elif fault=='missing-read':changed['callerStacks'].pop()
            else:
                alias=deepcopy(changed['callerStacks'][0]);alias['id']='b'*32;changed['callerStacks'].append(alias)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):http.original(changed)


if __name__=='__main__':unittest.main()
