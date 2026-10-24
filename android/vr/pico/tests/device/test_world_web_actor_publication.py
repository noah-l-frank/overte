"""Independent World source publications and the normal Parent activation gap."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device')]
from self_tests.test_pico_world_web_actor_publication import WorldWebActorPublicationTests
if __name__=='__main__':unittest.main()
