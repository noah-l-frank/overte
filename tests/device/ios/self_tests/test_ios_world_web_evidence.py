"""Repeated recipes retain all checkpoint evidence without expected facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.fixtures import context
from ios.adapters.world_web_evidence import required


class WorldWebEvidenceTests(unittest.TestCase):
    def test_repeated_reload_has_real_image_requirement_at_both_occurrences(self):
        rows=[row for row in SCENARIOS['world-web']['steps'] if row['verb']=='reload']
        self.assertEqual([['peer'],['image','peer']],[row['evidence'] for row in rows])
        self.assertEqual({'image','peer'},required('a'*32,'reload',{}))
        self.assertNotIn('changed',required('a'*32,'reload',{}))

    def test_each_recipe_preserves_every_original_requirement_and_contract_is_unchanged(self):
        run='a'*32;before=deepcopy(SCENARIOS['world-web'])
        for row in before['steps']:
            result=required(run,row['verb'],expand(row['inputs'],context(run)))
            self.assertTrue(set(row['evidence'])<=result)
            self.assertTrue(result<={'image','changed','peer'})
        self.assertEqual(before,SCENARIOS['world-web'])
        with self.assertRaises(NativeUIError):required(run,'reload',{'resource':'recovery.html'})
        with self.assertRaises(NativeUIError):required(run,'unknown',{})
        self.assertEqual(set(),required(run,'cleanup',{}))


if __name__=='__main__':unittest.main()
