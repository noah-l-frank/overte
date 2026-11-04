"""Exact canonical numeric lengths through the shared actual byte-budget API."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import random
import struct
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_namespace_bill as module
from adapters.script_journey.history import canonical


class CanonicalScalarSizeTests(unittest.TestCase):
    def values(self):
        values=[None,True,False,0,1,-1,0.,-0.,1e-308,5e-324,1.7976931348623157e308]
        for power in (1,10,53,63,255,1024,2048):values.extend((2**power,-2**power,10**power,-10**power))
        source=random.Random(433)
        for _index in range(4096):
            value=struct.unpack('!d',source.getrandbits(64).to_bytes(8,'big'))[0]
            if math.isfinite(value):values.append(value)
        return values

    def test_original_encoder_lengths_match_ieee_floats_integer_boundaries_and_exact_primitives(self):
        values=self.values();self.assertGreater(len(values),4000)
        for value in values:
            with self.subTest(value=value):self.assertEqual(len(canonical(value)),module.canonical_size(value))
        document={'originalValues':values,'quoted':'\\\"\n Ω \U0001f600','nested':[None,False,-0.]}
        self.assertEqual(len(canonical(document)),module.canonical_size(document))

    def test_same_exact_and_one_byte_short_budget_boundaries_use_unchanged_json_bytes(self):
        for value in (self.values(),{'numbers':[0,-0.,2**2048,-2**2048,1.25e-100],'label':'original'}):
            size=len(canonical(value));self.assertEqual(size,module.canonical_size(value,size))
            with self.assertRaises(NativeUIError):module.canonical_size(value,size-1)

    def test_nonfinite_values_keep_original_encoder_failure_instead_of_counting_invalid_json(self):
        for value in (float('nan'),float('inf'),-float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):canonical(value)
                with self.assertRaises(ValueError):module.canonical_size({'value':value})

    def test_exact_finite_scalar_budget_work_does_not_invoke_the_json_encoder(self):
        values=self.values();expected=len(canonical(values))
        with patch.object(module,'canonical',side_effect=AssertionError('No per-scalar encoder callback')):
            self.assertEqual(expected,module.canonical_size(values))


if __name__=='__main__':unittest.main()
