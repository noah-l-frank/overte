"""Same private Browser component and rootless marker guards; no whole claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))

CASE_NAMES=('self_tests.test_pico_browser_directory_archive.PicoBrowserDirectoryArchiveTests.test_existing_original_return_capture_archive_and_actual_host_close_use_the_same_graph', 'self_tests.test_pico_browser_directory_archive.PicoBrowserDirectoryArchiveTests.test_rootless_pending_file_directory_or_symlink_blocks_without_creating_a_state_namespace')

def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)

if __name__=='__main__':unittest.main()
