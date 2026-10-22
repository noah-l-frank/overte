"""Original Pico QML send boundary over explicit synthetic SDK/native seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
import test_normal_chat as sources
from adapters.pico4.navigation import NativeNavigationIO


class TransportHookTests(unittest.TestCase):
    def setUp(self):
        self.h=sources.PicoChatTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.io=self.h.flow.io.original.navigation.io

    def test_final_guard_then_exact_command_copy_then_single_original_writer(self):
        events=[];guard=self.io.guard;writer=self.h.native.write_debug_app_file
        def guarded():guard();events.append('guard')
        def callback(command):
            self.assertEqual('guard',events[-1]);events.append('callback')
            self.original=deepcopy(command)
            command['controlToken']='foreign';command['extra']={'nested':True}
        def written(*args,**kwargs):
            self.assertEqual('callback',events[-1]);events.append('write')
            return writer(*args,**kwargs)
        self.io.bind_before_send(callback);self.io.bind_before_send(callback)
        with patch.object(self.io,'guard',side_effect=guarded),patch.object(self.h.native,'write_debug_app_file',side_effect=written):
            self.h.flow.select_channel('domain')
        self.assertEqual(1,events.count('callback'));self.assertEqual(1,events.count('write'))
        self.assertEqual([self.original],self.h.native.inputs)
        self.assertEqual('chat.domain',self.original['controlId'])
        self.assertTrue(self.original['controlToken']);self.assertNotIn('extra',self.original)

    def test_callback_failure_prevents_publication_and_is_not_retried(self):
        seen=[]
        def failed(command):seen.append(deepcopy(command));raise RuntimeError('owned admission refused')
        self.io.bind_before_send(failed)
        with self.assertRaisesRegex(RuntimeError,'owned admission refused'):self.h.flow.select_channel('domain')
        self.assertEqual(1,len(seen));self.assertEqual([],self.h.native.inputs);self.assertEqual([],self.h.widget.calls)

    def test_changed_candidate_is_refused_before_callback(self):
        seen=[];self.io.bind_before_send(seen.append);self.h.native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):self.h.flow.select_channel('domain')
        self.assertEqual([],seen);self.assertEqual([],self.h.native.inputs)

    def test_original_callback_owner_cannot_be_replaced_or_cleared(self):
        first=lambda _command:None
        self.io.bind_before_send(first)
        for other in (None,False,lambda _command:None):
            with self.assertRaises(RuntimeError):self.io.bind_before_send(other)
        self.assertIs(first,self.io._before_send)
        with self.assertRaises(RuntimeError):NativeNavigationIO(None,None,None,None,before_send=False)
        constructed=NativeNavigationIO(None,None,None,None,before_send=first)
        self.assertIs(first,constructed._before_send)

    def test_unbound_default_preserves_original_normal_input(self):
        self.assertIsNone(self.io._before_send);self.h.flow.select_channel('domain')
        self.assertEqual(1,len(self.h.native.inputs));self.assertEqual('domain',self.h.widget.channel)


if __name__=='__main__':unittest.main()
