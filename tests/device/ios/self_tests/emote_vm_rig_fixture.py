"""Passive modeled Rig originals driven by actual persistent JS VM callbacks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from adapters.native_feature_observation import NativeFeatureObservation
from self_tests.test_native_feature_observation import Boundary as Features
from self_tests.test_emote_rig_measurements import RigPackets
from self_tests.test_emote_source_profile import actual


class ActualVMRig(RigPackets):
    def __init__(self,vm,clock,*,pose_profile='legacy-one-second'):
        if type(pose_profile) is not str or pose_profile not in ('legacy-one-second','requested-clip'):
            raise ValueError('Unknown declared modeled Rig pose profile')
        self.pose_profile=pose_profile
        super().__init__(root=vm.root);self.vm,self.clock=vm,clock
        self.root_reader=self.roots.reader(ios=True)
        self.code,self.code_reader=actual(vm.pin,root=vm.root+'/');observed=self.code.mutate
        self.code.engine['required'].update(sequence=0,modules=[]);self.augment=None
        self.code_reader=self.code.reader(ios=True)
        def original(value):
            observed(value);value.update(instance='a'*32,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch)
            value['source'].update(membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[self.manager()]))
            value['source'].update(loadSourceVersion=1,loads=dict(complete=True,instance='9'*32,sequence=0,events=[]),
                effectSourceVersion=1,effects=dict(complete=True,scanRadiusMeters=64,scannedEntities=0,entities=[],absentIds=[]))
            if self.augment is not None:self.augment(value)
        self.code.mutate=original;self.code_reader.clock_ms=lambda:self.epoch
        self.sequence=0;self.frames=[];self.frame_sequence=0;self.value=None
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1)

    def manager(self):
        return dict(instance=self.code.engine['required']['instance'],assigned=True,url=self.code.engine['url'],loadGeneration=1,assignedEpochMs=14000)

    def calls(self):
        events=[];override=0
        for index,call in enumerate(self.vm.state['events'],1):
            kind='override' if call['method']=='overrideAnimation' else 'restore'
            if kind=='override':override+=1
            caller=dict(callerVersion=1,method=call['method'],sequence=index,invokedEpochMs=call['epochMs'],manager=self.manager(),
                code=dict(submitted=True,encoding=self.vm.pin['encoding'],codeUnits=self.vm.pin['codeUnits'],sha256=self.vm.pin['sha256'],submittedEpochMs=15000))
            event=dict(eventSequence=index,kind=kind,overrideSequence=override,capturedEpochMs=call['epochMs'],caller=caller)
            if kind=='override':event['request']=deepcopy(call['request'])
            events.append(event)
        return events,override

    def send(self,query):
        self.clock.sleep(.005);self.epoch=self.roots.epoch=self.clock.epoch();self.vm.advance(self.epoch);self.sequence+=1;self.frame_sequence+=1
        events,override=self.calls();playing=bool(events and events[-1]['kind']=='override')
        current=events[-1] if playing else None
        progress=0. if current is None else min(1.,(self.epoch-current['capturedEpochMs'])/1000.)
        if current is not None and self.pose_profile=='requested-clip':
            # This declared host model moves through the actual requested clip;
            # the ordinary JS VM still owns its unchanged restore timer.
            request=current['request']
            duration_ms=1000.*(request['lastFrame']-request['firstFrame'])/request['framesPerSecond']
            progress=min(1.,(self.epoch-current['capturedEpochMs'])/duration_ms)
        pose=[0.,0.,0.,1.,.1+progress*.4,.2,.3]
        poses=[pose,[0.,0.,0.,1.,0.,0.,0.],[0.,0.,0.,1.,0.,0.,0.]]
        frame=dict(frameSequence=self.frame_sequence,overrideSequence=override,evaluationSequence=100+self.frame_sequence,
            capturedEpochMs=self.epoch,overrideActive=playing,joints=[dict(index=index,pose=deepcopy(value)) for index,value in enumerate(poses)])
        if playing:
            request=current['request'];frame['clip']=dict(request,requestedUrl=request['url'],
                frame=min(request['lastFrame'],(self.epoch-current['capturedEpochMs'])*request['framesPerSecond']/1000.),
                loadedFrames=self.vm.loaded_frames(request['url']),evaluatedEpochMs=self.epoch,evaluationSequence=100+self.frame_sequence)
        self.frames.append(frame);self.frames=self.frames[-32:]
        source=Features();source.sequence=self.sequence-1
        def original(value):
            value.update(instance='a'*32,processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch)
            value['lifecycle']=deepcopy(self.lifecycle)
            value['animationFence']=dict(rigId=2,sequence=99+self.frame_sequence,requestedEpochMs=self.epoch)
            animation=value['animation'];animation.update(rigId=2,capturedEpochMs=self.epoch,evaluationSequence=100+self.frame_sequence,
                overrideActive=playing,joints=deepcopy(poses),history=dict(historyVersion=2,instance='e'*32,available=True,
                    callSequence=len(events),overrideSequence=override,frameSequence=self.frame_sequence,droppedEvents=max(0,len(events)-64),
                    droppedFrames=self.frame_sequence-len(self.frames),events=deepcopy(events[-64:]),frames=deepcopy(self.frames)))
            if playing:animation['clip']=deepcopy(frame['clip'])
            else:animation.pop('clip',None)
        source.mutate=original;source.send(query);self.value=deepcopy(source.sample)

    def reader(self):
        return NativeFeatureObservation(self.send,lambda:json.dumps(self.value),self.clock.epoch,lambda:True,31,ios=True,native_clock_bound=True,
            monotonic=lambda:self.clock.time,sleep=self.clock.sleep)
