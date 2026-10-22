"""Actual loopback HTTPS/OAuth/People protocol; no device or simulated consent.

These tests send real HTTP requests from two owned principals. They establish
service behavior only; neither a native client nor rendered avatar is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import HTTPSHandler,ProxyHandler,build_opener
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys import witness
from feature_journeys.account_provider import AccountProvider,TOKEN_PATH
from feature_journeys.avatar_people_service import AvatarPeopleService,REQUEST,USERS,DELETE,validate_status
from feature_journeys.server import make_server
from self_tests import test_account_provider as account_tests

DOMAIN='11111111-1111-1111-1111-111111111111'
PRIMARY='22222222-2222-2222-2222-222222222222'
PEER='33333333-3333-3333-3333-333333333333'
TICKET='a'*32


class AvatarPeopleServiceTests(unittest.TestCase):
    setUpClass=classmethod(account_tests.AccountProviderTests.setUpClass.__func__)
    tearDownClass=classmethod(account_tests.AccountProviderTests.tearDownClass.__func__)
    request=account_tests.AccountProviderTests.request
    def setUp(self):
        self.epoch=20000;self.provider=AccountProvider(epoch_ms=lambda:self.epoch);self.social=AvatarPeopleService(self.provider,DOMAIN)
        self.reader,self.actor,self.adapter=(secrets.token_hex(32) for _ in range(3))
        self.server=make_server(self.reader,self.actor,adapter_token=self.adapter,account_provider=self.provider,tls_context=self.server_context,avatar_people_service=self.social)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.origin=f'https://localhost:{self.server.server_port}'
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=self.client_context),witness.NoRedirect())
        boundary=patch.object(witness,'build_opener',return_value=self.opener);boundary.start();self.addCleanup(boundary.stop)
        self.client=witness.Client(self.origin+'/feature-fixture/v1',self.reader)
        self.run,_=self.client.register('avatar-people');self.client.activate(TICKET)
        self.tokens={}
    def stop(self):
        self.provider.shutdown();self.server.shutdown();self.thread.join(timeout=3);self.server.server_close()
        self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)
    def endpoint(self,suffix):return '/feature-fixture/v1/runs/'+self.run+'/avatar-people'+suffix
    def grant(self,role):
        code,credentials=self.request(self.endpoint('/credentials/'+role),role='reader');self.assertEqual(200,code)
        code,value=self.request(TOKEN_PATH,body=dict(grant_type='password',scope='owner',**credentials),form_body=True)
        self.assertEqual(200,code);self.tokens[role]=value['access_token'];return value['access_token']
    def submit(self,role,*,method='POST',pair=None):
        if role not in self.tokens:self.grant(role)
        values=pair or dict(node_id=PRIMARY if role=='primary' else PEER,proposed_node_id=PEER if role=='primary' else PRIMARY)
        return self.request(REQUEST+('?' + urlencode(values) if method=='GET' else ''),method=method,
            body=dict(user_connection_request=values) if method=='POST' else None,headers={'Authorization':'Bearer '+self.tokens[role]})
    def connect(self):
        self.assertEqual('pending',self.submit('primary')[1]['connection'])
        self.assertEqual('success',self.submit('peer')[1]['status'])
        self.assertIsInstance(self.submit('primary',method='GET')[1]['connection'],dict)
    def test_actual_model_texture_and_missing_resource_responses_have_completed_wire_identity(self):
        from feature_journeys.fixtures import pinned_resource
        from urllib.request import Request
        expected={name:pinned_resource(name) for name in ('avatar-a.fst','mannequin/mannequin.fbx','mannequin/Eyes.png')}
        for name,raw in expected.items():
            with self.opener.open(Request(self.origin+'/feature-fixture/v1/runs/'+self.run+'/tickets/'+TICKET+'/'+name),timeout=3) as response:
                self.assertEqual(raw,response.read());identity=response.headers['X-Overte-Fixture-Response']
            source=self.client.avatar_people_status();original=source['responses'][-1]
            self.assertEqual(identity,original['responseId']);self.assertEqual('resource',original['role'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),original['sha256']);self.assertEqual(len(raw),original['bytes'])
        code,value=self.request('/feature-fixture/v1/runs/'+self.run+'/tickets/'+TICKET+'/missing.fst')
        self.assertEqual(404,code);self.assertEqual('not-found',value['error'])
        self.assertEqual(404,self.client.avatar_people_status()['responses'][-1]['status'])

    def test_original_people_pager_metadata_matches_the_actual_qml_consumer(self):
        self.connect()
        code,value=self.request('/api/v1/users/connections?per_page=1000&page=1',headers={'Authorization':'Bearer '+self.tokens['primary']})
        self.assertEqual(200,code);self.assertEqual(1,value['total_pages']);self.assertEqual(1,value['current_page']);self.assertEqual(1,value['total_entries'])
        self.assertEqual({'users'},set(value['data']));self.assertEqual(1,len(value['data']['users']))

    def test_delete_before_first_original_post_is_bounded_and_preserves_unbound_scope(self):
        token=self.grant('primary');peer_name=self.social.credentials(self.run,'peer')['username']
        status,value=self.request(DELETE+peer_name,method='DELETE',headers={'Authorization':'Bearer '+token})
        self.assertEqual(409,status);self.assertEqual('session-unbound',value['error'])
        original=self.client.avatar_people_status();self.assertIsNone(original['binding']);self.assertFalse(any(original['relationships'].values()))
        self.assertEqual(409,original['responses'][-1]['status'])

    def test_two_distinct_actual_authenticated_reciprocal_posts_and_completed_wire_receipts(self):
        self.connect();status=self.client.avatar_people_status()
        self.assertEqual(dict(domainId=DOMAIN,primarySession=PRIMARY,peerSession=PEER),status['binding'])
        self.assertEqual(['primary','peer','primary'],[row['role'] for row in status['responses']])
        self.assertEqual(['POST','POST','GET'],[row['method'] for row in status['responses']])
        self.assertNotEqual(self.tokens['primary'],self.tokens['peer'])
        for role in ('primary','peer'):
            code,result=self.request(USERS[0]+'?filter=connections&per_page=400',headers={'Authorization':'Bearer '+self.tokens[role]})
            self.assertEqual(200,code);self.assertEqual(1,len(result['data']['users']))
            self.assertEqual(status['relationships'][role][0],result['data']['users'][0]['username'])
        old=deepcopy(status['responses']);self.epoch+=100
        self.assertEqual(old,self.client.avatar_people_status()['responses'][:len(old)])
    def test_one_principal_polls_cannot_create_mutual_relationship_or_impersonate_peer(self):
        self.submit('primary')
        for _ in range(3):self.assertEqual('pending',self.submit('primary',method='GET')[1]['connection'])
        self.assertEqual(403,self.submit('primary',pair=dict(node_id=PEER,proposed_node_id=PRIMARY))[0])
        status=self.client.avatar_people_status();self.assertEqual({'primary':[],'peer':[]},status['relationships'])
        self.assertEqual({'primary'},set(status['pending']))
    def test_delayed_reciprocal_from_a_new_challenge_cannot_complete_old_request(self):
        self.submit('primary');self.client.activate('b'*32,'connection-request',{'peer':'owned-peer'})
        self.assertEqual('pending',self.submit('peer')[1]['connection'])
        self.assertEqual('pending',self.submit('primary',method='GET')[1]['connection'])
        self.assertFalse(any(self.client.avatar_people_status()['relationships'].values()))
        self.epoch+=12001;self.assertEqual({},self.client.avatar_people_status()['pending'])
    def test_real_delete_refreshes_both_principals_and_authority_cleanup_is_verified(self):
        self.connect();status=self.client.avatar_people_status();peer_name=status['relationships']['primary'][0]
        with self.assertRaises(ValueError):self.social.cleanup_accounts(self.run)
        code,_=self.request(DELETE+'unowned',method='DELETE',headers={'Authorization':'Bearer '+self.tokens['primary']});self.assertEqual(403,code)
        self.assertTrue(self.client.avatar_people_status()['relationships']['primary'])
        code,value=self.request(DELETE+peer_name,method='DELETE',headers={'Authorization':'Bearer '+self.tokens['primary']});self.assertEqual(200,code)
        for role in ('primary','peer'):
            code,value=self.request(USERS[1]+'?page=1&per_page=1000&sort=username,ASC',headers={'Authorization':'Bearer '+self.tokens[role]})
            self.assertEqual(200,code);self.assertEqual([],value['data']['users'])
        self.client.close();self.client.close();retired=self.client.avatar_people_status()
        self.assertFalse(retired['active']);self.assertEqual({},retired['pending']);self.assertFalse(any(retired['relationships'].values()))
        for role in ('primary','peer'):
            self.assertEqual(401,self.request(USERS[0],headers={'Authorization':'Bearer '+self.tokens[role]})[0])
    def test_credential_roles_are_separate_and_adapter_cannot_control_relationships_or_peer(self):
        for token,role,expected in ((self.actor,'primary',403),(self.actor,'peer',200),(self.adapter,'primary',200),(self.adapter,'peer',403)):
            self.assertEqual(expected,self.request(self.endpoint('/credentials/'+role),headers={'Authorization':'Bearer '+token})[0])
        for token in (self.reader,self.actor,self.adapter):
            self.assertEqual(401 if token!=self.adapter else 403,self.request(REQUEST,method='POST',body=dict(user_connection_request=dict(node_id=PRIMARY,proposed_node_id=PEER)),headers={'Authorization':'Bearer '+token})[0])
        self.assertFalse(any(self.client.avatar_people_status()['relationships'].values()))
    def test_generic_auth_routes_cannot_bypass_primary_peer_credential_separation(self):
        scopes=self.social.runs[self.run]['accounts']
        for auth_run in scopes.values():
            self.assertTrue(self.social.owns_account(auth_run))
            for token in (self.adapter,self.actor):
                for suffix in ('credentials/owned','credentials/rejected','status'):
                    with self.subTest(role='distinct fixture credential',suffix=suffix):
                        path='/feature-fixture/v1/runs/'+auth_run+'/account/'+suffix
                        self.assertEqual(403,self.request(path,headers={'Authorization':'Bearer '+token})[0])
        # The separately authorized fixture controller can still retire both.
        self.client.close();self.assertTrue(all(self.social.owns_account(auth) for auth in scopes.values()))

    def test_original_history_replay_drop_rewrite_and_wrong_request_cannot_validate(self):
        self.submit('primary');first=self.client.avatar_people_status();self.submit('peer');second=self.client.avatar_people_status()
        for changed in (second|dict(requestId=first['requestId']),second|dict(responses=[]),second|dict(avatarPeopleServiceVersion=True)):
            with self.subTest(keys=list(changed)),self.assertRaises(ValueError):validate_status(changed,run=self.run,request=changed['requestId'],instance=self.social.instance,previous=first)
        changed=deepcopy(second);changed['responses'][0]['sha256']='f'*64
        with self.assertRaises(ValueError):validate_status(changed,run=self.run,request=changed['requestId'],instance=self.social.instance,previous=first)
    def test_failed_wire_delivery_is_retained_and_cannot_become_clean_retirement(self):
        token=self.grant('primary')
        with self.social.response('Bearer '+token,'POST',REQUEST,{},dict(user_connection_request=dict(node_id=PRIMARY,proposed_node_id=PEER))) as response:
            self.assertEqual(200,response[0]) # Deliberately omit actual completed body write.
        failed=self.client.avatar_people_status();self.assertEqual(1,failed['failedResponses']);self.assertEqual([],failed['responses'])
        self.assertEqual(1,self.social.snapshot(self.run,secrets.token_hex(16))['failedResponses'])
        with self.assertRaises(ValueError):self.social.retire(self.run)
    def test_social_service_is_default_off_and_requires_same_trusted_account_owner(self):
        with self.assertRaises(ValueError):make_server('r'*64,'a'*64,avatar_people_service=self.social)
        with self.assertRaises(ValueError):make_server('r'*64,'a'*64,account_provider=AccountProvider(),tls_context=self.server_context,avatar_people_service=self.social)
        # This original listener remains HTTPS but removes its explicit social capability.
        self.server.avatar_people_service=None
        other=witness.Client(self.origin+'/feature-fixture/v1',self.reader)
        with self.assertRaises(ValueError):other.register('avatar-people')
        self.assertEqual(404,self.request(REQUEST,method='POST',body={},headers={'Authorization':'Bearer '+self.reader})[0])


if __name__=='__main__':unittest.main()
