"""Atomic shared model time for independent Tablet host fixture processes.

This is not a physical/native clock. Serialized increments prevent one host
producer from overwriting time advanced by another producer; no original
packet or acquisition deadline is rewritten.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math


def advance(clock,seconds):
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0:
        raise ValueError('Invalid Tablet host model clock increment')
    with clock.get_lock():
        clock.value+=seconds
        return clock.value
