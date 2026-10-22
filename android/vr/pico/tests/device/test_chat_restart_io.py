"""Actual Pico restart factory/host session; candidate/device IO are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch

import test_normal_scripts as pico_seams
from openxr_input.adapter_session import PicoOpenXrAdapterSession


class PicoChatRestartFactoryTests(unittest.TestCase):
    def setUp(self):
        self.pico=pico_seams.PicoNormalScriptsTests();self.pico.setUp();self.addCleanup(self.pico.doCleanups)
        self.instance,self.native=self.pico.instance,self.pico.native
        # The restart source requires the original numeric kernel PID:start ABI.
        self.native.identity='123:456';root=self.pico.fixture.state_root/'original-chat-input-session';root.mkdir(mode=0o700)
        self.session=PicoOpenXrAdapterSession(object(),self.native.target,root);self.session.begin(self.native.identity)
        patcher=patch.object(self.instance,'pico_input_session',return_value=self.session);patcher.start();self.addCleanup(patcher.stop)
    def test_original_pico_factory_only_captures_current_binding_and_host_cursor_without_target_input(self):
        binding=self.instance._scripts(self.native.target).binding;before=self.session.state_path.read_bytes()
        owner=self.instance._chat_restart_io(self.native.target,binding);self.addCleanup(owner.close_host)
        self.assertEqual(binding,owner.binding);self.assertEqual(binding['processIdentity'],owner.cursor['state']['processIdentity'])
        self.assertEqual(before,self.session.state_path.read_bytes());self.assertFalse(owner.stop_called);self.assertFalse(owner.launch_called)
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)
    def test_original_candidate_or_foreign_binding_prevents_restart_owner_construction(self):
        binding=self.instance._scripts(self.native.target).binding;before=self.session.state_path.read_bytes()
        with self.assertRaises(ValueError):self.instance._chat_restart_io(self.native.target,binding|dict(processIdentity='456:789'))
        self.native.digest='f'*64
        with self.assertRaises(ValueError):self.instance._chat_restart_io(self.native.target,binding)
        self.assertEqual(before,self.session.state_path.read_bytes());self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)


if __name__=='__main__':unittest.main()
