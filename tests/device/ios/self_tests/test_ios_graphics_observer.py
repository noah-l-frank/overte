"""Independent original Graphics role evidence and pixels on synthetic iOS SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION
from feature_journeys.witness import Client
from ios.adapters.graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending
from ios.adapters.graphics_observer import IOSGraphicsObserver,GraphicsEffectReferencePending
from adapters.script_feature.history import pack,unpack
from ios.adapters.graphics_preferences import IOSGraphicsPreferences
from ios.adapters.graphics_samples import IOSGraphicsSamples
from ios.self_tests.test_ios_graphics_samples import SamplesHarness,POLICY
from ios.self_tests.test_ios_graphics_scene import RUN,TICKET
from ios.self_tests.test_ios_graphics_restart import RestartHarness


class ObserverHarness(SamplesHarness):
    def setUp(self):
        super().setUp()
        self.adapter._graphics_samples=lambda selector,client,run,role,stage,lock,root,policy:IOSGraphicsSamples(
            self.adapter,selector,client,run,role,stage,lock,root,policy,epoch_ms=self.sdk.host_epoch,monotonic=lambda:self.sdk.clock)
        self.actor_client=Client(self.client.url,self.server.actor_token)
    def observer(self,role='primary'):
        source=GraphicsFixtureReader(self.actor_client if role=='actor' else self.client,RUN,epoch_ms=self.sdk.host_epoch)
        return IOSGraphicsObserver(self.adapter,'owned',source,role,self.lock,self.root/'pixels',POLICY,
            monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def preferences(self):
        scene=self.scene();return IOSGraphicsPreferences(scene,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def prepare(self):
        self.scene().prepare();self.preferences().prepare()
    def action(self,verb,inputs=None):
        self.counter=getattr(self,'counter',100)+1;ticket=format(self.counter,'032x');self.client.activate(ticket,verb,inputs or {});self.gpu.marker=ticket
        call=dict(contractVersion=VERSION,runId=RUN,ticket=ticket,fixtureUrl=self.client.url+'/runs/'+RUN+'/',verb=verb,inputs=inputs or {})
        self.preferences().act(call);return ticket


class ObserverTests(ObserverHarness,unittest.TestCase):
    def test_separate_role_originals_and_actor_publication_never_forward_primary_normalized_state(self):
        with self.lock.held():
            self.prepare();primary=self.observer();a=primary.read(0,0);actor=self.observer('actor');sequence=actor.publish(0,0)
            self.assertEqual(1,sequence);self.assertEqual(a['state'],actor.frame(actor.state['last'],actor.state['binding'])[2]['state'])
            self.assertNotEqual(primary.state['last']['requestId'],actor.state['last']['requestId'])
            self.assertNotEqual(primary.frame(primary.state['last'],primary.state['binding'])[0]['capture']['source']['renderTrace']['frameId'],
                actor.frame(actor.state['last'],actor.state['binding'])[0]['capture']['source']['renderTrace']['frameId'])
            self.assertEqual('owned-observer',self.client.observe()['entries'][-1]['actor'])
            public=a['artifacts'][0];self.assertEqual(a['capturedEpochMs'],public['capturedEpochMs'])
            self.assertLess(public['capturedEpochMs'],primary.frame(primary.state['last'],primary.state['binding'])[0]['capture']['capturedEpochMs'])

    def test_original_haze_and_mirror_pixels_are_compared_outside_the_current_challenge(self):
        with self.lock.held():
            self.prepare();observer=self.observer();observer.read(0,0);self.action('open');observer=self.observer();observer.read(0,0)
            for verb in ('set-haze','set-mirrors'):
                self.action(verb,dict(enabled=False));self.observer().read(0,0)
                self.action(verb,dict(enabled=True));actual=self.observer().read(0,0)
                self.assertTrue(actual['state']['haze' if verb=='set-haze' else 'mirror'])
            observer=self.observer();self.assertEqual({'haze','mirror'},{row['feature'] for row in observer.state['effects']})
            self.assertTrue(all(row['observed']['changedFraction']>=.05 for row in observer.state['effects']))

    def test_changed_settings_draws_and_challenge_without_effect_pixels_do_not_succeed(self):
        with self.lock.held():
            self.prepare();self.observer().read(0,0);self.action('open');self.observer().read(0,0)
            self.action('set-haze',dict(enabled=False));self.observer().read(0,0)
            self.gpu.effects=False;self.action('set-haze',dict(enabled=True))
            with self.assertRaises(NativeUIError):self.observer().read(0,0)

    def test_recreation_uses_new_frame_and_old_reference_remains_historical(self):
        with self.lock.held():
            self.prepare();old=self.observer();first=old.read(0,0);reference=deepcopy(old.state['last'])
            self.sdk.sleep(.25);current=self.observer();second=current.read(1,0)
            self.assertGreater(second['capturedEpochMs'],first['capturedEpochMs']);self.assertEqual(2,second['sequence'])
            self.assertNotEqual(reference['requestId'],current.state['last']['requestId'])
            historical=current.frame(reference,current.state['binding'])[2]
            self.assertEqual(first['capturedEpochMs'],historical['capturedEpochMs'])

    def test_late_pixel_validation_cannot_mint_a_fresh_public_envelope(self):
        with self.lock.held():
            self.prepare();observer=self.observer();original=observer.frame
            def slow(*args):
                value=original(*args);self.sdk.sleep(1.6);return value
            with patch.object(observer,'frame',side_effect=slow),self.assertRaises(NativeUIError):observer.read(0,0)

    def test_changed_frame_archive_or_png_is_rejected_without_a_native_read(self):
        with self.lock.held():
            self.prepare();observer=self.observer();observer.read(0,0);ref=observer.state['last'];native=len(self.gpu.commands)
            frame,raw,_actual,name=observer.frame(ref,observer.state['binding']);self.assertEqual(native,len(self.gpu.commands))
            (self.root/'pixels'/name).write_bytes(b'foreign PNG')
            with self.assertRaises(NativeUIError):self.observer()
            self.assertEqual(native,len(self.gpu.commands))

    def test_phase_crossing_retires_unknown_capture_without_publishing_or_replaying_it(self):
        with self.lock.held():
            self.prepare();self.observer().read(0,0);observer=self.observer()
            self.gpu.on_read=lambda:self.client.activate('7'*32,'open',{})
            with self.assertRaises(GraphicsPhasePending):observer.read(0,0)
            self.assertEqual('reading',observer.state['phase']);count=sum(row['operation']=='read' for row in self.gpu.commands)
            recovery=self.observer();recovery.retire_phase();self.assertEqual(1,len(recovery.state['retirements']))
            self.assertEqual(count,sum(row['operation']=='read' for row in self.gpu.commands))
            self.gpu.on_read=None;self.gpu.marker='7'*32
            self.assertEqual(2,self.observer().read(0,0)['sequence'])

    def test_same_phase_cannot_reset_a_lost_native_capture(self):
        with self.lock.held():
            self.prepare();self.observer().read(0,0);observer=self.observer();self.gpu.lost=True
            with self.assertRaises(NativeUIError):observer.read(0,0)
            with self.assertRaises(NativeUIError):self.observer().retire_phase()
            self.assertEqual(2,sum(row['operation']=='read' for row in self.gpu.commands))

    def test_failed_effect_keeps_original_files_and_can_retire_only_under_a_later_cleanup_phase(self):
        with self.lock.held():
            self.prepare();self.observer().read(0,0);self.action('open');self.observer().read(0,0)
            self.action('set-haze',dict(enabled=False));self.observer().read(0,0)
            self.gpu.effects=False;self.action('set-haze',dict(enabled=True))
            with self.assertRaises(NativeUIError):self.observer().read(0,0)
            self.client.activate('f'*32,'cleanup',{});self.gpu.marker='f'*32;self.preferences().cleanup()
            observer=self.observer();observer.retire_phase();value=self.observer().read(0,0)
            self.assertFalse(value['state']['haze']);self.assertFalse(value['state']['dialog']);self.assertEqual([],value['resources'])

    def test_enable_phase_early_read_does_not_replace_the_previous_actual_off_frame(self):
        with self.lock.held():
            self.prepare();self.observer().read(0,0);self.action('open');before=self.observer();before.read(0,0)
            ref=deepcopy(before.state['offFrames']['haze']);ticket='6'*32
            self.client.activate(ticket,'set-haze',dict(enabled=True));self.gpu.marker=ticket
            early=self.observer();value=early.read(0,0);self.assertFalse(value['state']['haze']);self.assertEqual(ref,early.state['offFrames']['haze'])
            self.preferences().act(dict(contractVersion=VERSION,runId=RUN,ticket=ticket,verb='set-haze',inputs=dict(enabled=True),fixtureUrl=self.client.url+'/runs/'+RUN+'/'))
            actual=self.observer().read(0,0);self.assertTrue(actual['state']['hazePass'])

    def test_effect_readiness_acquires_new_original_frames_without_repeating_the_setting_input(self):
        with self.lock.held():
            self.prepare();self.observer().read(0,0);self.action('open');self.observer().read(0,0)
            self.action('set-haze',dict(enabled=False));self.observer().read(0,0)
            self.gpu.effects=False;self.action('set-haze',dict(enabled=True));count=sum(c['operation']=='read' for c in self.gpu.commands)
            self.gpu.on_read=lambda:setattr(self.gpu,'effects',True)
            value=self.observer().read(0,0);self.assertTrue(value['state']['hazePass'])
            self.assertEqual(count+2,sum(c['operation']=='read' for c in self.gpu.commands))
            self.assertEqual(1,self.sdk.model.actions.count('graphics.haze'))

    def test_lost_phase_retirement_metadata_return_recovers_from_immutable_record_without_capture(self):
        with self.lock.held():
            self.prepare();self.observer().read(0,0);observer=self.observer()
            self.gpu.on_read=lambda:self.client.activate('7'*32,'open',{})
            with self.assertRaises(GraphicsPhasePending):observer.read(0,0)
            observer=self.observer();count=sum(c['operation']=='read' for c in self.gpu.commands)
            with patch.object(observer.store,'write',side_effect=OSError('Synthetic lost retirement metadata write')),self.assertRaises(OSError):observer.retire_phase()
            recovery=self.observer();recovery.retire_phase();self.assertEqual('ready',recovery.state['phase'])
            self.assertEqual(count,sum(c['operation']=='read' for c in self.gpu.commands))


class ObserverRestartTests(ObserverHarness,RestartHarness,unittest.TestCase):
    def test_each_role_acquires_new_originals_and_its_own_old_pid_absence_after_restart(self):
        with self.lock.held():
            ObserverHarness.prepare(self)
            self.observer().read(0,0);self.observer('actor').publish(0,0)
            controller=RestartHarness.prepare(self);self.gpu.marker='8'*32
            self.observer().read(0,0);self.observer('actor').publish(0,0)
            controller.act(RestartHarness.call(self))
            primary=self.observer();value=primary.read(0,1)
            actor=self.observer('actor');actor.publish(0,1)
            self.assertEqual(1,primary.state['stage']);self.assertEqual(1,actor.state['stage'])
            self.assertEqual(.5,value['state']['resolution']);self.assertEqual(.6,primary.baseline()['resolution'])
            self.assertNotEqual(primary.state['restart']['exit']['commandId'],actor.state['restart']['exit']['commandId'])
            self.assertEqual('ESRCH',primary.state['restart']['exit']['errorSymbol'])
            self.assertEqual('42',primary.state['restart']['oldBinding']['processIdentity'])
            self.assertEqual('43',primary.state['restart']['newBinding']['processIdentity'])

    def test_stage_change_without_a_new_actual_pid_is_rejected_before_another_capture(self):
        with self.lock.held():
            self.prepare();observer=self.observer();observer.read(0,0);native=len(self.gpu.commands)
            with self.assertRaises(NativeUIError):observer.read(0,1)
            self.assertEqual(native,len(self.gpu.commands))


class CurrentObserverHarness(ObserverHarness):
    def private_action(self,verb,inputs=None):
        self.counter=getattr(self,'counter',1000)+1
        self.preferences().act(dict(contractVersion=VERSION,runId=RUN,ticket=format(self.counter,'032x'),
            fixtureUrl=self.client.url+'/runs/'+RUN+'/',verb=verb,inputs=inputs or {}))
    def original_true(self):
        self.sdk.model.haze=self.sdk.model.mirrors=True
        ObserverHarness.prepare(self)
    def off_references(self,roles=('primary',)):
        self.private_action('open');self.private_action('set-haze',dict(enabled=False))
        self.private_action('set-mirrors',dict(enabled=False))
        refs={role:self.observer(role).seed_off(['haze','mirror'],0) for role in roles}
        self.private_action('restore-original');self.private_action('close')
        return refs


class CurrentObserverTests(CurrentObserverHarness,unittest.TestCase):
    def test_initially_enabled_effect_requires_actual_off_originals_before_any_capture_or_public_sequence(self):
        with self.lock.held():
            self.original_true();observer=self.observer();count=len(self.gpu.commands)
            with self.assertRaises(GraphicsEffectReferencePending):observer.read(0,0)
            self.assertEqual(count,len(self.gpu.commands));self.assertEqual('ready',observer.state['phase'])
            self.assertEqual(0,observer.state['sequence']);self.assertIsNone(observer.state['baseline'])

    def test_private_normal_calibration_keeps_actual_true_baseline_and_independent_actor_images(self):
        with self.lock.held():
            self.original_true();refs=self.off_references(('primary','actor'))
            self.assertNotEqual(refs['primary'],refs['actor'])
            self.assertEqual(TICKET,self.client.request('/runs/'+RUN+'/active')['ticket'])
            primary=self.observer();value=primary.read(0,0);actor=self.observer('actor');actor.publish(0,0)
            self.assertTrue(value['state']['haze']);self.assertTrue(value['state']['mirror'])
            self.assertEqual(1,value['sequence']);self.assertTrue(primary.baseline()['haze'])
            self.assertEqual({'haze','mirror'},{row['feature'] for row in primary.state['currentEffects']})
            self.assertEqual(refs['primary'],primary.state['offFrames'])
            self.assertNotEqual(primary.state['last'],actor.state['last'])

    def test_true_baseline_with_settings_and_draws_but_without_pixels_never_qualifies(self):
        with self.lock.held():
            self.original_true();refs=self.off_references();self.gpu.effects=False
            with self.assertRaises(NativeUIError):self.observer().read(0,0)
            observer=self.observer();self.assertIsNone(observer.state['baseline']);self.assertEqual(0,observer.state['sequence'])
            self.assertEqual(refs['primary'],observer.state['offFrames']);self.assertEqual('reading',observer.state['phase'])

    def test_non_enable_resolution_phase_still_requires_both_enabled_effect_pixels(self):
        with self.lock.held():
            self.original_true();self.off_references();self.observer().read(0,0)
            self.action('open');self.action('set-resolution',dict(value=.5));self.gpu.effects=False
            with self.assertRaises(NativeUIError):self.observer().read(0,0)
            self.assertEqual(1,self.observer().state['sequence'])

    def test_expired_off_reference_does_not_capture_or_reset_sequence_or_original_clocks(self):
        with self.lock.held():
            self.original_true();self.off_references();observer=self.observer();observer.read(0,0)
            refs=deepcopy(observer.state['offFrames']);before=observer.frame(refs['haze'],observer.state['binding'])[0]
            count=len(self.gpu.commands);self.sdk.sleep(46)
            with self.assertRaises(GraphicsEffectReferencePending):self.observer().read(0,0)
            current=self.observer();self.assertEqual(count,len(self.gpu.commands));self.assertEqual(1,current.state['sequence'])
            self.assertEqual(before,current.frame(refs['haze'],current.state['binding'])[0]);self.assertEqual('ready',current.state['phase'])

    def test_missing_last_current_pixel_proof_is_rejected_from_private_history(self):
        with self.lock.held():
            self.original_true();self.off_references();observer=self.observer();observer.read(0,0)
            changed=deepcopy(observer.previous);state=unpack(changed['payload'])[0];state['currentEffects']=[]
            changed['payload']=pack([state]);observer.store.write(changed,observer.previous)
            count=len(self.gpu.commands)
            with self.assertRaises(NativeUIError):self.observer()
            self.assertEqual(count,len(self.gpu.commands))

    def test_lost_private_reference_capture_is_not_repeated_and_retires_only_after_phase_change(self):
        with self.lock.held():
            self.original_true();self.private_action('open');self.private_action('set-haze',dict(enabled=False))
            observer=self.observer();self.gpu.lost=True
            with self.assertRaises(NativeUIError):observer.seed_off(['haze'],0)
            count=sum(c['operation']=='read' for c in self.gpu.commands)
            with self.assertRaises(NativeUIError):self.observer().seed_off(['haze'],0)
            with self.assertRaises(NativeUIError):self.observer().retire_phase()
            self.gpu.lost=False;self.client.activate('f'*32,'cleanup',{});self.gpu.marker='f'*32
            observer=self.observer();observer.retire_phase()
            self.assertEqual(count,sum(c['operation']=='read' for c in self.gpu.commands))
            self.assertIsNone(observer.state['offFrames']['haze']);self.assertEqual(0,observer.state['sequence'])

    def test_legacy_readable_history_keeps_original_native_floor_on_first_v2_passive_read(self):
        with self.lock.held():
            self.prepare();observer=self.observer();observer.read(0,0)
            floor=observer.frame(observer.state['last'],observer.state['binding'])[0]['clockJoin']['nativeAfter']
            value=deepcopy(observer.previous);value['iosGraphicsObserverVersion']=1;state=unpack(value['payload'])[0]
            for key in ('currentEffects','currentEffectsAfter','nativeFloor'):state.pop(key)
            value['payload']=pack([state]);observer.store.write(value,observer.previous)
            migrated=self.observer();self.assertEqual(floor,migrated.accepted_native())
            migrated.effect_preflight(0)
            self.assertGreater(migrated.state['nativeFloor']['sequence'],floor['sequence'])
            self.assertEqual(1,migrated.state['sequence']);self.assertEqual(1,migrated.state['currentEffectsAfter'])


class CurrentObserverRestartTests(CurrentObserverHarness,RestartHarness,unittest.TestCase):
    def test_enabled_effects_after_real_restart_use_original_old_role_refs_and_strict_receipt(self):
        with self.lock.held():
            self.original_true();refs=self.off_references(('primary','actor'))
            self.observer().read(0,0);self.observer('actor').publish(0,0)
            controller=RestartHarness.prepare(self);self.gpu.marker='8'*32
            self.observer().read(0,0);self.observer('actor').publish(0,0)
            controller.act(RestartHarness.call(self))
            for role in ('primary','actor'):
                observer=self.observer(role);value=observer.read(0,1)
                self.assertTrue(value['state']['haze']);self.assertTrue(value['state']['mirror'])
                self.assertEqual(refs[role],observer.state['offFrames'])
                current=[row for row in observer.state['currentEffects'] if row['stage']==1]
                self.assertEqual(2,len(current));self.assertTrue(all(row['observed']['restartSha256'] for row in current))
                self.assertEqual('ESRCH',observer.state['restart']['exit']['errorSymbol'])
            self.assertEqual(['app.stop','app.launch'],self.inputs)


if __name__=='__main__':unittest.main()
