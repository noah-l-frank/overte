"""Device-free counterexamples for passive native account data and history."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_account_observation import validate,accept,reply_after
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import Boundary


def account():
    return dict(loggedIn=False,principalSha256=hashlib.sha256(b'').hexdigest(),observation=dict(
        accountVersion=1,instance='d'*32,capturedEpochMs=20000,credentialGeneration=1,credentialActive=True,
        endpointPresent=True,endpointSha256='a'*64,loginPending=False,refreshPending=False,
        tokenPresent=False,tokenValid=False,refreshPresent=False,transportRejected=False,
        eventSequence=0,droppedEvents=0,events=[]))


def account_source(value):
    measured=account()
    measured['observation']['capturedEpochMs']=value['capturedEpochMs']
    value['account']=measured


def event(sequence=1,kind='login-reply',epoch=20000,generation=2,status=400):
    reply=kind.endswith('-reply')
    return dict(sequence=sequence,kind=kind,capturedEpochMs=epoch,credentialGeneration=generation,
        hasReply=reply,httpStatus=status if reply else 0,networkError=203 if reply else 0,
        transportRejected=False,timedOut=False)


def append(value,row):
    source=value['observation'];source['events'].append(row)
    source['eventSequence']=row['sequence'];source['credentialGeneration']=row['credentialGeneration']
    source['capturedEpochMs']=max(source['capturedEpochMs'],row['capturedEpochMs'])
    if len(source['events'])>64:source['events'].pop(0);source['droppedEvents']+=1


class AccountObservationTests(unittest.TestCase):
    def test_fresh_passive_pending_state_needs_no_expected_login_result(self):
        value=account();value['observation']['loginPending']=True
        self.assertTrue(validate(value,20000,20000)['loginPending'])
        self.assertFalse(value['loggedIn']);self.assertEqual([],value['observation']['events'])
        with self.assertRaises(NativeUIError):reply_after(value,'login-reply',after_sequence=0,after_epoch=20000,credential_generation=1)

    def test_required_source_rejects_old_narrow_native_packets(self):
        boundary=Boundary();reader=self.reader(boundary)
        with self.assertRaises(NativeUIError):reader.read(0,require_account=True)

    def reader(self,boundary):
        return NativeFeatureObservation(send=boundary.send,read=lambda:json.dumps(boundary.sample),pid=123,
            clock_ms=lambda:20000,guard=boundary.guard,monotonic=lambda:boundary.clock,sleep=boundary.sleep)

    def test_original_native_history_is_pinned_across_reads_and_cannot_downgrade(self):
        boundary=Boundary();value=account()
        boundary.mutate=lambda sample:sample.update(account=deepcopy(value))
        reader=self.reader(boundary);first=reader.read(0,require_account=True)
        value['observation']['instance']='e'*32
        with self.assertRaises(NativeUIError):reader.read(first['sequence'],require_account=True)
        boundary.mutate=None
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])

    def test_missing_and_stale_or_pre_request_account_sample_cannot_be_retimed(self):
        for captured in (18499,20001):
            value=account();value['observation']['capturedEpochMs']=captured
            with self.assertRaises(NativeUIError):validate(value,20000)
        with self.assertRaises(NativeUIError):validate(account(),20000,20001)

    def test_scalar_flags_and_token_contradictions_are_rejected(self):
        for edits in ({'loginPending':1},{'loginPending':True,'refreshPending':True},
                      {'tokenValid':True,'tokenPresent':False},{'accountVersion':True},
                      {'endpointPresent':False},{'credentialGeneration':0}):
            value=account();value['observation'].update(edits)
            with self.assertRaises(NativeUIError):validate(value,20000)
        value=account();value['loggedIn']=True
        with self.assertRaises(NativeUIError):validate(value,20000)

    def test_real_reply_is_distinct_from_profile_adoption_or_protected_access(self):
        value=account();append(value,event(status=200));validate(value,20000)
        row=reply_after(value,'login-reply',after_sequence=0,after_epoch=20000,credential_generation=2)
        self.assertEqual(200,row['httpStatus']);self.assertFalse(value['loggedIn'])
        self.assertNotIn('protectedAccess',value['observation'])
        with self.assertRaises(NativeUIError):reply_after(value,'profile-reply',after_sequence=0,after_epoch=20000,credential_generation=2)

    def test_prior_foreign_or_ambiguous_terminal_events_are_not_new_completion(self):
        value=account();append(value,event());validate(value,20000)
        for args in ({'after_sequence':1},{'after_epoch':20001},{'credential_generation':3}):
            options=dict(after_sequence=0,after_epoch=20000,credential_generation=2);options.update(args)
            with self.assertRaises(NativeUIError):reply_after(value,'login-reply',**options)
        append(value,event(sequence=2));validate(value,20000)
        with self.assertRaises(NativeUIError):reply_after(value,'login-reply',after_sequence=0,after_epoch=20000,credential_generation=2)

    def test_rewritten_historical_reply_and_generation_regression_are_rejected(self):
        value=account();append(value,event());validate(value,20000);old=accept(None,value)
        for mutate in (lambda row:row['events'][0].update(httpStatus=200),
                       lambda row:row.update(credentialGeneration=1),
                       lambda row:row.update(endpointSha256='b'*64),
                       lambda row:row.update(eventSequence=0,events=[])):
            newer=deepcopy(value);mutate(newer['observation'])
            with self.assertRaises(NativeUIError):
                validate(newer,20000);accept(old,newer)

    def test_original_bounded_ring_explicitly_counts_dropped_records(self):
        value=account()
        for sequence in range(1,70):append(value,event(sequence=sequence))
        source=validate(value,20000);self.assertEqual(5,source['droppedEvents']);self.assertEqual(6,source['events'][0]['sequence'])
        value['observation']['droppedEvents']=0
        with self.assertRaises(NativeUIError):validate(value,20000)

    def test_unknown_secret_and_desired_state_fields_or_bad_terminal_types_are_rejected(self):
        for edit in ({'password':'never-export'},{'protectedAccess':True}):
            value=account();value['observation'].update(edit)
            with self.assertRaises(NativeUIError):validate(value,20000)
        for edit in ({'httpStatus':True},{'hasReply':False},{'networkError':500},
                     {'kind':'expected-success'},{'capturedEpochMs':20001}):
            value=account();row=event();row.update(edit);append(value,row)
            with self.assertRaises(NativeUIError):validate(value,20000)

    def test_signal_notifications_cannot_forge_an_http_reply(self):
        value=account();append(value,event(kind='login-complete'));validate(value,20000)
        with self.assertRaises(NativeUIError):reply_after(value,'login-reply',after_sequence=0,after_epoch=20000,credential_generation=2)
        value['observation']['events'][0]['httpStatus']=200
        with self.assertRaises(NativeUIError):validate(value,20000)

    def test_native_sampler_uses_passive_owner_thread_api_without_refresh_or_ui_input(self):
        root=Path(__file__).resolve().parents[3]
        interface=(root/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
        start=interface.index('    const auto readAccount = [&] {');end=interface.index('    QVariantMap result',start)
        self.assertIn('featureAccountObservation()',interface[start:end])
        self.assertNotIn('isLoggedIn()',interface[start:end].replace('ordinary isLoggedIn() can refresh credentials.',''))
        native=(root/'libraries/networking/src/AccountManager.cpp').read_text()
        start=native.index('QVariantMap AccountManager::featureAccountObservation() const');end=native.index('#endif',start)
        source=native[start:end]
        for name in ('hasValidAccessToken(', 'isLoggedIn(', 'refreshAccessToken(', 'requestProfile(', 'emit ', 'sendRequest('):
            self.assertNotIn(name,source)
        self.assertIn('QThread::currentThread() != thread()',source)
        self.assertIn('token.isExpired()',source)


if __name__=='__main__':unittest.main()
