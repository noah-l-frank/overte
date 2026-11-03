"""Explicit ordinary deletion of an unrenamed owned bundle namespace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.assets_tree_owner import OwnedAssetsTree


class OwnedAssetsOriginalTree(OwnedAssetsTree):
    OWNER_VERSION=2
    RENAME_REQUIRED=False
    EXTRA_FIELDS=frozenset({'treePolicy'})
    def extra_envelope(self):return dict(treePolicy=dict(renameRequired=False))
