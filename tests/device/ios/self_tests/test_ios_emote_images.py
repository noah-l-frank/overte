"""Original PNG/geometry/GPU joins at synthetic native seams; no renderer run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import unittest
from PIL import Image,ImageDraw
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters import emote_images as images
from ios.self_tests.test_ios_emote_world import packet as world_packet,NONCE
from ios.self_tests.test_ios_graphics_world_measurements import world_bundle
from ios.self_tests.test_ios_graphics_measurements import NATIVE,HOST,RUN,TICKET,URL,BINDING
from ios.self_tests.test_ios_avatar_renderers import packet as renderers_packet,PEER,SELF
from ios.adapters.emote_peer import session_sha

MARKER_URL=URL+'tickets/'+TICKET+'/graphics-marker.v1.html'


def rebind(value):
    sources=images.originals(value);value['clockJoin']['originalsSha256']=digest(sources)
    value['clockJoin']['sourceTimes']=[dict(source=name,field=field,epochMs=row[field]) for name,row in sources.items()
        for field in ('capturedEpochMs','sampleEpochMs') if field in row]


def bundle(*,start=0,ticket=TICKET,change=False):
    original,raw,policy,_instance=world_bundle(start=start,ticket=ticket);policy['subject']=[290,200,350,330]
    geometry=next(r for r in original['subjectBefore']['source']['entities'] if r['type']=='Web')
    def world(sequence,offset):
        value=world_packet(42);value.update(runId=RUN,requestId='ios-'+format(sequence+5000,'032x'),sequence=sequence)
        for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=NATIVE+offset,monotonicMs=offset)
        source=value['source'];script=source['scriptOriginal'];script.update(requestedEpochMs=NATIVE+offset,capturedEpochMs=NATIVE+offset)
        marker=source['markers'][0];effect=script['source']['effects']['entities'][0]
        data=json.dumps(dict(kind='emote-marker-v1',runId=RUN,nonce=NONCE))
        marker.update(name='e2e-'+RUN+'-script',userData=data,sourceUrl=MARKER_URL,
            **{k:geometry[k] for k in ('position','rotation','dimensions')})
        effect.update(name=marker['name'],userData=data)
        source['avatar'].update(feetPosition=[0,0,-4],bounds=dict(corner=[-.5,0,-4.5],dimensions=[1,1.8,1]))
        source['domain']['selfSha256']=session_sha(SELF)
        source['view'].update(position=[0,1.6,0],rotation=[0,0,0,1],mode='look at',aspectRatio=1.6)
        return value
    cursor=start//1000*2
    result=dict(worldBefore=world(cursor+1,start+20),capture=original['capture'],retirement=original['retirement'],
        worldAfter=world(cursor+2,start+450),clockJoin=original['clockJoin'])
    for index,(key,offset) in enumerate((('renderersBefore',start+40),('renderersAfter',start+300))):
        packet=renderers_packet();packet.update(runId=RUN,requestId='ios-'+format(cursor+index+9000,'032x'),sequence=cursor+index+1)
        packet['clockBefore']=dict(epochMs=NATIVE+offset,monotonicMs=offset);packet['clockAfter']=deepcopy(packet['clockBefore'])
        for row in packet['source']['avatars']:
            if row['rigPose']:row['rigPose'].update(capturedEpochMs=NATIVE+offset,evaluationSequence=100+cursor+index)
            if row['externalPose']:row['externalPose'].update(capturedEpochMs=NATIVE+offset,evaluationSequence=10+cursor+index)
            row['bounds']=deepcopy(result['worldBefore']['source']['avatar']['bounds'])
            if not row['self']:row['bounds']['corner'][0]=20 # Actual modeled peer mesh outside this view.
        result[key]=packet
    if change:
        image=Image.open(BytesIO(raw)).convert('RGBA');draw=ImageDraw.Draw(image)
        for y in range(200,330,5):
            for x in range(290,350,5):draw.rectangle((x,y,x+4,y+4),fill=(240,30,20,255) if (x//5+y//5)%2 else (0,180,100,255))
        stream=BytesIO();image.save(stream,format='PNG');raw=stream.getvalue()
        result['capture']['source']['image'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
    rebind(result);return result,raw,policy


class ImagesTests(unittest.TestCase):
    def compose(self,value):
        frame,raw,policy=value
        return images.compose(RUN,TICKET,BINDING,frame,raw,policy,marker_nonce=NONCE,marker_url=MARKER_URL)

    def test_actual_world_target_pixels_geometry_and_full_gpu_retirement_join(self):
        sample=bundle();actual,subject=self.compose(sample)
        self.assertEqual(HOST,actual['capturedEpochMs']);self.assertEqual(NATIVE+20,actual['nativeEpochMs'])
        self.assertEqual((128,96),subject.size);self.assertIsNone(actual['remoteSessionId'])

    def test_requested_pixels_wrong_original_hash_foreign_camera_and_incomplete_gpu_retirement_fail(self):
        for fault in ('hash','pixelHash','camera','gpu','metadata','body','unknownBounds','subjectOutsideAvatar','markerOutsideEntity','worldEdit'):
            frame,raw,policy=bundle()
            if fault=='hash':frame['capture']['source']['image']['sha256']='f'*64
            elif fault=='pixelHash':frame['capture']['source']['image']['pixelSha256']='f'*64
            elif fault=='camera':frame['capture']['source']['renderTrace']['recordedView']['position'][0]+=.1
            elif fault=='gpu':frame['retirement']['source']['gpuBufferBytes']=4096
            elif fault=='metadata':frame['retirement']['source']['metadataBytes']=1024
            elif fault=='body':frame['worldAfter']['source']['avatar']['feetPosition'][0]+=.5
            elif fault=='unknownBounds':frame['worldAfter']['source']['avatar'].update(boundsReady=False,bounds=None)
            elif fault=='subjectOutsideAvatar':policy['subject']=[0,170,640,400]
            elif fault=='markerOutsideEntity':policy['marker']=[0,0,256,64]
            else:frame['worldAfter']['source']['tree']['entities'][0]['semanticSha256']='f'*64
            rebind(frame)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,AssertionError)):self.compose((frame,raw,policy))

    def test_marker_change_alone_is_not_changed_avatar_pixels_and_genuine_subject_change_is(self):
        before,raw_before,policy=bundle();after,raw_after,_=bundle(start=1000,ticket='f'*32)
        with self.assertRaises(AssertionError):images.changed(RUN,BINDING,before,raw_before,TICKET,after,raw_after,'f'*32,
            policy,marker_nonce=NONCE,marker_url=MARKER_URL)
        after,raw_after,_=bundle(start=1000,ticket='f'*32,change=True)
        value=images.changed(RUN,BINDING,before,raw_before,TICKET,after,raw_after,'f'*32,policy,marker_nonce=NONCE,marker_url=MARKER_URL)
        self.assertGreater(value['subjectChangedFraction'],.5)

    def test_challenge_crop_disjointness_cannot_hide_other_marker_pixels_in_avatar_roi(self):
        frame,raw,policy=bundle();policy['subject']=[290,135,350,138]
        # These are genuine modeled mesh bounds, deliberately including the
        # marker's lower projected pixels outside the selected challenge crop.
        for key in ('worldBefore','worldAfter'):frame[key]['source']['avatar']['bounds']['dimensions'][1]=4
        for key in ('renderersBefore','renderersAfter'):frame[key]['source']['avatars'][0]['bounds']['dimensions'][1]=4
        image=Image.open(BytesIO(raw)).convert('RGBA');draw=ImageDraw.Draw(image)
        for x in range(290,350):draw.line((x,135,x,137),fill=(250,10,20,255) if x%2 else (10,200,30,255))
        stream=BytesIO();image.save(stream,format='PNG');raw=stream.getvalue()
        frame['capture']['source']['image'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
        rebind(frame)
        with self.assertRaises(NativeUIError):images.compose(RUN,TICKET,BINDING,frame,raw,policy,marker_nonce=NONCE,marker_url=MARKER_URL)

    def remote(self):
        frame,raw,policy=bundle()
        for index,(key,offset) in enumerate((('renderersBefore',40),('renderersAfter',300))):
            packet=renderers_packet();packet.update(runId=RUN,requestId='ios-'+format(index+9000,'032x'),sequence=index+1)
            packet['clockBefore']=dict(epochMs=NATIVE+offset,monotonicMs=offset)
            packet['clockAfter']=dict(epochMs=NATIVE+offset,monotonicMs=offset)
            for row in packet['source']['avatars']:
                if row['rigPose']:row['rigPose'].update(capturedEpochMs=NATIVE+offset,evaluationSequence=100+index)
                if row['externalPose']:row['externalPose'].update(capturedEpochMs=NATIVE+offset,evaluationSequence=10+index)
                row['boundsReady']=True;row['bounds']=deepcopy(frame['worldBefore']['source']['avatar']['bounds'])
                if row['self']:row['bounds']['corner'][0]=20
            frame[key]=packet
        for key in ('worldBefore','worldAfter'):frame[key]['source']['avatar'].update(boundsReady=False,bounds=None)
        rebind(frame);return frame,raw,policy

    def test_actor_pixels_use_actual_remote_render_mesh_bounds_without_self_bbox_fallback(self):
        frame,raw,policy=self.remote();actual,_=images.compose(RUN,TICKET,BINDING,frame,raw,policy,
            marker_nonce=NONCE,marker_url=MARKER_URL,avatar_id=PEER)
        self.assertEqual(PEER,actual['remoteSessionId']);self.assertEqual([-.5,0,-4.5],actual['actualAvatarBounds']['corner'])
        for fault in ('self','legacy','unavailable','outside','foreignClock'):
            current=deepcopy(frame);avatar=PEER
            if fault=='self':avatar=SELF
            elif fault=='legacy':
                for key in ('renderersBefore','renderersAfter'):
                    current[key]['iosAvatarRenderersVersion']=3
                    for row in current[key]['source']['avatars']:row.pop('bounds');row.pop('boundsReady')
            elif fault=='unavailable':current['renderersAfter']['source']['avatars'][1].update(boundsReady=False,bounds=None)
            elif fault=='outside':current['renderersAfter']['source']['avatars'][1]['bounds']['corner'][0]+=1
            else:current['renderersAfter']['clockBefore']['epochMs']=NATIVE+80;current['renderersAfter']['clockAfter']['epochMs']=NATIVE+80
            rebind(current)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):images.compose(RUN,TICKET,BINDING,current,raw,policy,
                marker_nonce=NONCE,marker_url=MARKER_URL,avatar_id=avatar)

    def test_other_actual_rendered_avatar_cannot_supply_subject_pixels(self):
        for remote in (False,True):
            for fault in ('overlap','unknown'):
                frame,raw,policy=self.remote() if remote else bundle()
                for key in ('renderersBefore','renderersAfter'):
                    other=frame[key]['source']['avatars'][0 if remote else 1]
                    if fault=='overlap':other['bounds']=deepcopy(frame[key]['source']['avatars'][1 if remote else 0]['bounds'])
                    else:other.update(boundsReady=False,bounds=None)
                rebind(frame)
                with self.subTest(remote=remote,fault=fault),self.assertRaises(NativeUIError):images.compose(RUN,TICKET,BINDING,frame,raw,policy,
                    marker_nonce=NONCE,marker_url=MARKER_URL,avatar_id=PEER if remote else None)

    def test_old_self_frame_remains_historical_but_cannot_qualify_current_subject_identity(self):
        frame,raw,policy=bundle();frame.pop('renderersBefore');frame.pop('renderersAfter');rebind(frame)
        old,_=images.compose(RUN,TICKET,BINDING,frame,raw,policy,marker_nonce=NONCE,marker_url=MARKER_URL,legacy=True)
        self.assertEqual(1,old['iosEmoteImageVersion'])
        with self.assertRaises(NativeUIError):self.compose((frame,raw,policy))


if __name__=='__main__':unittest.main()
