"""A retained original raw world-frame prefix survives later real PNG reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.self_tests import test_ios_emote_restoration_frames as restoration_boundary
from ios.self_tests import test_ios_emote_retirement_prefixes as prefix_boundary


class RestorationPrefixTests(unittest.TestCase):
    assert_historical=prefix_boundary.RetirementPrefixTests.assert_historical

    def test_raw_world_frame_prefix_is_read_only_while_live_orphans_and_modified_originals_still_fail(self):
        f=restoration_boundary.RawFramesTests();f.setUp();self.addCleanup(f.doCleanups)
        owner=f.owner();first=owner.capture('initial');old=owner.store.read();owner.capture('initial');current=owner.store.read()
        archive=lambda value:IOSEmoteRestorationFrames.archive(value,store=owner.store,root=owner.root,binding=owner.binding,
            run=owner.run,role=owner.role,lock=owner.lock)
        historical=archive(old)
        for mutate in (lambda:historical.capture('initial'),lambda:historical.remember('nativeStart',{}),
                       lambda:historical.owner('ios-'+'f'*32),lambda:historical.journal_native(object())):
            with self.assertRaises(NativeUIError):mutate()
        self.assert_historical(owner,archive,old,first,current,f.owner)
