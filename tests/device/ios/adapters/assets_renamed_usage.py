"""Ordinary model use after an independently proved owned folder rename."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.assets_tree_owner import OwnedAssetsTree
from ios.adapters.assets_usage_owner import OwnedAssetsUsage


class RenamedAssetsUsage(OwnedAssetsUsage):
    OWNER_VERSION=2
    TREE_TYPE=OwnedAssetsTree
    EXTRA_FIELDS=frozenset({'renamedTree'})
    def __init__(self,*args,tree,**kwargs):
        need(type(tree) is self.TREE_TYPE);self.tree=tree
        super().__init__(*args,**kwargs)
        need(tree.upload is self.source and tree.lock is self.lock and tree.store.path.parent==self.store.path.parent)
    def directory(self):return self.tree.prefix(True)
    def rename_guard(self):
        tree=self.tree
        need(tree.state is not None and tree.state['phase'] in ('renamed','deleting','deleted')
            and same(tree.store.read(),tree.previous) and same(tree.decode(tree.previous),tree.state))
        return True
    def extra_envelope(self):
        self.rename_guard();tree=self.tree
        return dict(renamedTree=dict(path=str(tree.store.path),fileOwnerToken=tree.upload.files.state['token'],
            renamedInventorySha256=digest(tree.read_proof('tree-renamed'))))
    def envelope_guard(self):return self.rename_guard()
