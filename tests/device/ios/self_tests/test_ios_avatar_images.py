"""Synthetic native/GPU seams with actual PNG and strict original validation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import unittest
import uuid
from PIL import Image,ImageDraw
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_images as images
from ios.self_tests import test_ios_emote_images as frozen
from ios.self_tests.test_ios_graphics_measurements import NATIVE,RUN,TICKET,BINDING
from ios.self_tests.test_ios_avatar_renderers import packet as renderer_packet,SELF,PEER

NONCE,MARKER_URL=frozen.NONCE,frozen.MARKER_URL


def seal(frame):
    originals=images.originals(frame);frame['clockJoin']['originalsSha256']=digest(originals)
    frame['clockJoin']['sourceTimes']=[dict(source=name,field=field,epochMs=row[field]) for name,row in originals.items()
        for field in ('capturedEpochMs','sampleEpochMs') if field in row]


def bundle(*,start=0,ticket=TICKET,change=False,remote=False,unavailable=False,uniform=False):
    frame,raw,policy=frozen.bundle(start=start,ticket=ticket,change=change);cursor=start//1000*2
    for key in ('worldBefore','worldAfter'):
        value=frame[key];value['iosAvatarWorldVersion']=value.pop('iosEmoteWorldVersion');value['clockDomain']='native-main-avatar-world'
        for row in (value['source']['markers'][0],value['source']['scriptOriginal']['source']['effects']['entities'][0]):
            data=json.loads(row['userData']);data['kind']='avatar-marker-v1';row['userData']=json.dumps(data)
        value['source']['domain']['selfSha256']=hashlib.sha256(uuid.UUID(SELF).bytes).hexdigest()
        bodies=[dict(sessionId=identity,self=identity==SELF,replicated=False,position=[0,0,-4] if (identity==PEER)==remote else [5,0,-4],
            orientation=[0,0,0,1],velocity=[0,0,0]) for identity in (SELF,PEER)]
        value['source']['bodies']=dict(avatarBodyCollectionVersion=1,instance='a'*32,sequence=value['sequence'],
            capturedEpochMs=value['clockAfter']['epochMs'],complete=True,avatars=bodies)
        if remote:value['source']['avatar'].update(feetPosition=[5,0,-4],bounds=dict(corner=[5,0,-4.5],dimensions=[1,1.8,1]))
        if unavailable and not remote:value['source']['avatar'].update(boundsReady=False,bounds=None)
    for index,(key,offset) in enumerate((('renderersBefore',40),('renderersAfter',300))):
        value=renderer_packet();value.update(runId=RUN,requestId='ios-'+format(cursor+index+9001,'032x'),sequence=cursor+index+1)
        value['clockBefore']=dict(epochMs=NATIVE+start+offset,monotonicMs=start+offset);value['clockAfter']=deepcopy(value['clockBefore'])
        for row in value['source']['avatars']:
            target=(not row['self']) is remote
            row['bounds']=dict(corner=[-.5,0,-4.5] if target else [5,0,-4.5],dimensions=[1,1.8,1])
            if row['rigPose']:row['rigPose'].update(capturedEpochMs=NATIVE+start+offset,evaluationSequence=100+cursor+index)
            if row['externalPose']:row['externalPose'].update(capturedEpochMs=NATIVE+start+offset,evaluationSequence=10+cursor+index,
                totalJoints=3,joints=[[0,0,0,1,0,0,0] for _ in range(3)])
            if target and unavailable:row.update(geometryLoaded=False,rigReady=False,addedToScene=False,boundsReady=False,bounds=None)
        frame[key]=value
    if uniform:
        image=Image.open(BytesIO(raw)).convert('RGBA');draw=ImageDraw.Draw(image);draw.rectangle((290,200,349,329),fill=(20,20,20,255))
        stream=BytesIO();image.save(stream,format='PNG');raw=stream.getvalue()
        frame['capture']['source']['image'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
    seal(frame);return frame,raw,policy


class AvatarImagesTests(unittest.TestCase):
    def compose(self,frame,raw,policy,*,ticket=TICKET,remote=False,basis=None):
        return images.compose(RUN,ticket,BINDING,frame,raw,policy,marker_nonce=NONCE,marker_url=MARKER_URL,
            avatar_id=PEER if remote else None,absence_basis=basis)

    def test_real_png_native_gpu_and_actual_self_or_remote_mesh_body_are_joined(self):
        for remote in (False,True):
            frame,raw,policy=bundle(remote=remote);value,subject=self.compose(frame,raw,policy,remote=remote)
            self.assertEqual((128,96),subject.size);self.assertTrue(value['modelLoaded']);self.assertIs(remote,value['remote'])
            self.assertEqual(PEER if remote else SELF,value['sessionId']);self.assertEqual('current-rendered-avatar',value['subjectBoundsSource'])

    def test_other_avatar_overlap_unknown_body_or_incomplete_gpu_never_supplies_subject(self):
        for fault in ('overlap','body','position','gpu','camera','geometry'):
            frame,raw,policy=bundle(remote=True)
            if fault=='overlap':
                for key in ('renderersBefore','renderersAfter'):frame[key]['source']['avatars'][0]['bounds']=deepcopy(frame[key]['source']['avatars'][1]['bounds'])
            elif fault=='body':del frame['worldAfter']['source']['bodies']
            elif fault=='position':frame['worldAfter']['source']['bodies']['avatars'][1]['position'][0]+=.1
            elif fault=='gpu':frame['retirement']['source']['gpuBufferBytes']=1
            elif fault=='camera':frame['capture']['source']['renderTrace']['recordedView']['position'][0]+=.1
            else:frame['renderersAfter']['source']['avatars'][1].update(boundsReady=False,bounds=None)
            seal(frame)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,AssertionError)):self.compose(frame,raw,policy,remote=True)

    def test_actual_unavailable_model_uses_only_retained_prior_volume_and_honest_uniform_background(self):
        for remote in (False,True):
            before,old_raw,policy=bundle(remote=remote);frame,raw,_=bundle(start=1000,ticket='f'*32,remote=remote,unavailable=True,uniform=True)
            with self.subTest(remote=remote):
                value,_subject=self.compose(frame,raw,policy,ticket='f'*32,remote=remote,basis=(before,old_raw,TICKET))
                self.assertFalse(value['modelLoaded']);self.assertIsNone(value['actualAvatarBounds'])
                self.assertEqual('previously-rendered-avatar',value['subjectBoundsSource'])
                self.assertEqual(before['capture']['source']['renderTrace']['frameId'],value['basisFrameId'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(),value['image']['sha256'])
                with self.assertRaises(NativeUIError):self.compose(frame,raw,policy,ticket='f'*32,remote=remote)

    def test_unknown_current_geometry_cannot_reuse_old_volume_if_still_in_scene_or_body_moved(self):
        for fault in ('inScene','moved','scaled','oldPixels','oldPixelsWithNewEnvelope'):
            before,old_raw,policy=bundle();frame,raw,_=bundle(start=1000,ticket='f'*32,unavailable=True,uniform=True)
            if fault=='inScene':
                for key in ('renderersBefore','renderersAfter'):frame[key]['source']['avatars'][0]['addedToScene']=True
            elif fault=='moved':
                for key in ('worldBefore','worldAfter'):frame[key]['source']['bodies']['avatars'][0]['position'][0]+=.1
            elif fault=='scaled':
                for key in ('renderersBefore','renderersAfter'):frame[key]['source']['avatars'][0]['modelScale']=1.5
            else:
                raw=old_raw
                if fault=='oldPixelsWithNewEnvelope':frame['capture']['source']['image']=deepcopy(before['capture']['source']['image'])
            seal(frame)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,AssertionError)):
                self.compose(frame,raw,policy,ticket='f'*32,basis=(before,old_raw,TICKET))

    def test_marker_change_is_not_avatar_change_and_actual_changed_subject_pixels_are(self):
        before,old_raw,policy=bundle();after,new_raw,_=bundle(start=1000,ticket='f'*32)
        kwargs=dict(marker_nonce=NONCE,marker_url=MARKER_URL)
        with self.assertRaises(AssertionError):images.changed(RUN,BINDING,before,old_raw,TICKET,after,new_raw,'f'*32,policy,**kwargs)
        after,new_raw,_=bundle(start=1000,ticket='f'*32,change=True)
        value=images.changed(RUN,BINDING,before,old_raw,TICKET,after,new_raw,'f'*32,policy,**kwargs)
        self.assertGreater(value['subjectChangedFraction'],.5)
        for key in ('worldBefore','worldAfter'):after[key]['source']['domain']['domainId']='11111111-2222-4111-8111-111111111111'
        seal(after)
        with self.assertRaises(NativeUIError):images.changed(RUN,BINDING,before,old_raw,TICKET,after,new_raw,'f'*32,policy,**kwargs)


if __name__=='__main__':unittest.main()
