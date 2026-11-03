"""Same private state IO with the exact admitted Navigation root directory.

Canonical admission precedes opening the original directory. Every inherited
_parent boundary still obtains a fresh kernel path/full directory/OFD proof.
No pathname/stat verdict is cached and failed originals cannot be readopted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState


class NavigationSceneRootState(PrivateFeatureState):
    def __init__(self,path,directory):
        super().__init__(path)
        need(type(directory) is OriginalDescriptor)
        self.directory=self.original_directory=directory
        self.original_path=self.path;self.parent_path=self.original_parent_path=self.path.parent
        self.failed=False
        self._parent=self.original_parent_callback=self._parent
        self._parent()

    def _parent(self):
        try:
            need(not self.failed and self.directory is self.original_directory
                and isinstance(self.path,Path) and self.path==self.original_path
                and self.parent_path is self.original_parent_path and self.path.parent==self.parent_path
                and self._parent is self.original_parent_callback)
            require_directory(self.directory,self.parent_path)
        except BaseException:
            self.failed=True;raise
