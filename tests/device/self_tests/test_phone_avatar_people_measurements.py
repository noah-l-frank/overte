"""Original facts and measured camera ownership counterexamples; host only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from self_tests.test_world_render_evidence import frame_view
from self_tests.test_phone_avatar_people_native import avatar,URL,loads,digest
from overte_phone_avatar_people_measurements import body,model_resources,entity_semantics,native_model_semantics
from overte_phone_navigation_marker import input_command,camera_lease,continuation

RUN='a'*32


def camera():
    original=frame_view()|dict(mode='selfie',feetPosition=[0,0,0],modelScale=1,boomLength=2)
    view={key:deepcopy(original[key]) for key in ('mode','position','rotation','projection')}
    held=deepcopy(view);held['mode']='independent'
    source=dict(measuredCameraLeaseVersion=1,instance='c'*32,phase='held',originalObject=True,
        originalView=view,heldView=held,currentView=deepcopy(held),foreignModeChanges=0,restoration=None)
    return original,source


class CameraLeaseTests(unittest.TestCase):
    def test_optional_closed_hold_keeps_ordinary_navigation_grammar(self):
        request=dict(schemaVersion=1,commandId='b'*32,action='phone-navigation-marker-input',operation='prepare',runId=RUN,
            fixtureUrl='https://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/',ticket='d'*32,imageExtent=[640,480],markerRoi=[20,20,180,60])
        input_command(request);input_command(request|dict(holdView=True))
        for value in (False,1,'true',None):
            with self.subTest(value=value),self.assertRaises(NativeUIError):input_command(request|dict(holdView=value))
        with self.assertRaises(NativeUIError):input_command(request|dict(holdView=True,cameraPosition=[0,0,0]))
    def test_original_camera_view_identity_and_real_current_view_are_mandatory(self):
        view,source=camera();self.assertEqual(source,camera_lease(source,view))
        for change in (lambda s:s.update(originalObject=False),lambda s:s.update(foreignModeChanges=1),
                lambda s:s['heldView'].update(position=[1,2,3]),lambda s:s['currentView'].update(mode='selfie'),
                lambda s:s['currentView']['projection'].__setitem__(0,4),lambda s:s.update(measuredCameraLeaseVersion=True),
                lambda s:s.update(expectedRestored=True)):
            bad=deepcopy(source);change(bad)
            with self.subTest(change=change),self.assertRaises(NativeUIError):camera_lease(bad,view)
    def test_lost_or_replaced_camera_cannot_reacquire_ownership(self):
        view,source=camera();source.update(phase='lost',foreignModeChanges=1);camera_lease(source,view)
        old=dict(source=dict(fixtureInstance='e'*32,runId=RUN,createdEpochMs=10,originalInput={},originalView=view,objects=[],phase='active',cameraLease=source))
        new=deepcopy(old);new['source']['cameraLease'].update(phase='held',foreignModeChanges=0,restoration=None)
        with self.assertRaises(NativeUIError):continuation(old,new)
        source.update(originalObject=False,currentView={});camera_lease(source,view)
    def test_restoration_requires_original_mode_and_original_native_view(self):
        view,source=camera();source.update(phase='restored',currentView=deepcopy(source['originalView']),
            restoration=dict(capturedEpochMs=20000,originalObject=True,view=deepcopy(source['originalView'])));camera_lease(source,view,20000)
        source['currentView'].update(mode='first person look at',position=[0,1.6,9]);camera_lease(source,view,20000)
        source['restoration']['view']['position'][2]=9
        with self.assertRaises(NativeUIError):camera_lease(source,view,20000)


class ModelMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.initial=avatar();self.initial['requestedUrl']='qrc:/original.fst';self.initial['geometry']['url']='qrc:/original.fbx'
        self.urls={'A':{URL},'missing':{URL.replace('avatar-a.fst','missing.fst')},'wearable':set()}
    def test_fresh_history_cursors_do_not_mask_real_geometry_or_generation_changes(self):
        first=avatar();second=deepcopy(first)
        second['modelLoads'].update(sequence=2,capturedEpochMs=20001)
        self.assertEqual(native_model_semantics(first),native_model_semantics(second))
        second['modelLoads']['currentGeneration']=2
        self.assertNotEqual(native_model_semantics(first),native_model_semantics(second))
        left=dict(complete=True,entities=[dict(model=dict(modelInstance='c'*32,modelLoads=loads(),loaded=True))],absentIds=[])
        right=deepcopy(left);right['entities'][0]['model']['modelLoads'].update(sequence=2,capturedEpochMs=20001)
        self.assertEqual(entity_semantics(left),entity_semantics(right))
        right['entities'][0]['model']['modelInstance']='d'*32
        self.assertNotEqual(entity_semantics(left),entity_semantics(right))
    def test_actual_original_model_and_scale_supply_observation(self):
        actual=avatar();actual.update(scale=1.5,targetScale=1.5)
        observed=body(actual,self.initial,self.urls)
        self.assertEqual(dict(avatar='A',requestedAvatar='A',modelLoaded=True,loadFailed=False,scale=1.5),observed)
        actual.update(scale=1,targetScale=1)
        self.assertEqual(1,body(actual,self.initial,self.urls)['scale']) # Ignored scale stays red against the common contract.
    def test_retained_a_geometry_never_becomes_a_missing_fallback(self):
        actual=avatar();actual['requestedUrl']=next(iter(self.urls['missing']));actual['advertisedLoads']=loads(actual['requestedUrl'])
        with self.assertRaises(NativeUIError):body(actual,self.initial,self.urls)
    def test_current_generation_original_failure_is_required(self):
        actual=avatar();missing=next(iter(self.urls['missing']));actual.update(requestedUrl=missing,geometry=None,loaded=False)
        actual['advertisedLoads']=loads(missing);actual['advertisedLoads']['events'][1]['success']=False
        self.assertTrue(body(actual,self.initial,self.urls)['loadFailed'])
        actual['advertisedLoads']['currentGeneration']=2
        self.assertFalse(body(actual,self.initial,self.urls)['loadFailed'])
    def test_missing_model_still_needs_actual_consumed_404(self):
        actual=avatar();actual.update(requestedUrl=next(iter(self.urls['missing'])),geometry=None,loaded=False)
        with patch('overte_phone_avatar_people_measurements.consumed',side_effect=NativeUIError('No original response')) as consumed:
            with self.assertRaises(NativeUIError):model_resources(RUN,actual,self.urls,{},{} )
            self.assertEqual(404,consumed.call_args.kwargs['status'])

if __name__=='__main__':unittest.main()
