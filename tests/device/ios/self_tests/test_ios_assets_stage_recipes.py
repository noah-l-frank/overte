"""Original normal FBX actions stay separated across actual current tickets.

Native/Qt/server/parser/scene are declared models. Original QML/WAL and actual
backend/Geometry/HFM/scene files/objects execute. No native/device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_stage_recipes import AssetsStageRecipes
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_usage_controls import project as usage_controls
from ios.self_tests import assets_baked_tree_fixture as baked
from ios.self_tests.assets_paired_end_boundary_fixture import Boundary
from ios.self_tests.assets_reply_fixture import RUN,TICKET,URL

BAKE_TICKET='c'*32
IMPORT_TICKET='d'*32


class Fixture(baked.Fixture):
    boundary_type=Boundary
    def __init__(self,directory):
        super().__init__(directory);self.boundary.peer.resolve_model=self.resolve_model
class Runtime(AssetsStageRecipes,IOSAssetsRuntime):pass


class AssetsStageRecipeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.f=Fixture(self.root);self.addCleanup(self.f.close);self.b=self.f.boundary
        self.b.reads.resource='asset-stand.fbx';self.parts=self.f.parts()
        self.runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.b.monotonic)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.f))
    def upload(self):return self.runtime._assets_stage_fbx_upload('declared-existing-parts',RUN,'primary',URL,TICKET,self.f.lock,self.f.backend.config,parts=self.parts)
    def off(self):self.upload();return self.runtime._assets_stage_baking_off(self.parts)
    def on(self):self.off();return self.runtime._assets_stage_baking_on(self.parts,BAKE_TICKET)
    def test_normal_original_upload_off_on_have_no_Model_until_separate_import_and_keep_each_query_ticket(self):
        self.upload();self.assertFalse(self.b.entities);self.assertFalse(self.b.models);self.assertIsNone(self.parts['usage'].state)
        self.assertIsNone(self.parts['model'].state);self.assertIsNone(self.parts['baking'].state)
        off=self.runtime._assets_stage_baking_off(self.parts);self.assertFalse(off['baking']['checked']);self.assertFalse(self.b.models)
        result=self.runtime._assets_stage_baking_on(self.parts,BAKE_TICKET)
        self.assertTrue(result);self.assertFalse(self.b.models);self.assertIsNone(self.parts['model'].state);self.assertIsNone(self.parts['parsed'].state)
        current=usage_controls(self.parts['usage'].capture(),self.parts['upload'].state['page']);self.assertTrue(current['baking']['checked']);self.assertFalse(current['model']['visible'])
        proof=self.runtime._assets_stage_import_baked(self.parts,IMPORT_TICKET);self.assertTrue(proof)
        self.assertEqual('observed',self.parts['parsed'].state['phase']);self.assertEqual(1,len(self.b.entities));self.assertEqual(TICKET,self.f.files.state['ticket'])
        self.assertEqual(2,self.parts['baking'].previous['iosAssetsBakingOwnerVersion']);self.assertEqual(BAKE_TICKET,self.parts['baking'].previous['actionTicket'])
        self.assertEqual(2,self.parts['parsed'].previous['iosAssetsParsedInputOwnerVersion']);self.assertEqual(IMPORT_TICKET,self.parts['parsed'].previous['actionTicket'])
        rows=self.parts['backend'].state['samples']
        self.assertTrue(all(row['query']['ticket']==BAKE_TICKET for row in rows if row['slot'].startswith(('usage-bake-baseline-','usage-bake-result-'))))
        self.assertEqual(IMPORT_TICKET,next(row['query']['ticket'] for row in rows if row['slot']=='parsed-output-1'))
    def test_ignored_on_ACK_leaves_checkbox_false_and_original_pending_command_cannot_be_resent(self):
        self.off();self.b.configure(ignore='assets.baking')
        with self.assertRaises(NativeUIError):self.runtime._assets_stage_baking_on(self.parts,BAKE_TICKET)
        entry=next(row for row in self.parts['usage'].state['inputs'] if row['slot']=='usage-bake-on')
        self.assertIsNotNone(entry['receipt']);self.assertIsNone(entry['resolvedBy']);inputs=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.runtime._assets_stage_baking_on(self.parts,BAKE_TICKET)
        self.assertEqual(inputs,len(self.b.inputs));self.assertFalse(self.b.models);self.assertIsNone(self.parts['model'].state)
    def test_lost_on_return_recovers_actual_effect_without_repeating_input_or_importing_early(self):
        self.off();self.b.configure(lost='assets.baking')
        with self.assertRaises(NativeUIError):self.runtime._assets_stage_baking_on(self.parts,BAKE_TICKET)
        before=len(self.b.inputs);result=self.runtime._assets_stage_baking_on(self.parts,BAKE_TICKET)
        self.assertTrue(result);self.assertEqual(before,len(self.b.inputs));self.assertFalse(self.b.models)
        self.assertEqual(1,sum(row['slot']=='usage-bake-on' for row in self.parts['usage'].state['inputs']))
    def test_baking_and_import_action_tickets_cannot_be_rebound_after_actual_owned_query(self):
        self.on();before=len(self.b.inputs);queries=len(self.parts['backend'].state['samples'])
        with self.assertRaises(NativeUIError):self.runtime._assets_stage_baking_on(self.parts,'e'*32)
        self.assertEqual(before,len(self.b.inputs));self.assertEqual(queries,len(self.parts['backend'].state['samples']))
        self.runtime._assets_stage_import_baked(self.parts,IMPORT_TICKET);before=len(self.b.inputs);queries=len(self.parts['backend'].state['samples'])
        with self.assertRaises(NativeUIError):self.runtime._assets_stage_import_baked(self.parts,'e'*32)
        self.assertEqual(before,len(self.b.inputs));self.assertEqual(queries,len(self.parts['backend'].state['samples']))
    def test_import_before_qualified_on_fails_before_any_Model_command_or_ownership(self):
        self.off();before=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.runtime._assets_stage_import_baked(self.parts,IMPORT_TICKET)
        self.assertEqual(before,len(self.b.inputs));self.assertFalse(self.b.models);self.assertIsNone(self.parts['model'].state)
    def test_default_monolithic_recipe_keeps_literal_v1_owners_and_original_upload_ticket(self):
        self.runtime._assets_upload_model_bytes('declared-existing-parts',RUN,'primary',URL,TICKET,self.f.lock,self.f.backend.config,parts=self.parts)
        self.assertEqual('observed',self.parts['parsed'].state['phase']);self.assertEqual(1,self.parts['baking'].previous['iosAssetsBakingOwnerVersion'])
        self.assertEqual(1,self.parts['parsed'].previous['iosAssetsParsedInputOwnerVersion'])
        self.assertNotIn('actionTicket',self.parts['baking'].previous);self.assertNotIn('actionTicket',self.parts['parsed'].previous)
        self.assertTrue(all(row['query']['ticket']==TICKET for row in self.parts['backend'].state['samples']))


if __name__=='__main__':unittest.main()
