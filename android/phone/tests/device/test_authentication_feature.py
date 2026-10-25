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
        self.epoch=lambda:20000+round(self.s.clock*1000)
        self.s.epoch_ms=self.epoch;self.s.provider_epoch_ms=self.epoch
        self.journal=Journal(self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.assertEqual(RUN,self.journal.register('authentication'))
        self.journal.activate(RUN,TICKET)
        self.provider=dict(providerVersion=2,instance=INSTANCE,transport='https',tlsVersion='TLSv1.3',internalErrors=0)
        self.grants_enabled=True;self.account_exists=True;self.remote_tokens=self.remote_refresh=0
        grant=self.s.grant
        def native_grant(password):
            grant(password)
            if password=='synthetic-private-owned' and self.s.fact['loggedIn']:
                self.remote_tokens+=1;self.remote_refresh+=1
        self.s.grant=native_grant
        # Preserve the original source helper's provider proof, then route the
        # control protocol through the real shared journal reducer. No desired
        # checkpoint or state is ever returned from this test transport.
        originals=self.s.request
        def request(role,path,value=None,method=None,**kwargs):
            self.calls.append((role,path))
            if path=='/runs/'+RUN+'/phase':
                self.assertIsNone(value);self.assertIsNone(method)
                self.assertEqual({'phase_nonce'},set(kwargs))
                return self.journal.phase(RUN,kwargs['phase_nonce'])
            self.assertEqual({},kwargs)
            if path=='/account-provider':return deepcopy(self.provider)
            if path=='/runs/'+RUN+'/account/status':
                return dict(providerVersion=2,instance=INSTANCE,runId=RUN,capturedEpochMs=self.epoch(),eventSequence=self.s.provider_sequence,
                    accountExists=self.account_exists,heldRequests=sum(row['state']=='held' for row in self.s.provider_rows),armedHold=False,inflightRequests=0,
                    accessTokens=self.remote_tokens,refreshTokens=self.remote_refresh,grantsEnabled=self.grants_enabled)
            if path=='/runs/'+RUN+'/account/control':
                self.assertEqual('primary',role);self.assertEqual({'operation':'cleanup'},value)
                self.account_exists=False;self.grants_enabled=False;self.remote_tokens=self.remote_refresh=0
                for row in self.s.provider_rows:
                    row.update(accessValid=False,refreshValid=False)
                    if row['state']=='held':row.update(state='cancelled',status=503)
                return {}
            if path=='/runs/'+RUN+'/active':
                if value is not None:
                    self.assertEqual('primary',role);self.journal.activate(RUN,**value);self.s.pending_ticket=value['ticket']
                    if value['verb']=='cleanup':
                        self.grants_enabled=False;self.remote_tokens=self.remote_refresh=0
                        for row in self.s.provider_rows:
                            row.update(accessValid=False,refreshValid=False)
                            if row['state']=='held':row.update(state='cancelled',status=503)
                    elif value['verb']=='release-stale-response':
                        for row in self.s.provider_rows:
                            if row['state']=='held':
                                row.update(releasedEpochMs=self.epoch(),issuedEpochMs=self.epoch(),status=200,state='issued',accessValid=True,refreshValid=True)
                                self.remote_tokens+=1;self.remote_refresh+=1
                    return {}
                return self.journal.active(RUN)
            if path=='/runs/'+RUN:
                if method=='DELETE':
                    self.assertEqual('primary',role);self.assertFalse(self.account_exists)
                    self.journal.close(RUN);return {}
                return self.journal.snapshot(RUN)
            if path=='/runs/'+RUN+'/samples':
                self.assertEqual('actor',role);self.journal.publish(RUN,value);return {}
            if '/account/proof/' in path:
                self.assertEqual('actor',role)
                if path.rsplit('/',2)[1]!=self.journal.active(RUN)['ticket']:raise ValueError('Synthetic retired actual request')
                return originals(path)
            if path=='/runs/'+RUN+'/account/delayed':
                return originals(path)|dict(grantsEnabled=self.grants_enabled,
                    delayedGrantOutstanding=any(row['accessValid'] or row['refreshValid'] for row in self.s.provider_rows))
            self.fail('Unexpected synthetic fixture request')
        self.s.client.request=lambda *args,**kwargs:request('primary',*args,**kwargs)
        self.s.client.monotonic=lambda:self.s.clock
        self.s.client.sleep=lambda value:setattr(self.s,'clock',self.s.clock+value)
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
        self.s.tablet.mutate=lambda packet:packet.update(processId=self.s.pid,capturedEpochMs=self.epoch(),controls=[],scriptInventory=inventory(tabletShown=self.s.menu_client.panel is not None))
        self.s.authentication_samples_store=lambda _selector,role,stage:PrivateFeatureState(self.root/('phone-authentication-'+role+'-'+str(stage)+'-samples.json'))
        self.s.authentication_actions_store=lambda _selector:PrivateFeatureState(self.root/'phone-authentication-actions.json')
        self.s._authentication_actions=lambda selector,client,run:PhoneAuthenticationActions(self.s,selector,client,run)
        self.primary=PhoneAuthenticationFeature(self.s,'selector',AuthenticationFixtureReader(self.s.client,RUN,epoch_ms=self.epoch),
            monotonic=lambda:self.s.clock,sleep=lambda value:setattr(self.s,'clock',self.s.clock+value))
        self.actor=PhoneAuthenticationFeature(self.s,'selector',AuthenticationFixtureReader(actor,RUN,epoch_ms=self.epoch),role='actor',
            monotonic=lambda:self.s.clock,sleep=lambda value:setattr(self.s,'clock',self.s.clock+value))
    def observe(self,owner=None):
        from feature_journeys.scenarios import VERSION
        return (owner or self.primary).observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
    def act(self,verb,inputs=None):
        from feature_journeys.scenarios import VERSION
        self.counter+=1;ticket=format(self.counter,'032x');inputs=inputs or {}
        self.s.client.activate(ticket,verb,inputs)
        return self.primary.act(dict(contractVersion=VERSION,runId=RUN,fixtureUrl=URL+'/runs/'+RUN+'/',ticket=ticket,verb=verb,inputs=inputs))

    def cleanup(self):
        from feature_journeys.scenarios import VERSION
        active=self.journal.active(RUN)
        if active['stimulus']['verb']!='cleanup':self.s.client.activate('e'*32,'cleanup',{})
        return self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))

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

    def test_cleanup_requires_fresh_native_and_host_quiet_window_and_two_fresh_idempotent_reads(self):
        self.observe();self.observe(self.actor)
        self.assertEqual({'performed':True},self.cleanup())
        first=self.primary.control();self.assertEqual('cleaned',first['phase'])
        frames=[row['frame'] for row in first['cleanupProof'] if row['kind']=='frame']
        self.assertGreaterEqual(len(frames),3)
        self.assertGreaterEqual(frames[-1]['nativeAfter']['capturedEpochMs']-frames[0]['nativeBefore']['capturedEpochMs'],3000)
        self.assertEqual({'performed':True},self.cleanup())
        primary=self.observe();actor=self.observe(self.actor)
        self.assertEqual([],primary['resources']);self.assertEqual(primary['state'],actor['state'])
        self.assertEqual([],self.s.login.inputs);self.assertEqual([],self.s.inputs)
        self.assertTrue(all(row['probeReleased']['source']['credentialBytes']==0 for row in frames))

    def test_cleanup_closes_actual_owned_menu_and_revokes_remote_authority_after_normal_logout(self):
        self.observe();self.observe(self.actor)
        for verb,inputs in (('login-open',{}),('login-submit',{'account':'owned'}),('logout',{})):
            self.act(verb,inputs);self.observe();self.observe(self.actor)
        self.assertIsNotNone(self.s.menu_client.panel);self.assertEqual(1,self.remote_tokens)
        self.cleanup();self.assertIsNone(self.s.menu_client.panel)
        self.assertEqual(0,self.remote_tokens);self.assertEqual([],self.observe()['resources'])
        self.assertEqual(1,sum(resource=='nav.close' for resource,_label in self.s.menu_client.inputs))

    def test_ignored_tablet_close_is_retained_and_is_not_replayed_on_another_cleanup_call(self):
        self.observe();self.act('login-open');self.act('login-submit',{'account':'owned'});self.act('logout')
        self.s.menu_client.ignore='nav.close'
        with self.assertRaises(NativeUIError):self.cleanup()
        self.assertIsNotNone(self.s.menu_client.panel);self.assertEqual('cleaning',self.primary.control()['phase'])
        before=list(self.s.menu_client.inputs)
        with self.assertRaises(NativeUIError):self.cleanup()
        self.assertEqual(before,self.s.menu_client.inputs)

    def test_remote_authority_not_revoked_cannot_be_hidden_by_native_anonymous_cleanup(self):
        self.observe();self.s.client.activate('e'*32,'cleanup',{})
        self.remote_tokens=1;self.remote_refresh=1;self.grants_enabled=True
        with self.assertRaises(NativeUIError):self.cleanup()
        self.assertEqual('cleaning',self.primary.control()['phase']);self.assertFalse(self.s.fact['loggedIn'])

    def test_frozen_original_native_and_provider_clocks_cannot_satisfy_quiet_cleanup(self):
        self.observe();self.s.epoch_ms=lambda:20000;self.s.provider_epoch_ms=lambda:20000
        self.primary.source.epoch_ms=lambda:20000
        self.epoch=lambda:20000
        with self.assertRaises(NativeUIError):self.cleanup()
        self.assertEqual('cleaning',self.primary.control()['phase'])

    def ready_to_finalize(self):
        self.observe();self.observe(self.actor);self.cleanup();self.observe();self.observe(self.actor)
        self.s.client.close()

    def test_final_host_retirement_requires_both_independent_cleanup_frames_and_retired_actual_fixture(self):
        self.ready_to_finalize();before=sum(command['operation']=='read' for command in self.s.probe.commands)
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertTrue(all(store.read() is None for store in self.primary._retirement_paths()))
        self.assertIsNone(self.primary.retirement_store.read())
        self.assertEqual(before,sum(command['operation']=='read' for command in self.s.probe.commands))
        self.assertFalse(self.s.origin.path.exists());self.assertEqual([],self.s.inputs)

    def test_missing_actor_cleanup_cannot_be_replaced_with_primary_baseline(self):
        self.observe();self.observe(self.actor);self.cleanup();self.observe();self.s.client.close()
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.store.read());self.assertIsNone(self.primary.retirement_store.read())

    def test_actual_live_fixture_account_prevents_host_retirement_even_after_both_roles_cleaned(self):
        self.observe();self.observe(self.actor);self.cleanup();self.observe();self.observe(self.actor)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.store.read());self.assertIsNotNone(self.primary.retirement_store.read())

    def test_host_retirement_recovery_rechecks_actual_native_absence_without_new_http_get_or_input(self):
        from adapters.normal_feature_state import PrivateFeatureState
        self.ready_to_finalize();discard=PrivateFeatureState.discard;removed=[]
        def lost(store,previous):
            discard(store,previous)
            if store.path.name=='phone-authentication-actions.json' and not removed:
                removed.append(1);raise OSError('Synthetic lost host-retirement return')
        with patch.object(PrivateFeatureState,'discard',new=lost),self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.retirement_store.read())
        before=len(self.s.native.commands)
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertGreater(len(self.s.native.commands),before);self.assertIsNone(self.primary.store.read())

    def test_retained_native_probe_body_and_reopened_ui_prevent_final_retirement(self):
        self.ready_to_finalize();self.s.probe.pending=True
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.store.read())
        self.s.probe.pending=False;self.s.login.ui.dialog=True
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.store.read())

    def test_replaced_known_host_journal_is_never_deleted_by_a_retirement_plan(self):
        self.ready_to_finalize();self.s.probe.pending=True
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.s.probe.pending=False
        store=self.s.authentication_actions_store('selector');old=store.read();replacement={'foreign':True};store.write(replacement,old)
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertEqual(replacement,store.read())

    def test_entire_shared_journey_uses_both_original_readers_three_restarts_and_verified_retirement(self):
        from feature_journeys.engine import Journey
        from feature_journeys.phase_fixture import PhaseFixtureReader
        import test_feature_adapters as bound
        reports=[];f=self.registered_adapter()
        def invoke(operation,fields):return f.adapter.invoke(bound.SELECTOR,operation,fields)
        def witness():self.actor.publish();return self.s.client.observe()
        journey=Journey('authentication',RUN,URL+'/runs/'+RUN+'/',invoke=invoke,witness=witness,
            activate=self.s.client.activate,read_artifact=lambda _name:self.fail('Authentication requires original peer facts'),
            image_policy={},continuity=lambda *_args:None,monotonic=lambda:self.s.clock,epoch_ms=self.epoch,
            sleep=lambda value:setattr(self.s,'clock',self.s.clock+value),report=reports.append)
        # The public cleanup dispatcher reads the same nonce-bound Journal on
        # this fixture's synthetic clock. Keep its original phase validator;
        # no external HTTP transport belongs to this local-source composition.
        with (patch.dict(os.environ,dict(OVERTE_PHONE_FEATURE_AUTHENTICATION='1',OVERTE_PHONE_ACCOUNT_FIXTURE='1',
                    OVERTE_E2E_FEATURE_FIXTURE_URL=URL,**self.fixture_access_environment())),
              patch.object(f.adapter,'_authentication_feature',return_value=self.primary),
              patch.object(f.adapter,'_feature_fixture_client',return_value=self.s.client) as fixture_client,
              patch('overte_phone_feature_dispatch.PhaseFixtureReader',side_effect=lambda client,run,area:
                    PhaseFixtureReader(client,run,area,epoch_ms=self.epoch,monotonic=lambda:self.s.clock)),
              patch('feature_journeys.witness.Client.request',side_effect=AssertionError('Unexpected HTTP in synthetic Authentication fixture'))):
            journey.execute()
        self.assertGreater(fixture_client.call_count,0)
        self.assertIn(('primary','/runs/'+RUN+'/phase'),self.calls)
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
        self.assertEqual(17,len(reports[-1]['phases'])-2)
        self.assertEqual(['app.stop','app.launch']*3,self.s.inputs)
        self.s.client.close();self.assertEqual({'performed':True},self.primary.finalize())
        self.assertTrue(all(store.read() is None for store in self.primary._retirement_paths()))

    def fixture_access_environment(self):
        from adapters.normal_feature_state import PrivateFeatureState
        path=self.root/'adapter-fixture-access.json';store=PrivateFeatureState(path)
        if store.read() is None:store.write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=URL,adapterToken='d'*64),None)
        return dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(path))

    def registered_adapter(self):
        from test_account_fixture_launch import AccountFixtureLaunchTests
        setup=AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups)
        return setup.f

    def test_existing_adapter_entrypoint_advertises_only_with_explicit_bound_https_launch_and_reader_configuration(self):
        from feature_journeys.scenarios import VERSION
        import test_feature_adapters as bound
        f=self.registered_adapter()
        config=dict(OVERTE_PHONE_FEATURE_AUTHENTICATION='1',OVERTE_PHONE_ACCOUNT_FIXTURE='1',
            OVERTE_E2E_FEATURE_FIXTURE_URL=URL,**self.fixture_access_environment())
        with patch.dict(os.environ,config),patch.object(f.adapter,'_authentication_feature',return_value=self.primary) as factory:
            operations=f.adapter.advertised_capabilities(f.target)
            self.assertTrue(all('feature.authentication.'+kind in operations for kind in ('act','observe','cleanup')))
            actual=f.adapter.invoke(bound.SELECTOR,'feature.authentication.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
            self.assertEqual([],actual['resources']);factory.assert_called_once_with(bound.SELECTOR,RUN)
        with patch.dict(os.environ,{'OVERTE_PHONE_FEATURE_AUTHENTICATION':'0'}),patch.object(f.adapter,'_authentication_feature') as factory:
            with self.assertRaises(ValueError):f.adapter.invoke(bound.SELECTOR,'feature.authentication.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
            factory.assert_not_called()

    def test_missing_required_launch_reader_or_https_scope_is_never_advertised_as_complete(self):
        f=self.registered_adapter()
        good=dict(OVERTE_PHONE_FEATURE_AUTHENTICATION='1',OVERTE_PHONE_ACCOUNT_FIXTURE='1',
            OVERTE_E2E_FEATURE_FIXTURE_URL=URL,**self.fixture_access_environment())
        for edit in (dict(OVERTE_PHONE_FEATURE_AUTHENTICATION='yes'),dict(OVERTE_PHONE_ACCOUNT_FIXTURE='0'),
                     dict(OVERTE_E2E_FEATURE_FIXTURE_URL='http://owned.invalid/feature-fixture/v1'),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG='')):
            with self.subTest(edit=edit),patch.dict(os.environ,good|edit),self.assertRaises((ValueError,RuntimeError)):
                f.adapter.advertised_capabilities(f.target)

    def test_generic_cleanup_retires_verified_authentication_before_base_teardown_and_retains_unfinished_owner(self):
        import test_feature_adapters as bound
        f=self.registered_adapter();self.observe()
        with (patch.object(f.adapter,'state_path',return_value=self.s.path),
              patch.object(f.adapter,'_authentication_feature',return_value=self.primary),
              patch.object(bound.AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base):
            with self.assertRaisesRegex(ValueError,'PHONE_AUTHENTICATION_.*CLEANUP_INCOMPLETE'):f.adapter.cleanup(bound.SELECTOR)
            base.assert_called_once();self.assertIsNotNone(self.primary.store.read())
            self.observe(self.actor);self.cleanup();self.observe();self.observe(self.actor);self.s.client.close()
            base.reset_mock()
            self.assertEqual({'cleaned':True},f.adapter.cleanup(bound.SELECTOR));base.assert_called_once()
        self.assertIsNone(self.primary.store.read())

    def test_independent_registered_observer_worker_uses_actor_credential_and_own_sources_until_retired(self):
        import script_observer
        from types import SimpleNamespace
        from overte_phone_authentication_feature import PhoneAuthenticationFeature
        self.observe();self.observe(self.actor);self.cleanup();self.observe()
        def factory(selector,run,*,role,client):
            self.assertEqual('actor',role);self.assertEqual('y'*64,client.token)
            client.request=self.actor.source.client.request
            return PhoneAuthenticationFeature(self.s,selector,AuthenticationFixtureReader(client,run,epoch_ms=self.epoch),
                role='actor',monotonic=lambda:self.s.clock,sleep=lambda value:setattr(self.s,'clock',self.s.clock+value))
        adapter=SimpleNamespace(authentication_feature_store=lambda _selector:self.primary.store,
            authentication_retirement_store=lambda _selector:self.primary.retirement_store,_authentication_feature=factory)
        sleeps=[]
        def sleep(value):
            self.s.clock+=value;sleeps.append(value)
            if len(sleeps)==1:self.s.client.close()
        config=dict(area='authentication',target='selector',fixtureUrl=URL,actorToken='y'*64,durationSeconds=30)
        before=list(self.s.login.inputs)
        with patch.object(self.primary,'observe',side_effect=AssertionError('Unexpected primary observation')):
            self.assertEqual(0,script_observer.run(adapter,config,monotonic=lambda:self.s.clock,sleep=sleep))
        self.assertEqual(before,self.s.login.inputs);self.assertEqual('retired',self.actor.role_state()['phase'])

    def test_authentication_observer_configuration_is_versioned_private_https_and_cannot_inherit_reader_fields(self):
        import script_observer
        from adapters.normal_feature_state import PrivateFeatureState
        store=PrivateFeatureState(self.root/'observer.json')
        value=dict(featureObserverVersion=2,area='authentication',target='selector',candidateArguments=[],
            fixtureUrl=URL,actorToken='y'*64,durationSeconds=30)
        store.write(value,None);self.assertEqual(value,script_observer.configuration(store.path))
        for edit in (dict(featureObserverVersion=True),dict(area='assets'),dict(readerToken='x'*64),
                     dict(fixtureUrl='http://owned.invalid/feature-fixture/v1'),dict(scriptObserverVersion=1)):
            store.write(value|edit,store.read())
            with self.subTest(edit=edit),self.assertRaises((ValueError,RuntimeError)):script_observer.configuration(store.path)
        store.write(value,store.read());store.path.chmod(0o644)
        with self.assertRaises(NativeUIError):script_observer.configuration(store.path)

    def test_new_process_owner_can_finalize_from_archived_metadata_without_replaying_bootstrap_or_input(self):
        from overte_phone_authentication_feature import PhoneAuthenticationFeature
        self.ready_to_finalize()
        client=Client(URL,'x'*64);client.request=self.s.client.request
        flow=PhoneAuthenticationFeature(self.s,'selector',AuthenticationFixtureReader(client,RUN,epoch_ms=self.epoch),
            monotonic=lambda:self.s.clock,sleep=lambda value:setattr(self.s,'clock',self.s.clock+value))
        before=list(self.s.login.inputs)
        self.assertEqual({'performed':True},flow.finalize())
        self.assertEqual(before,self.s.login.inputs);self.assertIsNone(self.primary.store.read())

    def test_final_retirement_deadline_preserves_plan_before_deleting_any_host_journal(self):
        self.ready_to_finalize();send=self.s.origin.send
        def late(command):send(command);self.s.clock+=30
        self.s.origin.send=late
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.store.read());self.assertIsNotNone(self.s.authentication_actions_store('selector').read())
        self.assertIsNotNone(self.primary.retirement_store.read())

    def test_observer_wait_for_authentication_owner_has_a_deadline_and_no_native_query_or_session_bootstrap(self):
        import script_observer
        from types import SimpleNamespace
        adapter=SimpleNamespace(authentication_feature_store=lambda _selector:self.primary.store,
            authentication_retirement_store=lambda _selector:self.primary.retirement_store,
            _authentication_feature=lambda *_args,**_kwargs:self.fail('Unexpected observer bootstrap'))
        config=dict(area='authentication',target='selector',fixtureUrl=URL,actorToken='y'*64,durationSeconds=30)
        with self.assertRaises(NativeUIError):script_observer.run(adapter,config,monotonic=lambda:self.s.clock,
            sleep=lambda value:setattr(self.s,'clock',self.s.clock+value))
        self.assertEqual([],self.s.native.commands);self.assertEqual([],self.s.login.inputs)

    def test_replaced_prior_role_request_is_not_an_inspectable_native_registry_entry(self):
        import uuid
        self.ready_to_finalize();primary=self.primary.role_state()['last']['frame']['probe']
        self.assertNotEqual(primary['requestId'],self.s.probe.slot[2])
        with self.primary.lock.held(),self.s.existing_input_session('selector'):
            reader=self.s._account_probe('selector',read_only=True,role='primary').probe
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-account-probe',operation='inspect',
                requestId=primary['requestId'],runId=RUN,ticket=primary['ticket'])
            with self.assertRaises(NativeUIError):reader._perform(request)
        self.assertEqual({'performed':True},self.primary.finalize())


if __name__=='__main__':unittest.main()
