"""Normal original baking/import inputs; no oven or rendering qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_controls import project
from ios.adapters.assets_tree_controls import project as tree
from ios.adapters.assets_usage_controls import project as usage
from ios.adapters.normal_input import observation
from ios.self_tests.assets_usage_fixture import Fixture,RUN


class AssetsUsageControlsTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.path=Path(directory.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.f.seeded_fbx_page();self.b=self.f.boundary
        self.commands=[];self.store=PrivateFeatureState(self.path/'usage-input-intents.json');self.previous=None;self.select()
    def capture(self):return self.f.input.capture()
    def current(self):return usage(self.capture(),self.b.page)
    def send(self,identifier,*,reference=None):
        reference=project(self.capture()) if reference is None else reference
        def intent(command):
            self.commands.append(deepcopy(command));value=dict(commands=self.commands);self.store.write(value,self.previous);self.previous=deepcopy(value);return True
        return self.f.input.assets_input(identifier,'activate',reference=reference,before_send=intent)
    def select(self):
        current=tree(self.capture(),self.b.page);path='/e2e-'+RUN+'/'
        for wanted in (path,path+'stand.fbx'):
            current=tree(self.capture(),self.b.page);rows=[row for row in current['rows'] if row['model']['path']==wanted]
            self.assertEqual(1,len(rows));self.send('assets.tree.row.'+str(rows[0]['index']))
    def test_original_checkbox_toggles_actual_service_and_independent_inventory_status(self):
        before=self.current();self.assertFalse(before['baking']['checked']);self.assertTrue(before['baking']['enabled'])
        self.send('assets.baking');after=self.current();self.assertTrue(after['baking']['checked'])
        proof=self.f.replies.read('baked');self.assertEqual(4,proof['mappings'][0]['status'])
        self.send('assets.baking');self.assertFalse(self.current()['baking']['checked']);self.assertEqual(1,self.f.replies.read('disabled')['mappings'][0]['status'])
        self.assertEqual([True,False],[event['enabled'] for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='baking-started'])
    def test_original_add_to_world_opens_actual_model_defaults_and_accepts_original_url(self):
        self.send('assets.import');current=self.current();self.assertTrue(current['model']['visible']);self.assertEqual('atp:/e2e-'+RUN+'/stand.fbx',current['model']['url'])
        self.assertEqual(2,current['model']['shapeIndex']);self.assertFalse(current['model']['dynamicChecked']);self.assertEqual(dict(x=0,y=1,z=-2),current['model']['position'])
        self.send('assets.model.accept');self.assertFalse(self.current()['model']['visible']);events=[event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='entity-returned']
        self.assertEqual(1,len(events));self.assertEqual('Model',events[0]['type']);self.assertEqual('stand.fbx',events[0]['args'][0]);self.assertEqual('atp:/e2e-'+RUN+'/stand.fbx',events[0]['args'][1]);self.assertEqual('simple-compound',events[0]['args'][3])

    def test_uploaded_import_consumes_existing_product_url_without_claiming_an_upload(self):
        # Explicit pre-existing product boundary input, not upload evidence.
        url='atp:/e2e-'+RUN+'/stand.fbx';self.b.configure(uploadedPrimaryUrl=url);self.send('assets.import-uploaded');current=self.current()
        self.assertEqual(url,current['model']['url']);self.assertEqual('stand.fbx',current['model']['name']);self.send('assets.model.cancel')
        self.assertEqual(0,self.b.host_state['uploads'])

    def test_deferred_baking_keeps_actual_busy_disabled_ui_until_original_callback(self):
        self.b.configure(deferBaking=True);self.send('assets.baking');self.assertTrue(self.current()['busy']);self.assertFalse(self.current()['baking']['enabled']);count=len(self.commands)
        with self.assertRaises(NativeUIError):self.send('assets.baking')
        self.assertEqual(count,len(self.commands));self.b.configure(completeBaking=True);self.assertFalse(self.current()['busy']);self.assertTrue(self.current()['baking']['checked'])

    def test_permission_change_after_model_open_preserves_the_original_denied_handler(self):
        self.send('assets.import');reference=project(self.capture());count=len(self.commands);self.b.configure(canRez=False,canRezTmp=False)
        with self.assertRaises(NativeUIError):self.send('assets.model.accept',reference=reference)
        self.assertEqual(count,len(self.commands));self.send('assets.model.accept');self.assertIn('do not have permission',self.b.host_state['page']['status'])
        self.assertFalse(any(event['kind']=='entity-returned' for event in self.b.host_state['bundleInfo']['serviceEvents']))
    def test_external_model_text_and_permission_changes_invalidate_acceptance_tokens(self):
        self.send('assets.import');reference=project(self.capture());count=len(self.commands);self.b.configure(modelUrl='atp:/foreign/model.fbx')
        with self.assertRaises(NativeUIError):self.send('assets.model.accept',reference=reference)
        self.assertEqual(count,len(self.commands));self.assertFalse(any(event['kind']=='entity-returned' for event in self.b.host_state['bundleInfo']['serviceEvents']))
        self.send('assets.model.cancel');self.b.configure(canRez=False,canRezTmp=False);self.assertFalse(self.current()['importEnabled'])
        with self.assertRaises(NativeUIError):self.send('assets.import')
    def test_effective_permission_is_distinct_from_cached_ui_and_original_writable_handler(self):
        self.b.configure(effectiveWrite=False);current=self.current();self.assertTrue(current['canWrite']);self.assertTrue(current['baking']['enabled']);self.assertFalse(current['permissions']['canWriteAssets'])
        self.send('assets.baking');self.assertFalse(self.current()['canWrite']);self.assertFalse(any(event['kind']=='baking-started' for event in self.b.host_state['bundleInfo']['serviceEvents']))
        self.assertIn('requires Asset Server permission',self.b.host_state['page']['status'])
    def test_model_cancel_and_denied_entity_return_are_not_import_or_render_success(self):
        self.send('assets.import');self.send('assets.model.cancel');self.assertFalse(any(event['kind']=='entity-returned' for event in self.b.host_state['bundleInfo']['serviceEvents']))
        self.b.configure(entityDenied=True);self.send('assets.import');self.send('assets.model.accept');self.assertIn('Import failed',self.b.host_state['page']['status'])
    def test_usage_extension_permission_types_metadata_join_and_fresh_source_are_strict(self):
        packet=self.capture()
        for mutate in (lambda value:value['assetUsageInventory']['pages'][0]['permissions'].update(canWriteAssets=1),lambda value:value['assetUsageInventory'].update(capturedEpochMs=1),
                lambda value:value['assetUsageInventory']['pages'][0].update(currentPath='/foreign/'),lambda value:value['assetUsageInventory'].update(iosAssetsUsageUiVersion=True)):
            wrong=deepcopy(packet);mutate(wrong)
            with self.assertRaises(NativeUIError):observation(wrong,42,self.b.clock())
    def test_usage_inputs_require_durable_intents_and_cannot_replace_model_url(self):
        reference=project(self.capture())
        with self.assertRaises(NativeUIError):self.f.input.assets_input('assets.baking','activate',reference=reference)
        self.send('assets.import');self.send('assets.model.url');reference=project(self.capture())
        with self.assertRaises(NativeUIError):self.f.input.assets_input('assets.model.url','replace',text='atp:/foreign/model.fbx',reference=reference,before_send=lambda _q:True)

    def test_missing_new_source_stays_unavailable_without_replacing_literal_legacy_rows(self):
        packet=self.capture();packet['controls']=[row for row in packet['controls'] if row['assetControl']['assetControlVersion']!=4]
        packet['assetUsageInventory'].update(available=False,complete=False,pages=[]);observation(packet,42,self.b.clock());project(packet)
        with self.assertRaises(NativeUIError):usage(packet,self.b.page)
