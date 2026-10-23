"""Original phase-to-image ordering uses the same adapter-host clock only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_restoration import authority_precedes_image


class NavigationRestorationAuthorityClockTests(unittest.TestCase):
    def test_independent_provider_utc_cannot_reverse_actual_host_acquisition_order(self):
        phase=dict(providerReadEpochMs=1700000000050,hostAfterMonotonic=10.05)
        base=dict(before=dict(epochMs=1700000000010,monotonic=10.06))
        originals=deepcopy((phase,base));authority_precedes_image(phase,base)
        self.assertEqual(originals,(phase,base))
        phase['providerReadEpochMs']=1699999999900;phase['hostAfterMonotonic']=10.061
        with self.assertRaises(NativeUIError):authority_precedes_image(phase,base)

    def test_missing_nonfinite_or_boolean_original_host_clock_cannot_qualify(self):
        base=dict(before=dict(epochMs=1700000000010,monotonic=10.06))
        for value in (None,True,float('nan'),float('inf'),-1):
            with self.subTest(value=value),self.assertRaises(NativeUIError):
                authority_precedes_image(dict(providerReadEpochMs=1700000000000,hostAfterMonotonic=value),base)


if __name__=='__main__':unittest.main()
