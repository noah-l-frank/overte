"""Real HTTP/AFC image owners preserve each original rendered lease.

Native GPU/Qt/scene producers are declared models. No frame/decoder/returned
PNG is patched: actual paint is counted and later source scene state changes
before real original-byte/storage queries and a genuinely new Read.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64,hashlib,json,unittest,uuid
from adapters.native_vulkan_world_frame import absent,storage
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor
from ios.self_tests.test_ios_avatar_native_gpu_completion import AvatarNativeGPUCompletionTests
from ios.self_tests.avatar_prepare_fixture import RUN,TICKET


class AvatarGPUOriginalPixelLeaseTests(AvatarNativeGPUCompletionTests):
    def first_lease(self):
        f=NativeInstalledFrontdoor(self);d=f.domain;flow=d.owners['primary'];paints=[];paint=d.paint
        def rendered(role):
            image=paint(role);paints.append(dict(role=role,pixelsSha256=hashlib.sha256(image.tobytes()).hexdigest()))
            return image
        d.paint=rendered;request='ios-'+uuid.uuid4().hex
        producer=d.natives['primary'].avatar_channels.raw_reader('gpu')
        producer.send(dict(schemaVersion=1,action='feature-vulkan-world-frame',commandId='ios-'+uuid.uuid4().hex,
            requestId=request,operation='inspect'))
        self.assertEqual([],paints)
        root=f.root/'original-gpu-pixel-lease';root.mkdir(mode=0o700)
        return f,d,flow,request,root,paints,producer
    def test_actual_inspect_bytes_archive_release_do_not_repaint_or_change_original_png(self):
        f,d,flow,request,root,paints,producer=self.first_lease()
        with flow.held(paired=True):
            owner=self.owner(f,d,flow,request,root);frame,png=owner.capture(TICKET);gpu=d.scenes['primary'].gpus[request]
            self.assertEqual(1,len(paints));self.assertEqual(png,gpu.png)
            self.assertEqual(hashlib.sha256(png).hexdigest(),frame['source']['image']['sha256'])
            self.assertEqual(paints[0]['pixelsSha256'],frame['source']['image']['pixelSha256'])
            saved=deepcopy(owner.state['frame']);pixels=gpu.raw_pixels
            self.assertEqual(png,owner.archive());self.assertTrue(absent(owner.release()));self.assertEqual(png,owner.archive())
            self.assertEqual(1,len(paints));self.assertEqual(saved,owner.state['frame']);self.assertEqual(png,gpu.png);self.assertEqual(pixels,gpu.raw_pixels)
            self.assertEqual(1,sum(row['operation']=='read' for row in gpu.commands))
            self.assertEqual(1,sum(row['operation']=='release' for row in gpu.commands))
    def test_scene_change_and_uncertain_same_read_preserve_pixels_but_next_new_read_captures_fresh_scene(self):
        f,d,flow,request,root,paints,producer=self.first_lease()
        with flow.held(paired=True):
            send=producer.send;duplicates=[]
            def uncertain(query):
                result=send(query)
                if query['operation']=='read' and not duplicates:
                    gpu=d.scenes['primary'].gpus[request]
                    original=dict(started=gpu.started,request=deepcopy(gpu.request),value=deepcopy(gpu.value))
                    send(query);duplicates.append(deepcopy(query))
                    self.assertEqual(original,dict(started=gpu.started,request=gpu.request,value=gpu.value))
                return result
            producer.send=uncertain
            owner=self.owner(f,d,flow,request,root);frame,png=owner.capture(TICKET);gpu=d.scenes['primary'].gpus[request]
            producer.send=send;self.assertEqual(1,len(duplicates))
            self.assertEqual(1,len(paints));original_pixels=gpu.raw_pixels;original_frame=deepcopy(frame)
            # Explicit future scene producer input, never a retained original
            # rewrite or a decoder/result substitution.
            d.widgets['primary'].scale*=1.1
            # One separately retained pure byte query uses the actual HTTP/AFC
            # transport after the scene changed. It issues no new frame input.
            query=dict(schemaVersion=1,action='feature-vulkan-world-frame',commandId='ios-'+uuid.uuid4().hex,
                requestId=request,operation='read-bytes',offset=0)
            journal=PrivateFeatureState(root/'counter-original-storage-query.json');journal.write(query,None)
            source=IOSAvatarRuntime(f.adapter)._sources('primary');observer=source['observer'];observer.send(query)
            remote=observer.remote.rsplit('/',1)[0]+'/feature-vulkan-world-frame.json'
            raw=observer.original(remote=remote,limit=131072);packet=json.loads(raw)
            storage(packet,query,31,source['clock_source'].read(0)['capturedEpochMs'])
            self.assertEqual(png[:65536],base64.b64decode(packet['source']['data'],validate=True))
            self.assertEqual(1,len(paints));self.assertEqual(png,gpu.png);self.assertEqual(original_pixels,gpu.raw_pixels)
            self.assertEqual(png,owner.archive());self.assertTrue(absent(owner.release()));self.assertEqual(1,len(paints))
            next_request='ios-'+uuid.uuid4().hex
            producer.send(dict(schemaVersion=1,action='feature-vulkan-world-frame',commandId='ios-'+uuid.uuid4().hex,
                requestId=next_request,operation='inspect'))
            self.assertEqual(1,len(paints))
            newer=self.owner(f,d,flow,next_request,root);new_frame,new_png=newer.capture(TICKET)
            self.assertEqual(2,len(paints));self.assertNotEqual(png,new_png)
            self.assertNotEqual(frame['source']['image']['pixelSha256'],new_frame['source']['image']['pixelSha256'])
            self.assertEqual(paints[1]['pixelsSha256'],new_frame['source']['image']['pixelSha256'])
            self.assertTrue(absent(newer.release()));self.assertEqual(new_png,newer.archive())
            self.assertEqual(png,owner.archive());self.assertEqual(original_frame,owner.state['frame']);self.assertEqual(2,len(paints))
            self.assertEqual(1,sum(row['operation']=='read' for row in gpu.commands))
            self.assertEqual(1,sum(row['operation']=='read' for row in d.scenes['primary'].gpus[next_request].commands))


if __name__=='__main__':unittest.main()
