"""Owned fixture-phase attachment at explicit HTTP seams; no product evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from feature_journeys.witness import Client
from adapters.normal_ui import NativeUIError
from overte_phone_authentication_feature import AuthenticationFixtureReader,AuthenticationPhasePending,AuthenticationRunRetired

RUN='a'*32;TICKET='b'*32;INSTANCE='c'*32;URL='https://owned.invalid/feature-fixture/v1'


class AuthenticationFixtureTests(unittest.TestCase):
    def setUp(self):
        self.client=Client(URL,'x'*64);self.calls=[];self.clock=9000000
        self.provider=dict(providerVersion=2,instance=INSTANCE,transport='https',tlsVersion='TLSv1.3',internalErrors=0)
        self.status=dict(providerVersion=2,instance=INSTANCE,runId=RUN,capturedEpochMs=self.clock,eventSequence=1,
            accountExists=True,heldRequests=0,armedHold=False,inflightRequests=0,accessTokens=0,refreshTokens=0,grantsEnabled=True)
        self.active=dict(schemaVersion=1,runId=RUN,area='authentication',ticket=TICKET,stimulus=dict(verb='baseline',inputs={}))
        self.journal=dict(schemaVersion=1,runId=RUN,area='authentication',ticket=TICKET,sampleEpochMs=self.clock,entries=[])
        self.client.request=self.request;self.source=self.reader()
    def reader(self,**changes):return AuthenticationFixtureReader(self.client,RUN,epoch_ms=lambda:self.clock,**changes)
    def request(self,path,value=None,method=None,**kwargs):
        self.assertIsNone(value);self.assertIsNone(method);self.assertEqual({},kwargs);self.calls.append(path)
        rows={'/account-provider':self.provider,'/runs/'+RUN+'/account/status':self.status,
              '/runs/'+RUN+'/active':self.active,'/runs/'+RUN:self.journal}
        self.assertIn(path,rows);return deepcopy(rows[path])

    def test_fresh_original_run_attachment_never_registers_activates_or_reads_credentials(self):
        with (patch.object(self.client,'register',side_effect=AssertionError('Unexpected registration')),
              patch.object(self.client,'activate',side_effect=AssertionError('Unexpected activation')),
              patch.object(self.client,'account_credentials',side_effect=AssertionError('Unexpected credential request')),
              patch.object(self.client,'account_control',side_effect=AssertionError('Unexpected mutation'))):
            self.source.read()
        self.assertEqual(['/account-provider','/runs/'+RUN+'/account/status','/runs/'+RUN+'/active','/runs/'+RUN],self.calls)

    def test_original_reader_pins_provider_scope_and_host_read_barrier_without_journal_facts_as_state(self):
        actual=self.source.read()
        self.assertEqual(dict(ticket=TICKET,verb='baseline',inputs={},afterEpochMs=self.clock,status=self.status),actual)
        self.assertEqual(RUN,self.client.run);self.assertEqual(INSTANCE,self.client.account_instance)
        self.assertNotIn('state',actual);self.assertEqual(4,len(self.calls))
        self.journal['sampleEpochMs']=self.clock-.4
        self.assertEqual(self.clock,self.source.read(actual['status'])['afterEpochMs'])

    def test_provider_identity_tls_readiness_or_unreported_errors_cannot_be_replaced(self):
        self.source.read();before=len(self.calls)
        for edit in (dict(instance='f'*32),dict(providerVersion=True),dict(providerVersion=1),dict(transport='http'),
                     dict(tlsVersion='TLSv1'),dict(internalErrors=1)):
            provider=self.provider;self.provider=provider|edit
            with self.subTest(edit=edit),self.assertRaises((NativeUIError,ValueError)):self.source.read()
            self.provider=provider
        self.assertEqual(before+6,len(self.calls))

    def test_recreated_reader_restores_original_provider_clock_and_sequence_floors(self):
        first=self.source.read();self.client.account_epoch=self.client.account_sequence=0
        for edit in (dict(capturedEpochMs=self.clock-1),dict(eventSequence=0)):
            original=self.status;self.status=original|edit
            with self.subTest(edit=edit),self.assertRaises((NativeUIError,ValueError)):self.reader().read(first['status'])
            self.status=original

    def test_retired_original_zero_authority_is_detected_before_requesting_removed_active_scope(self):
        self.status.update(accountExists=False,grantsEnabled=False)
        with self.assertRaises(AuthenticationRunRetired) as error:self.source.read()
        self.assertEqual(self.status,error.exception.status)
        self.assertEqual(['/account-provider','/runs/'+RUN+'/account/status'],self.calls)

    def test_missing_account_with_held_request_or_issued_authority_is_an_error_not_retired_success(self):
        self.status.update(accountExists=False,grantsEnabled=False)
        for edit in (dict(accessTokens=1),dict(refreshTokens=1),dict(heldRequests=1),dict(inflightRequests=1),dict(armedHold=True)):
            original=self.status;self.status=original|edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):self.source.read()
            self.status=original

    def test_stale_provider_journal_unknown_phase_and_foreign_scope_never_become_ready(self):
        for attribute,edit in (('status',dict(capturedEpochMs=self.clock-1501)),
            ('journal',dict(sampleEpochMs=self.clock-1501)),('journal',dict(area='scripts')),
            ('active',dict(runId='f'*32)),('active',dict(schemaVersion=True)),
            ('active',dict(stimulus=dict(verb='login-submit',inputs=dict(account='expected'))))):
            original=getattr(self,attribute);setattr(self,attribute,original|edit)
            with self.subTest(attribute=attribute,edit=edit),self.assertRaises((NativeUIError,ValueError)):self.source.read()
            setattr(self,attribute,original)

    def test_ticket_race_is_pending_without_native_input_or_relabelling(self):
        self.journal['ticket']='f'*32
        with self.assertRaises(AuthenticationPhasePending):self.source.read()
        self.assertEqual(4,len(self.calls));self.assertEqual(TICKET,self.active['ticket'])

    def test_wrong_existing_client_run_area_retirement_or_non_https_origin_fails_before_transport(self):
        for field,value in (('run','f'*32),('area','scripts'),('closed',True),('url','http://owned.invalid/feature-fixture/v1')):
            client=Client(URL,'y'*64);setattr(client,field,value)
            with self.subTest(field=field),self.assertRaises(NativeUIError):AuthenticationFixtureReader(client,RUN)
        self.assertEqual([],self.calls)

    def test_original_host_clock_regression_is_not_hidden_by_a_fresh_transport_cursor(self):
        self.source.read();self.clock-=1
        with self.assertRaises(NativeUIError):self.source.read()

    def test_changed_attached_client_scope_or_boolean_history_cannot_be_silently_repaired(self):
        self.source.read()
        for field,value in (('run','f'*32),('area','scripts'),('account_instance','f'*32),('account_epoch',True),('account_sequence',True)):
            original=getattr(self.client,field);setattr(self.client,field,value);before=len(self.calls)
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.source.read()
            self.assertEqual(before,len(self.calls));self.assertEqual(value,getattr(self.client,field))
            setattr(self.client,field,original)


if __name__=='__main__':unittest.main()
