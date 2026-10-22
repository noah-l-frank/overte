"""Real OAuth state and social protocol logic; no device/peer/render acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from urllib.parse import urlencode

from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.avatar_social_provider import AvatarSocialProvider, REQUEST, USERS, CONNECTIONS, DELETE

RUN, OTHER, TICKET = 'a'*32, 'b'*32, 'c'*32
NODES = dict(primary='00000000-0000-4000-8000-000000000001', actor='00000000-0000-4000-8000-000000000002')
DOMAIN = '00000000-0000-4000-8000-000000000003'


class SocialTests(unittest.TestCase):
    def setUp(self):
        self.clock, self.epoch = 1., 1700000000000
        self.account = AccountProvider(epoch_ms=lambda: self.epoch)
        self.tokens, principals = {}, {}
        for role, run in (('primary', RUN), ('actor', OTHER)):
            self.account.provision(run)
            credentials = self.account.credentials(run, 'owned')
            status, grant = self.account.grant(urlencode(dict(grant_type='password', scope='owner', **credentials)).encode())
            self.assertEqual(200, status)
            self.tokens[role] = 'Bearer '+grant['access_token']; principals[role] = credentials['username']
        self.provider = AvatarSocialProvider(account_authenticator(self.account), epoch_ms=lambda: self.epoch,
                                            monotonic=lambda: self.clock)
        self.provider.provision(RUN, principals, NODES, DOMAIN); self.provider.activate(RUN, TICKET)
        self.principals = principals

    def request(self, role, method='POST', *, path=REQUEST, values=None, write=True, token=None):
        peer = 'actor' if role == 'primary' else 'primary'
        values = dict(node_id=NODES[role], proposed_node_id=NODES[peer]) if values is None else values
        raw = json.dumps(dict(user_connection_request=values)).encode() if method == 'POST' else b''
        query = urlencode(values) if method == 'GET' and path == REQUEST else ''
        if method == 'GET' and path == USERS: query = 'filter=connections&per_page=400'
        with self.provider.response(method, path, query, raw, token or self.tokens[role]) as response:
            status, raw, response_id, written = response
            if write and written:
                written(dict(status=status, responseId=response_id, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            return status, json.loads(raw)

    def test_real_mutual_POST_required_and_GET_cannot_accept_for_peer(self):
        self.assertEqual('pending', self.request('primary', 'GET')[1]['connection'])
        self.assertEqual([], self.provider.snapshot(RUN)['pendingRoles'])
        self.request('primary')
        for _ in range(5): self.assertEqual('pending', self.request('primary', 'GET')[1]['connection'])
        self.assertFalse(self.provider.snapshot(RUN)['connected'])
        self.assertEqual(['primary'], self.provider.snapshot(RUN)['pendingRoles'])
        status, value = self.request('actor')
        self.assertEqual((200, self.principals['primary']), (status, value['connection']['username']))
        self.assertEqual(self.principals['actor'], self.request('primary', 'GET')[1]['connection']['username'])
        self.assertTrue(self.provider.snapshot(RUN)['connected'])

    def test_fresh_directory_and_actual_delete_show_both_relationship_absence(self):
        for role in NODES: self.request(role)
        for role in NODES:
            rows = self.request(role, 'GET', path=USERS)[1]['data']['users']
            self.assertEqual(1, len(rows)); self.assertEqual('connection', rows[0]['connection'])
        self.assertEqual(200, self.request('primary', 'DELETE', path=DELETE+self.principals['actor'])[0])
        for role in NODES: self.assertEqual([], self.request(role, 'GET', path=USERS)[1]['data']['users'])
        snapshot = self.provider.snapshot(RUN)
        self.assertFalse(snapshot['connected']); self.assertEqual([], snapshot['pendingRoles'])
        self.provider.revoke(RUN); self.provider.retire(RUN)
        with self.assertRaises(ValueError): self.provider.provision(RUN, self.principals, NODES, DOMAIN)

    def test_expired_single_POST_does_not_match_a_later_peer(self):
        self.request('primary'); self.clock += 12; self.epoch += 12000
        self.request('actor')
        value = self.provider.snapshot(RUN)
        self.assertFalse(value['connected']); self.assertEqual(['actor'], value['pendingRoles'])
        self.clock += 12; self.epoch += 12000
        self.assertEqual([], self.provider.snapshot(RUN)['pendingRoles'])
        self.provider.revoke(RUN)

    def test_unknown_revoked_or_other_account_tokens_cannot_supply_partner(self):
        self.assertEqual(401, self.request('primary', token='Bearer arbitrary')[0])
        self.assertEqual(403, self.request('actor', token=self.tokens['primary'])[0])
        self.account.control(OTHER, 'revoke-issued')
        self.assertEqual(401, self.request('actor')[0])
        self.assertFalse(self.provider.snapshot(RUN)['connected'])

    def test_foreign_sessions_self_connections_and_wrong_delete_are_rejected(self):
        for values in (dict(node_id=NODES['primary'], proposed_node_id=NODES['primary']),
                       dict(node_id=NODES['actor'], proposed_node_id=NODES['primary'])):
            self.assertEqual(403, self.request('primary', values=values)[0])
        self.assertEqual(403, self.request('primary', 'DELETE', path=DELETE+'other')[0])
        self.assertFalse(self.provider.snapshot(RUN)['connected'])

    def test_missing_or_mismatched_actual_socket_write_retains_responsibility(self):
        self.request('primary', 'GET', path=USERS, write=False)
        with self.assertRaises(ValueError): self.provider.revoke(RUN)
        self.assertEqual(0, self.provider.snapshot(RUN)['inflightRequests'])
        self.assertFalse(self.provider.snapshot(RUN)['history'][0]['written'])
        with self.provider.response('GET', USERS, 'filter=connections', b'', self.tokens['primary']) as response:
            with self.assertRaises(ValueError): response[3](dict(status=200, responseId=response[2], bytes=1, sha256='0'*64))
        with self.assertRaises(ValueError): self.provider.revoke(RUN)

    def test_history_is_original_immutable_and_new_ticket_does_not_retime_requests(self):
        self.request('primary', 'GET', path=USERS)
        first = self.provider.snapshot(RUN); copy = deepcopy(first)
        self.epoch += 300; self.clock += .3; self.provider.activate(RUN, 'd'*32)
        self.request('actor', 'GET', path=USERS)
        current = self.provider.snapshot(RUN)
        self.assertEqual(copy['history'], current['history'][:1])
        self.assertEqual(first, copy)
        current['history'][0]['written'] = False
        self.assertTrue(self.provider.snapshot(RUN)['history'][0]['written'])

    def test_malformed_duplicate_fields_and_reused_scope_fail_closed(self):
        for raw in (b'{"user_connection_request":{},"user_connection_request":{}}',
                    b'{"user_connection_request":{"node_id":null,"proposed_node_id":false}}'):
            with self.assertRaises(ValueError):
                with self.provider.response('POST', REQUEST, '', raw, self.tokens['primary']): pass
        self.assertEqual(0, self.provider.snapshot(RUN)['inflightRequests'])
        with self.assertRaises(ValueError): self.provider.provision('e'*32, self.principals, NODES, DOMAIN)

    def test_pending_or_connected_resources_prevent_revocation(self):
        self.request('primary')
        with self.assertRaises(ValueError): self.provider.revoke(RUN)
        self.request('actor')
        with self.assertRaises(ValueError): self.provider.revoke(RUN)

    def test_actual_Pal_PSF_connections_table_endpoint_pagination_and_sort(self):
        for role in NODES: self.request(role)
        for page in (1, 2):
            with self.provider.response('GET', CONNECTIONS, f'per_page=1000&page={page}&sort=username,ASC',
                                        b'', self.tokens['primary']) as response:
                status, raw, response_id, written = response; value = json.loads(raw)
                written(dict(status=status, responseId=response_id, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
            self.assertEqual((200, page, 1, 1), (status, value['current_page'], value['total_pages'], value['total_entries']))
            self.assertEqual(1 if page == 1 else 0, len(value['data']['users']))
    def test_clock_regression_never_becomes_current_social_facts(self):
        self.request('primary', 'GET', path=USERS)
        self.epoch -= 1
        with self.assertRaises(ValueError): self.provider.snapshot(RUN)


if __name__ == '__main__': unittest.main()
