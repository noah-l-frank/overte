"""Pure cumulative-event reuse; native producers are explicit host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_source as source,world_web_event_prefix as prefix
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN,URL


def query(value):
    return dict(schemaVersion=1,action=source.ACTION,commandId=value['commandId'],runId=RUN,fixtureUrl=URL)


class WorldWebEventPrefixTests(unittest.TestCase):
    def test_equal_old_events_are_not_reinterpreted_and_outward_mutation_cannot_change_cached_prefix(self):
        f=OriginalSources();first=f.ledger();f.pointer();second=f.ledger()
        with patch.object(source,'detail',wraps=source.detail) as details:
            with source.validation_round():
                source.validate(first,query(first),42);count=details.call_count
                self.assertEqual(len(first['events']),count)
                source.validate(second,query(second),42,previous=first)
                self.assertEqual(len(second['events']),details.call_count)
                first['events'][0]['identity']['creation']=True
                # The cached prefix is private. A changed same-looking scalar
                # must take the full validator and fail its actual type rule.
                changed=deepcopy(second);changed['events'][0]['identity']['creation']=True
                with self.assertRaises(NativeUIError):source.validate(changed,query(changed),42)
            before=details.call_count;source.validate(second,query(second),42)
            self.assertEqual(before+len(second['events']),details.call_count)

    def test_prefix_cannot_hide_changed_original_details_old_clocks_or_duplicate_callback_return(self):
        f=OriginalSources();entry=f.pointer(returned=False);first=f.ledger()
        f.event('callback-enter',dict(entry=entry['sequence'],result=dict(error=False,result=False)))
        f.event('callback-return',dict(entry=entry['sequence']));second=f.ledger()
        with source.validation_round():
            source.validate(first,query(first),42);source.validate(second,query(second),42,previous=first)
            for fault in ('old-clock','changed-prefix','double-return','foreign-instance','boolean-prefix'):
                value=deepcopy(second)
                if fault=='old-clock':value['clockBefore']['monotonicMs']=first['events'][-1]['clock']['monotonicMs']-1
                elif fault=='changed-prefix':value['events'][0]['detail']={'invented':True}
                elif fault=='foreign-instance':value['instance']='f'*32
                elif fault=='boolean-prefix':value['events'][0]['identity']['creation']=True
                else:
                    duplicate=deepcopy(value['events'][-1]);duplicate.update(sequence=value['eventSequence']+1,eventId='e'*32)
                    value['events'].append(duplicate);value['eventSequence']+=1
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,query(value),42,previous=first)

    def test_current_freshness_pid_and_explicit_previous_relation_still_run_after_warm_prefix(self):
        f=OriginalSources();first=f.ledger();second=f.ledger()
        with source.validation_round():
            source.validate(first,query(first),42);source.validate(second,query(second),42,previous=first)
            with self.assertRaises(NativeUIError):source.validate(second,query(second),43)
            with self.assertRaises(NativeUIError):source.validate(second,query(second),42,epoch=second['clockAfter']['epochMs']+1501)
            with self.assertRaises(NativeUIError):source.validate(first,query(first),42,previous=second)
            altered=deepcopy(second);altered['commandId']=first['commandId']
            with self.assertRaises(NativeUIError):source.validate(altered,query(altered),42,previous=first)

    def test_cache_limits_fall_back_to_full_event_validation(self):
        f=OriginalSources();first=f.ledger();f.pointer();second=f.ledger()
        with patch.object(prefix,'MAX_BYTES',1),patch.object(source,'detail',wraps=source.detail) as details,source.validation_round():
            source.validate(first,query(first),42);source.validate(second,query(second),42)
            self.assertEqual(len(first['events'])+len(second['events']),details.call_count)
        with patch.object(prefix,'MAX_KEYS',0),patch.object(source,'detail',wraps=source.detail) as details,source.validation_round():
            source.validate(first,query(first),42);source.validate(second,query(second),42)
            self.assertEqual(len(first['events'])+len(second['events']),details.call_count)

    def test_earlier_original_packet_reuses_only_its_exact_validated_shorter_prefix(self):
        f=OriginalSources();first=f.ledger();entry=f.pointer(returned=False);middle=f.ledger()
        f.event('callback-enter',dict(entry=entry['sequence'],result=dict(error=False,result=False)))
        f.event('callback-return',dict(entry=entry['sequence']));last=f.ledger()
        with patch.object(source,'detail',wraps=source.detail) as details,source.validation_round():
            source.validate(last,query(last),42);count=details.call_count
            for ordinal,value in enumerate((first,middle),1):
                value=deepcopy(value);value['commandId']='ios-'+format(ordinal,'032x')
                source.validate(value,query(value),42)
                self.assertEqual(count,details.call_count)
            self.assertEqual([entry['sequence']],source.pending(value))


if __name__=='__main__':unittest.main()
