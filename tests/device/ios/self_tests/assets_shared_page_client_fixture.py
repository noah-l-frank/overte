"""Original upload/tree/usage QML on the real shared-page host fixture.

The native/Qt/service producers remain declared models. Published bytes flow
from original QML callbacks into independent reads, never requested outcomes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads
from ios.adapters.assets_page_clients import PageLeaseUpload
from ios.self_tests.assets_picker_fixture import BINDING,RUN,URL
from ios.self_tests.assets_shared_page_fixture import Boundary as PageBoundary,Fixture as PageFixture
from ios.self_tests.assets_usage_fixture import Boundary as UsageBoundary


class Boundary(UsageBoundary,PageBoundary):pass


class Fixture(PageFixture):
    boundary_type=Boundary
    def cancel_episode(self,index):
        scope=self.begin(index,format(index,'032x'))
        with scope.held():
            picker=self.picker(scope);picker.open_page();picker.open_picker();picker.choose_primary();picker.cancel_owned();picker.retire_inputs()
        return scope
    def upload(self,scope,picker):
        root=Path(scope.descriptor['directories']['primary']['stateRoot']['path']);lock=scope.locks['primary']
        self.boundary.reads.resource=scope.descriptor['resource']
        replies=OwnedAssetsReplyReads(self.boundary.reads.native(),PrivateFeatureState(root/('ios-assets-'+RUN+'-primary-replies.json')),
            BINDING,RUN,URL,lock=lock);replies.reserve(scope.descriptor['ticket'],scope.descriptor['resource'])
        return PageLeaseUpload(picker.native,self.boundary.clock_reader,picker.files,picker,replies,
            PrivateFeatureState(root/('ios-assets-'+RUN+'-primary-upload.json')),BINDING,lock=lock,
            page_lease=self.page,episode=scope,monotonic=self.boundary.monotonic,sleep=self.boundary.sleep)
