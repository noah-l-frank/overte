"""Private normal 1–4 operations/common waits, never execute/peer/images.

Native Qt/physics/OS and final app-file/controller I/O retain explicit models.
The original owners, session locks, phase grammar and consumers execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.chat_journey import source_bundles
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_operations import PicoLifecycleOperations
from feature_journeys.fixtures import context
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.witness import Client,Journal
from self_tests import test_pico_lifecycle_chat as chat_fixture
from self_tests import test_pico_lifecycle_background_owner as background_fixture
from self_tests import test_pico_lifecycle_observation_baseline as baseline_fixture
from self_tests import test_pico_lifecycle_primary_wait as wait_fixture
from self_tests.test_pico_lifecycle_readonly import readonly_entry


class LifecycleOperationsTests(unittest.TestCase):
    def at_prefix(self,probe):
        case=baseline_fixture.LifecycleObservationBaselineTests();self.addCleanup(case.doCleanups)
        case.coordinator_attach_roles=getattr(self,'coordinator_attach_roles',set())
        waiter=wait_fixture.LifecyclePrimaryWaitTests();self.addCleanup(waiter.doCleanups)
        waiter.fixture=case;waiter.frames=[];waiter.calls=[];waiter.forbidden_calls=[]
        self.in_session=False;self.inputs=[];self.finished=[]
        def baseline():
            self.source=case.observer;self.native=case.editor.native
            self.journal=Journal(self.native.epoch);run=self.journal.register('lifecycle-input')
            self.journal.runs[self.source.run]=self.journal.runs.pop(run)
            self.journal.activate(self.source.run,uuid.uuid4().hex)
            client=Client('http://controlled.invalid/feature-fixture/v1','r'*64)
            def request(path,**kwargs):
                self.assertFalse(self.in_session,'Phase HTTP reentered locked controller callback')
                self.assertEqual('/runs/'+self.source.run+'/phase',path)
                return self.journal.phase(self.source.run,kwargs['phase_nonce'])
            client.request=request
            phases=PhaseFixtureReader(client,self.source.run,'lifecycle-input',epoch_ms=self.native.epoch,monotonic=lambda:self.native.clock)
            # Explicit final Qt-I/O seams: invoke the bound hook at the model's
            # actual final input boundary, preserving its original native effect.
            for io in (self.source.editor.route.io,self.source.editor.field.io):
                def bind(callback,*,_io=io):
                    self.assertFalse(hasattr(_io,'phase_callback'));_io.phase_callback=callback
                io.bind_before_send=bind
                for name in ('activate','replace'):
                    if not hasattr(io,name):continue
                    original=getattr(io,name)
                    def input(*args,_io=io,_original=original,**kwargs):
                        _io.phase_callback({});self.inputs.append((args,deepcopy(kwargs)))
                        return _original(*args,**kwargs)
                    setattr(io,name,input)
            self.operations=PicoLifecycleOperations(self.source,phases,self.source.store.path.with_name('lifecycle-primary-operations.json'))
            self.source.observe_operation=self.operations.invoke
            held=self.source.world.session._lock
            @contextmanager
            def locked():
                with held():
                    self.assertFalse(self.in_session);self.in_session=True
                    try:yield
                    finally:self.in_session=False
            self.source.world.session._lock=locked
            waiter.baseline()
        def drive(editor,joined):
            self.assertIs(editor,self.source.editor);self.assertIs(joined,self.source.restore.joined)
            probe(case,waiter);self.finished.append(True)
            raise NativeUIError('Explicit stop after normal primary-only Lifecycle operation prefix')
        case.collect_baseline=baseline
        with readonly_entry(case),patch.object(chat_fixture,'run_create_world_back',drive):
            with self.assertRaises(NativeUIError):case.setUp()
        self.assertEqual([True],self.finished)
        return case,waiter

    def fields(self,index):
        step=SCENARIOS['lifecycle-input']['steps'][index];ticket=uuid.uuid4().hex
        inputs=expand(step['inputs'],context(self.source.run))
        self.journal.activate(self.source.run,ticket,step['verb'],inputs)
        return dict(verb=step['verb'],inputs=inputs,ticket=ticket,fixtureUrl=self.operations.scope['fixtureUrl'])

    def test_existing_normal_four_actions_and_unchanged_primary_waits_keep_all_originals(self):
        def probe(case,waiter):
            counts=[]
            for index in range(4):
                fields=self.fields(index);barrier=self.native.epoch()
                waiter.journey.call('act',fields)
                waiter.journey.required_lifecycle=deepcopy(waiter.journey.lifecycle)
                expected=expand(SCENARIOS['lifecycle-input']['steps'][index]['state'],context(self.source.run))
                waiter.journey.wait('private-'+str(index+1)+'-'+fields['verb'],fields['ticket'],barrier,expected,[],duration=3 if index==3 else .5)
                counts.append(dict(action=index+1,world=len(self.source.world.state['frames']),readonly=len(self.source.disk['records'])))
            self.assertEqual([],waiter.forbidden_calls);self.assertEqual(4,len(self.operations.state['steps']))
            self.assertTrue(all(row['phase']=='returned' for row in self.operations.state['steps']))
            self.assertEqual(3,len(case.editor.transport.envelopes))
            self.assertEqual(1,len(self.source.world.state['attempts']))
            self.assertLessEqual(len(self.source.world.state['frames']),128);self.assertLessEqual(len(self.source.disk['records']),128)
            with self.source.lock.held():self.source.world.load()
            report=dict(scope='private-normal-primary-only-prefix',counts=counts,
                worldTriples=len(self.source.world.state['frames']),readonlyTriples=len(self.source.disk['records']),
                totalPhysicalTriples=len(self.source.world.state['frames'])+len(self.source.disk['records']),
                readonlyParts=len(self.source.disk['chunks']),readonlyContainerRawBytes=self.source.history.raw_bytes,
                readonlyLogicalOriginalBytes=source_bundles.logical_bytes(self.source.disk['bundles']),
                readonlyActualStoredFileBytes=sum(path.stat().st_size for path in
                    [self.source.store.path,*[self.source.history._path(i) for i in range(len(self.source.disk['chunks']))]]),
                readonlyActualFileCount=1+len(self.source.disk['chunks']),
                phaseParts=len(self.operations.state['chunks']),phaseContainerRawBytes=self.operations.history.raw_bytes,
                phaseLogicalOriginalBytes=source_bundles.logical_bytes(self.operations.state['bundles']),
                phaseActualStoredFileBytes=sum(path.stat().st_size for path in
                    [self.operations.store.path,*[self.operations.history._path(i) for i in range(len(self.operations.state['chunks']))]]),
                phaseActualFileCount=1+len(self.operations.state['chunks']))
            PrivateFeatureState(self.source.store.path.with_name('lifecycle-operations-diagnostics.json')).write(report,None)
            print('Actual normal-operation prefix bill: '+str(report),flush=True)
        self.at_prefix(probe)

    def test_phase_change_after_actual_child_cas_refuses_before_transport_and_never_resends(self):
        def probe(case,waiter):
            fields=self.fields(0);save=self.source.editor.save;changed=[]
            def changing(state):
                save(state)
                if state['phase']=='tablet-issued' and state['tablet']['envelope'] is None:
                    changed.append(True);self.journal.activate(self.source.run,uuid.uuid4().hex,'cleanup')
            self.source.editor.save=changing
            for _attempt in range(2):
                with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
            self.assertEqual([True],changed);self.assertTrue(self.operations.failed)
            self.assertEqual([],case.editor.transport.envelopes);self.assertEqual([],self.inputs)
            self.assertEqual('issued',self.operations.store.read()['steps'][-1]['phase'])
            self.assertEqual('tablet-issued',self.source.editor.state['phase'])
        self.at_prefix(probe)

    def test_native_jump_after_actual_child_cas_under_fixed_host_cannot_refresh_input_anchor(self):
        def probe(case,waiter):
            fields=self.fields(0);save=self.source.editor.save;epoch=self.native.epoch;changed=[]
            def late(state):
                save(state)
                if state['phase']=='tablet-issued' and state['tablet']['envelope'] is None:
                    changed.append(True);self.operations.phases.epoch_ms=self.operations.fence.source.epoch_ms=lambda:epoch()+2000
            self.source.editor.save=late;before=self.native.clock
            with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
            self.assertEqual(before,self.native.clock);self.assertEqual([True],changed)
            self.assertEqual([],case.editor.transport.envelopes);self.assertEqual([],self.inputs)
            self.assertTrue(self.operations.failed);self.assertEqual('issued',self.operations.store.read()['steps'][-1]['phase'])
        self.at_prefix(probe)

    def test_phase_change_after_actual_qml_child_intent_prevents_unicode_delivery(self):
        def probe(case,waiter):
            opened=self.fields(0);waiter.journey.call('act',opened)
            expected=expand(SCENARIOS['lifecycle-input']['steps'][0]['state'],context(self.source.run))
            waiter.journey.wait('private-open-before-qml-counter',opened['ticket'],self.native.epoch(),expected,[],duration=.5)
            fields=self.fields(1);save=self.source.editor.save;changed=[];before=len(self.inputs)
            def changing(state):
                save(state)
                if state['phase']=='typing' and state['inputs'][-1]['phase']=='typing' and state['inputs'][-1]['consumed'] is None:
                    changed.append(True);self.journal.activate(self.source.run,uuid.uuid4().hex,'cleanup')
            self.source.editor.save=changing
            with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
            self.assertEqual([True],changed);self.assertEqual(before,len(self.inputs))
            self.assertEqual('',case.editor.field.text);self.assertEqual('typing',self.source.editor.state['phase'])
            self.assertTrue(self.operations.failed)
        self.at_prefix(probe)

    def test_actual_outer_operation_lock_exit_failure_retains_applied_input_without_ack_or_replay(self):
        def probe(case,waiter):
            fields=self.fields(0);held=self.source.lock.held;depth=0;exited=[]
            @contextmanager
            def exit_failure():
                nonlocal depth
                outer=depth==0;depth+=1
                try:
                    with held():yield
                finally:depth-=1
                if outer:exited.append(True);raise NativeUIError('Actual outer operation lock exit refused')
            with patch.object(self.source.lock,'held',exit_failure):
                with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
            before=len(self.inputs);self.assertTrue(before>0)
            self.assertEqual([True],exited);self.assertTrue(self.operations.failed)
            self.assertEqual('returned',self.operations.store.read()['steps'][-1]['phase'])
            with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
            self.assertEqual(before,len(self.inputs));self.assertEqual(1,len(case.editor.transport.envelopes))
        self.at_prefix(probe)

    def test_landed_parent_returned_save_with_native_jump_under_fixed_host_is_uncertain(self):
        def probe(case,waiter):
            fields=self.fields(0);save=self.operations.save;changed=[];epoch=self.native.epoch
            def late():
                save()
                if self.operations.state['steps'] and self.operations.state['steps'][-1]['phase']=='returned':
                    changed.append(True);self.operations.phases.epoch_ms=lambda:epoch()+2000
            self.operations.save=late;before=self.native.clock
            with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
            self.assertEqual(before,self.native.clock);self.assertEqual([True],changed)
            self.assertTrue(self.operations.failed);self.assertEqual(1,len(case.editor.transport.envelopes))
            self.assertEqual('returned',self.operations.store.read()['steps'][-1]['phase'])
        self.at_prefix(probe)

    def test_slow_locked_release_intent_refuses_grant_removal_without_phase_reentry_or_replay(self):
        def probe(case,waiter):
            for index in range(2):
                fields=self.fields(index);waiter.journey.call('act',fields)
                expected=expand(SCENARIOS['lifecycle-input']['steps'][index]['state'],context(self.source.run))
                waiter.journey.wait('private-before-release-counter-'+str(index),fields['ticket'],self.native.epoch(),expected,[],duration=.5)
            fields=self.fields(2);world=self.source.world;save=world.save;counts=[]
            def slow(state):
                save(state)
                if state['attempts'] and state['attempts'][-1]['phase']=='release-issued':
                    self.assertTrue(self.in_session);counts.append(world.session.transport.cleanup_count);self.native.clock+=2
            world.save=slow
            with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
            self.assertEqual(1,len(counts));self.assertEqual(counts[0],world.session.transport.cleanup_count)
            self.assertEqual('release-issued',world.state['attempts'][-1]['phase']);self.assertTrue(self.operations.failed)
            with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
            self.assertEqual(counts[0],world.session.transport.cleanup_count)
        self.at_prefix(probe)

    def outer_fault(self,*,observe=False,replace_phase=False):
        def probe(case,waiter):
            held=self.source.lock.held;depth=0;changed=[]
            @contextmanager
            def changed_after_exit():
                nonlocal depth
                outer=depth==0;depth+=1
                try:
                    with held():yield
                finally:depth-=1
                if outer:
                    changed.append(True)
                    if replace_phase:
                        original=self.operations.phases
                        self.operations.phases=PhaseFixtureReader(original.client,original.run,original.area,
                            epoch_ms=original.epoch_ms,monotonic=original.monotonic)
                    else:
                        path=self.operations.store.path
                        backup=path.with_name('counter-parent-original-before-exit.json')
                        backup.write_bytes(path.read_bytes());backup.chmod(0o600);path.unlink()
            fields=dict(afterSequence=waiter.journey.sequence) if observe else self.fields(0)
            with patch.object(self.source.lock,'held',changed_after_exit):
                with self.assertRaises(NativeUIError):waiter.journey.call('observe' if observe else 'act',fields)
            self.assertEqual([True],changed);self.assertTrue(self.operations.failed)
            before=len(self.inputs)
            with self.assertRaises(NativeUIError):waiter.journey.call('observe' if observe else 'act',fields)
            self.assertEqual(before,len(self.inputs))
            self.assertEqual(0 if observe else 1,len(case.editor.transport.envelopes))
        self.at_prefix(probe)

    def test_actual_outer_exit_parent_removal_cannot_deliver_applied_action_ack(self):self.outer_fault()
    def test_actual_outer_exit_parent_removal_cannot_deliver_fresh_observation(self):self.outer_fault(observe=True)
    def test_actual_outer_exit_phase_reader_replacement_cannot_deliver_action_ack(self):self.outer_fault(replace_phase=True)


class LifecycleOperationsBackgroundTests(unittest.TestCase):
    at_prefix=LifecycleOperationsTests.at_prefix
    fields=LifecycleOperationsTests.fields
    coordinator_attach_roles={'chat','background'}

    def run_seven(self):
        def probe(case,waiter):
            children={};counts=[]
            def chat(_fence):
                helper=chat_fixture.LifecycleChatTests();helper.initialize_from_editor(case.editor,self.source.restore.joined)
                self.addCleanup(helper.doCleanups);children['chat']=helper
                io=helper.owner.route.io
                def bind(callback):
                    self.assertFalse(hasattr(io,'phase_callback'));io.phase_callback=callback
                io.bind_before_send=bind
                for name in ('activate','replace'):
                    original=getattr(io,name)
                    def input(*args,_original=original,**kwargs):
                        io.phase_callback({});self.inputs.append((args,deepcopy(kwargs)))
                        return _original(*args,**kwargs)
                    setattr(io,name,input)
                return helper.owner
            def background(_fence):
                helper=background_fixture.LifecycleBackgroundOwnerTests();helper.initialize_from_chat(children['chat'])
                self.addCleanup(helper.doCleanups);children['background']=helper
                fault=getattr(self,'background_fault',None)
                if fault in ('home','resume'):
                    save=helper.owner.save
                    def changing(state):
                        save(state)
                        if state['phase']==dict(home='home-issued',resume='resume-issued')[fault]:
                            self.journal.activate(self.source.run,uuid.uuid4().hex,'cleanup')
                    helper.owner.save=changing
                elif fault=='arm':
                    runtime=helper.owner.runtime_factory
                    def changed(intent):
                        world,reader,native=runtime(intent);guard=reader.guard
                        def final_guard():
                            result=guard()
                            if helper.owner.state is not None and helper.owner.state['phase']=='arm-issued' and helper.owner.state['inputs']:
                                self.journal.activate(self.source.run,uuid.uuid4().hex,'cleanup')
                            return result
                        reader.guard=final_guard;return world,reader,native
                    helper.owner.runtime_factory=changed
                return helper.owner
            self.operations.factories=dict(chat=chat,background=background)
            for index in range(7):
                fields=self.fields(index);barrier=self.native.epoch()
                required=deepcopy(waiter.journey.lifecycle)
                if fields['verb']=='background-resume':required['backgrounds']+=1;required['activations']+=1
                waiter.journey.required_lifecycle=required
                if index==6 and getattr(self,'background_fault',None) is not None:
                    with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
                    helper=children['background'];fault=self.background_fault
                    self.assertEqual(['lifecycle.background'] if fault=='resume' else [],helper.inputs)
                    self.assertEqual(0 if fault=='arm' else 1,len([row for row in helper.history.commands if row['operation']=='arm']))
                    self.assertEqual(dict(arm='arm-issued',home='home-issued',resume='resume-issued')[fault],helper.owner.state['phase'])
                    self.assertTrue(self.operations.failed)
                    before=len(helper.inputs)
                    with self.assertRaises(NativeUIError):waiter.journey.call('act',fields)
                    self.assertEqual(before,len(helper.inputs));return
                waiter.journey.call('act',fields)
                expected=expand(SCENARIOS['lifecycle-input']['steps'][index]['state'],context(self.source.run))
                waiter.journey.wait('private-seven-'+str(index+1)+'-'+fields['verb'],fields['ticket'],barrier,expected,[],duration=3 if index==3 else .5)
                counts.append(dict(action=index+1,world=len(self.source.world.state['frames']),readonly=len(self.source.disk['records'])))
            self.assertEqual([],waiter.forbidden_calls);self.assertEqual(7,len(self.operations.state['steps']))
            self.assertIs(self.source.chat,children['chat'].owner);self.assertIs(self.source.background,children['background'].owner)
            self.assertIs(children['background'].world,self.source.world)
            self.assertEqual(['lifecycle.background','app.launch'],children['background'].inputs)
            self.assertEqual([],children['chat'].widgets.sent)
            self.assertEqual(['arm','release'],[row['operation'] for row in children['background'].history.commands if row['operation']!='observe'])
            report=dict(scope='private-normal-primary-only-seven',counts=counts,worldTriples=len(self.source.world.state['frames']),
                readonlyTriples=len(self.source.disk['records']),totalPhysicalTriples=len(self.source.world.state['frames'])+len(self.source.disk['records']))
            PrivateFeatureState(self.source.store.path.with_name('lifecycle-operations-seven-diagnostics.json')).write(report,None)
            print('Actual same-graph seven-action bill: '+str(report),flush=True)
        self.at_prefix(probe)

    def test_same_live_graph_normal_seven_actions_and_common_waits_keep_original_background_sources(self):self.run_seven()
    def test_phase_change_after_background_home_cas_prevents_home(self):self.background_fault='home';self.run_seven()
    def test_phase_change_after_background_resume_cas_prevents_launch_without_qt(self):self.background_fault='resume';self.run_seven()
    def test_phase_change_in_background_arm_final_guard_prevents_native_mutation(self):self.background_fault='arm';self.run_seven()


if __name__=='__main__':unittest.main()
