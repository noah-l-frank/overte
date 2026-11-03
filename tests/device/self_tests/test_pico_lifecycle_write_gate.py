"""Actual old writer codecs/CAS under opt-in original typed write permits."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from adapters.normal_ui import NativeUIError
from adapters.chat_journey.archive_file import signature
from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
from self_tests import test_pico_lifecycle_background_raw as raw_fixture


class LifecycleWriteStateGateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=raw_fixture.LifecycleBackgroundRawOwnerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.seams=self.fixture.seams;self.raw=self.fixture.raw
        self.writer=self.seams.chat;self.gate=self.raw.install_writer(self.writer,'chat')

    def test_actual_chat_observe_pack_write_readback_and_original_ofd_retirement(self):
        before=self.writer.store.path.read_bytes();anchor=self.writer.acquisition
        with self.writer.lock.held():self.writer.observe()
        self.assertNotEqual(before,self.writer.store.path.read_bytes())
        self.assertEqual(1,len(self.gate.receipts));self.assertIsNone(self.gate.pending)
        self.assertFalse(self.gate.poisoned);self.assertEqual([],self.gate.held)
        with self.writer.lock.held():self.raw.namespace.guard_lease()
        self.assertIsNone(self.raw.namespace._write)

    def test_actual_opt_in_world_writer_uses_bounded_codec_on_same_original_owner(self):
        from adapters.pico4 import lifecycle_world_codec
        world=self.seams.world;gate=self.raw.install_writer(world,'world')
        before=len(world.state['frames'])
        with world.lock.held(),patch('adapters.pico4.lifecycle_world.pack',wraps=lifecycle_world_codec.pack) as encoder:
            world.current();self.raw.namespace.guard_lease()
        self.assertEqual(before+1,len(world.state['frames']));self.assertEqual(1,len(gate.receipts))
        self.assertEqual(dict(bounded=True),encoder.call_args.kwargs)
        self.assertEqual(world.state,lifecycle_world_codec.owner_payload(world.disk)[0])
        self.assertIsNone(self.raw.namespace._write);self.assertEqual([],gate.held)

    def test_equal_byte_old_root_replacement_fails_before_pack_and_retains_exact_new_state(self):
        path=self.writer.store.path;data=path.read_bytes();replacement=path.with_name('same-byte-old-root')
        replacement.write_bytes(data);replacement.chmod(0o600);os.replace(replacement,path)
        incoming=deepcopy(self.writer.state)
        with self.writer.lock.held(),patch('adapters.pico4.lifecycle_chat.pack') as encoder,\
                self.assertRaises(NativeUIError):self.writer.save(incoming)
        encoder.assert_not_called();self.assertEqual(data,path.read_bytes());self.assertTrue(self.gate.poisoned)
        self.assertIs(incoming,self.gate.held[-1].value)
        self.assertTrue(any(owner is self.gate for _path,owner in UNRESOLVED))

    def test_before_encoding_capacity_refusal_has_zero_pack_cas_and_exact_value_retained(self):
        incoming=deepcopy(self.writer.state);incoming['untrusted-extra']='\x00'*(3*1024*1024)
        before=(self.writer.store.path.read_bytes(),signature(self.writer.store.path.lstat()))
        with self.writer.lock.held(),patch('adapters.pico4.lifecycle_chat.pack') as encoder,\
                patch.object(self.writer.store,'write') as write,self.assertRaises(NativeUIError):self.writer.save(incoming)
        encoder.assert_not_called();write.assert_not_called();self.assertEqual(before,(self.writer.store.path.read_bytes(),signature(self.writer.store.path.lstat())))
        self.assertIs(incoming,self.gate.held[-1].value)

    def test_unknown_actual_replace_keeps_original_old_ofd_new_bytes_and_value_without_adoption(self):
        incoming=deepcopy(self.writer.state);write=self.writer.store.write
        def unknown(value,previous):write(value,previous);raise OSError('actual replace, unknown return')
        with self.writer.lock.held(),patch.object(self.writer.store,'write',side_effect=unknown),self.assertRaises(OSError):self.writer.save(incoming)
        self.assertTrue(self.gate.poisoned);permit=self.gate.held[-1]
        self.assertIs(incoming,permit.value);self.assertIsNotNone(permit.old);permit.old.require(permit.old.fd)
        self.assertEqual(0,os.fstat(permit.old.fd).st_nlink)
        with self.writer.lock.held(),self.assertRaises(NativeUIError):self.raw.namespace()
        self.assertFalse(self.gate.close_host())

    def test_write_permit_cannot_silently_authorize_a_second_original_writer(self):
        incoming=deepcopy(self.writer.state)
        world=self.seams.world;world_gate=self.raw.install_writer(world,'world')
        before=(world.store.path.read_bytes(),signature(world.store.path.lstat()))
        with self.writer.lock.held():
            permit=self.gate.before_state(self.writer,incoming)
            with patch('adapters.pico4.lifecycle_world.pack') as encoder,self.assertRaises(NativeUIError):
                world.save(deepcopy(world.state))
            encoder.assert_not_called()
        self.assertEqual(before,(world.store.path.read_bytes(),signature(world.store.path.lstat())))
        self.assertIs(incoming,permit.value);self.assertTrue(world_gate.poisoned)
        self.assertTrue(self.gate.held);self.assertFalse(self.gate.close_host())

    def test_terminal_other_gate_refuses_new_writer_before_pack_cas_and_keeps_new_value(self):
        world=self.seams.world;world_gate=self.raw.install_writer(world,'world')
        incoming=deepcopy(world.state);self.gate.failed(self.writer,None)
        before=(world.store.path.read_bytes(),signature(world.store.path.lstat()))
        with world.lock.held(),patch('adapters.pico4.lifecycle_world.pack') as encoder,\
                patch.object(world.store,'write') as write,self.assertRaises(NativeUIError):world.save(incoming)
        encoder.assert_not_called();write.assert_not_called()
        self.assertEqual(before,(world.store.path.read_bytes(),signature(world.store.path.lstat())))
        self.assertIs(incoming,world_gate.held[-1].value);self.assertTrue(world_gate.poisoned)
        self.assertFalse(world_gate.close_host())

    def test_open_one_use_permit_refuses_external_namespace_reentry(self):
        incoming=deepcopy(self.writer.state)
        with self.writer.lock.held():
            permit=self.gate.before_state(self.writer,incoming)
            with self.assertRaises(NativeUIError):self.raw.namespace()
            self.gate.failed(self.writer,permit)
        self.assertTrue(self.gate.poisoned);self.assertIs(incoming,self.gate.held[-1].value)


if __name__=='__main__':unittest.main()
