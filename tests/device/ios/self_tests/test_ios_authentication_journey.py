"""Shared Authentication journey over synthetic iOS SDK and real local HTTPS.

OpenSSL only creates temporary loopback test certificates. Trust is limited to
this test's Python client; no system/device trust, app or simulator is changed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import partial
from copy import deepcopy
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import HTTPSHandler,ProxyHandler,build_opener
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from ios.self_tests import authentication_native_boundary as sdk
from self_tests import test_account_provider as tls
from feature_journeys import witness
from feature_journeys.account_provider import AccountProvider
from feature_journeys.server import make_server
from feature_journeys.engine import Journey
from feature_journeys.scenarios import VERSION
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.normal_ui import NativeUI
from adapters.normal_ui import NativeUIError
from ios.adapters import authentication_runtime,authentication_feature,script_runtime,normal_input,feature_observation
from ios.adapters.authentication_runtime import IOSAuthenticationRuntime,IOSLoginControls
from ios.adapters.authentication_feature import IOSAuthenticationFeature,AuthenticationFixtureReader
from ios.adapters.authentication_samples import measurement

RUN='a'*32


class IOSAuthenticationJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()

    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.provider=AccountProvider(epoch_ms=lambda:1700000000000)
        self.reader,self.actor_token,self.adapter_token=[secrets.token_hex(32) for _ in range(3)]
        self.server=make_server(self.reader,self.actor_token,account_provider=self.provider,
            tls_context=tls.AccountProviderTests.server_context,adapter_token=self.adapter_token)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.origin='https://localhost:'+str(self.server.server_port)
        opener=build_opener(ProxyHandler({}),HTTPSHandler(context=tls.AccountProviderTests.client_context),witness.NoRedirect())
        self.native=sdk.Native(self.root,self.origin,opener)
        self.provider.epoch_ms=self.native.host_epoch;self.server.journal.clock=self.native.host_epoch
        self.addCleanup(self.stop)
        patches=[patch.object(witness,'build_opener',return_value=opener),
            patch.object(script_runtime.backend,'WebDriver',return_value=self.native),
            patch.object(normal_input,'urlopen',side_effect=self.native.post),
            patch.object(feature_observation,'post_request',side_effect=self.native.post),
            patch.object(script_runtime,'NativeClockAcquisition',partial(script_runtime.NativeClockAcquisition,
                epoch_ms=self.native.host_epoch,monotonic=lambda:self.native.clock)),
            patch.object(authentication_runtime,'NativeUI',partial(NativeUI,monotonic=lambda:self.native.clock,sleep=self.native.sleep)),
            patch.object(script_runtime,'NativeUI',partial(NativeUI,monotonic=lambda:self.native.clock,sleep=self.native.sleep)),
            patch.object(script_runtime,'TokenScriptUI',partial(script_runtime.TokenScriptUI,monotonic=lambda:self.native.clock,sleep=self.native.sleep)),
            patch.object(authentication_runtime,'IOSLoginControls',partial(IOSLoginControls,monotonic=lambda:self.native.clock,sleep=self.native.sleep))]
        for boundary in patches:boundary.start();self.addCleanup(boundary.stop)
        self.client=witness.Client(self.origin+'/feature-fixture/v1',self.reader)
        with patch.object(witness.secrets,'token_hex',return_value=RUN):self.run,self.fixture=self.client.register('authentication')
        primary_client=AdapterFixtureClient(self.origin+'/feature-fixture/v1',self.adapter_token)
        actor_client=witness.Client(self.origin+'/feature-fixture/v1',self.actor_token)
        base=self.native.base()
        self.primary_runtime=IOSAuthenticationRuntime(base,primary_client,RUN)
        self.actor_runtime=IOSAuthenticationRuntime(base,actor_client,RUN)
        self.primary=IOSAuthenticationFeature(self.primary_runtime,'owned',AuthenticationFixtureReader(primary_client,RUN,epoch_ms=self.native.host_epoch),
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        self.actor=IOSAuthenticationFeature(self.actor_runtime,'owned',AuthenticationFixtureReader(actor_client,RUN,epoch_ms=self.native.host_epoch),
            role='actor',monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        self.reports=[]

    def action(self,verb,ticket,inputs=None):
        self.client.activate(ticket,verb,inputs or {})
        return dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.fixture,ticket=ticket,verb=verb,inputs=inputs or {})

    def test_ignored_submit_ack_fails_and_recovery_never_resends_credentials_or_submit(self):
        self.client.activate('0'*32)
        self.primary.prepare()
        self.primary.act(self.action('login-open','1'*32))
        self.native.ignored_submit=True
        call=self.action('login-submit','2'*32,dict(account='invalid'))
        with self.assertRaises(NativeUIError):self.primary.act(call)
        before=list(self.native.input_log)
        with self.assertRaises(NativeUIError):self.primary.act(call)
        self.assertEqual(before,self.native.input_log)
        self.assertEqual(1,self.native.input_log.count('login.submit'))
        self.assertEqual('acting',self.primary.control()['phase'])
        self.assertIsNotNone(self.primary_runtime.authentication_actions_store('owned').read())

    def test_foreign_saved_username_is_refused_before_any_normal_input(self):
        self.client.activate('0'*32)
        self.native.saved='another-account'
        with self.assertRaises(NativeUIError):self.primary.prepare()
        self.assertEqual([],self.native.input_log)

    def test_stale_foreign_or_modified_originals_cannot_be_relabelled_as_current(self):
        ticket='0'*32;self.client.activate(ticket)
        self.primary.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        frame=self.primary.role_state()['last']['frame']
        def check(value,**overrides):
            args=dict(provider_instance=self.primary.source.instance,native_epoch=frame['nativeAfter']['capturedEpochMs'],
                host_epoch=frame['status']['capturedEpochMs'],after_epoch=1,actor=False)
            return measurement(RUN,ticket,self.origin,value,**(args|overrides))
        self.assertEqual('anonymous',check(frame)['state']['principal'])
        for source in ('nativeBefore','nativeAfter','login','tablet','probe','originPresent','probeReleased','originAbsent'):
            changed=deepcopy(frame);changed[source]['capturedEpochMs']-=10000
            with self.subTest(source=source),self.assertRaises(NativeUIError):check(changed)
        changed=deepcopy(frame);changed['probe']['processId']+=1
        with self.assertRaises(NativeUIError):check(changed)
        with self.assertRaises(NativeUIError):check(frame,after_epoch=frame['clockJoin']['hostBeforeEpochMs']+1)

    def stop(self):
        self.provider.shutdown();self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        self.native.close();self.assertFalse(self.thread.is_alive());self.assertEqual(0,self.server.internal_errors)

    def test_full_shared_authentication_journey_keeps_independent_sources_three_restarts_and_original_preferences(self):
        original=self.native.preferences()
        def invoke(operation,values):return getattr(self.primary,operation.rsplit('.',1)[1])(values)
        def peer():self.actor.publish();return self.client.observe()
        journey=Journey('authentication',RUN,self.fixture,invoke=invoke,witness=peer,activate=self.client.activate,
            read_artifact=lambda _:self.fail('Authentication has no byte artifact shortcut'),image_policy={},
            continuity=lambda *_:None,monotonic=lambda:self.native.clock,epoch_ms=self.native.host_epoch,
            sleep=self.native.sleep,report=self.reports.append)
        journey.execute()
        self.assertTrue(self.reports[-1]['sequenceCompleted']);self.assertTrue(self.reports[-1]['cleanupSucceeded'])
        self.assertEqual(['app.stop','app.launch']*3,self.native.lifecycle_inputs)
        self.assertEqual(original,self.native.preferences());self.assertIn('clear-username',self.native.input_log)
        primary=self.primary.role_state()['last']['frame'];actor=self.actor.role_state()['last']['frame']
        self.assertNotEqual(primary['nativeAfter']['requestId'],actor['nativeAfter']['requestId'])
        self.assertIsNone(primary['proof']);self.assertIsNotNone(actor['proof'])
        # The adapter must not retire evidence while the independently owned
        # provider still has authority. This is the runner's separate close.
        with self.assertRaises(NativeUIError):self.primary.finalize()
        self.assertIsNotNone(self.primary.store.read())
        self.client.close()
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertTrue(all(store.read() is None for store in self.primary._retirement_paths()))
        self.assertFalse(self.native.origins.path.exists());self.assertFalse(self.native.origins.manifest.exists())
        self.assertTrue(all(row['fd'] is None for row in self.native.private.rows.values()))
        self.assertEqual([],list(self.native.private.root.glob('feature-login-input-*')))


if __name__=='__main__':unittest.main()
