"""Owned fixture-phase attachment at explicit HTTP seams; no product evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import os
import tempfile
import hashlib

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


class AuthenticationOwnerTests(unittest.TestCase):
    def setUp(self):
        from test_authentication_actions import InputSources
        from overte_phone_authentication_actions import PhoneAuthenticationActions
        from overte_phone_authentication_feature import PhoneAuthenticationFeature
        from feature_journeys.witness import Journal
        from self_tests.test_script_ui_inventory import inventory
        from adapters.normal_feature_state import PrivateFeatureState
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);os.chmod(self.root,0o700)
        self.s=InputSources(self.root);self.calls=[];self.counter=0
        self.journal=Journal(lambda:20000)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.assertEqual(RUN,self.journal.register('authentication'))
        self.journal.activate(RUN,TICKET)
        self.provider=dict(providerVersion=2,instance=INSTANCE,transport='https',tlsVersion='TLSv1.3',internalErrors=0)
        self.grants_enabled=True
        # Preserve the original source helper's provider proof, then route the
        # control protocol through the real shared journal reducer. No desired
        # checkpoint or state is ever returned from this test transport.
        originals=self.s.request
        def request(role,path,value=None,method=None,**kwargs):
            self.assertEqual({},kwargs);self.calls.append((role,path))
            if path=='/account-provider':return deepcopy(self.provider)
            if path=='/runs/'+RUN+'/account/status':
                return dict(providerVersion=2,instance=INSTANCE,runId=RUN,capturedEpochMs=20000,eventSequence=self.s.provider_sequence,
                    accountExists=True,heldRequests=0,armedHold=False,inflightRequests=0,
                    accessTokens=int(self.s.fact['loggedIn']),refreshTokens=int(self.s.fact['loggedIn']),grantsEnabled=self.grants_enabled)
            if path=='/runs/'+RUN+'/active':
                if value is not None:
                    self.assertEqual('primary',role);self.journal.activate(RUN,**value);return {}
                return self.journal.active(RUN)
            if path=='/runs/'+RUN:return self.journal.snapshot(RUN)
            if path=='/runs/'+RUN+'/samples':
                self.assertEqual('actor',role);self.journal.publish(RUN,value);return {}
            if '/account/proof/' in path:
                self.assertEqual('actor',role)
                if path.rsplit('/',2)[1]!=self.journal.active(RUN)['ticket']:raise ValueError('Synthetic retired actual request')
                return originals(path)|dict(capturedEpochMs=20000)
            if path=='/runs/'+RUN+'/account/delayed':return originals(path)|dict(capturedEpochMs=20000)
            self.fail('Unexpected synthetic fixture request')
        self.s.client.request=lambda *args,**kwargs:request('primary',*args,**kwargs)
        del self.s.client.account_status
        actor=Client(URL,'y'*64);actor.request=lambda *args,**kwargs:request('actor',*args,**kwargs)
        # Both sources read the actual current synthetic native token. The
        # independent fixture proof is generated only for that actual request.
        probe=self.s.probe.mutate
        def response(packet):
            probe(packet)
            if packet['operation']=='read':
                accepted=self.s.fact['loggedIn'] and self.grants_enabled
                packet['source'].update(httpStatus=200 if accepted else 401,networkError=0 if accepted else 204,
                    tokenAttached=self.s.fact['observation']['tokenValid'],
                    principalSha256=hashlib.sha256(('e2e-'+RUN).encode() if accepted else b'').hexdigest())
        self.s.probe.mutate=response
        self.s.tablet.mutate=lambda packet:packet.update(processId=self.s.pid,controls=[],scriptInventory=inventory(tabletShown=self.s.menu_client.panel is not None))
        self.s.authentication_samples_store=lambda _selector,role,stage:PrivateFeatureState(self.root/('phone-authentication-'+role+'-'+str(stage)+'-samples.json'))
        self.s.authentication_actions_store=lambda _selector:PrivateFeatureState(self.root/'phone-authentication-actions.json')
        self.s._authentication_actions=lambda selector,client,run:PhoneAuthenticationActions(self.s,selector,client,run)
        self.primary=PhoneAuthenticationFeature(self.s,'selector',AuthenticationFixtureReader(self.s.client,RUN,epoch_ms=lambda:20000),
            monotonic=lambda:self.s.clock,sleep=lambda value:setattr(self.s,'clock',self.s.clock+value))
        self.actor=PhoneAuthenticationFeature(self.s,'selector',AuthenticationFixtureReader(actor,RUN,epoch_ms=lambda:20000),role='actor',
            monotonic=lambda:self.s.clock,sleep=lambda value:setattr(self.s,'clock',self.s.clock+value))
    def observe(self,owner=None):
        from feature_journeys.scenarios import VERSION
        return (owner or self.primary).observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
    def act(self,verb,inputs=None):
        from feature_journeys.scenarios import VERSION
        self.counter+=1;ticket=format(self.counter,'032x');inputs=inputs or {}
        self.s.client.activate(ticket,verb,inputs)
        return self.primary.act(dict(contractVersion=VERSION,runId=RUN,fixtureUrl=URL+'/runs/'+RUN+'/',ticket=ticket,verb=verb,inputs=inputs))

    def test_baseline_has_two_independent_native_and_http_acquisitions_without_input(self):
        primary=self.observe();actor=self.observe(self.actor)
        self.assertEqual(primary['state'],actor['state']);self.assertEqual([],primary['resources'])
        self.assertEqual((1,1),(primary['sequence'],actor['sequence']))
        first,last=self.primary.role_state()['last']['frame'],self.actor.role_state()['last']['frame']
        self.assertNotEqual(first['probe']['requestId'],last['probe']['requestId'])
        self.assertIsNone(first['proof']);self.assertIsNotNone(last['proof'])
        self.assertEqual([],self.s.login.inputs);self.assertEqual([],self.s.inputs)

    def test_actor_waits_for_primary_owned_scope_and_for_each_actual_input_phase(self):
        with self.assertRaises(AuthenticationPhasePending):self.observe(self.actor)
        self.assertIsNone(self.actor.role_store.read());self.observe()
        self.s.client.activate('f'*32,'login-open',{})
        with self.assertRaises(AuthenticationPhasePending):self.observe(self.actor)
        self.assertEqual([],self.s.login.inputs);self.assertIsNone(self.actor.role_state()['last'])

    def test_invalid_then_owned_login_normal_input_is_joined_with_fresh_independent_protected_access(self):
        self.observe();self.actor.publish()
        for verb,inputs in (('login-open',{}),('login-submit',{'account':'invalid'}),('login-cancel',{}),
                            ('login-open',{}),('login-submit',{'account':'owned'})):
            self.act(verb,inputs);primary=self.observe();self.actor.publish()
            actual=self.journal.snapshot(RUN)['entries'][-1]['facts']
            self.assertEqual(primary['state'],actual)
        self.assertTrue(primary['state']['protectedAccess']);self.assertEqual('owned',primary['state']['principal'])
        self.assertFalse(primary['state']['dialog']);self.assertEqual(2,sum(action=='submit' for _,action in self.s.login.inputs))

    def test_each_role_acquires_own_restart_exit_and_new_account_birth(self):
        self.observe();self.observe(self.actor)
        self.act('restart-app');primary=self.observe();actor=self.observe(self.actor)
        self.assertEqual(2,primary['lifecycle']['launches']);self.assertEqual(primary['state'],actor['state'])
        one,two=self.primary.role_state(),self.actor.role_state()
        self.assertEqual((1,1),(one['stage'],two['stage']))
        self.assertNotEqual(one['restarts'][0]['exit']['commandId'],two['restarts'][0]['exit']['commandId'])
        for role in (one,two):
            self.assertNotEqual(role['last']['frame']['nativeAfter']['account']['observation']['instance'],
                role['restarts'][0]['oldFrame']['nativeAfter']['account']['observation']['instance'])

    def test_missing_own_old_role_observation_cannot_borrow_primary_restart_proof(self):
        self.observe();self.act('restart-app');self.observe()
        with self.assertRaises(NativeUIError):self.observe(self.actor)
        self.assertIsNone(self.actor.role_state()['last'])

    def test_corrupt_role_exit_history_blocks_another_fresh_observation(self):
        from overte_phone_script_history import pack,unpack
        self.observe();self.observe(self.actor);self.act('restart-app');self.observe();self.observe(self.actor)
        store=self.actor.role_store;old=store.read();state=unpack(old['payload'])[0]
        state['restarts'][0]['exit'].update(presence='unknown',nativeError=1,errorSymbol='EPERM')
        store.write(old|dict(payload=pack([state])),old)
        before=len(self.s.native.commands)
        with self.assertRaises(NativeUIError):self.observe(self.actor)
        self.assertEqual(before,len(self.s.native.commands))

    def test_missing_native_result_retains_reading_role_and_source_ownership(self):
        self.observe();self.s.native.ignored=True
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual('reading',self.primary.role_state()['phase'])

    def test_observer_cannot_publish_a_retired_sample_under_the_next_ticket(self):
        self.observe();self.observe(self.actor)
        post=self.actor.source.client.request
        def changed(path,value=None,method=None,**kwargs):
            if path.endswith('/samples'):
                self.journal.activate(RUN,'f'*32,'login-open',{})
            return post(path,value,method,**kwargs)
        with patch.object(self.actor.source.client,'request',side_effect=changed):self.assertIsNone(self.actor.publish())
        self.assertEqual([],self.journal.snapshot(RUN)['entries'])


if __name__=='__main__':unittest.main()
