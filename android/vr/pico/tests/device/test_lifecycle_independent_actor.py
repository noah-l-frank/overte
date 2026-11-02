"""Independent original Actor stage and canonical retained-file responsibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.test_lifecycle_independent_actor import LifecycleIndependentActorTests
import test_lifecycle_readonly_factory as source_fixture
from test_lifecycle_actor_factory import LifecycleActorFactoryTests
from test_lifecycle_actor_composition import LifecycleActorCompositionTests


class LifecycleActorOwnershipTests(unittest.TestCase):
    setUp=source_fixture.LifecycleReadOnlyFactoryTests.setUp
    retained=source_fixture.LifecycleReadOnlyFactoryTests.process_original_keeps_cleanup_owned

    def test_actor_root_retains_canonical_cleanup_responsibility(self):
        self.retained('lifecycle-actor-originals.json')

    def test_actor_orphan_retains_canonical_cleanup_responsibility_without_root(self):
        self.retained('lifecycle-actor-originals.json.frame-000.json')

    def test_actor_staging_and_pending_orphans_block_cleanup_without_main_root(self):
        for name in ('lifecycle-actor-in-progress.json','lifecycle-actor-in-progress.json.frame-000.json',
                'lifecycle-actor-in-progress.json.pending-'+'a'*32,'lifecycle-actor-originals.json.pending-'+'b'*32):
            with self.subTest(name=name):
                self.setUp()
                self.retained(name)
                root=self.adapter._lifecycle_world_store(self.transport.target).path.parent
                self.assertFalse((root/'lifecycle-actor-originals.json').exists())


if __name__=='__main__':unittest.main()
