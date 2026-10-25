"""Once-only process mechanics with explicit modeled successful-seal admission.

The full held-window decoder is not qualified by this component test. SDK HTTP,
private CAS journals and passive OS-quiet readers execute their real code.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_terminal import AvatarTerminal,AvatarTerminalProcess
from ios.self_tests import test_ios_avatar_abort as abort
from ios.self_tests import test_ios_avatar_whole_cleanup as diagnostic


class AvatarTerminalProcessTests(unittest.TestCase):
    def setUp(self):
        self.f=abort.AvatarAbortTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;flow=f.feature;flow.load();flow.selectors=dict(primary='ios:primary',actor='ios:actor')
        flow.state['bindings']['actor']=deepcopy(abort.BINDING);flow.locks=dict(primary=f.lock,actor=f.lock)
        flow.epoch_ms=lambda:f.os.clock*1000;flow.monotonic=lambda:f.os.clock
        f.runtime.adapter.state_path=lambda _selector:f.root/'session.json'
        self.terminal=object.__new__(AvatarTerminal);self.terminal.flow=flow
        self.terminal.state=dict(seal=dict(explicitModeledSealAdmission=True),description=dict(roles=dict(primary=dict(originalSha256='e'*64))))
        self.terminal.verify_seal=lambda:need(self.terminal.state['seal']==dict(explicitModeledSealAdmission=True))
        def guard():f.lock.assert_held();f.runtime.adapter._candidate_guard();return True
        self.terminal.guard=guard
    def owner(self):return AvatarTerminalProcess(self.terminal,'primary')
    def quiet(self,owner):
        self.assertFalse(owner.process_round());self.f.os.clock+=1.6;self.assertFalse(owner.process_round())
        self.f.os.clock+=1.6;self.assertTrue(owner.process_round())
    @diagnostic.original_error_chain
    def test_sealed_lifetime_ends_only_after_original_os_quiet_and_actual_sdk_404(self):
        with self.f.lock.held():
            self.f.runtime.adapter._operation='feature.avatar-people.terminal'
            owner=self.owner();owner.stop();self.quiet(owner);self.assertTrue(owner.delete())
            self.assertEqual('feature.avatar-people.terminal',self.f.runtime.adapter._operation)
            actual=owner.role_end('f'*64);self.assertEqual('e'*64,actual['heldOriginalSha256'])
            self.assertGreaterEqual(actual['osAbsence']['osBeforeLastEpochMs']-actual['osAbsence']['osAfterFirstEpochMs'],3000)
            self.assertEqual(1,self.f.stop_count);self.assertEqual(1,self.f.calls.count('DELETE'))
            rebuilt=self.owner();self.assertEqual(actual,rebuilt.role_end('f'*64))
    def test_unknown_stop_or_delete_return_retains_original_send_without_replay(self):
        with self.f.lock.held():
            owner=self.owner();self.f.stop_lost=True
            with self.assertRaises(OSError):owner.stop()
            owner=self.owner();self.quiet(owner);self.f.delete_lost=True
            with self.assertRaises(Exception):owner.delete()
            rebuilt=self.owner();self.assertEqual('delete-issued',rebuilt.state['phase']);self.assertTrue(rebuilt.delete())
            self.assertEqual(1,self.f.stop_count);self.assertEqual(1,self.f.calls.count('DELETE'))
    def test_actual_terminal_enclosure_is_restored_after_stop_and_lost_return(self):
        with self.f.lock.held():
            owner=self.owner();base=self.f.runtime.adapter;outer='feature.avatar-people.terminal';base._operation=outer
            invoke=base.invoke
            def actual(selector,operation,values):
                self.assertIsNone(base._operation);self.assertEqual('stop-issued',owner.state['phase'])
                self.assertEqual('stop-issued',owner.decode(owner.store.read())['phase'])
                return invoke(selector,operation,values)
            self.f.stop_lost=True
            with patch.object(base,'invoke',side_effect=actual),self.assertRaises(OSError):owner.stop()
            self.assertEqual(outer,base._operation);self.assertFalse(base._session_recreation_forbidden)
            rebuilt=self.owner();self.assertEqual('stop-issued',rebuilt.state['phase'])
            with self.assertRaises(NativeUIError):rebuilt.stop()
            self.assertEqual(1,self.f.stop_count);self.assertEqual(outer,base._operation)
    def test_foreign_enclosure_never_admits_stop_or_changes_its_owner(self):
        with self.f.lock.held():
            owner=self.owner();base=self.f.runtime.adapter;outer='feature.avatar-people.act';base._operation=outer
            before=deepcopy(owner.previous)
            with self.assertRaises(NativeUIError):owner.stop()
            self.assertEqual(before,owner.store.read());self.assertEqual(0,self.f.stop_count)
            self.assertEqual(outer,base._operation);self.assertFalse(base._session_recreation_forbidden)
    def test_historical_end_with_missing_process_original_fails_before_any_source_or_sdk_query(self):
        with self.f.lock.held():
            # Seal admission is explicitly modeled in this component fixture;
            # the missing actual end journal must never recreate an owner.
            self.terminal.state.update(finish=dict(explicitModeledFinish=True),archive=dict(index=1,sha256='f'*64),end={})
            before=list(self.f.calls);queries=list(self.f.os.queries)
            with self.assertRaises(NativeUIError):self.terminal.verify_end()
            self.assertEqual(before,self.f.calls);self.assertEqual(queries,self.f.os.queries)
            self.assertFalse(self.owner_path().exists())

    def test_unowned_archive_path_is_rejected_before_the_path_is_opened(self):
        # Only this inventory-membership counterexample replaces typed graph
        # admission. It can reject the archive; it cannot qualify any end.
        from pathlib import Path
        from ios.adapters import avatar_terminal as module
        f=self.f;flow=f.feature;flow.root=f.root;owner=self.terminal
        actual=PrivateFeatureState(f.root/'actual-decoded-original.json');actual.write(dict(actual=True),None)
        flow.kept=lambda _:dict(iosAvatarTerminalArchiveVersion=1,runId=flow.run,bindings=flow.state['bindings'],sealSha256=digest(owner.state['seal']),
            originalFiles=[dict(path='/unowned-avatar-archive-original',sha256='a'*64,signature=[])],processes={role:{} for role in ('primary','actor')})
        owner.state.update(end={},archive={},sealedRoles={});owner.store=PrivateFeatureState(f.root/'terminal.json')
        owner.roles=lambda _refs:{};owner.original_graph=lambda _processes:actual.read()
        for role in ('primary','actor'):
            PrivateFeatureState(f.root/('ios-avatar-'+role+'-'+flow.run+'-terminal-process.json')).write({},None)
        real_lstat=Path.lstat
        def lstat(path):
            if str(path)=='/unowned-avatar-archive-original':raise AssertionError('Unowned path was opened before membership')
            return real_lstat(path)
        with f.lock.held(),patch.object(module,'AvatarTerminalProcess',side_effect=lambda *_:SimpleNamespace(store=actual,previous={})),patch.object(Path,'lstat',lstat):
            with self.assertRaises(NativeUIError):owner.verify_end()

    def owner_path(self):
        return self.f.root/('ios-avatar-primary-'+self.f.feature.run+'-terminal-process.json')

    def test_ignored_delete_and_changed_candidate_cannot_be_promoted_to_ended(self):
        with self.f.lock.held():
            owner=self.owner();owner.stop();self.quiet(owner);self.f.delete_ignored=True
            self.assertFalse(owner.delete());self.assertEqual('delete-issued',owner.state['phase'])
            with self.assertRaises(NativeUIError):owner.role_end('f'*64)
            self.f.good=False;before=list(self.f.calls)
            with self.assertRaises(NativeUIError):owner.sdk_absence()
            self.assertEqual(before,self.f.calls)


if __name__=='__main__':unittest.main()
