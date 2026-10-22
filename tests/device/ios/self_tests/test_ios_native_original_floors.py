"""Prior native clock originals over committed model/transcript transports."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_source import IOSWorldWebSource
from ios.self_tests.test_ios_places_model import Boundary as Model
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN,URL
from self_tests.test_native_feature_observation import Boundary as Native


def floor(clock,pid=42):
    original=Native()
    def sampled(value):
        epoch=clock();value.update(processId=pid,requestedEpochMs=epoch,capturedEpochMs=epoch,animation={},animationFence={})
    original.mutate=sampled
    return NativeFeatureObservation(original.send,original.original,clock,lambda:True,pid,ios=True).read(0)


class NativeOriginalFloorTests(unittest.TestCase):
    def model(self):
        producer=Model();calls=[]
        def clock():calls.append(True);return producer.native_clock()
        reader=producer.reader();reader.clock_ms=clock
        return producer,reader,calls,(RUN,),producer.native_clock
    def transcript(self):
        producer=OriginalSources();calls=[];carrier={};producer.queries=[]
        def clock():calls.append(True);return producer.clock()
        def send(query):producer.queries.append(query);carrier['raw']=json.dumps(producer.ledger(query))
        reader=IOSWorldWebSource(send,lambda:carrier['raw'],clock,lambda:True,42,
            monotonic=lambda:producer.epoch/1000,sleep=lambda _n:None)
        return producer,reader,calls,(RUN,URL),producer.clock

    def test_default_clocks_remain_and_retained_before_floor_never_removes_new_terminal_reads(self):
        for factory,ordinary,with_floor in ((self.model,2,1),(self.transcript,3,2)):
            with self.subTest(kind=factory.__name__):
                _producer,reader,calls,args,actual=factory();reader.read(*args);self.assertEqual(ordinary,len(calls))
                retained=floor(actual);calls.clear();packet=reader.read(*args,native_before_floor=retained)
                self.assertEqual(with_floor,len(calls));self.assertGreaterEqual(packet['clockBefore']['epochMs'],retained['capturedEpochMs'])
                if hasattr(reader,'acquisition'):
                    self.assertIn('nativeBeforeOriginalFloorSha256',reader.acquisition)

    def test_genuine_foreign_pid_floor_is_rejected_before_any_source_query(self):
        for factory in (self.model,self.transcript):
            with self.subTest(kind=factory.__name__):
                producer,reader,_calls,args,actual=factory();foreign=floor(actual,pid=43)
                queries=producer.requests if hasattr(producer,'requests') else producer.queries
                with self.assertRaises(NativeUIError):reader.read(*args,native_before_floor=foreign)
                self.assertEqual([],queries)

    def test_floor_digest_and_validation_use_one_owned_copy_when_a_guard_mutates_the_callers_packet(self):
        for factory in (self.model,self.transcript):
            with self.subTest(kind=factory.__name__):
                _producer,reader,_calls,args,actual=factory();retained=floor(actual);expected=deepcopy(retained)
                def guard():
                    retained['capturedEpochMs']=0
                    return True
                reader.guard=guard
                value=reader.read(*args,native_before_floor=retained)
                self.assertEqual(0,retained['capturedEpochMs'])
                self.assertGreaterEqual(value['clockBefore']['epochMs'],expected['capturedEpochMs'])
                if hasattr(reader,'acquisition'):
                    self.assertEqual(digest(expected),reader.acquisition['nativeBeforeOriginalFloorSha256'])

    def test_aged_original_floor_cannot_be_relabelled_by_a_fast_new_terminal_clock(self):
        for factory in (self.model,self.transcript):
            with self.subTest(kind=factory.__name__):
                producer,reader,_calls,args,actual=factory();old=floor(actual)
                if isinstance(producer,Model):producer.sleep(1.6)
                else:producer.epoch+=1600
                with self.assertRaises(NativeUIError):reader.read(*args,native_before_floor=old)


if __name__=='__main__':unittest.main()
