"""Actual Emote JS/source/image pipeline with a new original marker version.

The fixture constructor selects version two before its first marker write.
Native/Qt/Rig/GPU producers remain models; JS, HTTP, source/PNG bytes are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters.emote_held_marker_scope import IOSEmoteHeldMarkerScope
from ios.adapters.emote_held_observation import IOSEmoteHeldObserver
from ios.adapters.emote_marker_files import OwnedEmoteMarkerFiles
from ios.adapters.emote_observation import IOSEmoteObservationDecoder
from ios.adapters.emote_originals import IOSEmoteOriginals
from ios.self_tests import emote_active_observer_fixture as fixtures
from ios.self_tests import test_ios_emote_marker_scope as marker_fixture


class EmoteHeldObservationTests(unittest.TestCase):
    def fixture(self):
        constructor=marker_fixture.MarkerScopeTests.owner
        def current(model,*args,**kwargs):
            old=constructor(model,*args,**kwargs);self.assertIsNone(old.previous)
            scope=object.__new__(IOSEmoteHeldMarkerScope);scope.__dict__.update(old.__dict__)
            scope.files=OwnedEmoteMarkerFiles(None,old.files.store,scope.binding)
            scope.originals=IOSEmoteOriginals(scope.root,scope.binding,scope.run,scope.role,scope.guard,scope.storage_intent,kind='inputs')
            return scope
        with patch.object(marker_fixture.MarkerScopeTests,'owner',current),patch.object(fixtures,'IOSEmoteObserver',IOSEmoteHeldObserver):
            f=fixtures.ActiveObserverFixture(self,defer_setup=True)
        f.scope.prepare();f.domain.paint();f.scope.admit_rendered();return f

    def test_original_scope_two_joins_actual_playback_and_changed_pngs_without_legacy_reinterpretation(self):
        f=self.fixture();first=f.observer.observe(0);self.assertEqual('idle',first['state']['animation'])
        self.assertEqual(2,f.scope.previous['iosEmoteMarkerScopeVersion']);self.assertEqual(1,len(first['artifacts']))
        f.actions.act(f.activate('open'));opened=f.observer.observe(first['sequence']);self.assertTrue(opened['state']['panel'])
        f.actions.act(f.activate('play',name='Waving'));before=f.actions.state['current']['before'];f.native.sleep(.25)
        played=f.observer.observe(opened['sequence'],input_barrier=dict(index=before['revision'],sha256=before['sha256']))
        self.assertEqual('Waving',played['state']['animation']);self.assertTrue(played['state']['override'])
        self.assertGreater(played['state']['poseProgress'],0.);self.assertEqual(1,len(played['artifacts']))
        original=f.observer.original(f.observer.state['records'][-1]);self.assertEqual(played,f.observer.decoder.derive(original)['public'])
        counts={key:len(value.commands) for key,value in f.f.gpus.items()}
        files={path:(path.stat().st_ino,path.read_bytes()) for path in f.root.rglob('*') if path.is_file()}
        # A new actual observer reopens the same originals; no image or native
        # query is issued merely to rebuild its retained public source history.
        old=f.observer
        rebuilt=IOSEmoteHeldObserver(old.store,old.sources,old.binding,old.role,old.root,old.policy,old.phase,old.lock,old.guard,
            samples=old.samples,monotonic=old.monotonic,epoch_ms=old.epoch_ms)
        self.assertEqual(played,rebuilt.decoder.derive(original)['public'])
        legacy=IOSEmoteObservationDecoder(old.sources,old.binding,old.role,old.root,old.policy,old.lock,phase_instance=old.phase.previous['instance'])
        with self.assertRaises(NativeUIError):legacy.derive(original)
        for version in (1,3):
            changed=deepcopy(original);changed['marker']['scope']['iosEmoteMarkerScopeVersion']=version
            with self.subTest(version=version),self.assertRaises(NativeUIError):rebuilt.decoder.derive(changed)
        self.assertEqual(counts,{key:len(value.commands) for key,value in f.f.gpus.items()})
        self.assertEqual(files,{path:(path.stat().st_ino,path.read_bytes()) for path in f.root.rglob('*') if path.is_file()})


if __name__=='__main__':unittest.main()
