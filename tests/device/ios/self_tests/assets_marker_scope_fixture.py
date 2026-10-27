"""Original normal marker Script flow on the closed Assets child namespace.

Only the modeled manager metadata path differs from the existing Create
fixture. The actual staged JS, token inputs, API returns, weak holders and
quiet callbacks retain the same declared host boundaries.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_script_manager import NormalScriptManager
from adapters.token_script_ui import TokenScriptUI
from adapters.token_script_file_ui import TokenScriptFilePicker
from ios.self_tests.create_marker_domain_fixture import RunningDomain


class AssetsMarkerDomain(RunningDomain):
    def manager(self):
        ui=TokenScriptUI(self.io,monotonic=lambda:self.time,sleep=self.io.sleep)
        picker=TokenScriptFilePicker(self.io,self.files.root.as_uri(),monotonic=lambda:self.time,sleep=self.io.sleep)
        return NormalScriptManager(ui,self.io.observe,self.scope.marker_store('script'),self.scope.binding,
            source_kind='script-file-bundle',file_owner=self.scope.files,file_picker=picker,monotonic=lambda:self.time,sleep=self.io.sleep)
