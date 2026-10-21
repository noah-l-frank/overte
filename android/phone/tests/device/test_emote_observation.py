"""Original input/source/image joins over synthetic IO, never product acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from PIL import Image
from adapters.native_phone_avatar_configuration import NativePhoneAvatarConfiguration
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import marker_bytes
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_effects import PhoneEmoteEffects
from overte_phone_emote_capture import PhoneEmoteCapture
from overte_phone_emote_observation import PhoneEmoteObservation
from test_emote_capture import Model as CaptureModel
from test_emote_pixels import POLICY
from test_emote_sources import RUN
from self_tests.test_native_phone_avatar_configuration import Boundary as ConfigurationBoundary
from test_emote_source_profile import included_source,included_caller


class Model(CaptureModel):
    def __init__(self,root):
        super().__init__(root);self.configuration=ConfigurationBoundary().configuration
        self.configuration['rigId']=2;self.config_sequence=0;self.image_fault=None;self.on_capture=None
        self.retained=[]

    def _avatar_configuration_observer(self,_selector,*,read_only):
        assert read_only;box={}
        def send(request):
            self.config_sequence+=1
            box['value']=dict(schemaVersion=1,requestId=request['commandId'],instance='a'*32,sequence=self.config_sequence,
                processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=deepcopy(self.configuration))
        return NativePhoneAvatarConfiguration(send,lambda:json.dumps(box['value']),lambda:self.epoch,lambda:self.okay,31,**self.options())

    def world_send(self,key,request):
        phase=self.journal.phase(RUN,'1'*32);ticket=phase['activations'][-1]['ticket']
        raw=self.pixel.paint(self.pixel.first,changed=self.actual_name is not None and self.image_fault!='frozen')
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            with Image.open(io.BytesIO(marker_bytes(RUN,'e'*32 if self.image_fault=='foreign-marker' else ticket))) as card:image.paste(card,(10,10))
            output=io.BytesIO();image.save(output,format='PNG');self.png=output.getvalue()
            self.pixel_sha=hashlib.sha256(image.tobytes()).hexdigest()
        self.world.storage.raw=self.png
        super().world_send(key,request)
        if self.on_capture is not None:self.on_capture()

    def scope(self,owner,index,*,role='primary'):
        self.current_index=index
        source=owner.source if role=='primary' else self.source(role)
        effect=PhoneEmoteEffects(owner,current_source=source)
        return PhoneEmoteObservation(effect,index,POLICY)


class EmoteObservationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-observation-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name))
        mock=patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=self.model.tablet);mock.start();self.addCleanup(mock.stop)

    def act(self,verb,inputs=None):
        m=self.model;call=m.call(verb,inputs);owner=PhoneEmoteInputs(m.source());owner.act(call)
        return owner,call

    def test_one_fresh_loaded_source_on_each_side_of_image_preserves_two_original_advancing_pose_frames(self):
        m=self.model;m.use_included_source()
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);prior=len(owner.source.frames)
            value=scope.read(call['ticket']);self.assertEqual(2,len(owner.source.frames)-prior)
            proof=value['effect']['proof'];self.assertEqual(2,len(proof['frameSequences']))
            captured=scope.load('capture');outcome=scope.load('outcome')
            before=scope.effects.current_original(captured['before'])['group']['native']
            after=scope.effects.current_original(outcome['after'])['group']['native']
            self.assertLess(before['animation']['evaluationSequence'],after['animation']['evaluationSequence'])
            self.assertEqual(before['animation']['clip']['assetSource'],after['animation']['clip']['assetSource'])

    def test_two_fresh_sources_with_advancing_clip_but_frozen_actual_pose_cannot_use_moving_image_as_success(self):
        m=self.model;m.use_included_source();m.frozen_rig=True
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertIsNotNone(scope.store.read());self.assertNotEqual('complete',scope.state['phase'])
            self.assertEqual(1,m.world.counters['capture'])

    def test_historical_image_replay_recomputes_derived_effect_state_and_proof_from_originals(self):
        m=self.model;m.use_included_source()
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);value=scope.read(call['ticket'])
            load=scope.load;calls=deepcopy(m.calls)
            for fault in ('animation','sit','pose','panel','early','kind','caller'):
                def changed(kind):
                    result=load(kind)
                    if kind=='outcome':
                        effect=result['effect'];state=effect['state']
                        if fault=='animation':state['animation']='Crying'
                        elif fault=='sit':state['sit']='Sit2'
                        elif fault=='pose':state['poseProgress']=0.
                        elif fault=='panel':state['panel']=not state['panel']
                        elif fault=='early':state['restoredBeforeNominalEnd']=True
                        elif fault=='kind':effect['kind']='expected'
                        else:effect['proof']['event']['caller']['compilation']['scriptId']=11
                    return result
                with self.subTest(fault=fault),patch.object(scope,'load',side_effect=changed),self.assertRaises(NativeUIError):scope.original()
            self.assertEqual(value,scope.original());self.assertEqual(calls,m.calls)

    def test_open_play_and_restore_join_current_original_pixels_to_stable_native_intervals(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('open');first=m.scope(owner,1);baseline=first.read(call['ticket'])
            self.assertFalse(baseline['state']['override']);self.assertEqual('primary',baseline['role'])
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,2)
            value=scope.read(call['ticket'],previous=first)
            self.assertEqual('Waving',value['state']['animation']);self.assertGreater(value['pixels']['bodyChangedFraction'],.05)
            self.assertFalse(scope.source.store.path.with_name('phone-emote-primary-capture-2.json').exists())
            play=value['effect']['playbackReference'];m.epoch+=2100;m.restore()
            owner,call=self.act('wait-complete');restored=m.scope(owner,3)
            value=restored.read(call['ticket'],played=play,previous=scope)
            self.assertFalse(value['state']['override']);self.assertGreater(value['pixels']['bodyChangedFraction'],.05)
            restored.retire(lambda proof:m.retained.append(deepcopy(proof)))
            self.assertIsNone(restored.store.read());self.assertEqual(1,len(m.retained))
            self.assertTrue(list(m.root.glob('emote-frame-observations-*.json')))

    def test_actor_acquires_its_own_png_and_rig_after_one_primary_input(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));before=len(m.controls.input_requests)
            primary=m.scope(owner,1);a=primary.read(call['ticket'])
            actor=m.scope(owner,1,role='actor');b=actor.read(call['ticket'])
            self.assertEqual('primary',a['role']);self.assertEqual('actor',b['role'])
            self.assertNotEqual(a['image']['payload'],b['image']['payload'])
            self.assertNotEqual(a['capture'],b['capture']);self.assertEqual(a['state'],b['state'])
            self.assertEqual(before,len(m.controls.input_requests));self.assertEqual(2,m.world.counters['capture'])

    def test_restore_between_original_image_and_postimage_source_cannot_publish_active_success(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            m.on_capture=m.restore
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertNotEqual('complete',scope.state['phase'])
            self.assertIsNotNone(scope.store.read());self.assertEqual(1,m.world.counters['capture'])
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertEqual(1,m.world.counters['capture'])

    def test_frozen_pixels_and_foreign_marker_do_not_use_correct_loaded_animation_as_image_success(self):
        for fault in ('frozen','foreign-marker'):
            temporary=tempfile.TemporaryDirectory(prefix='overte-emote-observation-fault-');self.addCleanup(temporary.cleanup)
            m=Model(Path(temporary.name));self.model=m
            with self.subTest(fault=fault),patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=m.tablet),m.lock.held():
                owner,call=self.act('open');first=m.scope(owner,1);first.read(call['ticket'])
                owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,2);m.image_fault=fault
                with self.assertRaises((NativeUIError,AssertionError)):scope.read(call['ticket'],previous=first)
                self.assertIsNotNone(scope.store.read());self.assertNotEqual('complete',scope.state['phase'])

    def test_external_loaded_resource_cannot_supply_controlled_image(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            m.configuration['loadedGeometry']['source']['bundledResource']=None
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertNotEqual('complete',scope.state['phase'])

    def test_parent_original_precedes_child_cleanup_and_source_advancement(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);cleanup=PhoneEmoteCapture.cleanup
            def checked(child):
                row=scope.load('capture');self.assertEqual(child.previous,row['header'])
                self.assertEqual(child.source_header,child.source.previous)
                return cleanup(child)
            with patch.object(PhoneEmoteCapture,'cleanup',checked):scope.read(call['ticket'])

    def test_lost_child_cleanup_return_preserves_parent_original_and_forbids_reacquisition(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);cleanup=PhoneEmoteCapture.cleanup
            def lost(child):cleanup(child);raise NativeUIError('Synthetic lost child cleanup return')
            with patch.object(PhoneEmoteCapture,'cleanup',lost),self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertIsNotNone(scope.state['capture']);self.assertIsNone(scope.state['retirement'])
            self.assertEqual('captured',scope.state['phase'])
            reconstructed=m.scope(PhoneEmoteInputs(m.source()),1)
            with self.assertRaises(NativeUIError):reconstructed.read(call['ticket'])
            with self.assertRaises(NativeUIError):reconstructed.retire(lambda *_:None)
            self.assertEqual(1,m.world.counters['capture']);self.assertIsNotNone(reconstructed.store.read())

    def test_missing_or_replaced_parent_original_and_png_prevent_retirement(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);scope.read(call['ticket'])
            ref=scope.state['capture'];path=scope.originals.path(scope.originals.expand(ref));raw=path.read_bytes()
            replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
            with self.assertRaises(NativeUIError):scope.retire(lambda *_:None)
            self.assertIsNotNone(scope.store.read())

    def test_failed_parent_retention_and_changed_candidate_keep_scope_responsibility(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);scope.read(call['ticket'])
            with self.assertRaises(NativeUIError):scope.retire(lambda *_:False)
            self.assertIsNotNone(scope.store.read())
            def changed(_proof):m.okay=False
            with self.assertRaises(NativeUIError):scope.retire(changed)
            self.assertIsNotNone(scope.store.read())

    def test_final_frozen_epoch_with_slow_parent_copy_or_guard_never_delivers_fresh_result(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);original=scope.original
            def slow():
                value=original();m.clock+=2;return value
            scope.original=slow
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertEqual('complete',scope.state['phase']) # Historical only.
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])

    def test_same_clip_restarted_during_capture_is_a_different_override(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            m.on_capture=lambda:m.start('Waving')
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertNotEqual('complete',scope.state['phase'])

    def test_changed_lifecycle_during_capture_cannot_be_hidden_by_same_loaded_clip(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            original=m.native_send
            def changed(request):
                original(request)
                if m.world.counters['capture']:m.value['lifecycle']['backgrounds']+=1
            m.native_send=changed
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertNotEqual('complete',scope.state['phase'])

    def test_phase_change_during_capture_keeps_originals_and_never_publishes_old_ticket(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            m.on_capture=lambda:m.call('close')
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertIsNotNone(scope.store.read());self.assertNotEqual('complete',scope.state['phase'])

    def test_actor_cannot_compare_primary_checkpoint_pixels(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('open');first=m.scope(owner,1);first.read(call['ticket'])
            owner,call=self.act('play',dict(name='Waving'));actor=m.scope(owner,2,role='actor')
            with self.assertRaises(NativeUIError):actor.read(call['ticket'],previous=first)
            self.assertEqual(1,m.world.counters['capture'])

    def test_missing_png_does_not_retire_an_original_result_from_memory(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);scope.read(call['ticket'])
            captured=scope.load('capture');header=captured['header']
            from overte_phone_script_history import unpack
            (m.root/unpack(header['payload'])[0]['image']['name']).unlink()
            with self.assertRaises((OSError,NativeUIError)):scope.retire(lambda *_:None)
            self.assertIsNotNone(scope.store.read())

    def test_final_retention_timeout_preserves_scope(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);scope.read(call['ticket'])
            def delayed(_proof):m.clock+=6
            with self.assertRaises(NativeUIError):scope.retire(delayed)
            self.assertIsNotNone(scope.store.read())

    def test_source_header_advancement_does_not_refresh_or_break_retained_capture_archive(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);value=scope.read(call['ticket'])
            captures=m.world.counters['capture'];m.epoch+=10000;owner.source.read()
            self.assertEqual(value,scope.original());self.assertEqual(captures,m.world.counters['capture'])
            scope.retire(lambda proof:m.retained.append(proof));self.assertIsNone(scope.store.read())

    def test_failed_parent_original_write_keeps_actual_child_and_pending_file_responsibility(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1);intent=scope.originals.intent
            def failed(kind,value):
                result=intent(kind,value)
                if value['phase']=='opened':raise NativeUIError('Synthetic parent evidence write failure')
                return result
            scope.originals.intent=failed
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertIsNotNone(scope.state['pending']);self.assertEqual('opened',scope.state['pending']['original']['phase'])
            self.assertTrue(m.root.joinpath('phone-emote-primary-capture-1.json').exists())
            reconstructed=m.scope(PhoneEmoteInputs(m.source()),1)
            with self.assertRaises(NativeUIError):reconstructed.read(call['ticket'])
            with self.assertRaises(NativeUIError):reconstructed.retire(lambda *_:None)
            self.assertEqual(1,m.world.counters['capture'])

    def test_undrained_native_buffer_or_callback_keeps_both_observation_and_capture_unresolved(self):
        m=self.model
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            m.world.storage.callbacks=1
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertEqual('capturing',scope.state['phase']);self.assertIsNotNone(scope.store.read())
            self.assertTrue(m.root.joinpath('phone-emote-primary-capture-1.json').exists())
            with self.assertRaises(NativeUIError):scope.retire(lambda *_:None)

    def test_shared_default_vm_normal_input_and_original_image_brackets_compose_for_both_roles(self):
        m=self.model;m.use_included_source()
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));primary=m.scope(owner,1)
            value=primary.read(call['ticket']);actor=m.scope(owner,1,role='actor');remote=actor.read(call['ticket'])
            self.assertEqual('Waving',value['state']['animation']);self.assertEqual(value['state'],remote['state'])
            self.assertEqual(23,remote['effect']['proof']['event']['caller']['compilation']['scriptId'])
            self.assertEqual(2,m.world.counters['capture'])

    def test_visible_moving_avatar_and_correct_loaded_url_cannot_hide_wrong_consumed_animation_bytes(self):
        m=self.model;m.use_included_source();m.actual_asset_name='Cheering'
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertIsNotNone(scope.store.read());self.assertNotEqual('complete',scope.state['phase'])
            self.assertEqual(1,m.world.counters['capture'])
            with self.assertRaises(NativeUIError):scope.retire(lambda *_:None)

    def test_changed_consumed_resource_across_original_image_bracket_cannot_publish(self):
        m=self.model;m.use_included_source()
        with m.lock.held():
            owner,call=self.act('play',dict(name='Waving'));scope=m.scope(owner,1)
            m.on_capture=lambda:setattr(m,'actual_asset_name','Cheering')
            with self.assertRaises(NativeUIError):scope.read(call['ticket'])
            self.assertIsNotNone(scope.store.read());self.assertNotEqual('complete',scope.state['phase'])


if __name__=='__main__':unittest.main()
