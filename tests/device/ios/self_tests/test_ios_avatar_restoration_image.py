"""Real private fenced frames; independently modeled native Avatar renderer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import unittest
from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.original_marker_scope import _components
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
from ios.adapters.avatar_restoration_image import restored
from ios.self_tests import test_ios_emote_restoration_frames as fixture
from ios.self_tests.test_ios_avatar_images import bundle
from ios.self_tests.test_ios_graphics_measurements import RUN,HOST


class AvatarRestorationImageTests(unittest.TestCase):
    def setUp(self):
        self.raw=fixture.RawFramesTests();self.raw.setUp();self.addCleanup(self.raw.doCleanups)
        f=self.raw.fixture;template,_pixels,_policy=bundle()
        # The producer emits the independent Avatar schema and marker owner
        # data from its own Avatar fixture; retained DTOs are never relabeled.
        f.template=deepcopy(template);self.raw.tree=deepcopy(template['worldBefore']['source']['tree'])
        self.raw.tree.update(totalEntities=0,entities=[])
        scope=object.__new__(IOSAvatarMarkerScope);scope.__dict__.update(f.scope.__dict__)
        scope._marker_components=_components('avatar');f.scope=scope
        world=f.world
        def actual_world(run):
            value=world(run)
            value.pop('iosEmoteWorldVersion',None);value['iosAvatarWorldVersion']=1
            value['clockDomain']='native-main-avatar-world'
            value['source']['bodies'].update(sequence=value['sequence'],capturedEpochMs=value['clockAfter']['epochMs'])
            return value
        f.world=actual_world;sources=f.runtime._sources
        def source(selector):
            value=sources(selector)
            value['observer'].avatar_world=lambda _clock:type('Reader',(),{'last':None,'read':lambda _self,run:actual_world(run)})()
            return value
        f.runtime._sources=source
        self.owner=IOSAvatarRestorationFrames(f.runtime,'owned',scope,f.root,f.lock,monotonic=lambda:f.gpu.clock,
            epoch_ms=lambda:HOST+f.gpu.clock*1000,sleep=lambda duration:f.gpu.sleep(duration))
        self.before=self.owner.capture('initial');self.raw.marker(True)
        self.admission=actual_world(RUN);self.marker=self.admission['source']['markers'][0]['id']
    def finish(self,*,outside=False):
        f=self.raw.fixture;self.raw.marker(False)
        if outside:
            image=Image.open(BytesIO(f.raw)).convert('RGBA');image.putpixel((0,0),(240,10,100,255))
            stream=BytesIO();image.save(stream,format='PNG');f.raw=stream.getvalue()
        f.scope.state.update(phase='released',pending=None);self.barrier=f.native(None).read(0)
        return self.owner.capture('cleanup')
    def test_untouched_original_full_output_restores_only_after_actual_native_barrier(self):
        reference=self.finish();value=restored(self.owner,self.before,reference,self.admission,self.marker,after_native=self.barrier)
        self.assertEqual(0,value['changedPixels']);self.assertEqual(640*400,value['pixels'])
    def test_single_stale_pixel_outside_both_avatar_and_marker_cannot_hide_in_tolerance(self):
        reference=self.finish(outside=True)
        from adapters.original_marker_restoration_image import restored as marker_only
        self.assertEqual(0,marker_only(self.owner,self.before,reference,self.admission,self.marker,after_native=self.barrier)['changedPixels'])
        with self.assertRaises(NativeUIError):restored(self.owner,self.before,reference,self.admission,self.marker,after_native=self.barrier)
    def test_new_native_endpoint_after_frame_invalidates_unchanged_pixels(self):
        reference=self.finish();self.barrier=self.raw.fixture.native(None).read(0)
        with self.assertRaises(NativeUIError):restored(self.owner,self.before,reference,self.admission,self.marker,after_native=self.barrier)


if __name__=='__main__':unittest.main()
