"""Real loopback HTTPS/OAuth fixture checks; no native client or device run.

OpenSSL generates a temporary test certificate only. It is trusted solely by
this test's Python client context and never installed in any trust store.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,HTTPSHandler,ProxyHandler,build_opener
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys import witness
from feature_journeys.account_provider import AccountProvider,TOKEN_PATH,PROFILE_PATH,REQUEST_HEADER,RUN_HEADER,TICKET_HEADER
from feature_journeys.server import make_server,read_account_body

PREFIX='/feature-fixture/v1'
TICKET='b'*32


class AccountProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.path=Path(cls.temporary.name);os.chmod(cls.path,0o700)
        cls.key,cls.cert=cls.path/'ephemeral.key',cls.path/'ephemeral.crt'
        result=subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-sha256','-days','1','-nodes',
            '-subj','/CN=localhost','-addext','subjectAltName=DNS:localhost,IP:127.0.0.1',
            '-keyout',str(cls.key),'-out',str(cls.cert)],capture_output=True,timeout=10)
        if result.returncode:raise RuntimeError('Ephemeral HTTPS test material could not be generated')
        os.chmod(cls.key,0o600);os.chmod(cls.cert,0o600)
        cls.server_context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        cls.server_context.minimum_version=ssl.TLSVersion.TLSv1_2
        cls.server_context.load_cert_chain(cls.cert,cls.key)
        cls.client_context=ssl.create_default_context(cafile=str(cls.cert))
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def setUp(self):
        self.epoch=20000;self.clock=0.
        self.provider=AccountProvider(epoch_ms=lambda:self.epoch)
        self.reader,self.actor=secrets.token_hex(32),secrets.token_hex(32)
        self.server=make_server(self.reader,self.actor,account_provider=self.provider,tls_context=self.server_context)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
        self.origin=f'https://localhost:{self.server.server_port}'
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=self.client_context),witness.NoRedirect())
        boundary=patch.object(witness,'build_opener',return_value=self.opener);boundary.start();self.addCleanup(boundary.stop)
        def sleep(value):self.clock+=value
        self.client=witness.Client(self.origin+PREFIX,self.reader,monotonic=lambda:self.clock,sleep=sleep)
        self.run,_=self.client.register('authentication');self.client.activate(TICKET)
    def stop(self):
        self.provider.shutdown();self.server.shutdown();self.thread.join(timeout=3);self.server.server_close()

    def request(self,path,*,body=None,method=None,role=None,headers=None,form_body=False):
        metadata={} if headers is None else dict(headers)
        if role:metadata['Authorization']='Bearer '+(self.reader if role=='reader' else self.actor)
        raw=None
        if body is not None:
            raw=(urlencode(body).encode() if form_body else json.dumps(body).encode()) if type(body) is dict else body
            metadata['Content-Type']='application/x-www-form-urlencoded' if form_body else 'application/json'
        request=Request(self.origin+path,data=raw,method=method,headers=metadata)
        try:response=self.opener.open(request,timeout=3)
        except HTTPError as error:response=error
        with response:
            self.last_raw=response.read(4097)
            return response.code,json.loads(self.last_raw)

    def grant(self,role='owned'):
        credentials=self.client.account_credentials(role)
        return self.request(TOKEN_PATH,body=dict(grant_type='password',scope='owner',**credentials),form_body=True)

    def profile(self,token='',*,run=None,ticket=TICKET,nonce=None):
        nonce=nonce or secrets.token_hex(16);run=run or self.run
        headers={RUN_HEADER:run,TICKET_HEADER:ticket,REQUEST_HEADER:nonce}
        if token:headers['Authorization']='Bearer '+token
        status,value=self.request(PROFILE_PATH,headers=headers)
        return nonce,status,value

    def test_actual_password_grant_and_bearer_profile_make_distinct_original_proof(self):
        status,token=self.grant();self.assertEqual(200,status)
        self.assertEqual({'access_token','refresh_token','token_type','expires_in'},set(token))
        nonce,status,value=self.profile(token['access_token']);self.assertEqual(200,status)
        self.assertEqual('e2e-'+self.run,value['data']['user']['username'])
        code,proof=self.request(PREFIX+f'/runs/{self.run}/account/proof/{TICKET}/{nonce}',role='actor')
        self.assertEqual(200,code);self.assertTrue(proof['protectedAccess']);self.assertEqual('owned',proof['principal'])
        self.epoch+=1000
        self.assertEqual(proof,self.provider.proof(self.run,TICKET,nonce)) # No retiming on another read.
        self.assertEqual(0,self.server.internal_errors)

    def test_original_https_profile_proof_joins_an_explicit_native_boundary_without_clock_equivalence(self):
        # The HTTPS provider is real; native response transport is an explicit
        # synthetic boundary here, not a native/client qualification result.
        import hashlib
        from adapters.native_account_probe import validate,protected_proof
        _,token=self.grant();nonce,status,_=self.profile(token['access_token']);raw=self.last_raw
        source=dict(httpStatus=status,networkError=0,parsed=True,principalSha256=hashlib.sha256(('e2e-'+self.run).encode()).hexdigest(),
            responseSha256=hashlib.sha256(raw).hexdigest(),responseBytes=len(raw),tokenAttached=True,
            credentialGeneration=2,endpointSha256=hashlib.sha256(self.origin.encode()).hexdigest(),sentEpochMs=9000000,completedEpochMs=9000001)
        native=dict(probeVersion=1,commandId=nonce,requestId=nonce,runId=self.run,ticket=TICKET,operation='read',
            instance='e'*32,sequence=1,processId=123,requestedEpochMs=9000000,capturedEpochMs=9000002,source=source)
        request={key:native[key] for key in ('commandId','requestId','runId','ticket','operation')}
        request.update(schemaVersion=1,action='feature-account-probe');validate(native,request,123,9000002)
        proof=self.provider.proof(self.run,TICKET,nonce)
        self.assertEqual(dict(principal='owned',protectedAccess=True),protected_proof(native,proof,
            provider_instance=self.provider.instance,username='e2e-'+self.run))
        self.assertNotEqual(native['capturedEpochMs'],proof['capturedEpochMs'])

    def test_bad_password_and_unknown_account_cannot_allocate_a_session(self):
        self.assertEqual(400,self.grant('invalid')[0])
        status,_=self.request(TOKEN_PATH,body=dict(grant_type='password',scope='owner',username='unknown',password='wrong'),form_body=True)
        self.assertEqual(400,status)
        self.assertEqual(0,self.client.account_status()['accessTokens'])
        nonce,status,_=self.profile();self.assertEqual(401,status)
        self.assertFalse(self.provider.proof(self.run,TICKET,nonce)['protectedAccess'])

    def test_grant_receipt_without_an_actual_profile_request_is_no_function_success(self):
        self.assertEqual(200,self.grant()[0])
        with self.assertRaises(ValueError):self.provider.proof(self.run,TICKET,'c'*32)

    def test_credential_collision_cannot_overwrite_an_existing_authority(self):
        _,token=self.grant()
        with patch('feature_journeys.account_provider.secrets.token_urlsafe',return_value=token['access_token']):
            self.assertEqual(503,self.grant()[0])
        self.assertEqual(1,self.client.account_status()['accessTokens'])
        self.assertEqual(200,self.profile(token['access_token'])[1])
        with self.assertRaises(ValueError):make_server(self.reader,self.actor,account_provider=self.provider,tls_context=self.server_context)

    def test_actual_foreign_token_cannot_become_another_runs_owned_principal(self):
        _,token=self.grant();other=witness.Client(self.origin+PREFIX,self.reader)
        run,_=other.register('authentication');other.activate(TICKET)
        nonce,status,_=self.profile(token['access_token'],run=run)
        self.assertEqual(401,status);self.assertEqual('anonymous',self.provider.proof(run,TICKET,nonce)['principal'])
        other.close()

    def test_previous_or_reused_nonce_and_retired_ticket_never_count_as_a_new_observation(self):
        _,token=self.grant();nonce,status,_=self.profile(token['access_token']);self.assertEqual(200,status)
        self.assertEqual(400,self.profile(token['access_token'],nonce=nonce)[1])
        self.client.activate('d'*32)
        with self.assertRaises(ValueError):self.provider.proof(self.run,TICKET,nonce)
        self.assertEqual(400,self.profile(token['access_token'],ticket=TICKET)[1])

    def test_expired_access_is_rejected_and_real_refresh_grant_issues_new_credentials(self):
        _,token=self.grant();self.epoch+=3600001
        self.assertEqual(401,self.profile(token['access_token'])[1])
        status,refreshed=self.request(TOKEN_PATH,body=dict(grant_type='refresh_token',scope='owner',
            refresh_token=token['refresh_token']),form_body=True)
        self.assertEqual(200,status);self.assertTrue(refreshed['access_token']!=token['access_token'],'Access token must rotate')
        self.assertEqual(200,self.profile(refreshed['access_token'])[1])

    def test_closed_journey_stimuli_hold_release_and_revoke_actual_requests(self):
        self.client.activate('d'*32,'login-submit',{'account':'delayed'})
        self.assertTrue(self.client.account_status()['armedHold'])
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.grant,'delayed')
            with self.provider.changed:
                self.assertTrue(self.provider.changed.wait_for(lambda:self.provider.snapshot(self.run)['heldRequests']==1,timeout=2))
            self.client.activate('e'*32,'release-stale-response');status,token=future.result(timeout=3)
        self.assertEqual(200,status);self.assertTrue(self.provider.delayed_status(self.run)['delayedGrantOutstanding'])
        self.client.activate('f'*32,'cleanup')
        self.assertFalse(self.provider.delayed_status(self.run)['delayedGrantOutstanding'])
        self.assertFalse(self.client.account_status()['grantsEnabled']);self.assertEqual(401,self.profile(token['access_token'],ticket='f'*32)[1])

    def test_duplicate_or_nonfinite_json_controls_are_rejected_without_mutating_authority(self):
        path=PREFIX+f'/runs/{self.run}/account/control'
        for raw in (b'{"operation":"hold-next","operation":"cleanup"}',b'{"operation":NaN}'):
            self.assertEqual(400,self.request(path,body=raw,role="reader")[0])
        self.assertTrue(self.client.account_status()['accountExists']);self.assertFalse(self.client.account_status()['armedHold'])

    def test_public_delayed_metadata_proves_actual_issued_authority_and_preserves_original_times(self):
        from adapters.account_fixture_observation import DelayedGrantObservation
        observation=DelayedGrantObservation(self.run,self.provider.instance)
        path=PREFIX+f'/runs/{self.run}/account/delayed'
        status,value=self.request(path);self.assertEqual(200,status);self.assertFalse(observation.accept(value))
        self.assertEqual(90,self.provider.hold_seconds);self.client.account_control('hold-next')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.grant,'delayed')
            with self.provider.changed:
                self.assertTrue(self.provider.changed.wait_for(lambda:self.provider.snapshot(self.run)['heldRequests']==1,timeout=2))
            _,held=self.request(path);self.assertFalse(observation.accept(held));self.assertEqual('held',held['requests'][0]['state'])
            self.client.activate('d'*32);self.client.account_control('release-delayed');status,token=future.result(timeout=3)
        self.assertEqual(200,status);_,issued=self.request(path);self.assertTrue(observation.accept(issued))
        self.assertEqual(TICKET,issued['requests'][0]['requestTicket']);self.assertEqual(200,issued['requests'][0]['status'])
        self.assertEqual(200,self.profile(token['access_token'],ticket='d'*32)[1])
        self.epoch+=1000;_,later=self.request(path);self.assertTrue(observation.accept(later))
        self.assertEqual(issued['requests'][0],later['requests'][0])
        for secret in (token['access_token'],token['refresh_token'],self.client.account_credentials('owned')['password']):
            self.assertNotIn(secret,json.dumps(later))
        self.client.account_control('revoke-issued');_,revoked=self.request(path)
        self.assertFalse(observation.accept(revoked));self.assertFalse(revoked['grantsEnabled'])
        self.assertEqual(401,self.profile(token['access_token'],ticket='d'*32)[1])

    def test_revocation_drains_a_real_held_grant_and_blocks_late_issuance_without_retiring_profile_scope(self):
        credentials=self.client.account_credentials('owned');self.client.account_control('hold-next')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.grant,'delayed')
            with self.provider.changed:
                self.assertTrue(self.provider.changed.wait_for(lambda:self.provider.snapshot(self.run)['heldRequests']==1,timeout=2))
            self.client.account_control('revoke-issued');self.assertEqual(503,future.result(timeout=3)[0])
        self.assertEqual(0,self.client.account_status()['accessTokens']);self.assertTrue(self.client.account_status()['accountExists'])
        self.assertFalse(self.client.account_status()['grantsEnabled']);self.assertEqual(401,self.profile()[1])
        status,_=self.request(TOKEN_PATH,body=dict(grant_type='password',scope='owner',**credentials),form_body=True)
        self.assertEqual(503,status);self.assertFalse(self.provider.delayed_status(self.run)['delayedGrantOutstanding'])

    def test_expired_or_unreleased_delayed_request_cannot_look_like_valid_old_success(self):
        from adapters.account_fixture_observation import DelayedGrantObservation
        self.provider.hold_seconds=.03;self.client.account_control('hold-next')
        self.assertEqual(503,self.grant('delayed')[0]);value=self.provider.delayed_status(self.run)
        self.assertEqual('expired',value['requests'][0]['state'])
        self.assertFalse(DelayedGrantObservation(self.run,self.provider.instance).accept(value))

    def test_delayed_observation_refuses_forged_foreign_dropped_or_rewritten_original_facts(self):
        from adapters.account_fixture_observation import DelayedGrantObservation
        from copy import deepcopy
        self.client.account_control('hold-next')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.grant,'delayed')
            with self.provider.changed:
                self.assertTrue(self.provider.changed.wait_for(lambda:self.provider.snapshot(self.run)['heldRequests']==1,timeout=2))
            original=self.provider.delayed_status(self.run)
            for edit in ({'providerVersion':1},{'instance':'e'*32},{'delayedGrantOutstanding':True},{'grantsEnabled':1}):
                with self.assertRaises(RuntimeError):DelayedGrantObservation(self.run,self.provider.instance).accept(original|edit)
            observer=DelayedGrantObservation(self.run,self.provider.instance);observer.accept(original)
            for edit in ({'requests':[]},{'capturedEpochMs':19999}):
                with self.assertRaises(RuntimeError):observer.accept(original|edit)
            rewritten=deepcopy(original);rewritten['requests'][0]['requestTicket']='e'*32
            with self.assertRaises(RuntimeError):observer.accept(rewritten)
            self.client.account_control('release-delayed');future.result(timeout=3)

    def test_delayed_grant_is_an_actual_waiting_request_until_explicit_release(self):
        self.client.account_control('hold-next')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.grant,'delayed')
            with self.provider.changed:
                self.assertTrue(self.provider.changed.wait_for(lambda:self.provider.snapshot(self.run)['heldRequests']==1,timeout=2))
            state=self.client.account_status();self.assertEqual(1,state['heldRequests']);self.assertEqual(1,state['inflightRequests'])
            self.assertEqual(0,state['accessTokens']);self.assertFalse(future.done())
            self.client.account_control('release-delayed');status,token=future.result(timeout=3)
            self.assertEqual(200,status);self.assertEqual(200,self.profile(token['access_token'])[1])
        self.assertEqual(0,self.client.account_status()['heldRequests'])

    def test_cleanup_releases_pending_handlers_without_issuing_late_valid_tokens(self):
        self.client.account_control('hold-next')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.grant,'delayed')
            with self.provider.changed:
                self.assertTrue(self.provider.changed.wait_for(lambda:self.provider.snapshot(self.run)['heldRequests']==1,timeout=2))
            self.client.account_control('cleanup');self.assertEqual(503,future.result(timeout=3)[0])
        self.assertEqual(0,self.client.account_status()['inflightRequests'])
        self.client.close();status=self.provider.snapshot(self.run)
        self.assertFalse(status['accountExists']);self.assertEqual(0,status['accessTokens'])
        with self.assertRaises(ValueError):self.provider.provision(self.run)

    def test_unknown_delayed_release_or_duplicate_hold_cannot_fake_a_release(self):
        with self.assertRaises(ValueError):self.client.account_control('release-delayed')
        self.client.account_control('hold-next')
        with self.assertRaises(ValueError):self.client.account_control('hold-next')

    def test_unreleased_grant_expires_with_no_token_and_no_owned_handler_left(self):
        self.provider.hold_seconds=.03;self.client.account_control('hold-next')
        self.assertEqual(503,self.grant('delayed')[0])
        status=self.client.account_status()
        self.assertEqual(0,status['heldRequests']);self.assertEqual(0,status['inflightRequests']);self.assertEqual(0,status['accessTokens'])

    def test_still_executing_response_cannot_be_hidden_by_an_empty_token_inventory(self):
        with self.provider.transaction(run=self.run):
            with self.assertRaises(ValueError):self.client.close()
            self.assertFalse(self.client.closed)
            self.assertEqual(1,self.client.account_status()['inflightRequests'])
            with self.assertRaises(ValueError):self.provider.retire(self.run)
        self.client.close();self.assertTrue(self.client.closed)

    def test_cleanup_budget_includes_mutation_and_recovery_keeps_original_context(self):
        original=self.client.request
        def delayed(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if path.endswith('/account/control'):self.clock+=5.01
            return value
        with patch.object(self.client,'request',side_effect=delayed):
            with self.assertRaises(ValueError):self.client.close()
        self.assertFalse(self.client.closed);self.client.close();self.assertTrue(self.client.closed)

    def test_lost_final_close_time_proof_recovers_only_from_original_retired_scope(self):
        original=self.client.request
        def delayed(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if kwargs.get('method')=='DELETE':self.clock+=5.01
            return value
        with patch.object(self.client,'request',side_effect=delayed):
            with self.assertRaises(ValueError):self.client.close()
        self.assertFalse(self.client.closed);self.assertNotIn(self.run,self.provider.runs)
        self.client.close();self.assertTrue(self.client.closed)

    def test_malformed_duplicate_or_expected_fields_are_rejected_before_any_token(self):
        credentials=self.client.account_credentials('owned')
        body=urlencode(dict(grant_type='password',scope='owner',**credentials)).encode()
        for raw in (body+b'&scope=owner',body+b'&expected=owned',body+b'&bad=%ZZ',body+b'x'*4097):
            status,_=self.request(TOKEN_PATH,body=raw,form_body=True);self.assertEqual(400,status)
        self.assertEqual(0,self.client.account_status()['accessTokens'])

    def test_actively_trickled_credentials_have_one_absolute_body_deadline(self):
        class Trickle:
            clock=0.
            def read1(self,_size):self.clock+=.8;return b'x'
            def settimeout(self,value):self.timeout=value
        source=Trickle()
        with self.assertRaises(ValueError):read_account_body(source,source,3,monotonic=lambda:source.clock)
        self.assertEqual(2,source.timeout)
        source.clock=10.
        def backwards(_size):source.clock=9.;return b'x'
        source.read1=backwards
        with self.assertRaises(ValueError):read_account_body(source,source,1,monotonic=lambda:source.clock)

    def test_reader_cannot_publish_proof_and_actor_cannot_fetch_passwords_or_mutate_service(self):
        self.assertEqual(403,self.request(PREFIX+f'/runs/{self.run}/account/credentials/owned',role='actor')[0])
        self.assertEqual(403,self.request(PREFIX+f'/runs/{self.run}/account/proof/{TICKET}/'+('c'*32),role='reader')[0])
        self.assertEqual(403,self.request(PREFIX+f'/runs/{self.run}/account/control',body={'operation':'cleanup'},role='actor')[0])
        self.assertEqual(400,self.request(PREFIX+f'/runs/{self.run}/account/control',
            body={'operation':'cleanup','expected':True},role='reader')[0])
        self.assertTrue(self.client.account_status()['accountExists'])

    def test_noop_cleanup_ack_is_not_empty_authority_and_preserves_client_ownership(self):
        self.grant();original=self.provider.control
        def noop(run,operation):
            if operation!='cleanup':return original(run,operation)
        with patch.object(self.provider,'control',side_effect=noop):
            with self.assertRaises(ValueError):self.client.close()
        self.assertFalse(self.client.closed);self.assertTrue(self.client.account_status()['accountExists'])
        self.client.close();self.assertTrue(self.client.closed)

    def test_provider_replacement_and_numeric_snapshot_flags_refuse_cleanup(self):
        original=self.provider.snapshot
        for edit in ({'instance':'c'*32},{'accountExists':0},{'inflightRequests':True}):
            with patch.object(self.provider,'snapshot',side_effect=lambda run:original(run)|edit):
                with self.assertRaises(ValueError):self.client.account_status()

    def test_credentials_never_appear_in_proof_inventory_or_public_journal(self):
        credentials=self.client.account_credentials('owned');_,token=self.grant();nonce,_,_=self.profile(token['access_token'])
        data=json.dumps([self.provider.proof(self.run,TICKET,nonce),self.client.account_status(),self.client.observe()])
        for secret in (credentials['password'],token['access_token'],token['refresh_token']):
            self.assertTrue(secret not in data,'Provider diagnostics exposed credential material')

    def test_tls_trust_and_hostname_validation_remain_enabled(self):
        untrusted=build_opener(ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context()))
        with self.assertRaises(URLError):untrusted.open(self.origin+PREFIX+'/account-provider',timeout=3)
        with socket.create_connection(('127.0.0.1',self.server.server_port),timeout=3) as raw:
            with self.assertRaises(ssl.SSLCertVerificationError):self.client_context.wrap_socket(raw,server_hostname='wrong.invalid')
        self.assertEqual(0,self.client.account_status()['accessTokens'])

    def test_http_and_missing_provider_cannot_register_an_authentication_run(self):
        with self.assertRaises(ValueError):make_server(self.reader,self.actor,account_provider=AccountProvider())
        client=witness.Client('http://127.0.0.1:1'+PREFIX,self.reader)
        with self.assertRaises(ValueError):client.register('authentication') # No socket or credentials on HTTP.
        server=make_server(self.reader,self.actor,tls_context=self.server_context)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            missing=witness.Client(f'https://localhost:{server.server_port}'+PREFIX,self.reader)
            with self.assertRaises(ValueError):missing.register('authentication')
            self.assertEqual({},server.journal.runs)
        finally:server.shutdown();thread.join(timeout=3);server.server_close()

    def test_cleanup_removes_real_token_access_before_retiring_run_and_is_idempotent(self):
        _,token=self.grant();self.client.close();self.client.close()
        status,_=self.request(PROFILE_PATH,headers={'Authorization':'Bearer '+token['access_token']})
        self.assertEqual(401,status);self.assertNotIn(self.run,self.provider.runs)
        self.assertFalse(self.provider.snapshot(self.run)['accountExists'])
