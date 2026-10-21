"""Analytical original HMD/owner inventories; no native compiler or device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import unittest
from adapters.native_graphics_subject import validate
from adapters.vr_graphics_subject import first_person_head,separate_inventory
from adapters.normal_ui import NativeUIError
from self_tests.test_native_graphics_subject import Boundary as Base, RUN
from feature_journeys.graphics_fixture import subject_ids

TABLET='11111111-1111-4111-8111-111111111111'
BACK='22222222-2222-4222-8222-222222222222'
KEY='33333333-3333-4333-8333-333333333333'
RAY='44444444-4444-4444-8444-444444444444'
USER='55555555-5555-4555-8555-555555555555'


def entity(identifier):return dict(id=identifier,present=True,type='Box',hostType='local',parentId=None,
    propertySha256='a'*64,appearanceSha256='b'*64)


def framework_source(source):
    # Independent explicit column-major matrices: avatar world yaw=+90 degrees,
    # world scale=1.25, sensor head translation=(.1,1.6,-.2). Thus the original
    # head world position is=(1.75,2.0,2.875), not avatar feet or a fixed eye.
    source.source.update(subjectVersion=3,avatarPose=dict(feetPosition=[2,0,3],orientation=[0,math.sqrt(.5),0,math.sqrt(.5)],modelScale=1.25),
        hmd=dict(display='OpenXR',active=True,visible=True,mounted=True,
            sensorToWorld=[0,0,-1.25,0,0,1.25,0,0,1.25,0,0,0,2,0,3,1],
            sensorPose=[1,0,0,0,0,1,0,0,0,0,1,0,.1,1.6,-.2,1],
            worldPosition=[1.75,2,2.875],worldRotation=[0,math.sqrt(.5),0,math.sqrt(.5)]),
        framework=dict(ownershipVersion=1,
            tablet=dict(frame=TABLET,screen=None,home=None,highlight=None,miniFrame=None,miniScreen=None),
            keyboard=dict(entityIds=sorted([BACK,KEY]),anchor=None,textDisplay=None,backPlate=BACK,raised=False,use3D=True),
            pointers=[dict(id=7,kind='laser',pickId=11,enabled=True,renderState='normal',scriptParametersSha256='c'*64,hasScriptParameters=True,
                states=[dict(scope='normal',name='normal',entities=dict(start=None,end=None,path=RAY))])],
            entities=[entity(identifier) for identifier in sorted([TABLET,BACK,KEY,RAY])]))
    source.source['view'].update(position=[1.75,2,2.875],rotation=[0,math.sqrt(.5),0,math.sqrt(.5)])
    source.source['scan'].update(scannedEntities=5,unowned=[dict(id=identifier,sha256='d'*64) for identifier in [TABLET,BACK,KEY,RAY,USER]])
    return source


class Boundary(Base):
    def __init__(self):super().__init__();framework_source(self)


class VrGraphicsSubjectTests(unittest.TestCase):
    def test_actual_head_relation_uses_original_scaled_rotated_sensor_transform(self):
        source=Boundary();reader=source.reader(require_framework=True);value=reader.read(RUN)
        head=first_person_head(value)
        self.assertEqual([1.75,2,2.875],head['worldPosition'])
        self.assertNotEqual(value['source']['avatarPose']['feetPosition'],head['worldPosition'])
        self.assertEqual(source.source,value['source']);self.assertEqual(1,len(source.commands))
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(source.commands[0]))

    def test_complete_raw_scan_is_preserved_and_only_original_registered_ids_are_partitioned(self):
        source=Boundary();value=source.reader().read(RUN,require_framework=True)
        inventory=separate_inventory(value)
        self.assertEqual(source.source['scan']['unowned'],inventory['raw'])
        self.assertEqual([dict(id=USER,sha256='d'*64)],inventory['scene'])
        self.assertEqual({TABLET,BACK,KEY,RAY},{row['id'] for row in inventory['framework']})
        inventory['raw'].clear();self.assertEqual(5,len(value['source']['scan']['unowned']))

    def test_legitimate_physical_head_motion_does_not_become_avatar_or_fixed_camera_restoration(self):
        source=Boundary();reader=source.reader();before=reader.read(RUN,require_framework=True)
        source.source['hmd']['sensorPose'][12]=.2
        source.source['hmd']['worldPosition']=[1.75,2,2.75]
        source.source['view']['position']=[1.75,2,2.75]
        after=reader.read(RUN,require_framework=True)
        self.assertEqual(before['source']['avatarPose'],after['source']['avatarPose'])
        self.assertNotEqual(first_person_head(before)['worldPosition'],first_person_head(after)['worldPosition'])

    def test_current_first_person_camera_relation_cannot_use_phone_eye_or_third_person(self):
        for changes in (dict(position=[0,1.6,0]),dict(rotation=[0,0,0,1]),dict(mode='third person'),dict(perspective=False)):
            source=Boundary();source.source['view'].update(changes)
            value=source.reader().read(RUN,require_framework=True)
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):first_person_head(value)

    def test_missing_native_v3_cannot_satisfy_required_framework_or_pico_constructor(self):
        for version in (1,2):
            source=Base()
            if version==2:source.source.update(subjectVersion=2,avatarPose=dict(feetPosition=[0,0,0],orientation=[0,0,0,1],modelScale=1))
            reader=source.reader(require_framework=True)
            with self.subTest(version=version),self.assertRaises(NativeUIError):reader.read(RUN,require_framework=False)
            self.assertIsNone(reader.last)
            self.assertEqual(version,source.reader().read(RUN)['source']['subjectVersion'])

    def test_fixture_owned_entities_are_never_adopted_as_framework(self):
        source=Boundary();identifier=subject_ids(RUN)['marker'];source.source['framework']['tablet']['frame']=identifier
        source.source['framework']['entities'][0]=entity(identifier);source.source['framework']['entities'].sort(key=lambda row:row['id'])
        with self.assertRaises(NativeUIError):source.reader().read(RUN,require_framework=True)

    def test_entities_named_like_framework_or_local_remain_in_unowned_scene(self):
        # USER is a local entity in the original raw scan; names and host type
        # supply no ownership. Only the independent native registration does.
        source=Boundary();value=source.reader().read(RUN,require_framework=True)
        self.assertEqual(USER,separate_inventory(value)['scene'][0]['id'])
        source.source['framework']['tablet']['frame']=None
        source.source['framework']['entities']=[row for row in source.source['framework']['entities'] if row['id']!=TABLET]
        value=source.reader().read(RUN,require_framework=True)
        self.assertEqual({USER,TABLET},{row['id'] for row in separate_inventory(value)['scene']})

    def test_absent_registered_ids_do_not_exclude_present_entities_from_original_scan(self):
        source=Boundary();row=next(row for row in source.source['framework']['entities'] if row['id']==RAY)
        row.update(present=False,type=None,hostType=None,parentId=None,propertySha256=None,appearanceSha256=None)
        value=source.reader().read(RUN,require_framework=True)
        self.assertIn(RAY,{row['id'] for row in separate_inventory(value)['scene']})

    def test_unknown_pointer_type_missing_original_slot_or_foreign_host_never_becomes_empty_inventory(self):
        edits=[lambda f:f['pointers'][0].update(kind='unknown'),lambda f:f['pointers'][0]['states'][0]['entities'].pop('path'),
            lambda f:f['pointers'][0]['states'][0]['entities'].update(expectedId=USER),
            lambda f:f['entities'][0].update(hostType='domain'),lambda f:f['entities'].pop(),
            lambda f:f['entities'].append(entity(USER)),lambda f:f['keyboard'].update(backPlate=USER),
            lambda f:f['pointers'].append(deepcopy(f['pointers'][0])),lambda f:f.update(ownershipVersion=True)]
        for edit in edits:
            source=Boundary();edit(source.source['framework'])
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):source.reader().read(RUN,require_framework=True)

    def test_all_pointer_render_states_and_stylus_slot_are_retained_without_inventing_legacy_state(self):
        source=Boundary();pointer=source.source['framework']['pointers'][0]
        pointer['states'].append(dict(scope='default',name='idle',entities=dict(start=None,end=RAY,path=None)))
        value=source.reader().read(RUN,require_framework=True);self.assertEqual(2,len(value['source']['framework']['pointers'][0]['states']))
        pointer.update(kind='stylus',renderState=None,states=[dict(scope='normal',name='stylus',entities=dict(stylus=RAY))])
        value=source.reader().read(RUN,require_framework=True);self.assertIsNone(value['source']['framework']['pointers'][0]['renderState'])
        pointer['renderState']='events on'
        with self.assertRaises(NativeUIError):source.reader().read(RUN,require_framework=True)

    def test_unavailable_head_display_visibility_and_nonrigid_or_wrong_original_matrices_fail(self):
        edits=[lambda h:h.update(display='Android Phone'),lambda h:h.update(active=False),
            lambda h:h['sensorPose'].__setitem__(0,0),lambda h:h['sensorPose'].__setitem__(15,0),
            lambda h:h['sensorToWorld'].__setitem__(0,2),lambda h:h.update(worldPosition=[0,1.6,0]),
            lambda h:h.update(worldRotation=[0,0,0,1]),lambda h:h['sensorPose'].__setitem__(0,float('nan'))]
        for edit in edits:
            source=Boundary();edit(source.source['hmd'])
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):source.reader().read(RUN,require_framework=True)
        for field in ('visible','mounted'):
            source=Boundary();source.source['hmd'][field]=False;value=source.reader().read(RUN,require_framework=True)
            with self.subTest(field=field),self.assertRaises(NativeUIError):first_person_head(value)

    def test_invalid_requirement_flags_do_not_send_and_source_downgrade_cannot_continue_history(self):
        source=Boundary()
        for invalid in (1,None,'true'):
            with self.assertRaises(NativeUIError):source.reader().read(RUN,require_framework=invalid)
        self.assertEqual([],source.commands)
        reader=source.reader();reader.read(RUN)
        source.source.pop('framework');source.source.pop('hmd');source.source['subjectVersion']=2
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(3,reader.last['source']['subjectVersion'])
