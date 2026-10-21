"""Real original quiet-window logic with explicit synthetic native work only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.native_script_work import NativeScriptWork
from adapters.normal_ui import NativeUIError
from overte_phone_emote_lifetime import PhoneEmoteLifetime
from test_emote_effects import EffectsModel
from test_emote_sources import RUN


class Model(EffectsModel):
    def __init__(self,root):
        super().__init__(root);self.widgets.tablet=False;self.work_sequence=0;self.work_value=None
        self.work_fault=None;self.work_commands=[];self.busy=0;self.clear_after=None;self.freeze_monotonic=False
    def sleep(self,seconds):
        if not self.freeze_monotonic:super().sleep(seconds)
        self.epoch+=round(seconds*1000);self.roots.epoch=self.epoch
    def _script_work(self,_selector,*,read_only):
        assert read_only
        return NativeScriptWork(self.work_send,lambda:json.dumps(self.work_value) if self.work_value else '',
            lambda:self.epoch,lambda:self.okay,31,monotonic=lambda:self.clock,sleep=self.sleep)
    def work_send(self,request):
        self.work_commands.append(deepcopy(request));self.work_sequence+=1
        caller=self.caller('override',self.epoch);manager=caller['manager'];code=caller['code']
        work=dict(scriptWorkVersion=1,requestId=request['commandId'],sequence=self.work_sequence,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,signalCallbacks=0,timerCallbacks=0,evaluating=False,timers=[])
        if self.clear_after is None or self.work_sequence<=self.clear_after:
            if self.busy==1:work['timers']=[dict(handle=1,active=True,singleShot=True,intervalMs=2000,remainingMs=100)]
            elif self.busy==2:work['timers']=[dict(handle=1,active=False,singleShot=True,intervalMs=2000,remainingMs=-1)]
            elif self.busy==3:work['signalCallbacks']=1
            elif self.busy==4:work['timerCallbacks']=1
            elif self.busy==5:work['evaluating']=True
        source=dict(complete=True,revision=1,manager=deepcopy(manager),code=deepcopy(code),work=work,
            workers=[dict(membership=deepcopy(manager),running=True,stopping=False,finished=False,done=False)])
        value=dict(schemaVersion=1,requestId=request['commandId'],instance='a'*32,sequence=self.work_sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=source)
        if self.work_fault=='foreign':
            source['manager']['instance']='8'*32;source['workers'][0]['membership']['instance']='8'*32
        elif self.work_fault=='code':source['code']['sha256']='f'*64
        elif self.work_fault=='birth':value['instance']='8'*32
        elif self.work_fault=='old':work['capturedEpochMs']-=1600;value['requestedEpochMs']-=1600;work['requestedEpochMs']-=1600
        elif self.work_fault=='frozen-sequence':value['sequence']=work['sequence']=1
        elif self.work_fault=='membership':source['revision']=2
        elif self.work_fault=='lost':raise NativeUIError('Synthetic lost selected worker read')
        elif self.work_fault=='guard':self.okay=False
        self.work_value=value


class PhoneEmoteLifetimeTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-lifetime-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name))
    def owner(self,role='primary'):
        m=self.model;m.call('cleanup');return PhoneEmoteLifetime(m.source(role))

    def test_actual_empty_work_idle_rig_and_closed_ui_require_a_three_second_dual_clock_window(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();window=owner.wait(sleep=m.sleep)
            self.assertGreaterEqual(window['elapsedMs'],3000);self.assertGreaterEqual(window['last']-window['first'],2)
            self.assertEqual('complete',owner.state['phase']);self.assertGreaterEqual(len(owner.state['records']),3)
            self.assertLess(owner.store.path.stat().st_size,65536)
            self.assertEqual([],m.controls.input_requests)
            self.assertTrue(all(set(command)=={'schemaVersion','commandId','action','managerInstance'} for command in m.work_commands))
            current=PhoneEmoteLifetime(m.source());current.retire();self.assertIsNone(current.store.read())
            self.assertIsNotNone(owner.source.store.read())

    def test_busy_timer_then_actual_release_starts_a_new_complete_window_after_the_busy_original(self):
        m=self.model;m.busy=1;m.clear_after=2
        with m.lock.held():
            owner=self.owner();window=owner.wait(sleep=m.sleep)
            self.assertEqual(3,window['first']);self.assertEqual(1,len(owner.state['records'][0]['work']['source']['work']['timers']))
            self.assertFalse(owner.quiet(owner.state['records'][0]))

    def test_inactive_retained_timer_is_not_an_empty_callback_inventory(self):
        m=self.model;m.busy=2
        with m.lock.held():
            owner=self.owner();owner.read()
            self.assertFalse(owner.quiet(owner.state['records'][0]));self.assertIsNone(owner.state['window'])
            self.assertEqual(-1,owner.state['records'][0]['work']['source']['work']['timers'][0]['remainingMs'])

    def test_actual_active_signal_timer_callback_or_engine_evaluation_cannot_qualify(self):
        m=self.model
        with m.lock.held():
            owner=self.owner()
            for busy in (3,4,5):
                m.busy=busy;owner.read();self.assertFalse(owner.quiet(owner.state['records'][-1]))
                self.assertNotEqual('complete',owner.state['phase'])

    def test_ignored_cleanup_with_a_retained_timer_never_finishes_or_deletes_ownership(self):
        m=self.model;m.busy=1
        with m.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.wait(sleep=m.sleep)
            self.assertIsNotNone(owner.store.read());self.assertEqual(32,len(owner.state['records']))
            with self.assertRaises(NativeUIError):owner.retire()
        self.assertEqual([],m.controls.input_requests)

    def test_open_chooser_or_tablet_cannot_become_quiet_from_empty_work(self):
        m=self.model;m.widgets.tablet=True;m.widgets.page=True
        with m.lock.held():
            owner=self.owner();owner.read();self.assertFalse(owner.quiet(owner.state['records'][0]))

    def test_new_call_during_the_window_restarts_the_stable_native_call_barrier(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.read();m.sleep(1.5);owner.read()
            m.start('Waving');m.restore();m.sleep(1.5);owner.read()
            self.assertIsNone(owner.state['window']);owner.wait(sleep=m.sleep)
            self.assertEqual(3,owner.state['window']['first'])

    def test_old_foreign_or_wrong_code_work_cannot_borrow_current_source_roots(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();m.work_fault='code'
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual('reading',owner.state['phase']);self.assertIsNotNone(owner.store.read())

    def test_native_birth_or_registry_revision_mismatch_is_not_a_complete_snapshot(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();m.work_fault='membership'
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual('reading',owner.state['phase'])

    def test_reused_selected_worker_cursors_cannot_extend_the_window(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.read();m.work_fault='frozen-sequence'
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual(1,len(owner.state['records']))

    def test_missing_work_result_preserves_pending_scope_and_cannot_restart_as_empty(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();m.work_fault='lost'
            with self.assertRaises(NativeUIError):owner.read()
            current=PhoneEmoteLifetime(m.source());before=len(m.work_commands)
            with self.assertRaises(NativeUIError):current.read()
            self.assertEqual(before,len(m.work_commands));self.assertEqual('reading',current.state['phase'])

    def test_both_roles_have_separate_original_source_and_work_histories(self):
        m=self.model
        with m.lock.held():
            left=self.owner();left.read();right=PhoneEmoteLifetime(m.source('actor'));right.read()
            self.assertNotEqual(left.store.path,right.store.path)
            self.assertNotEqual(left.state['records'][0]['work']['requestId'],right.state['records'][0]['work']['requestId'])
            self.assertGreater(right.state['records'][0]['work']['sequence'],left.state['records'][0]['work']['sequence'])

    def test_foreign_phase_cannot_be_a_cleanup_window(self):
        m=self.model
        with m.lock.held():
            m.call('open');owner=PhoneEmoteLifetime(m.source())
            with self.assertRaises(NativeUIError):owner.read()
            self.assertIsNotNone(owner.store.read())

    def test_missing_historical_source_original_is_not_hidden_by_window_metadata(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.read();entries=owner.originals.manifest(owner.source.state['manifests'][0])
            owner.originals.path(owner.originals.expand(entries[0])).unlink()
            with self.assertRaises((NativeUIError,OSError)):PhoneEmoteLifetime(owner.source)

    def test_unknown_actual_worker_cannot_echo_the_requested_manager_as_an_empty_inventory(self):
        m=self.model;m.work_fault='foreign'
        with m.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual('reading',owner.state['phase']);self.assertEqual([],owner.state['records'])

    def test_foreign_native_birth_cannot_borrow_the_same_process_id(self):
        m=self.model;m.work_fault='birth'
        with m.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual('reading',owner.state['phase'])

    def test_old_worker_capture_cannot_extend_a_fresh_source_envelope(self):
        m=self.model;m.work_fault='old'
        with m.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual([],owner.state['records'])

    def test_advancing_native_time_with_frozen_host_monotonic_clock_cannot_finish(self):
        m=self.model;m.freeze_monotonic=True
        with m.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.wait(sleep=m.sleep)
            records=owner.state['records'];self.assertEqual(32,len(records));self.assertIsNone(owner.state['window'])
            self.assertGreater(records[-1]['epochMs']-records[0]['epochMs'],3000)
            self.assertEqual(records[-1]['monotonicMs'],records[0]['monotonicMs'])

    def test_delayed_final_journal_work_with_frozen_external_epoch_cannot_publish_fresh(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();save=owner.save
            def delayed():save();m.clock+=2
            owner.save=delayed
            with self.assertRaises(NativeUIError):owner.read()
            self.assertIsNotNone(owner.store.read());self.assertNotEqual('complete',owner.state['phase'])

    def test_unpersisted_complete_window_or_source_metadata_is_not_adopted(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.read();original=deepcopy(owner.state)
            owner.state['phase']='complete';owner.state['window']=dict(first=1,last=1,elapsedMs=3000)
            with self.assertRaises(NativeUIError):owner.read()
            owner.state=original;owner.source.state['revision']-=1
            with self.assertRaises(NativeUIError):owner.read()

    def test_failed_result_commit_keeps_pending_scope_and_blocks_same_object_and_reconstructed_success(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();writer=owner.store.write
            from overte_phone_script_history import unpack
            def lost(value,previous):
                if unpack(value['payload'])[0]['records']:raise OSError('Synthetic interrupted original work commit')
                return writer(value,previous)
            owner.store.write=lost
            with self.assertRaises((NativeUIError,OSError)):owner.read()
            before=len(m.work_commands)
            with self.assertRaises(NativeUIError):owner.read()
            current=PhoneEmoteLifetime(m.source())
            with self.assertRaises(NativeUIError):current.read()
            self.assertEqual(before,len(m.work_commands));self.assertEqual('reading',current.state['phase'])

    def test_retirement_rechecks_actual_work_instead_of_using_a_previous_green_window(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.wait(sleep=m.sleep);m.busy=3
            with self.assertRaises(NativeUIError):owner.retire()
            self.assertIsNotNone(owner.store.read());self.assertEqual('ready',owner.state['phase'])


if __name__=='__main__':unittest.main()
