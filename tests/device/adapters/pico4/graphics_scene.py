"""Pico scene policy over original tracked HMD, avatar and framework owners.

Ordinary Go To changes avatar feet/yaw. Physical sensor poses are observations;
this policy neither sets Camera/HMD transforms nor supplies rendered evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.native_feature_observation import need
from adapters.native_scene_loads import resource_hash
from adapters.vr_graphics_subject import first_person_head,separate_inventory,rotation_columns
from adapters.graphics_journey.geometry import near,aligned_entities
from adapters.token_graphics_ui import on_grid
from feature_journeys.graphics_fixture import VIEW,LEGACY_PROFILE,PICO_PROFILE,PICO_RESOURCE

VERSION=3


def rotation_equal(a,b,tolerance=.001):return near(a,b,tolerance) or near(a,[-v for v in b],tolerance)


def yaw(rotation):
    columns=rotation_columns(rotation)
    return math.atan2(columns[2][0],columns[2][2])


def stable_framework(original,current):
    """Exact native registrations and appearance; raw properties stay archived.

    Tablet/keyboard/ray geometry can follow physical tracking. Omitting their
    spatial fields from appearance comparison is explicit, never a whole UI,
    keyboard, callback, renderer or input-retirement verdict.
    """
    a,b=(deepcopy(value) for value in (original,current))
    for value in (a,b):
        for row in value['entities']:row.pop('propertySha256')
    need(a==b and not current['keyboard']['raised'])


class PicoGraphicsScenePolicy:
    profile='pico-stereo-v1'
    fixture_profile=LEGACY_PROFILE
    require_framework=True
    camera_mode='first person'
    graphics_profile='generic-immediate-v1'

    @staticmethod
    def validate_original_settings(packet):
        # Current generic Qt slider source has this range/step. A native .65
        # preference cannot be restored through it, so reject before any
        # preference action. Each later actual row is independently checked.
        need(on_grid(packet['graphics']['requestedResolutionScale'],dict(minimum=.1,maximum=2.,step=.1)))

    @staticmethod
    def eligible(packet):
        first_person_head(packet);source=packet['source'];pose=source['avatarPose']
        need(source['view']['mode']=='first person' and not source['entities'] and len(source['absentIds'])==7
            and abs(pose['orientation'][0])<.0001 and abs(pose['orientation'][2])<.0001
            and not source['framework']['keyboard']['raised'])
        resource_hash(source['sceneUrl'])

    @classmethod
    def aligned_entities(cls,packet,run,scene_ticket,fixture_url):
        inventory=separate_inventory(packet)
        aligned_entities(packet,run,scene_ticket,fixture_url,scene_inventory=inventory['scene'],profile=cls.fixture_profile)

    @staticmethod
    def alignment(packet):
        """One intended avatar pose from original scaled/rotated physical head.

        Yaw may be corrected by normal navigation. Pitch and roll require a
        physically level tracked rig; neither can be repaired by this test.
        """
        hmd=first_person_head(packet);pose=packet['source']['avatarPose']
        need(packet['source']['view']['mode']=='first person'
            and abs(pose['orientation'][0])<.0001 and abs(pose['orientation'][2])<.0001)
        columns=rotation_columns(hmd['worldRotation'])
        need(columns[1][1]>=math.cos(.03))
        delta=-yaw(hmd['worldRotation']);angle=yaw(pose['orientation'])+delta
        offset=[a-b for a,b in zip(hmd['worldPosition'],pose['feetPosition'])]
        c,s=math.cos(delta),math.sin(delta)
        rotated=[c*offset[0]+s*offset[2],offset[1],-s*offset[0]+c*offset[2]]
        feet=[VIEW['position'][axis]-rotated[index] for index,axis in enumerate('xyz')]
        return feet,[0,math.sin(angle/2),0,math.cos(angle/2)]

    @classmethod
    def aligned_subject(cls,packet,run,scene_ticket,fixture_url):
        cls.aligned_entities(packet,run,scene_ticket,fixture_url);head=first_person_head(packet)
        need(packet['source']['view']['mode']=='first person'
            and near(head['worldPosition'],[VIEW['position'][a] for a in 'xyz'],.02))
        columns=rotation_columns(head['worldRotation'])
        need(all(abs(columns[c][r]-(1 if c==r else 0))<=.04 for c in range(3) for r in range(3)))

    @classmethod
    def restored(cls,original,current,*,framework_original=None):
        cls.eligible(original);cls.eligible(current)
        old,new=original['source'],current['source'];a,b=separate_inventory(original),separate_inventory(current)
        need(resource_hash(old['sceneUrl'])==resource_hash(new['sceneUrl'])
            and set(old['absentIds'])==set(new['absentIds']) and a['scene']==b['scene']
            and near(old['scan']['center'],new['scan']['center'],.01)
            and old['scan']['radiusMeters']==new['scan']['radiusMeters']
            and old['scan']['propertyScope']==new['scan']['propertyScope'])
        before,after=old['avatarPose'],new['avatarPose']
        need(near(before['feetPosition'],after['feetPosition'],.01)
            and rotation_equal(before['orientation'],after['orientation']) and near(before['modelScale'],after['modelScale'],.0001)
            and near(old['hmd']['sensorToWorld'],new['hmd']['sensorToWorld'],.0001))
        # Head/camera relation is checked independently on each original; normal
        # physical tracking is not confused with moving the restored avatar.
        for field,tolerance in (('fieldOfViewDegrees',.001),('aspectRatio',.001)):
            need(near(old['view'][field],new['view'][field],tolerance))
        if framework_original is None:
            need(original['processId']==current['processId'] and original['instance']==current['instance'])
            ownership=a['ownership']
        else:
            # The scene owner separately validates the qualified old-PID exit
            # and exact restart receipt before supplying this new-process
            # original. The old scene/avatar/property originals stay intact.
            cls.eligible(framework_original)
            need(original['instance']!=current['instance'] and original['processId']!=current['processId']
                and framework_original['instance']==current['instance'] and framework_original['processId']==current['processId']
                and framework_original['sequence']<=current['sequence']
                and framework_original['capturedEpochMs']<=current['capturedEpochMs'])
            ownership=separate_inventory(framework_original)['ownership']
        stable_framework(ownership,b['ownership'])


class PicoGraphicsSurfaceScenePolicy(PicoGraphicsScenePolicy):
    profile=PICO_PROFILE
    fixture_profile=PICO_PROFILE
    fixture_resource=PICO_RESOURCE
