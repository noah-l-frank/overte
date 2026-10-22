"""Actual optional TLS fixture account routes and original authority drainage."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor
import json
import secrets
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from urllib.request import HTTPSHandler,ProxyHandler,build_opener

from self_tests import test_avatar_social_http as social_http_tests
from self_tests.test_avatar_social_provider import NODES,DOMAIN,TICKET
from feature_journeys.account_provider import AccountProvider,TOKEN_PATH,PROFILE_PATH,RUN_HEADER,TICKET_HEADER,REQUEST_HEADER
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.avatar_social_provider import AvatarSocialProvider,REQUEST,DELETE
from feature_journeys.server import make_server,Handler

PREFIX='/feature-fixture/v1'


class AvatarAccountHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):social_http_tests.SocialHTTPTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):social_http_tests.SocialHTTPTests.tearDownClass.__func__(cls)
    def setUp(self):
        self.epoch=1700000000000;self.account=AccountProvider(epoch_ms=lambda:self.epoch)
        self.social=AvatarSocialProvider(account_authenticator(self.account),epoch_ms=lambda:self.epoch)
        self.reader,self.actor,self.adapter=(secrets.token_hex(32) for _ in range(3))
        self.server=make_server(self.reader,self.actor,account_provider=self.account,avatar_social_provider=self.social,
            tls_context=self.server_context,adapter_token=self.adapter)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.stop)
        self.origin=f'https://localhost:{self.server.server_port}'
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=self.client_context))
        status,value=self.call(PREFIX+'/runs',body=dict(area='avatar-people'));self.assertEqual(200,status)
        self.run=value['runId'];self.base=PREFIX+'/runs/'+self.run
        self.assertEqual(200,self.call(self.base+'/active',body=dict(ticket=TICKET,verb='baseline',inputs={}))[0])
    def stop(self):
        self.account.shutdown();self.server.shutdown();self.thread.join(timeout=3);self.server.server_close()
    def request(self,*args,**kwargs):return social_http_tests.SocialHTTPTests.request(self,*args,**kwargs)
    def call(self,path,*,body=None,role='reader',method=None,headers=None):
        auth='Bearer '+dict(reader=self.reader,actor=self.actor,adapter=self.adapter)[role]
        return self.request(path,method=method or ('POST' if body is not None else 'GET'),
            raw=json.dumps(body).encode() if body is not None else None,content_type='application/json' if body is not None else None,
            auth=auth,headers=headers)
    def status(self):
        status,value=self.call(self.base+'/avatar/accounts');self.assertEqual(200,status);return value
    def credentials(self,role):
        status,value=self.call(self.base+'/avatar/credentials/'+role);self.assertEqual(200,status);return value
    def grant(self,role):
        credentials=self.credentials(role)
        status,value=self.request(TOKEN_PATH,method='POST',raw=urlencode(dict(grant_type='password',scope='owner',**credentials)).encode(),
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(200,status);return 'Bearer '+value['access_token']
    def profile(self,role,auth,nonce,*,ticket=TICKET):
        child=self.status()['accounts'][role]['runId']
        return self.request(PROFILE_PATH,auth=auth,headers={RUN_HEADER:child,TICKET_HEADER:ticket,REQUEST_HEADER:nonce})
    def bind(self):return self.call(self.base+'/avatar/sessions',body=dict(sessions=NODES,domain=DOMAIN))
    def consent(self,role,auth,method='POST'):
        peer='actor' if role=='primary' else 'primary'
        raw=json.dumps(dict(user_connection_request=dict(node_id=NODES[role],proposed_node_id=NODES[peer]))).encode() if method=='POST' else None
        path=REQUEST if method=='POST' else DELETE+self.credentials(peer)['username']
        return self.request(path,method=method,raw=raw,content_type='application/json' if raw else None,auth=auth)

    def test_each_actual_password_grant_and_profile_proof_is_separately_bound_and_not_exposed_as_input_credentials(self):
        before=self.status();self.assertEqual('allocated',before['phase']);self.assertIsNone(before['social'])
        self.assertNotEqual(before['accounts']['primary']['runId'],before['accounts']['actor']['runId'])
        for role,nonce in (('primary','ios-'+'d'*32),('actor','ios-'+'e'*32)):
            auth=self.grant(role);self.assertEqual(200,self.profile(role,auth,nonce)[0])
            path=self.base+'/avatar/proof/'+role+'/'+TICKET+'/'+nonce
            status,proof=self.call(path,role='actor');self.assertEqual(200,status);self.assertTrue(proof['protectedAccess'])
            self.assertEqual(before['accounts'][role]['runId'],proof['runId'])
            self.assertEqual(403,self.call(path)[0])
            for secret in (auth,self.credentials(role)['password']):self.assertNotIn(secret,json.dumps(proof))
        self.assertEqual(0,self.server.internal_errors)

    def test_private_get_roles_duplicate_session_binding_and_current_phase_activation(self):
        path=self.base+'/avatar/credentials/primary'
        self.assertEqual(200,self.call(path,role='adapter')[0]);self.assertEqual(403,self.call(path,role='actor')[0])
        for role in ('actor','adapter'):
            self.assertEqual(403,self.call(self.base+'/avatar/sessions',role=role,body=dict(sessions=NODES,domain=DOMAIN))[0])
            self.assertEqual(403,self.call(self.base+'/avatar/control',role=role,body=dict(operation='revoke'))[0])
        self.assertEqual(200,self.bind()[0]);self.assertEqual('ready',self.status()['phase'])
        self.assertEqual(400,self.bind()[0])
        self.assertEqual(200,self.call(self.base+'/active',body=dict(ticket='f'*32,verb='connection-request',inputs=dict(peer='owned-peer')))[0])
        status=self.status();self.assertEqual('f'*32,status['ticket']);self.assertEqual('f'*32,status['social']['ticket'])
        _,phase=self.call(self.base+'/phase',headers={'X-Overte-Phase-Read':'0'*32})
        self.assertEqual('f'*32,phase['activations'][-1]['ticket'])

    def test_actual_pending_connected_relationships_and_unrevoked_accounts_block_early_retirement(self):
        self.assertEqual(400,self.call(self.base,method='DELETE')[0]);self.assertEqual(200,self.bind()[0])
        tokens={role:self.grant(role) for role in NODES}
        self.assertEqual(200,self.consent('primary',tokens['primary'])[0])
        self.assertEqual(400,self.call(self.base+'/avatar/control',body=dict(operation='revoke'))[0])
        self.assertEqual('ready',self.status()['phase'])
        self.assertEqual(200,self.consent('actor',tokens['actor'])[0]);self.assertTrue(self.status()['social']['connected'])
        self.assertEqual(400,self.call(self.base+'/avatar/control',body=dict(operation='revoke'))[0])
        self.assertEqual(200,self.consent('primary',tokens['primary'],method='DELETE')[0])
        self.assertEqual(200,self.call(self.base+'/avatar/control',body=dict(operation='revoke'))[0])
        status=self.status();self.assertFalse(status['social']['active']);self.assertFalse(status['social']['connected'])
        for role in NODES:self.assertEqual((False,0,0),(status['accounts'][role]['accountExists'],status['accounts'][role]['accessTokens'],status['accounts'][role]['refreshTokens']))
        self.assertEqual(200,self.call(self.base,method='DELETE')[0])
        _,phase=self.call(self.base+'/phase',headers={'X-Overte-Phase-Read':'0'*32});self.assertFalse(phase['active'])

    def test_actual_delayed_profile_socket_write_remains_inflight_and_old_original_cannot_become_post_revoke_access(self):
        auth=self.grant('primary');child=self.status()['accounts']['primary']['runId'];entered=threading.Event();release=threading.Event()
        original_send=Handler.send
        def send(handler,*args,**kwargs):
            if handler.path==PROFILE_PATH:
                entered.set()
                if not release.wait(3):raise TimeoutError('Bounded synthetic response hold expired')
            return original_send(handler,*args,**kwargs)
        with ThreadPoolExecutor(max_workers=1) as pool,patch.object(Handler,'send',new=send):
            future=pool.submit(self.request,PROFILE_PATH,auth=auth,
                headers={RUN_HEADER:child,TICKET_HEADER:TICKET,REQUEST_HEADER:'a'*32})
            self.assertTrue(entered.wait(2));self.epoch+=100
            self.assertEqual(200,self.call(self.base+'/avatar/control',body=dict(operation='revoke'))[0])
            self.assertEqual(1,self.status()['accounts']['primary']['inflightRequests'])
            self.assertEqual(400,self.call(self.base,method='DELETE')[0])
            release.set();self.assertEqual(200,future.result(timeout=3)[0])
        with self.account.changed:
            self.assertTrue(self.account.changed.wait_for(lambda:self.account.snapshot(child)['inflightRequests']==0,timeout=2))
        status,proof=self.call(self.base+'/avatar/proof/primary/'+TICKET+'/'+'a'*32,role='actor')
        self.assertEqual(200,status);self.assertTrue(proof['protectedAccess']);self.assertLess(proof['capturedEpochMs'],self.epoch)
        # The account scope is now closed: a correlated probe is rejected as
        # an inactive scope, while the ordinary product bearer request is 401.
        self.assertEqual(400,self.profile('primary',auth,'b'*32)[0])
        self.assertEqual(401,self.request(PROFILE_PATH,auth=auth)[0])
        self.assertEqual(200,self.call(self.base,method='DELETE')[0])

    def test_legacy_http_fixture_without_optional_social_preserves_registration_and_never_exposes_social_credentials(self):
        server=make_server(secrets.token_hex(32),secrets.token_hex(32));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            from urllib.request import Request,urlopen
            # This is an intentionally credential-free plain legacy fixture.
            origin=f'http://127.0.0.1:{server.server_port}'
            request=Request(origin+PREFIX+'/runs',data=b'{"area":"avatar-people"}',method='POST',
                headers={'Authorization':'Bearer '+server.reader_token,'Content-Type':'application/json'})
            with urlopen(request,timeout=3) as response:self.assertEqual(200,response.code)
            self.assertIsNone(server.avatar_accounts);self.assertIsNone(server.avatar_social_provider)
        finally:server.shutdown();thread.join(timeout=3);server.server_close()


if __name__=='__main__':unittest.main()
