"""Historical decoder reuse keeps actual graph and current delivery guards."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.self_tests.world_web_actor_scene_fixture import actor_scene


class WorldWebRetirementOriginalsTests(unittest.TestCase):
    def test_copied_historical_result_is_scoped_and_fresh_read_membership_replays_actual_files(self):
        with actor_scene() as (_whole,_actor,_observer,retirement,original,publisher):
            decode=retirement._validate_original
            with patch.object(retirement,'_validate_original',wraps=decode) as actual:
                with retirement.publication_round(publisher):
                    a=retirement.validate_original(original);a['scene']['remaining'].clear();a['retirement']['quiet'].clear()
                    b=retirement.validate_original(original)
                    self.assertEqual(['native-process-resources'],b['scene']['remaining']);self.assertTrue(b['retirement']['quiet'])
                    self.assertEqual(0,actual.call_count) # warmed by the real cleanup original
                    with read_scope(fresh=True) as paths:
                        retirement.validate_original(original)
                        retained=set(paths);self.assertEqual(1,actual.call_count)
                        retirement.validate_original(original)
                        self.assertEqual(1,actual.call_count);self.assertEqual(retained,paths)
                    self.assertEqual(1,actual.call_count);self.assertTrue(paths)
            with retirement.original_round():
                # The enclosing original round is still the same API here.
                self.assertEqual(b,retirement.validate_original(original))

    def test_changed_original_state_candidate_context_and_parent_inode_cannot_use_warm_result(self):
        replaced=False
        with self.assertRaises(NativeUIError):
            with actor_scene() as (_whole,_actor,observer,retirement,original,publisher):
                with retirement.publication_round(publisher):
                    retirement.validate_original(original)
                    altered=deepcopy(original);altered['owner']['role']='foreign'
                    with self.assertRaises(NativeUIError):retirement.validate_original(altered)
                    before=deepcopy(retirement.state);retirement.state['quiet']=retirement.state['quiet'][:2]
                    with self.assertRaises(NativeUIError):retirement.validate_original(original)
                    retirement.state=before
                    guard=observer.source.guard;observer.source.guard=lambda:False
                    with self.assertRaises(NativeUIError):retirement.validate_original(original)
                    observer.source.guard=guard
                    origins=deepcopy(observer.origins);observer.origins['primary']='http://foreign.invalid'
                    with self.assertRaises(NativeUIError):retirement.validate_original(original)
                    observer.origins=origins
                path=observer.source.parts.snapshot.paths(observer.source.frame(observer.source.state['records'][-1])['nativeSnapshot'])[0]
                with self.assertRaises(NativeUIError):
                    with retirement.publication_round(publisher):
                        retirement.validate_original(original);replacement=path.with_suffix('.replacement')
                        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path);replaced=True
                        retirement.validate_original(original)
        self.assertTrue(replaced)

    def test_expired_warm_original_refuses_actual_publication_before_post(self):
        with actor_scene() as (whole,_actor,_observer,retirement,original,publisher):
            before=deepcopy(retirement.validate_original(original));requests=[];request=publisher.phase.client.request
            def counted(path,*args,**kwargs):
                if path.endswith('/retirements') and (args or kwargs.get('body') is not None):requests.append(path)
                return request(path,*args,**kwargs)
            publisher.phase.client.request=counted
            with self.assertRaises(NativeUIError):
                with retirement.publication_round(publisher):
                    retirement.validate_original(original);whole.sdk.sleep(2);publisher.publish(original)
            self.assertEqual([],requests);self.assertEqual(before,retirement.validate_original(original))


if __name__=='__main__':unittest.main()
