"""Aborted rendering retains actual submitted code without inventing a marker."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_marker_partial import executed,restored,drained_partial
from ios.self_tests.test_ios_emote_marker_measurements import frames,FILES,DIRECTORY
from ios.self_tests import test_ios_emote_marker_measurements as marker_fixture
from ios.self_tests.test_ios_web_closures import ClosureBoundary


class PartialMarkerTests(unittest.TestCase):
    def missing_entity(self):
        before,after=frames();after['source']['markers']=[];after['source']['tree']=deepcopy(before['source']['tree'])
        after['source']['scriptOriginal']['source']['effects']=deepcopy(before['source']['scriptOriginal']['source']['effects'])
        return before,after
    def test_actual_code_and_worker_are_owned_even_when_add_entity_created_nothing(self):
        before,after=self.missing_entity();owned=executed(before,after,FILES,DIRECTORY,after_epoch=13000)
        self.assertIsNone(owned['marker']);self.assertEqual(DIRECTORY+'/script-bundle/main.js',owned['sourceUrl'])
        proof=marker_fixture.MarkerMeasurementsTests().terminal(owned)
        self.assertEqual(3,len(restored(before,before,owned,proof,after_sequence=1,after_epoch=17001)))
    def test_missing_entity_never_permits_foreign_code_manager_or_unowned_tree_changes(self):
        for fault in ('code','manager','extra'):
            before,after=self.missing_entity()
            if fault=='code':after['source']['scriptOriginal']['source']['engines'][0]['code']['sha256']='f'*64
            elif fault=='manager':after['source']['scriptOriginal']['source']['membership']['managers'][0]['assignedEpochMs']=12000
            else:
                row=frames()[1]['source']['tree']['entities'][0];after['source']['tree'].update(totalEntities=1,entities=[row])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):executed(before,after,FILES,DIRECTORY,after_epoch=13000)
    def closure(self,sequence=1):
        b=ClosureBoundary();b.version=5;b.send(dict(commandId='ios-'+format(sequence,'032x')))
        p=json.loads(b.original());p.update(runId=FILES['runId'],fixtureUrl=FILES['fixtureUrl'],sequence=sequence,processId=31)
        p['contexts'][0]['descriptor']['sourceUrl']=FILES['fixtureUrl']+'tickets/'+FILES['ticket']+'/graphics-marker.v1.html'
        return p
    def test_unpainted_setup_may_have_no_context_but_every_later_original_lifetime_must_drain(self):
        before=self.closure();before['contexts']=[];empty=self.closure(2);empty['contexts']=[]
        self.assertEqual([],drained_partial(empty,before));pending=self.closure(2)
        with self.assertRaises(NativeUIError):drained_partial(pending,before)
        for row in pending['contexts']:
            for group in ('callbacks','resources'):
                for counter in row[group].values():counter.update(retired=counter['created'],pending=0)
        self.assertEqual(1,len(drained_partial(pending,before)))
        pending['complete']=False
        with self.assertRaises(NativeUIError):drained_partial(pending,before)


if __name__=='__main__':unittest.main()
