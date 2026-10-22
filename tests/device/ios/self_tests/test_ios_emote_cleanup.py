"""Actual token recipes/private input journal at synthetic source/SDK seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_cleanup import IOSEmoteCleanup
from ios.adapters.emote_controls import IOSEmoteIO
from ios.adapters.emote_originals import IOSEmoteOriginals
from ios.adapters.emote_sources import IOSEmoteSources
from ios.self_tests.test_ios_emote_controls import NativeBoundary
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class Source(IOSEmoteSources):
    def __init__(self,root,lock):
        self.lock,self.root,self.run,self.binding,self.role=lock,root,RUN,deepcopy(BINDING),'primary';self.historical=False
        self.store=PrivateFeatureState(root/'ios-emote-primary-sources.json');self.frames=[];self.state=dict(manifests=[])
        self.native=NativeBoundary();self.native.active='Waving';self.native.page=True
        self.readers=dict(ui=IOSEmoteIO(self.native));self.monotonic=lambda:self.native.clock
        self.originals=IOSEmoteOriginals(root,self.binding,RUN,self.role,lambda:True,lambda *_:None)
    def bound(self):self.lock.assert_held()
    def read(self):
        ui=self.readers['ui'].capture();widgets=deepcopy(self.readers['ui'].original_packet)
        widgets.update(emoteControlsVersion=2,emoteInventory=dict(iosEmoteUiInventoryVersion=1,complete=True,roots=[]))
        if self.native.page:widgets['emoteInventory']['roots']=[dict(rootId='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
            qmlSource='qrc:/scripts/system/+android_phoneInterface/PhoneEmote.qml',activeName=self.native.active,
            windowPresent=True,visible=widgets['tabletShown'],enabled=True,attached=True)]
        frame=dict(ui=ui,widgets=widgets,group=dict(native=dict(animation=dict(overrideActive=bool(self.native.active)))),
            phaseAfter=dict(activations=[dict(stimulus=dict(verb='cleanup',inputs={}))]))
        index=len(self.frames)+1;item=self.originals.write(index,frame);self.state['manifests']=self.originals.append(self.state['manifests'],item)
        self.frames.append(deepcopy(frame));return frame


class SDK(NativeUI):
    def __init__(self,source):self.source=source;self.sleep=source.native.sleep;self.calls=[];self.lost=None
    def click(self,locator):
        self.calls.append(locator.value);self.source.native.tablet=locator.value=='OverteTabletOpen'
        if self.lost=='click':raise NativeUIError('Synthetic lost ordinary SDK input')
    def release_actions(self):
        self.calls.append('release')
        if self.lost=='release':raise NativeUIError('Synthetic lost pointer release')


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.source=Source(self.root,self.lock);self.sdk=SDK(self.source);self.store=PrivateFeatureState(self.root/'ios-emote-cleanup-inputs.json')
        self.recovery=patch('ios.adapters.emote_cleanup.IOSEmoteSourceRecovery',return_value=SimpleNamespace(recover=lambda:True,follow=lambda _:True));self.recovery.start()
    def tearDown(self):self.recovery.stop();self.held.__exit__(None,None,None);self.temp.cleanup()
    def owner(self):return IOSEmoteCleanup(self.store,self.source,self.sdk,validate_owned=lambda _:True,
        validate_restored=lambda f:need(not f['group']['native']['animation']['overrideActive']))
    def test_actual_cancel_home_tablet_close_release_and_repeated_retirement(self):
        self.assertEqual({'performed':True},self.owner().close());self.assertFalse(self.source.native.active);self.assertFalse(self.source.native.page)
        self.assertFalse(self.source.native.tablet);self.assertIn('emote.play.Waving',self.source.native.actions)
        self.assertEqual('release',self.sdk.calls[-1]);before=(len(self.source.native.requests),len(self.sdk.calls),len(self.source.frames))
        self.assertEqual({'performed':True},self.owner().close());self.assertEqual(before,(len(self.source.native.requests),len(self.sdk.calls),len(self.source.frames)))
    def test_lost_actual_home_return_resolves_native_sequence_without_a_second_home(self):
        deliver=self.source.native.deliver;lost=[False]
        def delivered(request):
            deliver(request)
            if not self.source.native.page and not lost[0]:lost[0]=True;raise NativeUIError('Synthetic lost actual Home reply')
        with patch.object(self.source.native,'deliver',side_effect=delivered),self.assertRaises(NativeUIError):self.owner().close()
        count=self.source.native.actions.count('tablet.home');self.assertEqual({'performed':True},self.owner().close())
        self.assertEqual(count,self.source.native.actions.count('tablet.home'))
    def test_lost_actual_tablet_open_return_continues_from_observed_state(self):
        self.source.native.tablet=False;self.sdk.lost='click'
        with self.assertRaises(NativeUIError):self.owner().close()
        self.sdk.lost=None;self.assertEqual({'performed':True},self.owner().close())
        self.assertEqual(1,self.sdk.calls.count('OverteTabletOpen'))
    def test_lost_pointer_release_keeps_ownership_and_never_sends_release_again(self):
        self.sdk.lost='release'
        with self.assertRaises(NativeUIError):self.owner().close()
        self.sdk.lost=None
        with self.assertRaises(NativeUIError):self.owner().close()
        self.assertEqual(1,self.sdk.calls.count('release'));self.assertEqual('closing',self.owner().state['phase'])
    def test_unowned_override_is_refused_before_any_cleanup_input(self):
        owner=IOSEmoteCleanup(self.store,self.source,self.sdk,validate_owned=lambda _:False,validate_restored=lambda _:True)
        with self.assertRaises(NativeUIError):owner.close()
        self.assertFalse(self.source.native.requests);self.assertFalse(self.sdk.calls)
    def test_unknown_later_native_command_cannot_settle_a_lost_owned_input(self):
        deliver=self.source.native.deliver
        def lost(request):deliver(request);raise NativeUIError('Synthetic lost delivered command')
        with patch.object(self.source.native,'deliver',side_effect=lost),self.assertRaises(NativeUIError):self.owner().close()
        self.source.native.command_sequence+=1;count=len(self.source.native.requests)
        with self.assertRaises(NativeUIError):self.owner().close()
        self.assertEqual(count,len(self.source.native.requests));self.assertEqual('closing',self.owner().state['phase'])


if __name__=='__main__':unittest.main()
