"""Synthetic original-source joins, not a rendered client or device acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))

from PIL import Image,ImageDraw
from adapters.normal_ui import NativeUIError
from adapters.world_render_evidence import image_name
from feature_journeys.fixtures import marker_bytes
from feature_journeys.graphics_fixture import scene
from feature_journeys.graphics_resources import GraphicsResources
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_graphics_subject import Boundary as SubjectBoundary
from self_tests.test_world_render_evidence import Boundary as RenderBoundary,frame_view
from self_tests.test_token_graphics_ui import GraphicsBoundary
from audio_native_boundary import ControlNativeBoundary
from overte_phone_graphics_measurements import compose

RUN='b'*32
TICKET='c'*32
SCENE='d'*32
URL='http://controlled.invalid/feature-fixture/v1'
FIXTURE=URL+'/runs/'+RUN+'/'
POLICY=dict(source='world-render-target',marker=[4,4,132,36],subject=[0,48,160,144])


def original_image(ticket=TICKET,*,blank=False):
    # Fixed synthetic observed pixels: no expected feature flag drives them.
    image=Image.new('RGBA',(160,144),(128,128,128,255))
    image.paste(Image.open(io.BytesIO(marker_bytes(RUN,ticket))).convert('RGBA'),(0,0))
    if not blank:
        draw=ImageDraw.Draw(image)
        for y in range(48,144,12):
            for x in range(0,160,16):draw.rectangle((x,y,x+15,y+11),fill=(240,80,20,255) if (x//16+y//12)%2 else (20,80,210,255))
    output=io.BytesIO();image.save(output,format='PNG');return output.getvalue(),hashlib.sha256(image.tobytes()).hexdigest()


class Sources:
    def __init__(self):
        native=NativeBoundary();native.send(dict(commandId='1'*32))
        self.before=deepcopy(native.sample);self.before['processId']=31
        native.send(dict(commandId='2'*32));self.after=deepcopy(native.sample);self.after['processId']=31
        subject=SubjectBoundary();subject.source['sceneUrl']=FIXTURE+'tickets/'+SCENE+'/graphics-scene.v1.json'
        subject.source['view']['aspectRatio']=160/144
        for document in scene(RUN,SCENE,FIXTURE)['Entities']:
            name=document['name'].split('-graphics-',1)[1];row=subject.add(name)
            row.update(name=document['name'],type=document['type'],mirrorMode=document.get('mirrorMode','none'),
                position=[document['position'][a] for a in 'xyz'],dimensions=[document['dimensions'][a] for a in 'xyz'],
                rotation=[document['rotation'][a] for a in 'xyzw'],sourceUrl=document.get('sourceUrl',''))
            if 'color' in document:row['color']=[document['color'][a] for a in ('red','green','blue')]
            if document['type']=='Zone':
                haze=document['haze'];row.update(hazeMode=2,haze=dict(range=haze['hazeRange'],
                    color=[haze['hazeColor'][a] for a in ('red','green','blue')],glare=False,altitudeEffect=False,backgroundBlend=0))
        subject.send(dict(commandId='3'*32,runId=RUN));self.subject_before=deepcopy(subject.sample)
        subject.send(dict(commandId='4'*32,runId=RUN));self.subject_after=deepcopy(subject.sample)
        graphics=ControlNativeBoundary(GraphicsBoundary(),'phone-graphics-ui')
        graphics.send(dict(schemaVersion=1,commandId='5'*32,action='phone-graphics-ui',request=dict(schemaVersion=1,commandId='5'*32,action='observe')))
        self.ui=deepcopy(graphics.value)
        self.tablet=dict(schemaVersion=1,commandId='6'*32,action='observe',instance='e'*32,generation='f'*32,
            sourceSequence=1,lastCommandSequence=0,elapsedMs=1,capturedEpochMs=20000,processId=31,
            fileControlsVersion=1,ready=True,controls=[],scriptInventory=dict(inventoryVersion=1,complete=True,
                managers=[],pickers=[],tabletPresent=True,tabletShown=True))
        render=RenderBoundary();self.capture=deepcopy(render.reader().read(0)[0])
        self.capture['source'].update(captureVersion=2,sourceExtent=[104,94],sourceViewport=[0,0,104,94],targetExtent=[160,144],
            renderTrace=dict(traceVersion=2,recordedView=frame_view(160/144),frameId='8'*32,recordedEpochMs=20000,begunEpochMs=20000,completedEpochMs=20000,
                renderer='forward',view='main-mono',forwardBatches=2,forwardDrawCommands=8,hazeBatches=0,hazeDrawCommands=0,
                mirrorBatches=0,mirrorDrawCommands=0))
        self.image()
        provider=GraphicsResources(URL,clock_ms=lambda:20000);provider.provision(RUN);provider.activate(RUN,SCENE)
        # Explicit synthetic original socket boundary, separately covered by
        # actual loopback HTTP tests. No product scene is claimed here.
        with provider.response(RUN,SCENE,request_authority='controlled.invalid',request_scheme='http') as response:
            _,body,nonce,write=response
            write(dict(responseId=nonce,status=200,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
        provider.activate(RUN,TICKET)
        self.provider=provider.snapshot(RUN,'9'*32);self.instance=provider.instance;self.epoch=20000
        self.after_epoch=20000;self.policy=deepcopy(POLICY)

    def image(self,**options):
        self.pixels,pixel_sha=original_image(**options)
        self.capture['source']['image']=dict(name=image_name(self.capture['requestId']),bytes=len(self.pixels),
            sha256=hashlib.sha256(self.pixels).hexdigest(),pixelSha256=pixel_sha,width=160,height=144)

    def measure(self):
        return compose(RUN,TICKET,FIXTURE,31,self.provider,self.instance,self.provider['requestId'],
            self.before,self.subject_before,self.ui,self.tablet,self.capture,self.pixels,self.subject_after,self.after,
            self.epoch,self.after_epoch,self.policy)


class GraphicsMeasurementsTests(unittest.TestCase):
    def test_actual_viewport_ratios_and_executed_batch_facts_are_separate_from_preferences(self):
        source=Sources();value=source.measure()
        self.assertEqual(.65,value['state']['resolution']);self.assertAlmostEqual((104/160+94/144)/2,value['state']['renderScale'])
        self.assertFalse(value['state']['hazePass']);self.assertFalse(value['state']['mirrorPass'])
        self.assertEqual(['panel:graphics'],value['resources']);self.assertEqual(20000,value['capturedEpochMs'])
        self.assertEqual(hashlib.sha256(source.pixels).hexdigest(),value['image']['sha256'])

    def test_true_setting_cannot_substitute_for_missing_executed_passes(self):
        source=Sources()
        for native in (source.before,source.after):native['graphics'].update(hazeSetting=True,mirrorsSetting=True)
        for row in source.ui['controls']:
            if row['id'] in ('graphics.haze','graphics.mirrors'):row.update(checked=True,nativeChecked=True)
        value=source.measure()['state']
        self.assertTrue(value['haze']);self.assertTrue(value['mirror'])
        self.assertFalse(value['hazePass']);self.assertFalse(value['mirrorPass'])

    def test_executed_pass_facts_are_not_forced_to_match_false_preferences(self):
        source=Sources();source.capture['source']['renderTrace'].update(hazeBatches=1,hazeDrawCommands=4,mirrorBatches=1,mirrorDrawCommands=1)
        value=source.measure()['state'];self.assertFalse(value['haze']);self.assertTrue(value['hazePass'])
        self.assertFalse(value['mirror']);self.assertTrue(value['mirrorPass'])

    def test_missing_or_legacy_render_sources_cannot_satisfy_composition(self):
        for fault in ('legacy','missing','empty'):
            source=Sources()
            if fault=='legacy':source.capture['source'].update(captureVersion=1);source.capture['source'].pop('renderTrace')
            elif fault=='missing':source.capture['source'].pop('renderTrace')
            else:source.capture['source']['renderTrace'].update(forwardBatches=0,forwardDrawCommands=0)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.measure()

    def test_old_or_foreign_marker_pixels_fail_even_with_valid_transport_digests_and_trace(self):
        source=Sources();source.image(ticket='f'*32)
        with self.assertRaises(AssertionError):source.measure()

    def test_complete_png_and_current_marker_do_not_hide_a_blank_subject(self):
        source=Sources();source.image(blank=True)
        with self.assertRaises(AssertionError):source.measure()

    def test_ui_screen_capture_is_never_a_world_target_substitute(self):
        source=Sources();source.policy['source']='native-screen'
        with self.assertRaises(NativeUIError):source.measure()

    def test_missing_renamed_or_moved_scene_subjects_cannot_become_prepared_by_an_http_ack(self):
        for fault in ('missing','rename','move','url','mirror','haze'):
            source=Sources()
            for packet in (source.subject_before,source.subject_after):
                rows=packet['source']['entities']
                if fault=='missing':row=rows.pop();packet['source']['absentIds'].append(row['id'])
                elif fault=='rename':rows[0]['name']='foreign'
                elif fault=='move':rows[1]['position'][0]+=.1
                elif fault=='url':rows[-1]['sourceUrl']=FIXTURE+'tickets/'+TICKET+'/graphics-marker.v1.html'
                elif fault=='mirror':rows[4]['mirrorMode']='none'
                else:rows[0]['haze']['range']=1000
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.measure()

    def test_changed_camera_or_foreign_scene_cannot_match_the_owned_view(self):
        for change in (dict(position=[1,1.6,0]),dict(mode='third person'),dict(rotation=[0,1,0,0]),dict(perspective=False)):
            source=Sources()
            for packet in (source.subject_before,source.subject_after):packet['source']['view'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source.measure()

    def test_live_scene_or_view_mutation_during_capture_is_not_a_steady_comparison(self):
        for fault in ('pose','edited','projection','url'):
            source=Sources();packet=source.subject_after['source']
            if fault=='pose':packet['view']['position'][0]=.005
            elif fault=='edited':packet['entities'][0]['lastEditedEpochUs']+=1
            elif fault=='projection':packet['view']['fieldOfViewDegrees']+=1
            else:packet['sceneUrl']+='?location=/0,0,0/0,0,0,1'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.measure()

    def test_preference_or_lifecycle_change_inside_acquisition_cannot_be_hidden(self):
        for fault in ('preferences','lifecycle'):
            source=Sources()
            if fault=='preferences':source.after['graphics']['hazeSetting']=True
            else:source.after['lifecycle']['activations']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.measure()

    def test_source_ordering_rejects_old_queued_frames_even_when_image_capture_is_fresh(self):
        for fault in ('frame','subject','native'):
            source=Sources()
            if fault=='frame':source.capture['source']['renderTrace']['recordedEpochMs']-=1
            elif fault=='subject':source.subject_after['requestedEpochMs']-=1
            else:source.after['requestedEpochMs']-=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.measure()

    def test_different_native_contexts_cursors_or_missing_tablet_inventory_do_not_join(self):
        for fault in ('instance','cursor','inventory','profile'):
            source=Sources()
            if fault=='instance':source.subject_after['instance']='f'*32
            elif fault=='cursor':source.after['sequence']=source.before['sequence']
            elif fault=='inventory':source.tablet.pop('scriptInventory')
            else:next(row for row in source.ui['controls'] if row['id']=='graphics.page')['profile']='generic-immediate-v1'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.measure()

    def test_stale_phase_or_retired_provider_cannot_publish_an_original_measurement(self):
        for fault in ('barrier','clock','ticket','retired','delivery'):
            source=Sources()
            if fault=='barrier':source.after_epoch+=1
            elif fault=='clock':source.epoch+=1501
            elif fault=='ticket':source.provider['ticket']='f'*32
            elif fault=='retired':source.provider.update(active=False,ticket=None)
            else:source.provider['responses'][0]['status']=503
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):source.measure()

    def test_anisotropic_output_is_not_rounded_into_the_requested_uniform_scale(self):
        source=Sources();source.capture['source']['sourceViewport'][3]=80
        with self.assertRaises(NativeUIError):source.measure()

    def test_camera_projection_aspect_must_agree_with_original_world_target_extent(self):
        source=Sources()
        for packet in (source.subject_before,source.subject_after):packet['source']['view']['aspectRatio']=1.6
        with self.assertRaises(NativeUIError):source.measure()

    def test_fresh_capture_from_a_different_recorded_view_cannot_borrow_the_current_live_camera(self):
        for change in (dict(position=[1,1.6,0]),dict(rotation=[0,1,0,0]),dict(fieldOfViewDegrees=75)):
            source=Sources();source.capture['source']['renderTrace']['recordedView'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):source.measure()

    def test_measurement_v2_requires_recorded_view_even_when_batch_counts_and_pixels_are_valid(self):
        source=Sources();trace=source.capture['source']['renderTrace'];trace['traceVersion']=1;trace.pop('recordedView')
        with self.assertRaises(NativeUIError):source.measure()

    def test_normal_first_person_menu_mode_requires_the_same_actual_view_alignment(self):
        source=Sources()
        for packet in (source.subject_before,source.subject_after):packet['source']['view']['mode']='first person look at'
        self.assertEqual(.65,source.measure()['state']['resolution'])
        for packet in (source.subject_before,source.subject_after):packet['source']['view']['position'][2]=1
        with self.assertRaises(NativeUIError):source.measure()

    def test_foreign_entities_in_controlled_subject_scan_keep_preparation_red(self):
        source=Sources()
        for packet in (source.subject_before,source.subject_after):
            packet['source']['scan'].update(scannedEntities=8,unowned=[dict(id='11111111-1111-4111-8111-111111111111',sha256='f'*64)])
        with self.assertRaises(NativeUIError):source.measure()

    def test_v2_avatar_pose_must_remain_steady_during_original_frame_capture(self):
        for fault in ('none','position','orientation','scale'):
            source=Sources()
            for packet in (source.subject_before,source.subject_after):
                packet['source'].update(subjectVersion=2,avatarPose=dict(feetPosition=[0,-.2,0],orientation=[0,0,0,1],modelScale=1.25))
            pose=source.subject_after['source']['avatarPose']
            if fault=='position':pose['feetPosition'][0]=.01
            elif fault=='orientation':pose['orientation']=[0,1,0,0]
            elif fault=='scale':pose['modelScale']=1.5
            if fault=='none':self.assertEqual(.65,source.measure()['state']['resolution'])
            else:
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.measure()

    def test_closed_ui_is_observed_from_original_page_and_tablet_sources(self):
        source=Sources();source.ui['controls']=[];source.tablet['scriptInventory']['tabletShown']=False
        value=source.measure();self.assertFalse(value['state']['dialog']);self.assertEqual([],value['resources'])


if __name__=='__main__':unittest.main()
