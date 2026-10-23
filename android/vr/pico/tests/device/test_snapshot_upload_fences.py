"""Narrow normal Upload admission/recovery; no giant Capture/Save replay."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_snapshot_upload_owner import (
    SnapshotUploadAdmissionTests,SnapshotUploadContextTests,
    SnapshotUploadOriginalsTests,SnapshotUploadFenceTests,
)


if __name__=='__main__':unittest.main()
