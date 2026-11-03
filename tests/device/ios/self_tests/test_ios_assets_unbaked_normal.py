"""Fresh original QML bundle imports and independent original body joins.

Native/SDK/Qt/parser/server producers are declared host models. These cases
qualify component logic only and cannot advertise a whole Assets capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.self_tests.assets_unbaked_fixture import Fixture,RUN


class AssetsUnbakedNormalTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700)
        self.fixture=Fixture(self.path);self.addCleanup(self.fixture.close)
        self.runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.fixture.boundary.monotonic)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.fixture))
    def prepare(self,resource,*,renamed=False):
        f=self.fixture;f.boundary.reads.resource=resource;parts=f.parts(renamed=renamed)
        return self.runtime._assets_prepare_unbaked_upload('existing-component-parts',RUN,'primary',f.files.url,'b'*32,
            f.lock,f.backend.config,resource=resource,parts=parts)
    def no_bake(self):
        self.assertEqual([],self.fixture.implicit_jobs)
        self.assertFalse(any(row['kind']=='baking-started' for row in self.fixture.boundary.host_state['bundleInfo']['serviceEvents']))

    def test_actual_gltf_renamed_folder_import_keeps_all_companions_and_parses_original_unbaked_body(self):
        parts=self.prepare('gltf-bundle/main.gltf',renamed=True)
        tree=parts['tree'];tree.reserve();tree.browse();tree.rename()
        proof=self.runtime._assets_import_unbaked(parts)
        self.assertEqual(1,proof['assetModelBundleInputProofVersion']);self.assertNotIn('assetModelBakedInputProofVersion',proof)
        self.assertTrue(proof['path'].startswith('/renamed-'+RUN+'/'))
        self.assertEqual({'main.gltf','mesh/triangle.bin','textures/checker.png'},
            {row['path'][len('/renamed-'+RUN+'/'):] for row in proof['files']})
        self.assertEqual('observed',parts['parsed'].state['phase']);self.assertEqual('geometry-observed',parts['model'].state['phase'])
        self.assertEqual(2,parts['usage'].previous['iosAssetsUsageOwnerVersion']);self.no_bake()
        actual=self.fixture.boundary.models[proof['entityId']]
        self.assertTrue(actual.loaded);self.assertTrue(actual.added);self.assertEqual(proof['sha256'],actual.download['sha256'])

    def test_actual_obj_import_has_separate_unbaked_parser_body_and_original_material_texture_files(self):
        parts=self.prepare('obj-bundle/main.obj');proof=self.runtime._assets_import_unbaked(parts)
        self.assertEqual('obj-bundle/main.obj',proof['resource'])
        self.assertEqual({'main.obj','materials/palette.mtl','textures/checker.png'},
            {row['path'][len('/e2e-'+RUN+'/'):] for row in proof['files']})
        self.assertNotIn('bakeRequestId',proof);self.assertNotIn('outputPath',proof);self.no_bake()
        inputs=deepcopy(self.fixture.boundary.inputs);requests=deepcopy(self.fixture.requests)
        self.assertEqual(proof,parts['parsed'].observe())
        self.assertEqual(inputs,self.fixture.boundary.inputs);self.assertEqual(requests,self.fixture.requests)

    def test_normal_upload_ack_without_independent_companion_mapping_refuses_before_model_import(self):
        f=self.fixture;f.drop_server_companion=True
        with self.assertRaises(NativeUIError):self.prepare('gltf-bundle/main.gltf')
        self.assertEqual(1,f.boundary.host_state['uploads']);self.assertEqual({},f.boundary.models)
        self.assertFalse(any(name.endswith('/mesh/triangle.bin') for name in f.backend.mappings))
        self.assertEqual([],f.boundary.scene.events);self.no_bake()

    def test_model_accept_ack_with_held_real_delivery_cannot_qualify_until_actual_callback_without_resend(self):
        f=self.fixture;f.boundary.AUTO_MODEL_DELIVERY=False
        parts=self.prepare('obj-bundle/main.obj');usage,model=parts['usage'],parts['model']
        usage.reserve();usage.select();model.reserve();model.start()
        self.assertIsNone(model.observe());self.assertEqual('adopted',model.state['phase'])
        self.assertIsNone(model.state['geometryObserved']);self.assertIsNone(parts['parsed'].state)
        identity=model.state['creation']['proof']['entityId'];actual=f.boundary.models[identity]
        self.assertFalse(actual.loaded);self.assertFalse(actual.added)
        inputs=deepcopy(f.boundary.inputs);f.boundary.deliver_model(identity)
        self.assertIsNotNone(model.observe());self.assertEqual(inputs,f.boundary.inputs)
        parts['parsed'].reserve();proof=parts['parsed'].observe()
        self.assertEqual(identity,proof['entityId']);self.assertEqual(inputs,f.boundary.inputs);self.no_bake()
