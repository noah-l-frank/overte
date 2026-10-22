"""Marker fixture storage/bytes only; no native file or Script execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
from pathlib import Path
import tempfile
import unittest
from adapters.native_script_files import NAMES
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_marker_files import originals,OwnedEmoteMarkerFiles
from ios.self_tests.test_ios_emote_sources import BINDING,RUN

URL='http://127.0.0.1:12345/feature-fixture/v1/runs/'+RUN+'/'


class NativeBoundary:
    def __init__(self):self.calls=[];self.files=None;self.fail=False
    def request(self,operation,run,owner,files=None):
        self.calls.append((operation,run,owner))
        if operation=='stage':
            if self.fail:raise NativeUIError('Synthetic lost stage receipt')
            self.files=deepcopy(files);return dict(performed=True)
        if operation=='release':self.files=None;return dict(performed=True)
        if operation=='locate':return dict(locationVersion=1,exists=self.files is not None,directory='file:///private/feature-script-'+run)
        if self.files is None:return dict(exists=False,files=[])
        return dict(exists=True,directory='file:///private/feature-script-'+run,
            files=[dict(name=name,exists=True,base64=base64.b64encode(raw).decode()) for name,raw in self.files.items()])


class MarkerFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.native=NativeBoundary();self.store=PrivateFeatureState(self.root/'ios-emote-marker-files.json')
    def tearDown(self):self.temp.cleanup()
    def files(self):return OwnedEmoteMarkerFiles(self.native,self.store,BINDING)
    def test_marker_bundle_only_creates_and_deletes_one_local_web_marker(self):
        values=originals(RUN,URL,'a'*32,'b'*32);self.assertEqual(set(NAMES),set(values))
        code=values['script-bundle/main.js'].decode()
        self.assertIn('Entities.addEntity',code);self.assertIn('Entities.deleteEntity(marker)',code)
        self.assertIn('graphics-marker.v1.html',code);self.assertIn('"local"',code)
        for forbidden in ('overrideAnimation','restoreAnimation','MyAvatar.position =','MyAvatar.orientation =',
                          'Window.location','loadScene','Script.setInterval','Test.'):
            self.assertNotIn(forbidden,code)
    def test_original_file_bytes_and_origin_are_retained_across_reconstruction(self):
        owner=self.files().reserve_marker(RUN,URL,'a'*32);files=self.files()
        self.assertEqual(owner,files.owned());directory=files.stage_reserved()
        self.assertEqual('file:///private/feature-script-'+RUN,directory);self.assertEqual(directory,self.files().verify())
        self.assertEqual(owner['hashes'],self.files().owned()['hashes'])
    def test_changed_original_file_fails_independent_readback(self):
        files=self.files();files.reserve_marker(RUN,URL,'a'*32);files.stage_reserved()
        self.native.files['script.js']+=b'\nMyAvatar.restoreAnimation();'
        with self.assertRaises(NativeUIError):self.files().verify()
    def test_retirement_observes_original_file_absence_and_keeps_other_paths_unaddressed(self):
        files=self.files();files.reserve_marker(RUN,URL,'a'*32);files.stage_reserved();self.assertEqual({'performed':True},files.release())
        self.assertIsNone(self.store.read());self.assertIsNone(self.native.files)
        self.assertEqual(['release','observe'],[call[0] for call in self.native.calls[-2:]])
    def test_wrong_run_origin_or_implicit_default_source_is_refused(self):
        with self.assertRaises(NativeUIError):self.files().reserve(RUN)
        with self.assertRaises(ValueError):self.files().reserve_marker(RUN,URL.replace(RUN,'d'*32),'a'*32)
        self.assertEqual([],self.native.calls)

if __name__=='__main__':unittest.main()
