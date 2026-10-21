"""Original call/evaluated-frame history counterexamples; no Rig compilation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_animation_history import clip_run,restored_after
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import Boundary

URL='file:///actual/bundled/Sit2.fbx'


def history_source(value,*,event_epoch=19000):
    animation=value['animation'];clip=deepcopy(animation['clip'])
    request={k:clip[k] for k in ('framesPerSecond','loop','firstFrame','lastFrame')};request['url']=URL
    events=[dict(eventSequence=1,kind='override',overrideSequence=1,capturedEpochMs=event_epoch,request=request),
            dict(eventSequence=2,kind='restore',overrideSequence=1,capturedEpochMs=event_epoch+700)]
    frames=[]
    for sequence,epoch,active in ((1,event_epoch+500,True),(2,event_epoch+600,True),(3,event_epoch+800,False)):
        pose=[0.,0.,0.,1.,.1+sequence*.01,.2,.3]
        frame=dict(frameSequence=sequence,overrideSequence=1,evaluationSequence=sequence+5,capturedEpochMs=epoch,
            overrideActive=active,joints=[dict(index=0,pose=pose)])
        if active:
            actual=deepcopy(clip);actual.update(frame=sequence*10.,evaluationSequence=sequence,evaluatedEpochMs=epoch)
            frame['clip']=actual
        frames.append(frame)
    animation.update(overrideActive=False,history=dict(historyVersion=1,instance='e'*32,available=True,
        callSequence=2,overrideSequence=1,frameSequence=3,droppedEvents=0,droppedFrames=0,events=events,frames=frames))
    animation.pop('clip')


class AnimationHistoryTests(unittest.TestCase):
    def source(self,change=None):
        source=Boundary()
        def mutate(value):
            history_source(value)
            if change:change(value)
        source.mutate=mutate
        return source,source.reader()

    def test_finished_short_clip_keeps_original_call_loaded_frames_and_native_pose_effects(self):
        source,reader=self.source();value=reader.read(0,require_animation_history=True)
        self.assertFalse(value['animation']['overrideActive'])
        event,frames=clip_run(value,URL,after_event=0,after_epoch=19000)
        self.assertEqual(19000,event['capturedEpochMs']);self.assertEqual([19500,19600],[f['capturedEpochMs'] for f in frames])
        self.assertEqual([10.,20.],[f['clip']['frame'] for f in frames])
        restored,inactive=restored_after(value,event,after_epoch=19650,before_nominal_end=True)
        self.assertEqual(19700,restored['capturedEpochMs']);self.assertEqual(19800,inactive[0]['capturedEpochMs'])
        self.assertEqual({'schemaVersion','commandId','action'},set(source.commands[0]))
        self.assertNotIn('expected',str(source.commands))

    def test_new_control_envelope_cannot_relabel_a_previous_run_or_action_as_a_new_emote(self):
        source,reader=self.source();first=reader.read(0,require_animation_history=True)
        second=reader.read(first['sequence'],require_animation_history=True)
        self.assertEqual(first['animation']['history'],second['animation']['history'])
        for cursor,barrier in ((2,19000),(0,19001)):
            with self.assertRaises(NativeUIError):clip_run(second,URL,after_event=cursor,after_epoch=barrier)

    def test_a_native_override_call_without_loaded_or_advancing_clip_frames_is_not_an_effect(self):
        for fault in ('no-frames','unloaded','frozen-clip','foreign-loaded','wrong-requested','outside-frames'):
            with self.subTest(fault=fault):
                def change(value):
                    history=value['animation']['history'];frames=history['frames']
                    if fault=='no-frames':history.update(frames=[],frameSequence=0)
                    else:
                        for frame in frames[:2]:
                            if fault=='unloaded':frame['clip']['loadedFrames']=0
                            elif fault=='frozen-clip':frame['clip'].update(frame=10.,evaluationSequence=1)
                            elif fault=='foreign-loaded':frame['clip']['url']='file:///foreign.fbx'
                            elif fault=='wrong-requested':frame['clip']['requestedUrl']='file:///foreign.fbx'
                            else:frame['clip']['frame']=10000.
                source,reader=self.source(change);value=reader.read(0,require_animation_history=True)
                with self.assertRaises(NativeUIError):clip_run(value,URL,after_event=0,after_epoch=19000)

    def test_frozen_joints_or_quaternion_sign_flip_are_not_visible_pose_progress(self):
        for fault in ('frozen','antipodal'):
            def change(value):
                frames=value['animation']['history']['frames'];pose=deepcopy(frames[0]['joints'][0]['pose'])
                if fault=='antipodal':pose[:4]=[-n for n in pose[:4]]
                frames[1]['joints'][0]['pose']=pose
            source,reader=self.source(change);value=reader.read(0,require_animation_history=True)
            with self.assertRaises(NativeUIError):clip_run(value,URL,after_event=0,after_epoch=19000)

    def test_restore_call_without_a_later_inactive_evaluation_cannot_prove_restoration(self):
        def change(value):
            h=value['animation']['history'];h['frames']=h['frames'][:2];h['frameSequence']=2
        source,reader=self.source(change);value=reader.read(0,require_animation_history=True)
        event,frames=clip_run(value,URL,after_event=0,after_epoch=19000)
        with self.assertRaises(NativeUIError):restored_after(value,event,after_epoch=19650)

    def test_late_natural_completion_cannot_satisfy_an_early_restore_requirement(self):
        def change(value):
            value['animation']['history']['events'][0]['request']['lastFrame']=30.
            for f in value['animation']['history']['frames'][:2]:f['clip']['lastFrame']=30.
        source,reader=self.source(change);value=reader.read(0,require_animation_history=True)
        event,_=clip_run(value,URL,after_event=0,after_epoch=19000)
        self.assertTrue(restored_after(value,event,after_epoch=19650))
        with self.assertRaises(NativeUIError):restored_after(value,event,after_epoch=19650,before_nominal_end=True)

    def test_older_sources_and_post_observation_downgrade_fail_closed(self):
        with self.assertRaises(NativeUIError):Boundary().reader().read(0,require_animation_history=True)
        source,reader=self.source();first=reader.read(0,require_animation_history=True)
        source.mutate=None
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])

    def test_retimed_or_rewritten_historical_calls_and_frames_are_rejected(self):
        for fault in ('event-time','frame-time','pose','url'):
            source,reader=self.source();first=reader.read(0,require_animation_history=True)
            def change(value):
                h=value['animation']['history']
                if fault=='event-time':h['events'][0]['capturedEpochMs']+=1
                elif fault=='frame-time':h['frames'][0]['capturedEpochMs']+=1
                elif fault=='pose':h['frames'][0]['joints'][0]['pose'][4]+=.1
                else:h['events'][0]['request']['url']='file:///foreign.fbx'
            source.mutate=lambda value:(history_source(value),change(value))
            with self.assertRaises(NativeUIError):reader.read(first['sequence'])

    def test_rig_or_reloaded_graph_skeleton_context_cannot_borrow_original_history(self):
        for fault in ('rig','context'):
            source,reader=self.source();first=reader.read(0,require_animation_history=True)
            def change(value):
                history_source(value)
                if fault=='rig':value['animation']['rigId']=3
                else:value['animation']['history']['instance']='f'*32
            source.mutate=change
            with self.assertRaises(NativeUIError):reader.read(first['sequence'])

    def test_real_bounded_trimming_advances_drops_without_retiming_surviving_frames(self):
        source,reader=self.source();first=reader.read(0,require_animation_history=True)
        def trimmed(value):
            history_source(value);h=value['animation']['history'];h['frames']=h['frames'][1:];h['events']=h['events'][1:]
            h.update(droppedEvents=1,droppedFrames=1)
        source.mutate=trimmed;second=reader.read(first['sequence'],require_animation_history=True)
        self.assertEqual(first['animation']['history']['frames'][1:],second['animation']['history']['frames'])
        with self.assertRaises(NativeUIError):clip_run(second,URL,after_event=0,after_epoch=19000)

    def caller_source(self,change=None):
        from test_emote_rig_measurements import RigPackets
        model=RigPackets();origin=model.caller('override',19000)
        def original(value):
            history_source(value);history=value['animation']['history'];history['historyVersion']=2
            for row in history['events']:
                row['caller']=deepcopy(origin)
                row['caller'].update(method='overrideAnimation' if row['kind']=='override' else 'restoreAnimation',
                    sequence=row['eventSequence'],invokedEpochMs=row['capturedEpochMs'])
            if change:change(value)
        source=Boundary();source.mutate=original
        return source,source.reader()

    def test_v2_preserves_original_native_caller_and_explicit_non_script_origin(self):
        source,reader=self.caller_source();value=reader.read(0,require_animation_history=True)
        event,_frames=clip_run(value,URL,after_event=0,after_epoch=19000)
        self.assertEqual(1,event['caller']['sequence'])
        self.assertEqual('overrideAnimation',event['caller']['method'])
        self.assertEqual(15000,event['caller']['code']['submittedEpochMs'])
        source,reader=self.caller_source(lambda value:value['animation']['history']['events'][0].update(caller=None))
        value=reader.read(0,require_animation_history=True)
        self.assertIsNone(value['animation']['history']['events'][0]['caller'])

    def test_v2_origin_requires_closed_real_assignment_code_method_clocks_and_types(self):
        faults=[lambda c:c.update(callerVersion=True),lambda c:c.update(sequence=True),
            lambda c:c.update(sequence=0),lambda c:c.update(method='restoreAnimation'),
            lambda c:c.update(invokedEpochMs=20001),lambda c:c.update(invokedEpochMs=14999),
            lambda c:c.update(expectedManager='a'*32),lambda c:c['manager'].update(instance='foreign'),
            lambda c:c['manager'].update(assigned=False),lambda c:c['manager'].update(assignedEpochMs=16000),
            lambda c:c['code'].update(submitted=False),lambda c:c['code'].update(sha256='foreign')]
        for index,change in enumerate(faults):
            with self.subTest(fault=index):
                source,reader=self.caller_source(lambda value:change(value['animation']['history']['events'][0]['caller']))
                with self.assertRaises(NativeUIError):reader.read(0,require_animation_history=True)

    def test_v2_missing_origin_and_in_packet_caller_reuse_are_not_silently_adopted(self):
        for fault in ('missing','sequence','clock','code','assignment'):
            def change(value):
                rows=value['animation']['history']['events'];caller=rows[-1]['caller']
                if fault=='missing':rows[0].pop('caller')
                elif fault=='sequence':caller['sequence']=1
                elif fault=='clock':caller['invokedEpochMs']=18999
                elif fault=='code':caller['code']['sha256']='f'*64
                else:caller['manager']['url']='file:///foreign/script.js'
            source,reader=self.caller_source(change)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(0,require_animation_history=True)

    def test_caller_cursors_survive_complete_ring_trimming_and_are_not_reusable(self):
        from adapters.native_animation_history import accept,validate
        source,reader=self.caller_source();value=reader.read(0,require_animation_history=True)
        previous=accept(None,2,value['animation']['history'])
        base=deepcopy(value['animation']['history']);row=deepcopy(base['events'][-1])
        row.update(eventSequence=3,capturedEpochMs=19900)
        row['caller'].update(sequence=3,invokedEpochMs=19900)
        base.update(events=[row],callSequence=3,droppedEvents=2)
        validate(base,value['animation'],value['capturedEpochMs'])
        accepted=accept(previous,2,base)
        self.assertEqual(3,next(iter(accepted['callers'].values()))['sequence'])
        for fault in ('sequence','code','assignment','clock'):
            changed=deepcopy(base);caller=changed['events'][0]['caller']
            if fault=='sequence':caller['sequence']=2
            elif fault=='code':caller['code']['sha256']='f'*64
            elif fault=='assignment':caller['manager']['url']='file:///foreign/script.js'
            else:caller['invokedEpochMs']=19699
            validate(changed,value['animation'],value['capturedEpochMs'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):accept(previous,2,changed)

    def test_v1_remains_readable_but_cannot_replace_a_v2_history_in_the_same_rig(self):
        source,reader=self.caller_source();first=reader.read(0,require_animation_history=True)
        source.mutate=history_source
        with self.assertRaises(NativeUIError):reader.read(first['sequence'],require_animation_history=True)
        source,reader=self.source();self.assertEqual(1,reader.read(0,require_animation_history=True)['animation']['history']['historyVersion'])

    def test_missing_events_gap_numeric_flags_future_frames_and_malformed_poses_fail(self):
        def faults(h):
            return [lambda:h.update(available=1),lambda:h.update(historyVersion=True),lambda:h.update(events=[]),
                lambda:h['frames'][0].update(frameSequence=2),lambda:h['frames'][0].update(capturedEpochMs=21000),
                lambda:h['frames'][0]['joints'][0].update(pose=[0]*7),
                lambda:h['frames'][0].update(overrideActive=1),lambda:h.update(frames=h['frames']*11)]
        for index in range(8):
            def change(value):faults(value['animation']['history'])[index]()
            source,reader=self.source(change)
            with self.assertRaises(NativeUIError):reader.read(0,require_animation_history=True)
