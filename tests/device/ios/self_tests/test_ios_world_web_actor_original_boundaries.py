"""Actor memo boundaries are exact durable originals, never requested effects.

Actual Node, owned loopback transport and original private files execute;
native/Qt/WK/SDK and their clocks remain declared models in these cases.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from ios.self_tests.world_web_actor_scene_fixture import actor_scene


class WorldWebActorOriginalBoundariesTests(unittest.TestCase):
    def test_same_actual_boundary_copies_outward_and_does_not_query_or_recompute(self):
        with actor_scene() as (whole,actor,_observer,owner,original,_publisher):
            queries=deepcopy([whole.sdk.counts,actor.sdk.counts])
            with patch.object(owner,'_validate_original',wraps=owner._validate_original) as literal:
                expected=owner.validate_original(original);changed=owner.validate_original(original);changed['ticket']='outward-only'
                self.assertEqual(expected,owner.validate_original(original));self.assertEqual(1,literal.call_count)
            self.assertEqual(queries,[whole.sdk.counts,actor.sdk.counts])
    def test_new_actual_census_and_changed_parser_cannot_inherit_original_success(self):
        with actor_scene() as (_whole,_actor,_observer,owner,original,_publisher):
            with patch.object(owner,'_validate_original',wraps=owner._validate_original) as literal:
                expected=owner.validate_original(original)
                with scope(fresh=True) as reads:
                    self.assertEqual(expected,owner.validate_original(original));self.assertTrue(reads)
                self.assertEqual(2,literal.call_count)
                with patch.object(owner,'qualification',side_effect=NativeUIError('Declared changed qualification parser')):
                    with self.assertRaises(NativeUIError):owner.validate_original(original)
    def test_actual_source_and_observer_append_invalidates_result_without_retiming_history(self):
        with actor_scene() as (_whole,_actor,observer,owner,original,_publisher):
            with patch.object(owner,'_validate_original',wraps=owner._validate_original) as literal:
                expected=owner.validate_original(original);observer.capture()
                self.assertEqual(expected,owner.validate_original(original));self.assertEqual(2,literal.call_count)
    def test_equal_byte_original_inode_replacement_refuses_before_cached_success(self):
        with self.assertRaises(NativeUIError),actor_scene() as (_whole,_actor,_observer,owner,original,_publisher):
            owner.validate_original(original);source=owner.source
            frame=source.frame(source.state['records'][-1]);path=source.parts.snapshot.paths(frame['nativeSnapshot'])[0]
            replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
            owner.validate_original(original)


if __name__=='__main__':unittest.main()
