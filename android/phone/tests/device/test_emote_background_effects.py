"""Real Emote joins over synthetic native/OS/UI originals; no device acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]

from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_effects import PhoneEmoteEffects
from overte_phone_script_history import pack,unpack
from overte_phone_emote_observation import PhoneEmoteObservation,ObservationBoundaries
from test_emote_observation import Model as ImageModel
from test_emote_background import Model as BackgroundModel
from test_emote_pixels import POLICY


class Model(ImageModel,BackgroundModel):
    """Share the existing independent image and ordinary lifecycle boundaries."""


class EmoteBackgroundEffectTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-background-effects-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name));self.model.use_included_source()
        mock=patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=self.model.tablet)
        mock.start();self.addCleanup(mock.stop)

    def prepare(self,role='primary',*,second_cancel=False):
        m=self.model;play=m.call('play',dict(name='Crying'));owner=PhoneEmoteInputs(m.source());owner.act(play)
        first=m.scope(owner,1,role=role);played=first.read(play['ticket']);first.transfer(lambda *_:None)
        cancel=m.call('cancel');owner=PhoneEmoteInputs(m.source());owner.act(cancel)
        second=m.scope(owner,2,role=role)
        second.read(cancel['ticket'],played=played['effect']['playbackReference'])
        previous=second.transfer(lambda *_:None)
        if second_cancel:
            again=m.call('cancel');PhoneEmoteInputs(m.source()).act(again)
        call=m.call('background-resume');background=m.owner();background.act(call)
        owner=PhoneEmoteInputs(m.source());source=owner.source if role=='primary' else m.source(role)
        effects=PhoneEmoteEffects(owner,current_source=source);source.read()
        return effects,dict(previous=previous,header=deepcopy(background.previous),image_policy=POLICY),call

    def test_background_facts_recompute_current_native_restore_and_actual_early_cancel(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();calls=deepcopy(m.calls)
            value=effects.background_recompute(effects.reference(),**context)
            self.assertEqual(calls,m.calls);self.assertEqual(1,value['emoteBackgroundEffectVersion'])
            self.assertEqual(call,value['call']);self.assertEqual('idle',value['state']['animation'])
            self.assertTrue(value['state']['restoredBeforeNominalEnd']);self.assertFalse(value['state']['override'])
            self.assertEqual('primary',value['role']);self.assertEqual(context['previous']['result']['ticket'],value['previousTicket'])
            self.assertEqual(value,effects.measure(effects.reference(),background=context))
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)
            self.assertEqual(0,m.background_native_accesses)

    def test_actor_uses_its_own_prior_cancel_archive_and_current_source_measurement(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare('actor');reference=effects.reference()
            value=effects.measure(reference,background=context)
            self.assertEqual('actor',value['role']);self.assertEqual(call,value['call'])
            self.assertEqual(effects.source.frames[reference['revision']-1]['group'],value['proof']['group'])
            self.assertEqual('actor',context['previous']['result']['role'])
            self.assertTrue(value['state']['restoredBeforeNominalEnd'])

    def test_old_phase_and_stale_frames_are_historical_only_never_fresh_background_facts(self):
        m=self.model
        with m.lock.held():
            effects,context,_call=self.prepare();reference=effects.reference()
            original=effects.background_recompute(reference,**context);m.epoch+=1600
            self.assertEqual(original,effects.background_recompute(reference,**context))
            with self.assertRaises(NativeUIError):effects.measure(reference,background=context)
            m.call('close')
            with self.assertRaises(NativeUIError):effects.measure(reference,background=context)

    def test_later_cancel_cannot_borrow_an_earlier_actual_early_restore_checkpoint(self):
        m=self.model
        with m.lock.held():
            effects,context,_call=self.prepare(second_cancel=True)
            with self.assertRaises(NativeUIError):effects.background_recompute(effects.reference(),**context)

    def test_changed_original_effect_background_generation_and_forged_completion_are_rejected(self):
        m=self.model
        with m.lock.held():
            effects,context,_call=self.prepare();reference=effects.reference()
            for fault in ('prior-fact','prior-role','cycle-completion','cycle-namespace','cycle-cleanup'):
                changed=deepcopy(context)
                if fault=='prior-fact':changed['previous']['result']['state']['restoredBeforeNominalEnd']=False
                elif fault=='prior-role':changed['previous']['header']['role']='actor'
                else:
                    header=changed['header'];state=unpack(header['payload'])[0]
                    if fault=='cycle-completion':state['phase']='observing';state['afterHeader']=None
                    elif fault=='cycle-namespace':header['sourceSegment']=1
                    else:state['cleanup']={}
                    header['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,KeyError,ValueError)):
                    effects.background_recompute(reference,**changed)

    def test_extra_lifecycle_transition_is_not_the_completed_cycle(self):
        m=self.model
        with m.lock.held():
            effects,context,_call=self.prepare();m.lifecycle['activations']+=1;effects.source.read()
            with self.assertRaises(NativeUIError):effects.background_recompute(effects.reference(),**context)

    def test_current_panel_is_read_from_new_ui_instead_of_the_pre_background_checkpoint(self):
        m=self.model
        with m.lock.held():
            effects,context,_call=self.prepare();old=context['previous']['result']['state']['panel']
            m.widgets.page=not old;effects.source.read()
            value=effects.measure(effects.reference(),background=context)
            self.assertEqual(not old,value['state']['panel']);self.assertTrue(value['state']['restoredBeforeNominalEnd'])

    def test_another_actual_background_blocks_fresh_facts_without_foreground_native_getters(self):
        m=self.model
        with m.lock.held():
            effects,context,_call=self.prepare();m.foreground=False;reads=m.calls.count('native-read')
            with self.assertRaises(NativeUIError):effects.background_recompute(effects.reference(),**context)
            self.assertEqual(reads,m.calls.count('native-read'));self.assertEqual(0,m.background_native_accesses)

    def test_copied_original_header_at_another_namespace_path_cannot_relabel_the_cycle(self):
        m=self.model
        with m.lock.held():
            effects,context,_call=self.prepare();changed=deepcopy(context);changed['header']['sourceSegment']=1
            copied=PrivateFeatureState(m.root/'phone-emote-primary-sources-segment-1.json')
            copied.write(deepcopy(effects.input_source.previous),None)
            with self.assertRaises((NativeUIError,ValueError)):effects.background_recompute(effects.reference(),**changed)
            self.assertIsNotNone(copied.read())
    def test_new_actual_override_cannot_borrow_the_completed_idle_cycle(self):
        m=self.model
        with m.lock.held():
            effects,context,_call=self.prepare();m.start('Waving');effects.source.read()
            with self.assertRaises(NativeUIError):effects.background_recompute(effects.reference(),**context)


class EmoteBackgroundObservationTests(unittest.TestCase):
    setUp=EmoteBackgroundEffectTests.setUp
    prepare=EmoteBackgroundEffectTests.prepare

    def image_scope(self,effects):
        self.model.current_index=3
        return PhoneEmoteObservation(effects,3,POLICY)

    def boundary(self,effects,context):
        source=effects.source;intents=[]
        writer=ObservationBoundaries(source.artifact_root,source.binding,source.run,source.role,source.guard,
            lambda kind,value:intents.append((kind,deepcopy(value))),kind='observation-boundaries',monotonic=source.monotonic)
        reference=writer.write(1,context)
        self.assertEqual(['planned','opened','saved'],[value['phase'] for kind,value in intents])
        return writer,reference

    def test_actual_background_image_retains_current_early_restore_without_a_fake_ordinary_input(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();writer,reference=self.boundary(effects,context)
            before=deepcopy(effects.inputs.previous);scope=self.image_scope(effects)
            value=scope.read_background(call['ticket'],reference)
            self.assertEqual(3,value['emoteObservationResultVersion']);self.assertEqual(3,scope.previous['emoteObservationVersion'])
            self.assertEqual(1,value['effect']['emoteBackgroundEffectVersion']);self.assertTrue(value['state']['restoredBeforeNominalEnd'])
            self.assertEqual('idle',value['state']['animation']);self.assertEqual(before,effects.inputs.previous)
            self.assertEqual(reference,scope.state['background']);self.assertLess(scope.store.path.stat().st_size,65536)
            self.assertEqual(context,writer.read(writer.expand(reference)))
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_actor_background_image_uses_its_original_cancel_and_own_new_native_frame(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare('actor');_writer,reference=self.boundary(effects,context)
            scope=self.image_scope(effects);value=scope.read_background(call['ticket'],reference)
            self.assertEqual('actor',value['role']);self.assertEqual('actor',value['effect']['role'])
            self.assertEqual(effects.current_original(value['effect']['frame'])['group'],value['effect']['proof']['group'])

    def test_preparing_failure_transfers_real_background_dependencies_without_relabeling_cancel(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();writer,reference=self.boundary(effects,context)
            scope=self.image_scope(effects)
            with patch.object(effects.source,'read',side_effect=NativeUIError('Synthetic source failure')),self.assertRaises(NativeUIError):
                scope.read_background(call['ticket'],reference)
            self.assertEqual('preparing',scope.state['phase']);self.assertNotEqual(call['ticket'],effects.inputs.state['current']['call']['ticket'])
            packets=[];packet=scope.transfer_failed(lambda value:packets.append(deepcopy(value)))
            self.assertEqual([packet],packets);self.assertIsNone(scope.store.read());self.assertIsNone(packet['childRetirement'])
            self.assertEqual(packet,PhoneEmoteObservation.failure_archive(packet,effects,3,POLICY))
            self.assertEqual(context,writer.read(writer.expand(reference)))

    def test_missing_or_foreign_boundary_never_creates_a_capture_or_ready_result(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();writer,reference=self.boundary(effects,context)
            wrong=deepcopy(reference);wrong['sha256']='9'*64
            scope=self.image_scope(effects);reads=m.calls.count('native-read')
            with self.assertRaises((NativeUIError,FileNotFoundError)):scope.read_background(call['ticket'],wrong)
            self.assertIsNone(scope.store.read());self.assertEqual(reads,m.calls.count('native-read'))
            self.assertEqual(context,writer.read(writer.expand(reference)))

    def test_expectation_bearing_boundary_is_rejected_before_native_acquisition(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();writer,_reference=self.boundary(effects,context)
            reference=writer.write(2,context|dict(expectedState=dict(animation='idle')))
            scope=self.image_scope(effects);reads=m.calls.count('native-read')
            with self.assertRaises(NativeUIError):scope.read_background(call['ticket'],reference)
            self.assertIsNone(scope.store.read());self.assertEqual(reads,m.calls.count('native-read'))

    def test_completed_background_archive_replays_after_a_later_input_without_new_measurements(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();_writer,reference=self.boundary(effects,context)
            scope=self.image_scope(effects);value=scope.read_background(call['ticket'],reference)
            packet=scope.transfer(lambda *_:None);m.call('close');effects.source.read();calls=deepcopy(m.calls)
            self.assertEqual(value,PhoneEmoteObservation.archive(packet,effects,3,POLICY))
            self.assertEqual(calls,m.calls);self.assertIsNone(scope.store.read())

    def test_phase_change_after_the_image_preserves_an_incomplete_v3_archive_not_a_result(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();writer,reference=self.boundary(effects,context)
            scope=self.image_scope(effects);read=effects.source.read;reads=[]
            def changed_after_image():
                reads.append(True)
                if len(reads)==2:m.call('close')
                return read()
            with patch.object(effects.source,'read',side_effect=changed_after_image),self.assertRaises(NativeUIError):
                scope.read_background(call['ticket'],reference)
            self.assertEqual('measuring',scope.state['phase']);packets=[]
            packet=scope.transfer_incomplete(lambda value:packets.append(deepcopy(value)))
            self.assertEqual([packet],packets);self.assertNotIn('result',packet)
            self.assertEqual(packet,PhoneEmoteObservation.incomplete_archive(packet,effects,3,POLICY))
            self.assertIsNone(scope.store.read());self.assertEqual(context,writer.read(writer.expand(reference)))

    def test_missing_boundary_blocks_ready_replay_and_metadata_retirement(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();writer,reference=self.boundary(effects,context)
            scope=self.image_scope(effects);scope.read_background(call['ticket'],reference)
            writer.path(writer.expand(reference)).unlink();retained=[]
            with self.assertRaises(FileNotFoundError):scope.original()
            with self.assertRaises(FileNotFoundError):scope.transfer(lambda value:retained.append(value))
            self.assertEqual([],retained);self.assertIsNotNone(scope.store.read())

    def test_ignored_native_release_keeps_failed_background_scope_until_actual_cleanup(self):
        m=self.model
        with m.lock.held():
            effects,context,call=self.prepare();_writer,reference=self.boundary(effects,context)
            scope=self.image_scope(effects);m.world.storage.ignore_release=True;captures=m.world.counters['capture']
            with self.assertRaises(NativeUIError):scope.read_background(call['ticket'],reference)
            with self.assertRaises(NativeUIError):scope.transfer_failed(lambda *_:None)
            self.assertIsNotNone(scope.store.read());self.assertEqual(captures+1,m.world.counters['capture'])
            m.world.storage.ignore_release=False;packet=scope.transfer_failed(lambda *_:None)
            self.assertEqual(packet,PhoneEmoteObservation.failure_archive(packet,effects,3,POLICY))
            self.assertEqual(captures+1,m.world.counters['capture']);self.assertIsNone(scope.store.read())


if __name__=='__main__':unittest.main()
