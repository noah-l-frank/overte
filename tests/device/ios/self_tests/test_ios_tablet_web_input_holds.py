"""Actual typed UIKit2 control targets retain native holders, not WK aliases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from ios.adapters.tablet_web_quiet import input_holds
from ios.self_tests.test_ios_uikit_input import packet as wk_packet
from ios.self_tests.test_ios_uikit_input_controls import packet as control_packet


class TabletInputHoldTests(unittest.TestCase):
    def test_source_qualified_native_UIButton_is_retained_separately_from_actual_WK_view(self):
        value,_buttons=control_packet();original=deepcopy(value);actual=input_holds(value)
        target=value['targets'][0]['view'];chosen=[row for row in actual if row['resource']=='panel:tablet-uikit-'+target]
        self.assertEqual(1,len(chosen));self.assertEqual('native-holder',chosen[0]['kind']);self.assertEqual(original,value)
        wk=wk_packet(phase='ended');held=input_holds(wk);target=wk['targets'][0]['view']
        self.assertEqual('wk-view',next(row for row in held if row['resource']=='panel:tablet-uikit-'+target)['kind'])


if __name__=='__main__':unittest.main()
