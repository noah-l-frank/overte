"""One existing Audio owner through normal page, cycles and original restore."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
from ios.self_tests.audio_page_cycle_domain import AudioPageCycleDomain
from ios.self_tests.test_ios_audio_recorded_owner import AudioRecordedOwnerTests,RUN,BINDING
from ios.self_tests.test_ios_audio_pcm_lease import PCMModel


class AudioPageCycleTests(unittest.TestCase):
    def setUp(self):
        self.f=AudioRecordedOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.model=AudioPageCycleDomain(self.f.root);self.f.model.add_phase('open','3'*32)

    def test_normal_open_owned_completion_pcm_retirement_and_original_page_mute_restore(self):
        f=self.f;m=f.model;m.muted=True
        with f.owner() as owner:
            opened=owner.act(m.ticket,'open');self.assertEqual(dict(open=True,muted=False),opened['state'])
            self.assertEqual(0,owner.state['operations'][0]['launcher']['launcherCurrentIndex'])
            m.add_phase('record-start','4'*32);owner.act(m.ticket,'record-start')
            m.add_phase('await-completion','5'*32);owner.act(m.ticket,'await-completion')
            pcm=PCMModel(m);native,preview=pcm.reader();store=PrivateFeatureState(f.root/'ios-audio-pcm-lease.json')
            lease=IOSAudioPCMLease(store,owner,native=native,preview=preview);lease.capture();lease.retire()
            m.add_phase('close','6'*32);closed=owner.act(m.ticket,'close')
            self.assertEqual(dict(open=False,muted=True),closed['state']);self.assertEqual('closed',m.page_model.route)
            self.assertEqual(0,m.page_model.page);self.assertEqual(2,len(owner.state['operations'][-1]['quiet']))
            url=owner.fixture_url;expected=deepcopy(owner.state)
        with f.lock.held():
            archive=IOSAudioRecordedOwner.archive(f.store,f.root,BINDING,RUN,f.lock,url);self.assertEqual(expected,archive.state)
        self.assertEqual(1,m.actions.count('audio.record'));self.assertEqual(2,m.actions.count('audio.mute'))

    def test_open_lost_normal_entry_is_observed_without_a_second_entry_click(self):
        f=self.f;m=f.model;m.page_model.lost='audio.entry'
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'open')
        with f.owner() as owner:self.assertTrue(owner.act(m.ticket,'open')['state']['open'])
        self.assertEqual(1,m.page_model.actions.count('audio.entry'))

    def test_ignored_normal_entry_stays_owned_without_replay(self):
        f=self.f;m=f.model;m.page_model.ignore='audio.entry'
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'open')
        m.page_model.ignore=None
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'open')
        self.assertEqual(1,m.page_model.actions.count('audio.entry'))

    def test_active_capture_cannot_be_hidden_as_page_cleanup(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            owner.act(m.ticket,'open');m.add_phase('record-start','4'*32);owner.act(m.ticket,'record-start')
            before=deepcopy(m.page_model.actions);m.add_phase('close','6'*32)
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'close')
            self.assertEqual(before,m.page_model.actions);self.assertEqual('audio',m.page_model.route)

    def test_lost_final_close_is_observed_without_a_second_close_or_home(self):
        f=self.f;m=f.model
        with f.owner() as owner:owner.act(m.ticket,'open')
        m.add_phase('close','6'*32);m.page_model.lost='tablet.close'
        with self.assertRaises(NativeUIError):
            with f.owner() as owner:owner.act(m.ticket,'close')
        actions=deepcopy(m.page_model.actions)
        with f.owner() as owner:
            self.assertFalse(owner.act(m.ticket,'close')['state']['open'])
            self.assertTrue(any(row['verb']=='page' and not row['returned'] for row in owner.state['operations'][-1]['inputs']))
        self.assertEqual(actions,m.page_model.actions);self.assertEqual(1,m.page_model.actions.count('tablet.close'))

    def test_live_pcm_files_block_close_before_any_page_input(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            owner.act(m.ticket,'open');m.add_phase('record-start','4'*32);owner.act(m.ticket,'record-start')
            m.add_phase('await-completion','5'*32);owner.act(m.ticket,'await-completion')
            pcm=PCMModel(m);native,preview=pcm.reader();store=PrivateFeatureState(f.root/'ios-audio-pcm-lease.json')
            lease=IOSAudioPCMLease(store,owner,native=native,preview=preview);lease.capture()
            m.add_phase('close','6'*32);actions=deepcopy(m.page_model.actions)
            with self.assertRaises(NativeUIError):owner.act(m.ticket,'close')
            self.assertEqual(actions,m.page_model.actions);self.assertEqual('audio',m.page_model.route);self.assertTrue(pcm.files)
            lease.retire();self.assertFalse(owner.act(m.ticket,'close')['state']['open'])

    def test_archived_page_actions_reject_wrong_control_or_changed_opening_reference(self):
        f=self.f;m=f.model
        with f.owner() as owner:
            owner.act(m.ticket,'open');m.add_phase('close','6'*32);owner.act(m.ticket,'close')
            state=deepcopy(owner.state);url=owner.fixture_url
        with f.lock.held():
            archive=IOSAudioRecordedOwner.archive(f.store,f.root,BINDING,RUN,f.lock,url)
            bad=deepcopy(state);bad['operations'][0]['inputs'][0]['identifier']='audio.record'
            with self.assertRaises(NativeUIError):archive.decode(archive.envelope(bad))
            bad=deepcopy(state);bad['operations'][-1]['openedBefore']=deepcopy(bad['operations'][-1]['before'])
            with self.assertRaises(NativeUIError):archive.decode(archive.envelope(bad))
