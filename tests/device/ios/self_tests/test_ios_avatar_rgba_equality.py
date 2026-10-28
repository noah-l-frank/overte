"""Actual fenced PNGs and complete RGBA boundaries; native renderer is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.original_marker_restoration_image import restored as marker_only
from ios.adapters.avatar_restoration_image import restored
from ios.self_tests import test_ios_avatar_restoration_image as fixture
from ios.self_tests.retained_host_roots import retain_owned_root


class AvatarRGBAEqualityTests(unittest.TestCase):
    def case(self,*,transparent=False):
        original=fixture.fixture.RawFramesTests.setUp
        def producer(raw):
            original(raw)
            if transparent:
                # Before the first actual capture: never edit a retained PNG.
                raw.background.putpixel((0,0),(75,85,100,0));raw.render()
        case=fixture.AvatarRestorationImageTests();self.addCleanup(case.doCleanups)
        with patch.object(fixture.fixture.RawFramesTests,'setUp',producer):case.setUp()
        actual=case.raw.fixture;retain_owned_root(actual.temp,expected_root=actual.root)
        print('retained Avatar RGBA original root',actual.root,flush=True);return case

    @staticmethod
    def queries(case):return sum(len(gpu.commands) for gpu in case.raw.gpus.values())

    def test_equal_transparent_rgba_keeps_full_original_proof_without_new_native_queries(self):
        case=self.case(transparent=True);reference=case.finish();before=self.queries(case)
        value=restored(case.owner,case.before,reference,case.admission,case.marker,after_native=case.barrier)
        self.assertEqual((640*400,0),(value['pixels'],value['changedPixels']))
        self.assertEqual(before,self.queries(case))

    def test_each_rgba_channel_outside_marker_including_hidden_rgb_is_strict(self):
        for channel in range(4):
            case=self.case(transparent=True);pixel=[75,85,100,0];pixel[channel]+=1
            case.raw.background.putpixel((0,0),tuple(pixel));reference=case.finish();before=self.queries(case)
            self.assertEqual(0,marker_only(case.owner,case.before,reference,case.admission,case.marker,
                after_native=case.barrier)['changedPixels'])
            with self.subTest(channel=channel),self.assertRaises(NativeUIError):
                restored(case.owner,case.before,reference,case.admission,case.marker,after_native=case.barrier)
            self.assertEqual(before,self.queries(case))

    def test_different_original_png_container_with_equal_decoded_rgba_still_qualifies(self):
        case=self.case();render=case.raw.render
        def fresh_container():
            render();image=Image.open(BytesIO(case.raw.fixture.raw)).convert('RGBA')
            stream=BytesIO();image.save(stream,format='PNG',compress_level=0);case.raw.fixture.raw=stream.getvalue()
        with patch.object(case.raw,'render',side_effect=fresh_container):reference=case.finish()
        _first,old=case.owner.frame(case.before);_last,new=case.owner.frame(reference)
        self.assertNotEqual(old,new)
        self.assertEqual(Image.open(BytesIO(old)).tobytes(),Image.open(BytesIO(new)).tobytes())
        value=restored(case.owner,case.before,reference,case.admission,case.marker,after_native=case.barrier)
        self.assertEqual(0,value['changedPixels'])

    def test_actual_original_reader_still_refuses_nonrgba_format_or_extent(self):
        for fault in ('RGB','L','P','JPEG','extent'):
            case=self.case();case.raw.marker(False);actual=case.raw.fixture
            image=Image.open(BytesIO(actual.raw)).convert('RGBA');format='PNG'
            if fault=='extent':image=image.resize((639,400))
            elif fault=='JPEG':image=image.convert('RGB');format='JPEG'
            else:image=image.convert(fault)
            stream=BytesIO();image.save(stream,format=format);actual.raw=stream.getvalue()
            actual.scope.state.update(phase='released',pending=None);case.barrier=actual.native(None).read(0)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):case.owner.capture('cleanup')


if __name__=='__main__':unittest.main()
