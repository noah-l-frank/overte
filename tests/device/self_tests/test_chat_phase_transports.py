"""Actual child CAS/transport fences on explicit native/OS/HTTP clock seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack
from self_tests import test_chat_phase_fence as phases
from self_tests import test_chat_background as backgrounds
from self_tests import test_chat_mixer_owner as mixers
from self_tests.test_native_chat_observation import RUN


class PhaseTransportTests(unittest.TestCase):
    def setUp(self):
        self.phase=phases.PhaseFenceTests();self.phase.setUp();self.addCleanup(self.phase.doCleanups)
    def clocks(self,epoch,host):
        self.phase.fence.source.epoch_ms=epoch;self.phase.fence.source.monotonic=host
        self.phase.h.journal.clock=epoch
    def changed(self):self.phase.h.journal.activate(RUN,uuid.uuid4().hex,'open',{})

    def test_mixer_cas_changed_phase_does_not_publish_http_command(self):
        h=mixers.MixerOwnerTests();h.setUp();self.addCleanup(h.doCleanups)
        self.clocks(h.epoch,lambda:h.clock);h.owner.phase_fence=h.owner.controls[0].phase_fence=self.phase.fence
        write=h.store.write
        def changed(value,previous):
            write(value,previous)
            if value['phase']=='issuing-offline':self.changed()
        h.store.write=changed
        with self.phase.flow.session():
            with self.assertRaises(NativeUIError):h.owner.remove(20000)
        self.assertEqual([],h.controller.posts);self.assertTrue(h.h.primary.mixer)
        self.assertTrue(h.store.path.exists());self.assertTrue(self.phase.fence.failed)

    def test_background_home_cas_changed_phase_prevents_home_without_qt_borrowing(self):
        h=backgrounds.BackgroundTests();h.setUp();self.addCleanup(h.doCleanups)
        self.clocks(lambda:h.native.epoch,lambda:h.native.host)
        h.owner.phase_fence=h.owner.source.phase_fence=h.owner.os.phase_fence=self.phase.fence
        write=h.store.write
        def changed(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['phase']=='background-issued':self.changed()
        h.store.write=changed
        with self.phase.flow.session():
            with self.assertRaises(NativeUIError):h.owner.run(20000)
        self.assertEqual([],h.original.inputs);self.assertTrue(h.original.foreground)
        self.assertTrue(h.store.path.exists());self.assertTrue(self.phase.fence.failed)

    def test_background_resume_native_jump_under_frozen_host_prevents_resume_and_qt_reads(self):
        h=backgrounds.BackgroundTests();h.setUp();self.addCleanup(h.doCleanups)
        self.clocks(lambda:h.native.epoch,lambda:h.native.host)
        h.owner.phase_fence=h.owner.source.phase_fence=h.owner.os.phase_fence=self.phase.fence
        invoke=h.original.invoke;qt_after_home=[]
        def input(*args):
            value=invoke(*args)
            if args[1]=='lifecycle.background':qt_after_home.append(len(h.h.view.commands))
            return value
        h.original.invoke=input;write=h.store.write
        def changed(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['phase']=='foreground-issued':h.native.epoch+=2000
        h.store.write=changed
        with self.phase.flow.session():
            with self.assertRaises(NativeUIError):h.owner.run(20000)
        self.assertEqual(['lifecycle.background'],h.original.inputs);self.assertFalse(h.original.foreground)
        self.assertEqual([len(h.h.view.commands)],qt_after_home)
        self.assertTrue(h.store.path.exists());self.assertTrue(self.phase.fence.failed)


if __name__=='__main__':unittest.main()
