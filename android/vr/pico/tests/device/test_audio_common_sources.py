"""Original Common Audio host sources; Native/media/OS are declared models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
CASE_NAMES=('self_tests.test_pico_audio_common_primary.PrimaryTests', 'self_tests.test_pico_audio_common_files.FileTests', 'self_tests.test_pico_audio_common_flow.FlowTests')
def load_tests(loader,_tests,_pattern):return loader.loadTestsFromNames(CASE_NAMES)
if __name__=='__main__':unittest.main()
