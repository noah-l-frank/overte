"""Declared clock/measurement seams for role-correct setup quiet selection.

Only chronology and original endpoint selection are qualified. The full native
measurement call is a sentinel; these cases do not claim native cleanup, pixels,
process death or terminal completion. Actual retained full-owner replay is a
separate diagnostic, and the full feature cases remain mandatory.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.retirement_receipts import quiet as receipt_quiet
from ios.adapters.world_web_setup_retirement import WorldWebSetupRetirement
from ios.adapters.world_web_retired import quiet_summary

BASE=1700000000000


def frame(index,pid,begin,end):
    def native(at):return dict(processId=pid,instance=('b' if pid==31 else 'c')*32,capturedEpochMs=BASE+round(at*1000),lifecycle=dict(backgrounds=0,activations=0,launches=1))
    return dict(index=index,ticket='a'*32,clockJoin=dict(hostBeforeEpochMs=BASE+round(begin*1000),hostAfterEpochMs=BASE+round(end*1000),
        hostBeforeMonotonic=begin,hostAfterMonotonic=end,nativeBefore=native(begin),nativeAfter=native(end)),
        originals=dict(keys=dict(source=dict(instance='d'*32,eventSequence=0)),pointer=dict(source=dict(instance='e'*32,eventSequence=0)),
            ledgerAfter=dict(eventSequence=0),world=dict(clockBefore=dict(monotonicMs=round(begin*1000)),clockAfter=dict(monotonicMs=round(end*1000)))))


class WorldWebSetupQuietTests(unittest.TestCase):
    def owner(self):
        primary={};own={};rows=[]
        for number,at in enumerate((0.,1.,3.1,3.3),1):
            before=number*2-1;after=number*2;primary[before]=frame(before,31,at,at+.02);primary[after]=frame(after,31,at+.03,at+.05)
            own[number]=frame(number,52,at+.06,at+.08)
            rows.append(dict(before=dict(index=before),after=dict(index=after),peer=dict(index=number),native=dict(scriptRoots={}),
                acquisition=dict(hostBeforeEpochMs=BASE+round((at+.03)*1000),hostAfterEpochMs=BASE+round((at+.08)*1000),hostBeforeMonotonic=at+.03,hostAfterMonotonic=at+.08)))
        owner=object.__new__(WorldWebSetupRetirement);owner.observer=SimpleNamespace(validation_round=nullcontext);owner.role='actor';owner.source=SimpleNamespace(frame=lambda ref:deepcopy(primary[ref['index']]))
        owner.peer=SimpleNamespace(frame=lambda ref:deepcopy(own[ref['index']]));owner.state={};owner.measure=deepcopy
        state=dict(records=rows,quiet=[1,2,3,4]);return owner,state,primary,own

    def test_summary_uses_actor_pid_and_completed_own_interval_before_separate_dual_acquisition(self):
        owner,state,primary,own=self.owner();value=owner.qualification(state)
        self.assertEqual(52,value['quiet']['processId']);self.assertEqual('c'*32,value['quiet']['nativeInstance'])
        self.assertEqual(3080,value['quiet']['nativeBeforeLastEpochMs']-value['quiet']['nativeAfterFirstEpochMs'])
        receipt_quiet(value['quiet'],dict(processIdentity='52'))
        wrong=quiet_summary(primary[2],primary[7])
        with self.assertRaises(ValueError):receipt_quiet(wrong,dict(processIdentity='52'))
        value['quiet']['processId']=31;self.assertEqual(52,owner.qualification(state)['quiet']['processId'])
        self.assertEqual({},owner.state)

    def test_same_current_acquisition_overlap_is_not_a_completed_preceding_interval(self):
        owner,state,primary,_own=self.owner();primary[7]=frame(7,31,3.17,3.19)
        with self.assertRaises(NativeUIError):owner.qualification(state)

    def test_late_last_sample_cannot_replace_an_unfinished_penultimate_quiet_interval(self):
        owner,state,_primary,own=self.owner();own[3]=frame(3,52,2.9,2.92)
        with self.assertRaises(NativeUIError):owner.qualification(state)

    def test_three_samples_do_not_include_a_separate_final_dual_original(self):
        owner,state,_primary,_own=self.owner();state['quiet']=state['quiet'][:3]
        with self.assertRaises(NativeUIError):owner.qualification(state)


if __name__=='__main__':unittest.main()
