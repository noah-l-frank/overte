"""Original host execution policy; never a native clock/sample attestation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import threading
import time

from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import need
from adapters.pico4.browser_operation_protocol import budget


class BrowserExecutionBudget:
    def __init__(self, value, *, maximum=120, monotonic=time.monotonic):
        need(type(maximum) is int and maximum in (60, 120) and callable(monotonic))
        budget(value, maximum)
        self.value = deepcopy(value)
        self.original = self._original = (json_digest(self.value), maximum, monotonic,
            host_identity(), threading.get_ident(), value['startedMonotonic'], value['deadlineMonotonic'])
        self.monotonic = self._monotonic = monotonic
        self.previous = self._previous = value['startedMonotonic']
        self.failed = False
        self.check()

    def check(self):
        try:
            need(not self.failed and self.original is self._original
                and self.monotonic is self._monotonic is self.original[2]
                and json_digest(self.value) == self.original[0]
                and host_identity() == self.original[3] and threading.get_ident() == self.original[4]
                and self.previous == self._previous)
            now = self.monotonic()
            need(type(now) in (int, float) and self.previous <= now < self.original[6])
            self.previous = self._previous = now
            return now
        except BaseException:
            self.failed = True
            raise

    def same(self, value):
        try:
            need(json_digest(value) == self.original[0])
            return self.check()
        except BaseException:
            self.failed = True
            raise
