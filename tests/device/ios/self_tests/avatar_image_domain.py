"""Actual PNG owners and original-source joins over explicit native producers.

The modeled renderer paints actual modeled mesh bounds and the unchanged
challenge PNG fetched from the controlled HTTPS service. Pixels are never
replaced or retimed after a native frame has been emitted or retained.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from types import SimpleNamespace
import uuid
from unittest.mock import patch
from urllib.request import Request
from PIL import Image,ImageDraw
from adapters.graphics_subject_geometry import projected_box
from adapters.native_avatar_receive import NativeAvatarReceive
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame
from ios.adapters.avatar_peer import session_sha
from ios.self_tests.avatar_social_domain import SocialDomain,RUN,SESSIONS
from ios.self_tests import emote_marker_domain_fixture as marker_native
from ios.self_tests import test_ios_avatar_renderers as renderer_fixture
from self_tests.test_native_avatar_receive import record
from self_tests.test_native_vulkan_world_frame import World as GPU
from self_tests.test_native_completed_frame import view as native_view


class ImageDomain(SocialDomain):
    def __init__(self,test):
        super().__init__(test);outer=self;self.positions=dict(primary=[0,0,4],actor=[1.5,0,4])
        for role,scene in self.scenes.items():
            d,f,n=scene.domain,scene.f,self.natives[role];position=self.positions[role]
            d.world_template['source']['avatar']['feetPosition']=deepcopy(position);d.world_template['source']['view']['position']=[position[0],1.6,8];d.world_template['source']['domain']['avatarMixerSha256']='c'*64
            start=d.start
            def starting(old=start,role=role):
                point=outer.positions[role];literal='MyAvatar:{position:{x:0,y:0,z:4}'
                replacement='MyAvatar:{position:'+json.dumps(dict(zip(('x','y','z'),point)),separators=(',',':'))
                assert literal in marker_native.PROGRAM
                with patch.object(marker_native,'PROGRAM',marker_native.PROGRAM.replace(literal,replacement)):return old()
            d.start=starting
            world=d.world
            def current_world(run,old=world,role=role,d=d):
                value=old(run);own=outer.mesh(role);value['source']['avatar'].update(modelScale=own['scale'],boundsReady=True,bounds=deepcopy(own['bounds']))
                bodies=value['source']['bodies'];bodies['avatars']=[dict(sessionId=SESSIONS[subject],self=subject==role,replicated=False,
                    position=deepcopy(outer.positions[subject]),orientation=[0,0,0,1],velocity=[0,0,0]) for subject in ('primary','actor')]
                return value
            d.world=current_world;scene.scope.world.read=current_world
            old_model=f.mutate
            def model(name,value,old=old_model,role=role):
                old(name,value)
                if name!='renderers':return
                source=value['source']
                for row in source['avatars']:
                    subject=next(subject for subject,identity in SESSIONS.items() if identity==row['sessionId']);mesh=outer.mesh(subject)
                    row.update(requestedUrl=mesh['requested'],resourceUrl=mesh['resource'],modelScale=mesh['scale'],targetScale=mesh['scale'],
                        geometryLoaded=True,rigReady=True,addedToScene=True,shouldRender=True,boundsReady=True,bounds=deepcopy(mesh['bounds']))
                    if row['self']:
                        row['externalPose']=None
                        if row['rigPose'] is None:row['rigPose']=deepcopy(renderer_fixture.packet()['source']['avatars'][0]['rigPose'])
                        row['rigPose'].update(capturedEpochMs=value['clockAfter']['epochMs'],evaluationSequence=value['sequence']+100)
                    else:
                        row['rigPose']=None;row['externalPose']=dict(externalPoseVersion=1,instance='d'*32,rigId=124,
                            capturedEpochMs=value['clockAfter']['epochMs'],evaluationSequence=value['sequence']+100,totalJoints=3,
                            joints=[[0,0,0,1,0,0,0] for _ in range(3)])
                # Both local trees contain the genuinely owned primary wearable
                # after its actual normal creation and actual received state.
                primary=outer.widgets['primary']
                if primary.wearable_id and not any(row['id']==primary.wearable_id for row in source['avatarEntities']):
                    previous=deepcopy(source['tree']['entities']);renderer_fixture.attach(value)
                    source['avatarEntities'][-1].update(id=primary.wearable_id,parentId=SESSIONS['primary'],modelUrl=primary.wearable_url,resourceUrl=primary.wearable_url)
                    source['tree']['entities'][-1]['id']=primary.wearable_id
                    source['tree']['entities']=sorted(previous+source['tree']['entities'],key=lambda row:row['id']);source['tree']['totalEntities']=len(source['tree']['entities'])
                # The tree revision belongs to both actual local marker and
                # remote avatar-entity changes, even in the Actor's process.
                source['tree']['revisionBefore']+=primary.entity_revision;source['tree']['revisionAfter']+=primary.entity_revision
            f.mutate=model
            scene.vulkan=lambda intent,receipt,role=role:self.vulkan(role,intent,receipt)
            # Configuration is input only, set before any original admission.
            policy=dict(source='world-render-target',marker=[706,480,864,520],subject=[775,550,825,700] if role=='primary' else [450,550,500,700])
            self.owners[role].policy=policy
        base=type(self.runtime)
        class Runtime(base):
            def _avatar_receive(_self,selector):
                receiver=outer.receivers[selector];n=outer.natives[selector];other='actor' if selector=='primary' else 'primary'
                def send(query):
                    outer.clock[0]+=.001;mesh=outer.mesh(other);index=len(receiver.records)+1;row=record(index,0.)
                    payload=json.dumps(dict(sessionId=SESSIONS[other],url=mesh['requested'],scale=mesh['scale'],joints=[[0,0,0,1,0,0,0] for _ in range(3)]),sort_keys=True).encode()
                    row.update(capturedEpochMs=n.epoch(),avatarSha256=session_sha(SESSIONS[other]),mixerSha256='c'*64,recordSha256=hashlib.sha256(payload).hexdigest(),
                        recordBytes=len(payload),jointCount=3,joints=[dict(index=i,rotation=[0,0,0,1],translation=[0,0,0]) for i in range(3)],advertisedModelUrl=mesh['requested'],targetScale=mesh['scale'])
                    receiver.records.append(row);receiver.send(query);value=receiver.current
                    value.update(processId=31,requestedEpochMs=n.epoch(),capturedEpochMs=n.epoch());value['source'].update(processId=31,selfSha256=session_sha(SESSIONS[selector]),
                        droppedRecords=max(0,len(receiver.records)-32),records=deepcopy(receiver.records[-32:]))
                return NativeAvatarReceive(send,lambda:json.dumps(receiver.current),n.epoch,lambda:True,31,ios=True,monotonic=lambda:outer.clock[0],sleep=outer.sleep)
        self.runtime.__class__=Runtime
    def mesh(self,role):
        w=self.widgets[role];p=self.positions[role];scale=w.scale
        resource=self.scenes[role].f.prototypes['state']['source']['defaultResourceUrl'] if w.avatar_url.endswith('/missing.fst') else w.avatar_url
        return dict(requested=w.avatar_url,resource=resource,scale=scale,
            bounds=dict(corner=[p[0]-.3*scale,p[1],p[2]-.3*scale],dimensions=[.6*scale,1.8*scale,.6*scale]))
    def peer_world(self,selector,run):
        d=self.scenes[selector].domain;value=d.world(run)
        # This is the original common getter's other closed native profile:
        # all world/script/tree originals, with its literal Emote marker filter.
        # No saved observation is changed; this is a native producer boundary.
        sequence=self.peer_sequences[selector]+1;self.peer_sequences[selector]=sequence
        value.pop('iosAvatarWorldVersion');value['iosEmoteWorldVersion']=1;value['clockDomain']='native-main-emote-world'
        value.update(sequence=sequence,requestId='ios-'+uuid.uuid4().hex);value['source'].pop('bodies');value['source']['markers']=[]
        value['source']['domain']['avatarMixerSha256']='c'*64;return value
    def recorded_view(self,role):
        value=native_view();actual=self.scenes[role].domain.world_template['source']['view']
        for key in value:
            if key in actual:value[key]=deepcopy(actual[key])
        return value
    def paint(self,role):
        scene=self.scenes[role];d=scene.domain;view=self.recorded_view(role);extent=[1600,1000]
        image=Image.new('RGBA',extent,(75,85,100,255));draw=ImageDraw.Draw(image)
        for subject in ('primary','actor'):
            mesh=self.mesh(subject);bounds=mesh['bounds'];box=projected_box(dict(position=[a+b/2 for a,b in zip(bounds['corner'],bounds['dimensions'])],
                dimensions=bounds['dimensions'],rotation=[0,0,0,1]),view,extent)
            digest=hashlib.sha256((mesh['resource']+str(mesh['scale'])).encode()).digest()
            for y in range(max(0,int(box[1])),min(extent[1],int(box[3])),8):
                for x in range(max(0,int(box[0])),min(extent[0],int(box[2])),8):
                    draw.rectangle((x,y,min(int(box[2]),x+7),min(int(box[3]),y+7)),fill=tuple(digest[:3] if (x//8+y//8)%2 else digest[3:6])+(255,))
            if self.widgets[subject].wearable_id:
                center=(int((box[0]+box[2])/2),int((box[1]+box[3])/2));draw.rectangle((center[0]-30,center[1]-30,center[0]+30,center[1]+30),fill=(250,10,180,255))
        if d.running or scene.stale_pixels:
            box=projected_box(d.marker,view,extent)
            with self.opener.open(Request(self.origin+'/feature-fixture/v1/runs/'+RUN+'/current'),timeout=5) as response:status=json.loads(response.read(65537))
            ticket=status['ticket']
            request=Request(self.origin+'/feature-fixture/v1/runs/'+RUN+'/tickets/'+ticket+'/marker.png')
            with self.opener.open(request,timeout=5) as response:raw=response.read(65537)
            marker=Image.open(BytesIO(raw)).convert('RGBA').resize((round(box[2]-box[0]),round(box[3]-box[1])),Image.Resampling.NEAREST)
            image.paste(marker,(round(box[0]),round(box[1])))
        return image
    def vulkan(self,role,intent,receipt):
        scene=self.scenes[role];d=scene.domain;n=self.natives[role];current=[None];outer=self
        def sending(query):
            request=query['requestId']
            if request not in scene.gpus:
                class SharedGPU(GPU):
                    @property
                    def clock(_self):return outer.clock[0]
                    @clock.setter
                    def clock(_self,value):outer.clock[0]=value
                previous=self.clock[0];gpu=SharedGPU();self.clock[0]=previous
                gpu.sequence=scene.gpu_sequence;gpu.source_extent=[640,400];gpu.target_extent=[1600,1000];gpu.offset=scene.native_epoch_offset;gpu.epoch=n.epoch
                def observed(value):
                    value['processId']=31
                    if 'image' in value.get('source',{}):value['source']['image'].update(width=1600,height=1000)
                    if 'renderTrace' in value.get('source',{}):
                        trace=value['source']['renderTrace'];trace['frameId']=request[4:]
                        trace['recordedView']=outer.recorded_view(role)
                gpu.fault=observed;scene.gpus[request]=gpu
            current[0]=scene.gpus[request];image=self.paint(role);out=BytesIO();image.save(out,format='PNG');current[0].png=out.getvalue();current[0].raw_pixels=image.tobytes()
            current[0].send(query);scene.gpu_sequence=max(scene.gpu_sequence,current[0].sequence)
        def reading():return current[0].original()
        return NativeVulkanWorldFrame(sending,reading,n.epoch,lambda:True,31,intent,receipt=receipt,monotonic=lambda:self.clock[0],sleep=self.sleep)
