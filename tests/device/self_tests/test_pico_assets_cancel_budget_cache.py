"""Existing child state/physical reads; Native budget counter changes are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack,canonical,MAX_FRAMES,MAX_RAW
import test_assets_prefix as fixtures


class AssetsCancelBudgetCacheTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='pico-assets-child-budget-'));self.root.chmod(0o700)
        self.fixture=fixtures.AssetsPrefixTests(methodName='runTest')
        environment=patch.dict(os.environ,OVERTE_ASSETS_PREFIX_EVIDENCE=str(self.root));environment.start()
        self.addCleanup(environment.stop)
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.parent=self.fixture.owner;self.model=self.fixture.model;self.child=None

    def opened(self,*,selected=True):
        self.fixture.open();factory=self.parent.cancel_factory
        def create():
            child=factory()
            if selected:child.bind_budget_cache()
            self.child=child;return child
        self.parent.cancel_factory=create
        result=self.parent.act(self.model.activate('upload-picker-open',{'resource':'gltf-bundle/main.gltf'}))
        self.assertTrue(result['pickerObserved']);self.assertIs(self.child,self.parent.child)
        return self.child

    def test_default_mode_retains_original_two_field_cache_and_rejects_late_binding(self):
        child=self.opened(selected=False);before=len(self.model.inputs)
        self.assertFalse(child.budget_cache);self.assertEqual(2,len(child.validation_cache))
        with self.assertRaises(NativeUIError):child.bind_budget_cache()
        self.assertEqual(before,len(self.model.inputs))

    def test_unchanged_semantics_still_read_current_file_when_native_count_changes(self):
        child=self.opened();history=deepcopy(child.files.native.history)
        self.assertTrue(child.budget_cache);self.assertEqual(4,len(child.validation_cache))
        read=child.store.read;validate=child.validate
        try:
            with patch.object(child.store,'read',wraps=read) as physical,patch.object(child,'validate',wraps=validate) as full:
                for count in range(4):
                    child.files.native.history=history+([None] if count%2 else [])
                    child.state()
            self.assertEqual(4,physical.call_count);self.assertEqual(0,full.call_count)
        finally:child.files.native.history=history

    def test_live_history_bound_never_reuses_an_earlier_admissible_budget(self):
        child=self.opened();history=child.files.native.history;fixed=child.validation_cache[2]
        before=len(self.model.inputs)
        try:
            child.files.native.history=[None]*(MAX_FRAMES-fixed);child.state()
            child.files.native.history.append(None)
            with self.assertRaises(NativeUIError):child.state()
        finally:child.files.native.history=history
        self.assertEqual(before,len(self.model.inputs))

    def test_live_file_byte_bound_never_reuses_an_earlier_admissible_budget(self):
        child=self.opened();packed=deepcopy(child.files.state['originals']);fixed=child.validation_cache[3]
        before=len(self.model.inputs)
        try:
            child.files.state['originals']['bytes']=MAX_RAW-fixed;child.state()
            child.files.state['originals']['bytes']+=1
            with self.assertRaises(NativeUIError):child.state()
        finally:child.files.state['originals']=packed
        self.assertEqual(before,len(self.model.inputs))

    def test_public_mode_mutation_and_rebinding_refuse_without_further_input(self):
        child=self.opened();before=len(self.model.inputs)
        with self.assertRaises(NativeUIError):child.bind_budget_cache()
        child.budget_cache=False
        with self.assertRaises(NativeUIError):child.state()
        self.assertEqual(before,len(self.model.inputs))

    def test_equal_but_replaced_cache_tuple_is_not_admitted(self):
        child=self.opened();before=len(self.model.inputs)
        child.validation_cache=tuple(list(child.validation_cache))
        self.assertIsNot(child.validation_cache,child._sealed_validation_cache)
        with self.assertRaises(NativeUIError):child.state()
        self.assertEqual(before,len(self.model.inputs))

    def test_actual_semantic_file_change_cannot_hide_behind_warm_cache(self):
        child=self.opened();before=len(self.model.inputs);old=child.store.read()
        changed=deepcopy(old);changed['runId']='0'*32
        child.store.write(changed,old);child.previous=deepcopy(changed)
        with self.assertRaises(NativeUIError):child.state()
        self.assertEqual(before,len(self.model.inputs))

    def test_expected_type_change_cannot_alias_validated_canonical_json(self):
        child=self.opened();before=len(self.model.inputs)
        child.previous['unresolvedInputs']=tuple(child.previous['unresolvedInputs'])
        with self.assertRaises(NativeUIError):child.state()
        self.assertEqual(before,len(self.model.inputs))


if __name__=='__main__':unittest.main()
