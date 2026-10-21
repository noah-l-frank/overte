"""Real private host PNG files and intent records; no native/device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_graphics_images import PhoneGraphicsImages,record
from test_graphics_measurements import Sources,RUN,TICKET

BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='31:14',sessionId='native-session',
    generation=1,targetFingerprint='c'*64)


class GraphicsImageTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-graphics-images-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.store=PrivateFeatureState(self.root/'image-owner.json')
        source=Sources();self.capture,self.raw=source.capture,source.pixels
        self.clock=0.;self.okay=True;self.intents=[];self.fail=None
        self.images=self.factory()

    def intent(self,value):
        old=self.store.read();self.store.write(value,old);self.intents.append(deepcopy(value))
        path=self.root/value['name']
        if value['phase']=='planned':self.assertIsNone(value['file'])
        elif value['phase']=='opened':self.assertEqual(0,path.stat().st_size)
        else:self.assertEqual(self.raw,path.read_bytes())
        if self.fail==value['phase']:raise NativeUIError('Synthetic lost durable callback return')

    def factory(self,*,role='primary',stage=0,binding=None):
        return PhoneGraphicsImages(self.root,binding or BINDING,RUN,role,stage,lambda:self.okay,self.intent,
            monotonic=lambda:self.clock)

    def save(self):return self.images.write(TICKET,self.capture,self.raw)

    def test_original_png_bytes_and_inode_are_preserved_with_durable_three_phase_intent(self):
        value=self.save();path=self.root/value['name']
        self.assertEqual(['planned','opened','saved'],[row['phase'] for row in self.intents])
        self.assertEqual(self.raw,path.read_bytes());self.assertEqual(self.raw,self.images.read(value))
        self.assertEqual(0o600,path.stat().st_mode&0o777);self.assertEqual(path.stat().st_ino,value['file']['inode'])
        self.assertEqual(self.capture,value['capture']);self.assertFalse(self.images.absent(value))
        self.assertEqual(20000,value['capture']['capturedEpochMs'])

    def test_preexisting_foreign_or_matching_png_is_never_overwritten_or_adopted(self):
        name=self.images.KIND+'-'+RUN+'-primary-'+str(self.images.stage)+'-'+self.capture['requestId']+'.png';path=self.root/name
        for raw in (b'foreign replacement',self.raw):
            path.write_bytes(raw);path.chmod(0o600)
            with self.subTest(rawLength=len(raw)),self.assertRaises(FileExistsError):self.save()
            self.assertEqual(raw,path.read_bytes());self.assertEqual('planned',self.store.read()['phase'])
            with self.assertRaises(NativeUIError):self.images.read(self.store.read())
            path.unlink()

    def test_failed_planned_intent_prevents_creation_and_preserves_the_original_scope(self):
        self.fail='planned'
        with self.assertRaises(NativeUIError):self.save()
        value=self.store.read();self.assertEqual('planned',value['phase']);self.assertTrue(self.images.absent(value))
        self.assertEqual([],list(self.root.glob('*.png')))

    def test_failed_opened_intent_retains_the_actual_empty_file_and_cannot_fake_complete_evidence(self):
        self.fail='opened'
        with self.assertRaises(NativeUIError):self.save()
        value=self.store.read();self.assertEqual('opened',value['phase']);self.assertFalse(self.images.absent(value))
        self.assertEqual(0,(self.root/value['name']).stat().st_size)
        with self.assertRaises(NativeUIError):self.images.read(value)

    def test_lost_saved_return_is_recoverable_only_by_verifying_the_original_file(self):
        self.fail='saved'
        with self.assertRaises(NativeUIError):self.save()
        value=self.store.read();self.assertEqual('saved',value['phase'])
        self.assertEqual(self.raw,self.factory().read(value));self.assertEqual(3,len(self.intents))
        self.assertEqual(20000,value['capture']['capturedEpochMs'])

    def test_replaced_or_changed_file_does_not_inherit_the_previous_proof(self):
        value=self.save();path=self.root/value['name'];original=path.read_bytes()
        path.write_bytes(b'changed in place')
        with self.assertRaises(NativeUIError):self.images.read(value)
        path.write_bytes(original)
        replacement=self.root/'different-file.png';replacement.write_bytes(original);replacement.chmod(0o600)
        os.replace(replacement,path)
        with self.assertRaises(NativeUIError):self.images.read(value)
        self.assertEqual(original,path.read_bytes())

    def test_symlink_hardlink_and_exposed_permissions_are_refused(self):
        value=self.save();path=self.root/value['name'];alias=self.root/'alias.png'
        os.link(path,alias)
        with self.assertRaises(NativeUIError):self.images.read(value)
        alias.unlink();path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.images.read(value)
        path.chmod(0o600);path.rename(alias);path.symlink_to(alias)
        with self.assertRaises((OSError,NativeUIError)):self.images.read(value)
        self.assertEqual(self.raw,alias.read_bytes())

    def test_foreign_role_stage_candidate_or_process_cannot_read_this_scope_as_current(self):
        value=self.save()
        for options in (dict(role='actor'),dict(stage=self.images.stage+1),dict(binding=BINDING|dict(processIdentity='32:15')),
                dict(binding=BINDING|dict(artifactSha256='f'*64))):
            with self.subTest(options=options),self.assertRaises(NativeUIError):self.factory(**options).read(value)

    def test_absent_file_is_observed_independently_and_never_returned_as_empty_png_success(self):
        value=self.save();(self.root/value['name']).unlink()
        self.assertTrue(self.images.absent(value))
        with self.assertRaises(OSError):self.images.read(value)

    def test_decode_and_guard_latency_are_inside_the_whole_write_budget(self):
        from overte_phone_graphics_images import original_pixels
        for fault in ('decode','guard'):
            def delayed(*args):
                value=original_pixels(*args)
                if fault=='decode':self.clock+=5.01
                else:self.okay=False
                return value
            with self.subTest(fault=fault),patch('overte_phone_graphics_images.original_pixels',delayed),self.assertRaises(NativeUIError):self.save()
            self.assertIsNone(self.store.read());self.assertEqual([],list(self.root.glob('*.png')))
            self.clock=0.;self.okay=True;self.images=self.factory()

    def test_clock_regression_is_detected_across_write_read_and_callback_boundaries(self):
        previous=self.intent
        def callback(value):
            previous(value)
            if value['phase']=='opened':self.clock=1
            elif value['phase']=='saved':self.clock=.5
        self.images.intent=callback
        with self.assertRaises(NativeUIError):self.save()
        self.assertEqual('saved',self.store.read()['phase'])
        self.assertEqual(self.raw,(self.root/self.store.read()['name']).read_bytes())

    def test_historical_validation_returns_old_bytes_without_sdk_repair_or_new_timestamps(self):
        value=self.save();before=deepcopy(value);self.okay=False
        with self.assertRaises(NativeUIError):self.images.read(value)
        self.assertEqual(self.raw,type(self.images).archive(self.root,value))
        self.assertEqual(before,value);self.assertEqual(3,len(self.intents))

    def test_record_schema_refuses_unknown_versions_paths_expected_values_and_false_inode_claims(self):
        value=self.save()
        for change in (dict(graphicsImageVersion=True),dict(name='../foreign.png'),dict(expectedPixels=True),
                dict(stage=True),dict(file=dict(device=1,inode=False)),dict(capture=value['capture']|dict(processId=99))):
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.images.record(value|change)

    def test_original_pixel_mismatch_fails_before_any_intent_or_artifact_is_created(self):
        with self.assertRaises(NativeUIError):self.images.write(TICKET,self.capture,self.raw[:-5])
        self.assertIsNone(self.store.read());self.assertEqual([],list(self.root.glob('*.png')))


if __name__=='__main__':unittest.main()
