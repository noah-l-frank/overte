"""Ordinary private login/protected/logout over real HTTPS and explicit SDK DTOs.

The reusable boundary synthesizes Qt/native events. OAuth, original protected
replies, proof routes, private files and retained journals are real host data.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import partial
from copy import deepcopy
from pathlib import Path
import secrets
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import HTTPSHandler,ProxyHandler,build_opener

from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.native_account_probe import protected_proof
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys import witness
from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.avatar_social_provider import AvatarSocialProvider
from feature_journeys.server import make_server
from ios.adapters import authentication_runtime,script_runtime,normal_input,feature_observation
from ios.adapters.authentication_runtime import IOSLoginControls
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_login_owner import IOSAvatarLoginOwner
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.self_tests import authentication_native_boundary as sdk
from self_tests import test_account_provider as tls


class AvatarLoginOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()

    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.provider=AccountProvider(epoch_ms=lambda:1700000000000)
        self.social=AvatarSocialProvider(account_authenticator(self.provider),epoch_ms=lambda:self.native.host_epoch())
        self.reader,self.actor_token,self.adapter_token=[secrets.token_hex(32) for _ in range(3)]
        self.server=make_server(self.reader,self.actor_token,account_provider=self.provider,avatar_social_provider=self.social,
            tls_context=tls.AccountProviderTests.server_context,adapter_token=self.adapter_token)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.origin='https://localhost:'+str(self.server.server_port)
        opener=build_opener(ProxyHandler({}),HTTPSHandler(context=tls.AccountProviderTests.client_context),witness.NoRedirect())
        self.native=sdk.Native(self.root,self.origin,opener);self.provider.epoch_ms=self.native.host_epoch;self.server.journal.clock=self.native.host_epoch
        self.addCleanup(self.stop)
        patches=[patch.object(witness,'build_opener',return_value=opener),
            patch.object(script_runtime.backend,'WebDriver',return_value=self.native),
            patch.object(normal_input,'urlopen',side_effect=self.native.post),
            patch.object(feature_observation,'post_request',side_effect=self.native.post),
            patch.object(authentication_runtime,'NativeUI',partial(NativeUI,monotonic=lambda:self.native.clock,sleep=self.native.sleep)),
            patch.object(script_runtime,'NativeUI',partial(NativeUI,monotonic=lambda:self.native.clock,sleep=self.native.sleep)),
            patch.object(authentication_runtime,'IOSLoginControls',partial(IOSLoginControls,monotonic=lambda:self.native.clock,sleep=self.native.sleep))]
        for boundary in patches:boundary.start();self.addCleanup(boundary.stop)
        self.client=witness.Client(self.origin+'/feature-fixture/v1',self.reader);self.run,self.fixture=self.client.register('avatar-people')
        self.client.activate('1'*32)
        primary=AdapterFixtureClient(self.origin+'/feature-fixture/v1',self.adapter_token)
        self.authority=AvatarAuthorityReader(primary,self.run,epoch_ms=self.native.host_epoch,monotonic=lambda:self.native.clock)
        self.runtime=IOSAvatarRuntime(self.native.base())._avatar_login('owned',self.authority,'primary')
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')

    def owner(self):
        return IOSAvatarLoginOwner(self.runtime,'owned',self.authority,self.lock,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep,epoch_ms=self.native.host_epoch)

    def stop(self):
        self.provider.shutdown();self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        self.native.close();self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)

    def test_ordinary_child_login_real_protected_get_and_actual_logout_restore_original_preferences(self):
        self.native.remember=True
        owner=self.owner();preferences=self.native.preferences();original=owner.prepare()
        account=owner.login('1'*32);self.assertTrue(account['account']['loggedIn'])
        self.assertNotEqual(self.run,self.runtime.run)
        self.assertEqual('e2e-'+self.runtime.run,self.native.saved)
        self.runtime=IOSAvatarRuntime(self.native.base())._avatar_login('owned',self.authority,'primary',initial=False)
        owner=self.owner()
        evidence=owner.protected('1'*32);self.assertEqual('complete',evidence['phase'])
        native=evidence['probe'];proof_client=witness.Client(self.client.url,self.actor_token)
        proof=proof_client.request('/runs/'+self.run+'/avatar/proof/primary/'+'1'*32+'/'+native['requestId'])
        protected=protected_proof(native,proof,provider_instance=self.provider.instance,username='e2e-'+self.runtime.run)
        self.assertTrue(protected['protectedAccess'])
        for fault in ('request-scope','probe-live','origin-live','fake-login-terminal'):
            state=deepcopy(owner.state)
            if fault=='request-scope':state['protected'][0]['probe']['runId']='f'*32
            elif fault=='probe-live':state['protected'][0]['released']['source']['inflight']=True
            elif fault=='origin-live':state['protected'][0]['originAbsent']['source']['ownerExists']=True
            else:state['actions'][0]['after']=state['actions'][0]['before']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.decode(owner.envelope(state))
        self.client.activate('2'*32)
        self.assertFalse(owner.logout('2'*32)['account']['loggedIn'])
        self.client.activate('3'*32)
        self.assertEqual(preferences,owner.restore_preferences('3'*32))
        self.assertEqual(preferences,self.native.preferences())
        with self.lock.held():restored=self.owner();self.assertEqual('restored',restored.load()['phase'])
        credentials=self.server.avatar_accounts.credentials(self.run,'primary')
        raw=owner.store.path.read_text();self.assertNotIn(credentials['password'],raw);self.assertNotIn(credentials['username'],raw)
        self.assertTrue(all(item['complete'] for item in restored.state['actions']))
        self.assertFalse(self.runtime.account_origin_store('owned').read());self.assertFalse(self.runtime.account_probe_store('owned').read())
        self.assertIsNone(self.runtime.private_login_input_store('owned').read())
        self.assertFalse(self.native.origins.path.exists());self.assertTrue(all(row['fd'] is None for row in self.native.private.rows.values()))
        self.assertNotEqual(original['samples'][0]['requestId'],account['requestId'])

    def test_ignored_submit_or_interrupted_input_remains_owned_without_replay_on_reconstruction(self):
        owner=self.owner();owner.prepare();self.native.ignored_submit=True
        with self.assertRaises(NativeUIError):owner.login('1'*32)
        inputs=list(self.native.input_log);self.assertEqual(1,inputs.count('login.submit'))
        for ticket in ('1'*32,'2'*32):
            with self.assertRaises(NativeUIError):self.owner().login(ticket)
        self.assertEqual(inputs,self.native.input_log)
        with self.lock.held():self.assertEqual('login-issued',self.owner().load()['phase'])

    def test_foreign_original_saved_username_prevents_preparation_and_all_native_input(self):
        self.native.saved='unowned-person'
        with self.assertRaises(NativeUIError):self.owner().prepare()
        self.assertEqual([],self.native.input_log);self.assertIsNone(self.owner().store.read())


if __name__=='__main__':unittest.main()
