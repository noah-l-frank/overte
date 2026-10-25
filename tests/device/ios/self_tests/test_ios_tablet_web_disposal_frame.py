"""Typed disposal originals stay separate from complete app/page facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_tablet_web_source_owner as sources


class TabletDisposalFrameTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.TabletWebSourceOwnerTests();self.fixture.setUpClass();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def test_actual_native_frame_read_does_not_invent_complete_app_or_page_facts(self):
        f=self.fixture;source=f.prepare();parts,row=f.capture(source);historical=f.owner(historical=True)
        with patch('ios.adapters.tablet_web_source_owner.derive',side_effect=AssertionError('Page facts require a separate full join')):
            actual,frame,prefix=historical.frame_at(source.state['records'][-1])
            self.assertEqual(row,actual);self.assertEqual(parts,frame);self.assertEqual([parts],prefix)
            with self.assertRaises(AssertionError):historical.facts_at(source.state['records'][-1],sources.ORIGINS)
        with self.assertRaises(NativeUIError):source.frame_at(source.state['records'][-1])


if __name__=='__main__':unittest.main()
