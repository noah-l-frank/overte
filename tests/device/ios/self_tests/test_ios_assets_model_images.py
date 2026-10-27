"""Declared native sources and actual PNG; no native draw/parser is executed.

The baked proof is a separate modeled source prerequisite here, not a claim
that this unit fixture performed the complete upload/parse/marker journey.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import MarkerNotReady
from ios.adapters import assets_model_images as images
from ios.self_tests import test_ios_create_world_measurements as create_image
from ios.self_tests import test_ios_assets_model_renderers as mesh
from ios.self_tests.test_ios_avatar_renderers import packet as avatar_packet
from ios.self_tests.test_ios_create_state import DOMAIN,ID
from ios.self_tests.test_ios_graphics_measurements import RUN,TICKET,NATIVE,HOST,BINDING


def seal(frame):
    raw=images.originals(frame);frame['clockJoin']['originalsSha256']=digest(raw)
    frame['clockJoin']['sourceTimes']=[dict(source=name,field=key,epochMs=packet[key]) for name,packet in raw.items()
        for key in ('capturedEpochMs','sampleEpochMs') if key in packet]


def bundle():
    frame,raw,policy,marker=create_image.bundle()
    # This fresh standalone unit producer declares its own baked/reader
    # boundary; no retained source from a different run is relabeled.
    proof=dict(assetModelBakedInputProofVersion=1,runId=RUN,processId=42,domainId=DOMAIN,entityId=ID,
        creationRequestId='ios-'+'5'*32,originRequestId='ios-'+'6'*32,readerId='d'*32,nativeGeometryRequestId='ios-'+'7'*32,
        backendRequestId='assets-'+'8'*32,bakeRequestId='assets-'+'9'*32,path='/e2e-'+RUN+'/asset-stand.fbx',
        outputPath='/.baked/'+'f'*64+'/asset.fbx',sha256='e'*64,bytes=128)
    for key in ('createBefore','createAfter'):
        entity=next(row for row in frame[key]['source']['entities'] if row['id']==proof['entityId'])
        entity['modelURL']='atp:'+proof['path']
    for index,(key,offset) in enumerate((('modelsBefore',30),('modelsAfter',320))):
        packet=mesh.packet();packet.update(runId=RUN,requestId='ios-'+str(index+1)*32,sequence=index+1)
        packet['clockBefore']=dict(epochMs=NATIVE+offset,monotonicMs=offset);packet['clockAfter']=dict(epochMs=NATIVE+offset+1,monotonicMs=offset+1)
        packet['source']['tree']=deepcopy(frame['createBefore']['source']['tree'])
        row=packet['source']['models'][0];row['bounds']=dict(corner=[-.5,.5,-3.5],dimensions=[1,1,1])
        row['origin'].update(modelUrl='atp:'+proof['path'],watcherUrl='atp:'+proof['path'])
        row['origin']['geometry']['readerId']=proof['readerId'];frame[key]=packet
    for index,(key,offset) in enumerate((('avatarsBefore',40),('avatarsAfter',300))):
        packet=avatar_packet();packet.update(runId=RUN,requestId='ios-'+str(index+3)*32,sequence=index+1)
        packet['clockBefore']=dict(epochMs=NATIVE+offset,monotonicMs=offset);packet['clockAfter']=dict(epochMs=NATIVE+offset+1,monotonicMs=offset+1)
        packet['source']['tree']=deepcopy(frame['createBefore']['source']['tree'])
        for row in packet['source']['avatars']:
            if row['self']:row['sessionId']=frame['createBefore']['source']['localSessionId']
            row['bounds']=dict(corner=[5,0,-4],dimensions=[1,1.8,1])
            for pose in (row['rigPose'],row['externalPose']):
                if pose is not None:pose.update(capturedEpochMs=NATIVE+offset,evaluationSequence=index+100)
        packet['source']['avatars'].sort(key=lambda row:row['sessionId'])
        frame[key]=packet
    policy['subject']=[290,245,350,305];seal(frame);return frame,raw,policy,proof,marker


class AssetsModelImagesTests(unittest.TestCase):
    def compose(self,sample,**kwargs):return images.compose(RUN,TICKET,BINDING,*sample,after_epoch=HOST,**kwargs)
    def test_fenced_original_pixels_join_actual_mesh_bound_reader_and_disjoint_marker(self):
        sample=bundle();before=deepcopy(sample[0]);observed,subject=self.compose(sample)
        self.assertEqual(sample[3]['entityId'],observed['entityId']);self.assertEqual(sample[3]['readerId'],observed['readerId'])
        self.assertEqual(sample[3]['sha256'],observed['bodySha256']);self.assertEqual([7,19],observed['renderItemIds'])
        self.assertEqual((128,96),subject.size);self.assertNotIn('objects',observed);self.assertEqual(before,sample[0])

    def test_other_geometry_or_unknown_avatar_cannot_supply_the_subject(self):
        for fault in ('avatar','unknown-avatar','model','unknown-model'):
            frame,raw,policy,proof,marker=bundle()
            for key in ('avatarsBefore','avatarsAfter'):
                row=next(row for row in frame[key]['source']['avatars'] if row['self'])
                if fault=='avatar':row['bounds']=deepcopy(frame['modelsBefore']['source']['models'][0]['bounds'])
                elif fault=='unknown-avatar':row.update(boundsReady=False,bounds=None)
            if fault in ('model','unknown-model'):
                # The actual complete source contains another visible Model;
                # its real mesh either overlaps the ROI or has missing bounds.
                identity='22222222-1111-4111-8111-111111111111'
                for key in ('createBefore','createAfter'):
                    row=deepcopy(next(row for row in frame[key]['source']['entities'] if row['id']==proof['entityId']));row['id']=identity
                    frame[key]['source']['entities'].append(row);frame[key]['source']['entities'].sort(key=lambda row:row['id'])
                    inventory=frame[key]['source']['tree'];wire=deepcopy(next(row for row in inventory['entities'] if row['id']==proof['entityId']));wire['id']=identity
                    inventory['entities'].append(wire);inventory['entities'].sort(key=lambda row:row['id']);inventory['totalEntities']+=1
                for key in ('modelsBefore','modelsAfter','avatarsBefore','avatarsAfter'):frame[key]['source']['tree']=deepcopy(frame['createBefore']['source']['tree'])
                for key in ('modelsBefore','modelsAfter'):
                    row=deepcopy(frame[key]['source']['models'][0]);row.update(entityId=identity,renderItemIds=[29])
                    if fault=='unknown-model':row.update(boundsReady=False,bounds=None)
                    frame[key]['source']['models'].append(row);frame[key]['source']['models'].sort(key=lambda row:row['entityId'])
            seal(frame)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.compose((frame,raw,policy,proof,marker))

    def test_requested_url_loaded_flag_or_global_draw_count_cannot_replace_actual_reader_and_mesh(self):
        for fault in ('reader','origin','bounds','items','tree','domain','source','gpu','view','order','lifecycle','graphics','self','avatar-complete'):
            frame,raw,policy,proof,marker=bundle();row=frame['modelsBefore']['source']['models'][0]
            if fault=='reader':row['origin']['geometry']['readerId']='f'*32
            elif fault=='origin':row['origin']['modelUrl']='atp:/wanted.fbx'
            elif fault=='bounds':row.update(boundsReady=False,bounds=None)
            elif fault=='items':row.update(renderItemIds=[],boundsReady=False,bounds=None)
            elif fault=='tree':frame['modelsBefore']['source']['tree']['treeInstance']='f'*32
            elif fault=='domain':proof['domainId']='ffffffff-ffff-4fff-8fff-ffffffffffff'
            elif fault=='source':frame['capture']['source']['backend']='opengl'
            elif fault=='gpu':frame['retirement']['source']['gpuBufferBytes']=1
            elif fault=='view':frame['capture']['source']['renderTrace']['recordedView']['position'][0]+=.1
            elif fault=='order':frame['modelsBefore']['clockAfter']['epochMs']=NATIVE+500
            elif fault=='lifecycle':frame['clockJoin']['nativeAfter']['lifecycle']['backgrounds']+=1
            elif fault=='graphics':frame['clockJoin']['nativeAfter']['graphics']['shadowsSetting']=True
            elif fault=='self':
                for key in ('avatarsBefore','avatarsAfter'):
                    frame[key]['source']['avatars']=[row for row in frame[key]['source']['avatars'] if not row['self']]
            else:frame['avatarsBefore']['source']['complete']=False
            seal(frame)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):self.compose((frame,raw,policy,proof,marker))

    def test_actual_mesh_and_whole_marker_quad_constrain_subject_not_the_challenge_crop_only(self):
        for crop in ([0,170,640,400],[600,0,640,40],[187,130,443,170]):
            frame,raw,policy,proof,marker=bundle();policy['subject']=crop
            with self.subTest(crop=crop),self.assertRaises(NativeUIError):self.compose((frame,raw,policy,proof,marker))

    def test_same_subject_is_not_changed_model_pixels(self):
        sample=bundle();_observed,subject=self.compose(sample)
        with self.assertRaises(AssertionError):self.compose(sample,previous=subject,changed=True)

    def test_actual_png_cannot_qualify_another_ticket_or_changed_body_hash(self):
        sample=bundle()
        with self.assertRaises(MarkerNotReady):images.compose(RUN,'f'*32,BINDING,*sample,after_epoch=HOST)
        frame,raw,policy,proof,marker=sample;raw=raw[:-20]+b'corrupt source bytes'
        with self.assertRaises(NativeUIError):self.compose((frame,raw,policy,proof,marker))
