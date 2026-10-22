"""Real account authority allocations and protocol ownership; no client login."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_accounts import AvatarAccountScopes
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.avatar_social_provider import AvatarSocialProvider,REQUEST,DELETE
from self_tests.test_avatar_social_provider import NODES,DOMAIN,RUN,TICKET


class AvatarAccountTests(unittest.TestCase):
    def test_failed_second_unexposed_allocation_retires_only_actual_created_child(self):
        original=self.accounts.provision;allocated=[]
        def provision(child):
            if allocated:raise ValueError('Second authority allocation unavailable')
            original(child);allocated.append(child)
        other='f'*32
        with patch.object(self.accounts,'provision',side_effect=provision):
            with self.assertRaises(ValueError):self.scope.provision(other)
        self.assertNotIn(other,self.scope.runs);self.assertIn(other,self.scope.retired)
        self.assertEqual(1,len(allocated));self.assertFalse(self.accounts.snapshot(allocated[0])['accountExists'])
        self.assertEqual('allocated',self.scope.snapshot(RUN)['phase'])

    def setUp(self):
        self.epoch=1700000000000;self.accounts=AccountProvider(epoch_ms=lambda:self.epoch)
        self.social=AvatarSocialProvider(account_authenticator(self.accounts),epoch_ms=lambda:self.epoch)
        self.scope=AvatarAccountScopes(self.accounts,self.social);self.scope.provision(RUN);self.scope.activate(RUN,TICKET)
    def grant(self,role):
        credentials=self.scope.credentials(RUN,role)
        status,value=self.accounts.grant(urlencode(dict(grant_type='password',scope='owner',**credentials)).encode())
        self.assertEqual(200,status);return 'Bearer '+value['access_token']
    def request(self,role,auth,method='POST'):
        peer='actor' if role=='primary' else 'primary'
        raw=json.dumps(dict(user_connection_request=dict(node_id=NODES[role],proposed_node_id=NODES[peer]))).encode() if method=='POST' else b''
        path=REQUEST if method=='POST' else DELETE+self.scope.credentials(RUN,peer)['username']
        with self.social.response(method,path,'',raw,auth) as response:
            status,raw,response_id,written=response
            written(dict(status=status,responseId=response_id,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        return status

    def test_separate_owned_accounts_create_no_grant_or_relationship_until_actual_product_requests(self):
        status=self.scope.snapshot(RUN);self.assertEqual('allocated',status['phase']);self.assertIsNone(status['social'])
        self.assertNotEqual(status['accounts']['primary']['runId'],status['accounts']['actor']['runId'])
        for row in status['accounts'].values():self.assertEqual((0,0),(row['accessTokens'],row['refreshTokens']))
        self.assertNotEqual(self.scope.credentials(RUN,'primary')['username'],self.scope.credentials(RUN,'actor')['username'])
        self.scope.bind_sessions(RUN,NODES,DOMAIN)
        self.assertFalse(self.scope.snapshot(RUN)['social']['connected'])

    def test_actual_each_account_protected_profile_nonce_binds_its_original_child_scope(self):
        for role,nonce in (('primary','d'*32),('actor','e'*32)):
            auth=self.grant(role);child=self.scope.snapshot(RUN)['accounts'][role]['runId']
            self.assertEqual(200,self.accounts.profile(auth,run=child,ticket=TICKET,request=nonce)[0])
            proof=self.scope.profile_proof(RUN,role,TICKET,nonce)
            self.assertTrue(proof['protectedAccess']);self.assertEqual(child,proof['runId'])
            other='actor' if role=='primary' else 'primary'
            with self.assertRaises(ValueError):self.scope.profile_proof(RUN,other,TICKET,nonce)

    def test_connected_or_pending_social_resources_prevent_early_OAuth_revocation(self):
        self.scope.bind_sessions(RUN,NODES,DOMAIN);tokens={role:self.grant(role) for role in NODES}
        self.request('primary',tokens['primary'])
        with self.assertRaises(ValueError):self.scope.revoke(RUN)
        self.assertEqual('ready',self.scope.snapshot(RUN)['phase'])
        self.request('actor',tokens['actor'])
        with self.assertRaises(ValueError):self.scope.revoke(RUN)
        self.assertEqual(200,self.accounts.profile(tokens['primary'])[0])
        self.request('primary',tokens['primary'],method='DELETE')
        status=self.scope.revoke(RUN);self.assertEqual('revoking',status['phase'])
        for role in NODES:
            self.assertEqual(401,self.accounts.profile(tokens[role])[0])
            self.assertEqual((False,0,0),(status['accounts'][role]['accountExists'],status['accounts'][role]['accessTokens'],status['accounts'][role]['refreshTokens']))
        self.scope.retire(RUN)
        with self.assertRaises(ValueError):self.scope.provision(RUN)

    def test_original_inflight_account_handler_prevents_metadata_retirement_even_after_authority_revoked(self):
        child=self.scope.snapshot(RUN)['accounts']['primary']['runId']
        with self.accounts.transaction(run=child):
            self.scope.revoke(RUN)
            with self.assertRaises(ValueError):self.scope.retire(RUN)
            self.assertIn(RUN,self.scope.runs)
        self.scope.retire(RUN);self.assertNotIn(RUN,self.scope.runs)

    def test_foreign_provider_fake_authenticator_duplicate_or_rebound_sessions_cannot_replace_owner(self):
        with self.assertRaises(ValueError):AvatarAccountScopes(AccountProvider(),self.social)
        with self.assertRaises(ValueError):AvatarAccountScopes(self.accounts,AvatarSocialProvider(lambda _:None))
        with self.assertRaises(ValueError):self.scope.provision(RUN)
        with self.assertRaises(ValueError):self.scope.bind_sessions(RUN,dict(primary=NODES['primary'],actor=NODES['primary']),DOMAIN)
        self.scope.bind_sessions(RUN,NODES,DOMAIN)
        with self.assertRaises(ValueError):self.scope.bind_sessions(RUN,NODES,DOMAIN)
        self.scope.revoke(RUN)
        with self.assertRaises(ValueError):self.scope.credentials(RUN,'primary')


if __name__=='__main__':unittest.main()
