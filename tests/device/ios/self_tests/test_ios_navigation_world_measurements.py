"""Real PNG/pixel and pure original joins, with synthetic GPU/native state only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import unittest

from PIL import Image,ImageDraw
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters import navigation_world_measurements as measured
from ios.self_tests.test_ios_navigation_state import Boundary as State,RUN,URL
from self_tests.test_native_vulkan_world_frame import World,request
from self_tests.test_native_completed_frame import view
from self_tests.test_native_feature_observation import Boundary as Native
from self_tests.test_completed_frame_lease import BINDING
from navigation_observation import viewpoint_urls


def global_packet(epoch,sequence):
    native=Native();native.send(dict(commandId='ios-'+str(sequence)*32))
    value=native.sample;value.update(processId=42,sequence=sequence,requestedEpochMs=epoch,capturedEpochMs=epoch,
        animation={},animationFence={})
    return value


def rebind(frame):
    packets=measured.originals(frame);frame['clockJoin']['originalsSha256']=digest(packets)
    frame['clockJoin']['sourceTimes']=[dict(source=name,field=field,epochMs=packet[field]) for name,packet in packets.items()
        for field in ('capturedEpochMs','sampleEpochMs') if field in packet]


def bundle(label='A',*,color=(180,80,180,255)):
    # All packets here are newly constructed SDK fixture originals. Production
    # code never rewrites original frames, native times, pixels or their hashes.
    state=State();reader=state.reader();native_before=state.epoch();x=0 if label=='A' else 2
    url=viewpoint_urls(URL)[label];state.source['sceneUrl']=url;state.source['avatar']['feetPosition']=[x,0,4]
    state.source['view'].update(position=[x,1.6,4],aspectRatio=1.6)
    before=reader.read(RUN);gpu=World();gpu.clock=state.clock+.005
    recorded=view();recorded['position']=[x,1.6,4]
    image=Image.new('RGBA',(320,200),(120,120,120,255));draw=ImageDraw.Draw(image)
    def project(world):
        camera=[a-b for a,b in zip(world,recorded['position'])]+[1]
        clip=[sum(recorded['projection'][row*4+col]*camera[col] for col in range(4)) for row in range(4)]
        return [(clip[0]/clip[3]+1)*160,(1-clip[1]/clip[3])*100]
    corners=[project(point) for point in [[-4,0,.75],[-4,4,.75],[4,4,.75],[4,0,.75]]]
    draw.polygon([tuple(point) for point in corners],fill=color)
    output=BytesIO();image.save(output,format='PNG');gpu.png=output.getvalue();gpu.raw_pixels=image.tobytes()
    def record(value):
        if 'source' in value and 'renderTrace' in value['source']:value['source']['renderTrace']['recordedView']=deepcopy(recorded)
    gpu.change=record;frames=gpu.reader();query=request();capture=frames.perform(query);raw=frames.image(capture)
    frames.perform(request('release','e'));gpu.sleep(.2);retired=frames.perform(request('inspect','f'))
    state.clock=gpu.clock+.001;after=reader.read(RUN);native_after=state.epoch()+1
    frame=dict(navigationBefore=before,capture=capture,retirement=retired,navigationAfter=after,
        clockJoin=dict(clockJoinVersion=1,hostBeforeEpochMs=1_000_000.,hostAfterEpochMs=1_000_000.+native_after-native_before,
            hostBeforeMonotonic=10.,hostAfterMonotonic=10.+(native_after-native_before)/1000,
            nativeBefore=global_packet(native_before,1),nativeAfter=global_packet(native_after,2)))
    rebind(frame);return frame,raw,query,url


class NavigationWorldMeasurements(unittest.TestCase):
    def measure(self,sample,label='A'):
        frame,raw,query,url=sample
        return measured.compose(RUN,BINDING,frame,raw,url=url,label=label,capture_query=query)

    def test_original_vulkan_pixels_native_pose_scene_and_retirement_remain_separate(self):
        sample=bundle();before=deepcopy(sample[0]);result=self.measure(sample)
        self.assertEqual(before,sample[0]);self.assertEqual('A',result['location'])
        self.assertEqual(hashlib.sha256(sample[1]).hexdigest(),result['imageSha256'])
        self.assertEqual('controlled-purple-wall-v1',result['pixels']['profile'])
        self.assertGreaterEqual(len(result['pixels']['samples']),6)
        self.assertNotIn('passed',result);self.assertNotIn('image',result)
        self.assertEqual(1_000_000,result['acquiredHostEpochMs'])
        self.assertGreater(result['nativeEpochMs'],1700000000000)

    def test_actual_B_pose_and_recorded_camera_project_independent_changed_scene_pixels(self):
        a=bundle('A');b=bundle('B');result=self.measure(b,'B')
        self.assertEqual('B',result['location']);self.assertNotEqual(a[1],b[1])
        self.assertNotEqual(a[0]['capture']['source']['renderTrace']['recordedView']['position'],
                            b[0]['capture']['source']['renderTrace']['recordedView']['position'])

    def test_matching_native_pose_and_gpu_ack_without_visible_scene_effect_fails(self):
        for color in ((120,120,120,255),(0,0,0,255),(180,180,80,255),(255,0,0,255)):
            with self.subTest(color=color),self.assertRaises(NativeUIError):self.measure(bundle(color=color))

    def test_foreign_or_truncated_png_cannot_borrow_another_native_hash(self):
        sample=bundle();frame,raw,query,url=sample
        for replacement in (raw[:-10],bundle('B')[1]):
            with self.assertRaises(NativeUIError):self.measure((frame,replacement,query,url))

    def test_unchanged_original_camera_cannot_be_replaced_by_an_expected_view(self):
        for field,new in [('position',[2,1.6,4]),('fieldOfViewDegrees',75),('aspectRatio',1.8),('rotation',[0,1,0,0])]:
            frame,raw,query,url=bundle();frame['capture']['source']['renderTrace']['recordedView'][field]=new;rebind(frame)
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.measure((frame,raw,query,url))

    def test_no_draws_or_wrong_render_stage_are_not_actual_scene_pixels(self):
        for fault in ('draws','stage','backend'):
            frame,raw,query,url=bundle();source=frame['capture']['source']
            if fault=='draws':source['renderTrace'].update(forwardBatches=0,forwardDrawCalls=0)
            elif fault=='stage':source['stage']='hud'
            else:source['backend']='opengl'
            rebind(frame)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.measure((frame,raw,query,url))

    def test_release_ack_cannot_hide_retained_callbacks_gpu_or_original_allocations(self):
        for field,new in [('callbacks',1),('gpuPending',True),('pngBytes',1),('gpuBufferBytes',1),('retired',False)]:
            frame,raw,query,url=bundle();frame['retirement']['source'][field]=new;rebind(frame)
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.measure((frame,raw,query,url))

    def test_scene_reloaded_during_original_frame_is_not_the_bracketed_scene(self):
        frame,raw,query,url=bundle();scene=frame['navigationAfter']['source']['sceneLoads'];scene['currentGeneration']=2
        scene['requests'].append(dict(scene['requests'][0],id='f'*32,generation=2));rebind(frame)
        with self.assertRaises(NativeUIError):self.measure((frame,raw,query,url))

    def test_camera_or_avatar_motion_inside_native_bracket_invalidates_the_frame(self):
        for field,new in [('view',[.01,1.6,4]),('avatar',[.05,0,4])]:
            frame,raw,query,url=bundle();source=frame['navigationAfter']['source']
            source[field]['position' if field=='view' else 'feetPosition']=new;rebind(frame)
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.measure((frame,raw,query,url))

    def test_native_utc_cannot_conceal_a_different_elapsed_source_gap(self):
        frame,raw,query,url=bundle()
        for clock in ('clockBefore','clockAfter'):frame['navigationAfter'][clock]['monotonicMs']+=500
        rebind(frame)
        with self.assertRaises(NativeUIError):self.measure((frame,raw,query,url))

    def test_fresh_digest_cannot_make_an_earlier_capture_follow_native_before(self):
        frame,raw,query,url=bundle()
        packet=frame['navigationBefore'];packet['clockBefore']['epochMs']=frame['capture']['requestedEpochMs']+1
        packet['clockAfter']['epochMs']=packet['clockBefore']['epochMs']
        packet['source']['sceneLoads']['capturedEpochMs']=packet['clockBefore']['epochMs'];rebind(frame)
        with self.assertRaises(NativeUIError):self.measure((frame,raw,query,url))

    def test_foreign_pid_request_and_ownership_binding_cannot_be_accepted(self):
        for fault in ('pid','request','binding','run','lifecycle'):
            frame,raw,query,url=bundle();binding=deepcopy(BINDING);run=RUN
            if fault=='pid':frame['capture']['processId']=43
            elif fault=='request':query=dict(query,requestId='ios-'+'9'*32)
            elif fault=='binding':binding['processIdentity']='43'
            elif fault=='run':run='f'*32
            else:frame['clockJoin']['nativeAfter']['lifecycle']['backgrounds']+=1
            rebind(frame)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):measured.compose(run,binding,frame,raw,
                url=url,label='A',capture_query=query)


if __name__=='__main__':unittest.main()
