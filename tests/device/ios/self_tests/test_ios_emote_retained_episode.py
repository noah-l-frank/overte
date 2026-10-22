"""Real modeled Rig ring expiry cannot erase an already immutable episode."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.emote_active_observer_fixture import ActiveObserverFixture


class RetainedEpisodeTests(unittest.TestCase):
    def test_only_exact_source_rig_and_original_override_survive_actual_active_frame_expiry(self):
        f=ActiveObserverFixture(self);observer=f.observer;observer.observe(0)
        f.native.tablet=True;f.ui.open();f.activate('play',name='Waving');f.ui.play('Waving');f.native.sleep(.25)
        observer.observe(0);episode=deepcopy(observer.state['episode']);self.assertIsNotNone(episode)
        f.ui.cancel();reader=f.rig.reader()
        for _ in range(40):reader.read(reader.sequence,require_animation_history=True)
        self.assertFalse(any(row['overrideActive'] for row in f.rig.frames))
        current=f.sources.read();observer.recover_owned_episode(episode['before'],current)
        self.assertEqual(episode,observer.state['episode'])
        # The same clip URL in a NEW actual override is not the old episode.
        f.ui.play('Waving');f.ui.cancel()
        for _ in range(40):reader.read(reader.sequence,require_animation_history=True)
        current=f.sources.read()
        with self.assertRaises(NativeUIError):observer.recover_owned_episode(episode['before'],current)
        self.assertEqual(episode,observer.state['episode'])
