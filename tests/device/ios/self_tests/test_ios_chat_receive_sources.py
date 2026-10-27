"""Immutable private receive originals; modeled native producers and clocks.

No build, SDK, product, device or actual network delivery is exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.self_tests.test_ios_chat_receive_runtime import IOSChatReceiveRuntimeTests
from self_tests.test_native_feature_observation import Boundary as ClockBoundary
from self_tests.test_native_chat_observation import SELF


class IOSChatReceiveSourcesTests(unittest.TestCase):
    def setUp(self):
        self.f=IOSChatReceiveRuntimeTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.clocks={}
        for role,pid,instance in (('primary',31,'6'*32),('peer',42,'7'*32)):
            boundary=ClockBoundary()
            boundary.mutate=lambda value,pid=pid,instance=instance:value.update(processId=pid,instance=instance)
            self.clocks[role]=boundary
        self.store=PrivateFeatureState(self.f.paths['peer'].with_name('ios-chat-receive-sources.json'))
        self.parts=self.f.parts();self.parts['primary_capture'].observe();self.source=self.make(self.parts)
    def make(self,parts):
        for role,boundary in self.clocks.items():
            reader=boundary.reader(ios=True);reader.pid=int(parts[role]['binding']['processIdentity'])
            parts[role]['clock_source']=reader
        return IOSChatReceiveSources(parts,self.store,epoch_ms=lambda:5000000.,monotonic=lambda:0.)
    def archive(self):
        return IOSChatReceiveSources.archive(self.store,self.parts['primary']['binding'],self.parts['peer']['binding'],
            self.parts['receiver'].peer.run,self.f.artifacts['primary'],self.f.artifacts['peer'],self.parts['binding'],
            self.f.locks['primary'],self.f.locks['peer'])
    def test_original_pair_native_brackets_reconstruction_and_pure_archive(self):
        first=self.source.capture();self.f.peer.event(sender=SELF);second=self.source.capture()
        packet=self.source.original(second);self.assertEqual(1,len(packet['sample']['peerMessages']))
        self.assertEqual(20000,packet['sample']['peer']['capturedEpochMs'])
        self.assertEqual(5000000.,packet['joins']['peer']['hostBeforeEpochMs'])
        calls=self.f.commands();files=self.f.census()
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No archive writes')):
            archived=self.archive();self.assertEqual(packet,archived.original(second))
        self.assertEqual(calls,self.f.commands());self.assertEqual(files,self.f.census())
        reopened=self.make(self.f.parts());third=reopened.capture()
        self.assertEqual([1,2,3],[row['index'] for row in reopened.state['records']]);self.assertEqual(1,first['index'])
        self.assertGreater(reopened.original(third)['sample']['peer']['sequence'],packet['sample']['peer']['sequence'])
    def test_wal_query_failure_blocks_native_send_and_restores_every_send_hook(self):
        readers=[*self.source.clocks.values(),self.parts['receiver'].primary,self.parts['receiver'].peer.reader]
        sends=[reader.send for reader in readers];reads=[reader.read for reader in self.source.clocks.values()]
        commands=self.f.commands();clock_calls=[len(row.commands) for row in self.clocks.values()]
        write=self.store.write
        def failed(value,previous):
            pending=unpack(value['payload'])[0]['pending']
            if pending is not None and pending['queries']:raise OSError('Declared query WAL failure')
            return write(value,previous)
        with patch.object(self.store,'write',side_effect=failed),self.assertRaises(NativeUIError):self.source.capture()
        self.assertEqual(sends,[reader.send for reader in readers]);self.assertEqual(commands,self.f.commands())
        self.assertEqual(reads,[reader.read for reader in self.source.clocks.values()])
        self.assertEqual(clock_calls,[len(row.commands) for row in self.clocks.values()])
    def test_missing_original_and_unowned_prefix_file_prevent_historical_acceptance(self):
        reference=self.source.capture();path=self.source.frames.path(self.source.frames.expand(reference));raw=path.read_bytes()
        path.write_bytes(raw[:-1]+b' ')
        with self.assertRaises((ValueError,RuntimeError)):self.archive()
        path.write_bytes(raw)
        extra=path.with_name('ios-chat-receive-foreign.json');extra.write_text('{}');extra.chmod(0o600)
        with self.assertRaises(NativeUIError):self.archive()
    def test_receiver_rewrite_and_changed_current_candidate_never_yield_an_original(self):
        self.source.capture();self.f.peer.event(sender=SELF);self.source.capture();self.f.peer.events[0]['localOnly']=True
        count=len(self.source.state['records'])
        with self.assertRaises(NativeUIError):self.source.capture()
        self.assertEqual(count,len(self.source.state['records']))
        self.f.peer.events[0]['localOnly']=False;self.f.f.fixture.process['pid']=43
        commands=self.f.commands()
        with self.assertRaises((ValueError,RuntimeError)):self.source.capture()
        self.assertEqual(commands,self.f.commands())
    def test_saved_original_cas_return_loss_restores_exact_cursor_and_adopts_without_queries(self):
        self.source.capture();write=self.store.write
        def lost(value,previous):
            result=write(value,previous);pending=unpack(value['payload'])[0]['pending']
            if pending is not None and pending['wire'] is not None and pending['wire']['phase']=='saved':
                raise OSError('Declared lost saved-original CAS return')
            return result
        with patch.object(self.store,'write',side_effect=lost),self.assertRaises(OSError):self.source.capture()
        with self.assertRaises(NativeUIError):self.archive()
        files=self.f.census();calls=self.f.commands();clock_calls=[len(row.commands) for row in self.clocks.values()]
        reopened=self.make(self.f.parts());self.assertEqual(files,self.f.census());reopened.recover()
        self.assertEqual(2,len(reopened.state['records']));self.assertIsNone(reopened.state['pending'])
        self.assertEqual(calls,self.f.commands());self.assertEqual(clock_calls,[len(row.commands) for row in self.clocks.values()])
        last=reopened.original(reopened.state['records'][-1])
        for role,clock in reopened.clocks.items():self.assertEqual(last['joins'][role]['nativeAfter']['sequence'],clock.sequence)
        self.assertEqual(3,reopened.capture()['index'])
    def test_interrupted_native_start_floors_and_unknown_query_survive_without_retiming(self):
        self.source.capture();reader=self.parts['receiver'].primary;send=reader.send
        reader.clock_ms=lambda:self.source.clocks['primary'].read(self.source.clocks['primary'].sequence)['capturedEpochMs']
        def lost(command):send(command);raise OSError('Declared lost read-only primary return')
        with patch.object(reader,'send',side_effect=lost),self.assertRaises(NativeUIError):self.source.capture()
        pending=deepcopy(unpack(self.store.read()['payload'])[0]['pending']);self.assertIsNone(pending['wire'])
        self.assertTrue(any(row['command']['action']=='feature-chat-observe' for row in pending['queries']))
        reopened=self.make(self.f.parts())
        for role,clock in reopened.clocks.items():self.assertEqual(pending['partial']['clockReads'][role][-1]['sequence'],clock.sequence)
        self.assertGreater(reopened.clocks['primary'].sequence,pending['partial']['primaryStart']['nativeBefore']['sequence'])
        reopened.capture();self.assertEqual(pending,reopened.state['interrupted'][0])
        archived=self.archive();self.assertEqual(pending,archived.state['interrupted'][0])
    def test_foreign_interrupted_clock_identity_or_pid_refuses_before_new_native_queries(self):
        self.source.capture()
        with patch.object(self.parts['receiver'],'sample',side_effect=NativeUIError('Declared unavailable receive')),self.assertRaises(NativeUIError):
            self.source.capture()
        saved=self.store.read();calls=self.f.commands();clock_calls=[len(row.commands) for row in self.clocks.values()]
        for change in (dict(instance='f'*32),dict(processId=999)):
            value=deepcopy(saved);rows=unpack(value['payload']);rows[0]['pending']['partial']['primaryStart']['nativeBefore'].update(change)
            value['payload']=pack(rows);self.store.write(value,self.store.read())
            with self.subTest(change=change),self.assertRaises(NativeUIError):self.make(self.f.parts())
            self.assertEqual(calls,self.f.commands());self.assertEqual(clock_calls,[len(row.commands) for row in self.clocks.values()])
        self.store.write(saved,self.store.read())
    def test_each_nested_native_clock_read_is_retained_in_exact_query_order(self):
        for role,reader in (('primary',self.parts['receiver'].primary),('peer',self.parts['receiver'].peer.reader)):
            clock=self.source.clocks[role];reader.clock_ms=lambda clock=clock:clock.read(clock.sequence)['capturedEpochMs']
        frame=self.source.original(self.source.capture())
        self.assertEqual(3,len(frame['clockReads']['primary']));self.assertEqual(4,len(frame['clockReads']['peer']))
        for role,rows in frame['clockReads'].items():
            ids=[row['command']['commandId'] for row in frame['queries'] if row['role']==role and row['command']['action']=='feature-native-observe']
            self.assertEqual(ids,[row['requestId'] for row in rows])
        modified=deepcopy(frame);modified['clockReads']['peer'].pop(1)
        with self.assertRaises(NativeUIError):self.source.frame(modified)


if __name__=='__main__':unittest.main()
