"""Closed private authority and paired target configuration, no SDK creation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.adapters.avatar_configuration import settings,authority_client,AvatarAuthorityClient
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters import avatar_authority
from feature_journeys import witness
from self_tests import test_avatar_account_http as http_fixture


class AvatarConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        self.config=dict(artifactRoot=str(root),imagePolicy=dict(source='world-render-target',marker=[0,0,128,32],subject=[0,40,100,100]),
            primaryTarget='actual-primary',authorityRead=dict(mode='adapter',token='read-'+'a'*48))
        self.client=Client('https://controlled.invalid/feature-fixture/v1','publisher-'+'b'*48)
    def test_actor_explicit_separate_read_client_keeps_publisher_unchanged_and_binds_actual_run_role(self):
        configuration=settings(self.config,role='actor',target='actual-actor');actual=authority_client(self.client,'c'*32,'actor',configuration)
        self.assertIsInstance(actual,AvatarAuthorityClient);self.assertNotEqual(actual.token,self.client.token)
        self.assertEqual('publisher-'+'b'*48,self.client.token);self.assertEqual(self.client.url,actual.url)
        with patch.object(Client,'request',return_value={'original':'response'}) as transport:
            self.assertEqual({'original':'response'},actual.request('/runs/'+'c'*32+'/avatar/accounts'))
            self.assertEqual(dict(method='GET',adapter_access=True),transport.call_args.kwargs)
            actual.request('/runs/'+'c'*32+'/avatar/credentials/actor')
        for path in ('/runs/'+'d'*32+'/avatar/accounts','/runs/'+'c'*32+'/avatar/credentials/primary',
            '/runs/'+'c'*32+'/samples','/runs/'+'c'*32+'/avatar/sessions'):
            with self.subTest(path=path),self.assertRaises(NativeUIError):actual.request(path)
        with self.assertRaises(NativeUIError):actual.request('/runs/'+'c'*32+'/avatar/accounts',{})
    def test_missing_authority_wrong_roles_same_target_and_private_schema_fail_before_transport(self):
        for fault in ('missing','role','target','mode','token','extra'):
            value=deepcopy(self.config)
            if fault=='missing':value.pop('authorityRead')
            elif fault=='role':value['actorTarget']=value.pop('primaryTarget')
            elif fault=='target':value['primaryTarget']='actual-actor'
            elif fault=='mode':value['authorityRead']['mode']='publisher'
            elif fault=='token':value['authorityRead']['token']='bad secret\n'
            else:value['nativeLoggedIn']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):settings(value,role='actor',target='actual-actor')
        with self.assertRaises(NativeUIError):authority_client(self.client,'c'*32,'actor',{})
    def test_primary_default_reader_and_explicit_reader_mode_preserve_closed_authority(self):
        config=self.config|dict(actorTarget='actual-actor');config.pop('primaryTarget');config.pop('authorityRead')
        self.assertEqual(config,settings(config,role='primary',target='actual-primary'))
        self.assertIs(self.client,authority_client(self.client,'c'*32,'primary',config))
        config['authorityRead']=dict(mode='reader',token='read-'+'a'*48)
        actual=authority_client(self.client,'c'*32,'primary',config)
        with patch.object(Client,'request',return_value={}) as transport:
            actual.request('/runs/'+'c'*32+'/avatar/accounts');self.assertEqual(False,transport.call_args.kwargs['adapter_access'])


class AvatarAuthorityConfigurationHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):http_fixture.AvatarAccountHTTPTests.setUpClass()
    @classmethod
    def tearDownClass(cls):http_fixture.AvatarAccountHTTPTests.tearDownClass()
    def setUp(self):
        self.f=http_fixture.AvatarAccountHTTPTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_actual_tls_actor_publisher_cannot_read_credentials_but_separate_scoped_adapter_can(self):
        f=self.f;publisher=Client(f.origin+http_fixture.PREFIX,f.actor)
        reader=AvatarAuthorityReader(AvatarAuthorityClient(publisher,f.run,'actor',dict(mode='adapter',token=f.adapter)),
            f.run,epoch_ms=lambda:f.epoch,monotonic=lambda:1.)
        with patch.object(witness,'build_opener',return_value=f.opener):
            status=reader.read();credentials=reader.credentials('actor')
            self.assertEqual('e2e-'+status['accounts']['actor']['runId'],credentials['username']);credentials.clear()
            with self.assertRaises(ValueError):publisher.request('/runs/'+f.run+'/avatar/accounts')
            with self.assertRaises(NativeUIError):reader.credentials('primary')
            wrong=AvatarAuthorityClient(publisher,f.run,'actor',dict(mode='adapter',token=f.actor))
            with self.assertRaises(ValueError):wrong.request('/runs/'+f.run+'/avatar/accounts')
        self.assertEqual(0,f.server.internal_errors)
    def test_default_real_host_clock_uses_integer_UTC_ms_for_actual_tls_provider_freshness(self):
        f=self.f;reader=AvatarAuthorityReader(Client(f.origin+http_fixture.PREFIX,f.reader),f.run)
        with patch.object(witness,'build_opener',return_value=f.opener),patch.object(avatar_authority.time,'time',return_value=f.epoch/1000+.00049):
            status=reader.read()
        self.assertEqual('allocated',status['phase']);self.assertIs(type(reader.last_epoch),int)
        self.assertEqual(f.epoch,reader.last_epoch);self.assertEqual(0,f.server.internal_errors)


if __name__=='__main__':unittest.main()
