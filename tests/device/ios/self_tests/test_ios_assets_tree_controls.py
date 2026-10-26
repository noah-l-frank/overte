"""Original tree/rename/delete UI and independently serialized mapping replies.

Qt/native/service/candidate boundaries remain explicit host models. No build,
server or device is started; normal adapter input executes original QML bodies.
"""
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
from ios.adapters.normal_input import observation
from ios.self_tests.assets_tree_fixture import Fixture,RUN


class AssetsTreeControlsTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);self.path=Path(directory.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.b=self.f.boundary;self.f.seeded_page()
        self.store=PrivateFeatureState(self.path/'source-input-intents.json');self.saved=None;self.commands=[]

    def capture(self):return self.f.input.capture()
    def page(self):return tree(self.capture(),self.b.page)
    def input(self,identifier,action='activate',*,text=None,reference=None):
        reference=project(self.capture()) if reference is None else reference
        def intent(command):
            self.commands.append(deepcopy(command));current=dict(testSourceInputIntents=self.commands);self.store.write(current,self.saved);self.saved=deepcopy(current);return True
        return self.f.input.assets_input(identifier,action,text=text,reference=reference,before_send=intent)
    def row(self,path):
        rows=[row for row in self.page()['rows'] if row['model']['path']==path];self.assertEqual(1,len(rows));return 'assets.tree.row.'+str(rows[0]['index'])
    def root(self):return '/e2e-'+RUN+'/'

    def test_actual_qml_tree_selection_expand_rename_and_delete_join_independent_inventory(self):
        before=self.f.replies.read('before');self.assertEqual(3,len(before['mappings']));root=self.root();renamed='/renamed-'+RUN+'/'
        self.input(self.row(root));self.assertEqual([root],self.page()['selectedPaths']);self.assertTrue(self.page()['rows'][0]['expanded'])
        self.input(self.row(root+'main.gltf'));self.assertEqual(root+'main.gltf',self.page()['currentPath'])
        self.assertEqual('atp:'+root+'main.gltf',self.page()['currentUrl'])
        self.input(self.row(root));self.input('assets.rename');self.input('assets.rename.path');self.input('assets.rename.path','replace',text=renamed);self.input('assets.rename.accept')
        after=self.f.replies.read('after-rename');self.assertEqual({renamed+row['path'][len(root):]:row['hash'] for row in before['mappings']},{row['path']:row['hash'] for row in after['mappings']})
        self.assertFalse(any(row['model']['path'].startswith(root) for row in self.page()['rows']))
        self.input(self.row(renamed));self.input('assets.delete');self.input('assets.delete.accept')
        final=self.f.replies.read('after-delete');self.assertEqual([],final['mappings']);self.assertEqual([],self.page()['modelRows']);self.f.replies.close()

    def test_external_selection_change_invalidates_delete_confirmation_before_delivery(self):
        root=self.root();self.input(self.row(root));self.input('assets.delete');reference=project(self.capture());count=len(self.commands)
        # A declared external-user model change at the producer boundary.
        self.b.configure(serverRows=[]);self.b.reads.data.clear()
        with self.assertRaises(NativeUIError):self.input('assets.delete.accept',reference=reference)
        self.assertEqual(count,len(self.commands));self.assertFalse(any(event['kind']=='mapping-started' for event in self.b.host_state['bundleInfo']['serviceEvents']))

    def test_actual_rename_text_changes_are_part_of_acceptance_tokens(self):
        self.input(self.row(self.root()));self.input('assets.rename');self.input('assets.rename.path');self.input('assets.rename.path','replace',text='/renamed-'+RUN+'/')
        reference=project(self.capture());count=len(self.commands)
        self.b.exchange(dict(op='input',id='assets.rename.path',action='replace',text='/foreign/'))
        with self.assertRaises(NativeUIError):self.input('assets.rename.accept',reference=reference)
        self.assertEqual(count,len(self.commands));self.assertEqual(3,len(self.b.reads.data))

    def test_owned_rename_field_refuses_foreign_and_nested_destinations(self):
        self.input(self.row(self.root()));self.input('assets.rename');self.input('assets.rename.path');count=len(self.commands)
        for text in ('/foreign/','/renamed-'+RUN+'/nested/',' /renamed-'+RUN+'/','/renamed-'+RUN+'/../'):
            with self.subTest(text=text),self.assertRaises(NativeUIError):self.input('assets.rename.path','replace',text=text)
        self.assertEqual(count,len(self.commands));self.assertEqual(3,len(self.b.reads.data))

    def test_disabled_delete_never_dispatches_the_original_mutation_handler(self):
        self.input(self.row(self.root()));self.b.configure(canWrite=False);count=len(self.commands)
        with self.assertRaises(NativeUIError):self.input('assets.delete')
        self.assertEqual(count,len(self.commands));self.assertFalse(self.page()['deleteVisible']);self.assertEqual(3,len(self.b.reads.data))

    def test_original_ui_rows_cannot_supply_hashes_or_foreign_model_identity(self):
        packet=self.capture()
        for mutate in (lambda value:value['assetTreeInventory']['pages'][0]['modelRows'][0].update(hash='f'*64),
                lambda value:value['assetTreeInventory']['pages'][0].update(modelId='99999999-9999-4999-8999-999999999999'),
                lambda value:value['assetTreeInventory'].update(iosAssetsTreeUiVersion=True)):
            wrong=deepcopy(packet);mutate(wrong)
            with self.assertRaises(NativeUIError):observation(wrong,42,self.b.clock())

    def test_flattened_rows_and_current_selection_must_join_original_model_indexes(self):
        self.input(self.row(self.root()));packet=self.capture()
        for mutate in (lambda value:value['assetTreeInventory']['pages'][0]['rows'][1]['model'].update(modelIndex=[63]),
                lambda value:value['assetTreeInventory']['pages'][0].update(selectedPaths=['/foreign/']),
                lambda value:value['assetTreeInventory']['pages'][0]['rows'][0].update(expanded=1)):
            wrong=deepcopy(packet);mutate(wrong)
            with self.assertRaises(NativeUIError):observation(wrong,42,self.b.clock())

    def test_tree_extension_cannot_replace_weak_roots_or_bypass_input_ownership(self):
        packet=self.capture();wrong=deepcopy(packet);wrong.pop('assetControlsVersion');wrong.pop('assetInventory')
        with self.assertRaises(NativeUIError):observation(wrong,42,self.b.clock())
        with self.assertRaises(NativeUIError):self.f.input.assets_input('assets.refresh','activate',reference=project(packet))
