"""Actual owned protected GET and independent HTTPS receipt; declared clock.

No credentials, token, expected response factory or timestamp retiming. The
actual producer class is chosen before the original Native constructor.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import time
import unittest
from unittest.mock import patch
from adapters.native_account_probe import NativeAccountProbe,AccountProbeOwner,OwnedAccountProbe
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters import feature_observation
from ios.self_tests import authentication_native_boundary as sdk
from ios.self_tests import test_ios_authentication_journey as journey
from ios.self_tests.test_ios_avatar_private_status_capture_order import ForwardNative


class AvatarProtectedProbeRequestOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):journey.IOSAuthenticationJourneyTests.setUpClass()
    @classmethod
    def tearDownClass(cls):journey.IOSAuthenticationJourneyTests.tearDownClass()

    def test_real_owned_protected_GET_shares_exact_send_request_time_then_completes_and_releases_original(self):
        fixture=journey.IOSAuthenticationJourneyTests();self.addCleanup(fixture.doCleanups)
        # Explicit raw clock producer is selected BEFORE any original binding.
        with patch.object(sdk,'Native',ForwardNative):fixture.setUp()
        n=fixture.native;ticket='0'*32;fixture.client.activate(ticket)
        store=PrivateFeatureState(fixture.root/'focused-account-probe-owner.json')
        binding=dict(n.scope(),processIdentity=str(n.pid))
        owner=AccountProbeOwner(store,binding,lambda:n.running,ios=True)
        def send(command):
            if command['operation']=='read':self.assertEqual(command,store.read()['probe'])
            feature_observation.send_original_command(n.target['testBuild']['fixtureOrigin'],command,4096)
        source=NativeAccountProbe(send,lambda:json.dumps(n.probe_value),n.epoch,lambda:n.running,n.pid,
            intent=owner.intent,ios=True,monotonic=time.monotonic,sleep=time.sleep)
        owned=OwnedAccountProbe(source,owner);packet=owned.acquire(journey.RUN,ticket)
        self.assertEqual(packet['requestedEpochMs'],packet['source']['sentEpochMs'])
        self.assertLessEqual(packet['source']['sentEpochMs'],packet['source']['completedEpochMs'])
        self.assertLessEqual(packet['source']['completedEpochMs'],packet['capturedEpochMs'])
        for stamp in (packet['requestedEpochMs'],packet['capturedEpochMs'],packet['source']['sentEpochMs'],packet['source']['completedEpochMs']):
            self.assertIs(type(stamp),int)
        # Compare the actual independent provider receipt for THIS nonce.
        proof=fixture.provider.proof(journey.RUN,ticket,packet['requestId'])
        self.assertEqual(packet['source']['httpStatus'],proof['status'])
        self.assertEqual(401,proof['status']);self.assertFalse(packet['source']['tokenAttached'])
        result=owned.release();self.assertEqual(dict(inflight=False,responseBytes=0,credentialBytes=0,released=True),result['source'])
        self.assertIsNone(store.read())
        self.assertEqual(1,sum(row['action']=='feature-account-probe' and row['operation']=='read' for row in n.commands))


if __name__=='__main__':unittest.main()
