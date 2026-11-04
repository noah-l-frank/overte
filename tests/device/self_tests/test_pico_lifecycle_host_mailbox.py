"""Declared GUI timer observations cannot rewrite a public SDK reply."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import threading
import unittest
from adapters.pico4.lifecycle_source import PicoLifecycleSource
from self_tests.pico_lifecycle_host_model import OriginalHostModel,HostUi
from self_tests import test_pico_lifecycle_chat as chat_fixture
from self_tests import test_pico_lifecycle_background_owner as background_fixture
from self_tests.test_pico_lifecycle_source import RUN


class LifecycleHostMailboxTests(unittest.TestCase):
    def test_real_ui_reader_keeps_public_nonce_when_internal_provider_runs_before_getter(self):
        context=OriginalHostModel();ui=HostUi(context);internal=[]
        def original():
            internal.append(ui.observe(dict(commandId='1'*32,runId=RUN)))
            return ui.read()
        reader=PicoLifecycleSource(ui.send,original,context.epoch,lambda:ui.alive,context.pid,
            monotonic=context.now,sleep=context.sleep,field_bindings=True)
        packet=reader.capture(RUN)
        self.assertEqual(ui.commands[-1]['commandId'],packet['commandId'])
        self.assertNotEqual('1'*32,packet['commandId']);self.assertEqual(1,len(ui.commands))
        self.assertEqual('1'*32,internal[-1]['commandId']);self.assertGreater(ui.sequence,packet['sequence'])
        self.assertEqual(2,packet['lifecycleUiVersion']);self.assertEqual(1,internal[-1]['lifecycleUiVersion'])

    def test_actual_autonomous_timer_between_public_send_and_getter_keeps_original_reply_and_single_query(self):
        context=OriginalHostModel();chat=chat_fixture.LifecycleChatTests();chat.setUp(model_context=context);self.addCleanup(chat.doCleanups)
        chat.owner.open_chat();chat.owner.focus_chat();chat.owner.type_chat()
        background=background_fixture.LifecycleBackgroundOwnerTests();background.initialize_from_chat(chat);self.addCleanup(background.doCleanups)
        background.owner.prepare(background.chat)
        with background.lock.held():world,observer,_native=background.owner.live()
        ready=threading.Event();observed=threading.Event();frame=background.history.frame
        def timer_frame(cause):
            frame(cause)
            if cause=='timer' and ready.is_set():observed.set()
        background.history.frame=timer_frame
        with background.lock.held():background.owner.phase('arm-issued');observer.arm(RUN)
        self.assertIsNotNone(background.history.timer_thread);self.assertTrue(background.history.timer_thread.is_alive())
        source=world.source;send,get=source.send,source.original;public=[]
        def publication(request):
            send(request);public.append(deepcopy(request));ready.set()
        def getter():
            self.assertTrue(observed.wait(1),'The actual autonomous timer must run between public send and getter')
            return get()
        source.send=publication;source.original=getter
        before=len(background.native.ui.commands);packet=source.capture(RUN)
        self.assertEqual(1,len(public));self.assertEqual(public[0]['commandId'],packet['commandId'])
        self.assertEqual(before+1,len(background.native.ui.commands))
        self.assertNotEqual('1'*32,packet['commandId']);self.assertGreater(background.native.ui.sequence,packet['sequence'])
        self.assertTrue(background.history.close_host());self.assertFalse(background.history.timer_thread.is_alive())
        # This is host timer retirement only; no native/product cleanup is
        # inferred from stopping a declared model thread.
