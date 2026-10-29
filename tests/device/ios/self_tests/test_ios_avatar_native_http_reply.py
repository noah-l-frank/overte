"""Original declared native POST responses remain independent per request.

Actual native handlers and the literal Source HTTP validator execute. No
Feature/factory result, AFC getter, original timestamps or scope is replaced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from unittest.mock import patch
from urllib.request import Request
from ios.adapters.feature_observation import send_original_command
from ios.adapters import feature_observation
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor
from ios.self_tests.avatar_installed_native_channels import NativeHTTPReply
from ios.self_tests import test_ios_avatar_prepare_composed as preparation


class AvatarNativeHTTPReplyTests(unittest.TestCase):
    retain_originals=True
    @classmethod
    def setUpClass(cls):preparation.AvatarPrepareComposedTests.setUpClass()
    @classmethod
    def tearDownClass(cls):preparation.AvatarPrepareComposedTests.tearDownClass()

    def test_real_native_two_requests_before_first_read_keep_original_echo_and_reject_malformed_raw_reply(self):
        f=NativeInstalledFrontdoor(self);native=f.domain.natives['primary'];origin=native.target['testBuild']['fixtureOrigin']
        first=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-native-observe')
        second=dict(schemaVersion=1,commandId='ios-'+'b'*32,action='feature-native-observe')
        def request(value):return Request(origin+'/e2e-client-command.json',data=json.dumps(value).encode(),method='POST')
        a=native.post(request(first),5);b=native.post(request(second),5)
        self.assertIsNot(a,b);self.assertEqual(second,json.loads(native.echo))
        self.assertEqual(first,json.loads(a.read(4097)));self.assertEqual(second,json.loads(b.read(4097)))
        # Real source validation must still reject foreign echo and non-200
        # status. Fault only the raw HTTP response, never its validator.
        for response in (NativeHTTPReply(200,json.dumps(second).encode()),NativeHTTPReply(503,json.dumps(first).encode())):
            with patch.object(feature_observation,'post_request',return_value=response):
                with self.assertRaises(ValueError):send_original_command(origin,first,4096)
        with patch.object(feature_observation,'post_request',return_value=a):
            send_original_command(origin,first,4096)
        self.assertEqual([first,second],native.commands[-2:])


if __name__=='__main__':unittest.main()
