"""Background4 real original creation/CAS joined to existing normal owners.

Product Qt/SDK remain explicit models; filesystem/OFD/CAS calls are actual.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from unittest.mock import patch
import unittest

from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
from adapters.pico4.lifecycle_background_raw import LifecycleBackgroundHistory
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
from self_tests.test_pico_lifecycle_background_owner import LifecycleBackgroundOwnerTests
from self_tests.test_pico_lifecycle_chat import LifecycleChatTests
from self_tests.test_pico_lifecycle_source import RUN

RETAINED_FOREIGN_FDS=[]


class LifecycleFamilyGateTests(unittest.TestCase):
    def setUp(self):
        fixture=LifecycleChatTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.owner.open_chat();fixture.owner.focus_chat();fixture.owner.type_chat()
        seams=LifecycleBackgroundOwnerTests();self.seams=seams
        def make():
            self.namespace=LifecycleNamespaceBill(seams.root,seams.lock,mutex_layout=2,
                expanded=lambda:None if getattr(seams,'owner',None) is None else seams.owner.state)
            self.addCleanup(self.namespace.close)
            self.bank=LifecycleSourceRaw4(seams.root/'lifecycle-background-raw.json',RUN,seams.chat.binding,
                seams.lock,seams.lock.assert_held,self.namespace,lambda:seams.native.clock)
            self.addCleanup(self.bank.close_host)
            return PicoLifecycleBackground(seams.root/'lifecycle-background-owner.json',RUN,seams.chat.binding,
                seams.lock,seams.status,seams.os_input,seams.runtime,monotonic=lambda:seams.native.clock,
                sleep=seams.sleep,raw_layout=self.bank)
        seams.make=make;seams.initialize_from_chat(fixture)

    def test_existing_normal_prepare_commits_first_background4_root_then_same_phase_cas_and_only_its_manifest(self):
        seams=self.seams;seams.owner.prepare(seams.chat)
        gate=self.bank.write_gates['background'];view=self.bank.view('background')
        self.assertEqual('prepared',seams.owner.state['phase']);self.assertEqual([],seams.inputs)
        self.assertEqual(4,seams.owner.disk['lifecycleBackgroundOwnerVersion'])
        self.assertEqual(view.manifest,seams.owner.disk['originalChunks']);self.assertTrue(view.confirmed)
        self.assertEqual([],self.bank.view('pending').manifest);self.assertIsNone(view.pending)
        self.assertEqual(1,len(gate.receipts));self.assertIsNone(gate.receipts[0][1])
        before=tuple(gate.receipts[0][2]);sources=self.bank.archive.state['reads']
        with seams.lock.held():
            seams.owner.save(deepcopy(seams.owner.state));seams.owner.load()
            self.namespace.guard_lease()
        self.assertEqual(sources,self.bank.archive.state['reads']);self.assertEqual(2,len(gate.receipts))
        self.assertEqual(before,gate.receipts[1][1]);self.assertNotEqual(before[:2],gate.receipts[1][2][:2])
        self.assertEqual(view.manifest,seams.owner.disk['originalChunks']);self.assertIsNone(self.namespace._write)
        self.assertIsNone(self.bank.active_family);self.assertEqual([],gate.held)
        from adapters.chat_journey.archive_file import signature
        before_files={path.name:(path.read_bytes(),signature(path.lstat())) for path in seams.root.iterdir()}
        calls=len(seams.history.commands);history=LifecycleBackgroundHistory(seams.owner.store.path);self.addCleanup(history.close)
        self.assertEqual(seams.owner.state,history.read());self.assertEqual(4,history.version)
        self.assertFalse(history.originals.report()['ownerCASAcknowledgementKnown'])
        self.assertEqual(before_files,{path.name:(path.read_bytes(),signature(path.lstat())) for path in seams.root.iterdir()})
        self.assertEqual(calls,len(seams.history.commands));self.assertEqual([],seams.inputs)

    def test_first_root_capacity_refuses_before_projection_or_codec_and_holds_exact_acquired_state(self):
        seams=self.seams
        from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
        original=LifecycleFamilyGate4.before
        def refuse(gate,value):
            with patch.object(gate.namespace,'begin_write',side_effect=NativeUIError('actual original capacity refusal')):
                return original(gate,value)
        with patch.object(LifecycleFamilyGate4,'before',refuse),self.assertRaises(NativeUIError):seams.owner.prepare(seams.chat)
        gate=self.bank.write_gates['background'];self.assertEqual(1,len(gate.held))
        self.assertIsNone(gate.held[0].projection);self.assertEqual('prepared',gate.held[0].value['phase'])
        self.assertFalse(seams.owner.store.path.exists());self.assertEqual((),self.bank.view('background').confirmed)
        self.assertEqual([],seams.inputs);self.assertFalse(self.bank.close_host())

    def test_unknown_actual_root_cas_retains_old_confirmed_manifest_and_blocks_all_next_io(self):
        seams=self.seams;seams.owner.prepare(seams.chat);view=self.bank.view('background')
        confirmed=view.confirmed;old=deepcopy(seams.owner.disk);write=seams.owner.store.write
        def uncertain(value,previous):write(value,previous);raise OSError('actual CAS happened; acknowledgment lost')
        with seams.lock.held(),patch.object(seams.owner.store,'write',side_effect=uncertain),self.assertRaises(OSError):
            seams.owner.save(deepcopy(seams.owner.state))
        self.assertIs(confirmed,view.confirmed);self.assertEqual(old,seams.owner.disk)
        self.assertIsNotNone(view.pending);self.assertTrue(self.bank.failed)
        self.assertFalse(self.bank.close_host());self.assertEqual([],seams.inputs)

    def test_whole_bill_failure_after_actual_cas_cannot_confirm_or_drop_projection(self):
        seams=self.seams;seams.owner.prepare(seams.chat);view=self.bank.view('background');confirmed=view.confirmed
        with (seams.lock.held(),patch.object(self.namespace,'finish_write',side_effect=NativeUIError('actual post-CAS full bill refusal')),
                self.assertRaises(NativeUIError)):seams.owner.save(deepcopy(seams.owner.state))
        self.assertIs(confirmed,view.confirmed);self.assertIsNotNone(view.pending)
        self.assertTrue(self.bank.failed);self.assertFalse(self.bank.close_host())

    def test_foreign_same_byte_root_or_plausible_child_cannot_gain_writer_admission(self):
        seams=self.seams;seams.owner.prepare(seams.chat);view=self.bank.view('background');confirmed=view.confirmed
        path=seams.owner.store.path;replacement=path.with_name('foreign-root')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        before=len(seams.history.commands)
        with seams.lock.held(),self.assertRaises(NativeUIError):seams.owner.save(deepcopy(seams.owner.state))
        self.assertIs(confirmed,view.confirmed);self.assertEqual(before,len(seams.history.commands))

    def test_default_background_owner_does_not_promote_or_reopen_raw4_without_explicit_selection(self):
        seams=self.seams;before={path.name:path.read_bytes() for path in seams.root.iterdir()}
        with self.assertRaises(NativeUIError):PicoLifecycleBackground(seams.root/'lifecycle-background-owner.json',RUN,seams.chat.binding,
            seams.lock,seams.status,seams.os_input,seams.runtime,monotonic=lambda:seams.native.clock,sleep=seams.sleep)
        self.assertEqual(before,{path.name:path.read_bytes() for path in seams.root.iterdir()})
        self.assertEqual([],seams.runtime_calls);self.assertEqual([],seams.inputs)

    def test_another_live4_owner_cannot_adopt_existing_root_even_with_the_same_original_warm_bank(self):
        seams=self.seams;seams.owner.prepare(seams.chat)
        before={path.name:path.read_bytes() for path in seams.root.iterdir()};calls=len(seams.history.commands)
        with self.assertRaises(NativeUIError):PicoLifecycleBackground(seams.owner.store.path,RUN,seams.chat.binding,
            seams.lock,seams.status,seams.os_input,seams.runtime,monotonic=lambda:seams.native.clock,
            sleep=seams.sleep,raw_layout=self.bank)
        self.assertEqual(before,{path.name:path.read_bytes() for path in seams.root.iterdir()})
        self.assertEqual(calls,len(seams.history.commands));self.assertEqual([],seams.inputs)

    def test_passive_background4_cached_decoded_value_cannot_change_same_size_original_facts(self):
        seams=self.seams;seams.owner.prepare(seams.chat)
        history=LifecycleBackgroundHistory(seams.owner.store.path);self.addCleanup(history.close)
        history.value[0]['phase']='released'
        with self.assertRaises(NativeUIError):history.read()
        self.assertEqual('prepared',seams.owner.state['phase']);self.assertEqual([],seams.inputs)

    def test_partial_first_root_write_retains_creation_ofd_value_and_no_confirmed_manifest(self):
        seams=self.seams;write=os.pwrite;attempts=[]
        def partial(fd,data,offset):
            if os.readlink('/proc/self/fd/'+str(fd))==str(seams.owner.store.path):
                attempts.append(fd);write(fd,data[:7],offset);raise OSError('actual partial original root write')
            return write(fd,data,offset)
        with patch('adapters.pico4.lifecycle_family_gate.os.pwrite',side_effect=partial),self.assertRaises(NativeUIError):
            seams.owner.prepare(seams.chat)
        gate=self.bank.write_gates['background'];permit=gate.held[0]
        self.assertEqual(1,len(attempts));self.assertEqual(7,seams.owner.store.path.stat().st_size)
        self.assertIsNotNone(permit.created);self.assertEqual('prepared',permit.value['phase'])
        self.assertEqual((),self.bank.view('background').confirmed);self.assertFalse(self.bank.close_host())
        self.assertEqual([],seams.inputs)

    def test_real_recycled_same_inode_creation_fd_is_not_closed_or_written_through_foreign_description(self):
        seams=self.seams;write=os.pwrite;foreign=[]
        def recycled(fd,data,offset):
            if os.readlink('/proc/self/fd/'+str(fd))==str(seams.owner.store.path):
                os.close(fd);replacement=os.open(seams.owner.store.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                if replacement!=fd:os.dup2(replacement,fd);os.close(replacement)
                foreign.append((fd,os.fstat(fd)));RETAINED_FOREIGN_FDS.append(fd)
                return len(data)
            return write(fd,data,offset)
        with patch('adapters.pico4.lifecycle_family_gate.os.pwrite',side_effect=recycled),self.assertRaises(NativeUIError):
            seams.owner.prepare(seams.chat)
        self.assertEqual(1,len(foreign));fd,before=foreign[0]
        self.assertEqual(0,seams.owner.store.path.stat().st_size);self.assertFalse(self.bank.close_host())
        self.assertEqual(before,os.fstat(fd));self.assertEqual(b'',os.pread(fd,1,0))
        self.assertEqual((),self.bank.view('background').confirmed)
