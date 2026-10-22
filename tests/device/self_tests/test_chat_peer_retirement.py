"""Original private files and FD ownership with synthetic native/clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.chat_journey.peer_retirement import ChatPeerRetirementFiles
from adapters.chat_peer_input import ChatPeerInput
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_peer_input_close as close_seams
from self_tests.test_native_chat_observation import RUN


class PeerRetirementTests(unittest.TestCase):
    def setUp(self):
        self.s=close_seams.PeerInputCloseTests();self.s.setUp();self.addCleanup(self.s.doCleanups)
        self.files=self.s.s.h.transport;self.retiring=[];self.addCleanup(self.detach)
    def detach(self):
        for files in self.retiring:files.detach()
    def make(self):
        files=ChatPeerRetirementFiles(self.files,self.s.owner);self.retiring.append(files);return files
    def complete(self):
        self.s.reader.perform(RUN,'observe');self.s.owner.run()
    def request(self,operation='inspect',nonce='e'*32):return self.s.s.h.request(operation,nonce)

    def test_original_consumed_channel_gets_its_own_strict_fd_and_never_replaces_old_callback(self):
        self.complete();before=deepcopy(self.files.store.read());original=object();self.files.phase_fence=original
        self.s.s.h.clock+=2 # Historical consumed handoff is never retimed as a fresh native sample.
        with self.s.lock.held():
            fresh=self.make();self.assertEqual(before,fresh.store.read());self.assertIsNone(getattr(fresh,'phase_fence',None))
            self.assertIs(original,self.files.phase_fence);self.assertIsNotNone(fresh.fd_owner)
            self.assertNotEqual(self.files.fd,fresh.fd);self.assertIs(fresh._chat_input_close_owner,self.s.owner)
            request=self.request('retire');fresh.send(request);self.s.s.h.actor.native.epoch=self.s.epoch();self.s.s.h.actor.tick()
            native=decode(fresh.read());self.assertTrue(native['source']['retired']);self.assertEqual(request['commandId'],native['source']['retiredCommandId'])
            result=fresh.close();self.assertTrue(result['removed']);self.assertEqual(result,fresh.store.read())
            self.assertTrue(fresh.fd_owner.closed);self.assertGreaterEqual(self.files.fd,0);self.files._check_source()
            self.assertIs(original,self.files.phase_fence)

    def test_unfinished_input_close_or_late_original_receipt_handle_never_creates_transport(self):
        with self.s.lock.held(),self.assertRaises(NativeUIError):self.make()
        self.assertIsNone(getattr(self.files,'_chat_retirement_transport',None))
        self.complete();released=self.files.released
        original_receipt={key:self.s.owner.original_receipt[key] for key in ('device','inode')}
        self.files.released=lambda value:False if value==original_receipt else released(value)
        with self.s.lock.held(),self.assertRaises(NativeUIError):self.make()
        self.assertIsNone(getattr(self.files,'_chat_retirement_transport',None))

    def test_fresh_writer_cannot_observe_another_run_or_reopen_peer_input_or_discard_retained_close(self):
        self.complete()
        with self.s.lock.held():
            fresh=self.make();before=deepcopy(fresh.store.read())
            for request in (self.request('observe'),self.request()|dict(runId='f'*32)):
                with self.subTest(request=request),self.assertRaises(NativeUIError):fresh.send(request)
                self.assertEqual(before,fresh.store.read())
            with self.assertRaises(NativeUIError):fresh.close(retain=False)
            with self.assertRaises(NativeUIError):self.make()
            with self.assertRaises(NativeUIError):ChatPeerInput(fresh,self.s.s.store,RUN)
            self.assertEqual(before,fresh.store.read())

    def test_unconsumed_original_inspect_is_never_adopted_or_relabelled_during_reconstruction(self):
        self.complete()
        with self.s.lock.held():
            request=self.request();self.files.send(request);before=deepcopy(self.files.store.read())
            with self.assertRaises(NativeUIError):self.make()
            self.assertEqual(before,self.files.store.read());self.assertNotEqual(request['commandId'],before['result']['commandId'])
            self.assertIsNone(getattr(self.files,'_chat_retirement_transport',None))


if __name__=='__main__':unittest.main()
