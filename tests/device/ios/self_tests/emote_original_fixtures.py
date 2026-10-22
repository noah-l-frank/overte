"""Synthetic original source archives shared by Emote host tests only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.emote_controls import project
from ios.adapters.emote_sources import IOSEmoteSources
from ios.self_tests.test_ios_emote_controls import NativeBoundary
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,phase
from ios.self_tests.test_ios_emote_world import packet as world_packet
from self_tests.test_emote_rig_measurements import RigPackets


class Originals:
    def __init__(self,root,lock,name='Waving',role='primary'):
        self.root,self.lock=root,lock;self.model=RigPackets(name);self.widget=NativeBoundary()
        self.owner=IOSEmoteSources(PrivateFeatureState(root/('ios-emote-'+role+'-sources.json')),root,BINDING,RUN,role,lock,
            lambda:True,None,historical=True);self.owner.historical=False;self.owner.save()
    def append(self,epoch,*,baseline=False,active=False,restore_epoch=None,domain=None,phase_offset=0):
        model=self.model;before=model.native(epoch,baseline=baseline,active=active,restore_epoch=restore_epoch)
        group=model.group(model.native(epoch,baseline=baseline,active=active,restore_epoch=restore_epoch))
        after=model.native(epoch,baseline=baseline,active=active,restore_epoch=restore_epoch)
        self.widget.tablet=self.widget.page=not baseline;self.widget.active=('Sit' if model.name.startswith('Sit') else model.name) if active else ''
        widgets=self.widget.capture();widgets['sampleEpochMs']=epoch
        if widgets['controls']:
            import hashlib
            [r for r in widgets['controls'] if r['id']=='emote.page'][0]['componentSourceSha256']=hashlib.sha256(
                (model.roots.root+'/system/+android_phoneInterface/PhoneEmote.qml').encode()).hexdigest()
        world=world_packet();world['sequence']=len(self.owner.frames)+1;world['requestId']='ios-'+format(9000+world['sequence'],'032x')
        if domain is not None:world['source']['domain'].update(domain)
        world['source']['scriptOriginal']['source']['effects']['entities'][0]['lastEditedEpochUs']=18000000
        world['source']['markers'][0]['lastEditedEpochUs']='18000000'
        for row in world['source']['tree']['entities']:
            for key in ('createdEpochUs','lastEditedEpochUs','lastEditedAfterEpochUs'):row[key]='18000000'
        for key in ('clockBefore','clockAfter'):world[key]=dict(epochMs=epoch,monotonicMs=epoch-18000)
        world['source']['scriptOriginal'].update(requestedEpochMs=epoch,capturedEpochMs=epoch)
        originals=dict(group,widgets=widgets,world=world);host=90000+epoch-18800;mono=1+(epoch-18800)/1000
        join=dict(clockJoinVersion=1,hostBeforeEpochMs=host,hostAfterEpochMs=host,hostBeforeMonotonic=mono,hostAfterMonotonic=mono,
            nativeBefore=before,nativeAfter=after,originalsSha256=digest(originals),sourceTimes=[dict(source=n,field=f,epochMs=p[f])
                for n,p in originals.items() for f in ('capturedEpochMs','sampleEpochMs') if f in p])
        count=len(self.owner.frames);frame=dict(group=group,widgets=widgets,ui=project(widgets),world=world,clockJoin=join,
            phaseBefore=phase(count*2+1+phase_offset,host),phaseAfter=phase(count*2+2+phase_offset,host))
        self.owner.validate_frame(frame,self.owner.frames[-1] if self.owner.frames else None)
        self.owner.state.update(phase='reading',pending=dict(original=None,manifest=None,partial={}));self.owner.save()
        item=self.owner.originals.write(count+1,frame);refs=self.owner.originals.append(self.owner.state['manifests'],item)
        self.owner.frames.append(deepcopy(frame));self.owner.state.update(phase='ready',revision=count+1,manifests=refs,pending=None);self.owner.save()
        return dict(index=count+1,sha256=digest(frame))


