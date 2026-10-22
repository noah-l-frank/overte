"""Original Pico controller routing with explicit native stage/SDK seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
import test_normal_chat as sources


class ControllerHookTests(unittest.TestCase):
    def setUp(self):
        self.h=sources.PicoChatTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.io=self.h.flow.io.original.navigation.io
        self.h.widget.tablet=False;self.h.widget.panel=False;self.h.native.opened=False

    def test_original_session_receives_exact_operation_and_same_host_only_callback(self):
        events=[]
        def before(operation):self.assertEqual('tablet.open',operation);events.append('admission')
        def intent(envelope):events.append('intent');self.assertEqual('tablet.open',envelope['commands'][0]['operation'])
        def stage(identity,operation,arguments,*,intent):
            self.assertEqual(['admission'],events);self.assertIs(host_intent,intent)
            self.assertEqual(self.io.identity,identity);self.assertEqual({'holdMilliseconds':1000},arguments)
            intent({'commands':[{'operation':operation}]});events.append('stage')
            self.h.native.opened=True;self.h.widget.tablet=True
            return {'performed':True}
        host_intent=intent;self.io.bind_controller_admission(before,intent=intent)
        self.io.bind_controller_admission(before,intent=intent)
        with patch.object(self.h.native,'stage',side_effect=stage):self.h.flow.open()
        self.assertEqual(['admission','intent','stage'],events)
        self.assertTrue(self.h.widget.panel);self.assertEqual(1,len(self.h.native.inputs))

    def test_denied_final_admission_keeps_original_intent_without_stage_or_qml_input(self):
        def refused(_operation):raise RuntimeError('original admission refused')
        self.io.bind_controller_admission(refused,intent=lambda _envelope:None)
        with patch.object(self.h.native,'stage') as stage:
            with self.assertRaisesRegex(RuntimeError,'original admission refused'):self.h.flow.open()
            stage.assert_not_called()
        self.assertTrue(self.h.flow.io.original.navigation.path.exists())
        self.assertEqual([],self.h.native.inputs);self.assertFalse(self.h.widget.tablet)

    def test_controller_owner_pair_cannot_be_partially_replaced_or_cleared(self):
        before=lambda _operation:None;intent=lambda _envelope:None
        self.io.bind_controller_admission(before,intent=intent)
        for callback,host in ((before,None),(None,intent),(lambda _operation:None,intent),(before,lambda _envelope:None)):
            with self.assertRaises(RuntimeError):self.io.bind_controller_admission(callback,intent=host)
        self.assertIs(before,self.io._before_controller);self.assertIs(intent,self.io._controller_intent)


if __name__=='__main__':unittest.main()
