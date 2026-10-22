"""Real PNG/projection joins with explicit synthetic Qt/GPU producers only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from self_tests.test_phone_avatar_people_native import source,SESSION,digest
from test_emote_pixels import Pair as PixelPair,POLICY
from overte_phone_avatar_people_pixels import measure,original

RUN='a'*32
PEER='77777777-7777-4777-8777-777777777777'


class Pair(PixelPair):
    def __init__(self,remote=False):
        super().__init__();self.remote=remote
        for frame in (self.first,self.second):
            frame['viewerBefore']=frame['avatarBefore'];frame['viewerAfter']=frame['avatarAfter']
            for viewer in (frame['viewerBefore'],frame['viewerAfter']):viewer['source']['cameraMode']='independent'
            frame.update(subjectSession=SESSION,wearableIds=[])
            for key,viewer_key in (('avatarBefore','viewerBefore'),('avatarAfter','viewerAfter')):
                viewer=frame[viewer_key];state=source();body=state['avatar'];body.update(modelInstance='c'*32,feetPosition=[0,0,-3])
                body['geometry']['instance']='d'*32
                if remote:
                    state['peers']=[deepcopy(body)];state['avatar'].update(sessionId=PEER,modelInstance='8'*32)
                    state['avatar']['geometry']['instance']='9'*32
                    viewer['source']['modelInstance']='8'*32;viewer['source']['geometry']['instance']='9'*32
                epoch=viewer['capturedEpochMs'];state['auth']['observation']['capturedEpochMs']=epoch
                for model in (state['avatar'],*state['peers']):
                    for field in ('advertisedLoads','modelLoads'):
                        model[field].update(sequence=viewer['sequence'],capturedEpochMs=epoch)
                        for event in model[field]['events']:event['capturedEpochMs']=19998
                for field in ('avatarEntityOrigins','resourceReplies','peopleReplies'):
                    state[field].update(sequence=viewer['sequence'],capturedEpochMs=epoch)
                frame[key]=dict(avatarPeopleObservationVersion=1,commandId=format(viewer['sequence']+1000,'032x'),runId=RUN,
                    instance=viewer['instance'],sequence=viewer['sequence'],processId=31,requestedEpochMs=viewer['requestedEpochMs'],capturedEpochMs=epoch,source=state)
            row=frame['draws']['source']['modelTrace']['models'][0]
            subject=frame['avatarBefore']['source']['peers'][0] if remote else frame['avatarBefore']['source']['avatar']
            row['loadedSourceSha256']=digest(subject['geometry']['url'])
    def measure(self,previous=True):
        return measure(RUN,self.second,self.right,POLICY,31,lambda:self.epoch,lambda:self.okay,
            previous=dict(frame=self.first,png=self.left) if previous else None,monotonic=lambda:self.clock)


class AvatarPeoplePixelTests(unittest.TestCase):
    def test_original_local_and_real_second_perspective_sources_join_separate_gpu_instance(self):
        for remote in (False,True):
            with self.subTest(remote=remote):
                pair=Pair(remote);proof=pair.measure()
                self.assertEqual('remote' if remote else 'local',proof['perspective']);self.assertEqual(SESSION,proof['subjectSession'])
                self.assertEqual(1,proof['avatarPeoplePixelsVersion']);self.assertGreater(proof['bodyChangedFraction'],.05)
                self.assertNotEqual(pair.second['avatarBefore']['instance'],pair.second['capture']['instance'])
    def test_camera_motion_or_wrong_actual_remote_model_cannot_borrow_pixels(self):
        for change in (lambda p:p.second['capture']['source']['renderTrace']['recordedView']['position'].__setitem__(0,.1),
                lambda p:p.second['avatarAfter']['source']['peers'][0].update(modelInstance='1'*32),
                lambda p:p.second['draws']['source']['modelTrace']['models'][0].update(modelInstance='8'*32),
                lambda p:p.second['avatarBefore']['source']['peers'][0].update(shouldRender=False)):
            pair=Pair(True);change(pair)
            with self.subTest(change=change),self.assertRaises(NativeUIError):pair.measure()
    def test_fresh_marker_or_background_change_is_not_a_body_effect(self):
        pair=Pair(True);pair.right=pair.paint(pair.second)
        with self.assertRaises(AssertionError):pair.measure()
        pair=Pair(True);pair.right=pair.paint(pair.second,changed=True,background=True)
        with self.assertRaises(NativeUIError):pair.measure()
    def test_missing_real_second_avatar_cannot_use_local_viewer_model(self):
        pair=Pair(True)
        for key in ('avatarBefore','avatarAfter'):pair.second[key]['source']['peers']=[]
        with self.assertRaises(NativeUIError):pair.measure()
    def test_geometry_texture_and_draw_sources_are_mandatory(self):
        for change in (lambda p:p.second['avatarBefore']['source']['peers'][0]['geometry'].update(texturesLoaded=False),
                lambda p:p.second['draws']['source']['modelTrace']['models'][0].update(skinnedDrawCommands=0),
                lambda p:p.second['draws']['source']['modelTrace']['models'][0].update(originalGeometryDrawCommands=0),
                lambda p:p.second['draws']['source']['modelTrace']['models'][0].update(geometryInstance='5'*32),
                lambda p:p.second['draws']['source']['modelTrace']['models'][0].update(loadedSourceSha256='0'*64)):
            pair=Pair(True);change(pair)
            with self.subTest(change=change),self.assertRaises(NativeUIError):pair.measure()
    def test_single_original_remote_png_has_no_invented_change_or_scale_result(self):
        proof=Pair(True).measure(False);self.assertIsNone(proof['bodyChangedFraction']);self.assertNotIn('scale',proof)
        self.assertNotIn('passed',proof);self.assertNotIn('requestedAvatar',proof)

if __name__=='__main__':unittest.main()
