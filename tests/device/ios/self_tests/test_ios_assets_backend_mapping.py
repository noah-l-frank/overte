"""One bounded original-QML mapping/backend-restoration host composition.

Candidate/native/Qt/HTTP/backend/oven boundaries stay declared models. Original
ordinary QML, real files, weak holders, binary reads and durable originals run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_backend_mapping_fixture import Fixture,RUN


class AssetsBackendMappingTests(unittest.TestCase):
    def test_original_mapping_flow_and_independent_backend_restoration_retire_only_same_successor(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);directory.chmod(0o700);fixture=Fixture(directory)
            try:
                for attribute,kind in (('file_store','files'),('picker_store','picker'),('upload_store','upload'),('reply_store','replies'),('tree_store','tree')):
                    getattr(fixture,attribute).path=directory/('ios-assets-'+RUN+'-primary-'+kind+'.json')
                upload=fixture.owner();tree=fixture.tree_owner(upload);runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=fixture.boundary.monotonic)
                parts=dict(owned_files=fixture.files,picker=fixture.picker,owned_replies=fixture.replies,upload=upload,tree=tree,check=upload.guard)
                with patch.object(runtime,'_assets_components',return_value=parts),patch.object(runtime,'state_path',return_value=directory/'session.json'),patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    proof=runtime._assets_mapping_with_backend('test-only',RUN,'primary',fixture.files.url,'b'*32,fixture.lock,fixture.backend.config)
                self.assertGreaterEqual(proof['hostQuietMs'],3000);self.assertGreaterEqual(proof['nativeQuietMs'],3000)
                self.assertEqual('retired',upload.state['phase']);self.assertEqual('deleted',tree.state['phase']);self.assertIsNotNone(tree.state['clientClosedBy']);self.assertEqual('primary-chosen',fixture.picker.state['phase'])
                self.assertEqual(fixture.backend.initial,fixture.backend.mappings);self.assertEqual(fixture.backend.initial_names,{path.name for path in fixture.backend.b.files.iterdir()})
                clocks=len(fixture.boundary.native_clock.commands);requests=len(fixture.requests);rows=inspect_directory(directory)
                self.assertEqual([],rows[0]['responsibilities']);self.assertTrue(rows[0]['successor']);self.assertTrue(rows[0]['clientRetired'])
                self.assertEqual(clocks,len(fixture.boundary.native_clock.commands));self.assertEqual(requests,len(fixture.requests));self.assertEqual([],runtime.cleanup_errors)
            finally:fixture.close()
