"""Original Vulkan-world pixel effects with visible ordinary Graphics UI."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import unittest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_world_effects import compare
from ios.self_tests.test_ios_graphics_measurements import provider_source,HOST,URL,BINDING,RUN
from ios.self_tests.test_ios_graphics_world_measurements import world_bundle,rebind


def observed_effect(frame,raw,feature,rgb):
    # Rasterize a synthetic native target stimulus. This helper supplies no
    # adapter verdict; the actual production decoder/statistics judge its bytes.
    from PIL import ImageDraw
    from adapters.graphics_subject_geometry import projected_box
    from feature_journeys.graphics_fixture import subject_ids
    target=next(row for row in frame['subjectAfter']['source']['entities']
                if row['id']==subject_ids(RUN)['fog-board' if feature=='haze' else 'reflector'])
    source=frame['capture']['source'];box=projected_box(target,source['renderTrace']['recordedView'],source['targetExtent'])
    image=Image.open(BytesIO(raw));draw=ImageDraw.Draw(image);dx=(box[2]-box[0])*.25;dy=(box[3]-box[1])*.25
    draw.rectangle([round(box[0]+dx),round(box[1]+dy),round(box[2]-dx),round(box[3]-dy)],fill=rgb)
    original=Image.open(BytesIO(raw));image.paste(original.crop((170,60,470,145)),(170,60))
    stream=BytesIO();image.save(stream,format='PNG');content=stream.getvalue()
    source['image'].update(bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
    rebind(frame);return content


class WorldEffects(unittest.TestCase):
    def samples(self,feature):
        provider=provider_source();before,raw_before,policy,instance=world_bundle(dialog=True,provider=provider)
        after,raw_after,_policy,_instance=world_bundle(dialog=True,provider=provider,ticket='8'*32,start=2000,**{feature:True})
        return [before,raw_before,after,raw_after,policy,instance]

    def measure(self,feature,samples,epoch=HOST+2600):
        before,a,after,b,policy,instance=samples
        return compare(RUN,feature,URL,BINDING,before,a,after,b,policy,instance,lambda:epoch,lambda:True,monotonic=lambda:0.)

    def test_actual_haze_and_reflection_pixels_are_required_even_with_visible_fullscreen_ui(self):
        for feature,rgb in (('haze',(25,90,210,255)),('mirror',(255,90,0,255))):
            samples=self.samples(feature);samples[3]=observed_effect(samples[2],samples[3],feature,rgb)
            actual=self.measure(feature,samples)
            self.assertGreater(actual['changedFraction'],.05);self.assertGreater(actual['pixels'],64)
            self.assertTrue(samples[2]['tablet']['scriptInventory']['tabletShown'])

    def test_changed_settings_issued_draws_and_challenge_without_effect_pixels_fail(self):
        for feature in ('haze','mirror'):
            with self.subTest(feature=feature),self.assertRaises(NativeUIError):self.measure(feature,self.samples(feature))

    def test_wrong_colors_or_expired_after_frame_cannot_be_effect_proof(self):
        for feature,rgb in (('haze',(255,0,0,255)),('mirror',(0,60,255,255))):
            samples=self.samples(feature);samples[3]=observed_effect(samples[2],samples[3],feature,rgb)
            with self.subTest(feature=feature),self.assertRaises(NativeUIError):self.measure(feature,samples)
        samples=self.samples('haze');samples[3]=observed_effect(samples[2],samples[3],'haze',(25,90,210,255))
        with self.assertRaises(NativeUIError):self.measure('haze',samples,epoch=HOST+4000)


if __name__=='__main__':unittest.main()
