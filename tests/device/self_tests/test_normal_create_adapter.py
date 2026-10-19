"""Owned Create adapter logic, with substituted native UI/service boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_create import NormalCreate, avatar_entities
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUIError
from create_journey import INITIAL, EDITED
from create_observation import PREFIX
from test_normal_script_manager import Boundary, BINDING

NONCE = 'a' * 32
URL = 'http://fixture.test/create/' + NONCE + '/observer.js'
NAME = PREFIX + NONCE + '_cube'
UUID = '{11111111-1111-1111-1111-111111111111}'


class NativeCreate(Boundary):
    def __init__(self, directory):
        super().__init__(directory)
        self.entities = []
        self.page = 'scripts'
        self.ignored_create = self.ignored_delete = self.partial_create = False
        self.complete = True
        self.ignore_import = False
        self.ignore_name = False
        self.selected = None
        self.originals = []

    def observe(self, after):
        value, epoch = super().observe(after)
        value.update(entitiesComplete=self.complete, avatarEntities=deepcopy(self.entities))
        return value, epoch

    def open_manager(self):
        super().open_manager(); self.page = 'scripts'
    def manager_visible(self): return super().manager_visible() and self.page == 'scripts'
    def open_create(self): self.page = 'create'; self.calls.append('open-create')
    def wait_create(self):
        if self.page != 'create': raise NativeUIError('no Create')
    def create_cube(self):
        self.calls.append('create-cube')
        if not self.ignored_create: self.entities.append(dict(id=UUID, name='', type='Box'))
        if self.partial_create: raise NativeUIError('uncertain Shape click')
    def select_entity(self, identifier):
        self.selected = next(row for row in self.entities if row['id'] == identifier)
        self.calls.append('select-entity')
    def name_entity(self, name):
        if not self.ignore_name: self.selected['name'] = name
        self.calls.append('name-entity')
    def edit_properties(self, values): self.calls.append('edit-properties')
    def delete_entity(self):
        self.calls.append('delete-entity')
        if not self.ignored_delete: self.entities.remove(self.selected)
    def history(self, action): self.calls.append(action)
    def import_entities(self, url):
        self.calls.append('import')
        if not url.endswith('missing.json') and not self.ignore_import:
            for n, role in enumerate(('import-parent', 'import-child'), 2):
                self.entities.append(dict(id='{' + str(n) * 8 + '-1111-1111-1111-111111111111}',
                    name=PREFIX + NONCE + '_' + role, type='Shape'))


class NormalCreateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.chmod(self.temp.name, 0o700)
        self.native = NativeCreate(self.temp.name)
        self.store = PrivateFeatureState(Path(self.temp.name) / 'create.json')
    def tearDown(self): self.temp.cleanup()
    def flow(self):
        scripts = NormalScriptManager(self.native, self.native.observe, self.native.store, BINDING,
            source_kind='create-observer', monotonic=lambda: self.native.clock, sleep=self.native.sleep)
        return NormalCreate(self.native, scripts, self.store, BINDING)
    def invoke(self, operation, values=None): return self.flow().invoke(operation, values or {})
    def open(self): self.invoke('create.reference.open', {'scriptUrl': URL})
    def cube(self): self.invoke('create.cube', {'name': NAME, 'properties': INITIAL})
    def close(self): return self.invoke('create.reference.close', {'scriptUrl': URL})

    def test_normal_create_edit_history_import_and_cleanup_keep_input_and_observer_separate(self):
        self.open(); self.cube()
        self.assertEqual(NAME, self.native.entities[0]['name'])
        self.invoke('create.update', {'name': NAME, 'properties': EDITED})
        self.invoke('create.undo'); self.invoke('create.redo')
        self.invoke('create.delete', {'names': [NAME]})
        self.invoke('create.import', {'url': URL.replace('observer.js', 'entities.json')})
        self.assertEqual(2, len(self.native.entities))
        self.assertEqual({'performed': True}, self.close())
        self.assertEqual([], self.native.entities)
        self.assertEqual([], self.native.rows)
        self.assertIsNone(self.store.read())
        self.assertIsNone(self.native.store.read())
        self.close()

    def test_uncertain_shape_input_is_not_replayed_and_unnamed_entity_is_recovered(self):
        self.open()
        self.native.partial_create = True
        with self.assertRaises(NativeUIError): self.cube()
        self.assertEqual('', self.native.entities[0]['name'])
        self.assertIsNotNone(self.store.read()['pendingBeforeIds'])
        self.close()
        self.assertEqual([], self.native.entities)
        self.assertEqual(1, self.native.calls.count('create-cube'))

    def test_ignored_create_is_detected_and_cleanup_checks_for_late_creation(self):
        self.open(); self.native.ignored_create = True
        with self.assertRaises(NativeUIError): self.cube()
        before = self.native.clock
        self.close()
        self.assertGreaterEqual(self.native.clock - before, 3)
        self.assertEqual(1, self.native.calls.count('create-cube'))

    def test_duplicate_new_entities_and_incomplete_queries_retain_pending_ownership(self):
        self.open(); self.native.partial_create = True
        with self.assertRaises(NativeUIError): self.cube()
        self.native.entities.append(dict(id='{22222222-1111-1111-1111-111111111111}', name='', type='Box'))
        with self.assertRaises(NativeUIError): self.close()
        self.assertIsNotNone(self.store.read()['pendingBeforeIds'])
        self.native.complete = False
        with self.assertRaises(NativeUIError): self.close()
        self.assertNotIn('delete-entity', self.native.calls)

    def test_ignored_delete_cannot_stop_observer_or_report_cleanup(self):
        self.open(); self.cube(); self.native.ignored_delete = True
        with self.assertRaises(NativeUIError): self.close()
        self.assertNotIn('stop', self.native.calls)
        self.assertIsNotNone(self.store.read())

    def test_foreign_existing_names_sources_and_entities_are_not_adopted(self):
        self.native.entities = [dict(id=UUID, name=NAME, type='Shape')]
        with self.assertRaises(NativeUIError): self.open()
        self.assertEqual([], self.native.calls)
        self.native.entities = []
        self.open()
        with self.assertRaises(NativeUIError):
            self.invoke('create.cube', {'name': NAME.replace(NONCE, 'f' * 32), 'properties': INITIAL})
        self.native.entities.append(dict(id=UUID, name=NAME, type='Box'))
        with self.assertRaises(NativeUIError): self.invoke('create.delete', {'names': [NAME]})
        self.assertNotIn('delete-entity', self.native.calls)

    def test_actual_entity_ids_and_completeness_are_required(self):
        for row in (dict(id='../foreign', name=NAME, type='Box'), dict(id=UUID, name=NAME, type=None)):
            with self.assertRaises(NativeUIError): avatar_entities(dict(entitiesComplete=True, avatarEntities=[row]))
        with self.assertRaises(NativeUIError):
            avatar_entities(dict(entitiesComplete=False, avatarEntities=[]))

    def test_foreign_replacement_cannot_inherit_an_owned_name(self):
        self.open(); self.cube()
        self.native.entities[0]['id'] = '{99999999-1111-1111-1111-111111111111}'
        with self.assertRaises(NativeUIError): self.invoke('create.delete', {'names': [NAME]})
        self.assertNotIn('delete-entity', self.native.calls)

    def test_unresolved_import_cannot_be_forgotten_as_an_empty_cleanup(self):
        self.open(); self.native.ignore_import = True
        with self.assertRaises(NativeUIError):
            self.invoke('create.import', {'url': URL.replace('observer.js', 'entities.json')})
        with self.assertRaises(NativeUIError): self.close()
        self.assertIsNotNone(self.store.read()['pendingImportBeforeIds'])
        self.assertNotIn('stop', self.native.calls)

    def test_cleanup_deletes_owned_unnamed_effect_even_when_product_ignores_name_edit(self):
        self.open(); self.native.ignore_name = True
        with self.assertRaises(NativeUIError): self.cube()
        self.assertEqual('', self.native.entities[0]['name'])
        edits = self.native.calls.count('name-entity')
        self.close()
        self.assertEqual([], self.native.entities)
        self.assertEqual(edits, self.native.calls.count('name-entity'))


if __name__ == '__main__': unittest.main()
