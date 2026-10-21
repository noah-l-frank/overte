"""Ordinary input journals over synthetic SDK/Qt/Rig boundaries, never a device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.emote_rig_measurements import playback
from adapters.normal_ui import NativeUIError
from adapters.token_emote_ui import TokenEmoteUI
from feature_journeys.scenarios import VERSION
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_script_history import pack,unpack
from test_emote_sources import Originals as SourceOriginals,RUN,TICKET,OTHER


class Originals(SourceOriginals):
    def __init__(self,root):
        super().__init__(root);self.tablet_inputs=[];self.input_fault=None;self.sessions=0;self.phase_index=0;self.idle=False
    def normal_feature_runtime(self,_selector,*,read_only=False):
        binding=deepcopy(self.binding)
        return None,None,binding,lambda:self.okay and self.binding==binding,dict(bound=True)
    def sleep(self,seconds):
        self.clock+=seconds;self.widgets.clock+=seconds
    @contextmanager
    def existing_input_session(self,_selector):
        self.sessions+=1
        yield
    def _emote_controls(self,selector,intent,*,receipt=None,read_only=False):
        io=super()._emote_controls(selector,intent,read_only=True).io
        if read_only:return SimpleNamespace(io=io)
        return TokenEmoteUI(io,intent,receipt=receipt,**self.options())
    def tablet(self,*_args):
        model=self
        class Tablet:
            def tablet_visible(self):return model.widgets.tablet
            def open_tablet(self):
                model.tablet_inputs.append('tablet.open')
                if model.input_fault=='lost-sdk':raise NativeUIError('Synthetic lost SDK return')
                if model.input_fault!='ignored-sdk':model.widgets.tablet=True
            def close_tablet(self):model.tablet_inputs.append('tablet.close');model.widgets.tablet=False
            def wait_tablet_absent(self):assert not model.widgets.tablet
        return Tablet()
    def call(self,verb,inputs=None):
        self.phase_index+=1;ticket=format(0x100+self.phase_index,'032x');inputs={} if inputs is None else inputs
        self.journal.activate(RUN,ticket,verb,inputs)
        return dict(contractVersion=VERSION,runId=RUN,ticket=ticket,fixtureUrl=URL(),verb=verb,inputs=inputs)


def URL():return 'http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'


class PhoneEmoteInputsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-inputs-');self.addCleanup(temporary.cleanup)
        self.model=Originals(Path(temporary.name));self.mock=patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=self.model.tablet)
        self.tablet_factory=self.mock.start();self.addCleanup(self.mock.stop)
    def test_open_play_and_close_use_original_normal_controls_and_durable_consumption_receipts(self):
        m=self.model
        with m.lock.held():
            call=m.call('open');source=m.source();owner=PhoneEmoteInputs(source);self.assertEqual({'performed':True},owner.act(call))
            self.assertTrue(m.widgets.page);self.assertEqual('acknowledged',owner.state['current']['phase'])
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call)
            row=owner.state['current'];self.assertEqual('Waving',m.widgets.active)
            play=[item for item in row['intents'] if item['kind']=='qt' and item['input']['controlId']=='emote.play.Waving']
            self.assertEqual(1,len(play));self.assertIsNotNone(play[0]['barrier']);self.assertIsNotNone(play[0]['after'])
            self.assertNotIn('state',row);self.assertNotIn('poseProgress',row)
            call=m.call('close');owner=PhoneEmoteInputs(m.source());owner.act(call)
            self.assertFalse(m.widgets.tablet);self.assertFalse(m.widgets.page)
            self.assertEqual(['tablet.close'],m.tablet_inputs);self.assertEqual(2,len(owner.state['history']))
            PhoneEmoteInputs(m.source()) # Full original input/source replay.
    def test_consumed_input_without_a_new_native_override_cannot_prove_playback(self):
        m=self.model;m.widgets.page=True
        with m.lock.held():
            call=m.call('play',dict(name='Crying'));owner=PhoneEmoteInputs(m.source());owner.act(call)
            intent=next(item for item in owner.state['current']['intents'] if item['kind']=='qt')
            before=owner.original(intent['barrier'])['group']['native'];after=owner.source.read()
            self.assertEqual('Crying',m.widgets.active)
            with self.assertRaises(NativeUIError):playback(after['group'],before,pid=31,epoch=after['epochMs'])
        self.assertEqual(1,len(m.controls.input_requests))
    def test_closed_tablet_is_opened_once_and_observed_before_entering_emote(self):
        m=self.model;m.widgets.tablet=False
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source());owner.act(call);row=owner.state['current']
            self.assertEqual('sdk',row['intents'][0]['kind']);self.assertIsNotNone(row['intents'][0]['after'])
            self.assertTrue(owner.original(row['intents'][0]['after'])['ui']['open'])
        self.assertEqual(['tablet.open'],m.tablet_inputs);self.assertTrue(m.widgets.page)
    def test_lost_sdk_input_return_cannot_be_repeated_after_reconstruction(self):
        m=self.model;m.widgets.tablet=False;m.input_fault='lost-sdk'
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
            owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual('issuing',owner.state['current']['phase'])
        self.assertEqual(['tablet.open'],m.tablet_inputs);self.assertEqual([],m.controls.input_requests)
    def test_ignored_sdk_input_cannot_use_its_ack_as_visibility(self):
        m=self.model;m.widgets.tablet=False;m.input_fault='ignored-sdk'
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(['tablet.open'],m.tablet_inputs);self.assertEqual('issuing',owner.state['current']['phase'])
    def test_lost_qt_return_keeps_the_exact_pending_intent_without_second_delivery(self):
        m=self.model;m.widgets.page=True;send=m.controls.send
        def lost(value):
            send(value)
            if value['request']['action']!='observe':raise NativeUIError('Synthetic lost native receipt')
        m.controls.send=lost
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
            owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(1,len(m.controls.input_requests));self.assertEqual('issuing',owner.state['current']['phase'])
    def test_duplicate_acknowledged_call_sends_no_more_inputs_but_still_checks_actual_phase(self):
        m=self.model
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source());owner.act(call);before=len(m.controls.input_requests)
            self.assertEqual({'performed':True},owner.act(call));self.assertEqual(before,len(m.controls.input_requests))
            m.call('close')
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(before,len(m.controls.input_requests))
    def test_foreign_ticket_or_fixture_input_mismatch_sends_nothing(self):
        m=self.model
        with m.lock.held():
            call=m.call('play',dict(name='Waving'));call['inputs']['name']='Crying';owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual([],m.controls.input_requests);self.assertIsNone(owner.store.read())
    def test_wait_complete_performs_no_synthetic_restore_or_expected_duration_sleep(self):
        m=self.model
        with m.lock.held():
            call=m.call('wait-complete');owner=PhoneEmoteInputs(m.source());owner.act(call)
        self.assertEqual([],owner.state['current']['intents']);self.assertEqual([],m.controls.input_requests)
        self.assertEqual([],m.tablet_inputs);self.assertEqual(0.,m.clock)
    def test_cancel_without_an_actual_active_widget_name_is_not_a_delivered_cancel(self):
        m=self.model;m.widgets.page=True
        with m.lock.held():
            call=m.call('cancel');owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual([],m.controls.input_requests);self.assertNotEqual('acknowledged',owner.state['current']['phase'])
    def test_sit_discovery_reset_of_actual_idle_is_verified_without_a_restore_input(self):
        m=self.model;m.widgets.page=True;m.idle=True
        with m.lock.held():
            call=m.call('cancel');owner=PhoneEmoteInputs(m.source());owner.act(call)
            row=owner.state['current'];self.assertEqual('acknowledged',row['phase'])
            frame=owner.original(row['idleReset']);self.assertFalse(frame['group']['native']['animation']['overrideActive'])
            self.assertEqual([],row['intents']);PhoneEmoteInputs(m.source())
        self.assertEqual([],m.controls.input_requests)
    def test_cancel_toggles_the_actual_current_name_once_without_requesting_a_restore(self):
        m=self.model;m.widgets.page=True;m.widgets.active='Crying'
        with m.lock.held():
            call=m.call('cancel');owner=PhoneEmoteInputs(m.source());owner.act(call)
        self.assertEqual('',m.widgets.active)
        self.assertEqual(['emote.play.Crying'],[item['controlId'] for item in m.controls.input_requests])
        self.assertEqual('acknowledged',owner.state['current']['phase'])
    def test_timer_completion_between_cancel_selection_and_delivery_is_not_acknowledged(self):
        m=self.model;m.widgets.page=True;m.widgets.active='Crying';factory=m._emote_controls
        def completed(*args,**kwargs):
            ui=factory(*args,**kwargs)
            if not kwargs.get('read_only',False):
                cancel=ui.cancel
                def race():m.widgets.active='';cancel()
                ui.cancel=race
            return ui
        m._emote_controls=completed
        with m.lock.held():
            call=m.call('cancel');owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual([],m.controls.input_requests)
        self.assertNotEqual('acknowledged',unpack(owner.store.read()['payload'])[0]['current']['phase'])
    def test_sit_selects_the_real_sit_control_and_never_selects_a_variant(self):
        m=self.model;m.widgets.page=True;m.widgets.offset=6
        with m.lock.held():
            call=m.call('sit');owner=PhoneEmoteInputs(m.source());owner.act(call)
        self.assertEqual(['emote.play.Sit'],[item['controlId'] for item in m.controls.input_requests])
        self.assertNotIn('sit',owner.state['current'])
    def test_failed_receipt_persistence_does_not_repeat_the_consumed_input(self):
        m=self.model
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source())
            owner.receipt=lambda *_:(_ for _ in ()).throw(NativeUIError('Synthetic receipt store failure'))
            with self.assertRaises(NativeUIError):owner.act(call)
            restored=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):restored.act(call)
        self.assertEqual(1,len(m.controls.input_requests));self.assertTrue(m.widgets.page)
        self.assertEqual('issuing',restored.state['current']['phase'])
    def test_failed_intent_persistence_sends_no_input_and_keeps_incomplete_owner(self):
        m=self.model
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source());write=owner.store.write
            def fail(value,previous):
                if unpack(value['payload'])[0]['current']['phase']=='issuing':raise NativeUIError('Synthetic intent store failure')
                write(value,previous)
            owner.store.write=fail
            with self.assertRaises(NativeUIError):owner.act(call)
            restored=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):restored.act(call)
        self.assertEqual([],m.controls.input_requests);self.assertEqual('acting',restored.state['current']['phase'])
    def test_phase_changed_during_play_barrier_cannot_deliver_the_old_input(self):
        m=self.model;m.widgets.page=True
        with m.lock.held():
            call=m.call('play',dict(name='Crying'));owner=PhoneEmoteInputs(m.source());intent=owner.intent
            def switched(value):m.journal.activate(RUN,OTHER,'close',{});intent(value)
            owner.intent=switched
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual([],m.controls.input_requests)
    def test_failed_final_ack_write_cannot_pass_on_same_object_retry(self):
        m=self.model
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source());write=owner.store.write
            def fail(value,previous):
                if unpack(value['payload'])[0]['current']['phase']=='acknowledged':raise NativeUIError('Synthetic final ACK write failure')
                write(value,previous)
            owner.store.write=fail
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual('acting',owner.state['current']['phase'])
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(1,len(m.controls.input_requests));self.assertTrue(m.widgets.page)
    def test_whole_input_deadline_covers_sdk_delivery_and_final_source_checks(self):
        m=self.model;m.widgets.tablet=False;tablet=m.tablet()
        open_tablet=tablet.open_tablet
        def delayed():open_tablet();m.clock+=46
        tablet.open_tablet=delayed
        self.tablet_factory.side_effect=lambda *_:tablet
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual(['tablet.open'],m.tablet_inputs);self.assertEqual('issuing',owner.state['current']['phase'])
    def test_corrupt_source_reference_or_consumption_receipt_cannot_be_adopted(self):
        m=self.model
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source());owner.act(call);original=owner.store.read()
            for fault in ('digest','revision','receipt','phase','binding','foreign-ui','foreign-counter'):
                changed=deepcopy(original);state=unpack(changed['payload'])[0];current=state['current'];item=current['intents'][0]
                if fault=='digest':current['before']['sha256']='f'*64
                elif fault=='revision':current['before']['revision']=True
                elif fault=='receipt':item['after']['scope']['sequence']=True
                elif fault=='phase':item['provider']['activations'][-1]['stimulus']['verb']='close'
                elif fault=='binding':changed['binding']['artifactSha256']='f'*64
                elif fault=='foreign-ui':
                    item['input']['original']['scope']['instance']=item['input']['instance']='f'*32
                    item['after']['scope']['instance']='f'*32
                else:
                    item['input']['original']['scope']['sequence']+=1;item['input']['sequence']+=1;item['after']['scope']['sequence']+=1
                changed['payload']=pack([state]);owner.store.write(changed,owner.store.read())
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):PhoneEmoteInputs(m.source())
    def test_lost_history_archive_preserves_pending_scope_and_never_delivers_the_next_call(self):
        m=self.model
        with m.lock.held():
            owner=PhoneEmoteInputs(m.source());owner.act(m.call('open'));next_call=m.call('wait-complete')
            intent=owner.history_store.intent
            def lost(kind,value):
                intent(kind,value)
                if kind=='original' and value['phase']=='opened':raise NativeUIError('Synthetic archive return lost')
            owner.history_store.intent=lost
            with self.assertRaises(NativeUIError):owner.act(next_call)
            restored=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):restored.act(next_call)
            self.assertEqual('opened',restored.history_state['pendingArchive']['original']['phase'])
        self.assertEqual(1,len(m.controls.input_requests))
    def test_completed_history_file_corruption_cannot_be_hidden_by_the_current_row(self):
        m=self.model
        with m.lock.held():
            owner=PhoneEmoteInputs(m.source());owner.act(m.call('open'));owner.act(m.call('wait-complete'))
            entry=owner.history_store.manifest(owner.history_state['manifests'][0])[0]
            owner.history_store.path(owner.history_store.expand(entry)).write_bytes(b'{}')
            with self.assertRaises(NativeUIError):PhoneEmoteInputs(m.source())
    def test_full_shared_sit_attempt_bound_fits_original_history_and_private_owner_records(self):
        from feature_journeys.scenarios import SCENARIOS
        maximum=len(SCENARIOS['emotes']['steps'])-3+3*24*2
        m=self.model;m.widgets.page=True;m.widgets.offset=6
        with m.lock.held():
            owner=PhoneEmoteInputs(m.source())
            for _ in range(3*24):
                owner.act(m.call('sit'));owner.act(m.call('cancel'))
            for _ in range(maximum-3*24*2):owner.act(m.call('wait-complete'))
            self.assertEqual(maximum-1,len(owner.state['history']))
            self.assertLess(owner.store.path.stat().st_size,65536);self.assertLess(owner.source.store.path.stat().st_size,65536)
            restored=PhoneEmoteInputs(m.source())
            self.assertEqual(maximum-1,len(restored.state['history']))
            self.assertEqual(owner.state,restored.state)
        # These are ordinary input/storage boundaries. Native Waving remained
        # unchanged throughout: this test establishes no Sit/product success.
        self.assertEqual(144,len(m.controls.input_requests))
    def test_lost_guard_during_ack_commit_cannot_pass_after_session_guard_returns(self):
        m=self.model
        with m.lock.held():
            owner=PhoneEmoteInputs(m.source());owner.act(m.call('open'));call=m.call('wait-complete');write=owner.store.write
            def lost(value,previous):
                current=unpack(value['payload'])[0]['current']
                if current is not None and current['call']['ticket']==call['ticket'] and current['phase']=='acknowledged':
                    m.okay=False;raise NativeUIError('Synthetic lost guard during ACK commit')
                write(value,previous)
            owner.store.write=lost
            with self.assertRaises(NativeUIError):owner.act(call)
            m.okay=True
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertTrue(owner.failed);self.assertEqual(1,len(m.controls.input_requests))
    def test_legacy_inline_input_history_is_preserved_without_adoption(self):
        m=self.model
        with m.lock.held():
            owner=PhoneEmoteInputs(m.source());legacy=dict(emoteInputsVersion=1,runId=RUN,fixtureUrl=URL(),binding=m.binding,
                payload=pack([dict(history=[],current=None)]))
            owner.store.write(legacy,None)
            with self.assertRaises(NativeUIError):PhoneEmoteInputs(m.source())
        self.assertEqual(legacy,owner.store.read());self.assertEqual([],m.controls.input_requests)


if __name__=='__main__':unittest.main()
