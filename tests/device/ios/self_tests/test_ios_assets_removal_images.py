"""Fresh declared native/raster emissions; actual PNG source/pixel assertions.

These unit producers do not execute normal Delete or native rendering. The
owned normal-input join is separate; no retained original is retimed here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import unittest
from PIL import Image
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import MarkerNotReady
from ios.adapters import assets_model_images as images,assets_removal_images as removal
from ios.self_tests.test_ios_assets_model_images import bundle,seal
from ios.self_tests.test_ios_graphics_measurements import RUN,TICKET,HOST,BINDING


def emitted_pair():
    before,raw_before,policy,proof,marker=bundle()
    # A distinct fresh producer specification starts1000ms later. Entity birth
    # metadata is unchanged. These objects have not been retained or acquired.
    after,raw_after,_,_,_=bundle()
    def clocks(node):
        if type(node) is dict:
            for key,value in node.items():
                if type(value) in (int,float) and (key.endswith('EpochMs') or key in ('epochMs','monotonicMs')):node[key]=value+1000
                else:clocks(value)
        elif type(node) is list:
            for value in node:clocks(value)
    clocks(after)
    after['clockJoin']['hostBeforeMonotonic']+=1;after['clockJoin']['hostAfterMonotonic']+=1
    for index,key in enumerate(('createBefore','modelsBefore','avatarsBefore','capture','retirement','avatarsAfter','modelsAfter','createAfter')):
        row=after[key];row['sequence']+=10
        if 'requestId' in row:row['requestId']='ios-'+format(1000+index,'032x')
        if 'commandId' in row:row['commandId']='ios-'+format(2000+index,'032x')
    after['retirement']['requestId']=after['capture']['requestId']
    for index,key in enumerate(('nativeBefore','nativeAfter')):
        row=after['clockJoin'][key];row['sequence']+=10;row['requestId']='ios-'+format(3000+index,'032x')
    after['capture']['source']['renderTrace']['frameId']='8'*32
    target=proof['entityId']
    for key in ('createBefore','createAfter'):
        source=after[key]['source'];source['entities']=[row for row in source['entities'] if row['id']!=target]
        tree=source['tree'];tree['entities']=[row for row in tree['entities'] if row['id']!=target]
        tree.update(totalEntities=len(tree['entities']),revisionBefore=2,revisionAfter=2)
    for key in ('modelsBefore','modelsAfter','avatarsBefore','avatarsAfter'):
        after[key]['source']['tree']=deepcopy(after['createBefore']['source']['tree'])
        if key.startswith('models'):after[key]['source']['models']=[]
        else:
            for row in after[key]['source']['avatars']:
                for pose in (row['rigPose'],row.get('externalPose')):
                    if pose is not None:pose['evaluationSequence']+=10
    image=Image.open(BytesIO(raw_after)).convert('RGBA');image.paste((70,70,70,255),tuple(policy['subject']))
    stream=BytesIO();image.save(stream,format='PNG');raw_after=stream.getvalue()
    after['capture']['source']['image'].update(bytes=len(raw_after),sha256=hashlib.sha256(raw_after).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
    seal(after)
    return before,raw_before,after,raw_after,policy,proof,marker


class AssetsRemovalImagesTests(unittest.TestCase):
    def pair(self,sample):return removal.pair(RUN,TICKET,BINDING,*sample,after_epoch=HOST)
    def test_actual_absent_sources_and_uniform_original_background_need_the_prior_measured_mesh(self):
        sample=emitted_pair();original=deepcopy(sample);before,after,fraction=self.pair(sample)
        self.assertEqual(original,sample)
        self.assertEqual(1,after['assetModelAbsentImageVersion']);self.assertNotIn('assetModelImageVersion',after)
        self.assertEqual([],after['renderItemIds']);self.assertGreaterEqual(fraction,.05)
        self.assertEqual(before['frameId'],after['basisFrameId'])
        self.assertEqual(before['meshBounds'],after['meshBounds'])
    def test_literal_present_image_profile_cannot_label_a_removed_model_as_present(self):
        before,raw_before,after,raw_after,policy,proof,marker=emitted_pair()
        with self.assertRaises(NativeUIError):images.compose(RUN,TICKET,BINDING,after,raw_after,policy,proof,marker,after_epoch=HOST)
        with self.assertRaises(NativeUIError):images.compose(RUN,TICKET,BINDING,before,raw_before,policy,proof,marker,after_epoch=HOST,absence_basis=(before,raw_before))
    def test_model_absence_with_unchanged_actual_pixels_is_not_a_visible_removal(self):
        sample=list(emitted_pair());sample[3]=sample[1]
        sample[2]['capture']['source']['image']=deepcopy(sample[0]['capture']['source']['image']);seal(sample[2])
        with self.assertRaises(NativeUIError):self.pair(sample)
    def test_missing_model_before_original_or_foreign_challenge_never_supplies_absent_bounds(self):
        sample=emitted_pair()
        with self.assertRaises(MarkerNotReady):removal.pair(RUN,'f'*32,BINDING,*sample,after_epoch=HOST)
        altered=list(sample);altered[0]=deepcopy(sample[2]);altered[1]=sample[3]
        with self.assertRaises(NativeUIError):self.pair(altered)
    def test_another_epoch_camera_graphics_avatar_or_scene_change_cannot_supply_the_subject(self):
        for fault in ('native-instance','request','frame','view','graphics','avatar','marker','tree','source','held-gpu'):
            sample=list(emitted_pair());before,raw_before,after,raw_after,policy,proof,marker=sample
            if fault=='native-instance':after['clockJoin']['nativeBefore']['instance']='f'*32
            elif fault=='request':after['capture']['requestId']=after['retirement']['requestId']=before['capture']['requestId']
            elif fault=='frame':after['capture']['source']['renderTrace']['frameId']=before['capture']['source']['renderTrace']['frameId']
            elif fault=='view':
                for key in ('createBefore','createAfter'):after[key]['source']['view']['position'][0]+=.01
                after['capture']['source']['renderTrace']['recordedView']['position'][0]+=.01
            elif fault=='graphics':
                for key in ('nativeBefore','nativeAfter'):after['clockJoin'][key]['graphics']['shadowsSetting']=True
            elif fault=='avatar':
                for key in ('avatarsBefore','avatarsAfter'):next(row for row in after[key]['source']['avatars'] if row['self'])['rigPose']['joints'][0][-1]+=.1
            elif fault=='marker':
                for key in ('createBefore','createAfter'):after[key]['source']['entities'][0]['name']+='changed'
            elif fault=='tree':
                for key in ('createBefore','createAfter','modelsBefore','modelsAfter','avatarsBefore','avatarsAfter'):
                    after[key]['source']['tree']['treeInstance']='9'*32
            elif fault=='source':after['modelsBefore']['source']['complete']=False
            else:after['retirement']['source']['gpuBufferBytes']=4
            seal(after)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,AssertionError)):self.pair(sample)
    def test_owned_entry_rejects_unrelated_helpers_before_source_access(self):
        with self.assertRaises(NativeUIError):removal.compose(object(),object(),object(),{})
