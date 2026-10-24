"""Fresh readonly Lifecycle triples, without another mutating World owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import need
from adapters.pico4 import lifecycle_source as ui,lifecycle_gesture as gesture,lifecycle_drive as drive
from adapters.pico4.lifecycle_world import PicoLifecycleWorld


class LifecycleReadOnlyAcquisition:
    # Reuse the exact original complete acquisition and original validators.
    # This object has no state journal, attempt list, save or input method.
    acquire=PicoLifecycleWorld.acquire
    originals=PicoLifecycleWorld.originals
    now=PicoLifecycleWorld.now
    fresh_current=PicoLifecycleWorld.fresh_current

    def __init__(self,world,source,axes,avatar):
        need(type(world) is PicoLifecycleWorld and type(source) is ui.PicoLifecycleSource
            and type(axes) is gesture.PicoLifecycleGesture and type(avatar) is drive.PicoLifecycleDrive)
        self.owner,self.source,self.axes,self.avatar=world,source,axes,avatar
        self.readers=(source,axes,avatar);self.run,self.binding,self.pid=world.run,deepcopy(world.binding),world.pid
        self.lock,self.monotonic=world.lock,world.monotonic
        self.guard=lambda:world.guard()
        self.last_clock=self.acquired_start=self.fresh_anchor=None
        self.control()
        need(all(reader.previous is None and reader.last_raw is None and reader.last_sha256 is None for reader in self.readers))

    def control(self):
        need(self.owner.run==self.run and self.owner.binding==self.binding and self.owner.pid==self.pid
            and self.owner.lock is self.lock and self.readers==(self.source,self.axes,self.avatar)
            and all(reader.pid==self.pid and reader.source_lock is self.lock for reader in self.readers)
            and all(reader is not original for reader,original in zip(self.readers,
                (self.owner.source,self.owner.axes,self.owner.avatar))))
        need(self.guard() is not False and all(reader.guard() is not False for reader in self.readers))

    def previous(self,original):
        """Keep the independent live cursors pinned to their saved literals."""
        self.control()
        for name,reader in (('ui',self.source),('gesture',self.axes),('drive',self.avatar)):
            if original is None:
                need(reader.previous is None and reader.last_raw is None and reader.last_sha256 is None)
            else:
                packet=self.originals(original)[name]
                prior=ui.summary(packet) if name=='ui' else packet
                need(json_digest(reader.previous)==json_digest(prior)
                    and reader.last_raw==original[name]['raw'] and reader.last_sha256==original[name]['sha256'])

    @staticmethod
    def advance(previous,current):
        ui.accept(ui.summary(previous['ui']),ui.summary(current['ui']))
        gesture.accept(previous['gesture'],current['gesture'])
        drive.continuity(previous['drive'],current['drive'])
