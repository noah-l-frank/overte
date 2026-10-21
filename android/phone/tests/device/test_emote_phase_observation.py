"""Original idle-phase Rig/PNG joins without invented input acknowledgements."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_emote_observation import Model,POLICY
from test_emote_sources import RUN,TICKET
from adapters.normal_ui import NativeUIError
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_effects import PhoneEmoteEffects
from overte_phone_emote_observation import PhoneEmoteObservation,ObservationOriginals
from overte_phone_script_history import pack,unpack


class EmotePhaseObservationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-phase-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name));mock=patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=self.model.tablet)
        mock.start();self.addCleanup(mock.stop)

    def baseline(self,*,role='primary',owner=None):
        m=self.model;owner=PhoneEmoteInputs(m.source()) if owner is None else owner
        # Independent actor sources have a real primary baseline context, but
        # no ordinary input owner/journal or primary result forwarding.
        if role=='actor' and not owner.source.frames:owner.source.read()
        return m.scope(owner,1,role=role)

    def test_initial_phase_joins_fresh_role_local_sources_and_original_image_without_input(self):
        m=self.model
        with m.lock.held():
            scope=self.baseline();value=scope.read_phase(TICKET)
            self.assertEqual(2,value['emoteObservationResultVersion']);self.assertEqual(1,value['effect']['emotePhaseEffectVersion'])
            self.assertEqual('baseline',value['effect']['phase']);self.assertFalse(value['state']['override'])
            self.assertEqual(2,scope.load('capture')['emoteObservationFrameVersion'])
            self.assertEqual(2,scope.load('outcome')['emoteObservationFrameVersion']);self.assertEqual(value,scope.original())
            self.assertEqual([],m.controls.input_requests);self.assertEqual([],m.tablet_inputs)
            self.assertIsNone(scope.effects.inputs.store.read());self.assertEqual(1,m.world.counters['capture'])
            self.assertFalse((m.world_root/'world-primary.json').exists())

    def test_phase_archive_with_absent_input_owner_replays_after_live_journals_advance(self):
        m=self.model;retained=[]
        with m.lock.held():
            scope=self.baseline();result=scope.read_phase(TICKET);packet=scope.transfer(lambda value:retained.append(deepcopy(value)))
            self.assertIsNone(packet['inputHeader']);self.assertEqual([packet],retained)
            call=m.call('play',dict(name='Waving'));owner=PhoneEmoteInputs(m.source());owner.act(call)
            current=PhoneEmoteEffects(owner);before=m.calls.count('native-read');count=m.world.counters['capture']
            self.assertEqual(result,PhoneEmoteObservation.archive(packet,current,1,POLICY))
            self.assertEqual(before,m.calls.count('native-read'));self.assertEqual(count,m.world.counters['capture'])
            context=current._archive_context(packet['inputHeader'],packet['inputSourceHeader'],packet['sourceHeader'])
            with self.assertRaises(NativeUIError):context.source.read()
            with self.assertRaises(NativeUIError):context.inputs.bound()

    def test_independent_actor_baseline_acquires_its_own_source_and_png_with_no_primary_input(self):
        m=self.model
        with m.lock.held():
            primary=self.baseline();left=primary.read_phase(TICKET);p=primary.transfer(lambda *_:None)
            actor=self.baseline(role='actor',owner=primary.effects.inputs);right=actor.read_phase(TICKET);a=actor.transfer(lambda *_:None)
            self.assertEqual('actor',right['role']);self.assertNotEqual(left['image'],right['image'])
            self.assertEqual(2,m.world.counters['capture']);self.assertEqual([],m.controls.input_requests)
            self.assertEqual(right,PhoneEmoteObservation.archive(a,actor.effects,1,POLICY))
            self.assertEqual(left,PhoneEmoteObservation.archive(p,primary.effects,1,POLICY))

    def test_cleanup_phase_observes_actual_post_input_idle_and_keeps_original_input_ownership(self):
        m=self.model
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source());owner.act(call)
            call=m.call('close');owner=PhoneEmoteInputs(m.source());owner.act(call)
            m.journal.activate(RUN,'e'*32,'cleanup',{});scope=m.scope(owner,3);before=deepcopy(m.controls.input_requests)
            value=scope.read_phase('e'*32);self.assertEqual('cleanup',value['effect']['phase'])
            self.assertFalse(value['state']['panel']);self.assertTrue(owner.store.path.exists());self.assertEqual(before,m.controls.input_requests)
            packet=scope.transfer(lambda *_:None);self.assertIsNotNone(packet['inputHeader'])
            self.assertEqual(value,PhoneEmoteObservation.archive(packet,scope.effects,3,POLICY))
            packet['inputHeader']=None
            with self.assertRaises(NativeUIError):PhoneEmoteObservation.archive(packet,scope.effects,3,POLICY)

    def test_ordinary_action_cannot_use_phase_mode_to_skip_its_native_effect_proof(self):
        m=self.model
        with m.lock.held():
            call=m.call('open');owner=PhoneEmoteInputs(m.source());owner.act(call);scope=m.scope(owner,2)
            with self.assertRaises(NativeUIError):scope.read_phase(call['ticket'])
            self.assertEqual('preparing',scope.state['phase']);self.assertEqual(0,m.world.counters['capture'])
            self.assertIsNotNone(scope.store.read())

    def test_baseline_cannot_use_an_invented_ordinary_input_or_active_override(self):
        m=self.model
        with m.lock.held():
            scope=self.baseline()
            with self.assertRaises(NativeUIError):scope.read(TICKET)
            self.assertEqual(0,m.world.counters['capture']);self.assertIsNone(scope.effects.inputs.store.read())
        # A new isolated scope index still sees the actual active Rig.
        with m.lock.held():
            m.start('Waving');owner=PhoneEmoteInputs(m.source());active=m.scope(owner,2)
            with self.assertRaises(NativeUIError):active.read_phase(TICKET)
            self.assertEqual(0,m.world.counters['capture'])

    def test_foreign_image_marker_never_publishes_idle_success(self):
        m=self.model;m.image_fault='foreign-marker'
        with m.lock.held():
            scope=self.baseline()
            with self.assertRaises(NativeUIError):scope.read_phase(TICKET)
            self.assertNotEqual('complete',scope.state['phase']);self.assertEqual(1,m.world.counters['capture'])

    def test_fixture_phase_change_during_capture_never_returns_the_old_baseline(self):
        m=self.model
        with m.lock.held():
            scope=self.baseline();m.on_capture=lambda:m.journal.activate(RUN,'e'*32,'cleanup',{})
            with self.assertRaises(NativeUIError):scope.read_phase(TICKET)
            self.assertNotEqual('complete',scope.state['phase']);self.assertEqual(1,m.world.counters['capture'])
            self.assertIsNotNone(scope.store.read())

    def test_override_started_during_original_image_interval_cannot_become_idle_success(self):
        m=self.model
        with m.lock.held():
            scope=self.baseline();m.on_capture=lambda:m.start('Waving')
            with self.assertRaises(NativeUIError):scope.read_phase(TICKET)
            self.assertNotEqual('complete',scope.state['phase']);self.assertEqual(1,m.world.counters['capture'])

    def test_faulty_writer_expected_closed_panel_cannot_replace_the_original_phase_measurement(self):
        m=self.model;m.widgets.page=True;m.widgets.tablet=True
        with m.lock.held():
            scope=self.baseline();self.assertTrue(scope.read_phase(TICKET)['state']['panel'])
            outcome=deepcopy(scope.load('outcome'));outcome['effect']['state']['panel']=False
            writer=ObservationOriginals(m.root,scope.source.binding,RUN,'primary',lambda:True,lambda *_:None,
                kind='observations',monotonic=lambda:m.clock)
            reference=writer.write(2,outcome);header=deepcopy(scope.previous);state=unpack(header['payload'])[0]
            state['outcome']=reference;header['payload']=pack([state]);scope.store.write(header,scope.previous)
            current=self.baseline()
            with self.assertRaises(NativeUIError):current.original()
            with self.assertRaises(NativeUIError):current.transfer(lambda *_:None)
            self.assertIsNotNone(current.store.read());self.assertEqual(1,m.world.counters['capture'])

    def test_phase_image_cannot_replace_its_saved_state_or_ordinary_effect_variant(self):
        m=self.model
        with m.lock.held():
            scope=self.baseline();scope.read_phase(TICKET);packet=scope.transfer(lambda *_:None)
            for fault in ('state','version','effect','scope','input'):
                value=deepcopy(packet)
                if fault=='state':value['result']['state']['panel']=not value['result']['state']['panel']
                elif fault=='version':value['result']['emoteObservationResultVersion']=1
                elif fault=='effect':value['result']['effect']['call']=dict(verb='open',performed=True)
                elif fault=='scope':value['header']['scopeId']='f'*32
                else:value['inputHeader']=dict(performed=True)
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,OSError)):
                    PhoneEmoteObservation.archive(value,scope.effects,1,POLICY)

    def test_incomplete_phase_image_retains_absent_input_owner_without_promoting_a_result(self):
        m=self.model
        with m.lock.held():
            scope=self.baseline();save=scope.save
            def fail():
                if scope.state['phase']=='complete':raise OSError('Synthetic failed final phase commit')
                return save()
            with patch.object(scope,'save',side_effect=fail),self.assertRaises(OSError):scope.read_phase(TICKET)
            current=self.baseline();packet=current.transfer_incomplete(lambda *_:None)
            self.assertIsNone(packet['inputHeader']);self.assertNotIn('result',packet)
            self.assertEqual('measuring',unpack(packet['header']['payload'])[0]['phase'])
            PhoneEmoteObservation.incomplete_archive(packet,current.effects,1,POLICY)

    def test_failed_baseline_preparation_retains_source_failure_without_inventing_an_input_owner(self):
        m=self.model
        with m.lock.held():
            scope=self.baseline();scope.source.read();send=m.native_send
            def lost(request):send(request);raise NativeUIError('Synthetic baseline preparation result loss')
            with patch.object(m,'native_send',side_effect=lost),self.assertRaises(NativeUIError):scope.read_phase(TICKET)
            self.assertEqual('preparing',scope.state['phase']);current=self.baseline();packet=current.transfer_failed(lambda *_:None)
            self.assertIsNone(packet['inputHeader']);self.assertIsNone(packet['childRetirement']);self.assertNotIn('result',packet)
            self.assertEqual('reading',unpack(packet['sourceHeader']['payload'])[0]['phase'])
            self.assertIsNone(current.effects.inputs.store.read());self.assertTrue(current.source.store.path.exists())
            self.assertEqual(0,m.world.counters['capture']);PhoneEmoteObservation.failure_archive(packet,current.effects,1,POLICY)


if __name__=='__main__':unittest.main()
