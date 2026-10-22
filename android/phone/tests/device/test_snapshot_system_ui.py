"""Explicit synthetic SDK/window boundary; no Android chooser or receiver run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUI,NativeUIError
from overte_phone_snapshot_system_ui import PhoneSnapshotSystemUI,PRIMARY,RECEIVER,RECEIVER_COMPONENT,LABEL,tree

CHOOSER='com.android.intentresolver/com.android.intentresolver.ChooserActivity'
IDENTITY=dict(package=RECEIVER,apkSha256='a'*64,uid=12000,processId=45,processIdentity='45:1234')


class Boundary:
    def __init__(self):
        self.component=CHOOSER;self.clock=0.;self.epoch=20000;self.okay=True;self.calls=[];self.intents=[]
        self.ignored=False;self.fault=None;self.changed=False;self.allow=True
        self.ui=NativeUI(self,'owned',lambda:self.okay,monotonic=lambda:self.clock,sleep=self.sleep)
        self.flow=PhoneSnapshotSystemUI(self.ui,self.intent,lambda:self.epoch,CHOOSER)
    def sleep(self,value):self.clock+=value
    def intent(self,value):
        self.intents.append(deepcopy(value))
        if self.changed:self.component='org.foreign.app/org.foreign.app.Dialog'
        return self.allow
    def call(self,method,path,body=None):
        self.calls.append((method,path,deepcopy(body)))
        if path.endswith('/current_package'):return self.component.split('/')[0]
        if path.endswith('/current_activity'):return self.component.split('/')[1]
        if path.endswith('/source'):
            package=self.component.split('/')[0]
            raw='<hierarchy><node package="'+package+'" enabled="true" clickable="true" bounds="[0,0][300,400]"><node package="'+package+'" text="'+LABEL+'" enabled="true" bounds="[10,100][200,160]"/></node></hierarchy>'
            return self.fault(raw) if self.fault else raw
        if method=='POST' and path.endswith('/actions'):
            if not self.ignored:self.component=RECEIVER_COMPONENT
            return {'ignoredReceipt':self.ignored}
        if method=='DELETE' and path.endswith('/actions'):return None
        if method=='POST' and path.endswith('/back'):
            if not self.ignored:self.component=PRIMARY+'/'+PRIMARY+'.MainActivity'
            return None
        raise AssertionError('Unexpected synthetic SDK operation')
    def inputs(self):return [row for row in self.calls if row[0]=='POST']


class SnapshotSystemUiTests(unittest.TestCase):
    def test_normal_receiver_selection_uses_current_unique_bounds_and_returns_no_consumption_claim(self):
        b=Boundary();result=b.flow.select_receiver(IDENTITY)
        self.assertEqual(RECEIVER_COMPONENT,result['component']);self.assertEqual(1,len(b.inputs()))
        self.assertEqual('share-select-owned',b.intents[0]['action']);self.assertNotIn('shares',result)
        self.assertEqual('DELETE',b.calls[next(i for i,r in enumerate(b.calls) if r[0]=='POST')+1][0])
    def test_older_android_framework_chooser_uses_same_original_sdk_window_guards(self):
        b=Boundary();b.component='android/com.android.internal.app.ChooserActivity'
        flow=PhoneSnapshotSystemUI(b.ui,b.intent,lambda:b.epoch,b.component)
        self.assertEqual(RECEIVER_COMPONENT,flow.select_receiver(IDENTITY)['component'])

    def test_normal_cancel_and_return_from_owned_receiver_observe_actual_app_window(self):
        b=Boundary();self.assertTrue(b.flow.back()['component'].startswith(PRIMARY+'/'))
        b=Boundary();b.component=RECEIVER_COMPONENT;self.assertTrue(b.flow.back(receiver=True)['component'].startswith(PRIMARY+'/'))
    def test_successful_ignored_sdk_input_never_proves_selection_or_cancel_and_is_not_replayed(self):
        for action in ('select','back'):
            b=Boundary();b.ignored=True
            with self.subTest(action=action),self.assertRaises(NativeUIError):
                b.flow.select_receiver(IDENTITY) if action=='select' else b.flow.back()
            self.assertEqual(1,len(b.inputs()));self.assertLessEqual(b.clock,5.01)
    def test_foreign_window_replacement_after_durable_intent_prevents_input(self):
        b=Boundary();b.changed=True
        with self.assertRaises(NativeUIError):b.flow.select_receiver(IDENTITY)
        self.assertEqual([],b.inputs());self.assertEqual(1,len(b.intents))
    def test_slow_intent_write_cannot_reuse_old_input_authority_even_with_identical_xml(self):
        b=Boundary();original=b.flow.intent
        def slow(value):
            result=original(value);b.epoch+=1600;return result
        b.flow.intent=slow
        with self.assertRaises(NativeUIError):b.flow.select_receiver(IDENTITY)
        self.assertEqual([],b.inputs())

    def test_failed_intent_does_not_send_normal_input(self):
        b=Boundary();b.allow=False
        with self.assertRaises(NativeUIError):b.flow.select_receiver(IDENTITY)
        self.assertEqual([],b.inputs())
    def test_missing_duplicate_disabled_or_foreign_named_receiver_never_receives_a_touch(self):
        for fault in ('missing','duplicate','disabled','foreign','bounds','wrong-activity'):
            b=Boundary()
            if fault=='missing':b.fault=lambda raw:raw.replace(LABEL,'Foreign')
            elif fault=='duplicate':b.fault=lambda raw:raw.replace('</hierarchy>',raw[11:raw.index('</hierarchy>')]+'</hierarchy>')
            elif fault=='disabled':b.fault=lambda raw:raw.replace('enabled="true"','enabled="false"')
            elif fault=='foreign':b.fault=lambda raw:raw.replace('text="'+LABEL+'"','package-ignored="x" text="Foreign"')
            elif fault=='bounds':b.fault=lambda raw:raw.replace('[10,100][200,160]','[10,100][400,160]')
            else:b.component='com.android.intentresolver/com.android.intentresolver.ForeignActivity'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.flow.select_receiver(IDENTITY)
            self.assertEqual([],b.inputs())
    def test_foreign_guard_or_apk_identity_never_authorizes_selection(self):
        b=Boundary();b.okay=False
        with self.assertRaises(NativeUIError):b.flow.select_receiver(IDENTITY)
        self.assertEqual([],b.calls)
        for change in (dict(package=PRIMARY),dict(uid=0),dict(processIdentity='46:1234'),dict(apkSha256='unknown')):
            b=Boundary()
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.flow.select_receiver(IDENTITY|change)
            self.assertEqual([],b.inputs())
    def test_entity_expansion_or_oversized_ui_source_is_rejected(self):
        for raw in ('<!DOCTYPE root><hierarchy/>','<!ENTITY a "b"><hierarchy/>','x'*262145):
            with self.subTest(length=len(raw)),self.assertRaises(NativeUIError):tree(raw)
    def test_frozen_epoch_cannot_hide_slow_ui_reads(self):
        b=Boundary()
        def slow(raw):b.clock+=1.6;return raw
        b.fault=slow
        with self.assertRaises(NativeUIError):b.flow.select_receiver(IDENTITY)
        self.assertEqual([],b.inputs())


if __name__=='__main__':unittest.main()
