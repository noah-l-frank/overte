"""Pico owning selection of no-build VR Home geometry counterexamples."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_pico_tablet_home import PicoTabletHomeTests
if __name__=='__main__':unittest.main()
