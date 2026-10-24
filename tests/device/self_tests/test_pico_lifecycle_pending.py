"""Original Python Lifecycle continuation over explicit Qt/input/physics seams.

The existing Create/X/Chat/HOME owners run first. Native prepared IME events,
normal widget input and headset observations remain model boundaries here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pending_commit_owner import NativePendingCommitOwner
from adapters.pico4.lifecycle_pending import PicoLifecyclePending,run_pending
from adapters.pico4.lifecycle_source import current_editor
from adapters.script_journey.history import pack,unpack
from adapters.token_script_ui import TokenScriptUI
from self_tests.test_pending_commit_owner import Boundary as PendingBoundary
from self_tests import test_pico_lifecycle_background_owner as background_fixture
from self_tests.test_pico_lifecycle_source import RUN,editor
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from self_tests.test_token_script_ui import NativeBoundary


class LifecyclePendingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=background_fixture.LifecycleBackgroundOwnerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.owner.run_owned();self.background=self.fixture.owner
        self.world,self.native,self.root,self.lock=self.fixture.world,self.fixture.native,self.fixture.root,self.fixture.lock
        self.path=self.root/'lifecycle-pending-owner.json';self.boundary=PendingBoundary();self.boundary.epoch=self.native.epoch
        self.model=NativeBoundary();self.model.opened=True;self.model.sequence=0
        self.lost=None;self.ignore_x=False;self.x_inputs=[];self.normal_inputs=[]
        self.send=self.boundary.send
        def pending_send(request):
            self.send(request)
            if self.lost==request['operation']:
                self.pending_original();raise NativeUIError('Explicit uncertain original native pending response')
        self.boundary.send=pending_send
        self.original=self.boundary.original
        transport=self.world.session.transport;original_status=transport.read_status
        def stage(envelope,profile,*,before_publish=None):
            payload=unpack(json.loads(self.path.read_text())['payload'])[0]
            self.assertEqual(envelope,payload['backs'][-1]['envelope'])
            result=FakeTransport.stage(transport,envelope,profile,before_publish=before_publish);self.x_inputs.append(deepcopy(envelope))
            if not self.ignore_x:
                current=next(row for row in self.native.ui.rows if row['current'])
                current.update(fieldAlive=False,pageAlive=False,current=False,attached=False,visible=False,focused=False,text='')
                self.native.ui.raised=False;self.native.ui.home=True;self.model.page='home'
            if self.lost=='grant':raise NativeUIError('Explicit uncertain original X grant')
            return result
        transport.stage=stage
        def status(**kwargs):
            if self.lost=='x' and kwargs.get('expected_sequence') is not None:raise NativeUIError('Explicit uncertain original X answer')
            return original_status(**kwargs)|dict(updatedEpochMs=self.native.epoch())
        transport.read_status=status
        self.owner=self.make();self.owner.prepare()

    def pending_original(self):
        raw=self.original();value=json.loads(raw)
        current=next((row for row in self.native.ui.rows if row['current'] and row['kind']=='scripts'),None)
        if current is None:value['current']=dict(status='none')
        else:
            current.update(focused=self.boundary.focused,text=self.boundary.text)
            self.native.ui.raised=self.boundary.focused
        return json.dumps(value)

    def make(self):
        outer=self
        class Normal:
            def __init__(self):self.callback=None;self.navigation=SimpleNamespace(io=self)
            def bind_before_send(self,callback):
                if self.callback is not None and self.callback is not callback:raise NativeUIError('Foreign callback ownership')
                self.callback=callback
            def capture(self):
                value=outer.model.capture();value.update(bridgeId=outer.world.binding['sessionId'],generation='2'*32,
                    lastCommandSequence=outer.model.sequence,elapsedMs=round(outer.native.clock*1000))
                for row in value['controls']:row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['id']))
                return value
            def activate(self,identifier):
                before=self.capture();control=next(row for row in before['controls'] if row['id']==identifier)
                command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),bridgeId=before['bridgeId'],generation=before['generation'],
                    sequence=before['lastCommandSequence']+1,observedElapsedMs=before['elapsedMs'],controlId=identifier,controlToken=control['token'],action='activate')
                self.callback(deepcopy(command))
                saved=unpack(json.loads(outer.path.read_text())['payload'])[0]
                outer.assertEqual(command,saved['normal'][-1]);outer.normal_inputs.append(deepcopy(command))
                outer.model.activate(identifier);outer.model.sequence+=1
                if outer.model.page=='scripts':
                    count=3+sum(row['kind']=='scripts' for row in outer.native.ui.rows)
                    row=editor(count,'scripts');row.update(focused=False,text='');outer.native.ui.rows.append(row)
                    outer.native.ui.home=False;outer.native.ui.raised=False
                    outer.boundary.token=uuid.uuid5(uuid.NAMESPACE_URL,row['fieldId']).hex
                    outer.boundary.focused=False;outer.boundary.text=''
                if outer.lost=='normal':raise NativeUIError('Explicit uncertain normal Scripts answer')
        route=TokenScriptUI(Normal(),monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        pending=NativePendingCommitOwner(self.boundary.send,self.pending_original,self.native.epoch,lambda:self.native.alive,123,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        return PicoLifecyclePending(self.background,self.world,route,pending,self.path)

    def through_hold(self):
        self.owner.back();self.owner.open_scripts();self.owner.mutate('focus');self.owner.mutate('type');return self.owner.mutate('hold')

    def test_original_create_chat_return_to_scripts_pending_replacement_attempt_release_and_quiet(self):
        result=run_pending(self.owner)
        self.assertEqual(('scripts','',4,False,False,0,1),(result['editor'],result['text'],result['generation'],result['focused'],
            result['keyboard'],result['deferredInputs'],result['staleAttempts']))
        self.assertFalse(result['completeLifecycle']);self.assertTrue(result['journalRetained'])
        self.assertEqual(2,len(self.x_inputs));self.assertEqual(['scripts.entry','scripts.entry'],[row['controlId'] for row in self.normal_inputs])
        self.assertEqual(['focus','type','hold','attempt','release'],[row['operation'] for row in self.boundary.commands if row['operation']!='observe'])
        self.assertNotEqual(self.owner.state['scriptId'],self.owner.state['replacementId'])
        old=next(row for row in self.native.ui.rows if row['id']==self.owner.state['scriptId'])
        self.assertTrue(old['contextAlive']);self.assertFalse(old['fieldAlive']);self.assertFalse(old['pageAlive'])
        self.assertEqual('quiet',self.owner.state['phase']);self.assertGreaterEqual(len(self.owner.state['quiet']),13)
        self.assertTrue(self.owner.originals.root.path.exists());self.assertTrue(self.owner.store.path.exists())

    def test_lost_hold_answer_recovers_original_event_without_second_capture(self):
        self.owner.back();self.owner.open_scripts();self.owner.mutate('focus');self.owner.mutate('type');self.lost='hold'
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.lost=None;self.owner=self.make();result=run_pending(self.owner)
        self.assertEqual(1,result['staleAttempts']);self.assertEqual(1,sum(row['operation']=='hold' for row in self.boundary.commands))

    def test_late_first_hold_observation_cannot_refresh_original_host_deadline(self):
        self.owner.back();self.owner.open_scripts();self.owner.mutate('focus');self.owner.mutate('type');self.lost='hold'
        captured=self.native.clock
        with self.assertRaises(NativeUIError):self.owner.mutate('hold')
        self.native.sleep(9.5);self.lost=None;self.owner=self.make();self.owner.reconcile()
        self.assertAlmostEqual(captured,self.owner.state['holdHost'])
        self.native.sleep(.6)
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.assertEqual(1,sum(row['operation']=='hold' for row in self.boundary.commands));self.assertEqual(1,len(self.x_inputs))

    def test_fresh_pending_packet_transport_latency_cannot_move_actual_hold_birth(self):
        self.owner.back();self.owner.open_scripts();self.owner.mutate('focus');self.owner.mutate('type')
        original=self.owner.pending.original;created=None;delayed=False
        def transport():
            nonlocal created,delayed
            raw=original();value=json.loads(raw)
            if value['operation']=='hold' and value['performed']:
                created=self.native.clock # Actual fixture producer's capture, before delivery delay.
            if value['operation']=='observe' and value['commit'] and self.owner.state['phase']=='hold-issued' and not delayed:
                delayed=True;self.native.sleep(.6)
            return raw # Preserve the exact original older, still-fresh native packet.
        self.owner.pending.original=transport;self.owner.mutate('hold')
        self.assertTrue(delayed);self.assertIsNotNone(created)
        self.assertLessEqual(self.owner.state['holdHost'],created)
        self.assertEqual(1,sum(row['operation']=='hold' for row in self.boundary.commands))
        # Persist the old unsafe value without altering any source original;
        # actual cold reconstruction must refuse it, never silently rebase it.
        unsafe=deepcopy(self.owner.state);unsafe['holdHost']=created+.6
        original=self.owner.store.read();changed=deepcopy(original)
        changed['payload']=pack(self.owner.originals.encode([unsafe]));self.owner.store.write(changed,original)
        before=len(self.boundary.commands)
        with self.assertRaises(NativeUIError):self.make()
        self.assertEqual(before,len(self.boundary.commands))

    def test_lost_normal_scripts_answer_and_x_answer_never_replay_original_input(self):
        self.lost='x'
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.lost=None;self.owner=self.make();self.owner.reconcile();self.lost='normal'
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.lost=None;self.owner=self.make();result=run_pending(self.owner)
        self.assertEqual(4,result['generation']);self.assertEqual(2,len(self.x_inputs));self.assertEqual(2,len(self.normal_inputs))

    def test_hold_expiry_cannot_become_stale_attempt_or_recreate_the_event(self):
        self.through_hold();self.native.sleep(10)
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.assertEqual(1,len(self.x_inputs));self.assertNotIn('attempt',[row['operation'] for row in self.boundary.commands])
        self.assertTrue(self.owner.store.path.exists())

    def test_ignored_x_keeps_original_context_and_never_represses_on_recovery(self):
        self.through_hold();self.ignore_x=True
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.assertEqual(2,len(self.x_inputs));self.assertIsNone(self.owner.state['replacementId'])
        with self.assertRaises(NativeUIError):run_pending(self.make())
        self.assertEqual(2,len(self.x_inputs))

    def test_failed_durable_intent_blocks_normal_x_and_preserves_prior_background_owner(self):
        before=self.background.store.path.read_bytes()
        with patch.object(self.owner.store,'write',side_effect=OSError('Explicit private persistence failure')),self.assertRaises((OSError,NativeUIError)):
            run_pending(self.owner)
        self.assertEqual([],self.x_inputs);self.assertEqual([],self.normal_inputs);self.assertEqual(before,self.background.store.path.read_bytes())

    def test_partial_failure_releases_only_original_holder_when_current_ui_is_unavailable(self):
        self.through_hold();current=next(row for row in self.native.ui.rows if row['current'])
        current.update(current=False,focused=False,visible=False,attached=False,text='')
        self.native.ui.raised=False;self.native.ui.home=True
        result=self.owner.release_owned();self.assertTrue(result['pendingReleased']);self.assertFalse(result['completeLifecycle'])
        self.assertEqual('released',self.boundary.record['events'][-1]['kind'])
        self.assertEqual(1,sum(row['operation']=='release' for row in self.boundary.commands))
        self.assertNotIn('attempt',[row['operation'] for row in self.boundary.commands])
        self.owner=self.make();self.assertTrue(self.owner.release_owned()['pendingReleased'])
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.assertEqual(1,sum(row['operation']=='release' for row in self.boundary.commands))

    def test_lost_failure_release_reads_original_terminal_inventory_without_releasing_again(self):
        self.through_hold();self.lost='release'
        with self.assertRaises(NativeUIError):self.owner.release_owned()
        self.lost=None;self.owner=self.make();self.assertTrue(self.owner.release_owned()['pendingReleased'])
        self.assertEqual(1,sum(row['operation']=='release' for row in self.boundary.commands))
        self.assertTrue(self.owner.store.path.exists())

    def test_unknown_grant_keeps_original_stream_without_adopting_neutral_or_repressing_x(self):
        self.lost='grant'
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.lost=None
        with self.assertRaises(NativeUIError):run_pending(self.make())
        self.assertEqual(1,len(self.x_inputs));self.assertEqual([],self.normal_inputs)

    def test_replacement_context_alias_is_refused_before_original_stale_attempt(self):
        self.through_hold();self.owner.back(True);original=self.owner.route.io.activate
        old=next(row for row in self.native.ui.rows if row['id']==self.owner.state['scriptId'])
        def replaced(identifier):
            original(identifier)
            if identifier=='scripts.entry':self.native.ui.rows[-1]['contextId']=old['contextId']
        self.owner.route.io.activate=replaced
        with self.assertRaises(NativeUIError):self.owner.open_scripts(True)
        self.assertNotIn('attempt',[row['operation'] for row in self.boundary.commands])

    def test_final_pending_transport_fence_catches_native_jump_after_durable_intent(self):
        self.owner.back();self.owner.open_scripts();intent=self.owner.pending.intent;clock=self.owner.pending.clock_ms
        def late(request):
            intent(request);self.owner.pending.clock_ms=lambda:clock()+2000
        self.owner.pending.intent=late
        with self.assertRaises(NativeUIError):self.owner.mutate('focus')
        self.assertEqual([], [row for row in self.boundary.commands if row['operation']!='observe'])
        self.assertEqual('focus-issued',self.owner.state['phase']);self.assertEqual(1,len(self.owner.state['mutations']))

    def test_original_manifest_replacement_cannot_be_adopted_on_cold_owner(self):
        path=self.owner.originals.root.path;raw=path.read_bytes();before=len(self.boundary.commands)
        replacement=path.with_name(path.name+'.replacement');replacement.write_bytes(raw);replacement.chmod(0o600)
        replacement.replace(path)
        with self.assertRaises(NativeUIError):self.make()
        self.assertEqual(before,len(self.boundary.commands));self.assertEqual([],self.x_inputs);self.assertEqual([],self.normal_inputs)

    def test_final_back_report_copy_native_jump_cannot_escape_original_age(self):
        report=self.owner.report;clock=self.owner.pending.clock_ms
        def late():
            value=report();self.owner.pending.clock_ms=lambda:clock()+2000;return value
        with patch.object(self.owner,'report',side_effect=late),self.assertRaises(NativeUIError):self.owner.back()
        self.assertEqual('home',self.owner.state['phase']);self.assertEqual(1,len(self.x_inputs));self.assertEqual([],self.normal_inputs)

    def test_actual_outer_source_lock_exit_native_jump_is_checked_after_exit(self):
        held=self.lock.held;clock=self.owner.pending.clock_ms;changed=False
        @contextmanager
        def late_exit():
            nonlocal changed
            with held():yield
            if self.lock._owner is None and not changed:
                changed=True;self.owner.pending.clock_ms=lambda:clock()+2000
        with patch.object(self.lock,'held',side_effect=late_exit),self.assertRaises(NativeUIError):self.owner.back()
        self.assertTrue(changed);self.assertIsNone(self.lock._owner)
        self.assertEqual('home',self.owner.state['phase']);self.assertEqual(1,len(self.x_inputs))

    def test_nested_current_child_calls_cannot_reset_whole_twenty_second_budget(self):
        back,opened=self.owner.back,self.owner.open_scripts
        def delayed_back(replacement=False):
            value=back(replacement)
            if not replacement:self.native.sleep(12)
            return value
        def delayed_open(replacement=False):
            value=opened(replacement)
            if not replacement:self.native.sleep(9)
            return value
        self.owner.back=delayed_back;self.owner.open_scripts=delayed_open
        with self.assertRaises(NativeUIError):run_pending(self.owner)
        self.assertEqual('opened',self.owner.state['phase']);self.assertEqual(1,len(self.x_inputs));self.assertEqual(1,len(self.normal_inputs))
        self.assertEqual([], [row for row in self.boundary.commands if row['operation']!='observe'])


def lifecycle_pending_progress_tests():
    return unittest.TestSuite(LifecyclePendingTests(name) for name in (
        'test_original_create_chat_return_to_scripts_pending_replacement_attempt_release_and_quiet',
        'test_lost_hold_answer_recovers_original_event_without_second_capture',
        'test_late_first_hold_observation_cannot_refresh_original_host_deadline',
        'test_fresh_pending_packet_transport_latency_cannot_move_actual_hold_birth',
        'test_lost_normal_scripts_answer_and_x_answer_never_replay_original_input',
        'test_partial_failure_releases_only_original_holder_when_current_ui_is_unavailable',
        'test_lost_failure_release_reads_original_terminal_inventory_without_releasing_again'))


def lifecycle_pending_failure_tests():
    # Disjoint counterexamples; the composed positive is never split/repeated.
    progress={case._testMethodName for case in lifecycle_pending_progress_tests()}
    return unittest.TestSuite(LifecyclePendingTests(name) for name in unittest.defaultTestLoader.getTestCaseNames(LifecyclePendingTests)
        if name not in progress)


if __name__=='__main__':unittest.main()
