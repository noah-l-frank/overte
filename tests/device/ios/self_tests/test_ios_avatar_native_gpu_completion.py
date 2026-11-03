"""Real HTTP/AFC GPU completion and ordinary frame owner; native GPU is modeled.

No pending DTO is declared complete, no timestamp/result/decoder is patched,
and original1.5s guards remain literal. Actual source polls the original fence
producer; retained completed bodies must stay immutable after real time passes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import hashlib,json,time,unittest,uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.native_vulkan_world_frame import validate as validate_frame,absent
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor
from ios.self_tests.avatar_prepare_fixture import RUN,TICKET
from ios.self_tests import test_ios_avatar_prepare_composed as preparation


class AvatarNativeGPUCompletionTests(preparation.AvatarPrepareComposedTests):
    def gpu(self):
        f=NativeInstalledFrontdoor(self);d=f.domain;role='primary';flow=d.owners[role]
        request='ios-'+uuid.uuid4().hex
        # Declare the existing modeled producer before the first actual Read.
        # Inspect allocates no frame/callback/PNG; consumers still use original
        # real HTTP/AFC and the existing production VulkanWorldFrameOwner.
        producer=d.natives[role].avatar_channels.raw_reader('gpu')
        producer.send(dict(schemaVersion=1,action='feature-vulkan-world-frame',commandId='ios-'+uuid.uuid4().hex,
            requestId=request,operation='inspect'))
        root=f.root/'original-gpu-owner';root.mkdir(mode=0o700)
        return f,d,flow,request,root,d.scenes[role].gpus[request]
    def owner(self,f,d,flow,request,root):
        runtime=IOSAvatarRuntime(f.adapter);source=runtime._sources('primary')
        return VulkanWorldFrameOwner(PrivateFeatureState(flow.lock.path.with_name('graphics-world-frame-primary-0-'+request[4:]+'.json')),root,source['binding'],RUN,'primary',0,request,
            lambda intent,receipt:source['observer'].vulkan_world_frame(intent,receipt),source['check'],source_lock=flow.lock)
    def test_original_owner_receives_completed_fence_png_from_one_read_and_separately_observes_absence(self):
        f,d,flow,request,root,gpu=self.gpu()
        with flow.held(paired=True):
            owner=self.owner(f,d,flow,request,root);capture,png=owner.capture(TICKET)
            self.assertGreater(len(png),0);self.assertEqual(hashlib.sha256(png).hexdigest(),capture['source']['image']['sha256'])
            self.assertEqual(1,sum(row['operation']=='read' for row in gpu.commands))
            self.assertIsNone(d.natives['primary'].avatar_channels.pending_gpu)
            original=d.natives['primary'].avatar_channels.originals['feature-vulkan-world-frame.json'];time.sleep(.06)
            source=IOSAvatarRuntime(f.adapter)._sources('primary');remote=source['observer'].remote.rsplit('/',1)[0]+'/feature-vulkan-world-frame.json'
            self.assertEqual(original,source['observer'].original(remote=remote,limit=131072))
            self.assertEqual(capture,owner.state['frame'])
            self.assertEqual(json.loads(original)['capturedEpochMs'],json.loads(source['observer'].original(remote=remote,limit=131072))['capturedEpochMs'])
            self.assertTrue(absent(owner.release()));self.assertEqual(1,sum(row['operation']=='release' for row in gpu.commands))
            self.assertEqual(png,(root/owner.name).read_bytes())
    def test_actual_pending_afc_body_advances_after_original_fence_without_command_resend_or_completed_reclock(self):
        f,d,flow,request,root,gpu=self.gpu();gpu.no_fence=True;commands=[]
        with flow.held(paired=True):
            source=IOSAvatarRuntime(f.adapter)._sources('primary');observer=source['observer'];remote=observer.remote.rsplit('/',1)[0]+'/feature-vulkan-world-frame.json'
            store=PrivateFeatureState(root/'direct-original-command-intents.json')
            def send(operation):
                query=dict(schemaVersion=1,action='feature-vulkan-world-frame',commandId='ios-'+uuid.uuid4().hex,requestId=request,operation=operation)
                old=store.read();commands.append(deepcopy(query));store.write(dict(declaredOriginalQueries=commands),old);observer.send(query);return query
            query=send('read');pending=observer.original(remote=remote,limit=131072)
            self.assertTrue(json.loads(pending)['pending']);(root/'actual-first-pending.txt').write_text(pending)
            gpu.no_fence=False;time.sleep(.06);completed=observer.original(remote=remote,limit=131072);value=json.loads(completed)
            validate_frame(value,query,31,source['clock_source'].read(0)['capturedEpochMs'])
            self.assertNotIn('pending',value);self.assertEqual(1,sum(row['operation']=='read' for row in gpu.commands))
            time.sleep(.06);self.assertEqual(completed,observer.original(remote=remote,limit=131072))
            (root/'actual-completed-original.txt').write_text(completed)
            send('release');time.sleep(.12);final=send('inspect');self.assertTrue(absent(json.loads(observer.original(remote=remote,limit=131072))))
            self.assertEqual('inspect',final['operation']);self.assertEqual(1,sum(row['operation']=='release' for row in gpu.commands))
    def test_genuine_missing_fence_still_refuses_with_original1point5_guard_and_recovers_without_new_read_or_release(self):
        f,d,flow,request,root,gpu=self.gpu();gpu.no_fence=True
        with flow.held(paired=True):
            owner=self.owner(f,d,flow,request,root);started=time.monotonic()
            with self.assertRaises(NativeUIError):owner.capture(TICKET)
            self.assertGreaterEqual(time.monotonic()-started,1.5);self.assertIsNone(owner.state['frame'])
            self.assertEqual(0,(root/owner.name).stat().st_size);self.assertEqual(1,sum(row['operation']=='read' for row in gpu.commands))
            proof=owner.release_once();self.assertFalse(absent(proof))
            self.assertIsNone(owner.state['absence']);self.assertEqual(1,sum(row['operation']=='release' for row in gpu.commands))
            gpu.no_fence=False;time.sleep(.12)
            self.assertTrue(absent(owner.release()));self.assertEqual(1,sum(row['operation']=='read' for row in gpu.commands))
            self.assertEqual(1,sum(row['operation']=='release' for row in gpu.commands));self.assertIsNone(owner.state['frame'])


if __name__=='__main__':unittest.main()
