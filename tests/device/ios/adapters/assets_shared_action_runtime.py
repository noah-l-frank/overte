"""Explicit current-action factories on canonical SDK roots/episode outputs.

Only source/owner assembly is supplied. Shared29 dispatch, consumed-step and
cleanup-phase admission, complete evidence/global end remain separate gates.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.assets_action_runtime import AssetsActionRuntime
from ios.adapters.assets_stage_recipes import AssetsStageRecipes
from ios.adapters.assets_action_unbaked import ActionAssetsUnbakedInput
from ios.adapters.assets_selected_runtime import SelectedAssetsRuntime
from ios.adapters.assets_page_lease import OwnedAssetsPageLease
from ios.adapters.assets_page_picker import PageLeasePicker
from ios.adapters.assets_page_clients import PageLeaseUpload,PageLeaseTree,PageLeaseOriginalTree,PageLeaseUsage,PageLeaseRenamedUsage
from ios.adapters.assets_action_reply_owner import ActionAssetsReplyReads
from ios.adapters.assets_action_owners import ActionAssetsBaking,ActionAssetsParsed
from ios.adapters.assets_backend_owner import OwnedAssetsBackend
from adapters.asset_backend_client import AssetsBackendClient


class SharedActionAssetsRuntime(AssetsStageRecipes,AssetsActionRuntime,SelectedAssetsRuntime):
    PICKER_OWNER=PageLeasePicker
    REPLIES_OWNER=ActionAssetsReplyReads
    UPLOAD_OWNER=PageLeaseUpload
    BAKING_OWNER=ActionAssetsBaking
    PARSED_OWNER=ActionAssetsParsed
    UNBAKED_OWNER=ActionAssetsUnbakedInput
    def __init__(self,*args,page_lease=None,**kwargs):
        self.assets_page=page_lease;super().__init__(*args,**kwargs)
        episode=self.assets_episode
        if episode is None:
            need(self.assets_action.index==1 and page_lease is None)
        else:
            need(isinstance(page_lease,OwnedAssetsPageLease) and not page_lease.historical and page_lease.episodes is episode.owner
                and self.assets_action.owner.selected is self.assets_selection)
            self.TREE_OWNER=PageLeaseTree if episode.index==2 else PageLeaseOriginalTree
            self.USAGE_OWNER=PageLeaseRenamedUsage if episode.index==2 else PageLeaseUsage
    def _assets_components(self,*args,**kwargs):
        need(self.assets_episode is not None and self.assets_page is not None)
        return super()._assets_components(*args,**kwargs)
    def _ticket(self,index):
        actions=self.assets_action.owner;actions.guard();need(actions.state is not None and same(actions.store.read(),actions.previous)
            and same(actions.envelope(),actions.previous))
        if len(actions.state['records'])>=index:return actions.ticket_for(index)
        pending=actions.state['pending'];need(pending is not None and pending['index']==index)
        actions.phase_packet(pending['before'],index,pending['ticket']);return pending['ticket']
    def _assets_owner_values(self,kind,selector,run,role,lock):
        scope=self.assets_episode;need(scope is not None and role=='primary' and scope.role(selector)==role and scope.owner.run==run
            and lock is scope.locks[role]);lock.assert_held()
        if kind in ('picker','upload'):return dict(page_lease=self.assets_page,episode=scope)
        if kind=='replies':return dict(actions=self.assets_action.owner,episode=scope,action=self.assets_action)
        if kind=='unbaked':
            need(scope.index in (2,3));return dict(action_ticket=self._ticket(8 if scope.index==2 else 15))
        need(scope.index==4 and scope.descriptor['resource']=='asset-stand.fbx')
        if kind=='baking':return dict(action_ticket=self._ticket(20))
        need(kind=='parsed');return dict(action_ticket=self._ticket(21))
    def _assets_usage_values(self,selector,run,role,tree):
        return dict(tree=tree) if self.assets_episode.index==2 else {}
    def _assets_stage_upload_components(self,selector,run,role,fixture_url,lock,backend_config):
        # Action18 cannot reserve an owner challenged by future action20.
        need(self.assets_episode.index==4 and self.assets_action.index==18)
        parts=self._assets_components(selector,run,role,fixture_url,lock)
        backend=OwnedAssetsBackend(parts['upload'],AssetsBackendClient(backend_config,parts['check']),
            self._assets_store(selector,run,role,'backend'),lock=lock)
        parts['check']();return dict(parts,backend=backend)
    def _assets_unbaked_upload_components(self,selector,run,role,fixture_url,lock,backend_config,*,parts=None):
        need(self.assets_episode.index in (2,3) and self.assets_action.index in (4,14))
        parts=self._assets_components(selector,run,role,fixture_url,lock) if parts is None else parts
        need('parsed' not in parts and 'model' not in parts)
        backend=OwnedAssetsBackend(parts['upload'],AssetsBackendClient(backend_config,parts['check']),
            self._assets_store(selector,run,role,'backend'),lock=lock)
        parts['check']();return dict(parts,backend=backend)
