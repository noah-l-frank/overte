"""Original selected Android SDK profile; never a Save/export success receipt."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import time
from adapters.native_feature_observation import integer,need,number
from adapters.normal_ui import NativeUIError


def profile(sdk):
    need(type(sdk) is str and sdk.isascii() and sdk.isdecimal() and str(int(sdk))==sdk and 26<=int(sdk)<=1000)
    return dict(snapshotAndroidPlatformVersion=1,sdk=int(sdk),
        saveBackend='media-store' if int(sdk)>=29 else 'document-picker',savePermission='not-required')


class PhoneSnapshotPlatform:
    def __init__(self,read_sdk,guard,clock_ms,*,monotonic=time.monotonic):
        need(all(callable(fn) for fn in (read_sdk,guard,clock_ms,monotonic)))
        self.read_sdk,self.guard,self.clock_ms,self.monotonic=read_sdk,guard,clock_ms,monotonic
        self.original=None

    def read(self):
        try:
            need(self.guard() is not False);start=self.monotonic();need(number(start,0,1e15))
            requested=self.clock_ms();need(integer(requested,1));raw=self.read_sdk();value=profile(raw)
            need(self.guard() is not False);captured=self.clock_ms();now=self.monotonic()
            need(integer(captured,requested) and captured-requested<=1500 and number(now,start,1e15) and now-start<=1.5)
            if self.original is not None:need(value==self.original)
            self.original=dict(value)
            return dict(requestedEpochMs=requested,capturedEpochMs=captured,source=value)
        except Exception:raise NativeUIError('Original Android Snapshot platform profile is unavailable or changed') from None
