"""A separate filesystem scale case, not a live Browser or whole-run verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from self_tests import test_chat_archive_directories as existing


class DirectoryArchiveScaleTests(unittest.TestCase):
    def test_989_actual_originals_fit_the_unchanged_atomic_move_window(self):
        class Large(existing.ChatArchiveDirectoryTests):
            SOURCE_FILES=989
            LITERAL='x'*6000
        case=Large('test_complete_copies_and_original_phase_precede_one_move_then_existing_artifact_unlink')
        case.setUp();self.addCleanup(case.doCleanups)
        case.test_complete_copies_and_original_phase_precede_one_move_then_existing_artifact_unlink()


if __name__=='__main__':unittest.main()
