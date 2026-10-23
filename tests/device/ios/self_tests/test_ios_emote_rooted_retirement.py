"""Actual host rooted cleanup composition with explicit native/Qt/GPU models.

Production module imports are unchanged here; no code or verdict is patched.
Only the host fixture selects the new producer before its first raw original.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_retirement import IOSEmoteRetirement
from ios.adapters.emote_rendered_retirement import IOSEmoteRenderedRetirement
from ios.adapters.emote_keyed_retirement import IOSEmoteKeyedRetirement
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedNativeRetirement,IOSEmoteRootedRenderedRetirement,IOSEmoteRootedKeyedRetirement
from ios.adapters.emote_rooted_quiet import refresh
from ios.self_tests import test_ios_emote_rendered_retirement as fixture
from ios.self_tests.test_ios_emote_rooted_marker_scope import rooted
from ios.self_tests.emote_rooted_marker_fixture import RootedMarkerDomain
from ios.self_tests.emote_keys_fixture import KeyDomain

pointer_domain=fixture.PointerDomain
class RootedRetirementCompositionTests(unittest.TestCase):
    def setUp(self):
        self.key_domains=[]
        def pointer(test,scope,domain):
            result=pointer_domain(test,scope,domain)
            keys=KeyDomain(scope,domain);scope._test_keys=keys.owner();scope._test_keys.capture()
            self.key_domains.append(keys);return result
        def quiet(scope,*,clock,sleep,pointers):
            return refresh(scope,pointers,scope._test_keys,clock=clock,sleep=sleep)
        f=fixture.RenderedRetirementTests();self.f=f;self.addCleanup(f.doCleanups)
        with (patch.object(fixture.journey.scope_fixture.MarkerScopeTests,'owner',rooted),
              patch.object(fixture.journey,'RunningDomain',RootedMarkerDomain),
              patch.object(fixture,'PointerDomain',pointer),patch.object(fixture,'refresh',quiet),
              patch.object(fixture,'IOSEmoteRetirement',IOSEmoteRootedNativeRetirement)):
            f.setUp()
        self.rendered=IOSEmoteRootedRenderedRetirement(PrivateFeatureState(f.root/'rooted-rendered.json'),f.native,f.frames)
        self.rendered_ref=self.rendered.retain(dict(nativeReference=f.native_reference,frames=f.frames.store.read(),
            initialReference=f.initial,currentReference=f.current))
        self.keys=f.scope._test_keys;self.keys.capture()
        self.keyed=IOSEmoteRootedKeyedRetirement(PrivateFeatureState(f.root/'rooted-keyed.json'),self.rendered,self.keys)
        self.keyed_ref=self.keyed.retain(dict(renderedReference=self.rendered_ref,keys=self.keys.store.read()))

    def test_actual_cached_scope_native_files_png_pointer_and_keys_reopen_as_explicit_v2_components(self):
        f=self.f;result=self.keyed.derive(self.keyed_ref)
        self.assertTrue({'qt-root','qimage','qsg-root','native-holder'}<={row['kind'] for row in result['held']})
        self.assertEqual(f.scope.held_originals(),result['held'])
        self.assertEqual(2,f.native.previous['iosEmoteRetirementVersion'])
        self.assertEqual(2,self.rendered.previous['iosEmoteRenderedRetirementVersion'])
        self.assertEqual(2,self.keyed.previous['iosEmoteKeyedRetirementVersion'])
        self.assertEqual([],result['public']['artifacts']);self.assertEqual([],result['public']['resources'])
        # The unchanged public DTO is a normal-source component only. Actual
        # held originals remain separately mandatory; no Complete is returned.
        self.assertNotIn('end',result);self.assertNotIn('complete',result)
        history=len(f.domain.history);actions=list(f.domain.io.actions)
        files={p:(p.stat().st_ino,p.read_bytes()) for p in f.root.rglob('*') if p.is_file()}
        rebuilt=IOSEmoteRootedKeyedRetirement(self.keyed.store,self.rendered,self.keys)
        self.assertEqual(result,rebuilt.derive(self.keyed_ref));self.assertEqual(history,len(f.domain.history))
        self.assertEqual(actions,f.domain.io.actions)
        self.assertEqual(files,{p:(p.stat().st_ino,p.read_bytes()) for p in f.root.rglob('*') if p.is_file()})
        for kind,call in [('native',lambda:IOSEmoteRetirement(f.native.store,f.native.root,f.native.binding,f.native.primary_binding,
                f.native.run,f.native.role,f.native.fixture_url,f.native.phase_instance,f.native.lock,f.native.primary_lock,
                f.native.policy,f.native.paths,f.native.guard)),
                ('rendered',lambda:IOSEmoteRenderedRetirement(self.rendered.store,f.native,f.frames)),
                ('keyed',lambda:IOSEmoteKeyedRetirement(self.keyed.store,self.rendered,self.keys))]:
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):call()

    def test_version_two_parent_cannot_relabel_web_only_marker_scope_as_whole_tree_roots(self):
        f=self.f;wrong=deepcopy(f.native.original(f.native_reference))
        wrong['scope']['iosEmoteMarkerScopeVersion']=2
        history=len(f.domain.history);actions=list(f.domain.io.actions)
        with self.assertRaises(NativeUIError):f.native.retain(wrong)
        self.assertIsNotNone(f.native.state['pending'])
        self.assertEqual(history,len(f.domain.history));self.assertEqual(actions,f.domain.io.actions)


if __name__=='__main__':unittest.main()
