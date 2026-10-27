"""Small input operands preserve actual Source/file/parser and public-copy semantics."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import cProfile
from copy import deepcopy
import pstats
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_sources import WorldWebSources
from ios.self_tests import test_ios_world_web_input as fixture


class WorldInputProjectionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebInputTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_normal_delivery_reads_real_point_without_copying_a_complete_frame(self):
        t=self.f
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source)
            profile=cProfile.Profile();profile.enable()
            try:row=owner.perform(t.sdk.ticket,'projected-focus','tap','text')
            finally:profile.disable()
            code=WorldWebSources.frame.__code__
            calls=pstats.Stats(profile).stats.get((code.co_filename,code.co_firstlineno,code.co_name))
            self.assertIsNone(calls,'Internal delivery must not allocate a complete public Source frame')
            self.assertEqual('returned',row['phase']);self.assertEqual(1,len(t.sdk.posted))
            after=source.frame(source.capture('independent-focused'))
            self.assertTrue(after['originals']['document']['source']['dom']['editor']['focused'])

    def test_projected_operands_and_public_proof_are_independent_values(self):
        t=self.f
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source)
            row=owner.perform(t.sdk.ticket,'normal-focus','tap','text')
            before=deepcopy(source.frame(row['source']))
            projection=source.input_projection(row['source'],t.sdk.entity,'tap','text')
            projection['clockJoin']['hostBeforeEpochMs']+=1000;projection['point']['domPoint'][0]+=1000
            projection['field']['focused']=not projection['field']['focused']
            self.assertEqual(before,source.frame(row['source']))
            proof=owner.proof(row);proof['originals']['widgets']['tabletShown']=True
            self.assertEqual(before,source.frame(row['source']))

    def test_changed_frame_reader_keeps_literal_validation_and_cannot_use_old_proof_cache(self):
        t=self.f
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source)
            row=owner.perform(t.sdk.ticket,'normal-focus','tap','text');owner.decode(owner.previous)
            def replaced(_reference):raise NativeUIError('Declared changed Source frame reader')
            source.frame=replaced
            with self.assertRaisesRegex(NativeUIError,'Declared changed Source frame reader'):
                source.input_projection(row['source'],t.sdk.entity,'tap','text')
            with self.assertRaisesRegex(NativeUIError,'Declared changed Source frame reader'):
                owner.decode(owner.previous)

    def test_changed_projection_predicate_cannot_inherit_an_old_geometry_success(self):
        t=self.f
        with t.held():
            source=t.sdk.owner(t.source_store,t.lock);owner=t.owner(source)
            owner.perform(t.sdk.ticket,'normal-focus','tap','text');owner.decode(owner.previous)
            def replaced(_row,_original):raise NativeUIError('Declared changed input predicate')
            owner._proof_projection=replaced
            with self.assertRaisesRegex(NativeUIError,'Declared changed input predicate'):
                owner.decode(owner.previous)


if __name__=='__main__':unittest.main()
