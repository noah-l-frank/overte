"""Normal file selection precedes real host app code and original admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles
from ios.adapters.normal_input import observation
from ios.self_tests.tablet_web_normal_fixture import TabletNormalBoundary


class TabletNormalSetupTests(unittest.TestCase):
    def test_generated_Home_controls_conform_to_actual_NativeInput_source_extension(self):
        boundary=TabletNormalBoundary(self)
        files=OwnedTabletWebAppFiles(None,PrivateFeatureState(boundary.root/'preflight-files.json'),boundary.binding)
        metadata=files.reserve_app(boundary.source.run,boundary.source.fixture,'b'*32)
        from ios.adapters.tablet_web_app_files import originals
        import base64
        query=dict(schemaVersion=1,action='feature-script-files',commandId='ios-'+'e'*32,operation='stage',runId=metadata['runId'],ownerToken=metadata['ownerToken'],
            files={name:base64.b64encode(raw).decode() for name,raw in originals(metadata['featureRun'],metadata['fixtureUrl'],metadata['ticket'],metadata['nonce']).items()})
        boundary.produce(query);boundary.load(boundary.directories[metadata['runId']].as_uri()+'/script.js');boundary.ui.qt.opened=True
        _name,packet=boundary.produce(dict(action='normal-ui-input',operation='observe',commandId='ios-'+'f'*32))
        self.assertIs(packet['observation'],observation(packet['observation'],42,boundary.epoch()))
        self.assertEqual(3,len([row for row in packet['observation']['controls'] if 'tabletAppButton' in row]))
        reference=boundary.runtime.remember_app(metadata)
        self.assertEqual(reference,boundary.source.state['apps'][-1])

    def test_actual_W3C_file_selection_runs_exact_generated_app_before_source_admission(self):
        boundary=TabletNormalBoundary(self);owner=TabletWebAppOwner(boundary.runtime)
        reference=owner.prepare('b'*32)
        self.assertEqual(reference,owner.state['generations'][0]['admission'])
        self.assertEqual(1,len(boundary.loaded));self.assertEqual(3,len(boundary.controls))
        self.assertEqual(1,boundary.ui.file_ui.actions.count('script-file.confirm'))
        self.assertTrue(boundary.ui.qt.opened);self.assertEqual('home',boundary.ui.qt.page)
        self.assertEqual(reference,TabletWebAppOwner(boundary.runtime).prepare('b'*32))


if __name__=='__main__':unittest.main()
