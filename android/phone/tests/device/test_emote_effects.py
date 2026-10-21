"""Real owned input/effect joins over explicit synthetic SDK/Qt/native sources."""
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
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_effects import PhoneEmoteEffects
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from test_emote_inputs import Originals
from test_emote_source_profile import included_source,included_caller
from test_native_animation_source import source_for_clip


class EffectsModel(Originals):
    def __init__(self,root):
        super().__init__(root);self.actual_name=None;self.events=[];self.actual_frames=[];self.generation=0;self.call_cursor=0
        self.ignore_native=False;self.foreign=False;self.compiled_assets=False;self.actual_asset_name=None
        original=self.widgets.activate
        def activate(identifier,*,token):
            original(identifier,token=token)
            if not identifier.startswith('emote.play.') or self.ignore_native:return
            name=identifier[len('emote.play.'):]
            if self.actual_name is not None and self.widgets.active=='':self.restore()
            else:self.start('Sit2' if name=='Sit' else name)
        self.widgets.activate=activate

    def use_included_source(self):
        observe=self.code.mutate;caller=self.caller;self.compiled_assets=True
        def included(value):observe(value);included_source(value,self.roots.root)
        self.code.mutate=included;self.caller=lambda kind,epoch:included_caller(caller(kind,epoch),self.roots.root)

    def _script_roots(self,*args,**kwargs):
        self.roots.epoch=self.epoch
        return super()._script_roots(*args,**kwargs)

    def event(self,kind):
        self.call_cursor+=1;caller=self.caller(kind,self.epoch);caller['sequence']=self.call_cursor
        if self.foreign:caller['manager']['instance']='8'*32
        event=dict(eventSequence=len(self.events)+1,kind=kind,overrideSequence=self.generation,capturedEpochMs=self.epoch,caller=caller)
        return event

    def start(self,name):
        self.actual_name=name;self.generation+=1;self.started_at=self.epoch
        self.actual_url=self.roots.root+'/system/assets/animations/'+name+'.fbx'
        event=self.event('override');event['request']=dict(url=self.actual_url,framesPerSecond=60.,loop=False,firstFrame=0.,lastFrame=120.)
        self.events.append(event)

    def restore(self):
        assert self.actual_name is not None
        self.actual_name=None;self.events.append(self.event('restore'));self.widgets.active=''

    def native_send(self,request):
        self.calls.append('native-read');self.epoch+=100;self.roots.epoch=self.epoch;self.sequence+=1
        frame=dict(frameSequence=self.sequence,overrideSequence=self.generation,evaluationSequence=self.sequence*10,
            capturedEpochMs=self.epoch,overrideActive=self.actual_name is not None,
            joints=[dict(index=0,pose=[0.,0.,0.,1.,.1+self.sequence*.01 if self.actual_name else .1,.2,.3])])
        if self.actual_name:
            frame['clip']=dict(self.events[-1]['request'],requestedUrl=self.actual_url,frame=min((self.epoch-self.started_at)*.06,120.),
                loadedFrames=120,evaluatedEpochMs=self.epoch,evaluationSequence=self.sequence)
            if self.compiled_assets:frame['clip'].update(animationSourceVersion=1,
                assetSource=source_for_clip(frame['clip'],consumed=self.started_at,actual_name=self.actual_asset_name))
        self.actual_frames.append(frame)
        history=dict(historyVersion=2,instance='e'*32,available=True,callSequence=len(self.events),overrideSequence=self.generation,
            frameSequence=self.sequence,droppedEvents=max(0,len(self.events)-64),droppedFrames=max(0,len(self.actual_frames)-32),
            events=deepcopy(self.events[-64:]),frames=deepcopy(self.actual_frames[-32:]))
        def observed(value):
            value.update(instance='a'*32,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,
                animationFence=dict(rigId=2,sequence=frame['evaluationSequence']-1,requestedEpochMs=self.epoch))
            value['animation'].update(rigId=2,capturedEpochMs=self.epoch,evaluationSequence=frame['evaluationSequence'],
                overrideActive=frame['overrideActive'],joints=[deepcopy(row['pose']) for row in frame['joints']],history=history)
            if 'clip' in frame:value['animation']['clip']=deepcopy(frame['clip'])
            else:value['animation'].pop('clip',None)
        native=NativeBoundary();native.sequence=self.sequence-1;native.mutate=observed;native.send(request);self.value=deepcopy(native.sample)


class PhoneEmoteEffectTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-effects-');self.addCleanup(temporary.cleanup)
        self.model=EffectsModel(Path(temporary.name));mock=patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=self.model.tablet)
        mock.start();self.addCleanup(mock.stop)

    def act(self,verb,inputs=None):
        m=self.model;call=m.call(verb,inputs);owner=PhoneEmoteInputs(m.source());owner.act(call)
        return owner,PhoneEmoteEffects(owner)

    def observe(self,owner,effect,played=None):
        owner.source.read();owner.source.read()
        return effect.measure(effect.reference(),played=played)

    def test_normal_open_loaded_play_automatic_restore_and_close_reconstruct_original_ownership(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('open');value=self.observe(owner,effect)
            self.assertTrue(value['state']['panel']);self.assertEqual('idle',value['state']['animation'])
            owner,effect=self.act('play',dict(name='Waving'));value=self.observe(owner,effect)
            self.assertEqual('Waving',value['state']['animation']);self.assertEqual(1.,value['state']['poseProgress'])
            play=value['playbackReference'];inputs=len(m.controls.input_requests)
            m.epoch+=2100;m.restore()
            owner,effect=self.act('wait-complete');value=self.observe(owner,effect,play)
            self.assertEqual('restoration',value['kind']);self.assertFalse(value['state']['override'])
            self.assertFalse(value['state']['restoredBeforeNominalEnd']);self.assertEqual(inputs,len(m.controls.input_requests))
            owner,effect=self.act('close');value=self.observe(owner,effect,play)
            self.assertFalse(value['state']['panel']);self.assertEqual('idle',value['state']['animation'])
            self.assertFalse(m.widgets.tablet)

    def test_all_ten_normal_emote_buttons_join_their_own_loaded_originals_and_restoration(self):
        m=self.model
        with m.lock.held():
            for name in ('Crying','Surprised','Dancing','Cheering','Waving','Fall','Pointing','Clapping','Sit','Love'):
                owner,effect=self.act('play',dict(name=name));value=self.observe(owner,effect);play=value['playbackReference']
                self.assertEqual(name,value['state']['animation']);self.assertTrue(value['state']['override'])
                self.assertEqual('Sit2' if name=='Sit' else 'none',value['state']['sit'])
                if name=='Sit':owner,effect=self.act('cancel')
                else:
                    m.epoch+=2100;m.restore();owner,effect=self.act('wait-complete')
                value=self.observe(owner,effect,play)
                self.assertFalse(value['state']['override']);self.assertEqual('idle',value['state']['animation'])
                self.assertEqual(name=='Sit',value['state']['restoredBeforeNominalEnd'])

    def test_actual_sit_variant_and_new_ordinary_early_cancel_are_independently_measured(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('sit');value=self.observe(owner,effect)
            self.assertEqual('Sit2',value['state']['sit']);play=value['playbackReference']
            owner,effect=self.act('cancel');value=self.observe(owner,effect,play)
            self.assertEqual('idle',value['state']['animation']);self.assertTrue(value['state']['restoredBeforeNominalEnd'])
            self.assertEqual('restoreAnimation',value['proof']['restore']['caller']['method'])

    def rejected_input_effect(self,*,foreign=False):
        m=self.model;m.foreign=foreign;m.ignore_native=not foreign
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));owner.source.read();owner.source.read()
            self.assertEqual('Waving',m.widgets.active)
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())

    def test_consumed_ignored_input_cannot_return_expected_success(self):self.rejected_input_effect()

    def test_loaded_foreign_same_clip_cannot_return_expected_success(self):self.rejected_input_effect(foreign=True)

    def test_loaded_different_animation_from_the_same_manager_is_not_the_delivered_button(self):
        m=self.model
        with m.lock.held():
            m.ignore_native=True;owner,effect=self.act('play',dict(name='Crying'));m.start('Waving')
            owner.source.read();owner.source.read()
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())

    def test_unacknowledged_or_previous_action_source_cannot_publish_a_current_effect(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));value=self.observe(owner,effect);old=effect.reference()
            owner.source.read()
            with self.assertRaises(NativeUIError):effect.measure(old)
            row=owner.state['current'];original=deepcopy(row);row['phase']='issuing';row['intents'][-1]['after']=None
            owner.save()
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())
            self.assertNotEqual(original,row)

    def test_old_play_reference_cannot_borrow_a_more_recent_override_or_another_input(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));old=self.observe(owner,effect)['playbackReference']
            owner,effect=self.act('play',dict(name='Crying'));new=self.observe(owner,effect)['playbackReference']
            m.epoch+=2100;m.restore();owner,effect=self.act('wait-complete');owner.source.read();owner.source.read()
            with self.assertRaises(NativeUIError):effect.measure(effect.reference(),played=old)
            new['inputTicket']='f'*32
            with self.assertRaises(NativeUIError):effect.measure(effect.reference(),played=new)

    def test_idle_sit_discovery_reset_cannot_become_the_final_early_cancellation(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('cancel');value=self.observe(owner,effect)
            self.assertEqual('idle-reset',value['kind']);self.assertFalse(value['state']['restoredBeforeNominalEnd'])
            self.assertIsNone(value['proof']);self.assertEqual([],m.controls.input_requests[1:])

    def test_missing_or_replaced_immutable_original_is_not_hidden_by_memory(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));self.observe(owner,effect)
            reference=effect.reference();entries=owner.source.originals.manifest(owner.source.state['manifests'][-1])
            value=owner.source.originals.expand(entries[-1]);path=owner.source.originals.path(value);path.unlink()
            with self.assertRaises((NativeUIError,OSError)):effect.measure(reference)

    def test_equal_bytes_in_a_replacement_original_inode_are_not_adopted(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));self.observe(owner,effect)
            entries=owner.source.originals.manifest(owner.source.state['manifests'][-1])
            original=owner.source.originals.path(owner.source.originals.expand(entries[-1]));copy=original.with_suffix('.replacement')
            copy.write_bytes(original.read_bytes());copy.chmod(0o600);copy.replace(original)
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())

    def test_unpersisted_input_and_source_memory_cannot_replace_durable_ownership(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));self.observe(owner,effect)
            original=deepcopy(owner.state);owner.state['current']['call']['inputs']['name']='Crying'
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())
            owner.state=original;owner.source.state['revision']-=1
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())

    def test_wait_complete_needs_an_original_owned_play_even_when_actual_native_is_idle(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('wait-complete');owner.source.read();owner.source.read()
            self.assertEqual([],m.controls.input_requests)
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())

    def test_final_slow_guard_or_provider_with_frozen_epoch_cannot_refresh_originals(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));self.observe(owner,effect)
            status=owner.source.phase.status
            def delayed(*args):
                value=status(*args);m.clock+=2;return value
            owner.source.phase.status=delayed
            before=len(m.controls.input_requests)
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())
            self.assertEqual(before,len(m.controls.input_requests))

    def test_lost_guard_before_delivery_cannot_publish_a_completed_join(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));self.observe(owner,effect)
            status=owner.source.phase.status
            def lost(*args):
                value=status(*args);m.okay=False;return value
            owner.source.phase.status=lost
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())

    def test_delayed_automatic_restore_after_ignored_cancel_does_not_report_early_cancellation(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));play=self.observe(owner,effect)['playbackReference']
            m.ignore_native=True;owner,effect=self.act('cancel');m.epoch+=2100;m.restore()
            value=self.observe(owner,effect,play)
            self.assertEqual('idle',value['state']['animation']);self.assertFalse(value['state']['restoredBeforeNominalEnd'])

    def test_stale_original_or_changed_current_phase_is_not_refreshed_by_measurement(self):
        m=self.model
        with m.lock.held():
            owner,effect=self.act('play',dict(name='Waving'));self.observe(owner,effect);m.epoch+=1600
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())
            owner.source.read();owner.source.read();m.call('close')
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())

    def actor(self,owner):
        source=self.model.source(role='actor')
        source.read();source.read()
        return PhoneEmoteEffects(owner,current_source=source)

    def test_actor_measures_its_own_loaded_effect_without_replaying_primary_inputs(self):
        m=self.model
        with m.lock.held():
            owner,primary=self.act('play',dict(name='Waving'))
            primary_value=self.observe(owner,primary);inputs=len(m.controls.input_requests)
            actor=self.actor(owner);value=actor.measure(actor.reference())
            self.assertEqual(2,value['emoteEffectVersion']);self.assertEqual('actor',value['role'])
            self.assertEqual('Waving',value['state']['animation'])
            self.assertNotEqual(primary_value['frame'],value['frame'])
            self.assertEqual(2,value['frame']['revision'])
            self.assertGreater(len(primary.source.frames),len(actor.source.frames))
            self.assertEqual(inputs,len(m.controls.input_requests))

    def test_actor_restoration_reopens_actor_play_and_primary_input_barriers(self):
        m=self.model
        with m.lock.held():
            owner,primary=self.act('sit');primary_play=self.observe(owner,primary)['playbackReference']
            actor=self.actor(owner);play=actor.measure(actor.reference())['playbackReference']
            owner,_effect=self.act('cancel');actor=self.actor(owner)
            value=actor.measure(actor.reference(),played=play)
            self.assertEqual('restoration',value['kind']);self.assertFalse(value['state']['override'])
            self.assertTrue(value['state']['restoredBeforeNominalEnd'])
            with self.assertRaises(NativeUIError):actor.measure(actor.reference(),played=primary_play)

    def test_actor_cannot_borrow_a_primary_frame_or_observation_before_consumption(self):
        m=self.model
        with m.lock.held():
            owner,primary=self.act('open');self.observe(owner,primary)
            actor=self.actor(owner);old=actor.reference()
            owner,primary=self.act('play',dict(name='Crying'));self.observe(owner,primary)
            actor=PhoneEmoteEffects(owner,current_source=actor.source)
            with self.assertRaises(NativeUIError):actor.measure(old)
            with self.assertRaises(NativeUIError):actor.measure(primary.reference())
            actor.source.read();actor.source.read()
            self.assertEqual('Crying',actor.measure(actor.reference())['state']['animation'])

    def test_actor_rejects_ignored_foreign_and_wrong_loaded_effects_after_consumed_input(self):
        for fault in ('ignored','foreign','different'):
            with self.subTest(fault=fault):
                temporary=tempfile.TemporaryDirectory(prefix='overte-emote-actor-');self.addCleanup(temporary.cleanup)
                m=EffectsModel(Path(temporary.name));self.model=m
                with patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=m.tablet),m.lock.held():
                    m.ignore_native=fault!='foreign';m.foreign=fault=='foreign'
                    owner,_primary=self.act('play',dict(name='Crying'))
                    if fault=='different':m.start('Waving')
                    actor=self.actor(owner)
                    self.assertEqual('Crying',m.widgets.active)
                    with self.assertRaises(NativeUIError):actor.measure(actor.reference())

    def test_actor_missing_current_original_and_missing_primary_barrier_stay_unavailable(self):
        for role in ('actor','primary'):
            with self.subTest(role=role):
                temporary=tempfile.TemporaryDirectory(prefix='overte-emote-actor-files-');self.addCleanup(temporary.cleanup)
                m=EffectsModel(Path(temporary.name));self.model=m
                with patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=m.tablet),m.lock.held():
                    owner,_primary=self.act('play',dict(name='Waving'));actor=self.actor(owner)
                    source=actor.source if role=='actor' else owner.source
                    entries=source.originals.manifest(source.state['manifests'][0])
                    source.originals.path(source.originals.expand(entries[-1])).unlink()
                    with self.assertRaises((NativeUIError,OSError)):actor.measure(actor.reference())

    def test_actor_unpersisted_current_state_and_lost_final_guard_cannot_publish(self):
        m=self.model
        with m.lock.held():
            owner,_primary=self.act('play',dict(name='Waving'));actor=self.actor(owner)
            original=deepcopy(actor.source.state);actor.source.state['revision']-=1
            with self.assertRaises(NativeUIError):actor.measure(actor.reference())
            actor.source.state=original;status=actor.source.phase.status
            def lost(*args):
                value=status(*args);m.okay=False;return value
            actor.source.phase.status=lost
            with self.assertRaises(NativeUIError):actor.measure(actor.reference())

    def test_slow_primary_archive_replay_is_included_in_actor_freshness(self):
        m=self.model
        with m.lock.held():
            owner,_primary=self.act('play',dict(name='Waving'));actor=self.actor(owner)
            decode=owner.decode
            def slow(value):
                result=decode(value);m.clock+=2;return result
            owner.decode=slow
            with self.assertRaises(NativeUIError):actor.measure(actor.reference())

    def test_actor_constructor_rejects_other_run_binding_or_lock(self):
        m=self.model
        with m.lock.held():
            owner,_primary=self.act('open');source=m.source(role='actor')
            for key,replacement in (('run','f'*32),('binding',dict(source.binding,processIdentity='32:other'))):
                with self.subTest(key=key):
                    original=getattr(source,key);setattr(source,key,replacement)
                    with self.assertRaises(NativeUIError):PhoneEmoteEffects(owner,current_source=source)
                    setattr(source,key,original)
            other=m.source()
            with self.assertRaises(NativeUIError):PhoneEmoteEffects(owner,current_source=other)

    def test_primary_and_actor_ordinary_input_effects_support_the_actual_shared_default_vm(self):
        m=self.model;m.use_included_source()
        with m.lock.held():
            owner,effect=self.act('sit');value=self.observe(owner,effect)
            actor=self.actor(owner);remote=actor.measure(actor.reference())
            self.assertEqual('Sit2',value['state']['sit']);self.assertEqual(value['state'],remote['state'])
            self.assertEqual(2,remote['proof']['event']['caller']['callerVersion'])
            play=value['playbackReference'];actor_play=remote['playbackReference']
            owner,effect=self.act('cancel');value=self.observe(owner,effect,play)
            actor=self.actor(owner);remote=actor.measure(actor.reference(),played=actor_play)
            self.assertTrue(value['state']['restoredBeforeNominalEnd']);self.assertEqual(value['state'],remote['state'])

    def test_consumed_correct_button_url_and_moving_rig_with_foreign_file_bytes_cannot_publish_for_either_role(self):
        for role in ('primary','actor'):
            m=self.model;m.use_included_source();m.actual_asset_name='Cheering'
            with self.subTest(role=role),patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=m.tablet),m.lock.held():
                owner,_effect=self.act('play',dict(name='Waving'));owner.source.read();owner.source.read()
                effect=PhoneEmoteEffects(owner) if role=='primary' else self.actor(owner)
                with self.assertRaises(NativeUIError):effect.measure(effect.reference())
            # Independent attempts need fresh durable ownership, not a retry
            # over the failed journal. The next subcase uses a new test model.
            if role=='primary':
                temporary=tempfile.TemporaryDirectory(prefix='overte-emote-wrong-bytes-');self.addCleanup(temporary.cleanup)
                self.model=EffectsModel(Path(temporary.name))


if __name__=='__main__':unittest.main()
