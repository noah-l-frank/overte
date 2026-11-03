"""Versioned local client retirement while the independent page remains alive.

Actual file/work/read-holder quiet sources remain mandatory. A transferred
page is never called dead, and unresolved input effects remain blocking.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.assets_budget import operation
from ios.adapters.assets_controls import project
from ios.adapters.assets_picker import root
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_tree_owner import OwnedAssetsTree
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_renamed_usage import RenamedAssetsUsage
from ios.adapters.assets_page_picker import PageLeasePicker


class PageLeaseUpload(OwnedAssetsUpload):
    OWNER_VERSION=2
    EXTRA_FIELDS=frozenset({'pageLease','episode'})
    def __init__(self,*args,page_lease,episode,**kwargs):
        self.page_lease,self.episode=page_lease,episode
        super().__init__(*args,**kwargs)
        need(type(self.picker) is PageLeasePicker and self.picker.page_lease is page_lease and self.picker.episode is episode
            and self.lock is episode.locks['primary'] and self.files is self.picker.files)
    def extra_envelope(self):return dict(pageLease=self.page_lease.link(),episode=self.episode.link())
    def cleanup_phase(self):return 'page-borrowed-quiet'
    def cleanup_page(self,current,state):return self.picker.cleanup_page(current,state)
    def cleanup_home(self):self.page_lease.live(self.episode);self.cleanup_page(self.current(),self.state)
    def retire_unresolved(self,index):need(all(entry['resolvedBy'] is not None and entry['abandonedBy'] is None for entry in self.state['inputs']))
    @operation
    def cleanup(self,*,abort=False):
        self.page_lease.live(self.episode)
        # An alive page cannot retire uncertain native/QML input effects merely
        # by setting an abandonment index. Resolve the original effect first.
        self.retire_unresolved(0)
        packet=super().cleanup(abort=abort)
        need(self.files.state['phase']=='retired' and self.replies.state['phase']=='closed')
        if self.picker.state['phase']!=self.picker.retirement_phase():
            self.picker.capture();self.picker.state['cleanupWindow']=dict(kind='cleanup',**deepcopy(self.state['cleanupWindow']))
            self.picker.state['phase']=self.picker.retirement_phase();self.picker.save()
        self.page_lease.transferred(self.episode,self.picker);return packet


class PageClients:
    def client_page(self,packet,state):
        source=self.upload if hasattr(self,'upload') else self.source
        need(type(source) is PageLeaseUpload);return source.cleanup_page(project(packet),source.state)
    def retire_unresolved(self,index):need(all(entry['resolvedBy'] is not None and entry['abandonedBy'] is None for entry in self.state['inputs']))
    def close_clients(self):
        self.retire_unresolved(0);return super().close_clients()


class PageLeaseTree(PageClients,OwnedAssetsTree):
    OWNER_VERSION=3
    EXTRA_FIELDS=frozenset({'pageLease','episode'})
    def extra_envelope(self):
        need(type(self.upload) is PageLeaseUpload);return self.upload.extra_envelope()


class PageLeaseOriginalTree(PageLeaseTree):
    OWNER_VERSION=4
    RENAME_REQUIRED=False
    EXTRA_FIELDS=PageLeaseTree.EXTRA_FIELDS|frozenset({'treePolicy'})
    def extra_envelope(self):return dict(super().extra_envelope(),treePolicy=dict(renameRequired=False))


class PageLeaseUsage(PageClients,OwnedAssetsUsage):
    OWNER_VERSION=3
    EXTRA_FIELDS=frozenset({'pageLease','episode'})
    def extra_envelope(self):
        need(type(self.source) is PageLeaseUpload);return self.source.extra_envelope()


class PageLeaseRenamedUsage(PageClients,RenamedAssetsUsage):
    OWNER_VERSION=4
    TREE_TYPE=PageLeaseTree
    EXTRA_FIELDS=RenamedAssetsUsage.EXTRA_FIELDS|frozenset({'pageLease','episode'})
    def extra_envelope(self):
        need(type(self.source) is PageLeaseUpload)
        return dict(super().extra_envelope(),**self.source.extra_envelope())
