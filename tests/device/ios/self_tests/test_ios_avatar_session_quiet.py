"""Fresh SDK originals after actual fixture retirement; no account GET replay.

Native Qt/SDK producers are modeled. Actual samplers, private source files,
phase journal retirement and historical validators are composed unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import secrets
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Journal,Client
from ios.adapters.avatar_session_quiet import IOSAvatarSessionQuiet
from ios.self_tests import test_ios_avatar_final as final_fixture


class AvatarSessionQuietTests(unittest.TestCase):
    def setUp(self):
        self.f=final_fixture.AvatarFinalTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.active='primary';self.phase=Journal(clock=self.f.host)
        with patch.object(secrets,'token_hex',return_value=final_fixture.RUN):self.phase.register('avatar-people')
        self.phase.activate(final_fixture.RUN,final_fixture.TICKET,'cleanup');self.phase.close(final_fixture.RUN)
        # The actual account scope is gone. Any attempted AccountProvider GET
        # would now fail rather than supplying a fabricated fresh snapshot.
        self.f.scopes.retire(final_fixture.RUN)
        self.client=Client(self.f.client.url,'r'*64)
        self.client.request=lambda path,phase_nonce:self.phase.phase(final_fixture.RUN,phase_nonce)
        self.reader=PhaseFixtureReader(self.client,final_fixture.RUN,'avatar-people',epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
        self.store=PrivateFeatureState(self.f.store.path.with_name('ios-avatar-primary-session-quiet.json'))
    def owner(self):
        return IOSAvatarSessionQuiet(self.store,self.f.root,self.f.bindings['primary'],final_fixture.RUN,'primary',self.f.locks['primary'],
            lambda:True,lambda:self.f.factory('primary'),self.reader,self.f.inputs['primary'],epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
    def archive(self,owner):
        return IOSAvatarSessionQuiet.archive(owner.previous,store=self.store,root=self.f.root,binding=self.f.bindings['primary'],
            run=final_fixture.RUN,role='primary',lock=self.f.locks['primary'],inputs=self.f.inputs['primary'])
    def test_actual_retired_phase_and_own_original_quiet_without_removed_account_endpoint(self):
        owner=self.owner();refs=[owner.capture()]
        self.f.clock[0]+=1.6;refs.append(owner.capture());self.f.clock[0]+=1.6;refs.append(owner.capture())
        proof=owner.quiet(refs);self.assertFalse(proof['phase']['active']);self.assertNotIn('public',proof)
        self.assertEqual('primary',proof['role']);self.assertGreaterEqual(proof['quiet']['nativeBeforeLastMonotonicMs']-proof['quiet']['nativeAfterFirstMonotonicMs'],3000)
        self.assertNotIn('provider',owner.record(refs[-1]));self.assertNotIn('providerClock',owner.record(refs[-1]))
        count=len(self.f.cases['primary'].f.calls);self.assertEqual(proof,self.archive(owner).quiet(refs));self.assertEqual(count,len(self.f.cases['primary'].f.calls))
        with self.assertRaises(NativeUIError):self.archive(owner).capture()
    def test_fast_reads_and_active_phase_cannot_discharge_owned_sdk(self):
        owner=self.owner();refs=[owner.capture() for _ in range(3)]
        with self.assertRaises(NativeUIError):owner.quiet(refs)
        self.phase.runs[final_fixture.RUN]=self.phase.retired_phases.pop(final_fixture.RUN)
        before=len(self.f.cases['primary'].f.calls)
        with self.assertRaises((NativeUIError,ValueError)):owner.capture()
        self.assertEqual(before,len(self.f.cases['primary'].f.calls));self.assertIsNotNone(owner.state['pending'])
    def test_lost_completed_owner_return_adopts_without_sdk_or_http(self):
        owner=self.owner();write=PrivateFeatureState.write;lost=[]
        def writing(store,value,previous):
            write(store,value,previous)
            if store.path==self.store.path and owner.state['records'] and not lost:
                lost.append(True);raise OSError('Lost final owner return')
        with patch.object(PrivateFeatureState,'write',writing),self.assertRaises(OSError):owner.capture()
        count=len(self.f.cases['primary'].f.calls);sequence=self.phase.phase_sequence
        rebuilt=self.owner();self.assertIsNone(rebuilt.recover());self.archive(rebuilt)
        self.assertEqual(count,len(self.f.cases['primary'].f.calls));self.assertEqual(sequence,self.phase.phase_sequence)
    def test_lost_partial_source_is_owned_then_new_query_advances_without_resend(self):
        owner=self.owner();case=self.f.cases['primary'];case.lost=True
        with self.assertRaises(NativeUIError):owner.capture()
        old=deepcopy(case.channel_calls[-1]);self.assertIsNotNone(owner.state['pending'])
        counts=len(case.f.calls);queries=len(case.channel_calls);case.lost=False
        rebuilt=self.owner();self.assertIsNone(rebuilt.recover())
        self.assertEqual(counts,len(case.f.calls));self.assertEqual(queries,len(case.channel_calls))
        self.assertIsNone(rebuilt.state['records'][0]['reference']);self.assertIn('tail',rebuilt.state['records'][0]['owners'])
        current=rebuilt.capture();self.assertEqual(1,sum(query==old for query in case.channel_calls));self.assertNotEqual(old,case.channel_calls[-1])
        self.archive(rebuilt).original(rebuilt.record(current))

    def test_slow_original_storage_is_historical_only(self):
        owner=self.owner();write=self.store.write
        def slow(value,previous):
            write(value,previous)
            if owner.state['records'] and owner.state['pending'] is None:self.f.clock[0]+=1.501
        with patch.object(self.store,'write',side_effect=slow),self.assertRaises(NativeUIError):owner.capture()
        old=self.archive(self.owner());self.assertEqual(1,len(old.state['records']));old.original(old.record(old.state['records'][0]['reference']))


if __name__=='__main__':unittest.main()
