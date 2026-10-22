"""Actual ordinary event recipes interrupted at each URL input boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
import uuid
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input
from ios.adapters.avatar_recipe_ui import AvatarRecipeUI
from ios.adapters.avatar_inputs import delivered
from ios.self_tests import test_ios_avatar_input_owner as fixture
from ios.self_tests.test_ios_avatar_inputs import packet

URL='https://controlled.invalid/avatar-a.fst'


class AvatarRecipeUITests(unittest.TestCase):
    def make(self,lost_at):
        f=fixture.InputOwnerTests();f.setUp();self.addCleanup(f.doCleanups)
        held=f.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        calls=[];post=f.source.post
        def transport(request,timeout):
            import json
            query=json.loads(request.data)
            if query['operation']=='edit':
                calls.append(deepcopy(query['input']));f.source.lost=len(calls)==lost_at
            return post(request,timeout)
        boundary=patch.object(normal_input,'urlopen',transport);boundary.start();self.addCleanup(boundary.stop)
        owner=f.owner();owner.begin(fixture.CALL)
        with self.assertRaises(NativeUIError):f.ui(owner).avatar_url(URL)
        f.source.lost=False;last=owner.state['calls'][0]['events'][-1];original=last['intent'];receipt=deepcopy(f.source.receipt)
        epoch=receipt['status']['sampleEpochMs'];value=packet(42,epoch);identity=str(uuid.uuid4())
        control=next(row for row in original['reference']['controls'] if row['id']==original['controlId'])
        value['source']['events']=[dict(sequence=1,eventId=str(uuid.uuid4()),inputId=identity,kind='received',clock=dict(epochMs=epoch,monotonicMs=1),
            details=dict(outerCommandId=receipt['commandId'],command=deepcopy(original['nativeCommand']),controlId=original['controlId'],
                root={key:control[key] for key in ('rootId','qmlSource')})),
            dict(sequence=2,eventId=str(uuid.uuid4()),inputId=identity,kind='returned',clock=dict(epochMs=epoch,monotonicMs=2),details=receipt)]
        restored=f.owner();restored.load();restored.delivered(original,delivered(value,original));restored.observed(original,f.io.capture())
        return f,restored,calls
    def ui(self,f,owner,*,deadline=lambda:True):
        return AvatarRecipeUI(f.io,owner.intent,owner.state['calls'][0]['events'],deadline=deadline,
            delivered=owner.delivered,observed=owner.observed,monotonic=lambda:f.source.clock,
            sleep=lambda seconds:setattr(f.source,'clock',f.source.clock+seconds))
    def test_every_lost_URL_input_return_resumes_program_counter_without_duplicate_native_commands(self):
        for lost_at in range(1,5):
            with self.subTest(lost_at=lost_at):
                f,owner,calls=self.make(lost_at);prefix=deepcopy(calls);ui=self.ui(f,owner)
                capture=f.io.capture;historical=[]
                def live():
                    self.assertEqual(len(prefix),ui.cursor);historical.append(True);return capture()
                f.io.capture=live;ui.avatar_url(URL);ui.complete();owner.finish()
                self.assertEqual(prefix,calls[:lost_at]);self.assertEqual(4,len(calls));self.assertEqual(URL,f.source.avatar_url)
                self.assertEqual(4,len({row['commandId'] for row in calls}));self.assertTrue(historical)
                self.assertTrue(all(row['phase']=='observed' for row in owner.state['calls'][0]['events']))
    def test_changed_current_root_or_source_refuses_the_first_remaining_input(self):
        for fault in ('root','source'):
            with self.subTest(fault=fault):
                f,owner,calls=self.make(1);count=len(calls);rows=f.source.rows
                def changed():
                    values=rows()
                    for row in values:
                        if row.get('rootId'):
                            if fault=='root':row['rootId']='ffffffff-ffff-4fff-8fff-ffffffffffff'
                            else:row['qmlSource']='qrc:/different/hifi/AvatarApp.qml'
                    return values
                f.source.rows=changed
                with self.assertRaises(NativeUIError):self.ui(f,owner).avatar_url(URL)
                self.assertEqual(count,len(calls))
    def test_different_recipe_branch_cannot_consume_or_replay_saved_prefix(self):
        f,owner,calls=self.make(2);count=len(calls)
        with self.assertRaises(NativeUIError):self.ui(f,owner).save_bookmark('e2e-'+fixture.RUN)
        self.assertEqual(count,len(calls))
    def test_expired_original_deadline_prevents_even_historical_planning_and_all_new_input(self):
        f,owner,calls=self.make(2);count=len(calls)
        def expired():raise NativeUIError('Original operation deadline has elapsed')
        with self.assertRaises(NativeUIError):self.ui(f,owner,deadline=expired).avatar_url(URL)
        self.assertEqual(count,len(calls))
    def test_received_only_event_cannot_be_used_as_a_program_counter(self):
        f,owner,calls=self.make(1);events=deepcopy(owner.state['calls'][0]['events']);events[0].update(phase='issued',delivery=None,observed=None)
        with self.assertRaises(NativeUIError):AvatarRecipeUI(f.io,owner.intent,events,deadline=lambda:True,
            monotonic=lambda:f.source.clock,sleep=lambda _:None)
        self.assertEqual(1,len(calls))
    def test_slow_original_intent_save_or_second_capture_cannot_send_after_deadline(self):
        from ios.adapters import avatar_operation_clock
        for fault in ('intent-save','second-capture','native-process-read'):
            with self.subTest(fault=fault):
                f=fixture.InputOwnerTests();f.setUp();self.addCleanup(f.doCleanups)
                with f.lock.held(),patch.object(normal_input,'urlopen',f.source.post):
                    owner=f.owner();owner.begin(fixture.CALL)
                    original=avatar_operation_clock.begin(1000000,f.source.clock);started=f.source.clock
                    def deadline():return avatar_operation_clock.check(original,1000000+(f.source.clock-started)*1000,f.source.clock)
                    save=owner.intent
                    def saved(value):
                        save(value)
                        if fault=='intent-save':f.source.clock+=26
                    capture=f.io.capture;observed=0
                    def captured():
                        nonlocal observed
                        value=capture();observed+=1
                        if fault=='second-capture' and observed==2:f.source.clock+=26
                        return value
                    process=f.native.observe_process;checked=0
                    def checked_process():
                        nonlocal checked
                        value=process();checked+=1
                        # Each capture checks the process four times. The edit
                        # starts its own final process check after both captures.
                        if fault=='native-process-read' and checked==9:f.source.clock+=26
                        return value
                    f.io.capture=captured;f.native.observe_process=checked_process
                    ui=AvatarRecipeUI(f.io,saved,[],deadline=deadline,delivered=owner.delivered,observed=owner.observed,
                        monotonic=lambda:f.source.clock,sleep=lambda _:None)
                    with self.assertRaises(NativeUIError):ui.input('avatar.url-open')
                    self.assertEqual([], [row for row in f.source.requests if row['operation']=='edit'])
                    self.assertEqual('issued',owner.load()['calls'][0]['events'][-1]['phase'])


if __name__=='__main__':unittest.main()
