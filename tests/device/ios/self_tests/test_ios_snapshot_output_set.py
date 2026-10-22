"""Complete ordinary output sets; actual files/weak jobs with modeled native IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_completion as source
from ios.self_tests import snapshot_modes_fixture as fixtures


class SnapshotOutputSets(unittest.TestCase):
    def fixture(self):
        fixture=fixtures.ModesFixture();fixture.setUp();self.addCleanup(fixture.doCleanups);return fixture

    def test_actual_output_manifests_and_ordinary_inputs_join_all_five_cases(self):
        for mode,kind in (('still','png'),('still','jpg'),('animated','png'),('panorama','png'),('cubemap','png')):
            with self.subTest(mode=mode,kind=kind):
                f=self.fixture()
                with f.ctx.lock.held():
                    args=f.prepared_set(mode,kind);result=source.output_set(*args)
                    self.assertEqual(mode,result['mode']);self.assertEqual(f.request,result['captureId'])
                    self.assertEqual({'png','gif'} if mode=='animated' else {kind},{v['format'] for v in result['files']})
                    self.assertTrue(result['sceneFidelityRequired']);self.assertTrue(result['independentWitnessRequired'])
                    if mode=='still':
                        legacy=source.completed(*args[:7],args[7][0],args[8]);self.assertEqual(1,legacy.pop('iosSnapshotCompletedCaptureVersion'))
                        self.assertEqual(result['files'][0],legacy)

    def test_actual_animated_gif_and_still_bytes_decode_but_do_not_prove_visual_motion(self):
        f=self.fixture()
        with f.ctx.lock.held():
            result=source.decoded_output_set(*f.prepared_set('animated'))
            self.assertEqual([2,1],sorted([len(v['decodedFrames']) for v in result['images']],reverse=True))
            self.assertTrue(result['visualMotionRequired']);self.assertEqual(1000,max(v['durationMilliseconds'] for v in result['images']))

    def test_missing_or_duplicate_companion_and_extra_original_output_cannot_be_hidden(self):
        f=self.fixture()
        with f.ctx.lock.held():
            args=f.prepared_set('animated')
            for files in (args[7][:1],[args[7][0],args[7][0]]):
                bad=list(args);bad[7]=files
                with self.assertRaises(NativeUIError):source.output_set(*bad)
        f=self.fixture()
        with f.ctx.lock.held():
            args=list(f.prepared_set(extra=True));args[7]=args[7][:1]
            with self.assertRaises(NativeUIError):source.output_set(*args)

    def test_native_processing_return_and_selected_projection_mode_are_required(self):
        f=self.fixture()
        with f.ctx.lock.held():
            args=f.prepared_set('animated');bad=list(args);bad[5]=deepcopy(args[5])
            row=next(v for v in bad[5]['source']['events'] if v['kind']=='status' and v['detail']['phase']=='processing')
            row['detail']['hasPath']=False
            with self.assertRaises(NativeUIError):source.output_set(*bad)
            bad=list(args);bad[3]=deepcopy(args[3]);bad[3]['source']['workers'][0]['state']['mode']='cubemap'
            with self.assertRaises(NativeUIError):source.output_set(*bad)

    def test_terminal_status_and_actual_file_hash_cannot_substitute_for_gif_duration_or_projection_geometry(self):
        for mode in ('animated','panorama','cubemap'):
            with self.subTest(mode=mode):
                f=self.fixture()
                with f.ctx.lock.held():
                    args=f.prepared_set(mode,gif_frames=1);source.output_set(*args)
                    with self.assertRaises(ValueError):source.decoded_output_set(*args)

    def test_projection_processing_must_remain_the_actual_pathless_native_conversion(self):
        for mode in ('panorama','cubemap'):
            with self.subTest(mode=mode):
                f=self.fixture()
                with f.ctx.lock.held():
                    args=f.prepared_set(mode);bad=list(args);bad[5]=deepcopy(args[5])
                    row=next(v for v in bad[5]['source']['events'] if v['kind']=='status' and v['detail']['phase']=='processing')
                    row['detail']['hasPath']=True
                    with self.assertRaises(NativeUIError):source.output_set(*bad)

    def test_actual_mutated_artifact_is_rejected_even_when_native_completion_and_output_set_match(self):
        f=self.fixture()
        with f.ctx.lock.held():
            args=f.prepared_set('animated');source.output_set(*args);args[7][-1].path().write_bytes(b'GIF89a')
            with self.assertRaises(NativeUIError):source.decoded_output_set(*args)


if __name__=='__main__':unittest.main()
