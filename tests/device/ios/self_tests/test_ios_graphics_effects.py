"""Synthetic original-screen subject effects, distinct from settings and marker."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import unittest
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from adapters.graphics_subject_geometry import projected_box
from feature_journeys.graphics_fixture import subject_ids
from ios.adapters.graphics_effects import compare
from ios.self_tests.test_ios_graphics_measurements import original_bundle,provider_source,rebind,HOST,URL,BINDING,RUN


def paint(frame,raw,feature,rgb):
    source=frame['frameAfter']['source'];name='fog-board' if feature=='haze' else 'reflector'
    row=next(row for row in frame['subjectAfter']['source']['entities'] if row['id']==subject_ids(RUN)[name])
    box=projected_box(row,source['renderTrace']['recordedView'],source['targetExtent'])
    image=Image.open(BytesIO(raw));draw=ImageDraw.Draw(image)
    dx=(box[2]-box[0])*.25;dy=(box[3]-box[1])*.25
    draw.rectangle([round(box[0]+dx),round(box[1]+dy),round(box[2]-dx),round(box[3]-dy)],fill=rgb)
    # The model's native screenshot preserves its separately rendered challenge.
    original=Image.open(BytesIO(raw));image.paste(original.crop((170,60,470,145)),(170,60))
    stream=BytesIO();image.save(stream,format='PNG');result=stream.getvalue()
    frame['screen'].update(bytes=len(result),sha256=hashlib.sha256(result).hexdigest());rebind(frame)
    return result


class EffectTests(unittest.TestCase):
    def samples(self,feature,*,before_on=False,after_on=True):
        provider=provider_source()
        before,raw_before,policy,instance=original_bundle(provider=provider,**{feature:before_on})
        after,raw_after,_policy,_instance=original_bundle(provider=provider,ticket='8'*32,start=2000,**{feature:after_on})
        return before,raw_before,after,raw_after,policy,instance

    def compare(self,feature,samples,*,epoch=HOST+2600,guard=lambda:True,monotonic=lambda:0.):
        before,raw_before,after,raw_after,policy,instance=samples
        return compare(RUN,feature,URL,BINDING,before,raw_before,after,raw_after,policy,instance,
                       lambda:epoch,guard,monotonic=monotonic)

    def test_original_blue_haze_and_orange_reflection_pixels_are_measured(self):
        for feature,rgb in (('haze',(25,90,210)),('mirror',(255,90,0))):
            samples=list(self.samples(feature));samples[3]=paint(samples[2],samples[3],feature,rgb)
            result=self.compare(feature,samples)
            self.assertGreater(result['changedFraction'],.05);self.assertGreater(result['pixels'],64)
            if feature=='haze':self.assertGreater(result['blueDominanceAfter']-result['blueDominanceBefore'],10)
            else:self.assertGreater(result['orangeFractionAfter']-result['orangeFractionBefore'],.005)

    def test_disabling_uses_observed_native_direction_and_actual_pixel_reversal(self):
        samples=list(self.samples('haze',before_on=True,after_on=False))
        samples[1]=paint(samples[0],samples[1],'haze',(25,90,210));samples[3]=paint(samples[2],samples[3],'haze',(180,180,180))
        result=self.compare('haze',samples);self.assertLess(result['blueDominanceAfter'],result['blueDominanceBefore'])

    def test_setting_and_draw_flags_with_only_a_changed_challenge_cannot_prove_effect(self):
        for feature in ('haze','mirror'):
            with self.subTest(feature=feature),self.assertRaises(NativeUIError):self.compare(feature,self.samples(feature))

    def test_wrong_color_or_unrelated_subject_changes_cannot_substitute_for_haze_or_reflection(self):
        for feature,rgb in (('haze',(255,20,0)),('mirror',(20,90,255))):
            samples=list(self.samples(feature));samples[3]=paint(samples[2],samples[3],feature,rgb)
            with self.subTest(feature=feature),self.assertRaises(NativeUIError):self.compare(feature,samples)

    def test_changed_camera_resolution_context_or_other_preference_refuses_pixel_comparison(self):
        for fault in ('camera','resolution','lifecycle','source'):
            samples=list(self.samples('haze'));samples[3]=paint(samples[2],samples[3],'haze',(25,90,210));after=samples[2]
            if fault=='camera':after['frameBefore']['source']['renderTrace']['recordedView']['position'][0]=1
            elif fault=='resolution':
                for key in ('frameBefore','frameAfter'):after[key]['source']['sourceExtent']=[384,240]
            elif fault=='lifecycle':after['nativeBefore']['lifecycle']['backgrounds']=1
            else:after['nativeBefore']['sequence']=samples[0]['nativeBefore']['sequence']
            rebind(after)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.compare('haze',samples)

    def test_stale_after_interval_lost_guard_and_time_budget_are_rejected(self):
        samples=list(self.samples('haze'));samples[3]=paint(samples[2],samples[3],'haze',(25,90,210))
        for options in (dict(epoch=HOST+4000),dict(guard=lambda:False)):
            with self.subTest(options=options),self.assertRaises(NativeUIError):self.compare('haze',samples,**options)
        times=iter([0.,0.,6.])
        with self.assertRaises(NativeUIError):self.compare('haze',samples,monotonic=lambda:next(times))


if __name__=='__main__':unittest.main()
