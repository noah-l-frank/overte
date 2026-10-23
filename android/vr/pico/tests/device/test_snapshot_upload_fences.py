"""Narrow normal Upload admission/recovery; no giant Capture/Save replay."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import json
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import test_snapshot_upload_owner as flow_fixture
from self_tests.test_native_feature_observation import Boundary
from adapters.native_feature_observation import validate
from adapters.normal_ui import NativeUIError
from self_tests.test_pico_snapshot_upload_owner import (
    SnapshotUploadAdmissionTests,SnapshotUploadContextTests,
    SnapshotUploadOriginalsTests,SnapshotUploadFenceTests,
)


class SnapshotUploadFixtureClockTests(unittest.TestCase):
    def test_normal_account_model_retains_actual_current_query_clock_after_long_prefix(self):
        # No warm prefix: prove its measured 10.202 s gap at the exact producer.
        case=object.__new__(flow_fixture.SnapshotUploadFlowTests)
        case.h=SimpleNamespace(producer=SimpleNamespace(outer='e'*32),clock=lambda:30202)
        case.feature=Boundary();case.token='explicit native-adoption seam';case.origin='https://localhost:1'
        command=dict(commandId='a'*32);case.observe_account(command);value=json.loads(case.account_raw)
        validate(value,'a'*32,123,30202,require_account=True)
        self.assertEqual(30202,value['requestedEpochMs']);self.assertEqual({},value['animation']);self.assertNotIn('animationFence',value)
        value['requestedEpochMs']=20000
        with self.assertRaises(NativeUIError):validate(value,'a'*32,123,30202,require_account=True)


if __name__=='__main__':unittest.main()
