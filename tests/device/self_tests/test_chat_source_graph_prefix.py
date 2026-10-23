"""Pure strict-JSON prefix admission from one original sealed source fixture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.chat_journey import remote_actor_graph as grammar
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_remote_actor_graph as source_fixture


class ChatSourceGraphPrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=source_fixture.ChatRemoteActorGraphTests();cls.addClassCleanup(cls.fixture.doCleanups)
        cls.fixture.setUp();cls.graph=cls.fixture.acquire()

    def packet(self,count=3):
        g=self.graph;stages=grammar.STAGES[:count]
        keys=('publisher','cursor','code')+tuple(stage+suffix for stage in stages for suffix in ('-samples','-observation'))
        roots={key:deepcopy(g.roots[key]) for key in keys};frames={key:deepcopy(g.frames[key]) for key in keys}
        for key in ('publisher','cursor','code'):
            roots[key]['chunks']=roots[key]['chunks'][:count];frames[key]=frames[key][:count]
        roots['code']['revision']=2*count;roots['cursor']['stages']=roots['cursor']['stages'][:count]
        return [roots,frames,g.stores,deepcopy(g.expected),deepcopy(g.flow),deepcopy(g.flow_rows),
            deepcopy(g.cleanup) if count==3 else None,stages]

    def warm(self):
        memo=grammar.ChatSourceGraphPrefix();memo.commit(memo.validate(*self.packet(1)));return memo

    def test_only_new_original_rows_use_full_grammar_and_same_prefix_never_replays_it(self):
        memo=self.warm()
        with patch.object(grammar,'compose',wraps=grammar.compose) as compose,patch.object(grammar,'validate_transaction',wraps=grammar.validate_transaction) as transaction:
            memo.commit(memo.validate(*self.packet(2)))
            self.assertEqual(2,compose.call_count);self.assertEqual(1,transaction.call_count)
            memo.commit(memo.validate(*self.packet(2)))
            self.assertEqual(2,compose.call_count);self.assertEqual(1,transaction.call_count)
            memo.commit(memo.validate(*self.packet(3)))
            self.assertEqual(4,compose.call_count);self.assertEqual(2,transaction.call_count)
        grammar.validate_source_graph(*self.packet())

    def test_uncommitted_candidate_is_never_a_prefix_and_copied_candidate_cannot_commit(self):
        memo=grammar.ChatSourceGraphPrefix();candidate=memo.validate(*self.packet(1))
        with self.assertRaises(NativeUIError):memo.commit(deepcopy(candidate))
        self.assertIsNone(memo.previous)
        with patch.object(grammar,'compose',wraps=grammar.compose) as compose:
            memo.commit(memo.validate(*self.packet(2)));self.assertEqual(4,compose.call_count)

    def test_original_value_changes_and_json_aliases_refuse_without_prefix_adoption(self):
        for fault in ('value','bool','tuple','subclass','path','scope','flow','root'):
            with self.subTest(fault=fault):
                memo=self.warm();args=self.packet(2);old=deepcopy(memo.previous)
                if fault=='value':args[1]['initial-samples'][0]['peer']['processId']+=1
                elif fault=='bool':args[1]['cursor'][0]['sequence']=True
                elif fault=='tuple':args[1]['initial-samples']=tuple(args[1]['initial-samples'])
                elif fault=='subclass':
                    class Alias(dict):pass
                    args[1]['cursor'][0]=Alias(args[1]['cursor'][0])
                elif fault=='path':args[2]={**args[2],'code':PrivateFeatureState(args[2]['code'].path.with_name('foreign-code.json'))}
                elif fault=='scope':args[3]['instance']='f'*32
                elif fault=='flow':args[5][0]['ticket']='f'*32
                else:args[0]['initial-samples']['revision']=True
                with self.assertRaises(NativeUIError):memo.validate(*args)
                self.assertTrue(memo.failed);self.assertEqual(old,memo.previous)

    def test_new_bad_native_row_is_fully_validated_after_good_prefix(self):
        memo=self.warm();args=self.packet(2);args[1]['active-samples'][0]['peer']['processId']+=1
        with self.assertRaises(NativeUIError):memo.validate(*args)
        self.assertTrue(memo.failed);self.assertEqual(['initial'],memo.previous['stages'])

    def test_changed_original_local_code_pins_cannot_qualify_a_grammar_cache_hit(self):
        memo=self.warm();changed=deepcopy(memo.previous['pins']);changed['sha256']='f'*64
        with patch.object(grammar,'pins',return_value=changed),self.assertRaises(NativeUIError):memo.validate(*self.packet(1))
        self.assertTrue(memo.failed)

    def test_mutated_pending_or_committed_cache_cannot_be_adopted_as_valid(self):
        for field in ('pending','previous'):
            with self.subTest(field=field):
                memo=self.warm();memo.validate(*self.packet(2))
                if field=='pending':memo.pending['value']['stages'].append('cleanup')
                else:memo.previous['frames']['code']=tuple(memo.previous['frames']['code'])
                with self.assertRaises(NativeUIError):memo.control()


if __name__=='__main__':unittest.main()
