"""Real paired file census; native roles/windows remain explicit host models.

Only filesystem responsibility, original membership and journal output bounds
are tested here. No fixture role or ACK qualifies native/process retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack,nullcontext
import os
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.world_web_final_archive import file_original
from ios.adapters.world_web_rooted_inventory import WorldWebRootedInventory,inventory,read_current_end
from ios.self_tests import test_ios_world_web_terminal_seal_recovery as storage_fixture


class WorldWebRootedInventoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=storage_fixture.WorldWebTerminalSealRecoveryTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.owner=self.fixture.owner();self.root=self.fixture.f.root
        stack=self.enterContext(ExitStack());flows=[]
        for role in ('primary','actor'):
            sdk=self.root/(role+'-sdk');sdk.mkdir(mode=0o700)
            lock=ScriptSourceLock(sdk/'script-feature-sources.lock');stack.enter_context(lock.held())
            flows.append(SimpleNamespace(run='a'*32,root=self.root,lock=lock,
                store=PrivateFeatureState(sdk/('ios-world-web-'+role+'-feature.json'))))
        flows[0].primary_lock=flows[0].lock;flows[1].primary_lock=flows[0].lock
        self.owner.flow,self.owner.actor=flows

    def store(self,root,name):
        store=PrivateFeatureState(root/name);store.write(dict(ownedByFixture=1),None);return store

    def test_unknown_existing_and_new_carriers_in_either_sdk_or_artifacts_fail_closed(self):
        roots={self.root,self.owner.flow.store.path.parent,self.owner.actor.store.path.parent}
        for root in sorted(roots):
            with self.subTest(root=root):
                barrier=WorldWebRootedInventory(self.owner,set())
                store=self.store(root,'world-web-unowned.json')
                with self.assertRaises(NativeUIError):barrier.guard()
                with self.assertRaises(NativeUIError):WorldWebRootedInventory(self.owner,set())
                self.assertEqual(dict(ownedByFixture=1),store.read());store.discard(store.read())

    def test_recovery_gpu_and_companion_png_names_have_no_suffix_exemption(self):
        names=('worldweb-marker-read-abandoned-unowned.json',
            'graphics-world-frame-primary-0-unowned.json','vulkan-world-unowned.png',
            'wwc-unowned.binary','wwrg-unowned.json','wwsu-unowned.json',
            'phase-retirement-world-web-unowned.json')
        for name in names:
            with self.subTest(name=name):
                store=self.store(self.root,name)
                with self.assertRaises(NativeUIError):WorldWebRootedInventory(self.owner,set())
                store.discard(store.read())

    def test_actual_original_reads_are_required_and_same_inode_rewrite_rejects_reuse(self):
        store=self.store(self.owner.actor.store.path.parent,'ios-world-web-actor-original.json')
        with read_scope(fresh=True) as reads:store.read()
        self.assertEqual({store.path},reads)
        barrier=WorldWebRootedInventory(self.owner,reads)
        before=store.path.stat();raw=store.path.read_bytes();time.sleep(.002)
        store.path.write_bytes(raw.replace(b':1',b':2'));store.path.write_bytes(raw)
        os.utime(store.path,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.assertEqual(before.st_ino,store.path.stat().st_ino)
        self.assertEqual(raw,store.path.read_bytes())
        with self.assertRaises(NativeUIError):barrier.guard()

    def test_exact_typed_terminal_outputs_can_commit_without_exempting_the_namespace(self):
        barrier=WorldWebRootedInventory(self.owner,set());fixture=self.fixture.f
        measured=dict(source='actual storage sentinel');seal=fixture.seal(measured)
        self.owner.commit_seal(fixture.samples,measured,seal,fixture.roles);barrier.guard()
        self.assertEqual(2,len(self.owner.state['records']))
        actual=self.owner.frames.path(self.owner.frames.expand(self.owner.state['records'][-1]))
        unknown=actual.with_name(actual.name+'.unowned')
        self.store(unknown.parent,unknown.name)
        with self.assertRaises(NativeUIError):barrier.guard()

    def test_root_context_changes_and_symlink_carriers_do_not_escape_the_census(self):
        barrier=WorldWebRootedInventory(self.owner,set())
        original=self.owner.actor.store
        self.owner.actor.store=PrivateFeatureState(self.root/'ios-world-web-actor-feature.json')
        with self.assertRaises(NativeUIError):barrier.guard()
        self.owner.actor.store=original
        path=self.root/'world-web-link.json';path.symlink_to(self.owner.store.path)
        with self.assertRaises(NativeUIError):inventory(barrier.roots)

    def test_final_archive_actual_binary_hash_reads_join_membership(self):
        path=self.root/'vulkan-world-original.png';path.write_bytes(b'actual-original-bytes\x00\xff');path.chmod(0o600)
        with read_scope(fresh=True) as reads:result=file_original(path)
        self.assertEqual({path},reads);self.assertEqual(path.stat().st_size,result['bytes'])
        WorldWebRootedInventory(self.owner,reads).guard()

    def test_finish_refuses_existing_unknown_carrier_before_fixture_status_or_any_stop(self):
        # Model the expensive native proof only; the terminal journal, carrier,
        # paired roots, locks and refusing census remain the real implementation.
        fixture=self.fixture.f;seal=fixture.seal({})
        self.owner.commit_seal(fixture.samples,{},seal,fixture.roles)
        self.owner.held=lambda:nullcontext()
        self.owner.roles=lambda *args,**kwargs:(fixture.roles,{})
        self.owner.descriptor=lambda roles:fixture.description
        self.owner.live=lambda *args,**kwargs:{}
        calls=[]
        def forbidden():calls.append('fixture');raise AssertionError('Unknown carrier reached fixture/Stop')
        self.owner.flow.phase=SimpleNamespace(status=forbidden)
        carrier=self.store(self.owner.actor.store.path.parent,'world-web-unowned-before-stop.json')
        before=self.owner.store.read()
        with patch('ios.adapters.world_web_terminal.read_current_end'),self.assertRaises(NativeUIError):
            self.owner.finish(seal)
        self.assertEqual([],calls);self.assertEqual(before,self.owner.store.read())
        self.assertEqual(dict(ownedByFixture=1),carrier.read())


class WorldWebCurrentEndInventoryTests(unittest.TestCase):
    def setUp(self):
        from ios.self_tests.test_ios_world_web_worker_routes import WorldWebWorkerRouteTests
        self.fixture=WorldWebWorkerRouteTests();self.addCleanup(self.fixture.doCleanups)
        self.actor,self.owner=self.fixture.modeled_admitted_roles()
        def forbidden(*args,**kwargs):raise AssertionError('Pure end census reached SDK/native/fixture')
        self.actor.runtime._existing=forbidden
        self.actor.phase.status=self.owner.flow.phase.status=forbidden

    def test_absent_end_owners_need_no_live_transport_and_existing_coordinators_stay_unchanged(self):
        with self.owner.held(),read_scope(fresh=True) as reads:
            before={flow.store.path:flow.previous for flow in (self.owner.flow,self.actor)}
            read_current_end(self.owner,dict(primary={},actor={}))
            self.assertTrue(reads)
            for flow in (self.owner.flow,self.actor):self.assertEqual(before[flow.store.path],flow.store.read())

    def test_sdk_original_without_real_process_scene_chain_is_refused(self):
        with self.owner.held():
            store=self.actor.runtime._world_web_store(self.actor.selector,
                'ios-world-web-actor-'+self.actor.run+'-sdk-final.json')
            value=dict(unqualifiedSDKOwner=True);store.write(value,None)
            with self.assertRaises(NativeUIError):read_current_end(self.owner,dict(primary={},actor={}))
            self.assertEqual(value,store.read())


if __name__=='__main__':unittest.main()
