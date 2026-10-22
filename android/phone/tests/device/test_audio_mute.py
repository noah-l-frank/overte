"""Mandatory normal mute foundation against explicit synthetic native widgets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from test_audio_feature import Target,Clock
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_audio_mute import PhoneAudioMute


class AudioMuteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name);root.chmod(0o700)
        self.target=Target(root,Clock());self.store=PrivateFeatureState(root/'phone-audio-mute.json')
    def flow(self):return PhoneAudioMute(self.target,'target',self.store)

    def test_normal_mute_roundtrip_closes_the_owned_page_and_retires_only_at_real_original_value(self):
        self.flow().act(True);self.assertTrue(self.target.muted);self.assertFalse(self.target.page);self.assertIsNotNone(self.store.read())
        self.flow().act(False);self.assertFalse(self.target.muted);self.assertFalse(self.target.page);self.assertIsNone(self.store.read())
        self.assertEqual(2,self.target.inputs.count('audio.mute'))

    def test_repeated_completed_request_does_not_reopen_or_retoggle(self):
        self.flow().act(True);count=len(self.target.inputs);self.flow().act(True)
        self.assertEqual(count,len(self.target.inputs));self.flow().cleanup();self.assertIsNone(self.store.read())

    def test_lost_mute_return_uses_fresh_original_value_without_redelivering_the_toggle(self):
        original=self.target.activate
        def lost(identifier,**kwargs):
            original(identifier,**kwargs)
            if identifier=='audio.mute':raise NativeUIError('Synthetic lost native return after original widget activation')
        self.target.activate=lost
        with self.assertRaises(NativeUIError):self.flow().act(True)
        self.target.activate=original;self.flow().act(True)
        self.assertEqual(1,self.target.inputs.count('audio.mute'));self.flow().cleanup();self.assertIsNone(self.store.read())

    def test_foreign_audio_page_and_changed_candidate_are_never_adopted(self):
        self.target.page=True
        with self.assertRaises(NativeUIError):self.flow().act(True)
        self.assertEqual([],self.target.inputs);self.assertIsNone(self.store.read())
        self.target.page=False;self.flow().act(True);before=list(self.target.inputs);self.target.binding['artifactSha256']='e'*64
        with self.assertRaises(NativeUIError):self.flow().cleanup()
        self.assertEqual(before,self.target.inputs);self.assertIsNotNone(self.store.read())

    def test_foreign_replacement_page_after_a_completed_request_is_not_closed(self):
        self.flow().act(True);self.target.page=True;before=list(self.target.inputs)
        with self.assertRaises(NativeUIError):self.flow().act(False)
        self.assertEqual(before,self.target.inputs);self.assertTrue(self.target.page)


if __name__=='__main__':unittest.main()
