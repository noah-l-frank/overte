"""Real host PNG/file ownership around a modeled existing WDA endpoint."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from adapters.original_screen_images import OriginalScreenImages
from adapters.script_feature.history import pack,unpack
from ios.adapters.tablet_web_images import IOSTabletWebImages
from ios.self_tests.test_ios_graphics_images import SDK
from self_tests.test_completed_frame_lease import BINDING,RUN


class OldGraphicsProfile(OriginalScreenImages):PROFILE='graphics'


class TabletScreenImagesTests(unittest.TestCase):
    def owner(self,root,store,b,cls=IOSTabletWebImages):
        return cls(store,root,BINDING,RUN,'primary',0,b,b.native,lambda:b.valid,epoch_ms=b.host,monotonic=lambda:b.clock)

    def test_native_screen_png_has_real_private_file_and_separate_original_clocks(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);store=PrivateFeatureState(root/'screen.json');b=SDK();owner=self.owner(root,store,b)
            row,raw=owner.capture('e'*32);self.assertEqual(raw,b.raw);self.assertTrue(row['name'].startswith('tablet-web-'))
            self.assertEqual(86400000,row['capture']['nativeBeforeMs']-row['capture']['hostBeginEpochMs'])
            self.assertEqual([('GET','/session/owned-session/screenshot')],b.calls)
            self.assertNotIn('capturedEpochMs',row['capture']);self.assertNotIn('frameId',row['capture'])
            self.assertEqual(1,store.read()['tabletWebScreenImagesVersion']);self.assertNotIn('graphicsScreenImagesVersion',store.read())
            self.assertEqual(raw,self.owner(root,store,b).archive(row['nonce']))
            self.assertTrue(self.owner(root,store,b).cleanup());self.assertFalse((root/row['name']).exists())
            self.assertTrue(self.owner(root,store,b).cleanup());self.assertEqual(1,len(b.calls))

    def test_independently_authored_original_graphics_v1_bytes_and_filename_remain_readable(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);store=PrivateFeatureState(root/'old.json');b=SDK();nonce='c'*32;name='graphics-'+RUN+'-primary-0-'+nonce+'.png'
            # Literal old envelope/filename, not produced by the new writer.
            file=root/name;fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(b.raw)
            info=file.lstat();capture=dict(screenCaptureVersion=1,requestId='ios-'+nonce,source='native-screen',transport='webdriveragent-original-png',
                sessionId=BINDING['sessionId'],processId=int(BINDING['processIdentity']),nativeBeforeMs=b.native(),nativeAfterMs=b.native(),
                hostBeginEpochMs=b.host(),hostEndEpochMs=b.host(),hostBeginMonotonic=0.,hostEndMonotonic=0.,bytes=len(b.raw),sha256=hashlib.sha256(b.raw).hexdigest(),extent=[320,200])
            row=dict(nonce=nonce,name=name,ticket='d'*32,phase='saved',file=dict(device=info.st_dev,inode=info.st_ino),capture=capture)
            original=dict(graphicsScreenImagesVersion=1,binding=deepcopy(BINDING),runId=RUN,role='primary',stage=0,root=str(root),transcript=pack([row]))
            store.write(original,None);before=store.path.read_bytes();image_before=file.read_bytes()
            self.assertEqual(b.raw,self.owner(root,store,b,OldGraphicsProfile).archive(nonce))
            self.assertEqual(before,store.path.read_bytes());self.assertEqual(image_before,file.read_bytes());self.assertEqual([],b.calls)

    def test_lost_screenshot_never_reissues_and_retains_owned_open_file_until_actual_absence(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);store=PrivateFeatureState(root/'screen.json');b=SDK();b.error=True
            with self.assertRaises(NativeUIError):self.owner(root,store,b).capture('e'*32)
            row=unpack(store.read()['transcript'])[0];self.assertEqual('opened',row['phase']);self.assertTrue((root/row['name']).exists())
            with self.assertRaises(NativeUIError):self.owner(root,store,b).capture('e'*32)
            self.assertEqual(1,len(b.calls));self.assertTrue(self.owner(root,store,b).cleanup());self.assertFalse((root/row['name']).exists())

    def test_other_namespace_and_replaced_inode_are_neither_adopted_nor_deleted(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);store=PrivateFeatureState(root/'screen.json');b=SDK();row,raw=self.owner(root,store,b).capture('e'*32)
            with self.assertRaises(NativeUIError):self.owner(root,store,b,OldGraphicsProfile).cleanup()
            file=root/row['name'];file.rename(root/'kept-original.png');file.write_bytes(raw);file.chmod(0o600)
            with self.assertRaises(NativeUIError):self.owner(root,store,b).archive(row['nonce'])
            with self.assertRaises(NativeUIError):self.owner(root,store,b).cleanup()
            self.assertEqual(raw,file.read_bytes());self.assertEqual('saved',unpack(store.read()['transcript'])[0]['phase'])

    def test_actual_png_membership_is_recorded_only_after_full_original_byte_validation(self):
        with tempfile.TemporaryDirectory() as path:
            root=Path(path);store=PrivateFeatureState(root/'screen.json');b=SDK();row,raw=self.owner(root,store,b).capture('e'*32)
            with scope(fresh=True) as files:
                self.owner(root,store,b).archive(row['nonce']);self.assertIn(root/row['name'],files)
            file=root/row['name'];file.write_bytes(raw+b'x')
            with scope(fresh=True) as files:
                with self.assertRaises(NativeUIError):self.owner(root,store,b).archive(row['nonce'])
                self.assertNotIn(file,files)


if __name__=='__main__':unittest.main()
