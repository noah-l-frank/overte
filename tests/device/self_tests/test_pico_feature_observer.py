"""Independent worker privacy/control boundaries; no device/network calls."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from adapters.pico4.feature_observer import configuration,run
from adapters.authentication_journey.feature import AuthenticationPhasePending
from adapters.normal_ui import NativeUIError
from adapters.graphics_journey.fixture import GraphicsPhasePending,GraphicsRunRetired
from adapters.normal_feature_state import PrivateFeatureState
from unittest.mock import patch


class PicoFeatureObserverTests(unittest.TestCase):
    def setUp(self):
        self.clock=0.;self.count=0;self.invalid=False;self.finished=False
        self.config=dict(picoFeatureObserverVersion=1,area='authentication',target='synthetic-target',
            candidateArguments=['--apk','owned.apk'],fixtureUrl='https://owned.invalid/feature-fixture/v1',actorToken='b'*64,durationSeconds=30)
        self.owner=dict(runId='a'*32,fixtureUrl=self.config['fixtureUrl']+'/runs/'+'a'*32+'/')
        self.flow=SimpleNamespace(run='a'*32,fixture_url=self.owner['fixtureUrl'],publish=self.publish,
            role_store=SimpleNamespace(read=lambda:None if self.finished else {}))
        self.journey=SimpleNamespace(authentication_feature_store=lambda _target:SimpleNamespace(read=lambda:self.owner),
            authentication_retirement_store=lambda _target:SimpleNamespace(read=lambda:None),_authentication_feature=self.actor)
    def actor(self,target,run,*,role,client):
        self.assertEqual('actor',role);self.assertEqual('a'*32,run);self.assertEqual(self.config['actorToken'],client.token)
        return self.flow
    def publish(self):
        self.count+=1
        if self.invalid:raise ValueError('Invalid synthetic original')
        if self.count==1:raise AuthenticationPhasePending('Pending synthetic transaction')
        self.owner=None;self.finished=True
    def sleep(self,value):self.clock+=value
    def test_only_owned_actor_publication_and_pending_wait_are_allowed(self):
        self.assertEqual(0,run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep))
        self.assertEqual(2,self.count)
    def test_invalid_original_is_fatal_and_does_not_request_repair_or_retry_input(self):
        self.invalid=True
        with self.assertRaises(ValueError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(1,self.count)
    def test_missing_or_foreign_owned_run_never_publishes_success(self):
        self.owner=None
        with self.assertRaises(NativeUIError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(0,self.count)
        self.clock=0.;self.owner=dict(runId='a'*32,fixtureUrl='https://foreign.invalid/run/')
        with self.assertRaises(NativeUIError):run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep)
        self.assertEqual(0,self.count)
    def test_private_config_is_https_and_has_only_read_actor_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);path=root/'actor.json'
            path.write_text(json.dumps(self.config));path.chmod(0o600)
            self.assertEqual(self.config,configuration(path))
            for change in (dict(fixtureUrl='http://owned.invalid/feature-fixture/v1'),dict(readerToken='x'*64),dict(area='audio')):
                path.write_text(json.dumps(self.config|change))
                with self.assertRaises(NativeUIError):configuration(path)
    def test_graphics_v2_config_pins_private_artifacts_and_does_not_promote_the_v1_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);path=root/'actor.json'
            value=self.config|dict(picoFeatureObserverVersion=2,area='graphics',artifactRoot=str(root))
            path.write_text(json.dumps(value));path.chmod(0o600);self.assertEqual(value,configuration(path))
            for change in (dict(picoFeatureObserverVersion=1),dict(artifactRoot='relative'),dict(readerToken='x'*64)):
                path.write_text(json.dumps(value|change))
                with self.assertRaises(NativeUIError):configuration(path)
    def test_graphics_keeps_publishing_during_the_parent_plan_until_its_own_final_window_finishes(self):
        self.config.update(picoFeatureObserverVersion=2,area='graphics')
        plan=dict(kind='retirement',runId='a'*32,fixtureUrl=self.owner['fixtureUrl'])
        def publish():
            self.count+=1
            if self.count==1:raise GraphicsPhasePending('Original world restoration is pending')
            raise GraphicsRunRetired({})
        self.flow.publish=publish
        self.journey=SimpleNamespace(graphics_feature_store=lambda target:SimpleNamespace(read=lambda:self.owner),
            graphics_retirement_store=lambda target:SimpleNamespace(read=lambda:plan),_graphics_feature=self.actor)
        self.assertEqual(0,run(self.journey,self.config,monotonic=lambda:self.clock,sleep=self.sleep))
        self.assertEqual(2,self.count)

    def test_chat_v3_requires_original_private_peer_configuration_and_preserves_legacy_shapes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);path=root/'actor.json'
            peer=PrivateFeatureState(root/'original-peer.json');peer.write(dict(explicitProducerSeam=True),None)
            value=self.config|dict(picoFeatureObserverVersion=3,area='chat',peerConfig=str(peer.path))
            path.write_text(json.dumps(value));path.chmod(0o600);self.assertEqual(value,configuration(path))
            for change in (dict(picoFeatureObserverVersion=2),dict(peerConfig='relative'),dict(peerConfig=True),dict(readerToken='x'*64)):
                path.write_text(json.dumps(value|change))
                with self.assertRaises((NativeUIError,OSError)):configuration(path)
            alias=root/'alias.json';alias.symlink_to(peer.path);path.write_text(json.dumps(value|dict(peerConfig=str(alias))))
            with self.assertRaises(NativeUIError):configuration(path)
            peer.path.chmod(0o644);path.write_text(json.dumps(value))
            with self.assertRaises(NativeUIError):configuration(path)

    def test_chat_route_passes_only_exact_existing_adapter_and_config_to_original_publisher_loop(self):
        self.config.update(picoFeatureObserverVersion=3,area='chat',peerConfig='/private/original-peer.json')
        adapter=object();calls=[]
        def owned(original,config,**clocks):
            calls.append((original,config,clocks));return 7
        with patch('adapters.pico4.chat_cursor_actor.run',side_effect=owned):
            self.assertEqual(7,run(adapter,self.config,monotonic=lambda:self.clock,sleep=self.sleep))
        self.assertIs(adapter,calls[0][0]);self.assertIs(self.config,calls[0][1]);self.assertEqual(1,len(calls))

    def chat_loop(self,*,late=False,closed=True):
        from adapters.pico4.chat_cursor_actor import run as run_chat
        from feature_journeys.phase_fixture import PhasePending
        binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:456',
            sessionId='c'*32,generation=0,targetFingerprint='d'*64)
        peer={**binding,'processIdentity':'456:789','sessionId':'e'*32}
        config=self.config|dict(picoFeatureObserverVersion=3,area='chat',peerConfig='/private/original-peer.json')
        parent=dict(picoChatCompositionVersion=6,runId='a'*32,fixtureUrl=self.owner['fixtureUrl'],binding=binding,
            peerBinding=peer,peerOriginBasis='native-configured-metadata-only',phase='prepared',completedSteps=0)
        calls=[];stop=[]
        actor=SimpleNamespace(closed=False,failed=False,stop_store=SimpleNamespace(read=lambda:dict(originalStop=True) if stop else None))
        def publish():
            calls.append('publish')
            if calls.count('publish')==1:raise PhasePending('Original input pending')
            stop.append(True)
        def finish():calls.append('stop');actor.closed=closed;return dict(performed=True)
        actor.publish=publish;actor.stop_once=finish
        def acquire(target,source,peer_config):
            calls.append('acquire');self.assertEqual(config['actorToken'],source.client.token)
            self.assertEqual(Path(config['peerConfig']),peer_config.path)
            if late:self.clock=31.
            return actor
        adapter=SimpleNamespace(_chat_composition_store=lambda _target:SimpleNamespace(read=lambda:parent),
            _native_feature_observer=lambda _target:SimpleNamespace(guard=lambda:True,clock_ms=lambda:self.clock*1000),
            _chat_cursor_actor=acquire)
        return lambda:run_chat(adapter,config,monotonic=lambda:self.clock,sleep=self.sleep),calls,actor

    def test_chat_loop_keeps_one_actual_factory_owner_and_stops_without_another_publication(self):
        execute,calls,actor=self.chat_loop();self.assertEqual(0,execute())
        self.assertEqual(['acquire','publish','publish','stop'],calls);self.assertTrue(actor.closed)

    def test_chat_loop_refuses_late_acquisition_and_close_ack_without_actual_owner_closed_state(self):
        execute,calls,_actor=self.chat_loop(late=True)
        with self.assertRaises(NativeUIError):execute()
        self.assertEqual(['acquire'],calls)
        self.clock=0.;execute,calls,actor=self.chat_loop(closed=False)
        with self.assertRaises(NativeUIError):execute()
        self.assertEqual(['acquire','publish','publish','stop'],calls);self.assertFalse(actor.closed)


if __name__=='__main__':unittest.main()
