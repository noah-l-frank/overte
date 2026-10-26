"""Original interruption journals and ordinary OS dispatch; host models only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.self_tests.audio_background_domain import AudioBackgroundDomain,TICKET


class AudioBackgroundTests(unittest.TestCase):
    def setUp(self):self.b=AudioBackgroundDomain(self)

    def test_owned_start_original_os_cancellation_and_two_quiet_clocks_preserve_parent(self):
        b=self.b;before=(b.f.sessions,b.f.launches);result=b.owner.act(TICKET)
        self.assertTrue(result['historical']);self.assertTrue(result['parentBridgeRequired'])
        self.assertEqual(['mobile: backgroundApp','mobile: activateApp'],b.inputs)
        self.assertEqual(before,(b.f.sessions,b.f.launches));self.assertEqual(b.parent_bytes,b.store.path.read_bytes())
        self.assertEqual('observed',b.owner.state['phase']);self.assertEqual(3,len(b.owner.state['records']))
        self.assertTrue(b.owner.state['queries']);queries=deepcopy(b.owner.state['queries'])
        reads=b.reads;b.native_blocked=True;self.assertEqual(result,b.reopen().act(TICKET));self.assertEqual(reads,b.reads)
        self.assertEqual(queries,b.owner.state['queries'])
        self.assertEqual(1,b.m.actions.count('audio.record'))

    def test_lost_home_reconstructs_in_background_without_native_or_second_home(self):
        b=self.b;b.fault='lost-home'
        with self.assertRaises(OSError):b.owner.act(TICKET)
        self.assertFalse(b.f.process['foreground']);reads=b.reads;b.native_blocked=True;b.reopen();self.assertEqual(reads,b.reads)
        b.native_blocked=False;b.fault=None;b.owner.act(TICKET);self.assertEqual(2,len(b.inputs))

    def test_lost_activation_uses_existing_foreground_without_another_activation(self):
        b=self.b;b.fault='lost-activation'
        with self.assertRaises(OSError):b.owner.act(TICKET)
        b.fault=None;b.reopen().act(TICKET);self.assertEqual(2,len(b.inputs))

    def test_ignored_home_never_activates_or_resends_and_preserves_recording(self):
        b=self.b;b.fault='ignored-home'
        with self.assertRaises(NativeUIError):b.owner.act(TICKET)
        with self.assertRaises(NativeUIError):b.reopen().act(TICKET)
        self.assertEqual(['mobile: backgroundApp'],b.inputs);self.assertTrue(b.m.active)

    def test_ignored_activation_never_reads_background_native_or_resends(self):
        b=self.b;b.fault='ignored-activation'
        with self.assertRaises(NativeUIError):b.owner.act(TICKET)
        reads=b.reads;b.native_blocked=True
        with self.assertRaises(NativeUIError):b.reopen().act(TICKET)
        self.assertEqual(reads,b.reads);self.assertEqual(2,len(b.inputs))

    def test_ack_without_native_lifecycle_counters_does_not_qualify(self):
        b=self.b;b.fault='native-counters'
        with self.assertRaises(NativeUIError):b.owner.act(TICKET)
        self.assertEqual('foreground-issued',b.owner.state['phase']);self.assertEqual(1,len(b.owner.state['records']))

    def test_wrong_cancel_reason_is_not_background_recovery(self):
        b=self.b;b.fault='wrong-error'
        with self.assertRaises(NativeUIError):b.owner.act(TICKET)
        self.assertEqual(1,len(b.owner.state['records']));self.assertEqual(2,len(b.inputs))

    def test_retained_capture_is_not_background_cancellation(self):
        b=self.b;b.fault='capture-retained'
        with self.assertRaises(NativeUIError):b.owner.act(TICKET)
        self.assertTrue(b.m.active);self.assertEqual(1,len(b.owner.state['records']))

    def test_process_replacement_prevents_background_recovery_without_new_native(self):
        b=self.b;b.fault='lost-home'
        with self.assertRaises(OSError):b.owner.act(TICKET)
        reads=b.reads;b.f.process['pid']=43
        with self.assertRaises((ValueError,NativeUIError)):b.reopen()
        self.assertEqual(reads,b.reads);self.assertEqual(['mobile: backgroundApp'],b.inputs)

    def test_same_pid_with_new_native_launch_is_not_same_process_resume(self):
        b=self.b;b.fault='restart'
        with self.assertRaises(NativeUIError):b.owner.act(TICKET)
        self.assertEqual(1,len(b.owner.state['records']));self.assertEqual(2,len(b.inputs))

    def test_new_foreign_recording_cycle_cannot_borrow_the_owned_start(self):
        b=self.b;m=b.m
        from self_tests.test_recorded_preview_history import voice,event
        m.tick();m.cycle+=1;m.recorded=voice([event(m.recorded['events'][-1]['eventSequence']+1,'capturing',96000,epoch=m.native_epoch())],
            cycle=m.cycle,started=m.native_epoch())
        with self.assertRaises(NativeUIError):b.owner.act(TICKET)
        self.assertEqual([],b.inputs);self.assertTrue(m.active)

    def test_saved_before_cut_cannot_authorize_home_after_its_fresh_window_expires(self):
        b=self.b;write=OriginalFrameStore.write
        def lost(store,index,value):
            result=write(store,index,value)
            if store.namespace=='ios-audio-background' and index==1:raise OSError('Declared loss after saved before cut')
            return result
        with patch.object(OriginalFrameStore,'write',lost):
            with self.assertRaises(OSError):b.owner.act(TICKET)
        b.m.sleep(2)
        with self.assertRaises(NativeUIError):b.reopen().act(TICKET)
        self.assertEqual([],b.inputs);self.assertTrue(b.m.active)

    def test_changed_parent_cannot_be_adopted_as_the_original_owned_start(self):
        b=self.b;b.fault='lost-home'
        with self.assertRaises(OSError):b.owner.act(TICKET)
        old=b.store.read();changed=dict(old,runId='b'*32);b.store.write(changed,old);reads=b.reads
        with self.assertRaises((ValueError,NativeUIError)):b.reopen()
        self.assertEqual(reads,b.reads);self.assertEqual(['mobile: backgroundApp'],b.inputs)

    def test_saved_post_resume_original_recovers_same_bytes_inode_without_new_cut(self):
        b=self.b;write=OriginalFrameStore.write;saved={}
        def lost(store,index,value):
            result=write(store,index,value)
            if store.namespace=='ios-audio-background' and index==3:
                path=store.path(store.expand(result));saved.update(path=path,body=path.read_bytes(),inode=path.stat().st_ino)
                raise OSError('Declared loss after immutable original saved')
            return result
        with patch.object(OriginalFrameStore,'write',lost):
            with self.assertRaises(OSError):b.owner.act(TICKET)
        reads=b.reads;b.native_blocked=True;b.reopen().act(TICKET)
        self.assertEqual(reads,b.reads);self.assertEqual(saved['body'],saved['path'].read_bytes())
        self.assertEqual(saved['inode'],saved['path'].stat().st_ino);self.assertEqual(2,len(b.inputs))

    def test_failed_durable_intent_prevents_first_home(self):
        b=self.b
        with patch.object(b.owner.store,'write',side_effect=OSError('Declared failed CAS')):
            with self.assertRaises(OSError):b.owner.act(TICKET)
        self.assertEqual([],b.inputs);self.assertTrue(b.m.active)

    def test_original_os_and_parent_membership_cannot_be_replaced_in_archive(self):
        b=self.b;b.owner.act(TICKET);value=deepcopy(b.owner.previous)
        from adapters.script_feature.history import pack,unpack
        for mutate in (lambda v:v['background'].update(appState=4),lambda v:v['startedBy'].update(sha256='f'*64),
            lambda v:v['foreground']['source'].update(instance='e'*32)):
            state=unpack(value['payload'])[0];mutate(state);bad=dict(value,payload=pack([state]))
            with self.assertRaises((ValueError,NativeUIError)):b.owner.decode(bad)
