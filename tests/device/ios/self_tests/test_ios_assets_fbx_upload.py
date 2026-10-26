"""One ordinary pinned-FBX upload/readback/client-cleanup source composition.

Native/Qt/service/candidate boundaries remain declared host models. No actual
AssetServer, oven, compiler, renderer, device or complete feature verdict runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from feature_journeys.fixtures import pinned_resource
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_usage_fixture import Fixture,RUN,TICKET


class AssetsFbxUploadTests(unittest.TestCase):
    def test_original_normal_fbx_bundle_upload_independent_bytes_and_client_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);directory.chmod(0o700);fixture=Fixture(directory)
            try:
                for attribute,kind in (('file_store','files'),('picker_store','picker'),('upload_store','upload'),('reply_store','replies')):getattr(fixture,attribute).path=directory/('ios-assets-'+RUN+'-primary-'+kind+'.json')
                boundary=fixture.boundary;self.assertEqual({},boundary.reads.data);boundary.reads.resource='asset-stand.fbx'
                fixture.files.reserve(TICKET,'asset-stand.fbx');fixture.files.stage();fixture.picker.reserve();fixture.picker.open_page();fixture.picker.open_picker();fixture.picker.choose_primary();fixture.replies.reserve(TICKET,'asset-stand.fbx')
                upload=fixture.owner();upload.reserve();upload.review();upload.destination();upload.start_upload();proof=upload.uploaded()
                self.assertEqual('uploaded',upload.state['phase']);self.assertEqual(1,boundary.host_state['uploads']);self.assertEqual(['stand.fbx'],[row['relativePath'] for row in proof['files']])
                original=pinned_resource('asset-stand.fbx');self.assertEqual(25196,len(original));self.assertEqual(original,base64.b64decode(proof['files'][0]['body']['base64'],validate=True))
                self.assertEqual(original,boundary.reads.data['/e2e-'+RUN+'/stand.fbx']);self.assertEqual([],fixture.replies.proof('upload-before')['mappings'])
                before=deepcopy(boundary.inputs);restored=fixture.owner();self.assertEqual('uploaded',restored.state['phase']);self.assertEqual(before,boundary.inputs)
                final=restored.cleanup();self.assertEqual({'exists':False,'files':[]},final['source']['files']);self.assertFalse(boundary.root.exists());self.assertEqual('primary-chosen',fixture.picker.state['phase'])
                requests=deepcopy(boundary.requests);clocks=deepcopy(boundary.native_clock.commands);reads=deepcopy(boundary.reads.requests);rows=inspect_directory(directory)
                self.assertEqual(['server-retirement'],rows[0]['responsibilities']);self.assertEqual(requests,boundary.requests);self.assertEqual(clocks,boundary.native_clock.commands);self.assertEqual(reads,boundary.reads.requests)
                self.assertEqual(original,boundary.reads.data['/e2e-'+RUN+'/stand.fbx']);self.assertEqual(2,fixture.file_store.read()['iosAssetsFileOwnerVersion'])
            finally:fixture.close()


if __name__=='__main__':unittest.main()
