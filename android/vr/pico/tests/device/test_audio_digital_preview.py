"""Normal Pico recipe joins independently retained digital PC preview originals.

Native/Android/media/readiness sources are explicit unit-test models; no
compiler, audio service, client, microphone, speaker or device is started.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_audio_recipe_evidence import AudioRecipeEvidenceTests

if __name__=='__main__':unittest.main()
