"""Interrupted read resumes original normal setup without a second load/input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from ios.self_tests.test_ios_world_web_scope import WorldWebScopeTests


class WorldWebScopeResumeTests(unittest.TestCase):
    def test_failed_passive_view_read_keeps_original_load_uuid_and_all_normal_input_intentions(self):
        fixture=WorldWebScopeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        scope,domain=fixture.scope,fixture.domain;capture=scope.capture
        def failing(label,*args):
            if label=='view-ready':raise OSError('Modeled lost passive source before view-ready')
            return capture(label,*args)
        with patch.object(scope,'capture',side_effect=failing),self.assertRaises(OSError):scope.prepare()
        ownership=deepcopy(scope.state['fileOwnership']);marker=deepcopy(scope.state['admission']);actions=list(domain.io.actions)
        admitted=scope.prepare();self.assertEqual(marker,admitted);self.assertEqual(actions,domain.io.actions)
        self.assertEqual(ownership,scope.state['fileOwnership']);self.assertEqual(1,len([frame for frame in scope.frames if frame['label']=='marker-loaded']))
        self.assertEqual(1,domain.io.actions.count('script-file.confirm'))
        domain.paint();scope.admit_rendered();scope.cleanup();self.assertFalse(domain.files.root.exists())


if __name__=='__main__':unittest.main()
