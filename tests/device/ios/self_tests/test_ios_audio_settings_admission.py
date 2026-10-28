"""Real private settings/WAL/input codecs; Audio/Qt producers remain models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.audio_settings_owner import AudioSettingsOwner
from ios.adapters.audio_settings_source import selected
from ios.self_tests.audio_settings_fixture import Fixture


class AudioSettingsAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='audio-settings-admission-originals-'));self.root.chmod(0o700)
        print('Retained settings admission root: '+str(self.root),flush=True)
        self.f=Fixture(self.root);self.addCleanup(self.f.close)

    def rebuild(self):
        f=self.f;owner=AudioSettingsOwner(f.owner.store,f.sources,f.domain.io(),sleep=f.domain.sleep)
        f.domain.owner=owner;f.owner=owner;return owner

    def clicks(self):return [row for row in self.f.domain.actions if row in ('audio.mute','audio.live-echo')]

    def test_other_value_changed_during_visible_refuses_before_click_and_keeps_original_admission_on_reopen(self):
        f=self.f;f.owner.baseline();f.domain.echo=True;visible=f.owner.ui.visible;admission=[]
        def drift(identifier):
            admission.append(deepcopy(f.owner.state['pending']['admittedBefore']))
            f.domain.muted=True  # Independent producer change during visible preparation.
            # The real ordinary lookup now returns its actual CURRENT token.
            # A stale-token failure must not mask the typed admission check.
            return visible(identifier)
        with patch.object(f.owner.ui,'visible',side_effect=drift),self.assertRaises(NativeUIError):f.owner.restore()
        self.assertEqual([],self.clicks());self.assertEqual(1,len(admission))
        pending=deepcopy(f.owner.state['pending']);self.assertEqual(admission[0],pending['admittedBefore'])
        self.assertEqual(pending['admittedBefore'],pending['before']);self.assertIsNone(pending['input'])
        self.assertFalse(pending['returned']);self.assertEqual(dict(muted=False,localEcho=True),selected(f.owner.packet(pending['admittedBefore'])))
        owner=self.rebuild();self.assertEqual(pending,owner.state['pending'])
        with self.assertRaises(NativeUIError):owner.restore()
        with self.assertRaises(NativeUIError):owner.resolve()
        self.assertEqual([],self.clicks());self.assertEqual(pending,owner.state['pending'])

    def test_other_value_changed_after_actual_scroll_refuses_before_mute_and_retains_navigation(self):
        f=self.f;f.owner.baseline();f.domain.muted=True;scroll=f.domain.scroll;admission=[]
        def drift(identifier,direction,*,token):
            scroll(identifier,direction,token=token)
            admission.append(deepcopy(f.owner.state['pending']['admittedBefore']))
            f.domain.echo=True  # Independent producer change after a real normal scroll.
        with patch.object(f.domain,'scroll',side_effect=drift),self.assertRaises(NativeUIError):f.owner.restore()
        self.assertEqual(['scroll-up'],f.domain.actions);self.assertEqual([],self.clicks())
        pending=deepcopy(f.owner.state['pending']);self.assertEqual([pending['admittedBefore']],admission)
        self.assertIsNone(pending['input']);self.assertFalse(pending['returned']);self.assertEqual(1,len(pending['navigation']))
        nav=pending['navigation'][0];self.assertEqual(('scroll-up','audio.scrollbar'),(nav['verb'],nav['identifier']))
        self.assertEqual(dict(muted=True,localEcho=False),selected(f.owner.packet(pending['admittedBefore'])))
        self.assertEqual(pending,self.rebuild().state['pending']);self.assertEqual([],self.clicks())

    def test_legitimate_lost_return_reopens_then_resolves_from_new_original_without_another_click(self):
        f=self.f;f.owner.baseline();f.domain.echo=True;f.domain.loss=True
        with self.assertRaises(NativeUIError):f.owner.restore()
        pending=deepcopy(f.owner.state['pending']);self.assertIsNotNone(pending['input']);self.assertFalse(pending['returned'])
        self.assertEqual(['audio.live-echo'],self.clicks());f.domain.loss=False
        owner=self.rebuild();self.assertEqual(pending,owner.state['pending'])
        before_queries=len(f.domain.queries);owner.resolve();result=owner.restore()
        self.assertGreater(len(f.domain.queries),before_queries);self.assertEqual(['audio.live-echo'],self.clicks())
        completed=owner.state['operations'][0];self.assertEqual(pending['admittedBefore'],completed['admittedBefore'])
        self.assertEqual(pending['before'],completed['before']);self.assertFalse(completed['returned'])
        self.assertIsNone(owner.state['pending']);self.assertTrue(result['observedSelectedMuteEchoValuesRestored'])
        for key in ('wholeSettingsRestorationAvailable','independentAcousticsAvailable','processSdkRetirementAvailable'):
            self.assertFalse(result[key])

    def test_wal_cannot_rebase_admission_to_the_actual_after_effect_original(self):
        f=self.f;f.owner.baseline();f.domain.echo=True;f.domain.loss=True
        with self.assertRaises(NativeUIError):f.owner.restore()
        self.assertEqual(['audio.live-echo'],self.clicks());f.domain.loss=False
        saved=deepcopy(f.owner.previous);pending=deepcopy(f.owner.state['pending'])
        after=f.sources.capture('after-input');self.assertFalse(selected(f.owner.packet(after))['localEcho'])
        forged=deepcopy(saved);forged['state']['pending']['admittedBefore']=after
        with self.assertRaises(NativeUIError):f.owner.decode(forged)
        self.assertEqual(pending,f.owner.state['pending']);self.assertEqual(saved,f.owner.previous)
        self.assertEqual(['audio.live-echo'],self.clicks())


if __name__=='__main__':unittest.main()
