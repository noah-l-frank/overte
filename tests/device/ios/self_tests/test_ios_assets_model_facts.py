"""Actual normal API event/tree joins; native geometry remains explicitly modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_model_facts as facts
from ios.self_tests.assets_model_fixture import Fixture


class AssetsModelFactsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.b=self.f.boundary;self.o,self.before,self.after=self.f.accepted()

    def test_observed_uuid_comes_from_new_tree_row_after_original_normal_acceptance(self):
        proof=facts.imported(self.o,self.before,self.after);event=next(event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='entity-returned')
        self.assertEqual(event['id'],proof['entityId']);self.assertEqual(event['args'][1],proof['url']);self.assertEqual([0,1,-2],proof['position']);self.assertEqual(0,self.b.host_state['uploads'])
        with self.assertRaises(NativeUIError):facts.geometry(self.o,self.before,self.after,self.after)
        self.b.models[proof['entityId']].loaded=True;self.b.models[proof['entityId']].added=True;original=self.b.state()
        geometry=facts.geometry(self.o,self.before,self.after,original);self.assertEqual(proof['entityId'],geometry['entityId']);self.assertEqual(original['requestId'],geometry['requestId'])

    def test_existing_lookalike_is_not_a_newly_owned_entity(self):
        before=deepcopy(self.before);before['source']['entities']=deepcopy(self.after['source']['entities']);before['source']['tree']=deepcopy(self.after['source']['tree'])
        with self.assertRaises(NativeUIError):facts.imported(self.o,before,self.after)

    def test_wrong_owner_domain_url_position_or_creation_time_cannot_be_adopted(self):
        def old_time(packet):
            packet['source']['entities'][0]['createdEpochUs']='1';packet['source']['tree']['entities'][0]['createdEpochUs']='1'
        for mutate in (lambda packet:packet['source']['entities'][0].update(lastEditedBy='11111111-1111-4111-8111-111111111111'),
                lambda packet:packet['source'].update(domainId='11111111-1111-4111-8111-111111111111'),lambda packet:packet['source']['entities'][0].update(modelURL='atp:/foreign/model.fbx'),
                lambda packet:packet['source']['entities'][0].update(position=[4,5,6]),old_time):
            wrong=deepcopy(self.after);mutate(wrong)
            with self.assertRaises(NativeUIError):facts.imported(self.o,self.before,wrong)

    def test_zero_or_two_added_actual_entities_are_not_one_owned_import(self):
        for count in (0,2):
            wrong=deepcopy(self.after)
            if count==0:wrong['source']['entities']=[];wrong['source']['tree'].update(entities=[],totalEntities=0)
            else:
                row=deepcopy(wrong['source']['entities'][0]);wire=deepcopy(wrong['source']['tree']['entities'][0]);row['id']=wire['id']='ffffffff-ffff-4fff-8fff-ffffffffffff'
                wrong['source']['entities'].append(row);wrong['source']['tree']['entities'].append(wire);wrong['source']['entities'].sort(key=lambda row:row['id']);wrong['source']['tree']['entities'].sort(key=lambda row:row['id']);wrong['source']['tree']['totalEntities']=2
            with self.assertRaises(NativeUIError):facts.imported(self.o,self.before,wrong)

    def test_requested_url_or_geometry_failure_never_becomes_added_scene_effect(self):
        proof=facts.imported(self.o,self.before,self.after);model=self.b.models[proof['entityId']]
        for loaded,added,failed in ((False,False,False),(True,False,False),(True,True,True)):
            model.loaded,model.added,model.failed=loaded,added,failed;original=self.b.state()
            with self.assertRaises(NativeUIError):facts.geometry(self.o,self.before,self.after,original)

    def test_source_sample_before_ui_resolution_cannot_bracket_creation(self):
        wrong=deepcopy(self.after);wrong['clockBefore']['epochMs']=wrong['clockAfter']['epochMs']=self.before['clockAfter']['epochMs']
        wrong['clockBefore']['monotonicMs']=wrong['clockAfter']['monotonicMs']=self.before['clockAfter']['monotonicMs']
        with self.assertRaises(NativeUIError):facts.imported(self.o,self.before,wrong)


if __name__=='__main__':unittest.main()
