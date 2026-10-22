"""Real throwing/cached host functors; no failed publication becomes file proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_file_work as source
from ios.self_tests.test_ios_snapshot_file_work import Jobs


class SnapshotFileWorkFailureTests(unittest.TestCase):
    def failed(self,*,publication=None):
        jobs=Jobs();owner,query=jobs.queued();record=next(iter(jobs.jobs.values()))[1]
        def actual_failed_job(held=owner):
            record['enteredEpochMs']=jobs.tick()
            try:
                if publication is False:
                    record.update(publication=False,publishedEpochMs=jobs.tick(),returnedEpochMs=jobs.tick());return False
                raise OSError('Actual host model worker throws before publication')
            finally:record['finallyEpochMs']=jobs.tick();assert callable(held)
        if publication is False:self.assertFalse(actual_failed_job())
        else:
            with self.assertRaises(OSError):actual_failed_job()
        return jobs,actual_failed_job,query
    def test_actual_finally_and_last_cached_capture_death_allow_failure_retirement_only(self):
        jobs,callback,query=self.failed();held=jobs.read()
        with self.assertRaises(NativeUIError):source.retired(held,[query])
        del callback;ended=jobs.read();source.retired(ended,[query])
        self.assertIsNone(ended['source']['jobs'][0]['publication'])
        self.assertIsNone(ended['source']['jobs'][0]['returnedEpochMs'])
        with self.assertRaises(NativeUIError):source.drained(ended,[query])
    def test_ended_failed_publication_does_not_become_a_successful_query(self):
        jobs,callback,query=self.failed(publication=False)
        del callback;ended=jobs.read();source.retired(ended,[query])
        with self.assertRaises(NativeUIError):source.drained(ended,[query])
    def test_missing_unknown_unentered_unfinished_or_resurrected_jobs_cannot_retire(self):
        jobs,callback,query=self.failed();del callback;ended=jobs.read()
        for fault in ('missing','query','entered','finally','expiry','alive','complete'):
            value=deepcopy(ended)
            if fault=='missing':value['source']['jobs']=[]
            elif fault=='complete':value['source']['complete']=False
            else:
                row=value['source']['jobs'][0]
                if fault=='query':row['query']['commandId']='ios-'+'f'*32
                elif fault=='entered':row['enteredEpochMs']=None
                elif fault=='finally':row['finallyEpochMs']=None
                elif fault=='expiry':row['expiredEpochMs']=None
                else:row.update(alive=True,expiredEpochMs=None)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.retired(value,[query])
        with self.assertRaises(NativeUIError):source.retired(ended,[query,query])


if __name__=='__main__':unittest.main()
