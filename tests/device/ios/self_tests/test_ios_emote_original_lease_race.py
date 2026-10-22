"""A real directory mutation inside one scan cannot qualify an inventory."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_original_lease import EmoteOriginalLease


class OriginalLeaseRaceTests(unittest.TestCase):
    def test_new_actual_entry_after_scandir_before_directory_final_stat_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);original=root/'original';original.write_bytes(b'original')
            original.chmod(0o600);created=root/'scan-race';events=[];scan=os.scandir
            class ActualScan:
                def __init__(self,path):self.path=path;self.actual=scan(path)
                def __enter__(self):return self.actual.__enter__()
                def __exit__(self,*args):
                    result=self.actual.__exit__(*args)
                    if Path(self.path)==root and not events:
                        events.append('created-after-enumeration');created.write_bytes(b'new actual entry');created.chmod(0o600)
                    return result
            with patch('ios.adapters.emote_original_lease.os.scandir',side_effect=ActualScan):
                with self.assertRaises(NativeUIError):EmoteOriginalLease(root,[])
            self.assertEqual(['created-after-enumeration'],events)
            self.assertEqual(b'original',original.read_bytes());self.assertTrue(created.exists())
