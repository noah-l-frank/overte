"""Actual assignment/submission order in the closed combined work profile."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_combined_work as source
from ios.self_tests.snapshot_combined_work_fixture import packet,advance,timer,URL,EPOCH


def query(value):return dict(schemaVersion=1,action=source.ACTION,commandId=value['requestId'],runId=value['runId'])


def unsubmitted():
    value=packet();value['source'].update(workers=[],callerStacks=[],eventSequence=0)
    native=value['source']['timerSources']['workers'][0]
    native['code']=dict(submitted=False,encoding='utf-16le-code-units',codeUnits=0,sha256='',submittedEpochMs=0)
    native['codeSources']['evaluations']=[];native['running']=False
    return value


def first_submission():
    before=unsubmitted();after=packet(EPOCH+2500)
    after.update(requestId='ios-'+'4'*32,sequence=2)
    after['clockBefore']['monotonicMs']=3500;after['clockAfter']['monotonicMs']=3501
    member=deepcopy(before['source']['timerSources']['workers'][0]['membership'])
    after['source']['workers'][0]['manager']=deepcopy(member)
    after['source']['timerSources']['workers'][0]['membership']=deepcopy(member)
    return before,after


class SnapshotCombinedClockTests(unittest.TestCase):
    def extended(self,epoch,*,with_timer=False):
        before=packet()
        if with_timer:timer(before)
        after=advance(before)
        row=deepcopy(after['source']['workers'][0]['codeSources']['evaluations'][2]);row.update(sequence=5,submittedEpochMs=epoch)
        for worker in (after['source']['workers'][0],after['source']['timerSources']['workers'][0]):worker['codeSources']['evaluations'].append(deepcopy(row))
        return before,after

    def test_original_main_submission_cannot_predate_actual_manager_assignment(self):
        value=packet()
        value['source']['workers'][0]['manager']['assignedEpochMs']=EPOCH-900
        value['source']['timerSources']['workers'][0]['membership']['assignedEpochMs']=EPOCH-900
        with self.assertRaises(NativeUIError):source.original(value)

    def test_native_partial_evaluation_cannot_predate_assignment_even_without_work_owner(self):
        value=unsubmitted();native=value['source']['timerSources']['workers'][0]
        native['membership']['assignedEpochMs']=EPOCH-900
        native['codeSources']['evaluations']=deepcopy(packet()['source']['workers'][0]['codeSources']['evaluations'][:1])
        with self.assertRaises(NativeUIError):source.original(value)

    def test_genuine_first_submission_after_unsubmitted_original_is_readable_but_never_old_absence(self):
        before,after=first_submission();source.original(before)
        with self.assertRaises(NativeUIError):source.admit(before,URL,quiet=True)
        source.validate(after,query(after),42,previous=before)
        self.assertEqual(URL+'defaultScripts.js',source.admit(after,URL,quiet=True)['manager']['url'])

    def test_first_submission_backdated_before_original_observation_is_rejected(self):
        before,after=first_submission()
        for row in (after['source']['workers'][0],after['source']['timerSources']['workers'][0]):row['code']['submittedEpochMs']=EPOCH+900
        with self.assertRaises(NativeUIError):source.validate(after,query(after),42,previous=before)

    def test_actual_later_evaluation_is_retained_without_becoming_unique_source_admission(self):
        before,after=self.extended(EPOCH+1005,with_timer=True);source.validate(after,query(after),42,previous=before)
        with self.assertRaises(NativeUIError):source.admit(after,URL,quiet=True)

    def test_new_evaluation_cannot_be_inserted_before_original_observation(self):
        before,after=self.extended(EPOCH+999)
        with self.assertRaises(NativeUIError):source.validate(after,query(after),42,previous=before)

    def test_future_compiled_frame_cannot_be_borrowed_for_historical_work_event(self):
        value=packet();caller=value['source']['callerStacks'][0]['callerStack']['frames'][0]
        caller['compiled']['firstObservedEpochMs']=value['source']['workers'][0]['events'][0]['capturedEpochMs']+1
        with self.assertRaises(NativeUIError):source.original(value)

    def test_future_compiled_frame_cannot_be_borrowed_for_original_timer_birth(self):
        value=packet();actual=timer(value)
        value['source']['timerSources']['workers'][0]['timerWork']['callerStacks'][0]['callerStack']['frames'][0]['compiled']['firstObservedEpochMs']=actual['createdEpochMs']+1
        with self.assertRaises(NativeUIError):source.original(value)


if __name__=='__main__':unittest.main()
