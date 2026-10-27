"""Unchanged original geometry proof across real private delivery-WAL changes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.self_tests import test_ios_world_web_input as fixture


class InputProofDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebInputTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_actual_single_proof_avoids_duplicate_cost_before_original_1500ms_send(self):
        t=self.f
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source);proof=owner.proof;calls=[]
            def expensive(row):
                value=proof(row);calls.append(None);t.sdk.sleep(.8);return value
            owner.proof=expensive
            result=owner.perform(t.sdk.ticket,'normal-focus','tap','text')
            self.assertEqual('returned',result['phase']);self.assertEqual(1,len(calls));self.assertEqual(1,len(t.sdk.posted))
            self.assertTrue(source.frame(source.capture('independent-after'))['originals']['document']['source']['dom']['editor']['focused'])
            owner.decode(owner.previous);self.assertEqual(1,len(calls))
    def test_phase_and_release_grammar_is_rechecked_even_with_the_same_geometry_key(self):
        t=self.f
        with t.held():
            owner=t.owner(t.sdk.owner(t.source_store,t.lock));owner.perform(t.sdk.ticket,'focus','tap','text')
            for field,value in (('phase',True),('releaseReturned',1)):
                changed=deepcopy(owner.previous);rows=unpack(changed['payload']);rows[0]['records'][0][field]=value;changed['payload']=pack(rows)
                with self.subTest(field=field),self.assertRaises(NativeUIError):owner.decode(changed)
            for field in ('body','point','source'):
                changed=deepcopy(owner.previous);rows=unpack(changed['payload']);row=rows[0]['records'][0]
                if field=='body':row[field]['actions'][0]['actions'][0]['x']+=1
                elif field=='point':row[field]['x']+=10
                else:row[field]['sha256']='0'*64
                changed['payload']=pack(rows)
                with self.subTest(field=field),self.assertRaises(NativeUIError):owner.decode(changed)
    def test_changed_pure_parser_cannot_inherit_a_previous_success(self):
        t=self.f
        with t.held():
            owner=t.owner(t.sdk.owner(t.source_store,t.lock));owner.perform(t.sdk.ticket,'focus','tap','text')
            def changed(_row):raise NativeUIError('Declared unavailable proof parser')
            owner.proof=changed
            with self.assertRaises(NativeUIError):owner.decode(owner.previous)


if __name__=='__main__':unittest.main()
