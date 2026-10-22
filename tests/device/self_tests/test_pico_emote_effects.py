"""Actual Pico source/input/effect joins on explicit synthetic Rig/Qt boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_effects import PicoEmoteEffects
from self_tests import test_pico_emote_inputs as input_seams
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_animation_source import source_for_clip


class EffectsBoundary:
    """Synthetic original VM/Rig/timer; never product playback or GPU pixels."""
    def __init__(self):
        self.input=input_seams.InputsTests();self.input.setUp();self.s=self.input.s
        self.actual=None;self.events=[];self.frames=[];self.generation=0;self.sequence=0
        self.ignore=False;self.foreign=False;self.wrong_asset=None;self.frozen=False;self.variant='Sit2'
        self.value=None;old_readers=self.s.readers
        def readers():
            roots,code,cache,_native,widgets=old_readers()
            native=NativeFeatureObservation(self.send,lambda:json.dumps(self.value),lambda:self.s.epoch,
                self.s.guard,31,monotonic=lambda:self.s.clock,sleep=self.input.sleep)
            return roots,code,cache,native,widgets
        self.s.readers=readers
        original=self.input.input
        def activate(identifier,*args,**kwargs):
            original(identifier,*args,**kwargs)
            if not identifier.startswith('emote.play.') or self.ignore:return
            name=identifier[len('emote.play.'):]
            if self.actual is not None and not self.s.widget.active:self.restore()
            else:
                highlighted=self.s.widget.active
                if self.actual is not None:self.restore()
                self.s.widget.active=highlighted;self.start(self.variant if name=='Sit' else name)
        self.input.input=activate;self.input.original.navigation.input=activate

    def close(self):self.input.doCleanups()
    def tick(self,ms):self.s.epoch+=ms;self.s.clock+=ms/1000;self.s.widget.clock=self.s.clock
    def caller(self,kind):
        engine=self.s.code['source']['engines'][0]
        member=deepcopy(self.s.code['source']['membership']['managers'][0])
        if self.foreign:member['instance']='8'*32
        return dict(callerVersion=2,method='overrideAnimation' if kind=='override' else 'restoreAnimation',
            sequence=len(self.events)+1,invokedEpochMs=self.s.epoch,manager=member,
            code=deepcopy(engine['code']),compilation=deepcopy(engine['compiled']['compilations'][0]))
    def event(self,kind):
        return dict(eventSequence=len(self.events)+1,kind=kind,overrideSequence=self.generation,
            capturedEpochMs=self.s.epoch,caller=self.caller(kind))
    def start(self,name):
        self.actual=name;self.generation+=1;self.started=self.s.epoch
        event=self.event('override');self.request=dict(url=self.s.before['source']['defaultScriptsUrl']+
            '/system/assets/animations/'+name+'.fbx',framesPerSecond=60.,loop=False,firstFrame=0.,lastFrame=120.)
        event['request']=deepcopy(self.request);self.events.append(event)
    def restore(self):
        self.actual=None;self.events.append(self.event('restore'));self.s.widget.active=''
    def send(self,request):
        self.s.calls.append('effect-native');self.sequence+=1;self.tick(100)
        pose=.1+self.sequence*.01 if self.actual is not None else .1
        if self.actual and self.frozen:pose=.2
        frame=dict(frameSequence=self.sequence,overrideSequence=self.generation,evaluationSequence=self.sequence*10,
            capturedEpochMs=self.s.epoch,overrideActive=self.actual is not None,
            joints=[dict(index=0,pose=[0.,0.,0.,1.,pose,.2,.3])])
        if self.actual:
            clip=dict(self.request,requestedUrl=self.request['url'],frame=min((self.s.epoch-self.started)*.06,120.),
                loadedFrames=120,evaluatedEpochMs=self.s.epoch,evaluationSequence=self.sequence)
            clip.update(animationSourceVersion=1,assetSource=source_for_clip(clip,consumed=self.started,actual_name=self.wrong_asset))
            frame['clip']=clip
        self.frames.append(frame)
        history=dict(historyVersion=2,instance='e'*32,available=True,callSequence=len(self.events),
            overrideSequence=self.generation,frameSequence=self.sequence,droppedEvents=max(0,len(self.events)-64),
            droppedFrames=max(0,len(self.frames)-32),events=deepcopy(self.events[-64:]),frames=deepcopy(self.frames[-32:]))
        boundary=NativeBoundary();boundary.sequence=self.sequence-1
        def mutate(value):
            value.update(instance=self.s.before['instance'],processId=31,requestedEpochMs=self.s.epoch,capturedEpochMs=self.s.epoch,
                animationFence=dict(rigId=2,sequence=frame['evaluationSequence']-1,requestedEpochMs=self.s.epoch))
            value['animation'].update(rigId=2,capturedEpochMs=self.s.epoch,evaluationSequence=frame['evaluationSequence'],
                overrideActive=frame['overrideActive'],joints=[row['pose'] for row in frame['joints']],history=history)
            if self.actual:value['animation']['clip']=deepcopy(frame['clip'])
            else:value['animation'].pop('clip',None)
        boundary.mutate=mutate;boundary.send(request);self.value=deepcopy(boundary.sample)
    def act(self,verb,inputs=None):
        owner=self.input.create();owner.act(self.input.call(verb,inputs));return owner,PicoEmoteEffects(owner)
    def observe(self,owner,effect,played=None):
        owner.source.read();owner.source.read()
        return effect.measure(effect.reference(),played=played)


class EffectsTests(unittest.TestCase):
    def setUp(self):
        self.model=EffectsBoundary();self.addCleanup(self.model.close)
    def test_normal_play_is_joined_to_actual_compiled_caller_advancing_clip_and_pose(self):
        m=self.model
        with m.s.lock.held():
            owner,effect=m.act('play',{'name':'Crying'});value=m.observe(owner,effect)
            self.assertEqual('Crying',value['state']['animation']);self.assertTrue(value['state']['override'])
            self.assertGreaterEqual(len(value['proof']['frameSequences']),2)
            self.assertEqual(2,value['proof']['event']['caller']['callerVersion'])
            before=list(m.s.calls);self.assertEqual(value,effect.recompute(effect.reference()));self.assertEqual(before,m.s.calls)
    def test_ignored_native_play_never_inherits_widget_highlight_or_input_ack(self):
        m=self.model;m.ignore=True
        with m.s.lock.held():
            owner,effect=m.act('play',{'name':'Crying'})
            self.assertEqual('Crying',m.s.widget.active)
            with self.assertRaises(NativeUIError):m.observe(owner,effect)
    def test_foreign_compilation_wrong_loaded_asset_and_frozen_final_pose_fail(self):
        for fault in ('caller','asset','pose'):
            with self.subTest(fault=fault):
                m=EffectsBoundary();self.addCleanup(m.close);m.foreign=fault=='caller';m.wrong_asset='Waving' if fault=='asset' else None;m.frozen=fault=='pose'
                with m.s.lock.held():
                    owner,effect=m.act('play',{'name':'Crying'})
                    with self.assertRaises(NativeUIError):m.observe(owner,effect)
    def test_natural_completion_and_early_cancel_use_original_native_and_caller_clocks(self):
        for verb in ('wait-complete','cancel'):
            with self.subTest(verb=verb):
                m=EffectsBoundary();self.addCleanup(m.close)
                with m.s.lock.held():
                    owner,effect=m.act('play',{'name':'Waving'});played=m.observe(owner,effect)['playbackReference']
                    if verb=='wait-complete':m.tick(2200);m.restore()
                    owner,effect=m.act(verb);value=m.observe(owner,effect,played)
                    self.assertFalse(value['state']['override']);self.assertEqual('idle',value['state']['animation'])
                    self.assertEqual(verb=='cancel',value['state']['restoredBeforeNominalEnd'])
    def test_normal_sit_replacement_requires_actual_prior_restore_and_new_loaded_motion(self):
        m=self.model
        with m.s.lock.held():
            owner,effect=m.act('sit');first=m.observe(owner,effect);self.assertEqual('Sit2',first['state']['sit'])
            owner,effect=m.act('override',{'name':'Waving'});value=m.observe(owner,effect)
            self.assertEqual('Waving',value['state']['animation'])
            self.assertEqual(['override','restore','override'],[event['kind'] for event in m.events])
    def test_override_from_idle_and_idle_cancel_do_not_fabricate_early_restore(self):
        m=self.model
        with m.s.lock.held():
            owner,effect=m.act('override',{'name':'Waving'})
            with self.assertRaises(NativeUIError):m.observe(owner,effect)
        m=EffectsBoundary();self.addCleanup(m.close)
        with m.s.lock.held():
            owner,effect=m.act('cancel');value=m.observe(owner,effect)
            self.assertEqual('idle-reset',value['kind']);self.assertFalse(value['state']['restoredBeforeNominalEnd'])
    def test_closed_original_baseline_is_measured_without_creating_input_journal(self):
        m=self.model;m.s.widget.tablet=False
        with m.s.lock.held():
            owner=m.input.create();owner.source.read();effect=PicoEmoteEffects(owner)
            value=effect.phase_measure(effect.reference())
            self.assertEqual('baseline',value['phase']);self.assertFalse(value['state']['panel']);self.assertIsNone(owner.store.read())
            self.assertEqual([],m.input.inputs);self.assertEqual([],m.input.controllers)
    def test_controller_open_generation_edge_is_followed_by_actual_effect_panel(self):
        m=self.model;m.s.widget.tablet=False
        with m.s.lock.held():
            owner,effect=m.act('open');value=m.observe(owner,effect)
            self.assertTrue(value['state']['panel']);self.assertEqual(['tablet.open'],m.input.controllers)
            self.assertFalse(value['state']['override'])
    def test_archival_recompute_reopens_originals_without_queries_or_current_authority(self):
        m=self.model
        with m.s.lock.held():
            owner,effect=m.act('play',{'name':'Crying'});value=m.observe(owner,effect)
            calls=list(m.s.calls)
            historical=effect._archive_context(owner.store.read(),owner.source.store.read(),owner.source.store.read())
            self.assertEqual(value,historical.recompute(effect.reference()));self.assertEqual(calls,m.s.calls)
            with self.assertRaises(NativeUIError):historical.measure(effect.reference())
            altered=deepcopy(effect.reference());altered['sha256']='0'*64
            with self.assertRaises(NativeUIError):historical.recompute(altered)

    def test_pending_native_restore_never_becomes_completed_cancel(self):
        m=self.model
        with m.s.lock.held():
            owner,effect=m.act('play',{'name':'Waving'});played=m.observe(owner,effect)['playbackReference']
            m.ignore=True;owner,effect=m.act('cancel');owner.source.read();owner.source.read()
            self.assertTrue(effect.pending_restore(effect.reference(),played)['state']['override'])
            with self.assertRaises(NativeUIError):effect.measure(effect.reference(),played=played)

    def test_final_guard_native_clock_jump_is_rechecked_with_frozen_host_clock(self):
        m=self.model
        with m.s.lock.held():
            owner,effect=m.act('play',{'name':'Crying'});m.observe(owner,effect)
            original=effect.source.guard;count=0
            def trace():
                nonlocal count
                count+=1;return original()
            effect.source.guard=trace;effect.measure(effect.reference());total=count;self.assertGreater(total,1)
            count=0
            def jump():
                nonlocal count
                count+=1
                if count==total:m.s.epoch+=2000
                return original()
            effect.source.guard=jump
            with self.assertRaises(NativeUIError):effect.measure(effect.reference())
            self.assertEqual(total,count)

    def test_stale_frame_changed_phase_and_slow_final_guard_cannot_be_current(self):
        m=self.model
        with m.s.lock.held():
            owner,effect=m.act('play',{'name':'Crying'});m.observe(owner,effect);ref=effect.reference()
            m.tick(1600)
            with self.assertRaises(NativeUIError):effect.measure(ref)
        for fault in ('phase','guard'):
            with self.subTest(fault=fault):
                m=EffectsBoundary();self.addCleanup(m.close)
                with m.s.lock.held():
                    owner,effect=m.act('play',{'name':'Crying'});m.observe(owner,effect)
                    if fault=='phase':m.input.call('close')
                    else:
                        original=m.s.guard
                        def late():m.s.clock+=2;return original()
                        effect.source.guard=late
                    with self.assertRaises((NativeUIError,ValueError)):effect.measure(effect.reference())


if __name__=='__main__':unittest.main()
