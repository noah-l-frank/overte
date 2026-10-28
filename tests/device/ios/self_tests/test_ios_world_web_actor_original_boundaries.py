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


    def test_prior_unrelated_mutable_wal_read_does_not_become_decoder_operand(self):
        from adapters.normal_feature_state import PrivateFeatureState
        with actor_scene() as (whole,actor,_observer,owner,original,_publisher):
            metadata=PrivateFeatureState(actor.root/'world-web-mutable-feature-test.json')
            cleaning=dict(phase='cleaning');cleaned=dict(phase='cleaned')
            metadata.write(cleaning,None)
            queries=deepcopy([whole.sdk.counts,actor.sdk.counts])
            with scope(fresh=True) as reads:
                self.assertEqual(cleaning,metadata.read())
                with patch.object(owner,'_validate_original',wraps=owner._validate_original) as literal:
                    expected=owner.validate_original(original)
                    original_inode=metadata.path.stat().st_ino
                    metadata.write(cleaned,cleaning)
                    self.assertNotEqual(original_inode,metadata.path.stat().st_ino)
                    self.assertEqual(expected,owner.validate_original(original))
                    self.assertEqual(1,literal.call_count)
                self.assertIn(metadata.path,reads)
                self.assertIn(owner.store.path,reads)
            self.assertEqual(queries,[whole.sdk.counts,actor.sdk.counts])

    def test_wal_actually_read_by_decoder_remains_inode_pinned_after_normal_cas(self):
        from adapters.normal_feature_state import PrivateFeatureState
        with actor_scene() as (_whole,actor,_observer,owner,original,_publisher):
            metadata=PrivateFeatureState(actor.root/'world-web-mutable-feature-test.json')
            cleaning=dict(phase='cleaning');cleaned=dict(phase='cleaned')
            metadata.write(cleaning,None);literal=owner._validate_original
            def decoder(value):
                self.assertEqual(cleaning,metadata.read())
                return literal(value)
            with scope(fresh=True),patch.object(owner,'_validate_original',side_effect=decoder) as actual_decoder:
                owner.validate_original(original)
                old_inode=metadata.path.stat().st_ino;metadata.write(cleaned,cleaning)
                self.assertNotEqual(old_inode,metadata.path.stat().st_ino)
                with self.assertRaises(NativeUIError):owner.validate_original(original)
                self.assertEqual(1,actual_decoder.call_count)


    def test_fresh_census_same_body_inode_cas_cannot_replace_prior_original_pins(self):
        from adapters.normal_feature_state import PrivateFeatureState
        with actor_scene() as (whole,actor,_observer,owner,original,_publisher):
            metadata=PrivateFeatureState(actor.root/'world-web-mutable-feature-test.json')
            body=dict(phase='cleaning',declaredMetadataOnly=True);metadata.write(body,None)
            queries=deepcopy([whole.sdk.counts,actor.sdk.counts])
            literal=owner._validate_original;completed=[]
            def decoder(value):
                metadata.read()  # An actual operand, without a value fault.
                result=literal(value)
                completed.append(deepcopy(result))
                return result
            # The identical decoder callable spans both censuses, keeping the
            # original cache key. Only actual read-set identity and file inode
            # change; no second parser/guard mutation may mask this fault.
            with patch.object(owner,'_validate_original',side_effect=decoder) as actual_decoder:
                with scope(fresh=True) as first_reads:
                    expected=owner.validate_original(original)
                    self.assertIn(metadata.path,first_reads)
                old_inode=metadata.path.stat().st_ino;old_bytes=metadata.path.read_bytes()
                metadata.write(deepcopy(body),body)
                self.assertNotEqual(old_inode,metadata.path.stat().st_ino)
                self.assertEqual(old_bytes,metadata.path.read_bytes())
                with scope(fresh=True) as second_reads:
                    self.assertIsNot(first_reads,second_reads)
                    with self.assertRaises(NativeUIError):owner.validate_original(original)
                    self.assertEqual(2,actual_decoder.call_count)
                    self.assertEqual([expected,expected],completed)
                    self.assertIn(metadata.path,second_reads)
                    # A refused refresh must not first install new pins and
                    # then raise. The same census must still refuse a cached
                    # success on the next call, without another mutation.
                    with self.assertRaises(NativeUIError):owner.validate_original(original)
                    self.assertEqual(3,actual_decoder.call_count)
                    self.assertEqual([expected,expected,expected],completed)
            self.assertEqual(queries,[whole.sdk.counts,actor.sdk.counts])



if __name__=='__main__':unittest.main()
