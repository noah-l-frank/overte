"""Bounded measurement-only marker readiness; no ordinary input or fact reuse."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time

from adapters.native_feature_observation import fresh,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_graphics_samples import PhoneGraphicsSamples,GraphicsMarkerPending

VERSION=1


class PhoneGraphicsReadiness:
    def __init__(self,samples,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(samples,PhoneGraphicsSamples) and callable(monotonic) and callable(sleep))
        self.samples,self.monotonic,self.sleep=samples,monotonic,sleep

    def read(self,ticket,after_epoch):
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.samples.lock.assert_held();current=self.monotonic()
            need(number(current,previous,1e15) and current-started<20);previous=current
        for attempt in range(16):
            bound()
            try:result=self.samples.read(ticket,after_epoch)
            except GraphicsMarkerPending:
                # The live producer proved all original sources/PNG ownership
                # and permanent native memory/file retirement before this path.
                # Corruption, foreign context, missing results and incomplete
                # cleanup have different failures and cannot enter this loop.
                self.samples.retire_marker_not_ready();bound()
                if attempt==15:break
                self.sleep(min(1,20-(previous-started)));bound();continue
            bound();fresh(result['capturedEpochMs'],self.samples.epoch_ms());bound();return result
        raise NativeUIError('Original Graphics world pixels did not reach the current challenge within the readiness budget')
