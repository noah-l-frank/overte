"""Owned process lifecycle against synthetic workers, never a real mixer/domain."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture.messages_mixer import MessagesMixer,start_identity
from fixture.owned_processes import OwnedProcesses

WORKER="import sys;print('synthetic-ready',flush=True);sys.stdin.readline()"


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux owned mixer fixture')
class MessagesMixerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.env=os.environ.copy();self.env['XDG_CONFIG_HOME']=self.temp.name;self.owner=OwnedProcesses(self.env)
        self.processes=[];self.addCleanup(self.stop);self.store=PrivateFeatureState(Path(self.temp.name)/'intent.json')
        self.intent=None;self.enabled=True
        self.mixer=MessagesMixer(self.spawn(),lambda pid:self.enabled and self.owner.matches(pid),self.spawn,self.write,self.clear,self.store.read)
    def spawn(self,kind='4'):
        process=subprocess.Popen([sys.executable,'-c',WORKER,'-t',kind],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,text=True,env=self.env)
        self.processes.append(process);self.assertEqual('synthetic-ready',process.stdout.readline().strip());return process
    def stop(self):
        for process in self.processes:
            if process.poll() is None:process.terminate()
            process.wait(timeout=3)
            for stream in (process.stdin,process.stdout,process.stderr):stream.close()
    def write(self,value):
        self.intent=value;self.store.write(value,None)
    def clear(self):
        actual=self.store.read()
        if actual is not None:self.store.discard(self.intent)
        self.intent=None

    def test_only_original_mixer_stops_other_owned_processes_survive_and_restart_is_fresh(self):
        peers=[self.spawn(kind) for kind in ('0','1','2','3','5','6')];original=self.mixer.process
        self.assertEqual(dict(mixerProcessVersion=1,running=True,generation=1,pending=False),self.mixer.state())
        offline=self.mixer.transition('offline');self.assertFalse(offline['running']);self.assertFalse(offline['pending'])
        self.assertIsNotNone(original.poll());self.assertTrue(all(p.poll() is None for p in peers));self.assertIsNone(self.store.read())
        self.assertEqual(offline,self.mixer.transition('offline'))
        online=self.mixer.transition('online');self.assertTrue(online['running']);self.assertGreater(online['generation'],offline['generation'])
        self.assertNotEqual(original.pid,self.mixer.process.pid);self.assertTrue(all(p.poll() is None for p in peers))
        self.assertEqual(online,self.mixer.transition('online'));self.assertIsNone(self.store.read())

    def test_wrong_assignment_type_owner_or_start_identity_cannot_be_signalled(self):
        other=self.spawn('1')
        with self.assertRaises(NativeUIError):MessagesMixer(other,self.owner.matches,self.spawn,self.write,self.clear,self.store.read)
        self.enabled=False
        with self.assertRaises(NativeUIError):self.mixer.transition('offline')
        self.enabled=True;self.mixer.start='0'
        with self.assertRaises(NativeUIError):self.mixer.transition('offline')
        self.assertIsNone(self.mixer.process.poll());self.assertIsNone(other.poll());self.assertIsNone(self.store.read())

    def test_failed_intent_prevents_signal_and_healthy_baseline_can_cancel_undispatched_intent(self):
        original=self.mixer.write_intent
        def fail(_):raise OSError('private intent unavailable')
        self.mixer.write_intent=fail
        with self.assertRaises(OSError):self.mixer.transition('offline')
        self.assertIsNone(self.mixer.process.poll());self.assertTrue(self.mixer.state()['pending']);self.assertFalse(self.mixer.dispatched)
        self.mixer.write_intent=original;self.assertFalse(self.mixer.transition('online')['pending']);self.assertIsNone(self.store.read())

    def test_ignored_signals_are_not_offline_and_keep_original_intent(self):
        with patch('fixture.messages_mixer.signal.pidfd_send_signal',return_value=None):
            with self.assertRaises(NativeUIError):self.mixer.transition('offline')
        self.assertIsNone(self.mixer.process.poll());self.assertTrue(self.mixer.state()['running']);self.assertTrue(self.mixer.state()['pending'])
        self.assertIsNotNone(self.store.read())
        with self.assertRaises(RuntimeError):self.mixer.transition('online')

    def test_failed_clear_is_incomplete_cleanup_until_actual_state_is_rechecked_and_journal_removed(self):
        original=self.mixer.clear_intent
        def fail():raise OSError('journal removal unavailable')
        self.mixer.clear_intent=fail
        with self.assertRaises(OSError):self.mixer.transition('offline')
        self.assertFalse(self.mixer.state()['running']);self.assertTrue(self.mixer.state()['pending']);self.assertIsNotNone(self.store.read())
        self.mixer.clear_intent=original;self.assertFalse(self.mixer.transition('offline')['pending']);self.assertIsNone(self.store.read())
        self.assertTrue(self.mixer.transition('online')['running'])

    def test_unexpected_process_exit_cannot_be_an_intentional_outage_receipt(self):
        original=self.mixer.process;original.terminate();original.wait(timeout=3)
        with self.assertRaises(NativeUIError):self.mixer.state()
        with self.assertRaises(NativeUIError):self.mixer.transition('online')
        self.assertIsNone(self.store.read())

    def test_failed_start_retains_intent_and_does_not_report_running(self):
        self.mixer.transition('offline')
        def fail():raise OSError('fixture startup unavailable')
        self.mixer.spawn=fail
        with self.assertRaises(OSError):self.mixer.transition('online')
        self.assertFalse(self.mixer.state()['running']);self.assertTrue(self.mixer.state()['pending']);self.assertIsNotNone(self.store.read())
        with self.assertRaises(RuntimeError):self.mixer.transition('offline')

    def test_transient_exec_read_is_retried_with_the_same_pinned_child_start(self):
        calls=0
        def owned(pid):
            nonlocal calls
            calls+=1
            return calls>2 and self.owner.matches(pid)
        self.mixer.owned=owned
        self.assertTrue(self.mixer.state()['running']);self.assertGreaterEqual(calls,3)

    def test_foreign_pending_journal_prevents_cleanup_ack_and_is_not_removed(self):
        original=self.mixer.clear_intent
        def foreign():
            value=self.store.read();self.store.write(value|{'action':'foreign'},value);original()
        self.mixer.clear_intent=foreign
        with self.assertRaises(NativeUIError):self.mixer.transition('offline')
        with self.assertRaises(NativeUIError):self.mixer.state()
        self.assertEqual('foreign',self.store.read()['action'])
        self.store.write(self.intent,self.store.read());self.mixer.clear_intent=original
        self.assertFalse(self.mixer.transition('offline')['pending']);self.assertIsNone(self.store.read())

    def test_uncertain_intent_write_can_restore_unchanged_baseline_without_process_input(self):
        original=self.mixer.write_intent;pid=self.mixer.process.pid
        def fail_after_write(value):original(value);raise OSError('write acknowledgement lost')
        self.mixer.write_intent=fail_after_write
        with self.assertRaises(OSError):self.mixer.transition('offline')
        self.assertIsNotNone(self.store.read());self.assertFalse(self.mixer.dispatched)
        self.assertTrue(self.mixer.transition('online')['running']);self.assertEqual(pid,self.mixer.process.pid)
        self.assertIsNone(self.store.read());self.assertEqual(1,len(self.processes))

    def test_offline_bookkeeping_cannot_hide_an_actual_original_live_process(self):
        self.mixer.transition('offline');other=self.spawn('4')
        self.mixer.last_stopped=(other.pid,start_identity(other.pid))
        with self.assertRaises(NativeUIError):self.mixer.state()
        self.assertIsNone(other.poll())

    def test_ignored_persistence_ack_never_allows_a_process_signal(self):
        self.mixer.write_intent=lambda _:None
        with self.assertRaises(NativeUIError):self.mixer.transition('offline')
        self.assertIsNone(self.mixer.process.poll());self.assertFalse(self.mixer.dispatched)
        self.assertTrue(self.mixer.state()['pending']);self.assertIsNone(self.store.read())

    def test_ignored_journal_removal_is_pending_until_independent_file_absence(self):
        original=self.mixer.clear_intent;self.mixer.clear_intent=lambda:None
        with self.assertRaises(NativeUIError):self.mixer.transition('offline')
        self.assertTrue(self.mixer.state()['pending']);self.assertIsNotNone(self.store.read())
        self.mixer.clear_intent=original
        self.assertFalse(self.mixer.transition('offline')['pending']);self.assertIsNone(self.store.read())

    def test_closed_actions_refuse_expected_nodes_or_whole_stack_requests(self):
        for value in ('restart-domain','remove-peer',None,{'running':False}):
            with self.assertRaises((NativeUIError,TypeError)):self.mixer.transition(value)
        self.assertIsNone(self.mixer.process.poll());self.assertIsNone(self.store.read())


if __name__=='__main__':unittest.main()
