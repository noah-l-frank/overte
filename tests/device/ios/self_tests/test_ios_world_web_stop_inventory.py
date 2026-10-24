"""Actual Source append/filesystem bridge; process/scene are explicit models.

The real closed census, Source4 decoder, original carrier writes and signatures
run here. No normal Stop, installed source or process retirement is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import time
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import same
from ios.adapters.world_web_process_end import WorldWebProcessEnd
from ios.adapters.world_web_rooted_inventory import WorldWebRootedInventory
from ios.adapters.world_web_stop_inventory import WorldWebStopInventory
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.self_tests import test_ios_world_web_rooted_inventory as census_fixture
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebStopInventoryTests(unittest.TestCase):
    def setUp(self):
        self.f=census_fixture.WorldWebRootedInventoryTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.owner=self.f.owner;f=self.f.fixture.f;measured={};seal=f.seal(measured)
        self.owner.commit_seal(f.samples,measured,seal,f.roles)
        self.owner.state['phase']='ending';self.owner.save()
        self.sdk=SDK();self.sdk.use_snapshot=True;self.sdk.stimulus=dict(verb='cleanup',inputs={})
        store=PrivateFeatureState(self.owner.flow.store.path.with_name('ios-world-web-primary-sources.json'))
        self.source=self.sdk.owner(store,self.owner.flow.lock);self.source.capture('cleanup-original')
        with read_scope(fresh=True) as reads:
            self.source.decode(self.source.previous);self.source.store.read()
        self.census=WorldWebRootedInventory(self.owner,reads)
        self.scene=dict(explicitSceneModel=True)
        process=object.__new__(WorldWebProcessEnd);self.process=process
        process.flow=self.owner.flow;process.role='primary';process.run=self.sdk.run;process.binding=deepcopy(self.sdk.binding)
        process.store=PrivateFeatureState(store.path.with_name('ios-world-web-primary-'+process.run+'-process-final.json'))
        process.state=dict(phase='fencing',fence=None,processSha256=None,sceneSha256=digest(self.scene),
            source=dict(explicitInstalledSourceModel=True),bundleId='modeled.bundle',peer=None)
        process.previous=process.envelope(process.state);process.store.write(process.previous,None)
        # This is an explicit process-owner seam. Only storage continuity is
        # exercised; the production Stop path also runs the real owner decoder.
        def bound():
            need(same(process.store.read(),process.previous) and same(process.previous,process.envelope(process.state)))
        process.bound=bound
        self.parts=dict(source=self.source,peer=None,retirement=object())

    def bridge(self):
        with patch('ios.adapters.world_web_fence.original',return_value=self.scene):
            return WorldWebStopInventory(self.census,self.process,self.parts)

    def append(self,bridge,*,unknown=False,missing_reads=False):
        if unknown:self.f.store(self.owner.actor.store.path.parent,'world-web-gap-before-append.json')
        self.sdk.fixture_active=False;self.sdk.retired_epoch=self.sdk.phase_epoch()
        with self.source.input_round(PrivateFeatureState(self.source.store.path.with_name('ios-world-web-inputs.json'))):
            with read_scope(fresh=True) as reads:
                reference=self.source.capture('final-fence',retired=True)
                fresh=dict(primary=reference,own=None,explicitFenceModel=True)
                bridge.freeze(fresh,set() if missing_reads else reads)
        self.process.state.update(phase='stop-issued',fence=fresh)
        value=self.process.envelope(self.process.state);self.process.store.write(value,self.process.previous);self.process.previous=deepcopy(value)
        return reference

    def test_gap_before_append_snapshot_is_rejected_before_any_stop_authority(self):
        bridge=self.bridge()
        with self.assertRaises(NativeUIError):self.append(bridge,unknown=True)
        self.assertIsNone(bridge.expected);self.assertEqual('fencing',self.process.state['phase'])

    def test_unknown_between_initial_census_and_process_prepare_is_not_admitted(self):
        self.f.store(self.owner.actor.store.path.parent,'world-web-gap-before-process.json')
        with self.assertRaises(NativeUIError):self.bridge()
        self.assertEqual('fencing',self.process.state['phase'])

    def test_exact_successfully_decoded_append_is_pinned_through_issued_stop_intent(self):
        bridge=self.bridge();old=deepcopy(self.source.state['records'])
        reference=self.append(bridge);self.assertTrue(bridge.guard())
        self.assertEqual(old,self.source.state['records'][:-1]);self.assertEqual(reference,self.source.state['records'][-1])
        self.assertEqual(bridge.expected,self.process.store.read())
        for path in self.source.original_pins(self.source.previous):
            self.assertEqual(EmoteOriginalLease.signature(path.lstat()),bridge.pins[path])

    def test_read_membership_cannot_be_replaced_by_guessed_new_carrier_names(self):
        bridge=self.bridge()
        with self.assertRaises(NativeUIError):self.append(bridge,missing_reads=True)
        self.assertIsNone(bridge.expected);self.assertEqual('fencing',self.process.state['phase'])

    def test_unknown_after_append_freeze_is_rejected_by_the_last_guard(self):
        bridge=self.bridge();self.append(bridge)
        self.f.store(self.owner.actor.store.path.parent,'world-web-gap-before-transport.json')
        with self.assertRaises(NativeUIError):bridge.guard()

    def test_same_inode_rewrite_of_the_new_head_cannot_inherit_the_frozen_signature(self):
        bridge=self.bridge();self.append(bridge);path=self.source.store.path
        before=path.stat();raw=path.read_bytes();time.sleep(.002)
        path.write_bytes(raw);os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.assertEqual(raw,path.read_bytes());self.assertEqual(before.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):bridge.guard()


if __name__=='__main__':unittest.main()
