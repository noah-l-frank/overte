"""Actual normal marker, key/pointer journals and weak roots; native modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.emote_rooted_quiet import refresh,extend
from ios.self_tests.test_ios_emote_rooted_marker_scope import EmoteRootedMarkerTests
from ios.self_tests.emote_pointer_fixture import PointerDomain
from ios.self_tests.emote_keys_fixture import KeyDomain
from ios.self_tests.world_web_ui_roots_fixture import Root


class EmoteRootedQuietTests(unittest.TestCase):
    def setUp(self):
        self.f=EmoteRootedMarkerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.scope,self.domain=self.f.scope,self.f.domain
        self.pointer_model=PointerDomain(self,self.scope,self.domain)
        self.pointers=self.pointer_model.owner();self.keys_model=KeyDomain(self.scope,self.domain);self.keys=self.keys_model.owner()
        # These original global input baselines must precede ordinary setup,
        # just as the existing whole owner acquires them before its marker.
        self.pointers.capture();self.keys.capture();self.f.prepare();self.scope.cleanup()

    def refresh(self):return refresh(self.scope,self.pointers,self.keys,clock=self.scope.monotonic,sleep=self.scope.sleep)

    def test_fresh_global_key_pointer_and_native_holder_originals_extend_without_new_ordinary_input(self):
        operations=list(self.scope.state['operations']);actions=list(self.domain.io.actions)
        self.assertTrue(self.refresh());old=list(self.scope.state['quiet']);held=self.scope.held_originals()
        self.domain.sleep(1.);self.assertTrue(extend(self.scope,self.pointers,self.keys))
        self.assertEqual(old,self.scope.state['quiet'][:-1]);self.assertEqual(held,self.scope.held_originals())
        self.assertTrue(self.pointers.closed(self.scope));self.assertTrue(self.keys.closed(self.scope))
        self.assertEqual(operations,self.scope.state['operations']);self.assertEqual(actions,self.domain.io.actions)
        self.assertEqual(held,self.f.archive().held_originals())

    def test_new_detached_root_and_complete_input_cycle_cannot_borrow_the_old_window(self):
        self.refresh();old=list(self.scope.state['quiet']);root=Root('manager')
        self.domain.actual_roots['new-detached']=root;self.domain.roots.observe(root)
        self.pointer_model.boundary.touch('touch-begin');self.pointer_model.boundary.touch('touch-end')
        with self.assertRaises(NativeUIError):extend(self.scope,self.pointers,self.keys)
        self.assertEqual(old,self.scope.state['quiet'])
        with self.assertRaises(NativeUIError):self.scope.held_originals()
        self.assertTrue(self.refresh());self.assertGreater(self.scope.state['quiet'][0],old[-1])
        manager=next(row for row in self.scope.held_originals() if row['original'].get('rootKind')=='manager')
        self.assertEqual(2,len(manager['original']['roots']))
        self.assertTrue(self.pointers.closed(self.scope));self.assertTrue(self.keys.closed(self.scope))

    def test_current_uikit_keyboard_blocks_refresh_and_old_held_projection_until_actual_new_quiet(self):
        self.refresh();old=list(self.scope.state['quiet']);self.keys_model.keyboard=True;self.keys_model.inset=120
        with self.assertRaises(NativeUIError):self.refresh()
        self.assertEqual(old,self.scope.state['quiet'])
        with self.assertRaises(NativeUIError):self.scope.held_originals()
        self.keys_model.keyboard=False;self.keys_model.inset=0
        self.assertTrue(self.refresh());self.assertTrue(self.keys.closed(self.scope))
        self.assertTrue(self.scope.held_originals())

    def test_lost_passive_end_retains_partial_originals_and_cannot_project_old_holds_as_current(self):
        self.refresh();old=list(self.scope.state['quiet']);actions=list(self.domain.io.actions)
        read=self.scope.web.read
        def lost(*_args):raise OSError('Actual passive Web inventory return lost')
        self.scope.web.read=lost
        with self.assertRaises(OSError):extend(self.scope,self.pointers,self.keys)
        self.assertIsNotNone(self.scope.state['pending']);self.assertEqual(old,self.scope.state['quiet'])
        partial=self.scope.state['pending']['partial'];self.assertTrue(partial['terminal'])
        with self.assertRaises(NativeUIError):self.scope.held_originals()
        archived=self.f.archive();self.assertEqual(old,archived.state['quiet'])
        with self.assertRaises(NativeUIError):archived.held_originals()
        self.scope.web.read=read;self.assertTrue(self.refresh())
        self.assertGreater(self.scope.state['quiet'][0],old[-1]);self.assertTrue(self.scope.held_originals())
        self.assertEqual(actions,self.domain.io.actions)

    def test_genuine_other_role_key_owner_is_refused_before_any_source_read(self):
        foreign=KeyDomain(self.scope,self.domain,role='actor');owner=foreign.owner()
        before=dict(self.domain.sequences);revision=len(self.scope.frames);raw=self.scope.store.path.read_bytes()
        with self.assertRaises(NativeUIError):
            refresh(self.scope,self.pointers,owner,clock=self.scope.monotonic,sleep=self.scope.sleep)
        self.assertEqual([],foreign.commands);self.assertEqual(before,self.domain.sequences)
        self.assertEqual(revision,len(self.scope.frames));self.assertEqual(raw,self.scope.store.path.read_bytes())


if __name__=='__main__':unittest.main()
