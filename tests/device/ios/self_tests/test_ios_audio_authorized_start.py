"""Normal WDA intent/OS decision ownership, with explicit native/SDK models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import time
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import check as transport_check
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters.audio_authorized_start import AudioAuthorizedStarts
from ios.adapters.audio_authorization_sources import AudioAuthorizationSources
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.self_tests.test_ios_audio_authorization_sources import AuthorizationDomain
from ios.self_tests import test_ios_audio_recorded_owner as recording


class StartDomain:
    def __init__(self,case,*,real_time=False):
        self.d=AuthorizationDomain(case,started=False,model=RealHostModel() if real_time else None);self.before_click=None
        parent=self.d.parent;original=parent.ui.io.original.ui.click_with_token
        def click(locator,token):
            transport_check()
            if self.before_click:self.before_click()
            transport_check();return original(locator,token)
        parent.ui.io.original.ui.click_with_token=click
        self.store=PrivateFeatureState(self.d.f.root/'ios-audio-authorized-starts.json')
        self.owner=self.reopen()
    def reopen(self):
        self.owner=AudioAuthorizedStarts(self.store,self.d.parent,self.d.owner);return self.owner
    def act(self):return self.owner.act(self.d.m.ticket)


class RealHostModel(recording.Model):
    """New producer snapshots share a real host clock, retaining native offset."""
    @property
    def clock(self):return time.monotonic()-self._origin
    @clock.setter
    def clock(self,value):self._origin=time.monotonic()-value
    def tick(self):pass
    def sleep(self,seconds):
        if seconds:time.sleep(seconds)


class AudioAuthorizedStartTests(unittest.TestCase):
    def setUp(self):self.s=StartDomain(self,real_time=self._testMethodName=='test_real_host_cpu_and_original_native_offset_fit_the_actual_input_grant_window')

    def test_actual_normal_start_requires_original_grant_and_retains_independent_after_cut(self):
        s=self.s;result=s.act();self.assertEqual('capturing',result['state']['phase'])
        self.assertEqual(1,s.d.m.actions.count('audio.record'));self.assertEqual('complete',s.owner.state['entries'][0]['phase'])
        before=s.d.owner.frame(result['authorizationBefore']);after=s.d.owner.frame(result['authorizationAfter'])
        self.assertEqual('before-start',before['stage']);self.assertEqual('after-start',after['stage'])
        self.assertTrue(result['historical']);self.assertNotEqual(before['originals']['session']['requestId'],after['originals']['session']['requestId'])

    def test_denied_before_input_can_use_only_a_new_actual_grant_without_replaying_record(self):
        s=self.s;s.d.session.gate['osPermission']=2
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual(0,s.d.m.actions.count('audio.record'));self.assertEqual('denied',s.owner.state['entries'][0]['phase'])
        denied=s.owner.state['entries'][0]['attempts'][0]['before'];body=s.d.owner.frame(denied)
        s.d.session.gate['osPermission']=1;result=s.act()
        self.assertEqual('capturing',result['state']['phase']);self.assertEqual(1,s.d.m.actions.count('audio.record'))
        self.assertEqual(body,s.d.owner.frame(denied));self.assertEqual(2,len(s.owner.state['entries'][0]['attempts']))

    def test_unknown_os_authorization_does_not_deliver_record(self):
        s=self.s;s.d.session.gate['osPermission']=0
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual(0,s.d.m.actions.count('audio.record'));self.assertEqual('unknown',s.owner.state['entries'][0]['attempts'][0]['decision'])

    def test_lost_record_return_resolves_from_product_without_second_record(self):
        s=self.s;s.d.m.loss=True
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual(1,s.d.m.actions.count('audio.record'));self.assertEqual('record-intent',s.owner.state['entries'][0]['phase'])
        s.d.m.loss=False;s.reopen();result=s.act()
        self.assertEqual('capturing',result['state']['phase']);self.assertEqual(1,s.d.m.actions.count('audio.record'))

    def test_ignored_record_is_not_a_second_authorized_attempt(self):
        s=self.s;s.d.m.ignore=True
        with self.assertRaises(NativeUIError):s.act()
        s.d.m.ignore=False
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual(1,s.d.m.actions.count('audio.record'));self.assertEqual(1,len(s.owner.state['entries'][0]['attempts']))

    def test_actual_transport_expiry_after_intent_prevents_click_and_resend(self):
        s=self.s;s.before_click=lambda:s.d.m.sleep(1.6)
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual(0,s.d.m.actions.count('audio.record'))
        self.assertEqual('record-intent',s.owner.state['entries'][0]['phase'])
        s.before_click=None
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual(0,s.d.m.actions.count('audio.record'))

    def test_same_byte_replaced_grant_original_refuses_transport(self):
        s=self.s
        def replace():
            reference=s.owner.state['entries'][0]['attempts'][-1]['before'];path=s.d.owner.frames.path(s.d.owner.frames.expand(reference))
            body=path.read_bytes();replacement=path.with_suffix('.replacement');replacement.write_bytes(body);replacement.chmod(0o600);os.replace(replacement,path)
        s.before_click=replace
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual(0,s.d.m.actions.count('audio.record'))

    def test_denied_after_start_remains_failed_without_a_later_green_resample(self):
        s=self.s;send=s.d.session.send
        def revoked(command):
            if s.d.m.active:s.d.session.gate['osPermission']=2
            return send(command)
        s.d.owner.session.send=revoked
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual('blocked-after',s.owner.state['entries'][0]['phase']);count=s.d.source_reads
        s.d.session.gate['osPermission']=1
        with self.assertRaises(NativeUIError):s.act()
        self.assertEqual(count,s.d.source_reads);self.assertEqual(1,s.d.m.actions.count('audio.record'))

    def test_completed_decision_replays_without_native_sdk_or_file_writes(self):
        s=self.s;result=s.act();count=s.d.source_reads;s.d.block=True
        parent=IOSAudioRecordedOwner.archive(s.d.f.store,s.d.f.root,recording.BINDING,recording.RUN,s.d.f.lock,s.d.parent.fixture_url)
        sources=AudioAuthorizationSources.archive(s.d.store,parent)
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical decision attempted a write')):
            archive=AudioAuthorizedStarts.archive(s.store,parent,sources);self.assertEqual(result,archive.result(archive.state['entries'][0]))
        self.assertEqual(count,s.d.source_reads)

    def test_failed_decision_write_prevents_any_record(self):
        s=self.s
        with patch.object(s.store,'write',side_effect=OSError('Declared failed decision CAS')):
            with self.assertRaises(OSError):s.act()
        self.assertEqual(0,s.d.m.actions.count('audio.record'));self.assertIsNone(s.store.read())

    def test_real_host_cpu_and_original_native_offset_fit_the_actual_input_grant_window(self):
        s=self.s;started=time.monotonic();result=s.act();elapsed=time.monotonic()-started
        before=s.d.owner.frame(result['authorizationBefore']);original=s.d.parent.original(result['original'])
        event=original['originals']['native']['audio']['recordedVoice']['events'][0]
        self.assertLess(event['publishedEpochMs']-before['originals']['session']['clockBefore']['epochMs'],1500)
        self.assertLess(elapsed,25);self.assertEqual(1,s.d.m.actions.count('audio.record'))
        self.assertGreater(before['clockJoin']['hostBeforeEpochMs']-before['clockJoin']['nativeBefore']['capturedEpochMs'],1000000)

    def test_lost_saved_before_cut_is_adopted_without_another_permission_query(self):
        s=self.s;write=OriginalFrameStore.write;saved={}
        def lost(store,index,value):
            reference=write(store,index,value)
            if store.namespace=='ios-audio-authorization' and value['stage']=='before-start':
                path=store.path(store.expand(reference));saved.update(path=path,body=path.read_bytes(),inode=path.stat().st_ino)
                raise OSError('Declared lost saved before authorization cut')
            return reference
        with patch.object(OriginalFrameStore,'write',lost):
            with self.assertRaises(OSError):s.act()
        self.assertEqual(0,s.d.m.actions.count('audio.record'));self.assertEqual(1,len(s.d.session.queries))
        s.reopen();result=s.act();self.assertEqual('capturing',result['state']['phase'])
        self.assertEqual(2,len(s.d.session.queries));self.assertEqual(1,s.d.m.actions.count('audio.record'))
        self.assertEqual(saved['body'],saved['path'].read_bytes());self.assertEqual(saved['inode'],saved['path'].stat().st_ino)

    def test_old_recovered_grant_is_retained_as_expired_before_a_new_actual_decision(self):
        s=self.s;write=OriginalFrameStore.write
        def lost(store,index,value):
            reference=write(store,index,value)
            if store.namespace=='ios-audio-authorization' and value['stage']=='before-start':raise OSError('Declared saved before cut interruption')
            return reference
        with patch.object(OriginalFrameStore,'write',lost):
            with self.assertRaises(OSError):s.act()
        s.d.m.sleep(1.6);s.reopen()
        with self.assertRaises(NativeUIError):s.act()
        expired=s.owner.state['entries'][0]['attempts'][0];self.assertEqual('expired',expired['decision'])
        self.assertEqual('granted',expired['permission']);self.assertEqual(0,s.d.m.actions.count('audio.record'))
        s.act();self.assertEqual(1,s.d.m.actions.count('audio.record'));self.assertEqual(2,len(s.owner.state['entries'][0]['attempts']))


class AudioAuthorizedPageFlowTests(unittest.TestCase):
    def test_normal_page_grant_record_auto_completion_pcm_release_and_original_close(self):
        from ios.self_tests.audio_page_cycle_domain import AudioPageCycleDomain
        from ios.self_tests.test_ios_audio_pcm_file import OriginalPCM,stereo
        from feature_journeys.fixtures import challenge
        from feature_journeys.evidence import file_observation
        from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
        d=AuthorizationDomain(self,started=False,model_factory=AudioPageCycleDomain);parent=d.parent;m=d.m
        m.add_phase('open','3'*32);parent.act(m.ticket,'open');m.add_phase('record-start','4'*32)
        ui=parent.ui.io.original.ui;click=ui.click_with_token
        def guarded(locator,token):transport_check();return click(locator,token)
        ui.click_with_token=guarded
        starts=AudioAuthorizedStarts(PrivateFeatureState(d.f.root/'ios-audio-authorized-starts.json'),parent,d.owner)
        result=starts.act(m.ticket);record_ticket=m.ticket;self.assertEqual('capturing',result['state']['phase'])
        m.add_phase('await-completion','5'*32);parent.act(m.ticket,'await-completion')
        raw=stereo(challenge(parent.run,record_ticket).hex())
        pcm=OriginalPCM(m,raw,b'\0'*len(raw)*2);native,preview=pcm.reader()
        lease=IOSAudioPCMLease(PrivateFeatureState(d.f.root/'ios-audio-pcm-lease.json'),parent,native=native,preview=preview)
        lease.capture()
        self.assertTrue(file_observation(lease.input_wav(),'audio',parent.run,lease.recording['ticket'],{})['passed'])
        lease.retire();m.add_phase('close','6'*32);self.assertFalse(parent.act(m.ticket,'close')['state']['open'])
        self.assertEqual('closed',m.page_model.route);self.assertEqual(1,m.actions.count('audio.record'))
        archived_parent=IOSAudioRecordedOwner.archive(d.f.store,d.f.root,recording.BINDING,recording.RUN,d.f.lock,parent.fixture_url)
        archived_sources=AudioAuthorizationSources.archive(d.store,archived_parent)
        archived=AudioAuthorizedStarts.archive(starts.store,archived_parent,archived_sources)
        self.assertEqual(result,archived.result(archived.state['entries'][0]))
