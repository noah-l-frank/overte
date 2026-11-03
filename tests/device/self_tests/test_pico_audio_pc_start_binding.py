"""Canonical BoundAdapter Audio factory with explicit native and PC RPC models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import json
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
import test_normal_scripts as original
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_pc_start import PicoAudioPCStartCoordinator
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class AudioPCBindingTests(unittest.TestCase):
    def setUp(self):
        self.h=original.PicoNormalScriptsTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        candidate=self.h.fixture.fixture;apk=candidate.fixture
        apk.temporary._finalizer.detach()
        candidate._cleanups=[row for row in candidate._cleanups if getattr(row[0],'__self__',None) is not apk]
        print('Retained original Audio canonical factory:',candidate.root,flush=True)
        self.adapter,self.sdk=self.h.instance,self.h.native;self.calls=[]
        self.primary=PhaseFixtureReader(Client('http://127.0.0.1:9876/feature-fixture/v1','a'*64),'a'*32,'audio')
        self.actor=PhaseFixtureReader(Client(self.primary.client.url,'b'*64),'a'*32,'audio')
        self.lock=self.adapter._script_journey()._lock(self.sdk.target)
        self.session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-audio-pc',self.h.fixture.state_root);self.session.begin(self.sdk.identity)
        self.addCleanup(patch.stopall);patch.object(self.adapter,'pico_input_session',return_value=self.session).start()
        root=self.h.fixture.state_root/'pc-model';root.mkdir(mode=0o700)
        PrivateFeatureState(root/'session.json').write(dict(url='http://127.0.0.1:1',token='local-model-only'),None)
        self.config=dict(audioConfigurationVersion=1,artifactRoot=str(self.h.fixture.state_root),peerState=str(root),
            peerClientSha256='a'*64,peerRunnerSha256='b'*64,domainId='00000000-0000-0000-0000-000000000001')
        patch('adapters.pico4.audio_peer.subprocess.run',side_effect=self.rpc).start()
    def rpc(self,command,**kwargs):
        self.calls.append(command);self.assertEqual('--state-dir',command[2]);action=command[4]
        if action=='domain-check':value=dict(sameDomain=True)
        else:
            self.assertEqual('status',action)
            value=dict(schemaVersion=1,previewProviderVersion=1,recordedPreviewEnabled=True,previewRunnerSha256='b'*64,
                clientRunning=True,snapshotFresh=True,audioRouted=True,clientSha256='a'*64,snapshotAgeSeconds=0,
                client=dict(connected=True,mixerReady=True,muted=True,localEcho=False,serverEcho=False))
        return SimpleNamespace(stdout=json.dumps(value).encode(),returncode=0)
    def make(self,**kwargs):
        return self.adapter._audio_pc_start_coordinator(self.sdk.target,'a'*32,self.primary,self.actor,self.config,source_lock=kwargs.pop('source_lock',self.lock),**kwargs)
    def test_canonical_factory_binds_separate_role_exact_lock_and_original_pid_without_input(self):
        owner=self.make();self.addCleanup(owner.actor.raws.close_host);self.assertIsInstance(owner,PicoAudioPCStartCoordinator)
        self.assertIs(owner.lock,self.lock);self.assertIs(owner.recipe.source,self.primary);self.assertIs(owner.actor.source,self.actor)
        self.assertIs(owner.actor.settings.source_lock,self.lock);self.assertIs(owner.actor.pages.source_lock,self.lock)
        self.assertEqual(int(self.sdk.identity.split(':')[0]),owner.actor.native.pid)
        self.assertEqual(owner.recipe.binding['sessionId'],owner.actor.pages.bridge)
        self.assertEqual([],self.sdk.inputs);self.assertIsNone(owner.recipe.store.read())
        self.assertIsNone(owner.actor.native.instance);self.assertIsNone(owner.actor.settings.previous)
        self.assertIsNone(owner.actor.pages.previous);self.assertEqual(2,len(self.calls))
        self.sdk.identity=self.sdk.identity.replace(':',':999',1)
        before=len(self.calls)
        with self.assertRaises(Exception):owner.actor.peer_factory()
        self.assertEqual(before,len(self.calls));self.assertEqual([],self.sdk.inputs)
    def test_same_actor_credential_refuses_before_recipe_or_rpc(self):
        self.actor=self.primary
        with patch.object(self.adapter,'_audio_recipe',side_effect=AssertionError('recipe must not be constructed')) as recipe:
            with self.assertRaises(ValueError):self.make()
            recipe.assert_not_called()
        self.assertEqual([],self.calls);self.assertEqual([],self.sdk.inputs)
    def test_foreign_source_lock_refuses_before_pc_authority_or_input(self):
        with self.assertRaises(ValueError):self.make(source_lock=ScriptSourceLock(self.lock.path.with_name('foreign.lock')))
        self.assertEqual([],self.calls);self.assertEqual([],self.sdk.inputs)
    def test_independent_original_reader_wrong_pid_refuses_before_pc_authority(self):
        original_source=self.adapter._audio_settings_source
        def wrong(*args,**kwargs):
            source=original_source(*args,**kwargs);source.pid+=1;return source
        with patch.object(self.adapter,'_audio_settings_source',side_effect=wrong):
            with self.assertRaises(ValueError):self.make()
        self.assertEqual([],self.calls);self.assertEqual([],self.sdk.inputs)

if __name__=='__main__':unittest.main()
