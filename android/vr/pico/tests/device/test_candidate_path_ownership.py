"""Original candidate path topology, live callbacks and sticky refusal."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'tests/device'))


def load_tests(loader, _tests, _pattern):
    return loader.loadTestsFromName(
        'self_tests.test_pico_candidate_path_ownership.CandidatePathOwnershipTests')


if __name__ == '__main__':
    unittest.main()
