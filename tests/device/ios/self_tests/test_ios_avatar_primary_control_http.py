"""Actual TLS, existing account scopes and durable scoped-control handoff.

These are host authority/protocol checks, not native or whole-flow acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys import witness
from feature_journeys.avatar_primary_control import prepare,issuer,PURPOSES
from ios.adapters.avatar_primary_control import load
from ios.self_tests.retained_host_roots import retain_owned_root
from self_tests import test_avatar_account_http as http
from self_tests.test_avatar_social_provider import NODES,DOMAIN


class AvatarPrimaryControlHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        http.AvatarAccountHTTPTests.setUpClass.__func__(cls)
        retain_owned_root(cls.temporary,expected_root=cls.path)
    @classmethod
    def tearDownClass(cls):http.AvatarAccountHTTPTests.tearDownClass.__func__(cls)
    request=http.AvatarAccountHTTPTests.request
    call=http.AvatarAccountHTTPTests.call
    status=http.AvatarAccountHTTPTests.status
    stop=http.AvatarAccountHTTPTests.stop
    def setUp(self):
        http.AvatarAccountHTTPTests.setUp(self)
        self.temp=tempfile.TemporaryDirectory(prefix='avatar-primary-control-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);retain_owned_root(self.temp,expected_root=self.root)
        self.store=PrivateFeatureState(self.root/('avatar-primary-control-'+self.run+'.json'))
        self.reader_client=witness.Client(self.origin+http.PREFIX,self.reader)
        self.adapter_client=AdapterFixtureClient(self.reader_client.url,self.adapter)
        transport=patch.object(witness,'build_opener',return_value=self.opener);transport.start();self.addCleanup(transport.stop)
    def original(self):return prepare(self.reader_client,self.store,self.run)
    def control(self):return load(self.adapter_client,self.run,'primary',dict(authorityControlRoot=str(self.root)))
    def scoped(self,value,path,body=None,method=None):
        return self.request(path,auth='Bearer '+value['grant']['token'],method=method or ('POST' if body is not None else 'GET'),
            raw=None if body is None else json.dumps(body).encode(),content_type=None if body is None else 'application/json')

    def test_actual_scoped_bind_and_revoke_preserve_adapter_GET_only_and_redacted_journal(self):
        value=self.original();control=self.control()
        self.assertEqual([],control.admit()['usedPurposes'])
        self.assertEqual([],self.adapter_client.request('/runs/'+self.run)['entries'])
        for path,body in (('/avatar/sessions',dict(sessions=NODES,domain=DOMAIN)),('/avatar/control',dict(operation='revoke'))):
            with self.assertRaises(NativeUIError):self.adapter_client.request('/runs/'+self.run+path,body,method='POST')
        self.assertEqual('allocated',self.status()['phase'])
        control.request('/runs/'+self.run+'/avatar/sessions',dict(sessions=NODES,domain=DOMAIN),method='POST')
        self.assertEqual('ready',self.status()['phase'])
        control.request('/runs/'+self.run+'/avatar/control',dict(operation='revoke'),method='POST')
        self.assertEqual('revoking',self.status()['phase'])
        self.assertEqual(PURPOSES,control.admit()['usedPurposes'])
        for route,body in (('sessions',dict(sessions=NODES,domain=DOMAIN)),('control',dict(operation='revoke'))):
            self.assertEqual(400,self.scoped(value,self.base+'/avatar/'+route,body)[0])
        self.assertEqual(value,self.store.read());self.assertEqual(0,self.server.internal_errors)

    def test_actual_grant_saved_but_return_lost_recovers_original_request_by_GET_without_second_POST(self):
        original=self.reader_client.request;calls=[]
        def request(path,*args,**kwargs):
            calls.append((path,kwargs.get('method')));value=original(path,*args,**kwargs)
            if kwargs.get('method')=='POST':raise OSError('Lost original successful grant return')
            return value
        self.reader_client.request=request
        with self.assertRaisesRegex(OSError,'Lost original'):self.original()
        old=self.store.read();self.assertEqual('issued',old['phase']);self.assertIsNone(old['grant'])
        server_grant=deepcopy(self.server.avatar_control_handoffs[self.run]['grant'])
        saved=self.original();self.assertEqual('saved',saved['phase']);self.assertEqual(server_grant,saved['grant'])
        self.assertEqual(old['requestId'],saved['requestId'])
        self.assertEqual([('/runs/'+self.run+'/avatar/control-handoff','POST'),
            ('/runs/'+self.run+'/avatar/control-handoff/'+old['requestId'],None)],calls)
        self.assertEqual(saved,self.original());self.assertEqual(2,len(calls))

    def test_unknown_original_delivery_refuses_missing_known_request_without_reissuing(self):
        original=self.reader_client.request;calls=[]
        def request(path,*args,**kwargs):
            calls.append((path,kwargs.get('method')))
            if kwargs.get('method')=='POST':raise OSError('Original socket outcome unavailable')
            return original(path,*args,**kwargs)
        self.reader_client.request=request
        with self.assertRaises(OSError):self.original()
        old=self.store.read();self.assertEqual({},self.server.avatar_control_handoffs)
        with self.assertRaises(ValueError):self.original()
        self.assertEqual(old,self.store.read());self.assertEqual(['POST',None],[item[1] for item in calls])
        self.assertEqual('allocated',self.status()['phase'])

    def test_unknown_provider_outcome_consumes_purpose_before_effect_and_refuses_replay(self):
        value=self.original();control=self.control();original=self.server.avatar_accounts.bind_sessions;calls=[]
        def bind(*args):
            calls.append(args);original(*args);raise ValueError('Lost provider return after actual binding')
        with patch.object(self.server.avatar_accounts,'bind_sessions',new=bind):
            with self.assertRaises(ValueError):control.request('/runs/'+self.run+'/avatar/sessions',dict(sessions=NODES,domain=DOMAIN),method='POST')
            self.assertEqual('ready',self.status()['phase'])
            with self.assertRaises(ValueError):control.request('/runs/'+self.run+'/avatar/sessions',dict(sessions=NODES,domain=DOMAIN),method='POST')
        self.assertEqual(1,len(calls));self.assertEqual(['bind-sessions'],control.admit()['usedPurposes'])
        self.assertEqual(value,self.store.read())

    def test_foreign_run_and_role_cannot_borrow_control_and_token_has_no_reader_or_actor_authority(self):
        value=self.original();self.assertEqual(200,self.call(http.PREFIX+'/runs',body=dict(area='avatar-people'))[0])
        foreign=next(run for run in self.server.journal.runs if run!=self.run)
        with self.assertRaises(NativeUIError):load(self.adapter_client,self.run,'actor',dict(authorityControlRoot=str(self.root)))
        changed=deepcopy(value);changed['runId']=foreign
        with self.assertRaises(ValueError):issuer(changed,self.run,self.reader_client.url)
        for role in ('adapter','actor'):
            self.assertEqual(403,self.call(self.base+'/avatar/control-handoff',role=role,body=dict(
                avatarPrimaryControlRequestVersion=1,runId=self.run,role='primary',purposes=PURPOSES,requestId='e'*32))[0])
            self.assertEqual(403,self.call(self.base+'/avatar/control-handoff/'+value['requestId'],role=role)[0])
        for path,body,method in ((self.base,None,'GET'),(self.base,None,'DELETE'),
                (self.base+'/avatar/credentials/primary',None,'GET'),(self.base+'/samples',dict(ticket='a'*32),'POST'),
                (self.base+'/active',dict(ticket='a'*32,verb='cleanup',inputs={}),'POST'),
                (http.PREFIX+'/runs/'+foreign+'/avatar/sessions',dict(sessions=NODES,domain=DOMAIN),'POST')):
            with self.subTest(path=path,method=method):self.assertEqual(403,self.scoped(value,path,body,method)[0])
        self.assertEqual([],self.server.avatar_control_handoffs[self.run]['used'])

    def test_retired_run_revokes_existing_control_without_creating_or_rebinding_another_run(self):
        self.original();control=self.control()
        control.request('/runs/'+self.run+'/avatar/control',dict(operation='revoke'),method='POST')
        self.assertEqual(200,self.call(self.base,method='DELETE')[0])
        with self.assertRaises(ValueError):control.admit()
        with self.assertRaises(ValueError):control.request('/runs/'+self.run+'/avatar/sessions',dict(sessions=NODES,domain=DOMAIN),method='POST')
        self.assertNotIn(self.run,self.server.journal.runs)


if __name__=='__main__':unittest.main()
