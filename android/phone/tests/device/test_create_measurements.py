"""Create reducer counterexamples over explicit independent original packets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest

from test_create_source import entity,RUN,ID
from test_create_workflows import Widgets
from overte_phone_create_measurements import facts,model,textured,CreatePending
from overte_phone_create_fixture import voxel_cells
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import payload

URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
TICKET='c'*32


class CreateMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.row=entity();self.widgets=Widgets();self.widgets.selected=[ID]
        self.owned=[dict(id=ID,instance=self.row['instance'],role='model')]
    def measured(self):return facts(RUN,URL,dict(source=dict(entities=[self.row],canRez=True)),self.widgets.capture(),self.owned)
    def texture(self):
        url=URL+'tickets/'+TICKET+'/checker.png';data=payload('checker.png',RUN,TICKET)[1]
        self.row['textures']=json.dumps({'checker.png':url})
        snapshot=dict(complete=True,revision=7,material=0,channel=0,name='checker.png',urlSha256=hashlib.sha256(url.encode()).hexdigest(),loaded=True,failed=False,
            originalBytes=len(data),originalSha256=hashlib.sha256(data).hexdigest(),gpuWidth=16,gpuHeight=16)
        self.row['render']['geometry']['textures']['rows']=[snapshot];return snapshot
    def test_static_original_metadata_can_be_older_than_current_capture_without_retiming(self):
        self.row['render']['recordedEpochMs']=1;self.texture();before=deepcopy(self.row)
        self.assertEqual(self.row['render'],model(self.row)[0]);self.assertTrue(self.measured()['textured']);self.assertEqual(before,self.row)
    def test_new_actual_model_url_cannot_reuse_old_loaded_geometry_copy(self):
        self.row['modelUrl']=URL+'tickets/'+TICKET+'/obj-bundle/main.obj'
        with self.assertRaises(NativeUIError):model(self.row)
    def test_actual_texture_assignment_without_consumed_original_and_gpu_is_false(self):
        snapshot=self.texture();self.assertTrue(self.measured()['textured'])
        for changed in (dict(originalSha256='0'*64),dict(originalBytes=snapshot['originalBytes']+1),dict(gpuWidth=0),dict(gpuHeight=32),dict(loaded=False),dict(failed=True),dict(complete=False)):
            self.row['render']['geometry']['textures']['rows']=[snapshot|changed]
            with self.subTest(changed=changed):self.assertFalse(self.measured()['textured'])
    def test_new_texture_property_cannot_adopt_old_url_resource_generation(self):
        self.texture();self.row['textures']=json.dumps({'checker.png':URL+'tickets/'+'e'*32+'/checker.png'})
        self.assertFalse(self.measured()['textured'])
    def test_partial_material_snapshot_does_not_complete_from_last_decoder_ack(self):
        self.texture();self.row['render']['geometry']['textures']['complete']=False
        self.assertFalse(self.measured()['textured'])
        with self.assertRaises(NativeUIError):model(self.row)
    def test_replaced_lifetime_or_foreign_host_lock_parent_and_name_are_red(self):
        original=deepcopy(self.row)
        for change in (dict(instance='0'*32),dict(host='local'),dict(locked=True),dict(parentId=ID),dict(name='foreign'),dict(visible=False)):
            self.row=original|change
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.measured()
    def voxel(self):
        self.row=entity('PolyVox');self.row['voxel']['cells']=dict(sha256=hashlib.sha256(voxel_cells()).hexdigest(),occupied=64)
        self.owned[0]['role']='voxel';self.baseline=deepcopy(self.row)
    def voxel_value(self):return facts(RUN,URL,dict(source=dict(entities=[self.row],canRez=True)),self.widgets.capture(),self.owned,self.baseline)['voxelValue']
    def test_only_actual_lower_occupied_cell_count_changed_cells_and_saved_digest_count_as_remove(self):
        self.voxel();self.assertEqual(0,self.voxel_value())
        self.row['voxel'].update(cells=dict(sha256='a'*64,occupied=48),savedSha256='b'*64)
        self.assertEqual(1,self.voxel_value())
    def test_unchanged_cells_or_only_saved_compression_cannot_supply_voxel_effect(self):
        self.voxel();self.row['voxel']['savedSha256']='b'*64;self.assertEqual(0,self.voxel_value())
        self.row['voxel']['cells']['sha256']='a'*64
        with self.assertRaises(NativeUIError):self.voxel_value()
    def test_not_ready_cells_have_no_public_default_or_expected_voxel_value(self):
        self.voxel();self.row['voxel'].update(ready=False,cells=None)
        with self.assertRaises(CreatePending):self.voxel_value()
    def test_original_permission_denial_survives_regrant_until_actual_success_clears_status(self):
        from overte_phone_create_measurements import DENIED
        self.row=None;ui=self.widgets.capture();ui['controls'][0].update(statusError=True,statusText=DENIED,selectedIds=[])
        state=facts(RUN,URL,dict(source=dict(entities=[],canRez=True)),ui,[])
        self.assertEqual('permission-denied',state['error']);self.assertTrue(state['canRez'])


class CreateActorQuietTests(unittest.TestCase):
    def test_real_quiet_window_restarts_after_gap_without_shortening_three_seconds(self):
        from overte_phone_create_actor import quiet_window
        value=None
        for index,now in enumerate((10.,11.,12.,14.),1):value=quiet_window(value,now,index)
        self.assertFalse(value['complete']);self.assertEqual([4],value['sequences']);self.assertEqual(14.,value['started'])
        for index,now in enumerate((15.,16.,17.),5):value=quiet_window(value,now,index)
        self.assertTrue(value['complete']);self.assertEqual(3.,value['last']-value['started'])

    def test_repeated_slow_sources_never_complete_quiet_window_or_retime_samples(self):
        from overte_phone_create_actor import quiet_window
        value=None
        for index,now in enumerate((10.,12.,14.,16.),1):
            value=quiet_window(value,now,index);self.assertFalse(value['complete']);self.assertEqual(now,value['last'])
        with self.assertRaises(NativeUIError):quiet_window(value,15.,5)


if __name__=='__main__':unittest.main()
