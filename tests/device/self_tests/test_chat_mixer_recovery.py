"""Original controller recovery preserves interrupted native transcript ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.mixer_recovery import ChatMixerRecovery
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_mixer_owner as seams
from self_tests.test_native_chat_observation import RUN


class MixerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.MixerOwnerTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.owner.remove(20000)
        # A real interrupted source journal cannot be adopted as ready by a new
        # ChatSamples. Keep that actual private file and every earlier frame.
        self.old=self.h.h.store.read();reading={**self.old,'phase':'reading'}
        self.h.h.store.write(reading,self.old);self.interrupted=deepcopy(reading)
        self.h.h.primary.alive=False
        self.native=[len(self.h.h.primary.commands),len(self.h.h.peer.commands)]
        self.original=deepcopy(self.h.store.read()['transcript'])
    def recovery(self,guard=lambda:True):
        return ChatMixerRecovery(self.h.controls(),self.h.store,self.h.roles[0].binding,RUN,guard,
            component_only=True,monotonic=lambda:self.h.clock)
    def unchanged(self):
        self.assertEqual(self.interrupted,self.h.h.store.read())
        self.assertEqual(self.original,self.h.store.read()['transcript'])
        self.assertEqual(self.native,[len(self.h.h.primary.commands),len(self.h.h.peer.commands)])
    def test_reconstructed_controller_owner_restores_without_adopting_or_reading_interrupted_native_roles(self):
        with self.assertRaises(NativeUIError):self.h.h.sampler()
        result=self.recovery().restore_once();self.assertTrue(result['mixerProcessRestored'])
        self.assertTrue(result['nativeChatUnresolved']);self.assertTrue(result['journalsRetained'])
        self.assertNotIn('state',result);self.assertNotIn('resources',result)
        self.assertEqual('recovery-observed',self.h.store.read()['phase']);self.unchanged()
        with self.assertRaises(NativeUIError):self.recovery().restore_once()
        self.assertEqual(['offline','online'],[row['action'] for row in self.h.controller.posts])
    def test_lost_original_online_response_never_resends_after_reconstruction(self):
        self.h.controller.lost='online'
        with self.assertRaises(NativeUIError):self.recovery().restore_once()
        self.assertEqual('issuing-online',self.h.store.read()['phase']);self.h.controller.lost=None
        result=self.recovery().restore_once();self.assertTrue(result['mixerProcessRestored'])
        self.assertEqual(2,len(self.h.controller.posts));self.unchanged()
    def test_late_original_online_admission_is_observed_passively_without_a_second_input(self):
        self.h.controller.effect=lambda command:None;self.h.controller.lost='online'
        with self.assertRaises(NativeUIError):self.recovery().restore_once()
        self.h.controller.lost=None
        with self.assertRaises(NativeUIError):self.recovery().restore_once()
        self.assertEqual(2,len(self.h.controller.posts));self.unchanged()
        original_online=self.h.controller.posts[1];self.h.controller.apply(original_online)
        self.assertTrue(self.recovery().restore_once()['mixerProcessRestored'])
        self.assertEqual(2,len(self.h.controller.posts));self.unchanged()
    def test_lost_durable_recovery_intent_prevents_control_input_and_keeps_all_originals(self):
        recovery=self.recovery();old_write=recovery.store.write
        def ignore(value,previous):
            if value['phase']=='issuing-online':return
            old_write(value,previous)
        recovery.store.write=ignore
        with self.assertRaises(NativeUIError):recovery.restore_once()
        self.assertEqual(1,len(self.h.controller.posts));self.unchanged()
        recovery.store.write=old_write
        self.assertTrue(self.recovery().restore_once()['mixerProcessRestored']);self.unchanged()
    def test_recovery_intent_fsync_clock_jump_blocks_actual_online_dispatch(self):
        recovery=self.recovery();write=recovery.store.write;wall=0
        for source in recovery.controls:source.clock_ms=lambda:self.h.epoch()+wall
        def persisted(value,previous):
            nonlocal wall
            write(value,previous)
            if value['phase']=='issuing-online':wall=2000
        recovery.store.write=persisted
        with self.assertRaises(NativeUIError):recovery.restore_once()
        self.assertEqual(1,len(self.h.controller.posts));self.assertEqual('issuing-online',self.h.store.read()['phase'])
        self.unchanged()

    def test_candidate_guard_clock_jump_after_live_reads_fails_under_frozen_host_timer(self):
        recovery=self.recovery();wall=0;calls=0
        for source in recovery.controls:source.clock_ms=lambda:self.h.epoch()+wall
        def guarded():
            nonlocal calls,wall
            calls+=1
            if calls==2:wall=2000
            return True
        recovery.guard=guarded
        with self.assertRaises(NativeUIError):recovery.restore_once()
        self.assertEqual(1,len(self.h.controller.posts));self.unchanged()

    def test_changed_fixture_or_candidate_guard_cannot_retarget_recovery(self):
        with self.assertRaises(NativeUIError):self.recovery(guard=lambda:False).restore_once()
        self.h.controller.value['instance']='0'*32
        with self.assertRaises(NativeUIError):self.recovery().restore_once()
        self.assertEqual(1,len(self.h.controller.posts));self.unchanged()


if __name__=='__main__':unittest.main()
