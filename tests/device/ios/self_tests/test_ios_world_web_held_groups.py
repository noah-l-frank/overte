"""Lossless labels over explicitly modeled already-decoded native groups.

These are projection/identity cases, not native lifetime or cleanup evidence.
The retained full-journey graph separately exercises the actual source decoder.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_held_groups import project,expand,verify,visible
from feature_journeys.terminal import held
from ios.self_tests.test_ios_create_files import BINDING


def row(index,kind='qimage'):
    original=dict(iosWorldWebHeldResourceVersion=1,binding=deepcopy(BINDING),runId='a'*32,source='web-native-bitmap',
        owner=dict(instance='b'*32,processId=int(BINDING['processIdentity']),contextId='%032x'%index,
            descriptor=dict(creation=index),counter=dict(created=1,retired=0,pending=1)))
    return rebound(dict(resource='',kind=kind,originalSha256='',original=original))


def rebound(value):
    value=deepcopy(value);value['originalSha256']=digest(value['original'])
    value['resource']='panel:world-web-'+value['kind']+'-'+value['originalSha256'][:20];return value


def originals():return [row(index,('qt-root','qsg-root','qimage','native-holder')[index%4]) for index in range(1,135)]


class WorldWebHeldGroupsTests(unittest.TestCase):
    def test_literal_small_shape_remains_identical_and_does_not_alias(self):
        values=sorted([row(index) for index in range(1,65)],key=lambda value:value['resource'])
        result=project(values);self.assertEqual(values,result);self.assertEqual(values,expand(result))
        result[0]['original']['owner']['counter']['pending']=0
        self.assertTrue(all(value['original']['owner']['counter']['pending']==1 for value in values))

    def test_all_134_exact_originals_survive_four_public_labels(self):
        values=originals();result=project(values)
        self.assertEqual(4,len(result));self.assertEqual(4,len(held([visible(value) for value in result])))
        self.assertEqual(sorted(values,key=lambda value:value['resource']),expand(result))
        self.assertEqual(134,sum(len(value['original']['members']) for value in result))
        self.assertEqual(result,project(list(reversed(values))))
        self.assertEqual(expand(result),verify(result,values))

    def test_same_kind_new_member_native_birth_context_or_counter_changes_label(self):
        values=originals();before=project(values)
        for fault in ('new','nativeBirth','context','counter'):
            changed=deepcopy(values)
            if fault=='new':changed.append(row(999))
            else:
                owner=changed[0]['original']['owner']
                if fault=='nativeBirth':owner['instance']='c'*32
                elif fault=='context':owner['contextId']='d'*32
                else:owner['counter'].update(created=2,retired=1)
                changed[0]=rebound(changed[0])
            with self.subTest(fault=fault):
                after=project(changed);self.assertNotEqual(before,after)
                self.assertNotEqual([value['resource'] for value in before],[value['resource'] for value in after])

    def test_missing_member_even_with_repaired_outer_hash_cannot_match_actual_set(self):
        values=originals();result=project(values);changed=deepcopy(result)
        changed[0]['original']['members'].pop()
        with self.assertRaises((NativeUIError,ValueError)):expand(changed)
        repaired=project(values[:-1])
        with self.assertRaises((NativeUIError,ValueError)):verify(repaired,values)

    def test_duplicates_foreign_run_and_boolean_group_version_fail_closed(self):
        values=originals()
        for fault in ('duplicate','run','version','namespace'):
            with self.subTest(fault=fault):
                if fault=='version':
                    changed=project(values);changed[0]['original']['iosWorldWebHeldResourceGroupVersion']=True
                    with self.assertRaises((NativeUIError,ValueError)):expand(changed)
                else:
                    changed=deepcopy(values)
                    if fault=='duplicate':changed.append(deepcopy(changed[0]))
                    elif fault=='namespace':changed[0]['resource']='panel:other-feature-owned'
                    else:changed[0]['original']['runId']='f'*32;changed[0]=rebound(changed[0])
                    with self.assertRaises((NativeUIError,ValueError)):project(changed)

    def test_expanded_member_alias_never_mutates_retained_group_original(self):
        values=originals();result=project(values);before=deepcopy(result)
        expanded=expand(result);expanded[0]['original']['owner'].clear()
        self.assertEqual(before,result);self.assertEqual(134,len(expand(result)))


if __name__=='__main__':unittest.main()
