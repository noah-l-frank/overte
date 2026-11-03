"""The actual painted view remains paired with its lease's original pixels.

All consumers/owned PNG/HTTP/AFC/clock guards remain real; camera/GPU are
explicit native producer models. Future view input occurs only after actual
Read painted, before its genuine original fence completes. No saved row is
modified, and no failed/native clock is renewed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib,unittest,uuid
from adapters.native_vulkan_world_frame import absent
from ios.self_tests.test_ios_avatar_native_gpu_completion import AvatarNativeGPUCompletionTests
from ios.self_tests.avatar_prepare_fixture import TICKET


class AvatarGPUOriginalViewLeaseTests(AvatarNativeGPUCompletionTests):
    def camera_change(self,*,duplicate):
        f,d,flow,request,root,gpu=self.gpu();producer=d.natives['primary'].avatar_channels.raw_reader('gpu')
        old_view=deepcopy(d.recorded_view('primary'));send=producer.send;changed=[]
        def future(query):
            result=send(query)
            if query['operation']=='read' and not changed:
                original=dict(started=gpu.started,request=deepcopy(gpu.request),value=deepcopy(gpu.value),png=gpu.png)
                d.scenes['primary'].domain.world_template['source']['view']['position'][0]+=.1
                changed.append(deepcopy(d.recorded_view('primary')))
                if duplicate:
                    send(query)
                    self.assertEqual(original,dict(started=gpu.started,request=gpu.request,value=gpu.value,png=gpu.png))
            return result
        producer.send=future
        with flow.held(paired=True):
            owner=self.owner(f,d,flow,request,root);frame,png=owner.capture(TICKET);producer.send=send
            self.assertEqual(1,len(changed));self.assertNotEqual(old_view,changed[0])
            self.assertEqual(old_view,frame['source']['renderTrace']['recordedView'])
            self.assertEqual(hashlib.sha256(png).hexdigest(),frame['source']['image']['sha256'])
            self.assertEqual(1,sum(row['operation']=='read' for row in gpu.commands))
            self.assertTrue(absent(owner.release()));self.assertEqual(png,owner.archive())
            # A genuinely new lease must paint the current changed projection.
            later='ios-'+uuid.uuid4().hex
            producer.send(dict(schemaVersion=1,action='feature-vulkan-world-frame',commandId='ios-'+uuid.uuid4().hex,
                requestId=later,operation='inspect'))
            newer=self.owner(f,d,flow,later,root);new_frame,new_png=newer.capture(TICKET)
            self.assertEqual(changed[0],new_frame['source']['renderTrace']['recordedView']);self.assertNotEqual(png,new_png)
            self.assertTrue(absent(newer.release()));self.assertEqual(new_png,newer.archive())
            self.assertEqual(png,owner.archive());self.assertEqual(old_view,owner.state['frame']['source']['renderTrace']['recordedView'])
    def test_completed_original_frame_keeps_actual_paint_time_view_after_camera_changes_before_fence(self):
        self.camera_change(duplicate=False)
    def test_exact_uncertain_read_cannot_rebind_old_pixels_to_future_view_but_new_lease_is_fresh(self):
        self.camera_change(duplicate=True)


if __name__=='__main__':unittest.main()
