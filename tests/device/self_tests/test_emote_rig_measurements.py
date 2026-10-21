"""Original native Rig/source groups; no product execution or expected states."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.emote_rig_measurements import playback,restoration
from adapters.normal_ui import NativeUIError
from test_native_feature_observation import Boundary as Features
from test_native_script_roots import RootBoundary
from test_emote_source_profile import actual,pins,included_source,included_caller


class RigPackets:
    def __init__(self,name='Waving',*,root=None):
        self.epoch=20000;self.sequence=0;self.name=name;self.frames=[];self.restored_at=None
        self.roots=RootBoundary()
        if root is not None:self.roots.root=root
        self.root_reader=self.roots.reader()
        self.code,self.code_reader=actual(pins()[0],root=self.roots.root+'/')
        assigned=self.code.engine['url']
        if assigned.startswith('file:'):self.code.engine['url']='file:///~//system/+android_phoneInterface/phoneEmote.js'
        original=self.code.mutate
        def observed(value):
            original(value);value.update(instance='a'*32,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch)
            value['source'].update(membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[
                dict(instance=self.code.engine['required']['instance'],assigned=True,url=assigned,loadGeneration=1,assignedEpochMs=14000)]))
        self.code.mutate=observed;self.code_reader.clock_ms=lambda:self.epoch
        self.url=self.roots.root+'/system/assets/animations/'+name+'.fbx'
        self.request=dict(url=self.url,framesPerSecond=60.,loop=False,firstFrame=0.,lastFrame=120.)
    def caller(self,kind,epoch):
        return dict(callerVersion=1,method='overrideAnimation' if kind=='override' else 'restoreAnimation',
            sequence=1 if kind=='override' else 2,invokedEpochMs=epoch,
            manager=dict(instance=self.code.engine['required']['instance'],assigned=True,
                url=self.roots.root+'/system/+android_phoneInterface/phoneEmote.js',loadGeneration=1,assignedEpochMs=14000),
            code=dict(submitted=True,encoding=pins()[0]['encoding'],codeUnits=pins()[0]['codeUnits'],
                sha256=pins()[0]['sha256'],submittedEpochMs=15000))
    def frame(self,sequence,epoch,evaluation,active,*,position=0.):
        value=dict(frameSequence=sequence,overrideSequence=1 if sequence>1 else 0,evaluationSequence=evaluation,
            capturedEpochMs=epoch,overrideActive=active,joints=[dict(index=0,pose=[0.,0.,0.,1.,position,.2,.3])])
        if active:
            value['clip']=dict(self.request,requestedUrl=self.url,frame=(epoch-19000)*.06,loadedFrames=120,
                evaluatedEpochMs=epoch,evaluationSequence=sequence)
        return value
    def native(self,epoch,*,active=False,baseline=False,restore_epoch=None):
        self.sequence+=1
        frames=[self.frame(1,18800,10,False,position=.1)];events=[]
        if not baseline:
            events=[dict(eventSequence=1,kind='override',overrideSequence=1,capturedEpochMs=19000,request=deepcopy(self.request),caller=self.caller('override',19000))]
            frames += [self.frame(2,19200,20,True,position=.2),self.frame(3,19500,30,True,position=.3),
                self.frame(4,20000,50,True,position=.4)]
            # Continue the producer's original timeline, including frames from
            # a real earlier input-barrier acquisition. Never retime that prefix.
            if len(self.frames)>4:frames=deepcopy(self.frames)
            if not active:
                if self.restored_at is None:self.restored_at=restore_epoch
                assert self.restored_at==restore_epoch
                events.append(dict(eventSequence=2,kind='restore',overrideSequence=1,capturedEpochMs=self.restored_at,caller=self.caller('restore',self.restored_at)))
            if not active or epoch>frames[-1]['capturedEpochMs']:
                count=len(frames)+1;evaluation=frames[-1]['evaluationSequence']+10
                frames.append(self.frame(count,epoch,evaluation,active,position=.4+(count-4)*.1))
        self.frames=deepcopy(frames)
        history=dict(historyVersion=2,instance='e'*32,available=True,callSequence=len(events),overrideSequence=0 if baseline else 1,
            frameSequence=len(frames),droppedEvents=0,droppedFrames=0,events=events,frames=frames)
        latest=frames[-1];source=Features();source.sequence=self.sequence-1
        def original(value):
            animation=value['animation'];value.update(instance='a'*32,processId=31,requestedEpochMs=epoch,capturedEpochMs=epoch)
            value['animationFence']=dict(rigId=2,sequence=latest['evaluationSequence']-1,requestedEpochMs=epoch)
            animation.update(rigId=2,capturedEpochMs=epoch,evaluationSequence=latest['evaluationSequence'],overrideActive=active,
                joints=[row['pose'] for row in latest['joints']],history=history)
            if active:animation['clip']=deepcopy(latest['clip'])
            else:animation.pop('clip',None)
        source.mutate=original;source.send(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-native-observe'))
        return deepcopy(source.sample)
    def group(self,packet):
        self.epoch=self.roots.epoch=packet['capturedEpochMs']
        before=self.root_reader.read(0 if self.root_reader.last is None else self.root_reader.last['sequence'])
        script=self.code_reader.read(self.code_reader.sequence,require_code_identity=True,require_membership=True)
        after=self.root_reader.read(before['sequence'])
        return dict(rootsBefore=before,script=script,native=packet,rootsAfter=after)
    def playing(self):
        barrier=self.native(18800,baseline=True);group=self.group(self.native(20000,active=True))
        return barrier,group,playback(group,barrier,pid=31,epoch=20000)


class IncludedRigPackets(RigPackets):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);observe=self.code.mutate
        def measured(value):
            observe(value);included_source(value,self.roots.root)
        self.code.mutate=measured

    def caller(self,kind,epoch):return included_caller(super().caller(kind,epoch),self.roots.root)


class EmoteRigTests(unittest.TestCase):
    def test_normal_phone_included_code_joins_original_loaded_clip_and_its_actual_asset_directory(self):
        model=IncludedRigPackets();_barrier,group,value=model.playing()
        self.assertEqual('Waving',value['state']['animation'])
        self.assertEqual(model.roots.root+'/system/assets/animations/Waving.fbx',value['event']['request']['url'])
        self.assertEqual(2,value['event']['caller']['callerVersion']);self.assertEqual(23,value['event']['caller']['compilation']['scriptId'])
        self.assertTrue(group['script']['source']['engines'][0]['url'].endswith('/defaultScripts.js'))
        self.assertEqual(1,len(group['script']['source']['engines']))

    def test_included_phone_restore_retains_the_same_original_vm_and_compiled_function(self):
        model=IncludedRigPackets();_barrier,group,played=model.playing()
        current=model.group(model.native(20600,active=False,restore_epoch=20500))
        value=restoration(current,played,pid=31,epoch=20600,native_barrier=group['native'])
        self.assertTrue(value['state']['restoredBeforeNominalEnd']);self.assertFalse(value['state']['override'])
        self.assertEqual(23,value['restore']['caller']['compilation']['scriptId'])

    def test_loaded_correct_clip_from_the_shared_default_or_foreign_compilation_is_not_emote(self):
        for fault in ('default-script','foreign-id','foreign-code','unknown-origin','legacy-manager-only'):
            model=IncludedRigPackets();original=model.caller
            def foreign(kind,epoch):
                caller=original(kind,epoch)
                if fault=='default-script':
                    caller['compilation'].update(scriptId=11,resourceName=model.roots.root+'/defaultScripts.js',compiledEpochMs=15001,
                        **{key:caller['code'][key] for key in ('encoding','codeUnits','sha256')})
                elif fault=='foreign-id':caller['compilation']['scriptId']=24
                elif fault=='foreign-code':caller['compilation']['sha256']='f'*64
                elif fault=='unknown-origin':caller['compilation']=None
                else:caller['callerVersion']=1;caller.pop('compilation')
                return caller
            model.caller=foreign
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):model.playing()

    def test_current_playback_comes_from_actual_clip_frame_and_loaded_moving_poses(self):
        model=RigPackets();barrier,group,value=model.playing();original=deepcopy((barrier,group))
        self.assertEqual('Waving',value['state']['animation']);self.assertTrue(value['state']['override'])
        self.assertEqual(1.,value['state']['poseProgress']);self.assertEqual([2,3,4],value['frameSequences'])
        self.assertEqual(original,(barrier,group));self.assertEqual(model.url,value['event']['request']['url'])
    def test_all_three_sit_variants_are_derived_from_actual_loaded_urls_without_a_requested_variant(self):
        for name in ('Sit1','Sit2','Sit3'):
            with self.subTest(name=name):
                _barrier,_group,value=RigPackets(name).playing()
                self.assertEqual('Sit',value['state']['animation']);self.assertEqual(name,value['state']['sit'])
    def test_every_actual_clip_name_is_reported_without_accepting_a_requested_name(self):
        from adapters.emote_rig_measurements import NAMES
        for name in NAMES:
            with self.subTest(name=name):
                _barrier,_group,value=RigPackets(name).playing()
                self.assertEqual('Sit' if name.startswith('Sit') else name,value['state']['animation'])
                self.assertEqual(name if name.startswith('Sit') else 'none',value['state']['sit'])
                self.assertNotIn('panel',value['state'])
    def test_pose_progress_counts_changed_original_joints_independently_of_clip_position(self):
        model=RigPackets();barrier,group,_played=model.playing()
        unchanged=[0.,0.,0.,1.,.5,.2,.3]
        barrier['animation']['joints'] += [deepcopy(unchanged) for _ in range(3)]
        group['native']['animation']['joints'] += [deepcopy(unchanged) for _ in range(3)]
        value=playback(group,barrier,pid=31,epoch=20000)
        self.assertEqual(.25,value['state']['poseProgress'])
        self.assertEqual(60.,group['native']['animation']['clip']['frame'])
        self.assertEqual(120.,group['native']['animation']['clip']['lastFrame'])
        group['native']['animation']['joints'].pop()
        with self.assertRaises(NativeUIError):playback(group,barrier,pid=31,epoch=20000)
    def test_qt_qrc_and_file_resource_urls_are_both_resolved_from_the_original_assignment(self):
        for root in ('qrc:/scripts','qrc:/actual/packaged/scripts','file:///actual/configured/cache/scripts'):
            with self.subTest(root=root):
                model=RigPackets(root=root);_barrier,_group,value=model.playing()
                self.assertEqual(root+'/system/assets/animations/Waving.fbx',value['event']['request']['url'])
                self.assertEqual('Waving',value['state']['animation'])
    def test_native_read_counter_cannot_hide_a_regressed_actual_rig_evaluation(self):
        from adapters.emote_rig_measurements import continuation
        model=RigPackets();_barrier,group,_played=model.playing();before=deepcopy(group['native'])
        current=model.native(20100,active=True)
        before['animation']['evaluationSequence']=current['animation']['evaluationSequence']+1
        before['animationFence']['sequence']=before['animation']['evaluationSequence']-1
        with self.assertRaises(NativeUIError):continuation(before,current,31)
    def test_rewriting_an_accepted_native_prefix_or_dropping_an_unseen_call_is_red(self):
        for fault in ('event','frame','drop'):
            model=RigPackets();_barrier,group,_played=model.playing();before=group['native']
            current=model.group(model.native(20100,active=True));history=current['native']['animation']['history']
            if fault=='event':history['events'][0]['capturedEpochMs']+=1
            elif fault=='frame':history['frames'][1]['joints'][0]['pose'][4]+=.01
            else:history['droppedEvents']=2;history['events']=[];history['callSequence']=2
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):playback(current,before,pid=31,epoch=20100)
    def test_history_sampling_may_precede_current_evaluation_but_cannot_hide_an_old_pose(self):
        from adapters.emote_rig_measurements import source
        model=RigPackets();_barrier,group,_played=model.playing()
        # Native history samples at 75 ms, rather than at every Rig evaluation.
        group['native']['animation']['history']['frames'][-1]['evaluationSequence']-=1
        source(group,31,20000)
        for age in (75,100):
            changed=deepcopy(group);changed['native']['animation']['history']['frames'][-1]['capturedEpochMs']-=age
            changed['native']['animation']['history']['frames'][-1]['clip']['evaluatedEpochMs']-=age
            with self.subTest(age=age),self.assertRaises(NativeUIError):source(changed,31,20000)
    def test_natural_completion_is_current_inactive_evaluation_not_a_fresh_play_ack(self):
        model=RigPackets();_barrier,_group,played=model.playing()
        current=model.group(model.native(21010,restore_epoch=21000))
        value=restoration(current,played,pid=31,epoch=21010)
        self.assertEqual('idle',value['state']['animation']);self.assertFalse(value['state']['override'])
        self.assertFalse(value['state']['restoredBeforeNominalEnd']);self.assertEqual([5],value['inactiveFrameSequences'])
    def test_early_restore_requires_a_new_native_event_after_the_actual_input_barrier(self):
        model=RigPackets();_barrier,_group,played=model.playing();before=model.native(20100,active=True)
        packet=model.native(20200,restore_epoch=20150)
        value=restoration(model.group(packet),played,pid=31,epoch=20200,native_barrier=before)
        self.assertTrue(value['state']['restoredBeforeNominalEnd']);self.assertEqual(20150,value['restore']['capturedEpochMs'])
    def test_delayed_natural_completion_never_becomes_early_restoration(self):
        model=RigPackets();_barrier,_group,played=model.playing()
        value=restoration(model.group(model.native(22010,restore_epoch=22000)),played,pid=31,epoch=22010)
        self.assertFalse(value['state']['restoredBeforeNominalEnd'])
    def test_a_completed_short_clip_can_prove_playback_without_pretending_it_is_still_active(self):
        model=RigPackets();barrier=model.native(18800,baseline=True)
        value=playback(model.group(model.native(21010,restore_epoch=21000)),barrier,pid=31,epoch=21010)
        self.assertEqual('idle',value['state']['animation']);self.assertFalse(value['state']['override'])
        self.assertEqual([2,3,4],value['frameSequences'])
    def test_same_loaded_clip_and_changed_pose_from_a_foreign_caller_cannot_prove_emote(self):
        for fault in ('manager','assignment','generation','code','missing','null','before-barrier','legacy'):
            model=RigPackets();barrier,group,_played=model.playing();history=group['native']['animation']['history']
            caller=history['events'][0]['caller']
            if fault=='manager':caller['manager']['instance']='8'*32
            elif fault=='assignment':caller['manager']['url']='file:///foreign/phoneEmote.js'
            elif fault=='generation':caller['manager']['loadGeneration']=2
            elif fault=='code':caller['code']['sha256']='f'*64
            elif fault=='missing':history['events'][0].pop('caller')
            elif fault=='null':history['events'][0]['caller']=None
            elif fault=='before-barrier':caller['invokedEpochMs']=18799
            else:
                history['historyVersion']=1
                for row in history['events']:row.pop('caller')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):playback(group,barrier,pid=31,epoch=20000)

    def test_foreign_restore_and_queued_pre_cancel_call_cannot_borrow_a_valid_play(self):
        for fault in ('manager','assignment','code','null','before-cancel','sequence'):
            model=RigPackets();_barrier,_group,played=model.playing();before=model.native(20100,active=True)
            packet=model.native(20200,restore_epoch=20150);caller=packet['animation']['history']['events'][-1]['caller']
            if fault=='manager':caller['manager']['instance']='8'*32
            elif fault=='assignment':caller['manager']['url']='file:///foreign/phoneEmote.js'
            elif fault=='code':caller['code']['sha256']='f'*64
            elif fault=='null':packet['animation']['history']['events'][-1]['caller']=None
            elif fault=='before-cancel':caller['invokedEpochMs']=20099
            else:caller['sequence']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                restoration(model.group(packet),played,pid=31,epoch=20200,native_barrier=before)

    def test_already_completed_playback_still_requires_the_original_selected_restore_caller(self):
        model=RigPackets();barrier=model.native(18800,baseline=True)
        group=model.group(model.native(21010,restore_epoch=21000))
        group['native']['animation']['history']['events'][-1]['caller']=None
        with self.assertRaises(NativeUIError):playback(group,barrier,pid=31,epoch=21010)

    def test_ignored_repeated_input_or_old_override_is_not_a_new_playback(self):
        model=RigPackets();_barrier,group,_played=model.playing()
        current=model.group(model.native(20100,active=True))
        with self.assertRaises(NativeUIError):playback(current,group['native'],pid=31,epoch=20100)
    def test_native_call_unloaded_clip_frozen_pose_or_foreign_frames_cannot_qualify(self):
        for fault in ('call-only','unloaded','frozen-clip','frozen-pose','antipodal-pose','foreign','wrong-request'):
            model=RigPackets();barrier,group,_played=model.playing();packet=group['native'];frames=packet['animation']['history']['frames']
            active=[frame for frame in frames if frame['overrideActive']]
            if fault=='call-only':packet['animation']['history'].update(frames=frames[:1],frameSequence=1)
            elif fault=='unloaded':
                for frame in active:frame['clip']['loadedFrames']=0
            elif fault=='frozen-clip':
                for frame in active:frame['clip']['frame']=10.
            elif fault in ('frozen-pose','antipodal-pose'):
                for index,frame in enumerate(active):
                    frame['joints']=deepcopy(active[0]['joints'])
                    if fault=='antipodal-pose' and index%2:frame['joints'][0]['pose'][:4]=[0.,0.,0.,-1.]
                packet['animation']['joints']=[deepcopy(row['pose']) for row in active[-1]['joints']]
            elif fault=='foreign':
                for frame in active:frame['clip']['url']='file:///foreign/Waving.fbx'
            else:
                for frame in active:frame['clip']['requestedUrl']='file:///foreign/Waving.fbx'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):playback(group,barrier,pid=31,epoch=20000)
    def test_old_foreign_or_missing_originals_cannot_be_relabelled_current(self):
        for fault in ('missing','nonce','pid','birth','root','rig','history','old','code-after-event','superseded'):
            model=RigPackets();barrier,group,_played=model.playing();packet=group['native']
            if fault=='missing':group['native']=None
            elif fault=='nonce':packet['requestId']=None
            elif fault=='pid':packet['processId']=32
            elif fault=='birth':packet['instance']='f'*32
            elif fault=='root':group['rootsAfter']['source']['defaultScriptsUrl']='file:///foreign/scripts'
            elif fault=='rig':packet['animation']['rigId']=3;packet['animationFence']['rigId']=3
            elif fault=='history':packet['animation']['history']['instance']='f'*32
            elif fault=='old':packet['animation']['capturedEpochMs']=19000
            elif fault=='code-after-event':group['script']['source']['engines'][0]['code']['submittedEpochMs']=19500
            else:packet['animation']['history']['overrideSequence']=2
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):playback(group,barrier,pid=31,epoch=20000)
    def test_restore_without_later_inactive_evaluation_or_with_live_override_is_red(self):
        model=RigPackets();_barrier,_group,played=model.playing()
        packet=model.native(21010,restore_epoch=21000);packet['animation']['history']['frames'].pop()
        packet['animation']['history']['frameSequence']-=1
        with self.assertRaises(NativeUIError):restoration(model.group(packet),played,pid=31,epoch=21010)
        model=RigPackets();_barrier,_group,played=model.playing()
        with self.assertRaises(NativeUIError):restoration(model.group(model.native(20100,active=True)),played,pid=31,epoch=20100)
    def test_already_restored_before_the_input_cannot_prove_cancel(self):
        model=RigPackets();_barrier,_group,played=model.playing();before=model.native(21010,restore_epoch=21000)
        current=model.native(21100,restore_epoch=21000)
        with self.assertRaises(NativeUIError):restoration(model.group(current),played,pid=31,epoch=21100,native_barrier=before)
    def test_tampered_cached_proof_boolean_or_changed_source_manager_is_not_adopted(self):
        model=RigPackets();_barrier,_group,played=model.playing();current=model.group(model.native(21010,restore_epoch=21000))
        changed=deepcopy(played);changed['state']['override']=1
        with self.assertRaises(NativeUIError):restoration(current,changed,pid=31,epoch=21010)
        current['script']['source']['engines'][0]['required']['instance']='f'*32
        current['script']['source']['membership']['managers'][0]['instance']='f'*32
        with self.assertRaises(NativeUIError):restoration(current,played,pid=31,epoch=21010)


if __name__=='__main__':unittest.main()
