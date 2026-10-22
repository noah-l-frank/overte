"""Private unchanged native account originals with explicit native producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_account_reads import IOSAvatarAccountReads
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from feature_journeys.witness import Client
from ios.self_tests.test_ios_avatar_input_owner import BINDING
from ios.self_tests.test_ios_avatar_sources import SourcesFixture
from self_tests.test_native_account_observation import account


class AvatarAccountReadsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.artifacts=self.root/'originals';self.artifacts.mkdir(mode=0o700);self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.f=SourcesFixture();self.logged_in=True;self.lost=False;self.commands=[];self.subject_session='actual-connected-session'
        self.store=PrivateFeatureState(self.root/'ios-avatar-actor-primary-account-reads.json')

    def readers(self):
        native=self.f.native();send=native.send
        def product(query):
            pending=unpack(self.store.read()['payload'])[0]['pending']
            owned=[pending['query']]+[item['query'] for item in pending['clocks']]
            self.assertIn(query,owned);self.commands.append(deepcopy(query));send(query)
            current=account();current['observation']['capturedEpochMs']=self.f.now()
            if self.logged_in:
                current['loggedIn']=True;current['principalSha256']=hashlib.sha256(b'e2e-owned-primary').hexdigest()
                current['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
            self.f.core.sample['account']=current
            if self.lost:raise OSError('Synthetic lost passive native query return')
        clock=NativeFeatureObservation(product,native.original,lambda:int(self.f.host()),lambda:True,42,ios=True,
            monotonic=lambda:self.f.clock,sleep=self.f.sleep)
        def native_clock():
            return clock.read(clock.sequence)['capturedEpochMs']
        reader=NativeFeatureObservation(product,native.original,native_clock,lambda:True,42,ios=True,native_clock_bound=True,
            monotonic=lambda:self.f.clock,sleep=self.f.sleep)
        return reader,clock

    def owner(self,*,historical=False):
        reader,clock=(None,None) if historical else self.readers()
        return IOSAvatarAccountReads(self.store,self.artifacts,BINDING,self.f.run,'actor','primary',self.lock,lambda:True,
            reader,historical=historical,clock_source=clock,epoch_ms=self.f.host,monotonic=lambda:self.f.clock)

    def test_native_loggedout_original_remains_available_after_avatar_session_reset(self):
        with self.lock.held():
            owner=self.owner();before=owner.read();self.assertTrue(owner.packet(before)['account']['loggedIn'])
            self.logged_in=False;self.subject_session='00000000-0000-0000-0000-000000000000'
            restored=self.owner();after=restored.read();packet=restored.packet(after)
            self.assertFalse(packet['account']['loggedIn']);self.assertEqual(hashlib.sha256(b'').hexdigest(),packet['account']['principalSha256'])
            commands=deepcopy(self.commands);archive=self.owner(historical=True);self.assertEqual(packet,archive.packet(archive.state['rows'][1]))
            self.assertEqual(commands,self.commands);self.assertEqual(0o600,self.store.path.stat().st_mode&0o777)
            self.assertTrue(all(row['clocks'] for row in archive.state['rows']))

    def test_native_original_change_after_local_derivation_cannot_pass_the_round(self):
        with self.lock.held():
            owner=self.owner();row=owner.read();path=owner.originals.path(row['original']);original=owner.partial_file;changed=[]
            def actual(value):
                result=original(value)
                if not changed:
                    # The real immutable source has already been read for this
                    # round. Mutate that same inode after its partial-file
                    # qualification, before the round's final source read.
                    with path.open('ab') as stream:stream.write(b' ')
                    changed.append(True)
                return result
            before=deepcopy(self.commands)
            with patch.object(owner,'partial_file',side_effect=actual),self.assertRaises(NativeUIError):owner.parse(owner.previous)
            self.assertEqual([True],changed);self.assertEqual(before,self.commands)

    def test_actual_runtime_factory_passes_its_bound_original_clock_without_avatar_query(self):
        reader,clock=self.readers();seen=[]
        def bound(actual_clock):self.assertIs(clock,actual_clock);seen.append(True);return reader
        source=dict(binding=BINDING,check=lambda:True,observer=SimpleNamespace(bound_native_observer=bound),clock_source=clock)
        fixture=self
        class Runtime(IOSAvatarRuntime):
            def _sources(_self,_selector):return source
            def state_path(_self,_selector):return fixture.root/'session.json'
        runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True));client=Client('https://controlled.invalid/feature-fixture/v1','r'*64)
        with self.lock.held():
            owner=runtime._avatar_account_reads('target',client,self.f.run,'actor','primary',self.artifacts,self.lock)
            owner.epoch_ms=self.f.host;owner.monotonic=lambda:self.f.clock;owner.originals.monotonic=lambda:self.f.clock
            self.logged_in=False;self.subject_session='00000000-0000-0000-0000-000000000000'
            self.assertFalse(owner.packet(owner.read())['account']['loggedIn']);self.assertEqual([True],seen)
            self.assertTrue(all(query['action']=='feature-native-observe' for query in self.commands))

    def test_query_and_clock_queries_are_owned_before_transport_and_unknown_query_is_not_repeated(self):
        with self.lock.held():
            self.lost=True;owner=self.owner()
            with self.assertRaises(NativeUIError):owner.read()
            old=deepcopy(owner.state['pending']);self.assertTrue(old['clocks']);commands=deepcopy(self.commands)
            restored=self.owner();row=restored.recover();self.assertEqual('abandoned',row['status']);self.assertEqual(commands,self.commands)
            self.lost=False;new=restored.read();self.assertNotEqual(old['clocks'][0]['query'],new['clocks'][0]['query'])
            self.assertEqual(1,sum(query==commands[0] for query in self.commands))

    def test_lost_saved_native_file_return_is_retained_and_later_query_uses_new_nonce(self):
        with self.lock.held():
            owner=self.owner();intent=owner.originals.intent
            def lost(kind,value):
                intent(kind,value)
                if value['phase']=='saved':raise OSError('Synthetic lost original file return')
            owner.originals.intent=lost
            with self.assertRaises(NativeUIError):owner.read()
            old=deepcopy(owner.state['pending']);count=len(self.commands);again=self.owner();row=again.recover()
            self.assertEqual('abandoned',row['status']);self.assertEqual(count,len(self.commands));self.assertEqual(old['original'],row['original'])
            new=again.read();self.assertNotEqual(row['query'],new['query']);self.assertEqual(2,len(list(self.artifacts.glob('*-frame-*.json'))))

    def test_lost_completed_metadata_return_is_adopted_without_query(self):
        with self.lock.held():
            owner=self.owner();write=self.store.write
            def lost(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['pending'] is not None and unpack(value['payload'])[0]['pending']['acquisition'] is not None:
                    raise OSError('Synthetic lost completed account record save')
            with patch.object(self.store,'write',side_effect=lost),self.assertRaises(OSError):owner.read()
            count=len(self.commands);again=self.owner();row=again.recover()
            self.assertEqual('observed',row['status']);self.assertEqual(count,len(self.commands));again.packet(row)

    def test_slow_final_save_keeps_original_historical_and_refuses_fresh_return(self):
        with self.lock.held():
            owner=self.owner();write=self.store.write
            def slow(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['rows'] and unpack(value['payload'])[0]['pending'] is None:self.f.clock+=1.501
            with patch.object(self.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.read()
            before=len(self.commands);again=self.owner(historical=True);self.assertEqual('observed',again.state['rows'][0]['status'])
            again.packet(again.state['rows'][0]);self.assertEqual(before,len(self.commands))

    def test_partial_original_file_blocks_future_native_query_and_replacement_is_rejected(self):
        with self.lock.held():
            owner=self.owner();intent=owner.originals.intent
            def lost(kind,value):
                intent(kind,value)
                if value['phase']=='opened':raise OSError('Synthetic lost opened native file')
            owner.originals.intent=lost
            with self.assertRaises(NativeUIError):owner.read()
            original=owner.state['pending']['original'];path=owner.originals.path(original)
            again=self.owner();again.recover();count=len(self.commands)
            with self.assertRaises(NativeUIError):again.read()
            self.assertEqual(count,len(self.commands));raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600)
            with self.assertRaises(NativeUIError):self.owner(historical=True)


if __name__=='__main__':unittest.main()
