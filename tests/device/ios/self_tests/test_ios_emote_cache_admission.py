"""A modeled cleanup cannot advertise support across a known native cache gap."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_configuration as source


class EmoteCacheAdmissionTests(unittest.TestCase):
    def test_partial_emotes_configuration_refuses_complete_triple_before_any_target_setup(self):
        with patch.object(source,'configuration',return_value=dict(areas=['emotes'])),patch.object(source,'scripts_configuration') as setup:
            with self.assertRaises(NativeUIError):source.capabilities({})
            setup.assert_not_called()

    def test_mixed_configuration_cannot_silently_hide_missing_mandatory_emotes(self):
        with patch.object(source,'configuration',return_value=dict(areas=['scripts','emotes'])),patch.object(source,'scripts_configuration') as setup:
            with self.assertRaises(NativeUIError):source.capabilities({})
            setup.assert_not_called()

    def test_other_complete_source_areas_and_readable_emotes_operations_are_preserved(self):
        self.assertIn('emotes',source.AREAS);self.assertIn('feature.emotes.cleanup',source.OPERATIONS)
        self.assertIn(4,source.READS)
        with patch.object(source,'configuration',return_value=dict(areas=['scripts','graphics','create'])),patch.object(source,'scripts_configuration',return_value={}):
            actual=source.capabilities({})
        self.assertEqual(sorted('feature.'+area+'.'+kind for area in ('scripts','graphics','create') for kind in ('act','observe','cleanup')),actual)


if __name__=='__main__':unittest.main()
