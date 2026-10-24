"""Existing readonly scopes: actual Source5/Snapshot2 files, modeled producers.

No Node, physical/native execution, terminal success or new clock envelope is
qualified. These cases exercise the applied existing decoder/identity scopes
and their production readonly terminal connection.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_whole_snapshot as whole
from ios.adapters.world_web_scope_archive import original_round
from ios.adapters.world_web_api_clock import scope as api_scope
from ios.adapters.world_web_terminal import WorldWebTerminal
from ios.self_tests import test_ios_world_web_observer as fixture


class WorldWebReplayScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.WorldWebObserverTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.sdk.use_snapshot=True;self.fixture.sdk.use_whole_snapshot=True

    def owners(self):
        f=self.fixture;source=f.sdk.owner(f.source_store,f.lock);owner=f.observer(source)
        reference,expected=owner.capture();return source,owner,reference,expected

    def test_existing_source_and_observer_round_decode_same_bytes_once_and_copy_outward(self):
        f=self.fixture
        with f.held():
            source,owner,reference,expected=self.owners()
            with patch.object(source,'_decode_frames',wraps=source._decode_frames) as decoded,patch.object(source,'derive_browser',wraps=source.derive_browser) as derived:
                with whole.validation_round(),original_round(),owner.validation_round():
                    returned=owner.validate_original(reference);returned['public']['state']['open']=True
                    self.assertEqual(expected,owner.validate_original(reference))
                    self.assertEqual(1,decoded.call_count);self.assertEqual(1,derived.call_count)
                self.assertEqual(expected,owner.validate_original(reference));self.assertEqual(2,decoded.call_count)

    def test_existing_whole_memo_preserves_original_nonce_and_ends_after_round(self):
        f=self.fixture
        with f.held():
            source,_owner,_reference,_expected=self.owners();frame=source.frame(source.state['records'][-1])
            actual=source.parts.snapshot.packet(frame['nativeSnapshot'])
            query=dict(schemaVersion=1,commandId=actual['commandId'],action=whole.ACTION,runId=actual['runId'],fixtureUrl=actual['fixtureUrl'])
            with patch.object(whole,'_body',wraps=whole._body) as decoded:
                with api_scope(lambda:f.sdk.time):
                    whole.validate(actual,query,source.pid);whole.validate(deepcopy(actual),query,source.pid)
                    self.assertEqual(1,decoded.call_count)
                    changed=deepcopy(actual);changed['commandId']='ios-'+'f'*32
                    with self.assertRaises(NativeUIError):whole.validate(changed,dict(query,commandId=changed['commandId']),source.pid)
                with api_scope(lambda:f.sdk.time):whole.validate(actual,query,source.pid)
                self.assertEqual(3,decoded.call_count) # original, refused foreign nonce, next round

    def test_same_inode_changed_actual_bytes_fail_before_reusing_warm_measurement(self):
        f=self.fixture
        with f.held():
            source,owner,reference,_expected=self.owners();frame=source.frame(source.state['records'][-1])
            path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0];raw=path.read_bytes();native=len(f.sdk.native.commands)
            with self.assertRaises(NativeUIError),whole.validation_round(),owner.validation_round():
                owner.validate_original(reference)
                changed=bytearray(raw);at=changed.index(b'worldWebSnapshotPartFrameVersion');changed[at]=ord('W')
                with path.open('r+b') as stream:stream.write(changed);stream.truncate()
                owner.validate_original(reference)
            self.assertEqual(native,len(f.sdk.native.commands))

    def terminal_seam(self,source,observer,callback):
        # Only the readonly connection is under test. The callback does not
        # qualify a terminal result, role admission, seal or native resource.
        owner=object.__new__(WorldWebTerminal);owner._live=callback
        parts=dict(primary=dict(source=source,retirement=SimpleNamespace(lease=None)),
            actor=dict(source=source,peer=source,retirement=SimpleNamespace(observer=observer)))
        return owner,parts

    def test_actual_terminal_connection_keeps_existing_rounds_until_replay_returns(self):
        f=self.fixture
        with f.held():
            source,observer,reference,expected=self.owners()
            def callback(_samples,_roles,_parts,*,historical):
                self.assertIsNotNone(source._round);self.assertIsNotNone(observer._round)
                self.assertEqual(expected,observer.validate_original(reference))
                return observer.validate_original(reference)
            owner,parts=self.terminal_seam(source,observer,callback)
            with patch.object(source,'_decode_frames',wraps=source._decode_frames) as decoded,patch.object(source,'derive_browser',wraps=source.derive_browser) as derived:
                self.assertEqual(expected,owner.live([],{},parts,historical=True))
                self.assertEqual(1,decoded.call_count);self.assertEqual(1,derived.call_count)
            self.assertIsNone(source._round);self.assertIsNone(observer._round)

    def test_actual_terminal_connection_revalidates_files_on_exit_before_return(self):
        f=self.fixture
        with f.held():
            source,observer,reference,_expected=self.owners();frame=source.frame(source.state['records'][-1])
            path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0];raw=path.read_bytes();native=len(f.sdk.native.commands)
            def callback(_samples,_roles,_parts,*,historical):
                observer.validate_original(reference)
                replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
                return dict(unqualifiedSentinel='must never escape readonly exit')
            owner,parts=self.terminal_seam(source,observer,callback)
            with self.assertRaises(NativeUIError):owner.live([],{},parts,historical=True)
            self.assertIsNone(source._round);self.assertIsNone(observer._round)
            self.assertEqual(native,len(f.sdk.native.commands))

    def test_equal_byte_new_inode_cannot_inherit_a_warm_measurement(self):
        f=self.fixture
        with f.held():
            source,owner,reference,_expected=self.owners();frame=source.frame(source.state['records'][-1])
            path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0];raw=path.read_bytes();native=len(f.sdk.native.commands)
            with self.assertRaises(NativeUIError),whole.validation_round(),owner.validation_round():
                owner.validate_original(reference)
                replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
                owner.validate_original(reference)
            self.assertEqual(native,len(f.sdk.native.commands))


if __name__=='__main__':unittest.main()
