"""Unbaked parser owner2 with independently supplied actual import action."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from feature_journeys.contract import identifier
from ios.adapters.assets_action_owners import ActionTicket
from ios.adapters.assets_unbaked_input import OwnedAssetsUnbakedInput


class ActionAssetsUnbakedInput(ActionTicket,OwnedAssetsUnbakedInput):
    def __init__(self,*args,action_ticket,**kwargs):
        self.action_ticket=identifier(action_ticket);super().__init__(*args,**kwargs)
    def backend_row(self,index):
        row=super().backend_row(index);need(row['query']['ticket']==self.action_ticket);return row
