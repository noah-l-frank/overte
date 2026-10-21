"""Original account-event counterexamples; synthetic sources, no device claims."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tests/device')]
from adapters.authentication_journey.causality import check,wait,AuthenticationReadinessPending
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION
from self_tests.test_native_feature_observation import Boundary
from self_tests.test_native_account_observation import account,event,append

RUN='a'*32;TICKET='b'*32;PROVIDER='c'*32;ORIGIN='https://owned.invalid'


class AuthenticationCausalityTests(unittest.TestCase):
    def setUp(self):
        self.boundary=Boundary();self.fact=account()
        self.fact['observation']['endpointSha256']=hashlib.sha256(ORIGIN.encode()).hexdigest()
        self.boundary.mutate=lambda packet:packet.update(account=deepcopy(self.fact))
        self.reader=self.boundary.reader();self.before=self.reader.read(0,require_account=True)
        self.records=[]
    def call(self,verb='login-submit',role='invalid'):
        return dict(contractVersion=VERSION,runId=RUN,ticket=TICKET,fixtureUrl=ORIGIN+'/feature-fixture/v1/runs/'+RUN+'/',
            verb=verb,inputs={'account':role} if verb=='login-submit' else {})
    def current(self):return self.reader.read(self.reader.sequence,require_account=True)
    def reply(self,status=400):append(self.fact,event(status=status))
    def logged(self):
        self.fact.update(loggedIn=True,principalSha256=hashlib.sha256(('e2e-'+RUN).encode()).hexdigest())
        self.fact['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
    def delayed(self):
        return dict(providerVersion=2,instance=PROVIDER,runId=RUN,capturedEpochMs=9000000,eventSequence=1,grantsEnabled=True,
            requests=[dict(requestId='e'*32,requestTicket=TICKET,startedEpochMs=9000000,releasedEpochMs=0,
                issuedEpochMs=0,status=0,state='held',accessValid=False,refreshValid=False)],delayedGrantOutstanding=False)

    def test_actual_terminal_invalid_reply_is_required_without_manufacturing_visible_error(self):
        self.reply();actual=check(self.call(),self.before,self.current(),20000)
        self.assertEqual(400,actual['native']['account']['observation']['events'][0]['httpStatus'])
        self.assertFalse(actual['native']['account']['loggedIn']);self.assertNotIn('state',actual)
        self.assertIsNone(actual['delayed'])

    def test_successful_grant_needs_original_reply_and_loaded_cached_principal(self):
        self.reply(200);self.logged();actual=check(self.call(role='owned'),self.before,self.current(),20000)
        self.assertTrue(actual['native']['account']['loggedIn'])
        self.fact['principalSha256']=hashlib.sha256(b'').hexdigest()
        with self.assertRaises(AuthenticationReadinessPending):check(self.call(role='owned'),self.before,self.current(),20000)

    def test_ignored_submit_and_http_200_ack_without_native_terminal_reply_never_succeed(self):
        with self.assertRaises(AuthenticationReadinessPending):check(self.call(),self.before,self.current(),20000)
        self.fact['observation']['credentialGeneration']=2;self.logged()
        with self.assertRaises(AuthenticationReadinessPending):check(self.call(role='owned'),self.before,self.current(),20000)

    def test_old_reply_new_sample_or_signal_only_cannot_be_a_fresh_terminal_request(self):
        self.reply();before=self.current();current=self.current()
        with self.assertRaises(AuthenticationReadinessPending):check(self.call(),before,current,20000)
        append(self.fact,event(sequence=2,kind='login-failed'))
        with self.assertRaises(AuthenticationReadinessPending):check(self.call(),before,self.current(),20000)

    def test_repeated_or_wrong_generation_terminal_requests_are_rejected(self):
        self.reply();append(self.fact,event(sequence=2))
        with self.assertRaises(NativeUIError):check(self.call(),self.before,self.current(),20000)
        self.fact=account();self.fact['observation']['endpointSha256']=hashlib.sha256(ORIGIN.encode()).hexdigest()
        append(self.fact,event(generation=1))
        boundary=Boundary();boundary.mutate=lambda packet:packet.update(account=deepcopy(self.fact))
        current=boundary.reader().read(0,require_account=True);current['sequence']=2
        with self.assertRaises(NativeUIError):check(self.call(),self.before,current,20000)

    def test_delayed_submit_joins_actual_held_request_ticket_and_native_pending_state(self):
        self.fact['observation'].update(credentialGeneration=2,loginPending=True)
        actual=check(self.call(role='delayed'),self.before,self.current(),20000,delayed=self.delayed(),provider_instance=PROVIDER)
        self.assertTrue(actual['native']['account']['observation']['loginPending'])
        self.assertFalse(actual['delayed']['delayedGrantOutstanding'])
        for edit in (dict(instance='f'*32),dict(runId='f'*32)):
            with self.assertRaises(NativeUIError):check(self.call(role='delayed'),self.before,self.current(),20000,
                delayed=self.delayed()|edit,provider_instance=PROVIDER)

    def test_unmatched_missing_or_duplicate_held_request_cannot_qualify_delayed_submit(self):
        self.fact['observation'].update(credentialGeneration=2,loginPending=True)
        for fault in ('ticket','missing','duplicate'):
            delayed=self.delayed()
            if fault=='ticket':delayed['requests'][0]['requestTicket']='f'*32
            if fault=='missing':delayed['requests']=[]
            if fault=='duplicate':delayed['requests'].append(delayed['requests'][0]|dict(requestId='f'*32))
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                check(self.call(role='delayed'),self.before,self.current(),20000,delayed=delayed,provider_instance=PROVIDER)

    def test_view_cancel_and_reopen_preserve_actual_pending_request_without_new_reply(self):
        self.fact['observation'].update(credentialGeneration=2,loginPending=True)
        before=self.current()
        for verb in ('login-cancel','login-open'):
            actual=check(self.call(verb),before,self.current(),20000)
            self.assertTrue(actual['native']['account']['observation']['loginPending'])
        self.fact['observation']['loginPending']=False
        with self.assertRaises(NativeUIError):check(self.call('login-cancel'),before,self.current(),20000)

    def test_released_retired_response_cannot_adopt_or_clear_credentials_in_new_consumer(self):
        check(self.call('release-stale-response'),self.before,self.current(),20000)
        self.fact['observation']['credentialGeneration']=2;self.logged()
        with self.assertRaises(NativeUIError):check(self.call('release-stale-response'),self.before,self.current(),20000)

    def test_logout_requires_new_signal_actual_credential_clear_and_current_anonymous_principal(self):
        self.logged();before=self.current();self.fact=account()
        self.fact['observation']['endpointSha256']=hashlib.sha256(ORIGIN.encode()).hexdigest()
        with self.assertRaises(AuthenticationReadinessPending):check(self.call('logout'),before,self.current(),20000)
        append(self.fact,event(kind='logout-complete'));actual=check(self.call('logout'),before,self.current(),20000)
        self.assertFalse(actual['native']['account']['loggedIn'])
        for key in ('tokenPresent','refreshPresent','loginPending','refreshPending'):
            self.fact['observation'][key]=True
            with self.subTest(key=key),self.assertRaises(NativeUIError):check(self.call('logout'),before,self.current(),20000)
            self.fact['observation'][key]=False

    def test_unrelated_birth_endpoint_account_or_pre_barrier_clock_cannot_be_relabelled(self):
        self.reply();current=self.current()
        for key,value in (('instance','f'*32),('sequence',self.before['sequence']),('requestId',self.before['requestId']),
                          ('capturedEpochMs',19999),('processId',999)):
            wrong=deepcopy(current);wrong[key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):check(self.call(),self.before,wrong,20000)
        for key,value in (('instance','f'*32),('endpointSha256','f'*64)):
            wrong=deepcopy(current);wrong['account']['observation'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):check(self.call(),self.before,wrong,20000)

    def test_readiness_wait_reacquires_originals_and_records_pending_before_polling(self):
        def record(value):
            self.records.append(value)
            if len(self.records)==2:self.reply()
        actual=wait(self.call(),self.before,self.reader,monotonic=lambda:self.boundary.clock,
            sleep=self.boundary.sleep,record=record)
        self.assertEqual(3,len(self.records));self.assertEqual(4,len(self.boundary.commands))
        self.assertTrue(all(command['action']=='feature-native-observe' for command in self.boundary.commands))
        self.assertEqual(actual,self.records[-1])

    def test_readiness_deadline_record_failure_and_ignored_native_source_never_replay_input(self):
        def late(value):self.records.append(value);self.boundary.clock=20
        with self.assertRaises(NativeUIError):wait(self.call(),self.before,self.reader,
            monotonic=lambda:self.boundary.clock,sleep=self.boundary.sleep,record=late)
        self.assertEqual(1,len(self.records))
        self.boundary.clock=0
        def fail(_value):raise OSError('Synthetic journal unavailable')
        with self.assertRaises(OSError):wait(self.call(),self.before,self.reader,record=fail)
        self.boundary.ignored=True
        with self.assertRaises(NativeUIError):wait(self.call(),self.before,self.reader,record=self.records.append)

    def test_delayed_provider_join_uses_original_host_clock_and_persists_frame_before_causal_decision(self):
        self.fact['observation'].update(credentialGeneration=2,loginPending=True)
        provider=SimpleNamespace(account_instance=PROVIDER,request=lambda _path:self.delayed())
        actual=wait(self.call(role='delayed'),self.before,self.reader,provider=provider,record=self.records.append,epoch_ms=lambda:9000000)
        self.assertEqual(actual,self.records[0])
        with self.assertRaises(NativeUIError):wait(self.call(role='delayed'),self.before,self.reader,
            provider=provider,record=self.records.append,epoch_ms=lambda:9001501)


if __name__=='__main__':unittest.main()
