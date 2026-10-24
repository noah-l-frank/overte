"""Normal world ray/IME sequencing; explicit source/transport model boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_source import validate
from adapters.pico4.world_browser_text import PicoWorldTextInput
from self_tests import test_pico_world_browser_ray as ray_original
WorldBoundary=ray_original.WorldBoundary
RUN,URL,OWNER,VIEW=ray_original.RUN,ray_original.URL,ray_original.OWNER,ray_original.VIEW


class TextBoundary(WorldBoundary):
    """Independent model state changes only in declared input-consumer seams."""
    def __init__(self,lock):
        super().__init__(lock);self.focused=False;self.text='old 🌍';self.apply_focus=True;self.apply_text=True;self.delivered=True
        self.io.sleep=self.sleep
    def sleep(self,seconds):self.elapsed+=seconds;self.epoch+=round(seconds*1000)
    def send(self,call):
        super().send(call)
        geometry=json.loads(json.loads(self.packet['source']['geometryRaw']))
        units=len(self.text.encode('utf-16-le'))//2
        geometry['editor']=dict(focused=self.focused,text=self.text,cursor=units,anchor=units)
        raw=json.dumps(json.dumps(geometry))
        if call['operation']=='commit-text':
            need(self.focused)
            before=dict(text=self.text,cursor=units,anchor=units,absoluteCursor=units,kind='text',sensitive=False,focused=True,enabled=True)
            self.packet.update(picoBrowserVersion=4,source=dict(delivered=self.delivered,focusRaw=raw,nativeBeforeIME=before,
                imeEpochMs=self.epoch,nativeView={k:VIEW[k] for k in ('handle','creation','grant','page','url')}))
            # Explicit substitute for Android's independent IME consumer, with
            # ignored-event counters below. Source projections never assign it.
            if self.apply_text and self.delivered:self.text=call['text']
        else:self.packet['source']['geometryRaw']=raw


class WorldBrowserTextTests(unittest.TestCase):
    setUp=ray_original.WorldBrowserRayTests.setUp
    owner=ray_original.WorldBrowserRayTests.owner
    def make(self,commit_intent=None):
        self.b=TextBoundary(self.lock);original=self.transport.stage
        def consume(envelope,profile,**hooks):
            result=original(envelope,profile,**hooks)
            if self.b.apply_focus:self.b.focused=True
            return result
        self.transport.stage=consume
        click=self.owner();self.commits=[]
        def intent(value):
            self.commits.append(deepcopy(value))
            if commit_intent:commit_intent(value)
        return PicoWorldTextInput(click,intent)
    def replace(self,owner,text='Grüße 🌍'):
        with self.lock.held():return owner.replace(RUN,URL,OWNER,VIEW,text)
    def test_original_normal_gesture_then_independent_focus_one_ime_and_actual_readback(self):
        owner=self.make();result=self.replace(owner)
        before=json.loads(json.loads(result['focusBefore']['source']['geometryRaw']))
        after=json.loads(json.loads(result['focusAfter']['source']['geometryRaw']))
        self.assertTrue(before['editor']['focused']);self.assertEqual('old 🌍',before['editor']['text'])
        self.assertEqual('Grüße 🌍',after['editor']['text']);self.assertEqual(1,len(self.transport.envelopes))
        self.assertEqual(1,len(self.commits));self.assertEqual(4,result['commit']['picoBrowserVersion'])
        self.assertEqual('old 🌍',result['commit']['source']['nativeBeforeIME']['text'])
        self.assertNotIn('featureSucceeded',result);self.assertIsNone(self.b.io.before_send)
    def test_ignored_controller_ack_cannot_create_focus_or_submit_ime(self):
        owner=self.make();self.b.apply_focus=False
        with self.assertRaises(NativeUIError):self.replace(owner)
        self.assertTrue(owner.failed);self.assertEqual([],self.commits)
        self.assertFalse(any(call['operation']=='commit-text' for call in self.b.calls));self.assertEqual(1,len(self.transport.envelopes))
    def test_ime_ack_without_actual_editor_change_cannot_satisfy_readback_or_retry(self):
        owner=self.make();self.b.apply_text=False
        with self.assertRaises(NativeUIError):self.replace(owner)
        with self.assertRaises(NativeUIError):self.replace(owner)
        self.assertEqual('old 🌍',self.b.text);self.assertEqual(1,len(self.commits))
        self.assertEqual(1,len([call for call in self.b.calls if call['operation']=='commit-text']))
        self.assertEqual(1,len(self.transport.envelopes))
    def test_negative_delivery_keeps_original_attempt_metadata_and_consumes_sequence(self):
        owner=self.make();self.b.delivered=False
        with self.assertRaises(NativeUIError):self.replace(owner)
        self.assertFalse(self.b.io.last['source']['delivered']);self.assertEqual('old 🌍',self.b.io.last['source']['nativeBeforeIME']['text'])
        self.assertEqual(1,len(self.commits));self.assertTrue(owner.failed)
    def test_late_commit_intent_cannot_reset_whole_native_clock_with_frozen_host(self):
        owner=self.make(lambda _:setattr(self.b,'epoch',self.b.epoch+5001))
        with self.assertRaises(NativeUIError):self.replace(owner)
        self.assertEqual(1,len(self.commits));self.assertFalse(any(call['operation']=='commit-text' for call in self.b.calls))
        self.assertEqual(1,len(self.transport.envelopes));self.assertTrue(owner.failed)
    def test_invalid_text_is_rejected_before_normal_gesture_or_commit_intent(self):
        for text in ('x'*513,'bad\ntext','\ue001'):
            with self.subTest(text=text):
                self.setUp();owner=self.make()
                with self.assertRaises(NativeUIError):self.replace(owner,text)
                self.assertFalse(owner.issued);self.assertEqual([],self.transport.envelopes);self.assertEqual([],self.commits)
    def test_reply_cannot_replace_original_focused_dom_or_native_editor_metadata(self):
        owner=self.make();result=self.replace(owner);packet=result['commit'];call=self.commits[-1]['command']
        for change in ('unfocused','wrong-native','sensitive','future-attempt','wrong-version','false-integer'):
            bad=deepcopy(packet)
            if change=='unfocused':
                geometry=json.loads(json.loads(bad['source']['focusRaw']));geometry['editor']['focused']=False
                bad['source']['focusRaw']=json.dumps(json.dumps(geometry))
            if change=='wrong-native':bad['source']['nativeBeforeIME']['text']='foreign'
            if change=='sensitive':bad['source']['nativeBeforeIME']['sensitive']=True
            if change=='future-attempt':bad['source']['imeEpochMs']=bad['capturedEpochMs']+1
            if change=='wrong-version':bad['picoBrowserVersion']=2
            if change=='false-integer':bad['source']['nativeBeforeIME']['cursor']=True
            with self.subTest(change=change),self.assertRaises(NativeUIError):validate(bad,call,123,bad['capturedEpochMs'])


if __name__=='__main__':unittest.main()
