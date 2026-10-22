"""Bounded production retry/real key ACK; other native endpoints are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_operation import operation
from ios.adapters.emote_scene_operation import ScenePending,retry_scene
from ios.adapters.emote_scene_proof import ack as real_ack
from ios.self_tests import test_ios_emote_scene_gate as fixture


class SceneOperationTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.SceneGateTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.flow=self.h.f.flow;self.gate=self.h.gates['primary'];self.events=[]
        self.flow.state=dict(phaseInstance=self.h.instance);self.flow.load=lambda:None;self.flow.phase=self.h.f.target.phase
        self.flow.components=lambda:{};self.flow.keys=lambda _parts:self.h.f.keys.owner();self.gate.validate_ack=real_ack
        self.proof=self.h.endpoint('primary')
    def operation(self):
        gate,proof,events,ticket=self.gate,self.proof,self.events,self.h.ticket
        @operation(30)
        @retry_scene
        def actual(flow):
            with flow.held():
                gate.retain('own','initial',ticket,proof)
                try:ready=gate.ready('initial',ticket)
                except NativeUIError:raise ScenePending(gate,'initial',ticket) from None
                events.append(('normal-camera-allowed',ready['nativeEndpoint']['sequence']))
                return ready
        return actual
    def test_wait_releases_lease_and_real_current_keys_native_ack_precedes_camera(self):
        calls=[]
        def waiting(seconds):
            self.assertIsNone(self.flow.lock._owner);self.assertIsNone(self.flow.primary_lock._owner)
            self.assertEqual([],self.events);calls.append(seconds);self.h.write('actor','initial')
            self.h.f.target.domain.sleep(seconds)
        self.flow.sleep=waiting;result=self.operation()(self.flow)
        self.assertEqual(1,len(calls));self.assertEqual(1,len(self.events))
        self.assertGreater(result['nativeEndpoint']['sequence'],self.proof['packet']['sequence'])
        with self.flow.lock.held():self.gate.decode(self.gate.store.read())
        self.assertIsNone(self.flow.lock._owner)
    def test_missing_other_initial_never_changes_camera_and_wait_cannot_restart_deadline(self):
        start=self.flow.monotonic();samples=[]
        def waiting(seconds):
            self.assertIsNone(self.flow.lock._owner);samples.append(self.flow.deadline)
            self.h.f.target.domain.sleep(31)
        self.flow.sleep=waiting
        with self.assertRaises(NativeUIError):self.operation()(self.flow)
        self.assertEqual([],self.events);self.assertEqual([start+30],samples);self.assertEqual([],self.gate.state['peer'])
        self.assertIsNone(self.flow.lock._owner)
