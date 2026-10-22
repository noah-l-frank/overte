"""Exact private source/PNG ownership, using existing bounded evidence engines."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from overte_phone_emote_originals import PhoneEmoteOriginals
from overte_phone_navigation_feature import NavigationImages
from overte_phone_lifecycle_measurements import validate_sources,continuity_sources
from feature_journeys.phase_fixture import validate as phase_packet


class LifecycleOriginals(PhoneEmoteOriginals):
    # Internal archive vocabulary is separate from the public state contract.
    KINDS=frozenset({'lifecycle'})


class LifecycleEvidence:
    def __init__(self,flow,state,role):self.flow,self.state,self.role=flow,state,role
    def original(self):
        def intent(kind,value):
            self.state[kind+'Intent']=deepcopy(value);self.flow.save_role(self.state,self.role)
        # Historical inode/byte validation supplies no current target sample.
        # Keep it local under the exact owning OS lock, without O(history)
        # SDK/ADB round trips. Fresh source acquisitions retain every original
        # candidate/process/foreground/session guard before and after I/O.
        return LifecycleOriginals(self.flow.root,self.state['binding'],self.flow.run,self.role,
            self.flow.lock.assert_held,intent,kind='lifecycle',monotonic=self.flow.monotonic)
    def frames(self):
        return self.original().restore(self.state['manifests'],self.state['sequence'])
    def recover(self):
        pending=self.state['pending']
        if pending is None:return
        # Frozen original acquisition is archival input, never a fresh sample.
        if pending['frame'] is not None:
            frame=pending['frame'];original=self.original();index=self.state['sequence']+1
            ref=original.write(index,frame) if self.state['originalIntent'] is None else original.resume_write(index,frame,self.state['originalIntent'])
            self.state['manifests']=original.resume_manifest(self.state['manifests'],ref,self.state['manifestIntent'])
            self.state['sequence']=index
        if self.state['imageIntent'] is not None and self.state['imageIntent']['phase']!='saved':
            NavigationImages.retire_partial(self.flow.root,self.state['imageIntent'])
        elif self.state['imageIntent'] is not None:
            NavigationImages.archive(self.flow.root,self.state['imageIntent'])
        # A capture interrupted before its exact frame was frozen is retained
        # as its own immutable diagnostic, never silently lost from retirement.
        if pending['frame'] is None and self.state['imageIntent'] is not None:
            need(len(self.state['abandoned'])<256);self.state['abandoned'].append(deepcopy(self.state['imageIntent']))
        self.state.update(pending=None,originalIntent=None,manifestIntent=None,imageIntent=None)
        self.flow.save_role(self.state,self.role)
    def append(self,frame):
        need(self.state['pending'] is not None and self.state['sequence']<256)
        self.state['pending']['frame']=deepcopy(frame);self.flow.save_role(self.state,self.role);self.recover()
    def verify(self):
        need(self.state['pending'] is None and self.state['originalIntent'] is None and self.state['manifestIntent'] is None and self.state['imageIntent'] is None)
        frames=self.frames()
        previous=None;quiet=[]
        for frame in frames:
            sources=frame['sources'];pid=int(self.state['binding']['processIdentity'].split(':')[0]);epoch=max(v['capturedEpochMs'] for v in sources.values())
            validate_sources(self.flow.run,sources,pid,epoch)
            if previous is not None:continuity_sources(previous,sources,pid)
            previous=sources;phase=frame['phase']
            phase_packet(phase,run=self.flow.run,area='lifecycle-input',request=phase['requestId'],epoch=phase['capturedEpochMs'])
            if phase['activations'] and phase['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}):quiet.append(frame)
            if frame['image'] is not None:NavigationImages.archive(self.flow.root,frame['image'])
        for image in self.state['abandoned']:
            if image['phase']=='saved':NavigationImages.archive(self.flow.root,image)
            else:NavigationImages.retire_partial(self.flow.root,image)
        window=self.state['quiet'];need(window is not None and window['complete'] and len(quiet)>=3)
        first,last=quiet[0]['sources'],quiet[-1]['sources'];need(first['editor']['capturedEpochMs']==window['firstEpochMs']
            and last['editor']['capturedEpochMs']-first['editor']['capturedEpochMs']>=3000 and window['samples']==len(quiet))
        for frame in quiet:
            need(frame['ticket']==window['ticket']);self.flow.neutral(frame['sources'],frames[0]['sources']['world']['motion']['feetPosition'])
        if self.role=='actor':need(self.state['closed'] is not None and not self.state['closed']['active'] and quiet[-1]['phase']==self.state['closed'])
        return frames
