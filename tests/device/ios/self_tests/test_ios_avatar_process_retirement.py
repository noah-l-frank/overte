"""Avatar failure cleanup retains the actual role-owned OS retirement source."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.self_tests import test_ios_process_retirement as fixture


class AvatarProcessRetirementTests(fixture.ProcessRetirementTests):
    def owner(self,role='primary'):
        return IOSProcessRetirement(PrivateFeatureState(self.root/filename('avatar',role,0)),self.os.reader(),
            fixture.BINDING,fixture.RUN,role,0,self.lock,profile='avatar')

    def archived(self,owner,*,records=None):
        return IOSProcessRetirement.archive(owner.previous,path=owner.store.path,binding=fixture.BINDING,source=fixture.SOURCE,
            bundle=fixture.BUNDLE,run=fixture.RUN,role=owner.role,stage=0,records=records,profile='avatar')

    def test_another_feature_namespace_cannot_relabel_avatar_os_originals(self):
        with self.lock.held():
            owner=self.owner();self.finish(owner)
            with self.assertRaises(NativeUIError):
                IOSProcessRetirement.archive(owner.previous,path=self.root/filename('navigation','primary',0),binding=fixture.BINDING,
                    source=fixture.SOURCE,bundle=fixture.BUNDLE,run=fixture.RUN,role='primary',stage=0,profile='avatar')
