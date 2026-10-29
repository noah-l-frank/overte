"""Actual original pixel/input/Scene joins with a declared callback producer.

Real JS/W3C/HTTP/PNG and immutable typed files are exercised. Native Qt/SDK/GPU
sources remain models; terminal/process/SDK/whole Emote stays unqualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from feature_journeys.retirement_receipts import web_scene
from ios.adapters.emote_callback_observation import RESOURCE
from ios.adapters.emote_callback_scene import (
    IOSEmoteCallbackRenderedRetirement,IOSEmoteCallbackKeyedRetirement,IOSEmoteCallbackSceneRetirement)
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedRenderedRetirement,IOSEmoteRootedKeyedRetirement
from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
from ios.self_tests.emote_callback_scene_fixture import CallbackSceneFixture


class CallbackSceneTests(unittest.TestCase):
    def closed(self,*,play=False):
        f=CallbackSceneFixture(self)
        if play:f.play_cancel()
        f.cleanup();return f

    def queries(self,f):
        t=f.t
        return dict(native=len(f.domain.history),inputs=deepcopy(f.domain.io.actions),
            files=deepcopy(f.file_boundary.commands),keys=deepcopy(f.key_domain.commands),
            gpu=[deepcopy(q) for slot in t.callback_context.worlds.values() for q in slot.commands])

    def files(self,f):
        return {str(p.relative_to(f.root)):(p.stat().st_dev,p.stat().st_ino,p.read_bytes())
            for p in f.root.rglob('*') if p.is_file()}

    def test_actual_play_cancel_png_keyed_scene_retains_roots_and_historical_pending_duty(self):
        f=self.closed(play=True);scene=IOSEmoteCallbackSceneRetirement(f.keyed).read(f.keyed_ref)
        self.assertEqual(4,f.native.previous['iosEmoteRetirementVersion'])
        self.assertEqual(4,f.rendered.previous['iosEmoteRenderedRetirementVersion'])
        self.assertEqual(4,f.keyed.previous['iosEmoteKeyedRetirementVersion'])
        self.assertEqual([],scene['sourcePublic']['resources']);self.assertEqual([],scene['public']['artifacts'])
        self.assertEqual(f.scope.held_originals(),scene['held'])
        self.assertEqual([row['resource'] for row in scene['held']],scene['public']['resources'])
        self.assertTrue({'qt-root','qimage','qsg-root','native-holder'}<={row['kind'] for row in scene['held']})
        self.assertEqual(['native-process-resources'],scene['scene']['remaining'])
        self.assertEqual(scene['scene'],web_scene(scene['scene'],f.scope.run,scene['public']['sequence']))
        self.assertNotIn('end',scene);self.assertNotIn('complete',scene)
        before=self.queries(f)
        self.assertIn(RESOURCE,f.t.observer.decoder.derive(f.first_original)['public']['resources'])
        old=unpack(f.first_original['image']['payload'])[0]
        self.assertEqual(1,old['retirement']['source']['callbacks'])
        self.assertTrue(f.t.callback_context.all_drained());self.assertEqual(before,self.queries(f))

    def test_cold_rendered_keyed_scene_reopens_originals_without_new_input_image_or_wal_write(self):
        f=self.closed();expected=IOSEmoteCallbackSceneRetirement(f.keyed).read(f.keyed_ref)
        before=self.queries(f);files=self.files(f)
        rendered=IOSEmoteCallbackRenderedRetirement(f.rendered.store,f.native,f.frames)
        keyed=IOSEmoteCallbackKeyedRetirement(f.keyed.store,rendered,f.keys)
        self.assertEqual(expected,IOSEmoteCallbackSceneRetirement(keyed).read(f.keyed_ref))
        self.assertEqual(before,self.queries(f));self.assertEqual(files,self.files(f))
        with self.assertRaises(NativeUIError):IOSEmoteCallbackSceneRetirement(keyed).actor_original(f.keyed_ref)
        self.assertEqual(before,self.queries(f))

    def test_literal_rooted2_constructors_cannot_adopt_callback4_owners_or_scene(self):
        f=self.closed();before=self.queries(f);files=self.files(f)
        with self.assertRaises(NativeUIError):IOSEmoteRootedRenderedRetirement(f.rendered.store,f.native,f.frames)
        with self.assertRaises(NativeUIError):IOSEmoteRootedKeyedRetirement(f.keyed.store,f.rendered,f.keys)
        with self.assertRaises(NativeUIError):IOSEmoteRootedSceneRetirement(f.keyed)
        self.assertEqual(before,self.queries(f));self.assertEqual(files,self.files(f))

    def test_current_native_and_rendered_membership_cannot_be_borrowed_from_prior_scene_derivation(self):
        f=self.closed();reader=IOSEmoteCallbackSceneRetirement(f.keyed);reader.read(f.keyed_ref);before=self.queries(f)
        with patch.dict(f.native.state,records=[]),self.assertRaises(NativeUIError):reader.read(f.keyed_ref)
        with patch.dict(f.rendered.state,records=[]),self.assertRaises(NativeUIError):reader.read(f.keyed_ref)
        self.assertEqual(before,self.queries(f))

    def test_changed_actual_initial_png_cannot_be_hidden_by_saved_scene_or_current_cleanup_image(self):
        f=self.closed();reader=IOSEmoteCallbackSceneRetirement(f.keyed);reader.read(f.keyed_ref)
        original=f.frames.original(f.initial);owner=unpack(original['owner'])[0];path=f.root/owner['name']
        # Same inode, actual byte change after an earlier successful decode.
        identity=(path.stat().st_dev,path.stat().st_ino);path.write_bytes(path.read_bytes()+b'foreign')
        self.assertEqual(identity,(path.stat().st_dev,path.stat().st_ino));before=self.queries(f)
        with self.assertRaises(NativeUIError):reader.read(f.keyed_ref)
        self.assertEqual(before,self.queries(f))

    def test_lost_rendered_original_write_return_resolves_exact_pending_without_reacquiring_products(self):
        f=CallbackSceneFixture(self);write=PrivateFeatureState.write;lost=[]
        def written_then_lost(store,value,previous):
            result=write(store,value,previous)
            if store.path.name.startswith('emote-rendered-retirement-') and not lost:
                lost.append(store.path);raise OSError('Declared lost rendered immutable-original write return')
            return result
        with patch.object(PrivateFeatureState,'write',written_then_lost),self.assertRaises(OSError):f.cleanup()
        self.assertEqual(1,len(lost));self.assertIsNotNone(f.rendered.state['pending']);before=self.queries(f)
        owner=IOSEmoteCallbackRenderedRetirement(f.rendered.store,f.native,f.frames)
        reference=owner.resolve();self.assertIn(reference,owner.state['records']);self.assertIsNone(owner.state['pending'])
        self.assertEqual([],owner.derive(reference)['public']['resources']);self.assertEqual(before,self.queries(f))
        self.assertEqual(reference,owner.state['records'][0]);self.assertEqual(1,len(owner.state['records']))

    def test_actual_post_quiet_key_press_cannot_publish_a_new_keyed_scene_until_original_release(self):
        f=self.closed();qt=f.key_domain.qt;qt.finish(qt.enter('key-press'));f.keys.capture()
        self.assertTrue(qt.down);before=self.queries(f)
        with self.assertRaises(NativeUIError):f.keyed.retain(dict(renderedReference=f.rendered_ref,keys=f.keys.store.read()))
        self.assertIsNotNone(f.keyed.state['pending']);self.assertEqual(1,len(f.keyed.state['records']))
        self.assertEqual(before,self.queries(f));self.assertTrue(qt.down)

    def test_later_actual_cleanup_png_cannot_borrow_earlier_native_observation_cut(self):
        f=self.closed();f.domain.sleep(.05);later=f.frames.capture('cleanup');self.assertNotEqual(f.current,later)
        before=self.queries(f)
        with self.assertRaises(NativeUIError):f.rendered.retain(dict(nativeReference=f.native_ref,frames=f.frames.store.read(),
            initialReference=f.initial,currentReference=later))
        self.assertIsNotNone(f.rendered.state['pending']);self.assertEqual(1,len(f.rendered.state['records']))
        self.assertEqual(before,self.queries(f))


if __name__=='__main__':unittest.main()
