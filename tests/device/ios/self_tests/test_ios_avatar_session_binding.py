"""Original controlled session input readback over actual private loopback TLS."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.client import RemoteDisconnected
import socket
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from feature_journeys.avatar_accounts import session_binding
from feature_journeys.witness import Client
from feature_journeys import witness
from feature_journeys.server import Handler
from ios.adapters.avatar_authority import AvatarAuthorityReader
from self_tests import test_avatar_account_http as fixture
from self_tests.test_avatar_social_provider import NODES,DOMAIN


class AvatarSessionBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.AvatarAccountHTTPTests.setUpClass()
    @classmethod
    def tearDownClass(cls):fixture.AvatarAccountHTTPTests.tearDownClass()
    def setUp(self):
        self.f=fixture.AvatarAccountHTTPTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def reader(self):
        f=self.f;client=Client(f.origin+fixture.PREFIX,f.reader)
        return AvatarAuthorityReader(client,f.run,epoch_ms=lambda:f.epoch,monotonic=lambda:1.)
    def test_original_stored_sessions_are_optional_legacy_input_metadata_and_never_login_or_peer_evidence(self):
        f=self.f;before=f.status();self.assertNotIn('sessionBinding',before);self.assertEqual(200,f.bind()[0]);value=f.status()
        component=value['sessionBinding'];self.assertEqual(dict(avatarSessionBindingVersion=1,sessions=NODES,domain=DOMAIN),component)
        self.assertEqual(component,session_binding(component));self.assertEqual('ready',value['phase'])
        for account in value['accounts'].values():self.assertEqual((0,0),(account['accessTokens'],account['refreshTokens']))
        self.assertFalse(value['social']['connected']);self.assertEqual([],value['social']['history'])
        legacy=deepcopy(value);del legacy['sessionBinding'];self.reader().validate(legacy,f.epoch)
    def test_lost_actual_post_socket_return_is_resolved_by_original_get_readback(self):
        f=self.f;send=Handler.send;attempts=[]
        def lost(handler,status,value,*args,**kwargs):
            if handler.command=='POST' and handler.path==f.base+'/avatar/sessions' and status==200:
                attempts.append('actual bound POST');handler.close_connection=True;handler.connection.shutdown(socket.SHUT_RDWR);return
            return send(handler,status,value,*args,**kwargs)
        with patch.object(Handler,'send',lost),self.assertRaises((RemoteDisconnected,ConnectionError,OSError)):f.bind()
        value=f.status();self.assertEqual(NODES,value['sessionBinding']['sessions']);self.assertEqual(DOMAIN,value['sessionBinding']['domain'])
        self.assertEqual(['actual bound POST'],attempts);self.assertEqual('ready',value['phase'])
        self.assertEqual(0,f.server.internal_errors)
    def test_actual_https_reader_keeps_once_observed_binding_immutable_and_rejects_component_downgrade(self):
        f=self.f;reader=self.reader()
        with patch.object(witness,'build_opener',return_value=f.opener):
            old=reader.read();self.assertNotIn('sessionBinding',old);self.assertEqual(200,f.bind()[0]);bound=reader.read()
            self.assertEqual(NODES,bound['sessionBinding']['sessions'])
            missing=deepcopy(bound);del missing['sessionBinding']
            with self.assertRaises(NativeUIError):reader.validate(missing,f.epoch,bound)
            f.server.avatar_accounts.runs[f.run]['sessions']['actor']='00000000-0000-4000-8000-000000000004'
            with self.assertRaises(NativeUIError):reader.read()
    def test_original_binding_survives_revocation_and_is_not_a_replayed_preparation(self):
        f=self.f;self.assertEqual(200,f.bind()[0]);original=f.status()['sessionBinding']
        self.assertEqual(200,f.call(f.base+'/avatar/control',body=dict(operation='revoke'))[0]);retired=f.status()
        self.assertEqual(original,retired['sessionBinding']);self.assertEqual('revoking',retired['phase'])
        self.assertTrue(all(not row['grantsEnabled'] and not row['accountExists'] for row in retired['accounts'].values()))
        self.assertEqual(400,f.bind()[0]);self.assertEqual(original,f.status()['sessionBinding'])
    def test_foreign_missing_duplicate_or_boolean_source_component_cannot_supply_original_inputs(self):
        value=dict(avatarSessionBindingVersion=1,sessions=NODES,domain=DOMAIN)
        for fault in ('version','extra','duplicate','domain','missing'):
            wrong=deepcopy(value)
            if fault=='version':wrong['avatarSessionBindingVersion']=True
            elif fault=='extra':wrong['expectedPeerLoaded']=True
            elif fault=='duplicate':wrong['sessions']['actor']=wrong['sessions']['primary']
            elif fault=='domain':wrong['domain']='not-a-session'
            else:del wrong['sessions']['actor']
            with self.subTest(fault=fault),self.assertRaises(ValueError):session_binding(wrong)


if __name__=='__main__':unittest.main()
