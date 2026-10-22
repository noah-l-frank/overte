"""Actual loopback TLS/OAuth/social traffic; no native peer qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import secrets
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, HTTPSHandler, ProxyHandler, build_opener

from self_tests import test_account_provider as account_tests
from feature_journeys.account_provider import AccountProvider, TOKEN_PATH
from feature_journeys.avatar_social_http import AccountAuthenticator, account_authenticator
from feature_journeys.avatar_social_provider import AvatarSocialProvider, REQUEST, USERS, CONNECTIONS, DELETE
from feature_journeys.server import make_server

RUN, ACTOR, TICKET = 'a'*32, 'b'*32, 'c'*32
NODES = dict(primary='00000000-0000-4000-8000-000000000001', actor='00000000-0000-4000-8000-000000000002')
DOMAIN = '00000000-0000-4000-8000-000000000003'


class SocialHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): account_tests.AccountProviderTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls): account_tests.AccountProviderTests.tearDownClass.__func__(cls)

    def setUp(self):
        self.epoch = 1700000000000
        self.account = AccountProvider(epoch_ms=lambda: self.epoch)
        self.social = AvatarSocialProvider(account_authenticator(self.account), epoch_ms=lambda: self.epoch)
        self.reader, self.actor, self.adapter = (secrets.token_hex(32) for _ in range(3))
        self.server = make_server(self.reader, self.actor, account_provider=self.account,
            avatar_social_provider=self.social, tls_context=self.server_context, adapter_token=self.adapter)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.stop)
        self.origin = f'https://localhost:{self.server.server_port}'
        self.opener = build_opener(ProxyHandler({}), HTTPSHandler(context=self.client_context))
        self.tokens, principals = {}, {}
        for role, run in (('primary', RUN), ('actor', ACTOR)):
            self.account.provision(run)
            credentials = self.account.credentials(run, 'owned')
            status, value = self.request(TOKEN_PATH, method='POST', raw=urlencode(dict(
                grant_type='password', scope='owner', **credentials)).encode(), content_type='application/x-www-form-urlencoded')
            self.assertEqual(200, status)
            self.tokens[role] = 'Bearer '+value['access_token']; principals[role] = credentials['username']
        self.principals = principals
        self.social.provision(RUN, principals, NODES, DOMAIN); self.social.activate(RUN, TICKET)

    def stop(self):
        self.account.shutdown(); self.server.shutdown(); self.thread.join(timeout=3); self.server.server_close()

    def request(self, path, *, method='GET', raw=None, content_type=None, auth=None, headers=None):
        metadata = {} if headers is None else dict(headers)
        if content_type: metadata['Content-Type'] = content_type
        if auth: metadata['Authorization'] = auth
        request = Request(self.origin+path, data=raw, method=method, headers=metadata)
        try: response = self.opener.open(request, timeout=3)
        except HTTPError as error: response = error
        with response:
            self.last_raw = response.read(65537)
            return response.code, json.loads(self.last_raw)

    def consent(self, role, *, method='POST', auth=None):
        peer = 'actor' if role == 'primary' else 'primary'
        pair = dict(node_id=NODES[role], proposed_node_id=NODES[peer])
        path = REQUEST+('?' + urlencode(pair) if method == 'GET' else '')
        raw = json.dumps(dict(user_connection_request=pair)).encode() if method == 'POST' else None
        return self.request(path, method=method, raw=raw, content_type='application/json' if raw else None,
                            auth=auth or self.tokens[role])

    def test_two_actual_oauth_POSTs_and_query_polling_materialize_then_delete_owned_rows(self):
        self.assertEqual('pending', self.consent('primary', method='GET')[1]['connection'])
        self.assertEqual([], self.social.snapshot(RUN)['pendingRoles'])
        self.assertEqual(200, self.consent('primary')[0])
        self.assertEqual('pending', self.consent('primary', method='GET')[1]['connection'])
        self.assertEqual(200, self.consent('actor')[0])
        for role in NODES:
            self.assertEqual(1, len(self.request(USERS+'?filter=connections&per_page=400', auth=self.tokens[role])[1]['data']['users']))
            status, table = self.request(CONNECTIONS+'?per_page=1000&page=1&sort=username,ASC', auth=self.tokens[role])
            self.assertEqual((200, 1), (status, table['total_entries']))
        self.assertEqual(200, self.request(DELETE+self.principals['actor'], method='DELETE', auth=self.tokens['primary'])[0])
        for role in NODES:
            self.assertEqual([], self.request(USERS+'?filter=connections', auth=self.tokens[role])[1]['data']['users'])
        snapshot = self.social.snapshot(RUN)
        self.assertFalse(snapshot['connected']); self.assertEqual(0, snapshot['inflightRequests'])
        self.assertTrue(all(event['written'] for event in snapshot['history']))
        self.social.revoke(RUN); self.social.retire(RUN)
        self.assertEqual(0, self.server.internal_errors)

    def test_real_completed_socket_write_retains_exact_original_bytes_hash_and_time(self):
        status, _ = self.request(USERS+'?filter=connections', auth=self.tokens['primary'])
        original = self.last_raw; event = self.social.snapshot(RUN)['history'][-1]
        self.assertEqual(200, status); self.assertTrue(event['written'])
        self.assertEqual(hashlib.sha256(original).hexdigest(), event['responseSha256'])
        self.assertEqual(len(original), event['responseBytes'])
        self.epoch += 2000
        self.assertEqual(event, self.social.snapshot(RUN)['history'][-1])
        for secret in (*self.tokens.values(), self.reader, self.actor, self.adapter):
            self.assertNotIn(secret, json.dumps(event))

    def test_revoked_expired_foreign_and_adapter_credentials_cannot_supply_consent(self):
        self.assertEqual(403, self.consent('actor', auth=self.tokens['primary'])[0])
        self.assertEqual(403, self.consent('primary', auth='Bearer '+self.adapter)[0])
        self.assertEqual(401, self.consent('primary', auth='Bearer '+self.reader)[0])
        self.account.control(ACTOR, 'revoke-issued')
        self.assertEqual(401, self.consent('actor')[0])
        self.epoch += 3600001
        self.assertEqual(401, self.consent('primary')[0])
        self.assertFalse(self.social.snapshot(RUN)['connected'])

    def test_malformed_original_methods_bodies_and_duplicate_query_cannot_change_relationship(self):
        for path, method, raw, content_type in (
                (REQUEST, 'POST', b'{}', 'application/json'),
                (REQUEST, 'POST', b'{}', 'text/plain'),
                (USERS, 'GET', b'{}', 'application/json'),
                (USERS+'?filter=connections&filter=connections', 'GET', None, None)):
            self.assertEqual(400, self.request(path, method=method, raw=raw, content_type=content_type,
                                               auth=self.tokens['primary'])[0])
        self.assertFalse(self.social.snapshot(RUN)['connected'])

    def test_factory_requires_inspectable_same_actual_account_authority_and_primary_tls(self):
        reader, actor = secrets.token_hex(32), secrets.token_hex(32)
        for account, social, tls in (
                (None, self.social, self.server_context),
                (AccountProvider(), self.social, self.server_context),
                (AccountProvider(), AvatarSocialProvider(lambda _auth: 'e2e-'+RUN), self.server_context),
                (AccountProvider(), self.social, None)):
            with self.assertRaises(ValueError):
                make_server(reader, actor, account_provider=account, avatar_social_provider=social, tls_context=tls)
            if account is not None:
                self.assertFalse(account._attached)
        self.assertIs(type(self.social.authenticate), AccountAuthenticator)
        self.assertIs(self.account, self.social.authenticate.provider)
        with self.assertRaises(ValueError): account_authenticator(object())
        with self.assertRaises(ValueError):
            make_server(reader, actor, browser_peer_of=self.server, avatar_social_provider=self.social,
                        tls_context=self.server_context)


if __name__ == '__main__': unittest.main()
