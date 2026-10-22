"""Actual normal Script recipe and Node source; native/Qt/renderer are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.token_script_ui import TokenScriptUI
from adapters.token_script_file_ui import TokenScriptFilePicker
from ios.self_tests import emote_marker_domain_fixture as domain_fixture

# Preserve the ordinary actual Web code; extend only the explicit modeled SDK
# with the Camera and real signal APIs that this world-only script consumes.
PROGRAM=domain_fixture.PROGRAM.replace('Entities:{addEntity:',
    'Entities:{webEventReceived:{connect() {},disconnect() {}},emitScriptEvent() {},addEntity:').replace(
    'MyAvatar:{position:', 'Camera:{position:{x:0,y:1.6,z:7},orientation:{x:0,y:0,z:0,w:1}},MyAvatar:{position:')


class WorldWebDomain(domain_fixture.RunningDomain):
    def start(self):
        with patch.object(domain_fixture,'PROGRAM',PROGRAM):super().start()

    def manager(self):
        s=self.scope;ui=TokenScriptUI(self.io,monotonic=lambda:self.time,sleep=self.io.sleep)
        picker=TokenScriptFilePicker(self.io,self.files.root.as_uri(),monotonic=lambda:self.time,sleep=self.io.sleep)
        return NormalScriptManager(ui,self.io.observe,PrivateFeatureState(s.store.path.with_name('ios-worldweb-'+s.role+'-marker-script.json')),
            s.binding,source_kind='script-file-bundle',file_owner=s.files,file_picker=picker,monotonic=lambda:self.time,sleep=self.io.sleep)

    def select_view(self,mode):
        # IOSGraphicsSurface checks this original mode before any native input.
        if self.world_template['source']['view']['mode']==mode:return {'performed':False}
        return super().select_view(mode)
