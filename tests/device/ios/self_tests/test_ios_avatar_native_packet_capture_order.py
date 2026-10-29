"""Actual native/account decoder over a producer chosen before construction.

No retained timestamps, Source guards, credentials or factory outcomes change.
The deterministic forward clock exposes early enclosing-frame capture.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation
from ios.adapters import feature_observation
from ios.self_tests.test_ios_avatar_private_status_capture_order import ForwardNative


class AvatarNativePacketCaptureOrderTests(unittest.TestCase):
    def test_actual_native_reader_requires_account_with_all_nested_samples_before_final_enclosing_capture(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        root=Path(directory.name);root.chmod(0o700)
        native=ForwardNative(root,'https://controlled.invalid',None);self.addCleanup(native.close)
        def send(command):
            with patch.object(feature_observation,'post_request',side_effect=native.post):
                feature_observation.send_original_command('http://controlled.invalid:49121',command,4096)
        reader=NativeFeatureObservation(send,native.feature.original,native.epoch,lambda:native.running,native.pid,ios=True)
        value=reader.read(0,require_account=True)
        account=value['account']['observation']
        for stamp in (value['requestedEpochMs'],value['capturedEpochMs'],account['capturedEpochMs'],
                      value['animationFence']['requestedEpochMs']):self.assertIs(type(stamp),int)
        self.assertEqual(value['requestedEpochMs'],value['animationFence']['requestedEpochMs'])
        self.assertLessEqual(value['requestedEpochMs'],account['capturedEpochMs'])
        self.assertLessEqual(account['capturedEpochMs'],value['capturedEpochMs'])
        self.assertLessEqual(value['animationFence']['requestedEpochMs'],value['capturedEpochMs'])
        self.assertEqual(native.pid,value['processId']);self.assertFalse(value['account']['loggedIn'])
        self.assertEqual(1,len(native.commands));self.assertEqual(value['requestId'],native.commands[0]['commandId'])
        self.assertEqual(1,reader.sequence)


if __name__=='__main__':unittest.main()
