"""Actual geometric projection math with explicit native/entity/DOM models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_geometry as geometry
from ios.self_tests.test_ios_world_web_marker_measurements import frames
from ios.self_tests.world_web_source_fixture import OriginalSources


def originals():
    _before,world=frames();world['processId']=42;world['source']['scriptOriginal']['processId']=42
    marker=world['source']['markers'][0];marker.update(position=[0,1.6,5.5],dimensions=[1.8,1.4,.01])
    world['source']['view'].update(position=[0,1.6,7],aspectRatio=1024/728)
    row={key:deepcopy(marker[key]) for key in ('id','hostType','sourceUrl','userData','position','rotation','dimensions','visible','lastEditedEpochUs')}
    row.update(parentId='00000000-0000-0000-0000-000000000000',registrationPoint=[.5,.5,.5],dpi=12,inputMode='touch',billboardMode='none',locked=False)
    value=dict(iosWorldWebGeometryVersion=1,requestId='ios-'+'9'*32,runId=world['runId'],instance='8'*32,sequence=1,processId=42,
        clockDomain='native-main-ios-world-web-geometry',clockBefore=dict(epochMs=20005,monotonicMs=5),clockAfter=dict(epochMs=20010,monotonicMs=10),
        source=dict(complete=True,tree=deepcopy(world['source']['tree']),entities=[row],view=deepcopy(world['source']['view'])|dict(uiWidth=1024,uiHeight=728)))
    del value['source']['view']['mode']
    source=OriginalSources();source.epoch=20000;source.view['finishedEpochMs']=19000
    source.view.update(sourceIdentity='web-entity:'+marker['id'],sourceUrl=marker['sourceUrl'])
    document=source.document();document['runId']=world['runId'];document['source']['dom']['document']['runId']=world['runId']
    dom=document['source']['dom'];dom['document'].update(width=850,height=661)
    for element in dom['elements']:
        element.update(rect=[400,305.5,450,355.5],visible=True,enabled=True)
    uikit=dict(schemaVersion=1,commandId='ios-'+'7'*32,observation=dict(schemaVersion=1,sampleSequence=1,sampleEpochMs=20005,
        nativeUi=dict(valid=True,surfaceWidth=1024,surfaceHeight=768,safeInsetLeft=0,safeInsetTop=20,safeInsetRight=0,safeInsetBottom=20,
            keyboardVisible=False,imeInsetBottom=0),window=dict(width=1024,height=728)))
    return value,document,world,uikit,marker['id']


class WorldWebGeometryTests(unittest.TestCase):
    def test_actual_registered_entity_plane_camera_dom_and_safe_ui_viewport_determine_touch(self):
        args=originals();result=geometry.point(*args,'bridge')
        self.assertAlmostEqual(512,result['x']);self.assertAlmostEqual(384,result['y'])
        self.assertEqual([425,330.5],result['domPoint'])
        changed=deepcopy(args);changed[0]['source']['entities'][0]['registrationPoint'][0]=.4
        moved=geometry.point(*changed,'bridge');self.assertGreater(moved['x'],result['x'])
        expected=(.18/(1.5*math.tan(math.radians(60)/2)*(1024/728)))*1024/2
        self.assertAlmostEqual(expected,moved['x']-result['x'])

    def test_unknown_geometry_foreign_native_document_unowned_entity_and_offscreen_dom_refuse_input(self):
        for fault in ('dpi','parent','billboard','nativeOwner','tree','stale','camera','hidden','offscreen','behind','inputMode'):
            value,document,world,uikit,owned=originals();row=value['source']['entities'][0]
            if fault=='dpi':row['dpi']=24
            elif fault=='parent':row['parentId']='11111111-1111-4111-8111-111111111111'
            elif fault=='billboard':row['billboardMode']='full'
            elif fault=='nativeOwner':document['source']['nativeView']['sourceIdentity']='web-entity:foreign'
            elif fault=='tree':value['source']['tree']['entities'][0]['semanticSha256']='f'*64
            elif fault=='stale':value['clockBefore']['epochMs']+=2000;value['clockAfter']['epochMs']+=2000
            elif fault=='camera':value['source']['view']['position'][0]+=.1
            elif fault=='hidden':document['source']['dom']['elements'][0]['visible']=False
            elif fault=='offscreen':document['source']['dom']['elements'][0]['rect']=[-10,0,40,50]
            elif fault=='behind':row['position'][2]=8;world['source']['markers'][0]['position'][2]=8
            else:row['inputMode']='mouse'
            control=document['source']['dom']['elements'][0]['id']
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                geometry.point(value,document,world,uikit,owned,control)

    def test_actual_keyboard_occlusion_is_observed_instead_of_assuming_hidden_or_dismissing(self):
        args=originals();args[3]['observation']['nativeUi'].update(keyboardVisible=True,imeInsetBottom=200)
        geometry.point(*args,'bridge')
        args[3]['observation']['nativeUi']['imeInsetBottom']=500
        with self.assertRaises(NativeUIError):geometry.point(*args,'bridge')

    def test_command_cannot_select_requested_entity_registration_or_touch_effect(self):
        query=dict(schemaVersion=1,commandId='ios-'+'9'*32,action=geometry.ACTION,runId=originals()[0]['runId'])
        geometry.command(query)
        for field in ('entityId','registrationPoint','dpi','focused','expected'):
            with self.subTest(field=field),self.assertRaises(NativeUIError):geometry.command(query|{field:True})


if __name__=='__main__':unittest.main()
