"""Host-only original-packet counterexamples; no native or device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from adapters.normal_ui import NativeUIError
from feature_journeys import emote_motion as motion
from feature_journeys.scenarios import VERSION
from feature_journeys.witness import Journal
from test_emote_rig_measurements import IncludedRigPackets, RigPackets, ReplacementRigPackets
from test_native_animation_source import source_for_clip


class EmoteMotionTests(unittest.TestCase):
    def fixture(self, *, name='Waving', frames=44, times=(19075, 19150, 19225, 19300), compiled=True):
        model = (IncludedRigPackets if compiled else RigPackets)(name)
        model.request['lastFrame'] = float(frames)
        barrier = model.group(model.native(18800, baseline=True))
        # Simulated native evaluation boundary. It hashes actual bundled bytes;
        # these synthetic poses/times never qualify real playback or latency.
        current = model.native(20000, active=True)
        originals = [model.frame(1, 18800, 10, False, position=.1)]
        for index, epoch in enumerate(times, 2):
            row = model.frame(index, epoch, index*10, True, position=index/10)
            row['clip']['loadedFrames'] = frames
            if compiled: row['clip']['assetSource'] = source_for_clip(row['clip'])
            originals.append(row)
        end = times[-1]; last = originals[-1]
        current.update(requestedEpochMs=end, capturedEpochMs=end)
        current['animationFence'].update(sequence=last['evaluationSequence']-1, requestedEpochMs=end)
        animation = current['animation']
        animation.update(capturedEpochMs=end, evaluationSequence=last['evaluationSequence'],
                         joints=[row['pose'] for row in last['joints']], clip=deepcopy(last['clip']))
        animation['history'].update(frames=originals, frameSequence=len(originals))
        model.frames=deepcopy(originals);self.model=model
        after = model.group(current)
        self.host = 18800
        journal = Journal(lambda: self.host); run = journal.register('emotes'); ticket = 'b'*32
        journal.activate(run, ticket, 'sit' if name.startswith('Sit') else 'play',
                         {} if name.startswith('Sit') else dict(name=name))
        call = dict(contractVersion=VERSION, runId=run, verb='sit' if name.startswith('Sit') else 'play',
                    inputs={} if name.startswith('Sit') else dict(name=name), ticket=ticket,
                    fixtureUrl='http://controlled.test/feature-fixture/v1/runs/'+run+'/')
        def part(group, epoch):
            self.host=epoch
            before=journal.phase(run, ('c' if epoch==18800 else 'e')*32)
            after=journal.phase(run, ('d' if epoch==18800 else 'f')*32)
            return dict(group=group, epochMs=epoch, hostEpochMs=epoch, phaseBefore=before, phaseAfter=after)
        value=dict(emoteMotionVersion=1, role='primary', call=call,
                   before=part(barrier,18800), after=part(after,end))
        return value

    def measure(self, value, **kwargs):
        return motion.measure(value, call=value['call'], role='primary', epoch=value['after']['hostEpochMs'], **kwargs)

    def test_actual_short_window_qualifies_without_three_later_rpc_samples(self):
        value=self.fixture(); original=deepcopy(value); result=self.measure(value)
        self.assertEqual(4,result['nativeSamples']);self.assertEqual(225,result['nativeSpanMs'])
        self.assertAlmostEqual(44/60*1000/4,result['requiredSpanMs'])
        self.assertEqual(original,value)
        raw=motion.packet(value['call'],value['before'],value['after'],role='primary')
        state=result.pop('state')|dict(panel=False)
        self.assertEqual(result,motion.read(raw,call=value['call'],role='primary',epoch=19300,captured=19300,state=state))
        self.assertNotIn('url',str(result));self.assertNotIn('processId',str(result))

    def test_long_motion_keeps_half_second_window_and_all_three_sit_variants(self):
        for name in ('Crying','Sit1','Sit2','Sit3'):
            with self.subTest(name=name):
                result=self.measure(self.fixture(name=name,frames=401,times=(19075,19250,19500,19650)))
                self.assertEqual(500,result['requiredSpanMs'])
                self.assertEqual('Sit' if name.startswith('Sit') else name,result['state']['animation'])

    def test_long_clip_qualifies_only_fresh_suffix_without_redating_old_valid_prefix(self):
        value=self.fixture(name='Crying',frames=401,times=(19075,19250,20800,21100,21400))
        original=deepcopy(value);result=self.measure(value)
        self.assertEqual(3,result['nativeSamples']);self.assertEqual(600,result['nativeSpanMs'])
        self.assertEqual(4,result['firstFrameSequence']);self.assertEqual(original,value)

    def test_override_requires_actual_active_sit_history_and_genuine_old_stop(self):
        before,after=ReplacementRigPackets('Sit2').replacing();self.host=18800
        journal=Journal(lambda:self.host);run=journal.register('emotes');journal.activate(run,'1'*32,'sit',{})
        self.host=20000;journal.activate(run,'2'*32,'override',dict(name='Crying'))
        call=dict(contractVersion=VERSION,runId=run,verb='override',inputs=dict(name='Crying'),ticket='2'*32,
            fixtureUrl='http://controlled.test/feature-fixture/v1/runs/'+run+'/')
        def part(group,epoch,a,b):
            self.host=epoch
            return dict(group=group,epochMs=epoch,hostEpochMs=epoch,
                phaseBefore=journal.phase(run,a*32),phaseAfter=journal.phase(run,b*32))
        value=dict(emoteMotionVersion=1,role='primary',call=call,
            before=part(before,20000,'3','4'),after=part(after,20800,'5','6'))
        self.assertEqual('Crying',self.measure(value)['state']['animation'])
        changed=deepcopy(value)
        for frame in (changed['before'],changed['after']):
            for key in ('phaseBefore','phaseAfter'):
                frame[key]['activations'][0]['stimulus']=dict(verb='open',inputs={})
        with self.assertRaises((ValueError,NativeUIError)):self.measure(changed)
        ordinary=self.fixture(name='Crying');ordinary['call'].update(verb='override')
        for frame in (ordinary['before'],ordinary['after']):
            for key in ('phaseBefore','phaseAfter'):frame[key]['activations'][-1]['stimulus']['verb']='override'
        with self.assertRaises((ValueError,NativeUIError)):self.measure(ordinary)

    def test_too_few_native_samples_or_insufficient_span_does_not_borrow_rpc_stability(self):
        for times in ((19075,19300),(19075,19150,19225)):
            with self.subTest(times=times),self.assertRaises((ValueError, NativeUIError)):self.measure(self.fixture(times=times))

    def test_duration_comes_from_actual_request_and_loaded_data_not_a_name_table(self):
        value=self.fixture(frames=120)
        with self.assertRaises((ValueError, NativeUIError)):self.measure(value)
        result=self.measure(self.fixture(frames=120,times=(19075,19250,19500,19650)))
        self.assertEqual(2000,result['nominalDurationMs'])

    def test_frozen_positions_clip_frames_or_duplicate_native_times_are_rejected(self):
        for fault in ('pose','clip','time'):
            value=self.fixture();native=value['after']['group']['native'];frames=native['animation']['history']['frames'][1:]
            for row in frames:
                if fault=='pose':row['joints']=deepcopy(frames[0]['joints'])
                elif fault=='clip':row['clip']['frame']=frames[0]['clip']['frame']
                else:row['capturedEpochMs']=19300;row['clip']['evaluatedEpochMs']=19300
            native['animation']['clip']=deepcopy(frames[-1]['clip'])
            native['animation']['joints']=[row['pose'] for row in frames[-1]['joints']]
            with self.subTest(fault=fault),self.assertRaises((ValueError, NativeUIError)):self.measure(value)

    def test_wrong_role_ticket_run_selected_name_or_compilation_cannot_be_relabelled(self):
        for fault in ('role','ticket','run','name','phase','uncompiled','caller','bytes','birth','old-barrier'):
            value=self.fixture(compiled=fault!='uncompiled');after=value['after'];native=after['group']['native']
            if fault=='role':value['role']='actor'
            elif fault=='ticket':value['call']['ticket']='9'*32
            elif fault=='run':value['call']['runId']='9'*32
            elif fault=='name':value['call']['inputs']['name']='Cheering'
            elif fault=='phase':after['phaseAfter']['activations'][-1]['ticket']='9'*32
            elif fault=='caller':native['animation']['history']['events'][0]['caller']['compilation']['scriptId']+=1
            elif fault=='bytes':native['animation']['clip']['assetSource']['model']['sha256']='9'*64
            elif fault=='birth':native['instance']='9'*32
            elif fault=='old-barrier':value['before']=deepcopy(after)
            with self.subTest(fault=fault),self.assertRaises((ValueError, NativeUIError)):self.measure(value)

    def test_host_and_native_clocks_keep_original_pairs_and_both_freshness_limits(self):
        value=self.fixture();call=value['call']
        for part in (value['before'],value['after']):
            part['hostEpochMs']+=100000
            for key in ('phaseBefore','phaseAfter'):part[key]['capturedEpochMs']+=100000
        result=motion.measure(value,call=call,role='primary',epoch=119300)
        self.assertEqual(225,result['nativeSpanMs'])
        for now in (119049,120801,120650):
            with self.subTest(now=now),self.assertRaises((ValueError, NativeUIError)):motion.measure(value,call=call,role='primary',epoch=now)

    def test_public_fact_mismatch_missing_or_expectation_bearing_file_is_rejected(self):
        value=self.fixture();result=self.measure(value);raw=motion.packet(value['call'],value['before'],value['after'],role='primary')
        kwargs=dict(call=value['call'],role='primary',epoch=19300,captured=19300,state=result['state'])
        for content in (b'',b'null',b'{}',b'NaN',b'x'*(motion.LIMIT+1),
                        json.dumps(value|dict(expectedSpanMs=200)).encode(),raw.replace(b'"role":"primary"',b'"role":"primary","role":"primary"')):
            with self.subTest(length=len(content)),self.assertRaises(AssertionError):motion.read(content,**kwargs)
        for key,wrong in (('animation','Cheering'),('override',False),('poseProgress',0.),('restoredBeforeNominalEnd',True)):
            with self.subTest(key=key),self.assertRaises(AssertionError):motion.read(raw,**(kwargs|dict(state=kwargs['state']|{key:wrong})))

    def test_completed_original_motion_never_claims_current_active_playback(self):
        value=self.fixture();model=self.model;after=value['after']
        after['group']=model.group(model.native(19310,restore_epoch=19305))
        after.update(epochMs=19310,hostEpochMs=19310)
        for key in ('phaseBefore','phaseAfter'):after[key]['capturedEpochMs']=19310
        with self.assertRaises((ValueError,NativeUIError)):self.measure(value)

    def test_payload_has_closed_versions_shapes_types_and_no_saved_statistics(self):
        for change in (dict(emoteMotionVersion=True),dict(emoteMotionVersion=2),dict(nativeSamples=3),
                       dict(before=None),dict(after={}),dict(call=None)):
            value=self.fixture();call=deepcopy(value['call']);value.update(change)
            with self.subTest(fields=list(change)),self.assertRaises((ValueError,NativeUIError)):
                motion.measure(value,call=call,role='primary',epoch=19300)


if __name__=='__main__':unittest.main()
