"""Original Pico cleanup work owner with synthetic VM/Rig/Qt sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.native_script_work import NativeScriptWork
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_lifetime import PicoEmoteLifetime
from self_tests.test_pico_emote_effects import EffectsBoundary
from self_tests.test_pico_emote_sources import RUN
from self_tests.test_native_script_work import activity


class LifetimeBoundary(EffectsBoundary):
    def __init__(self):
        super().__init__();self.s.widget.tablet=False;self.work_sequence=0;self.work_value=None
        self.work_commands=[];self.work_factories=0;self.work_fault=None;self.busy=None;self.clear_after=0
        self.signal_calls=1;self.timer_calls=1;self.registrations=1
        self.s.journal.activate(RUN,'f'*32,'cleanup')
    def sleep(self,seconds):self.tick(round(seconds*1000))
    def reader(self):
        self.work_factories+=1
        return NativeScriptWork(self.work_send,lambda:json.dumps(self.work_value),lambda:self.s.epoch,
            self.s.guard,31,monotonic=lambda:self.s.clock,sleep=self.sleep)
    def work_send(self,request):
        self.work_commands.append(deepcopy(request));self.work_sequence+=1
        engine=self.s.code['source']['engines'][0];manager=deepcopy(self.s.code['source']['membership']['managers'][0])
        identifier=engine['compiled']['compilations'][0]['scriptId'];active=self.busy if self.work_sequence>self.clear_after else None
        counters=activity(identifier,signals=int(active=='signal'),timers=int(active=='callback'),
            signal_calls=self.signal_calls+int(active=='signal'),timer_calls=self.timer_calls+int(active=='callback'),registrations=self.registrations)
        timers=[]
        if active in ('timer','inactive','unknown'):
            timers=[dict(handle=1,active=active!='inactive',singleShot=True,intervalMs=2000,
                remainingMs=-1 if active=='inactive' else 100,functionScriptId=0 if active=='unknown' else identifier)]
        activities=([activity(0,registrations=1)] if active=='unknown' else [])+[counters]
        work=dict(scriptWorkVersion=2,requestId=request['commandId'],sequence=self.work_sequence,
            requestedEpochMs=self.s.epoch,capturedEpochMs=self.s.epoch,signalCallbacks=counters['signalCallbacks'],
            timerCallbacks=counters['timerCallbacks'],evaluating=active=='evaluating',timers=timers,
            activity=activities,timerEntries=len(timers),activityEntries=len(activities))
        if self.work_fault=='lost':raise NativeUIError('Synthetic lost original work reply')
        value=dict(schemaVersion=1,requestId=request['commandId'],instance=self.s.before['instance'],sequence=self.work_sequence,
            processId=31,requestedEpochMs=self.s.epoch,capturedEpochMs=self.s.epoch,source=dict(complete=True,
                revision=self.s.code['source']['membership']['revision'],manager=manager,code=deepcopy(engine['code']),
                compiled=deepcopy(engine['compiled']),work=work,
                workers=[dict(membership=deepcopy(member),running=True,stopping=False,finished=False,done=False)
                    for member in self.s.code['source']['membership']['managers']]))
        if self.work_fault=='foreign-code':value['source']['code']['sha256']='0'*64
        if self.work_fault=='foreign-membership':value['source']['revision']+=1
        if self.work_fault=='frozen-cursor':value['sequence']=work['sequence']=1
        self.work_value=value
    def owner(self,source=None):return PicoEmoteLifetime(source or self.s.owner(),self.reader)


class LifetimeTests(unittest.TestCase):
    def setUp(self):self.model=LifetimeBoundary();self.addCleanup(self.model.close)
    def test_actual_idle_and_closed_sources_require_all_original_clocks_and_retain_journals(self):
        m=self.model
        with m.s.lock.held():
            owner=m.owner();window=owner.wait(sleep=m.sleep)
            self.assertGreaterEqual(window['elapsedMs'],3000);self.assertEqual('complete',owner.state['phase'])
            self.assertIsNotNone(owner.store.read());self.assertIsNotNone(owner.source.store.read())
            calls=list(m.s.calls);commands=list(m.work_commands)
            recovered=m.owner(owner.source);self.assertEqual(owner.state,recovered.state)
            self.assertEqual(calls,m.s.calls);self.assertEqual(commands,m.work_commands)
            self.assertEqual([],m.input.inputs);self.assertEqual([],m.input.controllers)
    def test_inactive_timer_unknown_origin_live_callbacks_and_evaluation_are_retained(self):
        for busy in ('timer','inactive','unknown','signal','callback','evaluating'):
            with self.subTest(busy=busy):
                m=LifetimeBoundary();self.addCleanup(m.close);m.busy=busy
                with m.s.lock.held():
                    owner=m.owner();owner.read();self.assertFalse(owner.quiet(owner.state['records'][-1]))
                    self.assertIsNone(owner.state['window']);self.assertIsNotNone(owner.store.read())
    def test_original_timer_disappearance_begins_a_new_full_window(self):
        m=self.model;m.busy='timer'
        with m.s.lock.held():
            owner=m.owner();owner.read();self.assertFalse(owner.quiet(owner.state['records'][0]))
            m.busy=None;m.registrations=1;window=owner.wait(sleep=m.sleep)
            self.assertEqual(2,window['first']);self.assertGreaterEqual(window['elapsedMs'],3000)
    def test_unobserved_completed_callback_or_native_override_restarts_quiet(self):
        for fault in ('callback','override','gap'):
            with self.subTest(fault=fault):
                m=LifetimeBoundary();self.addCleanup(m.close)
                with m.s.lock.held():
                    owner=m.owner();owner.read();m.sleep(1);owner.read()
                    if fault=='callback':m.signal_calls+=1
                    elif fault=='override':m.start('Waving');m.restore()
                    else:m.sleep(2)
                    owner.read();self.assertIsNone(owner.state['window'])
                    window=owner.wait(sleep=m.sleep);self.assertEqual(3,window['first'])
    def test_missing_work_after_original_source_cannot_query_again_on_reconstruction(self):
        m=self.model;m.work_fault='lost'
        with m.s.lock.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual('reading',owner.state['phase']);calls=list(m.work_commands);queries=list(m.s.calls)
            recovered=m.owner(owner.source)
            with self.assertRaises(NativeUIError):recovered.read()
            self.assertEqual(calls,m.work_commands);self.assertEqual(queries,m.s.calls)
    def test_foreign_work_code_registry_and_reused_cursor_cannot_qualify(self):
        for fault in ('foreign-code','foreign-membership','frozen-cursor'):
            with self.subTest(fault=fault):
                m=LifetimeBoundary();self.addCleanup(m.close)
                with m.s.lock.held():
                    owner=m.owner();owner.read();m.work_fault=fault
                    with self.assertRaises(NativeUIError):owner.read()
                    self.assertEqual('reading',owner.state['phase']);self.assertIsNotNone(owner.store.read())
    def test_panel_or_active_rig_and_new_phase_cannot_borrow_empty_script_work(self):
        m=self.model
        with m.s.lock.held():
            owner=m.owner();m.s.widget.tablet=True;m.s.widget.page=True
            owner.read();self.assertFalse(owner.quiet(owner.state['records'][-1]))
            m.s.journal.activate(RUN,'e'*32,'play',{'name':'Waving'})
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual('reading',owner.state['phase'])
    def test_frozen_actual_ui_clock_never_extends_the_quiet_window(self):
        m=self.model;original=m.s.widgets
        def frozen():
            value=original();value['elapsedMs']=0;return value
        m.s.widgets=frozen
        with m.s.lock.held():
            owner=m.owner()
            for _ in range(6):owner.read();m.sleep(.6)
            self.assertIsNone(owner.state['window']);self.assertEqual('ready',owner.state['phase'])
            self.assertIsNotNone(owner.store.read())

    def test_failed_initial_intent_never_constructs_any_native_reader(self):
        m=self.model
        with m.s.lock.held():
            owner=m.owner()
            def fail(*args):raise NativeUIError('Synthetic journal unavailable')
            owner.store.write=fail
            with self.assertRaises(NativeUIError):owner.read()
            self.assertEqual(0,m.work_factories);self.assertEqual([],m.work_commands);self.assertEqual([],m.s.calls)


if __name__=='__main__':unittest.main()
