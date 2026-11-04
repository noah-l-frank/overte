"""Browser fixture clock born in the original actual host context.

Reuses the Lifecycle host context. Product, candidate, Qt and GPU producers
remain declared models; this clock does not qualify any of their effects.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from self_tests.pico_lifecycle_host_model import OriginalHostModel
from adapters.native_feature_observation import need


class BrowserHostClock(OriginalHostModel):
    def __init__(self):
        super().__init__();self.last_tick=None

    def tick(self):
        # Existing model producers require advancing millisecond frames. Wait
        # for an actual host millisecond instead of inventing elapsed time.
        with self.gui_lock:
            current=self.epoch()
            need(self.last_tick is None or type(self.last_tick) is int and 1<=self.last_tick<=current)
            while self.last_tick is not None and current<=self.last_tick:
                self.sleep(.001);current=self.epoch()
                need(current>=self.last_tick)
            self.last_tick=current
            return current
