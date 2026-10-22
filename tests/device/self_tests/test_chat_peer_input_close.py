"""Original journals/private files with explicit synthetic native/FD/time seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch

from adapters.chat_actor_files import node
from adapters.chat_journey.peer_input_close import ChatPeerInputClose
from adapters.chat_peer_input import COMMAND,RECEIPT
from adapters.native_chat_observation import NativeChatObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from self_tests import test_chat_peer_input as input_seams
from self_tests import test_chat_cache_lifetime as cache_seams
from self_tests.test_native_chat_observation import RUN


class PeerInputCloseTests(unittest.TestCase):
    def setUp(self):
        self.s=input_seams.PeerInputTests();self.s.setUp();self.addCleanup(self.s.doCleanups)
        self.s.h.transport.clock_ms=self.epoch
        def receipt(value):
            value['native'].update(peerInputVersion=3,avatarSha256='7'*64,avatarPosition=dict(x=2.,y=0.,z=2.),
                scriptPolls=1,releaseConsumed=True,capturedEpochMs=self.epoch())
        self.s.mutate=receipt;self.s.peer.issue('release');self.polls=1;self.close_fd=True;self.leak=None;self.report_closed=False
        self.s.h.actor.native=cache_seams.NativeBoundary()
        def envelope(value):
            if self.s.fd>=0 and not (self.s.h.root/RECEIPT).exists() and self.close_fd:self.s.close()
            def path(name):
                original=self.s.h.root/name
                return dict(present=True,node=node(original.stat())) if original.exists() else dict(present=False,node={})
            opened=self.s.fd>=0 and not (self.report_closed and not (self.s.h.root/RECEIPT).exists())
            value['inputLifetime']=dict(inputLifetimeVersion=1,commandId=value['native']['commandId'],runId=RUN,
                instance='d'*32,ownerRunId=RUN,sequence=1,scriptPolls=self.polls,releaseConsumed=True,
                processId=123,capturedEpochMs=self.epoch(),command=path(COMMAND),receipt=path(RECEIPT),
                receiptHandle=dict(open=opened,node=node(os.fstat(self.s.fd)) if opened else {}))
        self.s.h.actor.mutate=envelope
        def read():
            if self.leak=='after' and not (self.s.h.root/RECEIPT).exists():self.polls+=1
            if self.leak=='before':self.polls+=1
            self.s.h.actor.native.epoch=self.epoch();self.s.h.actor.tick();return self.s.h.transport.read()
        self.reader=NativeChatObservation(self.s.h.transport.send,read,self.epoch,lambda:True,123,
            monotonic=lambda:self.s.h.clock,sleep=self.sleep)
        self.lock=ScriptSourceLock(self.s.h.root.parent/'script-sources.lock')
        self.store=PrivateFeatureState(self.s.h.root.parent/'input-close.json')
        self.owner=self.make()

    def epoch(self):return 20000+int(self.s.h.clock*1000)
    def sleep(self,delay):self.s.h.clock+=delay
    def make(self):return ChatPeerInputClose(self.s.peer,self.reader,self.store,self.lock,
        monotonic=lambda:self.s.h.clock,sleep=self.sleep)

    def test_actual_original_unlinks_native_fd_and_two_full_quiet_windows_retain_all_journals(self):
        before=self.s.h.clock;result=self.owner.run()
        self.assertEqual('complete',result['phase']);self.assertGreaterEqual(self.s.h.clock-before,6)
        self.assertFalse((self.s.h.root/COMMAND).exists());self.assertFalse((self.s.h.root/RECEIPT).exists())
        self.assertEqual(-1,self.s.fd);self.assertIsNotNone(self.s.store.read());self.assertIsNotNone(self.store.read())
        stages=[row['stage'] for row in self.owner.frames];self.assertIn('before',stages);self.assertIn('after',stages)
        with self.assertRaises(NativeUIError):self.s.peer.issue('inspect')
        with self.assertRaises(NativeUIError):self.owner.run()
        with self.assertRaises(NativeUIError):self.make()
        self.assertEqual(1,self.s.count)

    def test_post_removal_poll_prevents_completion(self):
        self.leak='after'
        with self.assertRaises(NativeUIError):self.owner.run()
        self.assertFalse((self.s.h.root/COMMAND).exists());self.assertFalse((self.s.h.root/RECEIPT).exists())
        self.assertNotEqual('complete',self.store.read()['phase']);self.assertTrue(self.owner.failed)
        with self.assertRaises(NativeUIError):self.owner.run()
        self.assertEqual(1,self.s.count)

    def test_reported_closed_handle_requires_independent_actual_fd_absence(self):
        self.close_fd=False;self.report_closed=True
        with self.assertRaises(NativeUIError):self.owner.run()
        self.assertGreaterEqual(self.s.fd,0);self.assertTrue(self.owner.failed)
        self.assertFalse((self.s.h.root/RECEIPT).exists());self.assertNotEqual('complete',self.store.read()['phase'])
        with self.assertRaises(NativeUIError):self.s.peer.issue('inspect')
        self.assertEqual(1,self.s.count)

    def test_original_pre_removal_poll_prevents_any_unlink(self):
        self.leak='before'
        with patch('adapters.chat_journey.peer_input_close.os.unlink',wraps=os.unlink) as remove:
            with self.assertRaises(NativeUIError):self.owner.run()
            self.assertEqual([], [call for call in remove.call_args_list if call.args and call.args[0] in (COMMAND,RECEIPT)])
        self.assertTrue((self.s.h.root/COMMAND).exists());self.assertTrue((self.s.h.root/RECEIPT).exists())

    def test_lost_unlink_receipt_never_retries_or_overwrites_its_durable_intent(self):
        original=self.store.write
        def lost(value,previous):
            if value['phase']=='command-removal-observed':raise OSError('Lost original unlink receipt')
            return original(value,previous)
        self.store.write=lost
        with self.assertRaises(NativeUIError):self.owner.run()
        saved=self.store.read();self.assertEqual('command-removal-issued',saved['phase'])
        self.assertFalse((self.s.h.root/COMMAND).exists());self.assertTrue((self.s.h.root/RECEIPT).exists())
        self.store.write=original
        with self.assertRaises(NativeUIError):self.owner.run()
        self.assertEqual(saved,self.store.read());self.assertTrue((self.s.h.root/RECEIPT).exists())

    def test_foreign_command_replacement_after_intent_is_never_removed(self):
        original=self.store.write;replacement_node=[]
        def replaced(value,previous):
            result=original(value,previous)
            if value['phase']=='command-removal-issued':
                path=self.s.h.root/COMMAND;temporary=self.s.h.root/'foreign-input'
                temporary.write_bytes(path.read_bytes());temporary.chmod(0o600)
                os.replace(temporary,path);replacement_node.append(node(path.stat()))
            return result
        self.store.write=replaced
        with self.assertRaises(NativeUIError):self.owner.run()
        self.assertEqual(replacement_node[-1],node((self.s.h.root/COMMAND).stat()))
        self.assertTrue((self.s.h.root/RECEIPT).exists())
        self.assertEqual('command-removal-issued',self.store.read()['phase'])

    def test_consumed_restore_receipt_without_original_distant_observations_cannot_close_held_peer(self):
        seam=input_seams.PeerInputTests();seam.setUp();self.addCleanup(seam.doCleanups)
        def receipt(value):
            value['native'].update(peerInputVersion=3,avatarSha256='7'*64,avatarPosition=dict(x=2.,y=0.,z=2.),
                scriptPolls=seam.count,releaseConsumed=value['native']['operation']=='release')
        seam.mutate=receipt
        seam.peer.issue('hold',position=dict(x=40.,y=0.,z=2.));seam.peer.issue('restore');seam.peer.issue('release')
        reader=NativeChatObservation(seam.h.transport.send,lambda:None,lambda:20000,lambda:True,123)
        store=PrivateFeatureState(seam.h.root.parent/'close-held.json')
        with self.assertRaises(NativeUIError):ChatPeerInputClose(seam.peer,reader,store,
            ScriptSourceLock(seam.h.root.parent/'script-sources.lock'))
        self.assertIsNone(store.read());self.assertTrue((seam.h.root/COMMAND).exists())
        self.assertTrue((seam.h.root/RECEIPT).exists());self.assertEqual(3,seam.count)

    def test_slow_last_intent_native_clock_with_frozen_host_cannot_unlink(self):
        original=self.store.write
        def slow(value,previous):
            result=original(value,previous)
            if value['phase']=='command-removal-issued':self.s.h.transport.clock_ms=lambda:self.epoch()+2000
            return result
        self.store.write=slow
        with self.assertRaises(NativeUIError):self.owner.run()
        self.assertEqual('command-removal-issued',self.store.read()['phase'])
        self.assertTrue((self.s.h.root/COMMAND).exists());self.assertTrue((self.s.h.root/RECEIPT).exists())


if __name__=='__main__':unittest.main()
